"""Small repairs for the existing MOVIO booking implementation."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys
import threading
from urllib.parse import urlparse

VERSION='booking-reliability-1.0'
_providers={};_provider_lock=threading.RLock()


def provider_module(root):
    path=Path(root)/'integrations/movio_required_weather.py'
    key=str(path.resolve())
    with _provider_lock:
        if key not in _providers:
            spec=importlib.util.spec_from_file_location('_movio_manual_forecast_provider',path)
            module=importlib.util.module_from_spec(spec)
            exec(compile(path.read_text(encoding='utf-8'),str(path),'exec'),module.__dict__)
            if not callable(getattr(module,'complete',None)) or not callable(getattr(module,'Forecast',None)):
                raise RuntimeError('Run the required-spoken-weather cell before this repair.')
            _providers[key]=module
        return _providers[key]


def forecast_error(weather,lang):
    reason=weather.get('reason') or weather.get('status') or 'forecast_request_failed'
    status=weather.get('http_status')
    if reason in ('outside_forecast_window','outside_forecast_range'):
        messages=('This date is outside the weather forecast window. Your selected date is kept.',
            'இந்தத் தேதிக்கான வானிலை இன்னும் வெளியிடப்படவில்லை. நீங்கள் தேர்ந்தெடுத்த தேதி உள்ளது.',
            'Indha date-ku forecast innum varala. Neenga select panna date irukku.')
    elif status==429 or reason=='rate_limit_backoff':
        messages=('The weather service asked us to wait. Please try Review ride again shortly.',
            'வானிலை சேவை சிறிது நேரம் காத்திருக்கச் சொல்கிறது. பின்னர் பயணத்தை மீண்டும் சரிபார்க்கவும்.',
            'Weather service konjam wait panna solludhu. Konja nerathula Ride review retry pannunga.')
    else:
        messages=('The weather check did not finish. Your ride details are kept. Press Review ride to retry.',
            'வானிலைச் சரிபார்ப்பு முடியவில்லை. உங்கள் பயண விவரங்கள் உள்ளன. மீண்டும் பயணத்தைச் சரிபார்க்கவும்.',
            'Weather check mudiyala. Unga ride details irukku. Ride review press panni retry pannunga.')
    return dict(reason=reason,http_status=status,message=messages[('English','Tamil','Tanglish').index(lang) if lang in ('English','Tamil','Tanglish') else 0])


def install_namespace(engine,root):
    root=Path(root)
    if engine.get('_MOVIO_BOOKING_RELIABILITY_VERSION')==VERSION:
        return dict(version=VERSION,already_installed=True)
    required=('time_components','update_time_memory','manual_state','install_backend')
    if any(not callable(engine.get(key)) for key in required):
        raise RuntimeError('The current weather/booking engine is not initialized.')
    provider=provider_module(root)
    previous={key:engine[key] for key in required}
    lexicon=engine['number_lexicon'](59)
    words=[word for word,value in lexicon.items() if not word.isdigit() and 0<=value<=23]
    number=r'(?<![\w\u0b80-\u0bff])(?:\d{1,2}(?::\d{2})?|'+'|'.join(re.escape(word) for word in sorted(words,key=len,reverse=True))+r')(?![\w\u0b80-\u0bff])'
    before=re.compile(number+r'\s*(?:(?:o[.\s\x27’]?clock|மணி(?:க்கு)?|manikku|mani)\s*)?$',re.I)
    marker=re.compile(r'(?<![a-z])([ap])\s*\.?\s*m\.?(?![a-z])',re.I)
    alone=re.compile(r"^\s*(?:(?:it is|it's|its|i mean|make it|use)\s+)?[ap]\s*\.?\s*m\.?\s*(?:please)?\s*[.!?]?\s*$",re.I)
    dayparts=re.compile(r'காலை|அதிகாலை|மதியம்|நண்பகல்|மாலை|நள்ளிரவு|இரவு|\b(?:morning|afternoon|evening|night|tonight|noon|midnight|kaalai|kalai|adhikaalai|madhiyam|mathiyam|maalai|malai|iravu|nalliravu)\b',re.I)
    def normalize_periods(raw,allow_bare=False):
        text=engine['unicodedata'].normalize('NFKC',str(raw or '')).translate(str.maketrans('௦௧௨௩௪௫௬௭௮௯','0123456789'))
        standalone=bool(allow_bare and alone.fullmatch(text))
        def replace(match):
            # A clock suffix, or a short AM/PM clarification, is a period.
            # The verb in "I am one person" is ordinary sentence text.
            return match[1].lower()+'m' if standalone or before.search(text[:match.start()]) else ' '*len(match[0])
        return marker.sub(replace,text)
    def time_components(raw,now,allow_bare=False):
        return previous['time_components'](normalize_periods(raw,allow_bare),now,allow_bare=allow_bare)
    def update_time_memory(state,text,now):
        try:return previous['update_time_memory'](state,text,now)
        except engine['GuardError'] as exc:
            # Keep independently valid date/hour evidence when a real period
            # conflict needs clarification. Never choose one conflicting period.
            if str(exc)=='clarify_period':
                cleaned=dayparts.sub(' ',marker.sub(' ',str(text or '')))
                try:partial=previous['time_components'](cleaned,now,allow_bare=state.get('stage') in ('time','time_period'))
                except engine['GuardError']:partial={}
                parts=copy.deepcopy(state.get('_wx_time') or {})
                for key in ('date','hour','minute','clock24'):
                    if key in partial:parts[key]=partial[key]
                if 'hour' in partial:
                    parts.pop('period',None);parts.pop('day_period',None)
                state['_wx_time']=parts
            state['_wx_time_error']=str(exc)
            return None,str(exc)
    proxies={};lock=threading.RLock()
    def proxy(weather):
        with lock:
            item=proxies.get(id(weather))
            if item is None or item.base is not weather:
                item=provider.Forecast(weather,engine,root);proxies[id(weather)]=item
            return item
    def manual_state(data,weather,now=None):
        state=previous['manual_state'](data,proxy(weather),now=now)
        if not provider.complete(state.get('weather')):
            state['weather']=dict(state.get('weather') or {})
            state['weather'].pop('_optional_skip',None)
        return state
    def install_backend(module,weather=None):
        result=previous['install_backend'](module,weather=weather)
        install_http(module,engine,root)
        return result
    engine.update(time_components=time_components,update_time_memory=update_time_memory,
        manual_state=manual_state,install_backend=install_backend,
        _MOVIO_BOOKING_RELIABILITY_VERSION=VERSION,
        _movio_reliable_manual_forecast=proxy,_movio_reliable_provider=provider)
    return dict(version=VERSION)


def install_http(module,engine,root):
    if getattr(module.Handler,'_movio_booking_reliability',None)==VERSION:return
    old_get=module.Handler.do_GET;old_post=module.Handler.do_POST
    def get(h):
        if urlparse(h.path).path=='/api/weather-booking/reliability-health':
            return h.json(200,dict(ok=True,version=VERSION,manual_forecast='validated_hourly_pickup_and_drop',time_parser='clock_bound_meridiem'))
        return old_get(h)
    def post(h):
        if urlparse(h.path).path!='/api/weather-booking/manual-preview':return old_post(h)
        send=h.json;had_json='json' in h.__dict__;instance_json=h.__dict__.get('json')
        def json_reply(status,obj,*args,**kwargs):
            if status==200 and isinstance(obj,dict) and obj.get('ok') and obj.get('call_id'):
                with module.conn() as c:
                    row=c.execute('SELECT state FROM wx_calls WHERE id=?',(obj['call_id'],)).fetchone()
                state=json.loads(row['state']) if row else {}
                weather=state.get('weather') or {}
                obj=dict(obj,weather=weather,weather_status=weather.get('status'))
                if not engine['_movio_reliable_provider'].complete(weather):
                    obj['forecast_error']=forecast_error(weather,state.get('lang','English'))
            return send(status,obj,*args,**kwargs)
        h.json=json_reply
        try:return old_post(h)
        finally:
            if had_json:h.json=instance_json
            else:del h.json
    module.Handler.do_GET=get;module.Handler.do_POST=post
    module.Handler._movio_booking_reliability=VERSION


RESET_JS="""
   // MOVIO_VERIFIED_BOOKING_RESET_V1
   if(!result.ok||!Number.isInteger(Number(result.id))||Number(result.id)<1){
    const error=Error(words().unknown);error.http=502;throw error;
   }
   uncertain=false;review=null;el('wxManualReview').hidden=true;rideId=Number(result.id);serial++;
   // Abort only draft lookups. Preserve saved rides, driver tracking and OTPs.
   const draft=window.MOVIOCustomerBookingUI?.state;
   if(draft){clearTimeout(draft.previewTimer);draft.routeController?.abort();draft.routeSeq++;draft.searchSeq++;
    draft.routeKey=null;draft.routePromise=null;draft.lastPreview=null;draft.field='pickup';}
   if(typeof searchTimer!=='undefined')clearTimeout(searchTimer);
   pickup=null;destination=null;km=0;minutes=0;routeData=null;selecting='pickup';
   for(const id of ['pickup','destination']){const node=el(id);if(node){node.value='';node.removeAttribute('title');}}
   el('suggestions')?.replaceChildren();
   if(routeLine){try{map.removeLayer(routeLine);}catch{}routeLine=null;}
   if(typeof markers!=='undefined')for(const key of ['pickup','destination']){
    if(markers[key]){try{map.removeLayer(markers[key]);}catch{}delete markers[key];}
   }
   vehicle='Mini';countBox.value='1';
   document.querySelectorAll('.vehicle').forEach(node=>node.classList.toggle('active',node.dataset.type==='Mini'));
   dateBox.value='';
   for(const id of ['wxPickupDay','wxPickupTime'])if(el(id))el(id).value='';
   if(el('wxPickupDay'))el('wxPickupDay').min=indiaDay();syncDayButtons();
   for(const id of ['wxPickupName','wxDropName','wxTripPickup','wxTripDrop','wxTripDate','wxShortAdvice','wxManualAdvice','wxManualSummary','wxPickupRain','wxDropRain','wxCondition']){
    const node=el(id);if(node){node.textContent='';node.removeAttribute('title');}
   }
   el('wxTripFacts')?.replaceChildren();
   if(el('routeInfo'))el('routeInfo').textContent=langBox.value==='Tamil'?'புறப்படும் இடத்தையும் சேரும் இடத்தையும் தேர்ந்தெடுக்கவும்.':langBox.value==='Tanglish'?'Pickup, destination select pannunga.':'Choose pickup and destination for a new ride.';
   try{fares();}catch{}status(result.message);toast(result.message);
