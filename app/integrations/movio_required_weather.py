"""Require an actual pickup/drop forecast before MOVIO voice confirmation.

Uses the existing Open-Meteo provider and the existing voice, route and database
implementations. Provider reference: https://open-meteo.com/en/docs
"""
import copy
import inspect
import json
import logging
import math
import threading
import time
from datetime import datetime
from pathlib import Path

VERSION='required-spoken-weather-1.0'
ROLES=('pickup','destination')


def logger_for(root):
    path=Path(root)/'required_weather.log'
    logger=logging.getLogger('movio.required_weather.'+str(path.resolve()))
    logger.setLevel(logging.INFO);logger.propagate=False
    if not logger.handlers:
        handler=logging.FileHandler(path,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'));logger.addHandler(handler)
    return logger


def log(logger,event,**details):
    logger.info(json.dumps(dict(event=event,**details),ensure_ascii=False,default=str))


def number(value,low=None,high=None):
    if value is None or isinstance(value,bool):return None
    try:value=float(value)
    except (ValueError,TypeError,OverflowError):return None
    return value if math.isfinite(value) and (low is None or value>=low) and (high is None or value<=high) else None


def complete(weather):
    if not isinstance(weather,dict) or weather.get('status')!='ok':return False
    if weather.get('condition') not in ('rain','cloudy','clear','other'):return False
    points=weather.get('points')
    if not isinstance(points,list) or len(points)!=2:return False
    for role in ROLES:
        rows=[p for p in points if isinstance(p,dict) and p.get('location')==role]
        if len(rows)!=1:return False
        code=number(rows[0].get('weather_code'),0,99)
        if code is None or not code.is_integer() or number(rows[0].get('precipitation_probability'),0,100) is None:return False
    return True


class ProviderFailure(Exception):
    def __init__(self,reason,status=None):self.reason,self.status=reason,status;super().__init__(reason)


class Forecast:
    def __init__(self,base,engine,root):
        self.base,self.engine=base,engine;self.logger=logger_for(root)
        self.cache={};self.lock=threading.RLock();self.blocked_until=0;self.last_error=None
        self.requests=0
    def __getattr__(self,name):return getattr(self.base,name)
    def pending(self,reason,status=None):
        self.last_error=dict(reason=reason,http_status=status)
        log(self.logger,'weather_check_pending',**self.last_error)
        return dict(status='pending',source='Open-Meteo',reason=reason,http_status=status,policy=VERSION)
    def fetch(self,points,pickup):
        """MOVIO_INDEPENDENT_FORECAST_V1: one HTTP response per requested point."""
        getter=getattr(self.base,'getter',None)
        if not callable(getter):
            import requests
            getter=requests.get
        target=pickup.replace(minute=0,second=0,microsecond=0).strftime('%Y-%m-%dT%H:%M')
        # Snapshot coordinates before issuing requests; never modify caller data.
        requested=[dict(lat=float(p['lat']),lng=float(p['lng'])) for p in points]
        result=[]
        for requested_point in requested:
            params=dict(latitude=str(requested_point['lat']),longitude=str(requested_point['lng']),
                hourly='weather_code,precipitation_probability,precipitation,temperature_2m,apparent_temperature',
                timezone='Asia/Kolkata',timeformat='iso8601',temperature_unit='celsius',
                start_date=pickup.date().isoformat(),end_date=pickup.date().isoformat())
            response=None
            try:
                self.requests+=1
                response=getter('https://api.open-meteo.com/v1/forecast',params=params,timeout=(3,6))
                response.raise_for_status();payload=response.json()
                if isinstance(payload,dict) and payload.get('error'):
                    raise ProviderFailure('provider_rejected_query',getattr(response,'status_code',None))
                # A single-coordinate call must not borrow another response row.
                if isinstance(payload,list):
                    if len(payload)!=1:raise ProviderFailure('invalid_location_count')
                    payload=payload[0]
                if not isinstance(payload,dict):raise ProviderFailure('invalid_location_response')
                if payload.get('utc_offset_seconds') is not None and number(payload['utc_offset_seconds'])!=19800:
                    raise ProviderFailure('unexpected_forecast_timezone')
                units=payload.get('hourly_units') or {}
                if isinstance(units,dict) and units.get('temperature_2m') not in (None,'°C','celsius'):
                    raise ProviderFailure('unexpected_temperature_unit')
                hourly=payload['hourly'];times=hourly['time']
                if not isinstance(times,list) or times.count(target)!=1:
                    raise ProviderFailure('requested_hour_missing_or_duplicated')
                index=times.index(target)
                code=number(hourly['weather_code'][index],0,99)
                chance=number(hourly['precipitation_probability'][index],0,100)
                if code is None or not code.is_integer() or chance is None:
                    raise ProviderFailure('missing_hourly_condition_or_probability')
                point=dict(valid_at=target,weather_code=int(code),precipitation_probability=chance,
                    requested_latitude=requested_point['lat'],requested_longitude=requested_point['lng'],
                    provider_latitude=number(payload.get('latitude'),-90,90),
                    provider_longitude=number(payload.get('longitude'),-180,180),forecast_timezone='Asia/Kolkata')
                for key in ('precipitation','temperature_2m','apparent_temperature'):
                    values=hourly.get(key);point[key]=number(values[index]) if isinstance(values,list) and index<len(values) else None
                result.append(point)
            except ProviderFailure:raise
            except Exception as exc:
                status=getattr(getattr(exc,'response',None),'status_code',None)
                if status is None:status=getattr(response,'status_code',None)
                reason='http_error' if isinstance(status,int) and status>=400 else 'timeout' if 'timeout' in type(exc).__name__.lower() else 'invalid_hourly_response' if isinstance(exc,(ValueError,KeyError,IndexError,TypeError)) else 'connection_error'
                log(self.logger,'weather_request_failed',reason=reason,http_status=status,error_type=type(exc).__name__,locations=1)
                if status==429:
                    try:retry=float(response.headers.get('Retry-After','30'))
                    except (ValueError,TypeError,AttributeError):retry=30
                    self.blocked_until=time.monotonic()+max(1,min(3600,retry))
                raise ProviderFailure(reason,status) from exc
        return result
    def forecast(self,points,pickup,now=None):
        """MOVIO_INDEPENDENT_FORECAST_V1: exact-coordinate, hour-specific cache."""
        zone=self.engine['TZ'];now=now or datetime.now(zone)
        pickup=datetime.fromisoformat(pickup) if isinstance(pickup,str) else pickup
        pickup=pickup.replace(tzinfo=zone) if pickup.tzinfo is None else pickup.astimezone(zone)
        now=now.replace(tzinfo=zone) if now.tzinfo is None else now.astimezone(zone)
        if not 0<=(pickup.date()-now.date()).days<16:return self.pending('outside_forecast_window')
        if len(points)!=2 or not all(self.engine['valid_geo'](point) for point in points):return self.pending('invalid_location_coordinates')
        target=pickup.replace(minute=0,second=0,microsecond=0).isoformat()
        points=[dict(lat=float(p['lat']),lng=float(p['lng'])) for p in points]
        key=('MOVIO_INDEPENDENT_FORECAST_V1',tuple((p['lat'],p['lng']) for p in points),target)
        with self.lock:
            cached=self.cache.get(key);ttl=max(1,min(900,float(getattr(self.base,'ttl',900))))
            if cached and time.monotonic()-cached[0]<ttl:return copy.deepcopy(cached[1])
            if time.monotonic()<self.blocked_until:return self.pending('rate_limit_backoff',429)
            try:rows=self.fetch(points,pickup)
            except ProviderFailure as exc:return self.pending(exc.reason,exc.status)
            rows=[copy.deepcopy(row) for row in rows]
            for role,row in zip(ROLES,rows):row['location']=role
            rain=any(row['weather_code'] in self.engine['RAIN_CODES'] or row['precipitation_probability']>=getattr(self.base,'rain_threshold',60) for row in rows)
            cloudy=any(row['weather_code'] in (2,3) for row in rows);clear=all(row['weather_code'] in (0,1) for row in rows)
            heat=any(row['temperature_2m'] is not None and row['temperature_2m']>=getattr(self.base,'heat_c',38)
                or row['apparent_temperature'] is not None and row['apparent_temperature']>=getattr(self.base,'feels_like_c',40) for row in rows)
            result=dict(status='ok',source='Open-Meteo',points=rows,fetched_at=time.time(),policy=VERSION,
                condition='rain' if rain else 'cloudy' if cloudy else 'clear' if clear else 'other',
                heavy_rain=any(row['weather_code'] in (65,67,82) for row in rows),
                thunderstorm=any(row['weather_code'] in (95,96,97,99) for row in rows),heat=heat,
                pleasant=clear and not heat and all(row['temperature_2m'] is not None and 18<=row['temperature_2m']<=32 for row in rows),
                scope='pickup_and_destination_at_pickup_hour',lookup_mode='independent_per_location')
            self.cache[key]=(time.monotonic(),copy.deepcopy(result));self.last_error=None
            if len(self.cache)>256:self.cache.pop(next(iter(self.cache)))
            log(self.logger,'weather_forecast_ready',valid_at=target,probabilities=[row['precipitation_probability'] for row in rows])
            return result


def speech_registrar(engine):
    # The notebook's weather/closing quality cell stores its existing register
    # function in the completion wrapper. Reuse that exact speech-quality path.
    function=engine.get('completion_message')
    try:register=inspect.getclosurevars(function).nonlocals.get('register')
    except (TypeError,ValueError):return None
    return register if callable(register) else None


def waiting_text(state,engine):
    reason=(state.get('weather') or {}).get('reason')
    if reason=='outside_forecast_window':
        return engine['localized'](state['lang'],
            'Your selected date is kept. The weather check must be repeated closer to your journey.',
            'நீங்கள் தேர்ந்தெடுத்த தேதி உள்ளது. பயண நாளுக்கு அருகில் வானிலையை மீண்டும் சரிபார்க்க வேண்டும்.',
            'Neenga sonna date irukku. Journey date nerungumbodhu weather check thirumba pannanum.')
    return engine['localized'](state['lang'],
        'Please say “check weather again” to retry the weather check. Your journey details are kept.',
        'வானிலையை மீண்டும் சரிபார்க்க, “மீண்டும் சரிபாருங்கள்” என்று சொல்லுங்கள். உங்கள் பயண விவரங்கள் உள்ளன.',
        'Weather thirumba check panna, “check weather again” sollunga. Unga journey details irukku.')


def install_namespace(engine,root=None,bridge=None):
    root=Path(root or Path(engine['__file__']).resolve().parent.parent)
    if engine.get('_MOVIO_REQUIRED_WEATHER_VERSION')==VERSION:
        return dict(version=VERSION,already_installed=True,weather_mandatory=True,
            stable_weather_audio_registry=callable(speech_registrar(engine)),log=str(root/'required_weather.log'))
    previous=engine['prepare_turn'];previous_consent=engine['weather_consented'];previous_advisory=engine['advisory']
    previous_install=engine['install_bridge'];previous_segments=engine['speech_segments']
    optional=engine.get('_movio_optional_weather_original') or {}
    base_prepare=optional.get('prepare_turn');base_consent=optional.get('weather_consented')
    if not callable(base_prepare) or not callable(base_consent):raise RuntimeError('Run the existing optional-weather fix before this cell.')
    # Keep the compact existing language/vehicle advisory; only successful,
    # complete actual forecasts may enter the weather-consent stage.
    logger=logger_for(root);spoken=[];lock=threading.RLock();register=speech_registrar(engine)
    def advisory(state):
        if not complete(state.get('weather')):return ''
        text=previous_advisory(state)
        if callable(register):text=register(text,'weather')
        with lock:
            spoken.append(text)
            if len(spoken)>128:del spoken[:-128]
        return text
    def speech_segments(text):
        with lock:is_weather=any(prefix and (text==prefix or str(text).startswith(prefix+'\n') or str(text).startswith(prefix+' ')) for prefix in spoken)
        return [str(text)] if is_weather else previous_segments(text)
    def weather_consented(state):
        if state.get('_wx_required_weather')==VERSION:
            return complete(state.get('weather')) and base_consent(state)
        return previous_consent(state)
    def proxy(b,weather):
        current=getattr(b,'_wx_required_forecast',None)
        if not isinstance(current,Forecast) or current.base is not weather:
            current=Forecast(weather,engine,root);b._wx_required_forecast=current
        return current
    def prepare_turn(b,weather,state,text,now=None):
        state['_wx_required_weather']=VERSION
        if isinstance(state.get('weather'),dict):state['weather'].pop('_optional_skip',None)
        is_yes=engine['reply_normalized'](text) in engine['POSITIVE']
        frozen=state.get('stage') in ('confirm','fare','booking_pending') and state.get('dialogue_state') in ('AWAITING_BOOKING_CONFIRMATION','BOOKING_IN_PROGRESS')
        # A final Yes must continue the same reviewed journey, without redoing
        # weather/route lookup or restarting the separate consent flow.
        if frozen and (not str(text).strip() or is_yes) and weather_consented(state):
            return previous(b,weather,state,text,now=now)
        if not complete(state.get('weather')):state.pop('_wx_forecast_scope',None)
        normalizer=engine.get('_movio_weather_normalize')
        if callable(normalizer):
            for role in ROLES:
                if state.get(role):
                    name=normalizer(state[role],role)
                    if name and name!=state[role]:state[role]=name;state[role+'_geo']=None;state['fare']=None
        state,answer=base_prepare(b,proxy(b,weather),state,text,now=now)
        if state.get('stage')=='weather_advisory' and not complete(state.get('weather')):
            state['stage']='weather_pending';state['dialogue_state']='WEATHER_LOOKUP_PENDING'
            state.pop('_wx_weather_consent',None)
            log(logger,'confirmation_waiting_for_actual_weather',reason=(state.get('weather') or {}).get('reason'))
            return state,waiting_text(state,engine)
        state['dialogue_state']='WEATHER_ADVISORY' if state.get('stage')=='weather_advisory' else 'AWAITING_BOOKING_CONFIRMATION' if state.get('stage')=='confirm' else 'COLLECTING_DETAILS'
        return state,answer
    def install_bridge(b,db_path,weather=None,_route_wrapper=None):
        return previous_install(b,db_path,weather=weather,_route_wrapper=_route_wrapper)
    engine.update(prepare_turn=prepare_turn,weather_consented=weather_consented,advisory=advisory,speech_segments=speech_segments,
        install_bridge=install_bridge,_MOVIO_REQUIRED_WEATHER_VERSION=VERSION,
        _movio_required_weather_original=dict(prepare_turn=previous,weather_consented=previous_consent,advisory=previous_advisory,speech_segments=previous_segments),
        _movio_required_weather_proxy=proxy)
    return dict(version=VERSION,weather_mandatory=True,stable_weather_audio_registry=callable(register),log=str(root/'required_weather.log'))
