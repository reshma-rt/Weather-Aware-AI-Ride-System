"""Conversational weather choices for the existing MOVIO booking protocol."""
import contextvars
import copy
import inspect
import math
from pathlib import Path
import re
import threading
import types
from datetime import datetime

VERSION='friendly-weather-1.1'
TURN=contextvars.ContextVar('movio_friendly_weather_turn',default=None)


def number(value):
    if value is None or isinstance(value,bool):return None
    try:value=float(value)
    except (TypeError,ValueError,OverflowError):return None
    return value if math.isfinite(value) else None


def complete(weather):
    if not isinstance(weather,dict) or weather.get('status')!='ok':return False
    for role in ('pickup','destination'):
        point=next((p for p in weather.get('points',[]) if isinstance(p,dict) and p.get('location')==role),{})
        chance=number(point.get('precipitation_probability'));code=number(point.get('weather_code'))
        if chance is None or not 0<=chance<=100 or code is None:return False
    return True


def category(weather):
    if not complete(weather):return 'missing'
    points=weather.get('points',[])
    if weather.get('thunderstorm') or any(p.get('weather_code') in (95,96,99) for p in points):return 'storm'
    if weather.get('heavy_rain'):return 'heavy'
    if weather.get('heat'):return 'heat'
    # Wind advice is enabled only when actual wind fields exist in the forecast.
    if any((number(p.get('wind_speed_10m')) or 0)>=40 or (number(p.get('wind_gusts_10m')) or 0)>=50 for p in points):return 'wind'
    if weather.get('condition')=='rain':return 'rain'
    return 'normal'


def scope(state,engine):
    weather=copy.deepcopy(state.get('weather') or {});weather.pop('_friendly_notice_policy',None)
    values={k:state.get(k) for k in ('pickup','destination','pickup_geo','destination_geo','pickup_at','vehicle','count')}
    values['weather']=weather
    return engine['digest'](values)


def exemption(state,engine):
    weather=state.get('weather') or {};policy=weather.get('_friendly_notice_policy') or {}
    reason='forecast_missing' if category(weather)=='missing' else 'no_weather_choice_needed' if category(weather)=='normal' else None
    return bool(reason and policy.get('version')==VERSION and policy.get('reason')==reason and policy.get('scope')==scope(state,engine))


def pick(state,en,ta,roman):return ta if state.get('lang')=='Tamil' else roman if state.get('lang')=='Tanglish' else en


def fmt(value):return f'{float(value):g}'