"""


def patch_manual(source):
    anchor="const result=await request('manual-confirm',review.binding,true);"
    if source.count(anchor)!=1:raise RuntimeError('Expected one manual-confirm success handler; no files changed.')
    start=source.index(anchor)+len(anchor)
    end=source.find('// Refresh failures must not turn a successful save into a failed booking.',start)
    if end<0:end=source.find('await Promise.allSettled([refreshRides(),renderVoiceHistory()]);',start)
    if end<0:raise RuntimeError('Could not identify the manual booking refresh boundary; no files changed.')
    source=source[:start]+'\n'+RESET_JS+'   '+source[end:]
    old='timer=setTimeout(()=>controller.abort(),15000)'
    new="timer=setTimeout(()=>controller.abort(),path==='manual-preview'?45000:15000)"
    if old in source:source=source.replace(old,new,1)
    # A pending forecast cannot be presented as a completed weather review.
    start_marker='// MOVIO_MANUAL_FORECAST_VALIDATION_V1'
    if start_marker not in source:
        anchor="if(ticket!==serial||captured!==fingerprint()){discard({binding:result});status(words().changed);return;}"
        if source.count(anchor)!=1:raise RuntimeError('Manual preview revision check was not found; no files changed.')
        check="""
   // MOVIO_MANUAL_FORECAST_VALIDATION_V1
   if(result.weather){
    const w=result.weather,points=w.points||[];
    const complete=w.status==='ok'&&['pickup','destination'].every(role=>{
     const p=points.find(row=>row.location===role),n=p?.precipitation_probability;
     return n!==null&&n!==undefined&&Number.isFinite(Number(n))&&Number(n)>=0&&Number(n)<=100;
    });
    if(!complete){discard({binding:result});const error=Error(result.forecast_error?.message||words().failed);error.http=503;throw error;}
   }
"""
        source=source.replace(anchor,anchor+check,1)
    return source
