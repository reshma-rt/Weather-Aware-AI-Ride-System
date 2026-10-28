"""Optional, shared weather lookup for the existing MOVIO booking guard.

No model, user interface, booking transaction or evaluation implementation is replaced.
Provider contract: https://open-meteo.com/en/docs
"""
import copy
import importlib.util
import json
import logging
import math
import re
import sys
import threading
import time
import types
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

VERSION='optional-weather-1.0'
TZ=ZoneInfo('Asia/Kolkata')
PLACE_ALIASES={'Chennai Central': ('chennai central', 'central railway station', 'சென்னை சென்ட்ரல்', 'சென்னை சென்ட்ரலில்', 'சென்ட்ரலில்', 'சென்ட்ரல்', 'சென்னை மத்திய'), 'Chennai Airport': ('chennai airport', 'chennai international airport', 'சென்னை ஏர்போர்ட்', 'சென்னை விமான நிலையம்'), 'Kottivakkam': ('kottivakkam', 'கொட்டிவாக்கம்'), 'Chromepet': ('chromepet', 'chrome pit', 'chrompet', 'குரோம்பேட்டை', 'குரோம்பேட்'), 'Velachery': ('velachery', 'வேளச்சேரி'), 'T Nagar': ('t nagar', 't. nagar', 'டி நகர்', 'தியாகராய நகர்'), 'Anna Nagar': ('anna nagar', 'அண்ணா நகர்')}
_SCOPE_KEYS=('pickup','destination','pickup_at','pickup_geo','destination_geo')
_FAILED={'unavailable','outside_forecast_range'}
_RESIDUAL_SUFFIX=re.compile(r'(?:இலிருந்து|லிருந்து|லேர்ந்து|லருந்து|இல்\s*இருந்து|(?:\s|-)இருந்து|க்கு|வரை|\b(?:la\s*irun[dt]hu|il\s*irun[dt]hu|ilirun[dt]hu|lirun[dt]hu|lerndhu|varai|varaikkum))\s*$',re.I)