def report(state):
    """MOVIO weather wording step-2-v1: forecast facts and practical advice."""
    weather = state.get('weather') or {}
    kind = category(weather)
    if kind == 'missing':
        return ''
    points = {point['location']: point for point in weather['points']}
    pickup = state.get('pickup') or 'Pickup'
    destination = state.get('destination') or 'Destination'
    vehicle = state.get('vehicle') or 'vehicle'
    chance_a = fmt(points['pickup']['precipitation_probability'])
    chance_b = fmt(points['destination']['precipitation_probability'])
    temperature = number(points['pickup'].get('temperature_2m'))

    def say(english, tamil, tanglish):
        return pick(state, english, tamil, tanglish)

    conditions = {
        'rain': ('rain is possible', 'மழை பெய்ய வாய்ப்பு இருக்கு', 'rain peiya vaaippu irukku'),
        'heavy': ('heavy rain is forecast', 'கனமழை எதிர்பார்க்கப்படுகிறது', 'heavy rain peiya vaaippu irukku'),
        'storm': ('thunderstorms are forecast', 'இடியுடன் கூடிய மழை எதிர்பார்க்கப்படுகிறது', 'thunderstorm weather irukkum ena forecast irukku'),
        'heat': ('hot conditions are forecast', 'வெப்பம் அதிகமாக இருக்கும் என எதிர்பார்க்கப்படுகிறது', 'heat adhigamaaga irukkum'),
        'wind': ('strong winds are forecast', 'பலத்த காற்று எதிர்பார்க்கப்படுகிறது', 'strong wind irukkum ena forecast irukku'),
    }
    if kind in conditions:
        condition = say(*conditions[kind])
    elif weather.get('condition') == 'cloudy':
        condition = say('cloudy skies are forecast', 'மேகமூட்டம் இருக்கும் என எதிர்பார்க்கப்படுகிறது', 'cloudy weather irukkum')
    elif weather.get('pleasant'):
        condition = say('the forecast looks pleasant', 'வானிலை பயணத்திற்கு ஏற்றதாக இருக்கும் என எதிர்பார்க்கப்படுகிறது', 'weather nandraagave irukkum')
    elif weather.get('condition') == 'clear':
        condition = say('clear skies are forecast', 'வானம் தெளிவாக இருக்கும் என எதிர்பார்க்கப்படுகிறது', 'clear sky irukkum')
    else:
        condition = say('these are the available forecast details', 'கிடைத்த வானிலை விவரங்களைச் சொல்கிறேன்', 'forecast details irukku')

    # Temperatures and percentages come only from this request's forecast.
    extra_temperature = '' if temperature is None else say(
        f'; the pickup temperature should be about {fmt(temperature)} degrees Celsius',
        f'; புறப்படும் இடத்தில் வெப்பநிலை சுமார் {fmt(temperature)} டிகிரி செல்சியஸ் ஆக இருக்கும்',
        f'; pickup temperature sumaar {fmt(temperature)} degrees Celsius irukkum',
    )
    facts = say(
        f'A quick weather update for your pickup time: {condition}{extra_temperature}; the rain chance is {chance_a}% at {pickup} and {chance_b}% at {destination}.',
        f'ஒரு சின்ன வானிலை தகவல்: புறப்படும் நேரத்தில் {condition}{extra_temperature}; {pickup} பகுதியில் {chance_a}%, {destination} பகுதியில் {chance_b}% மழை வாய்ப்பு உள்ளது.',
        f'Oru weather update: pickup nerathil {condition}{extra_temperature}; {pickup}-la {chance_a}%, {destination}-la {chance_b}% rain chance irukku.',
    )

    if kind in ('rain', 'heavy', 'storm'):
        if vehicle == 'Bike':
            advice = say(
                'Carry an umbrella for before and after the ride and keep your belongings dry; a covered car can offer more rain protection than your bike.',
                'பயணத்திற்கு முன்னும் பின்னும் பயன்படுத்த குடை எடுத்துக்கொண்டு, உங்கள் பொருட்களை நனையாமல் பாதுகாத்துக்கொள்ளுங்கள்; பைக்கை விட மூடிய காரில் மழையிலிருந்து கூடுதல் பாதுகாப்பு கிடைக்கும்.',
                'Umbrella eduthukkondu unga belongings nanaiyaamal paadhugaathukkollunga; Bike open vehicle, rain protection-ku covered car consider pannalaam.',
            )
        elif vehicle == 'Auto':
            advice = say(
                'Rain can enter an auto from the sides, so carry an umbrella for getting in and out and keep your bags covered.',
                'ஆட்டோவின் பக்கவாட்டில் மழை படலாம்; ஏறும்போதும் இறங்கும்போதும் பயன்படுத்த குடை எடுத்துக்கொண்டு, உங்கள் பைகளை நனையாமல் பாதுகாத்துக்கொள்ளுங்கள்.',
                'Auto pakkavaatil rain padalaam; umbrella eduthukkondu unga belongings nanaiyaamal paadhugaathukkollunga.',
            )
        else:
            vehicle_tamil = {'Mini': 'மினி கார்', 'Sedan': 'செடான்', 'SUV': 'எஸ் யூ வி'}.get(vehicle, 'வாகனம்')
            advice = say(
                f'Your {vehicle} provides cover during the ride; carry an umbrella for getting in and out and keep your belongings dry.',
                f'நீங்கள் தேர்வு செய்த {vehicle_tamil} பயணத்தில் மழையிலிருந்து பாதுகாப்பு அளிக்கும்; ஏறும்போதும் இறங்கும்போதும் பயன்படுத்த குடை எடுத்துக்கொண்டு, உங்கள் பொருட்களை நனையாமல் பாதுகாத்துக்கொள்ளுங்கள்.',
                f'Unga {vehicle}-la cover irukkum; umbrella eduthukkondu erumboadhum irangumboadhum unga belongings nanaiyaamal paadhugaathukkollunga.',
            )
        if kind in ('heavy', 'storm'):
            advice = say(
                'Check official local weather alerts before leaving; ' + advice[0].lower() + advice[1:],
                'கிளம்புவதற்கு முன் உள்ளூர் வானிலை எச்சரிக்கைகளைச் சரிபாருங்கள்; ' + advice,
                'Purappadum mun ulloor weather warnings paarunga; ' + advice,
            )
        return facts + ' ' + advice

    if kind == 'wind':
        advice = say(
            'Secure loose belongings and take care when boarding and getting out; a covered car is an option if you would prefer more protection than a bike.' if vehicle == 'Bike' else
            'Secure loose belongings and take care when boarding and getting out of your vehicle.',
            'காற்றில் பறக்கக்கூடிய பொருட்களைப் பாதுகாப்பாக வைத்துக்கொண்டு, ஏறும்போதும் இறங்கும்போதும் கவனமாக இருங்கள்; விரும்பினால் பைக்கிற்குப் பதிலாக மூடிய காரைப் பரிசீலிக்கலாம்.' if vehicle == 'Bike' else
            'காற்றில் பறக்கக்கூடிய பொருட்களைப் பாதுகாப்பாக வைத்துக்கொண்டு, வாகனத்தில் ஏறும்போதும் இறங்கும்போதும் கவனமாக இருங்கள்.',
            'Unga belongings paadhugaathukkollunga; Bike-ku covered car consider pannalaam, erumboadhum irangumboadhum care eduthukkondu travel pannunga.' if vehicle == 'Bike' else
            'Unga belongings paadhugaathukkollunga; erumboadhum irangumboadhum care eduthukkondu travel pannunga.',
        )
        return facts + ' ' + advice

    if kind == 'heat' or temperature is not None and temperature >= 33:
        advice = say(
            'Since your ride is open to the weather, carry drinking water and use sun protection while outside.' if vehicle in ('Bike', 'Auto') else
            'Carry drinking water and use sun protection while waiting outside and walking to your vehicle.',
            'உங்கள் வாகனத்தில் வெளிப்புற வெப்பம் படலாம்; குடிநீர் எடுத்துக்கொண்டு, வெளியில் இருக்கும்போது வெயிலிலிருந்து பாதுகாப்பாக இருங்கள்.' if vehicle in ('Bike', 'Auto') else
            'குடிநீர் எடுத்துக்கொண்டு, வாகனத்திற்காக வெளியில் காத்திருக்கும்போது வெயிலிலிருந்து பாதுகாப்பாக இருங்கள்.',
            f'Kudineer eduthukkondu heat-ku prepare pannunga; unga {vehicle} open vehicle, sun protection consider pannalaam.' if vehicle in ('Bike', 'Auto') else
            'Kudineer eduthukkondu heat-ku prepare pannunga; vehicle-ku purappadum mun sun protection consider pannalaam.',
        )
    else:
        advice = say(
            'Dress comfortably for the forecast temperature and keep your travel essentials handy.' if temperature is not None else
            'Keep your travel essentials handy before leaving for the pickup.',
            'எதிர்பார்க்கப்படும் வெப்பநிலைக்கு ஏற்ற உடை அணிந்து, பயணத்திற்குத் தேவையான பொருட்களைத் தயாராக வைத்துக்கொள்ளுங்கள்.' if temperature is not None else
            'புறப்படுவதற்கு முன் பயணத்திற்குத் தேவையான பொருட்களைத் தயாராக வைத்துக்கொள்ளுங்கள்.',
            'Unga payanathirku thevaiyaana belongings eduthukkondu purappadum mun prepare pannunga.',
        )
    # Existing policy determines whether a weather decision is needed.
    # Normal weather already proceeds directly to the final ride summary.
    if kind == 'normal':
        advice += ' ' + say('Let me go through your ride details.', 'உங்கள் பயண விவரங்களைச் சொல்கிறேன்.', 'Unga ride details sollalaam.')
    return facts + ' ' + advice


