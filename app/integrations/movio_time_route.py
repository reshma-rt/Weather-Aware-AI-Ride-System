"""Targeted time/slot repair for the existing MOVIO voice booking guard.

No replacement booking database, TTS, STT, weather provider, UI, or fare model.
"""
import copy
import importlib.util
import json
import logging
import math
import re
import threading
import time
from datetime import datetime
from pathlib import Path

VERSION='time-route-1.0'
_LETTERS=r'A-Za-z\u0B80-\u0BFF'
_AFTER_AT_CLOCK=r'(?=\s*(?:$|[,;.?!]|(?:a\.?m\.?|p\.?m\.?|please|today|tomorrow|for|with|and|vehicle|cab|taxi|car|pickup|venum|vendum|o[.\s\x27’]?clock)(?![a-z])))'


def logger_for(root):
    path=Path(root)/'booking_lookup.log'
    logger=logging.getLogger('movio.time_route.'+str(path.resolve()))
    logger.setLevel(logging.INFO);logger.propagate=False
    if not logger.handlers:
        handler=logging.FileHandler(path,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
    return logger


def log(logger,name,**fields):
    # Never log user/session credentials, response bodies, or booking tokens.
    logger.info(json.dumps(dict(event=name,**fields),ensure_ascii=False,default=str))


def clock_patterns(engine):
    words={word:n for word,n in engine['number_lexicon'](59).items() if not word.isdigit() and 0<=n<=23}
    values=r'\d{1,2}(?::\d{2})?|'+'|'.join(re.escape(word) for word in sorted(words,key=len,reverse=True))
    number=r'(?<!['+_LETTERS+r'\d])(?:'+values+r')(?!['+_LETTERS+r'\d])'
    unit=r'(?:மணி(?:க்கு|யளவில்)?|manikku|mani|o[.\s\x27’]?clock)(?!['+_LETTERS+r'])'
    # Consume AM/PM together with "at 9". Leaving "AM" behind could make a
    # following bare route look like the invalid pickup "AM Tambaram".
    period=r'\s*(?:a\.?m\.?|p\.?m\.?)(?![a-z])'
    expression=number+r'\s*'+unit+r'|(?<![a-z])(?:at|around)\s+'+number+'(?:'+period+'|'+_AFTER_AT_CLOCK+')'
    return words,number,unit,expression


def patch_slots(slots,engine):
    """Make spoken clock expressions ineligible to replace a place slot."""
    namespace=slots if isinstance(slots,dict) else vars(slots)
    if namespace.get('_MOVIO_CLOCK_SLOT_VERSION')==VERSION:return
    words,number,unit,expression=clock_patterns(engine)
    old_time=namespace['_TIME'];old_carrier=namespace['_CARRIER']
    namespace['_TIME']=re.compile('(?:'+old_time.pattern+')|(?:'+expression+')',old_time.flags)
    namespace['_CARRIER']=re.compile(r'(?<!['+_LETTERS+r'])(?:'+old_carrier.pattern+r')(?!['+_LETTERS+r'])',old_carrier.flags)
    parser=namespace['Parser'];old_clean=parser.clean_place
    bare_unit=re.compile(r'(?<!['+_LETTERS+r'])'+unit,re.I)
    def clean_place(self,value,role):
        # Reject malformed leftovers such as "கு மணிக்கு" as well as a full clock.
        # Known place names remain eligible even if they happen to contain a unit.
        key=namespace['place_key'](value)
        if key not in self.places and bare_unit.search(str(value or '')):return None
        return old_clean(self,value,role)
    parser.clean_place=clean_place
    namespace['_MOVIO_CLOCK_SLOT_VERSION']=VERSION


def finite_fare(value):
    try:return isinstance(value,dict) and all(math.isfinite(float(value[k])) and float(value[k])>=0 for k in ('km','fare'))
    except (ValueError,TypeError,KeyError,OverflowError):return False


def attach_lookups(bridge,engine,root):
    """Retain the configured providers/rates; expire negative geocoder caches."""
    if getattr(bridge,'_movio_time_route_lookups',None)==VERSION:return
    logger=logger_for(root);valid_geo=engine['valid_geo']
    normalize=engine.get('_movio_weather_normalize',lambda name,*args:name)
    original_geo=getattr(bridge,'geocode',None);original_route=getattr(bridge,'road_fare',None)
    if not callable(original_geo) or not callable(original_route):raise RuntimeError('The original geocoder/road-fare functions are missing.')
    raw=original_geo;seen=set()
    while id(raw) not in seen:
        seen.add(id(raw));inner=getattr(raw,'_original_geocode',None)
        if not callable(inner):break
        raw=inner
    raw_globals=getattr(raw,'__globals__',{})
    cache=getattr(bridge,'GEOCODE_CACHE',raw_globals.get('GEOCODE_CACHE'))
    geo_lock=getattr(bridge,'GEO_LOCK',raw_globals.get('GEO_LOCK')) or threading.RLock()
    # The original geocoder caches None indefinitely. Remove only failed entries;
    # all valid successful provider results are kept.
    if isinstance(cache,dict):
        with geo_lock:
            for key in list(cache):
                if not valid_geo(cache.get(key)):cache.pop(key,None)
    failed={};failed_lock=threading.RLock()
    def geocode(name):
        canonical=normalize(name)
        if not canonical:
            log(logger,'geocode_rejected_name',location=str(name)[:120]);return None
        with failed_lock:
            if canonical in failed and time.monotonic()-failed[canonical]<30:return None
            if isinstance(cache,dict):
                with geo_lock:
                    for key in list(cache):
                        if isinstance(key,tuple) and key and str(key[-1]).casefold()==canonical.casefold() and not valid_geo(cache.get(key)):
                            cache.pop(key,None)
            try:result=original_geo(canonical)
            except Exception as exc:
                result=None;log(logger,'geocode_exception',location=canonical,error_type=type(exc).__name__)
            if valid_geo(result):
                failed.pop(canonical,None)
                log(logger,'geocode_ok',location=canonical)
                return result
            failed[canonical]=time.monotonic()
            log(logger,'geocode_failed',location=canonical,retry_after_s=30)
            return None
    # Keep the optional-weather wrapper from repeatedly wrapping this function.
    geocode._movio_optional_weather_geo=True
    geocode._original_geocode=original_geo
    def road_fare(state):
        if not all(valid_geo(state.get(role+'_geo')) for role in ('pickup','destination')):
            log(logger,'route_missing_coordinates',pickup=state.get('pickup'),destination=state.get('destination'))
            return None
        try:result=original_route(state)
        except Exception as exc:
            response=getattr(exc,'response',None)
            log(logger,'route_exception',error_type=type(exc).__name__,http_status=getattr(response,'status_code',None))
            return None
        if not finite_fare(result):
            log(logger,'route_no_valid_estimate',vehicle=state.get('vehicle'))
            return None
        log(logger,'route_ok',km=result['km'],estimated_fare=result['fare'])
        return result
    bridge.geocode=geocode;bridge.road_fare=road_fare
    bridge._movio_time_route_lookups=VERSION


def install_namespace(engine,root=None,bridge=None,slots=None):
    root=Path(root or Path(engine['__file__']).resolve().parent.parent)
    if slots is None:slots=getattr(bridge,'_wx_group_slots_module',None)
    if slots is None:
        path=root/'integrations/movio_group_booking_slots.py'
        spec=importlib.util.spec_from_file_location('_movio_clock_slots',path)
        slots=importlib.util.module_from_spec(spec);spec.loader.exec_module(slots)
    slots._ENGINE=engine;patch_slots(slots,engine)
    if engine.get('_MOVIO_TIME_ROUTE_VERSION')==VERSION:
        if bridge is not None:attach_lookups(bridge,engine,root)
        return dict(version=VERSION,already_installed=True)
    logger=logger_for(root)
    original={name:engine[name] for name in ('time_components','components_datetime','update_time_memory','collect_details','install_bridge')}
    # Also patch any live module already captured by earlier collector wrappers.
    previous_group=engine.get('_movio_optional_weather_original',{}).get('collect_details')
    if callable(previous_group) and 'Parser' in getattr(previous_group,'__globals__',{}):patch_slots(previous_group.__globals__,engine)
    words,number,unit,expression=clock_patterns(engine)
    at_clock=re.compile(r'(?<![a-z])(?:at|around)\s+(?P<hour>\d{1,2}|'
        +'|'.join(re.escape(k) for k in sorted(words,key=len,reverse=True))+r')(?!['+_LETTERS+r'\d])'+_AFTER_AT_CLOCK,re.I)
    def time_components(raw,now,allow_bare=False):
        result=original['time_components'](raw,now,allow_bare=allow_bare)
        if 'hour' not in result:
            text=engine['unicodedata'].normalize('NFKC',str(raw or '')).casefold().translate(str.maketrans('௦௧௨௩௪௫௬௭௮௯','0123456789'))
            match=at_clock.search(text)
            if match:
                tail=text[match.end():]
                # "at 4 passengers" or "at 4 kilometres" is not a clock.
                if not re.match(r'\s*(?:passengers?|people|persons?|kilomet(?:er|re)s?|km|பேர்|கிலோமீட்டர்)\b',tail,re.I):
                    value=match['hour'];hour=int(value) if value.isdigit() else words[value]
                    if not 0<=hour<=23:raise engine['GuardError']('invalid_datetime')
                    result.update(hour=hour,minute=0,clock24=hour==0 or hour>12)
        return result
    def components_datetime(parts,now):
        if parts.get('date') and 'hour' in parts and not parts.get('clock24') and not parts.get('period') and not parts.get('day_period') and 1<=parts['hour']<=12:
            local_now=now.astimezone(engine['TZ'])
            try:day=datetime.fromisoformat(parts['date']).date()
            except (ValueError,TypeError):raise engine['GuardError']('invalid_datetime')
            if day==local_now.date():
                try:
                    values=[datetime.combine(day,datetime.min.time(),tzinfo=engine['TZ']).replace(hour=h,minute=parts.get('minute',0))
                        for h in (parts['hour']%12,parts['hour']%12+12)]
                except (ValueError,TypeError):raise engine['GuardError']('invalid_datetime')
                future=[value for value in values if value>local_now]
                if len(future)==1:return future[0]
                if not future:raise engine['GuardError']('past_datetime')
                # Two future interpretations are genuinely ambiguous.
        return original['components_datetime'](parts,now)
    def update_time_memory(state,text,now):
        result,error=original['update_time_memory'](state,text,now)
        parts=state.get('_wx_time') or {}
        if result and not parts.get('clock24') and not parts.get('period') and not parts.get('day_period'):
            state['_wx_time_inference']={'rule':'only_future_interpretation_today','period':'am' if result.hour<12 else 'pm',
                'resolved':result.isoformat(),'checked_at':now.astimezone(engine['TZ']).isoformat()}
            # No inferred AM/PM is inserted into parts: a new date/time must be
            # independently re-evaluated rather than inheriting a guessed period.
            log(logger,'clock_inferred',**state['_wx_time_inference'])
        else:state.pop('_wx_time_inference',None)
        return result,error
    def collect_details(b,state,text):
        return slots.collect_details(b,state,text)
    def install_bridge(b,db_path,weather=None,_route_wrapper=None):
        result=original['install_bridge'](b,db_path,weather=weather,_route_wrapper=_route_wrapper)
        attach_lookups(b,engine,root)
        return dict(result,time_route=VERSION)
    engine.update(time_components=time_components,components_datetime=components_datetime,update_time_memory=update_time_memory,
        collect_details=collect_details,install_bridge=install_bridge,_MOVIO_TIME_ROUTE_VERSION=VERSION,
        _movio_time_route_original=original)
    if bridge is not None:attach_lookups(bridge,engine,root)
    return dict(version=VERSION,log=str(root/'booking_lookup.log'))


def diagnose(bridge,engine,text,check_apis=False,now=None):
    """No booking, database write, speech generation, or fabricated consent."""
    now=(now or datetime.now(engine['TZ'])).astimezone(engine['TZ'])
    state=dict(mode='book',stage='count',lang='Tamil')
    engine['collect_details'](bridge,state,text)
    try:pickup,error=engine['update_time_memory'](state,text,now)
    except engine['GuardError'] as exc:pickup,error=None,str(exc)
    report={key:state.get(key) for key in ('count','vehicle','pickup','destination','pickup_at')}
    report.update(local_now=now.isoformat(),time_error=error)
    if not check_apis:return report
    if error or not all(state.get(key) for key in ('count','vehicle','pickup','destination')):
        report['api_check']='skipped: complete valid booking details first';return report
    for role in ('pickup','destination'):state[role+'_geo']=bridge.geocode(state[role])
    report['coordinates_ok']=all(engine['valid_geo'](state.get(role+'_geo')) for role in ('pickup','destination'))
    if not report['coordinates_ok']:
        report.update(weather='not queried: geocoding failed',road_estimate='not queried: geocoding failed');return report
    weather=bridge._wx_weather
    try:result=weather.forecast([state['pickup_geo'],state['destination_geo']],pickup,now=now)
    except Exception as exc:result=dict(status='unavailable',reason=type(exc).__name__)
    report['weather']=result.get('status');report['weather_reason']=result.get('reason')
    if result.get('status')=='ok':
        report['rain_probability_pct']={row['location']:row.get('precipitation_probability') for row in result.get('points',[])}
    fare=bridge.road_fare(copy.deepcopy(state))
    report['road_estimate']=fare if finite_fare(fare) else 'unavailable: check booking_lookup.log'
    return report
