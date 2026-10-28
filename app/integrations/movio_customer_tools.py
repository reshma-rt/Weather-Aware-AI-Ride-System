"""Account-owned booking details and shared address/road lookups.

Primary API contracts: https://nominatim.org/release-docs/latest/api/Search/
https://operations.osmfoundation.org/policies/nominatim/
https://project-osrm.org/docs/v5.24.0/api/
"""
import copy
import json
import math
import os
import re
import threading
import time
from urllib.parse import parse_qs,urlparse

VERSION='customer-booking-tools-1.0'
_geo_lock=threading.RLock();_geo_last=0.0;_geo_cache={};_route_cache={};_route_lock=threading.RLock()

class LookupError(Exception):pass

def finite(value,low=None,high=None):
    if value is None or isinstance(value,bool):return None
    try:n=float(value)
    except (ValueError,TypeError,OverflowError):return None
    return n if math.isfinite(n) and (low is None or n>=low) and (high is None or n<=high) else None

def coords(lat,lng):
    a,b=finite(lat,-90,90),finite(lng,-180,180)
    if a is None or b is None:raise ValueError('Invalid location coordinates')
    return a,b

def place(row):
    a,b=coords(row['lat'],row.get('lon',row.get('lng')))
    full=str(row.get('display_name') or row.get('name') or '').strip()
    if not full:raise ValueError('Address is empty')
    # Long provider display strings used to exceed the booking API's 180-char
    # limit. Keep the nearby address components and retain the full tooltip.
    label=', '.join(full.split(',')[:3]).strip()
    if len(label)>170:label=label[:167].rsplit(' ',1)[0]+'…'
    return dict(name=label,full_address=full[:1000],lat=a,lng=b)

def geo_request(kind,params):
    global _geo_last
    import requests
    endpoint=os.environ.get('MOVIO_GEOCODER_URL','https://nominatim.openstreetmap.org/search').rstrip('/')
    url=endpoint if kind=='search' else endpoint.rsplit('/',1)[0]+'/reverse'
    key=(url,tuple(sorted(params.items())))
    with _geo_lock:
        saved=_geo_cache.get(key)
        if saved and time.monotonic()-saved[0]<86400:return copy.deepcopy(saved[1])
        delay=1.1-(time.monotonic()-_geo_last)
        if delay>0:time.sleep(delay)
        _geo_last=time.monotonic()
        try:
            response=requests.get(url,params=params,headers={'User-Agent':os.environ.get('MOVIO_GEOCODER_USER_AGENT','MOVIO-Ride-Booking-Research/5.3'),'Accept-Language':'en'},timeout=(3,8))
            response.raise_for_status();data=response.json()
        except (requests.RequestException,ValueError) as exc:raise LookupError('Address lookup could not complete. Please retry the search.') from exc
        if isinstance(data,dict) and data.get('error'):raise LookupError('Address not found for these coordinates.')
        _geo_cache[key]=(time.monotonic(),copy.deepcopy(data))
        if len(_geo_cache)>256:_geo_cache.pop(next(iter(_geo_cache)))
        return data

def address_search(query):
    query=str(query).strip()
    if not 3<=len(query)<=300:raise ValueError('Enter an address or landmark with 3–300 characters.')
    city=os.environ.get('MOVIO_SERVICE_CITY','Chennai').strip() or 'Chennai'
    box=os.environ.get('MOVIO_GEO_VIEWBOX','79.95,13.35,80.45,12.65')
    params=dict(q=query if city.casefold() in query.casefold() else query+', '+city,format='json',limit='6',countrycodes='in',addressdetails='1',viewbox=box,bounded='1')
    payload=geo_request('search',params)
    if not isinstance(payload,list):raise LookupError('Address lookup returned an invalid response. Please retry.')
    results=[]
    for row in payload:
        try:entry=place(row)
        except (KeyError,ValueError,TypeError):continue
        if not any(abs(entry['lat']-p['lat'])<1e-6 and abs(entry['lng']-p['lng'])<1e-6 and entry['name']==p['name'] for p in results):results.append(entry)
    return results

