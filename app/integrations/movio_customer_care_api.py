"""Authenticated dashboard care using the existing geocoder/weather client.

Browser coordinates are user-supplied location hints, not independently verified
GPS evidence. Weather/locality values are retrieved on the server. This module
does not write bookings, tracking grants, coordinates, or recommendation history.
"""
import copy
import importlib.util
import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

VERSION='customer-care-api-1.0'
ENGINE_VERSION='customer-care-engine-1.1-compatible'
LOG=logging.getLogger('movio.customer_care')


def _load_care(root):
    path=(root/'integrations/movio_customer_care.py').resolve()
    current=sys.modules.get('movio_customer_care')
    if (getattr(current,'VERSION',None)==ENGINE_VERSION
            and Path(getattr(current,'__file__','')).resolve()==path):return current
    spec=importlib.util.spec_from_file_location('movio_customer_care',path)
    care=importlib.util.module_from_spec(spec)
    exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),care.__dict__)
    if care.VERSION!=ENGINE_VERSION:raise RuntimeError('Run the compatible customer-care engine setup first.')
    sys.modules['movio_customer_care']=care
    return care


def _number(value,low,high):
    if isinstance(value,bool) or value is None or value=='':return None
    try:number=float(value)
    except (TypeError,ValueError,OverflowError):return None
    return number if math.isfinite(number) and low<=number<=high else None


def _instant(value):
    try:
        if isinstance(value,(int,float)) and not isinstance(value,bool):
            # Browser GeolocationPosition.timestamp uses milliseconds.
            if value>100000000000:value=value/1000
            return datetime.fromtimestamp(value,timezone.utc)
        if isinstance(value,str):
            parsed=datetime.fromisoformat(value.strip().replace('Z','+00:00'))
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError,TypeError,OverflowError,OSError):pass
    return None


def _delivered(value):
    allowed={'delivered','acknowledged','dismissed'}
    if not isinstance(value,dict):return {}
    return {key:status for key,status in list(value.items())[-128:]
            if isinstance(key,str) and len(key)<=180 and isinstance(status,str) and status in allowed}


def _weather_view(care,result):
    weather=result['weather']
    if weather is None:return dict(status='unavailable')
    codes={point['weather_code'] for point in weather['points']}
    condition=('storm' if weather['storm'] else 'heavy_rain' if weather['heavy_rain'] else
               'rain' if weather['rain'] else 'cloudy' if codes&{2,3} else
               'clear' if codes and codes<={0,1} else 'fog' if codes&{45,48} else 'other')
    return dict(status='ok',source=weather['source'],condition=condition,
                temperature_c=weather['max_temperature_c'],
                rain_probability_pct=weather['max_rain_probability_pct'],
                valid_at=weather['points'][0]['valid_at'],basis='current_hour_forecast')


def dashboard_response(care,context,user,reverse,forecast,now):
    """Pure orchestration except for the TWO injected, existing provider calls."""
    lang=care.LANGUAGES.get(str(context.get('language',context.get('lang','English'))).casefold(),'English')
    safe=dict(lang=lang,care_stage='dashboard',now=now.isoformat(),
              current_location={'status':'unavailable'},current_weather=None,
              care_scope_id='dashboard:'+str(user['id'])+':'+now.date().isoformat())
    location=context.get('current_location')
    if not isinstance(location,dict):location={}
    status=location.get('status')
    status=status if status in {'granted','denied','unavailable','unsupported','timeout'} else 'unavailable'
    safe['current_location']['status']=status
    if status=='granted':
        lat=_number(location.get('lat',location.get('latitude')),-90,90)
        lng=_number(location.get('lng',location.get('longitude')),-180,180)
        observed=_instant(location.get('observed_at',location.get('timestamp')))
        age=(now.astimezone(timezone.utc)-observed).total_seconds() if observed else None
        if lat is None or lng is None or age is None or not -60<=age<=900:
            safe['current_location']['status']='unavailable'
        else:
            # Only the approximate area is needed for companion advice. Never
            # change booking/map pins, and do not introduce a precise-GPS cache.
            area_lat,area_lng=round(lat,3),round(lng,3)
            safe['care_scope_id']+=':'+str(area_lat)+','+str(area_lng)
            safe['current_location']=dict(status='granted',observed_at=observed.isoformat(),
                locality='',locality_status='unavailable')
            try:
                place=reverse(area_lat,area_lng)
                if isinstance(place,dict) and place.get('locality_status')=='ok':
                    safe['current_location'].update(locality=place.get('locality') or '',locality_status='ok')
            except Exception as exc:
                LOG.warning('companion_locality_failed kind=%s',type(exc).__name__)
            try:
                # The existing optional-weather adapter requires exactly TWO
                # points. This dashboard has one current area, so query that
                # same area in both protocol slots and retain only its first
                # point. These are not the booking's pickup/drop-off pins.
                point=dict(lat=area_lat,lng=area_lng)
                value=forecast([dict(point),dict(point)],now,now=now)
                if isinstance(value,dict):
                    value=copy.deepcopy(value)
                    if isinstance(value.get('points'),list):value['points']=value['points'][:1]
                    value['scope']='dashboard_current_area'
                    safe['current_weather']=value
                if not isinstance(value,dict) or value.get('status')!='ok':LOG.warning('companion_weather_unavailable')
            except Exception as exc:
                LOG.warning('companion_weather_failed kind=%s',type(exc).__name__)
    history=_delivered(context.get('delivered'))
    safe['delivered']=history
    acknowledged=context.get('acknowledged')
    safe['acknowledged']=[v for v in acknowledged[:32] if isinstance(v,str) and len(v)<100] if isinstance(acknowledged,list) else []
    # Ignore all client weather, locality, date, fare, driver and ride-status claims.
    # Both entry points use the same shared engine and delivery history.
    result=care.recommend(safe,delivered=history)
    recommendations=care.evaluate(safe)
    view=_weather_view(care,result)
    raw=safe.get('current_weather') or {}
    if view['status']=='ok':view['fetched_at']=raw.get('fetched_at')
    return dict(ok=True,version=VERSION,engine_version=care.VERSION,language=lang,
                greeting=result['greeting'],locality=result['locality'],
                location_status=safe['current_location']['status'],weather=view,
                recommendations=recommendations,optional=True)