def question(state):
    if state.get('vehicle')=='Bike' and category(state.get('weather')) in ('rain','heavy','storm','wind'):
        return pick(state,'Would you like to keep your bike? Please say yes or no, or name another vehicle.',
            'பைக்கிலேயே தொடரலாமா? ஆம் அல்லது இல்லை என்று சொல்லுங்கள்; அல்லது வேறு வாகனத்தைக் குறிப்பிடுங்கள்.',
            'Bike-aiye keep pannalaama? Yes illa no sollunga; illa vera vehicle sollunga.')
    return pick(state,'Would you like to keep your pickup time? Please say yes or no, or give another time.',
        'அதே பயண நேரத்தில் தொடரலாமா? ஆம் அல்லது இல்லை என்று சொல்லுங்கள்; அல்லது வேறு நேரத்தைக் குறிப்பிடுங்கள்.',
        'Same pickup time-la continue pannalaama? Yes illa no sollunga; illa vera time sollunga.')


def keep_choice(text,state,engine):
    norm=engine['_friendly_previous_normalized'](text)
    plain={'keep my booking','retain my booking','keep this booking','keep the same booking','keep the same vehicle','retain the same vehicle','same vehicle','keep my pickup time','keep the pickup time','same time','keep the same time',
        'அதே நேரம்','அதே நேரத்தில் தொடரலாம்','இதே நேரம் போதும்','adhe time','same time venum','idhe time podhum'}
    if norm in plain:return 'time'
    v=state.get('vehicle','').casefold()
    aliases={'Bike':('bike','பைக்'),'Mini':('mini','mini car','மினி','மினி கார்'),
        'SUV':('suv','எஸ் யூ வி'),'Sedan':('sedan','செடான்'),'Auto':('auto','ஆட்டோ')}.get(state.get('vehicle'),(v,))
    vehicle=set()
    for alias in aliases:
        for action in ('','keep ','retain ','continue with ','stick with ','go with '):
            for determiner in ('','my ','the ','same ','current '):
                for ending in ('',' itself',' only',' booking',' ride'):
                    vehicle.add(engine['_friendly_previous_normalized'](action+determiner+alias+ending))
        vehicle.update(engine['_friendly_previous_normalized'](alias+ending) for ending in (' keep pannunga',' thaan venum',' dhaan venum',' podhum',' venum'))
    if v=='bike':vehicle|={'பைக்கிலேயே தொடரலாம்','பைக் போதும்','பைக் தான் வேண்டும்','பைக்கே வேண்டும்','அதே பைக்','bike-aiye keep pannunga','bike aiye keep pannunga'}
    if norm in vehicle:return 'vehicle'
    match=re.fullmatch(r'keep\s+(.+)',str(text).strip(),re.I)
    if match:
        words=[word for word,value in engine['number_lexicon'](23).items() if not word.isdigit() and 0<=value<=23]
        clock=r'(?:\d{1,2}(?::\d{2})?|'+'|'.join(re.escape(word) for word in sorted(words,key=len,reverse=True))+r')'
        if not re.fullmatch(r'(?:at\s+)?'+clock+r'\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)\s*(?:please)?[.!?]?',match[1],re.I):return None
        probe=copy.deepcopy(state)
        try:value,error=engine['update_time_memory'](probe,match[1],engine['datetime'].now(engine['TZ']))
        except engine['GuardError']:return None
        if not error and value.isoformat()==state.get('pickup_at'):return 'time'
    return None