def reverse_address(lat,lng):
    """MOVIO_MAIN_LOCALITY_V1_1: real area labels; exact pin/GPS coordinates."""
    import logging
    lat,lng=coords(lat,lng)
    fields=('suburb','quarter','neighbourhood','neighborhood','locality','village','hamlet','residential','town')
    admin=re.compile(r'(?<!\w)(?:sub[- ]?zone|zone|ward|division|taluk|tehsil|corporation|municipality|panchayat)(?:\b|(?=\d))|மண்டலம்|வார்டு|மாநகராட்சி|நகராட்சி|ஊராட்சி',re.I)
    road=re.compile(r'\b(?:road|street|highway|expressway|lane|avenue)\b|சாலை|தெரு|நெடுஞ்சாலை',re.I)
    def clean(value):return re.sub(r'\s+',' ',value).strip() if isinstance(value,str) else ''
    def acceptable(value,broad=()):
        value=clean(value)
        return bool(value and any(c.isalpha() for c in value) and not admin.search(value)
            and not road.search(value) and value.casefold() not in broad)
    def select(row,format_name):
        if not isinstance(row,dict):return None
        if format_name=='geocodejson':
            features=row.get('features')
            if not isinstance(features,list) or len(features)!=1:return None
            feature=features[0]
            if not isinstance(feature,dict):return None
            properties=feature.get('properties')
            if not isinstance(properties,dict):return None
            data=properties.get('geocoding')
            if not isinstance(data,dict):return None
            broad={clean(data.get(key)).casefold() for key in ('city','county','state','country') if clean(data.get(key))}
            for key in ('locality','district'):
                if acceptable(data.get(key),broad):return clean(data[key]),clean(data.get('label')),'geocodejson.'+key
            if data.get('type') in ('locality','district') and acceptable(data.get('name'),broad):
                return clean(data['name']),clean(data.get('label')),'geocodejson.name'
            return None
        address=row.get('address')
        if not isinstance(address,dict):address={}
        broad={clean(address.get(key)).casefold() for key in ('city','municipality','county','state_district','state','country') if clean(address.get(key))}
        for key in fields:
            # A real town/village may legitimately also be the city name.
            excluded=() if key in ('town','village','hamlet') else broad
            if acceptable(address.get(key),excluded):
                return clean(address[key]),clean(row.get('display_name')),'address.'+key
        if row.get('addresstype',row.get('type')) in fields and acceptable(row.get('name'),broad):
            return clean(row['name']),clean(row.get('display_name')),'place.name'
        return None
    # A building/street response can omit the neighbourhood. Only in that case
    # request the provider's neighbourhood-level structured result at this pin.
    for format_name,zoom in (('json','18'),('geocodejson','14')):
        try:
            row=geo_request('reverse',dict(lat=str(lat),lon=str(lng),format=format_name,
                zoom=zoom,addressdetails='1',layer='address'))
            chosen=select(row,format_name)
            if chosen:
                locality,full,source=chosen
                return dict(name=locality[:170],locality=locality[:170],full_address=(full or locality)[:1000],
                    lat=lat,lng=lng,locality_status='ok',locality_source=source,locality_policy='main-locality-1.1')
        except (LookupError,KeyError,ValueError,TypeError) as exc:
            logging.getLogger('movio.customer_tools').warning('reverse_area_lookup_failed: %s',type(exc).__name__)
            break
    logging.getLogger('movio.customer_tools').warning('reverse_area_unresolved: no non-administrative locality returned')
    # Do not relabel a whole zone as a neighbourhood or snap a GPS coordinate.
    return dict(name='Selected location',locality='',full_address='',lat=lat,lng=lng,
        locality_status='unavailable',locality_source=None,locality_policy='main-locality-1.1')

def road_route(a,b):
    import requests
    a=coords(*a);b=coords(*b);key=tuple(round(v,6) for v in (*a,*b))
    with _route_lock:
        saved=_route_cache.get(key)
        if saved and time.monotonic()-saved[0]<900:return copy.deepcopy(saved[1])
    base=os.environ.get('MOVIO_OSRM_BASE_URL','https://router.project-osrm.org').rstrip('/')
    url=f'{base}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}'
    try:
        response=requests.get(url,params=dict(overview='full',geometries='geojson'),timeout=(3,10))
        response.raise_for_status();payload=response.json();rows=payload.get('routes')
        if payload.get('code')!='Ok' or not rows:raise ValueError('no_route')
        row=rows[0];distance=finite(row.get('distance'),0);duration=finite(row.get('duration'),0)
        if distance is None or not 0<distance/1000<=400:raise ValueError('invalid_road_distance')
        geometry=(row.get('geometry') or {}).get('coordinates',[])
        if not isinstance(geometry,list):geometry=[]
        geometry=[list(coords(p[1],p[0])) for p in geometry if isinstance(p,(list,tuple)) and len(p)>=2]
        result=dict(km=distance/1000,minutes=max(1,round(duration/60)) if duration is not None else None,geometry=geometry)
    except (requests.RequestException,ValueError,TypeError,KeyError,IndexError) as exc:
        raise LookupError('The road route could not be calculated. Your selected addresses are kept; please retry.') from exc
    with _route_lock:
        _route_cache[key]=(time.monotonic(),copy.deepcopy(result))
        if len(_route_cache)>128:_route_cache.pop(next(iter(_route_cache)))
    return result

def parsed(value):
    try:value=json.loads(value) if isinstance(value,str) else value
    except (ValueError,TypeError):return {}
    return value if isinstance(value,dict) else {}