def configure_logger(root):
    path=Path(root)/'weather_lookup.log'
    logger=logging.getLogger('movio.weather_lookup.'+str(path.resolve()))
    logger.setLevel(logging.INFO);logger.propagate=False
    if not logger.handlers:
        handler=logging.FileHandler(path,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
    return logger

def log_failure(logger,reason,**details):
    logger.warning(json.dumps({'event':'weather_lookup_failed','reason':reason,**details},ensure_ascii=False,default=str))

def unavailable(reason,logger,status='unavailable',**details):
    log_failure(logger,reason,**details)
    return {'status':status,'source':'Open-Meteo','reason':reason,'checked_at':time.time()}

def numeric(value,lo=None,hi=None):
    try:
        result=float(value)
        if not math.isfinite(result) or lo is not None and result<lo or hi is not None and result>hi:return None
        return result
    except (TypeError,ValueError,OverflowError):return None

def usable(weather):
    if not isinstance(weather,dict) or weather.get('status')!='ok':return False
    points=weather.get('points')
    # Existing adapters can supply a condition without probability estimates.
    if points is None:return weather.get('condition') in ('rain','cloudy','clear')
    return bool(isinstance(points,list) and points and all(isinstance(p,dict) for p in points) and weather.get('condition') in ('rain','cloudy','clear','other')
        and any(isinstance(p,dict) and (numeric(p.get('weather_code')) is not None
            or numeric(p.get('precipitation_probability'),0,100) is not None
            or numeric(p.get('temperature_2m')) is not None) for p in points))

def load_slots(path):
    spec=importlib.util.spec_from_file_location('_movio_weather_place_rules',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if not callable(getattr(module,'extract_fields',None)) or not str(getattr(module,'VERSION','')).startswith('group-slots-'):
        raise RuntimeError('Run the updated pickup/destination extraction cell first.')
    return module

def make_normalizer(slots,engine,bridge=None):
    aliases=dict(PLACE_ALIASES)
    aliases.update(getattr(bridge,'VOICE_PLACE_ALIASES',{}) if bridge is not None else {})
    canonicalizer=getattr(bridge,'canonical_place',None) if bridge is not None else None
    proxy=types.SimpleNamespace(VOICE_PLACE_ALIASES=aliases,
        GROUP_PLACE_ALIASES=getattr(bridge,'GROUP_PLACE_ALIASES',{}) if bridge is not None else {},
        canonical_place=canonicalizer if callable(canonicalizer) else lambda x:x)
    parser=slots.Parser(proxy,{},'',engine)
    def normalize(value,role='pickup'):
        result=parser.clean_place(value,role)
        # Unknown inflected words are retained in dialogue memory, but cannot be
        # sent verbatim to geocoding. Registered forms are resolved above.
        return result if result and not _RESIDUAL_SUFFIX.search(result) else None
    return normalize

def forecast(client,points,pickup,now,engine,logger):
    """Same coordinate-based Open-Meteo query for every dialogue language."""
    try:
        if not isinstance(pickup,datetime):pickup=datetime.fromisoformat(str(pickup))
        pickup=pickup.replace(tzinfo=TZ) if pickup.tzinfo is None else pickup.astimezone(TZ)
        now=now or datetime.now(TZ)
        now=now.replace(tzinfo=TZ) if now.tzinfo is None else now.astimezone(TZ)
        horizon=(pickup.date()-now.date()).days
        if not 0<=horizon<16:return unavailable('outside_forecast_range',logger,status='outside_forecast_range')
        if len(points)!=2 or not all(engine['valid_geo'](p) for p in points):
            return unavailable('invalid_coordinates',logger)
        coords=tuple((round(float(p['lat']),5),round(float(p['lng']),5)) for p in points)
    except Exception as exc:return unavailable('invalid_weather_query',logger,error_type=type(exc).__name__)
    key=(VERSION,coords,pickup.date().isoformat())
    target=pickup.replace(minute=0,second=0,microsecond=0).strftime('%Y-%m-%dT%H:%M')
    with client.lock:
        cached=client.cache.get(key)
        valid_cache=bool(cached and time.monotonic()-cached[0]<client.ttl)
        if valid_cache:
            client.hits+=1;payload,fetched=cached[1],cached[2]
        else:
            failure_cache=getattr(client,'_movio_weather_failures',{})
            failed=failure_cache.get(key)
            if failed and time.monotonic()-failed[0]<20:return copy.deepcopy(failed[1])
            client.requests+=1
    if not valid_cache:
        response=None
        try:
            # Explicit dates and local timezone select the customer's booking
            # hour. Both locations are requested together, using coordinates.
            response=client.getter('https://api.open-meteo.com/v1/forecast',params={
                'latitude':','.join(str(p[0]) for p in coords),'longitude':','.join(str(p[1]) for p in coords),
                'hourly':'weather_code,precipitation_probability,precipitation,temperature_2m,apparent_temperature',
                'timezone':'Asia/Kolkata',
                'start_date':pickup.date().isoformat(),'end_date':pickup.date().isoformat()},timeout=(3,5))
            response.raise_for_status();payload=response.json()
            payload=payload if isinstance(payload,list) else [payload]
            if len(payload)!=2 or any(not isinstance(p,dict) or p.get('error') for p in payload):
                raise ValueError('invalid_location_response')
            fetched=time.time()
        except Exception as exc:
            status=getattr(getattr(exc,'response',None),'status_code',None)
            if status is None:status=getattr(response,'status_code',None)
            reason='http_error' if isinstance(status,int) and status>=400 else 'timeout' if 'timeout' in type(exc).__name__.lower() else 'request_or_response_error'
            result=unavailable(reason,logger,error_type=type(exc).__name__,http_status=status,provider_message=str(getattr(response,'text',''))[:250] if status == 400 else None)
            with client.lock:
                failures=getattr(client,'_movio_weather_failures',None)
                if failures is None:failures={};client._movio_weather_failures=failures
                failures[key]=(time.monotonic(),result)
                if len(failures)>256:failures.pop(next(iter(failures)))
            return result
    rows=[]
    try:
        for name,item in zip(('pickup','destination'),payload):
            hourly=item['hourly'];index=hourly['time'].index(target)
            code=numeric(hourly['weather_code'][index])
            if code is None or not code.is_integer() or not 0<=code<=99:raise ValueError('missing_condition')
            row={'location':name,'valid_at':target,'weather_code':int(code)}
            for field in ('precipitation_probability','precipitation','temperature_2m','apparent_temperature'):
                values=hourly.get(field)
                value=numeric(values[index]) if isinstance(values,list) and index<len(values) else None
                if field=='precipitation_probability' and value is not None and not 0<=value<=100:value=None
                row[field]=value
            rows.append(row)
    except Exception as exc:
        return unavailable('missing_or_invalid_hourly_data',logger,error_type=type(exc).__name__,requested_hour=target)
    if not valid_cache:
        with client.lock:
            client.cache[key]=(time.monotonic(),payload,fetched)
            if len(client.cache)>256:client.cache.pop(next(iter(client.cache)))
    rain=any(p['weather_code'] in engine['RAIN_CODES'] or p['precipitation_probability'] is not None and p['precipitation_probability']>=client.rain_threshold for p in rows)
    cloudy=any(p['weather_code'] in (2,3) for p in rows);clear=all(p['weather_code'] in (0,1) for p in rows)
    heat=any(p['temperature_2m'] is not None and p['temperature_2m']>=client.heat_c
        or p['apparent_temperature'] is not None and p['apparent_temperature']>=client.feels_like_c for p in rows)
    return {'status':'ok','source':'Open-Meteo','points':rows,'fetched_at':fetched,
        'condition':'rain' if rain else 'cloudy' if cloudy else 'clear' if clear else 'other',
        'heavy_rain':any(p['weather_code'] in (65,67,82) for p in rows),
        'thunderstorm':any(p['weather_code'] in (95,96,97,99) for p in rows),'heat':heat,
        'pleasant':clear and not heat and all(p['temperature_2m'] is not None and 18<=p['temperature_2m']<=32 for p in rows),
        'scope':'pickup_and_destination_at_pickup_hour',
        'advisory_thresholds':{'rain_probability_pct':client.rain_threshold,'heat_c':client.heat_c,'feels_like_c':client.feels_like_c}}

class SafeWeather:
    def __init__(self,weather,logger):self.weather,self.logger=weather,logger
    def __getattr__(self,name):return getattr(self.weather,name)
    def forecast(self,*args,**kwargs):
        try:result=self.weather.forecast(*args,**kwargs)
        except Exception as exc:return unavailable('forecast_exception',self.logger,error_type=type(exc).__name__)
        if usable(result):return result
        if isinstance(result,dict) and result.get('status') in _FAILED:
            result=dict(result);result.setdefault('reason',result['status']);result.setdefault('checked_at',time.time())
            return result
        return unavailable('invalid_forecast_result',self.logger)

def probability_text(state,engine):
    if not usable(state.get('weather')):return ''
    language=state.get('lang','English');pieces=[]
    for role in ('pickup','destination'):
        row=next((r for r in state['weather'].get('points',[]) if r.get('location')==role),{})
        chance=numeric(row.get('precipitation_probability'),0,100)
        if chance is None:continue
        value=engine['numeric_text'](chance);name=state.get(role) or ('pickup' if role=='pickup' else 'drop')
        label='pickup' if role=='pickup' else 'drop'
        pieces.append(engine['localized'](language,f'At your {label} location, {name}: {value}% rain chance.',
            f'{name} பகுதியில் மழை வாய்ப்பு {value}%.',f'{name}-la mazhai chance {value}%.'))
    return '\n'.join(pieces)

def compact_advisory(state,engine,precautions=True):
    weather=state.get('weather') or {}
    if not usable(weather):return ''
    language=state.get('lang','English');loc=lambda en,ta,rom:engine['localized'](language,en,ta,rom)
    parts=[probability_text(state,engine)];condition=weather.get('condition')
    if weather.get('thunderstorm'):parts.append(loc('Thunderstorms are expected.','இடியுடன் மழை எதிர்பார்க்கப்படுகிறது.','Idiyudan rain expected.'))
    elif weather.get('heavy_rain'):parts.append(loc('Heavy rain is expected.','கனமழை எதிர்பார்க்கப்படுகிறது.','Kanamazhai expected.'))
    elif condition=='rain':parts.append(loc('Rain is expected.','மழை எதிர்பார்க்கப்படுகிறது.','Mazhai vara vaaippu irukku.'))
    elif condition=='cloudy':parts.append(loc('Cloudy weather is expected.','மேகமூட்டம் எதிர்பார்க்கப்படுகிறது.','Cloudy weather expected.'))
    elif condition=='clear' and not weather.get('heat'):
        parts.append(loc('The weather looks pleasant.' if weather.get('pleasant') else 'Clear skies are expected.',
            'வானிலை நன்றாக இருக்கும்.' if weather.get('pleasant') else 'வானம் தெளிவாக இருக்கும்.',
            'Weather nalla irukkum.' if weather.get('pleasant') else 'Clear weather expected.'))
    if weather.get('heat'):parts.append(loc('Very hot weather is expected; carry water.','வெப்பம் அதிகமாக இருக்கும்; குடிநீர் எடுத்துக்கொள்ளுங்கள்.','Very hot weather expected; water eduthukkonga.'))
    if precautions and condition=='rain':
        if state.get('vehicle')=='Bike':
            choices=[v for v in ('Mini','Sedan','SUV') if engine['CAPACITY'][v]>=int(state.get('count') or 1)]
            names=', '.join(choices)
            if names:
                severity=bool(weather.get('heavy_rain') or weather.get('thunderstorm'))
                en=('A bike may be unsuitable; ' if severity else '')+f'covered options are {names}. The choice is yours.'
                parts.append(loc(en,
                    'மூடிய வாகனம் சிறந்தது: '+', '.join(engine['VEHICLES_TA'][v] for v in choices)+'. முடிவு உங்களுடையது.',
                    'Covered vehicle better: '+names+'. Unga choice.'))
        elif state.get('vehicle')=='Auto':parts.append(loc('An auto has exposed sides; carry an umbrella.','ஆட்டோவின் பக்கங்களில் மழை படலாம்; குடை எடுத்துக்கொள்ளுங்கள்.','Auto sides-la rain padalaam; umbrella eduthukkonga.'))
        else:parts.append(loc('Carry an umbrella for boarding.','வாகனத்தில் ஏறுவதற்குக் குடை எடுத்துக்கொள்ளுங்கள்.','Vehicle-la era umbrella eduthukkonga.'))
    return '\n'.join(p for p in parts if p)

def install_namespace(engine,root=None,bridge=None,slots=None):
    root=Path(root or Path(engine['__file__']).resolve().parent.parent)
    logger=configure_logger(root)
    if engine.get('_MOVIO_OPTIONAL_WEATHER_VERSION')==VERSION:
        if bridge is not None:install_geocoder(bridge,engine['_movio_weather_normalize'],logger)
        return {'version':VERSION,'already_installed':True,'log':str(root/'weather_lookup.log')}
    required=('prepare_turn','weather_consented','WeatherClient','collect_details','manual_state','install_backend','probability_report')
    if any(not callable(engine.get(k)) for k in required):raise RuntimeError('The original weather guard is not active.')
    slots=slots or load_slots(root/'integrations/movio_group_booking_slots.py')
    normalizer=make_normalizer(slots,engine,bridge)
    original={key:engine[key] for key in required}
    old_forecast=engine['WeatherClient'].forecast
    def normalize_state(state):
        for role in ('pickup','destination'):
            if not state.get(role):continue
            canonical=normalizer(state[role],role)
            if canonical and canonical!=state[role]:
                state[role]=canonical;state[role+'_geo']=None;state['fare']=None
    def scope(state):return engine['digest']({k:state.get(k) for k in _SCOPE_KEYS})
    def weather_consented(state):
        weather=state.get('weather') or {};skip=weather.get('_optional_skip') or {}
        if weather.get('status') in _FAILED and skip.get('policy')==VERSION and skip.get('scope')==scope(state):return True
        return original['weather_consented'](state)
    def collect_details(b,state,text):
        result=original['collect_details'](b,state,text);normalize_state(state);return result
    def prepare_turn(b,weather,state,text,now=None):
        install_geocoder(b,normalizer,logger);normalize_state(state)
        safe=weather if isinstance(weather,SafeWeather) else SafeWeather(weather,logger)
        state,answer=original['prepare_turn'](b,safe,state,text,now=now)
        # An unavailable forecast is optional. This is an explicit skip record,
        # NOT fabricated user consent. Final-summary playback/confirmation and
        # the existing atomic booking transaction remain mandatory.
        if state.get('stage')=='weather_advisory' and not usable(state.get('weather')):
            result=dict(state.get('weather') or {})
            if result.get('status') not in _FAILED:result=unavailable('invalid_forecast_result',logger)
            result.setdefault('reason',result.get('status','unavailable'))
            result['_optional_skip']={'policy':VERSION,'scope':scope(state),'recorded_at':time.time()}
            state['weather']=result;state.pop('_wx_weather_consent',None)
            log_failure(logger,result['reason'],action='skip_optional_advisory',pickup=state.get('pickup'),destination=state.get('destination'),pickup_at=state.get('pickup_at'))
            state,answer=original['prepare_turn'](b,safe,state,'',now=now)
        return state,answer
    def manual_state(data,weather,now=None):
        data=dict(data)
        for role in ('pickup','destination'):
            canonical=normalizer(data.get(role),role)
            if canonical:data[role]=canonical
        result=original['manual_state'](data,SafeWeather(weather,logger),now=now)
        if not usable(result.get('weather')):
            log_failure(logger,(result.get('weather') or {}).get('reason','unavailable'),action='skip_optional_manual_advisory')
        return result
    def patched_forecast(client,points,pickup,now=None):return forecast(client,points,pickup,now,engine,logger)
    def install_backend(module,weather=None):
        result=original['install_backend'](module,weather=weather)
        previous=module.Handler.do_GET
        if not getattr(previous,'_movio_optional_weather_health',False):
            def do_GET(h):
                if h.path.split('?',1)[0]=='/api/weather-booking/optional-health':
                    return h.json(200,{'ok':True,'version':VERSION,'weather_optional':True,'final_confirmation_required':True})
                return previous(h)
            do_GET._movio_optional_weather_health=True;module.Handler.do_GET=do_GET
        return result
    engine['WeatherClient'].forecast=patched_forecast
    engine.update(prepare_turn=prepare_turn,collect_details=collect_details,weather_consented=weather_consented,
        # Preserve the legacy probability report used by evaluation. Customer
        # speech/manual advisories use probability_text directly and never
        # announce missing probabilities. Failed forecasts are silent here too.
        probability_report=lambda s:original['probability_report'](s) if usable(s.get('weather')) else '',
        weather_report=lambda s:compact_advisory(s,engine,False),
        advisory=lambda s:compact_advisory(s,engine),manual_state=manual_state,install_backend=install_backend,
        _MOVIO_OPTIONAL_WEATHER_VERSION=VERSION,_movio_weather_normalize=normalizer,
        _movio_optional_weather_original={**original,'forecast':old_forecast})
    if bridge is not None:install_geocoder(bridge,normalizer,logger)
    return {'version':VERSION,'log':str(root/'weather_lookup.log')}

def install_geocoder(bridge,normalizer,logger):
    original=getattr(bridge,'geocode',None)
    if not callable(original) or getattr(original,'_movio_optional_weather_geo',False):return
    def geocode(name):
        canonical=normalizer(name)
        if not canonical:
            log_failure(logger,'unresolved_location_suffix_or_name',location=str(name)[:120]);return None
        try:
            result=original(canonical)
            if result is None:log_failure(logger,'geocoder_no_match',location=canonical)
            return result
        except Exception as exc:
            log_failure(logger,'geocoder_exception',location=canonical,error_type=type(exc).__name__);return None
    geocode._movio_optional_weather_geo=True;geocode._original_geocode=original
    bridge.geocode=geocode