class ChoiceSocket:
    def __init__(self,ws,bridge,engine):self.ws,self.bridge,self.engine,self.sid=ws,bridge,engine,None;self.pending=None
    def __getattr__(self,name):return getattr(self.ws,name)
    async def receive_json(self):
        while True:
            row=None
            if self.sid:
                try:row=self.bridge._wx_db.row(self.sid)
                except self.engine['GuardError']:pass
            if self.pending and row:
                if row['ride_id'] or row['summary_nonce']!=self.pending.get('summary_nonce'):
                    self.pending=None
                elif row['played']:
                    message=self.pending;self.pending=None
                    TURN.set(dict(db=self.bridge._wx_db,sid=self.sid,nonce=message.get('summary_nonce'),state=__import__('json').loads(row['state'])))
                    return message
            message=await self.ws.receive_json();kind=message.get('event')
            if kind=='start':self.sid=message.get('call_id')
            if kind=='interrupt':self.pending=None
            context=dict(db=self.bridge._wx_db,sid=self.sid,nonce=message.get('summary_nonce'))
            if self.sid:
                try:
                    row=self.bridge._wx_db.row(self.sid);context['state']=__import__('json').loads(row['state'])
                except (ValueError,KeyError,self.engine['GuardError']):row=None
            state=context.get('state') or {}
            if (kind in ('text','audio') and state.get('stage')=='weather_advisory' and row
                    and message.get('summary_nonce') and message['summary_nonce']==row['summary_nonce'] and not row['played']):
                self.pending=dict(message)
                continue
            TURN.set(context)
            return message