def booking_details(c,owner,rid):
    row=c.execute('SELECT r.*,d.name driver_name,d.phone driver_phone,p.vehicle_number driver_vehicle_number FROM rides r LEFT JOIN users d ON d.id=r.driver_id LEFT JOIN driver_profiles p ON p.user_id=r.driver_id WHERE r.id=? AND r.customer_id=?',(rid,owner)).fetchone()
    if row is None:return None
    record=dict(row);tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    snapshot={}
    if {'wx_calls','wx_permits'}<=tables:
        permit=c.execute('SELECT p.snapshot FROM wx_permits p JOIN wx_calls w ON w.id=p.call_id WHERE p.ride_id=? AND w.owner=? ORDER BY p.expires DESC LIMIT 1',(rid,owner)).fetchone()
        if permit:snapshot=parsed(permit['snapshot'])
    if not snapshot and 'wx_calls' in tables:
        call=c.execute('SELECT state FROM wx_calls WHERE ride_id=? AND owner=? LIMIT 1',(rid,owner)).fetchone()
        if call:snapshot=parsed(call['state'])
    keys=('id','pickup','destination','plat','plng','dlat','dlng','vehicle','fare','status','driver_id','driver_name','driver_phone','driver_vehicle_number','source','created','updated')
    result={key:record.get(key) for key in keys}
    result['passengers']=record.get('passengers') if record.get('passengers') is not None else snapshot.get('count')
    result['pickup_time']=record.get('pickup_time') or snapshot.get('pickup_at')
    distance=next((record[key] for key in ('distance_km','km','road_distance_km') if finite(record.get(key),0) is not None),None)
    if distance is None:distance=parsed(snapshot.get('fare')).get('km')
    result['distance_km']=finite(distance,0)
    weather=parsed(record.get('weather_json')) or parsed(snapshot.get('weather'))
    result['weather']=dict(status=weather.get('status'),condition=weather.get('condition'),fetched_at=weather.get('fetched_at'),points=[])
    if weather.get('status')=='ok':
        for point in weather.get('points',[]) if isinstance(weather.get('points'),list) else []:
            if isinstance(point,dict) and point.get('location') in ('pickup','destination'):
                result['weather']['points'].append(dict(location=point['location'],precipitation_probability=finite(point.get('precipitation_probability'),0,100),temperature_2m=finite(point.get('temperature_2m')),valid_at=point.get('valid_at')))
    result['pickup_verified']=False
    if 'ride_pickup_codes' in tables:
        code=c.execute('SELECT code,verified FROM ride_pickup_codes WHERE ride_id=?',(rid,)).fetchone()
        result['pickup_verified']=bool(code and code['verified'])
        if code and not result['pickup_verified'] and record['status'] in ('requested','accepted','arriving'):result['pickup_otp']=code['code']
    if 'location_requests' in tables and record.get('driver_id'):
        request=c.execute('SELECT status,expires FROM location_requests WHERE ride_id=? AND customer_id=? AND driver_id=?',(rid,owner,record['driver_id'])).fetchone()
        if request:
            result['location_request_status']='expired' if request['status']=='granted' and request['expires']<=time.time() else request['status']
            if request['status']=='granted' and request['expires']>time.time() and record['status'] in ('accepted','arriving','in_progress'):result['location_share_until']=request['expires']
    return result

def install_backend(module):
    if getattr(module.Handler,'_movio_customer_tools_version',None)==VERSION:return dict(version=VERSION,already_installed=True)
    previous=module.Handler.do_GET
    def get(h):
        parsed_url=urlparse(h.path);path=parsed_url.path
        if path=='/api/customer-tools/health':return h.json(200,dict(ok=True,version=VERSION))
        if not path.startswith('/api/customer-tools/'):return previous(h)
        try:
            with module.conn() as c:
                user=h.user(c)
                if user['role']!='customer':return h.json(403,dict(error='Customer account required'))
                owner=user['id']
                match=re.fullmatch(r'/api/customer-tools/booking/([1-9]\d*)',path)
                if match:
                    result=booking_details(c,owner,int(match[1]))
                    return h.json(200,dict(ok=True,booking=result)) if result else h.json(404,dict(error='Booking not found'))
            query=parse_qs(parsed_url.query)
            arg=lambda name:query.get(name,[''])[0]
            if path.endswith('/address-search'):return h.json(200,dict(ok=True,places=address_search(arg('q'))))
            if path.endswith('/reverse-address'):return h.json(200,dict(ok=True,place=reverse_address(arg('lat'),arg('lng'))))
            if path.endswith('/route'):return h.json(200,dict(ok=True,route=road_route((arg('plat'),arg('plng')),(arg('dlat'),arg('dlng')))))
            return h.json(404,dict(error='Unknown customer endpoint'))
        except PermissionError:return h.json(401,dict(error='Sign in to your customer account'))
        except (ValueError,KeyError,TypeError) as exc:return h.json(400,dict(error=str(exc)))
        except LookupError as exc:return h.json(502,dict(error=str(exc)))
        except Exception:return h.json(500,dict(error='The request could not be completed. Please retry.'))
    module.Handler.do_GET=get;module.Handler._movio_customer_tools_version=VERSION
    return dict(version=VERSION)