def install_backend(server,providers=None,clock=None,care=None):
    existing=getattr(server.Handler,'_customer_care_api_version',None)
    if existing==VERSION:return dict(version=VERSION,already_installed=True)
    if existing is not None:
        raise RuntimeError('Restart the website service to replace the older care endpoint without overlapping handlers.')
    root=Path(server.ROOT).resolve()
    care=_load_care(root) if care is None else care
    if providers is None:
        tools=getattr(server,'_ct_module',None)
        weather=getattr(server,'_wx_weather_client',None)
        if tools is None or not callable(getattr(tools,'reverse_address',None)):
            raise RuntimeError('The original customer-tools bootstrap must run before customer care.')
        if weather is None or not callable(getattr(weather,'forecast',None)):
            raise RuntimeError('The original weather bootstrap must run before customer care.')
        reverse,forecast=tools.reverse_address,weather.forecast
    else:reverse,forecast=providers
    now_fn=clock or (lambda:datetime.now(care.TZ))
    previous_post,previous_get=server.Handler.do_POST,server.Handler.do_GET
    def do_get(handler):
        if urlparse(handler.path).path!='/api/customer-care/health':return previous_get(handler)
        return handler.json(200,dict(ok=True,version=VERSION,engine_version=care.VERSION,
                                    verified_weather_connected=True))
    def do_post(handler):
        if urlparse(handler.path).path!='/api/customer-care/recommend':return previous_post(handler)
        try:
            with server.conn() as db:
                user=handler.user(db)
                if user['role']!='customer':return handler.json(403,dict(error='Customer account required'))
                user=dict(user)
            try:
                payload=handler.payload(limit=32768)
                if isinstance(payload,(bytes,bytearray)):payload=bytes(payload).decode('utf-8')
                if isinstance(payload,str):
                    def invalid_constant(value):raise ValueError('Invalid JSON number')
                    payload=json.loads(payload,parse_constant=invalid_constant)
                if not isinstance(payload,dict):raise ValueError('Invalid request')
                context=payload.get('context',{})
                if not isinstance(context,dict):raise ValueError('Invalid context')
            except (ValueError,TypeError,UnicodeError):return handler.json(400,dict(error='Invalid customer-care request'))
            answer=dashboard_response(care,context,user,reverse,forecast,now_fn())
            return handler.json(200,answer)
        except PermissionError:return handler.json(401,dict(error='Please sign in'))
        except Exception as exc:
            LOG.warning('companion_request_failed kind=%s',type(exc).__name__)
            return handler.json(503,dict(error='Travel companion temporarily unavailable',optional=True))
    server.Handler.do_POST=do_post;server.Handler.do_GET=do_get
    server.Handler._customer_care_api_version=VERSION
    return dict(version=VERSION,installed=True,engine_version=care.VERSION)