def patch_location_spans(bridge,engine):
    targets=[]
    if bridge is not None:targets.append(getattr(bridge,'_wx_group_slots_module',None))
    for function in (engine.get('collect_details'),engine.get('_movio_optional_weather_original',{}).get('collect_details')):
        if not callable(function):continue
        targets.append(getattr(function,'__globals__',{}))
        try:targets.extend(inspect.getclosurevars(function).nonlocals.values())
        except (TypeError,ValueError):pass
    boundary=re.compile(r'\s+(?:and\s+)?(?:i\s+(?:am|need|want|require)\b|we\s+(?:are|need|want)\b|there\s+(?:is|are)\b|book\s+(?:a\s+)?(?:cab|bike|car|taxi)\b)',re.I)
    for target in targets:
        namespace=target if isinstance(target,dict) else vars(target) if isinstance(target,types.ModuleType) else {}
        parser=namespace.get('Parser')
        if not isinstance(parser,type) or not callable(getattr(parser,'add_place',None)) or getattr(parser,'_friendly_place_boundary_version',None)==VERSION:continue
        previous=parser.add_place
        def add_place(self,role,a,b,clause_start,*args,_previous=previous,**kwargs):
            match=boundary.search(self.raw[a:b])
            if match:b=a+match.start()
            return _previous(self,role,a,b,clause_start,*args,**kwargs)
        parser.add_place=add_place;parser._friendly_place_boundary_version=VERSION


def install_socket(bridge,engine,_route_wrapper=None):
    previous=getattr(bridge,'_wx_endpoint',None)
    if not callable(previous) or getattr(previous,'_friendly_weather_version',None)==VERSION:return False
    while getattr(previous,'_friendly_weather_version',None):
        earlier=getattr(previous,'_friendly_original_endpoint',None)
        if not callable(earlier):
            try:earlier=inspect.getclosurevars(previous).nonlocals.get('previous')
            except (TypeError,ValueError):earlier=None
        if not callable(earlier):raise RuntimeError('Could not upgrade the previous weather socket safely.')
        previous=earlier
    async def wrapped(ws):
        if ws.query_params.get('mode','book')=='cancel':return await previous(ws)
        token=TURN.set(None)
        try:return await previous(ChoiceSocket(ws,bridge,engine))
        finally:TURN.reset(token)
    wrapped=types.FunctionType(wrapped.__code__,engine,wrapped.__name__,wrapped.__defaults__,wrapped.__closure__)
    engine['ChoiceSocket']=ChoiceSocket;engine['TURN']=TURN
    wrapped._friendly_weather_version=VERSION;wrapped._friendly_original_endpoint=previous
    if _route_wrapper is None:
        from starlette.routing import websocket_session
        _route_wrapper=websocket_session
    route=next(r for r in bridge.app.routes if getattr(r,'path','')=='/browser-call')
    route.endpoint=wrapped;route.app=_route_wrapper(wrapped);bridge._wx_endpoint=wrapped
    return True


def install_namespace(engine,root=None,bridge=None,_route_wrapper=None):
    if engine.get('_MOVIO_FRIENDLY_WEATHER_VERSION')==VERSION:
        patch_location_spans(bridge,engine)
        if bridge is not None:install_socket(bridge,engine,_route_wrapper)
        return dict(version=VERSION,already_installed=True)
    if engine.get('_MOVIO_FRIENDLY_WEATHER_VERSION'):
        original=engine.get('_friendly_original')
        if not isinstance(original,dict):
            try:original=inspect.getclosurevars(engine['prepare_turn']).nonlocals.get('previous')
            except (TypeError,ValueError):original=None
        if not isinstance(original,dict):raise RuntimeError('Could not upgrade the previous weather functions safely.')
        engine.update(original);engine.pop('_MOVIO_FRIENDLY_WEATHER_VERSION',None)
    root=Path(root or Path(engine['__file__']).resolve().parent.parent)
    patch_location_spans(bridge,engine)
    keys=('prepare_turn','weather_consented','advisory','weather_question','reply_normalized','install_bridge','install_backend','speech_segments','summary_text')
    previous={key:engine[key] for key in keys}
    base_prepare=engine.get('_movio_optional_weather_original',{}).get('prepare_turn',previous['prepare_turn'])
    engine['_friendly_previous_normalized']=previous['reply_normalized']
    local=threading.local();spoken=[];lock=threading.RLock()
    try:register=inspect.getclosurevars(engine['completion_message']).nonlocals.get('register')
    except (TypeError,ValueError):register=None
    def advisory(state):
        text=report(state);local.question=question(state);local.lang=state.get('lang')
        if text and callable(register):text=register(text,'weather')
        with lock:
            if text:spoken.append(text)
            if len(spoken)>128:del spoken[:-128]
        return text
    def weather_question(lang):
        return local.question if getattr(local,'lang',None)==lang else engine['localized'](lang,
            'Would you like to continue? Please say yes or no.','முன்பதிவைத் தொடரலாமா? ஆம் அல்லது இல்லை என்று சொல்லுங்கள்.',
            'Booking continue pannalaama? Yes illa no sollunga.')
    def summary_text(b,state):
        """MOVIO step-3E: exactly one Tanglish Yes/No instruction."""
        text=previous['summary_text'](b,state)
        if state.get('_wx_mode')=='manual':return text
        if state.get('lang')=='Tanglish':
            text=re.sub(r'(?:\s*Yes\s+illa\s+no\s+sollunga\s*[.!?]*)+\s*$', '', str(text), flags=re.I).rstrip()
            text=re.sub(r'(?i)\bunga\s+ride\s+details\s+(?:sollalaam|solluren|solluraen|solren|sollren)\b',
                        'Unga ride details solluren', text)
            return text+' Yes illa no sollunga.'
        return text+' '+pick(state,'Please say yes or no.','ஆம் அல்லது இல்லை என்று சொல்லுங்கள்.','Yes illa no sollunga.')
    def weather_consented(state):return exemption(state,engine) or previous['weather_consented'](state)
    def normalized(text):
        context=TURN.get();state=(context or {}).get('state') or {}
        if state.get('stage')=='weather_advisory':
            choice=keep_choice(text,state,engine)
            if choice:context['choice']=choice;return 'yes'
        return previous['reply_normalized'](text)
    def prepare_turn(b,weather,state,text,now=None):
        """MOVIO step-3C-v1: deliver normal-weather advice at final review."""
        context=TURN.get() or {};prior_stage=state.get('stage');ack=False
        # A normal-weather notice is acknowledged only by the existing reviewed
        # response record. Never manufacture a nonce, playback ACK or consent.
        record=state.get('_friendly_normal_notice') or {}
        if isinstance(record,dict) and record.get('version')=='step-3C-v1' and not record.get('acknowledged') and context.get('sid'):
            try:
                row=context['db'].row(context['sid'])
                if (row.get('played') and row.get('summary_kind')=='final'
                        and row.get('summary_hash')==record.get('summary_hash')
                        and row.get('summary_hash')==engine['digest'](engine['snapshot'](state))):
                    state['_friendly_normal_notice']={**record,'acknowledged':True}
            except (KeyError,engine['GuardError']):pass
        # Retain the existing real weather-choice/correction protocol unchanged.
        if prior_stage=='weather_advisory' and str(text).strip() and context.get('sid'):
            probe=copy.deepcopy(state)
            parsed=engine['collect_details'](b,probe,text)
            if parsed.get('changed'):
                db=context['db'];row=db.row(context['sid'])
                try:state=db.accept_weather(context['sid'],row['epoch'],context.get('nonce'),state);ack=True
                except engine['GuardError']:pass
        norm=previous['reply_normalized'](text)
        if prior_stage=='weather_advisory' and norm in {'earlier','leave earlier','choose an earlier pickup time','change pickup time','முன்னதாக வேண்டும்','வேறு நேரம் வேண்டும்','earlier venum'}:
            state['stage']='weather_change_time';state['dialogue_state']='COLLECTING_DETAILS'
            return state,pick(state,'What pickup time would you prefer? I will check the forecast for that time.',
                'எத்தனை மணிக்கு வாகனம் வேண்டும்? அந்த நேரத்திற்கான வானிலையைச் சரிபார்க்கிறேன்.',
                'Endha pickup time venum? Andha time-ku weather check pannren.')
        state,answer=previous['prepare_turn'](b,weather,state,text,now=now)
        kind=category(state.get('weather'))
        if state.get('stage') in ('weather_advisory','weather_pending') and kind in ('normal','missing'):
            w=state.setdefault('weather',{});w.pop('_friendly_notice_policy',None)
            reason='forecast_missing' if kind=='missing' else 'no_weather_choice_needed'
            w['_friendly_notice_policy']=dict(version=VERSION,reason=reason,scope=scope(state,engine))
            state.pop('_wx_weather_consent',None)
            state,answer=base_prepare(b,weather,state,'',now=now)
            if state.get('stage')=='confirm':
                state['dialogue_state']='AWAITING_BOOKING_CONFIRMATION'
        if state.get('stage')=='confirm' and (context.get('choice') or ack):
            context.pop('choice',None)
            intro=pick(state,'Sure, let me confirm your updated ride details. ',
                'சரி, உங்கள் பயண விவரங்களை உறுதி செய்துகொள்ளலாம். ',
                'Seri, unga ride details confirm pannalaam. ')
            answer=intro+answer
        # Attach actual normal-weather advice when a final review is ready,
        # including after a failed route lookup. Missing forecasts stay optional.
        if state.get('stage')=='confirm' and state.get('_wx_mode')!='manual' and category(state.get('weather'))=='normal':
            details=copy.deepcopy(state['weather']);details.pop('_friendly_notice_policy',None)
            notice_scope=engine['digest']({**{key:state.get(key) for key in ('pickup','destination','pickup_geo','destination_geo','pickup_at','vehicle','lang')},'weather':details})
            record=state.get('_friendly_normal_notice') or {}
            heard=isinstance(record,dict) and record.get('version')=='step-3C-v1' and record.get('scope')==notice_scope and record.get('acknowledged') is True
            if not heard:
                notice=advisory(state)
                if notice:
                    state['_friendly_normal_notice']=dict(version='step-3C-v1',scope=notice_scope,acknowledged=False,
                        summary_hash=engine['digest'](engine['snapshot'](state)))
                    # Two newlines identify the normal-weather/final-review pair
                    # for the existing speech chunk handler; transcript stays plain.
                    if not str(answer).startswith(notice):answer=notice+'\n\n'+answer
        return state,answer
    def speech_segments(text):
        """MOVIO step-3E: Tanglish sentence pauses with stable weather audio."""
        value=str(text)
        with lock:prefix=next((p for p in reversed(spoken) if value==p or value.startswith(p+'\n') or value.startswith(p+' ')),None)
        runtime=globals().get('_MOVIO_TG_SPEECH_RUNTIME') or {}
        bridge=runtime.get('bridge')
        if bridge is not None and bridge.CURRENT_LANGUAGE.get()=='Tanglish':
            with runtime['lock']:names=tuple(runtime['places'])
            split=lambda part:runtime['phrases'](part,names)
            if prefix:
                rest=value[len(prefix):].strip()
                review_pair=value.startswith(prefix+'\n\n') or bool(rest and ('estimated fare' in rest.casefold() or 'கட்டண' in rest or 'kattanam' in rest.casefold() or 'approximate fare' in rest.casefold()))
                weather_parts=split(prefix)
                if rest and not review_pair:
                    if weather_parts:weather_parts[-1]+=' '+rest
                    else:weather_parts=[value]
                for part in weather_parts:runtime['register'](part,'weather')
                return weather_parts+(split(rest) if rest and review_pair else [])
            if runtime['profile_for'](value)=='closing':return previous['speech_segments'](text)
            return split(value)
        # Retain the existing English/Tamil weather and final-review behaviour.
        if prefix:
            rest=value[len(prefix):].strip()
            normal_review_pair=value.startswith(prefix+'\n\n')
            return [prefix,rest] if rest and (normal_review_pair or 'estimated fare' in rest.casefold() or 'கட்டண' in rest or 'kattanam' in rest.casefold()) else [value]
        return previous['speech_segments'](text)
    def install_bridge(b,db_path,weather=None,_route_wrapper=None):
        result=previous['install_bridge'](b,db_path,weather=weather,_route_wrapper=_route_wrapper)
        patch_location_spans(b,engine)
        install_socket(b,engine,_route_wrapper);return dict(result,friendly_weather=VERSION)
    def install_backend(module,weather=None):
        result=previous['install_backend'](module,weather=weather);install_http(module);return result
    engine.update(advisory=advisory,weather_question=weather_question,weather_consented=weather_consented,
        reply_normalized=normalized,prepare_turn=prepare_turn,speech_segments=speech_segments,
        install_bridge=install_bridge,install_backend=install_backend,summary_text=summary_text,
        _MOVIO_FRIENDLY_WEATHER_VERSION=VERSION,_friendly_original=previous)
    if bridge is not None:install_socket(bridge,engine,_route_wrapper)
    return dict(version=VERSION,silent_missing_forecast=True,final_booking_confirmation=True)


def install_http(module):
    if getattr(module.Handler,'_friendly_weather_version',None)==VERSION:return
    previous=module.Handler.do_GET
    def get(h):
        if h.path.split('?',1)[0]=='/api/weather-booking/friendly-health':
            return h.json(200,dict(ok=True,version=VERSION,final_booking_confirmation=True))
        return previous(h)
    module.Handler.do_GET=get;module.Handler._friendly_weather_version=VERSION
