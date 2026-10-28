import contextvars
"""Sarvam-only STT + DhVaani + Qwen optional extraction, browser call server.
Prototype: route estimates and bookings are not driver dispatch.
"""
import os, re, io, json, uuid, time, base64, asyncio, logging, threading, math
from pathlib import Path
from urllib.parse import urlparse
import requests, numpy as np, soundfile as sf, librosa
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse

app=FastAPI(title="AI Taxi Call — Sarvam")
SESSIONS={}; LOCK=threading.RLock(); PUBLIC_URL=""
TTS=None; PREP=None; LLM=None; TOKENIZER=None; REFERENCE_WAV=None; SARVAM_KEY=None
ROOT=Path(__file__).resolve().parent
HTML=(ROOT/'ai_call_page.html').read_text(encoding='utf-8')
CAPACITY={'Bike':1,'Auto':3,'Mini':4,'Sedan':4,'SUV':6}
RATES={'Bike':(20,7),'Auto':(25,11),'Mini':(40,14),'Sedan':(65,20),'SUV':(95,27)}

def configure(url,*,tts,preprocessing,llm,tokenizer,reference_wav,sarvam_key):
 global PUBLIC_URL,TTS,PREP,LLM,TOKENIZER,REFERENCE_WAV,SARVAM_KEY
 PUBLIC_URL=url.rstrip('/');TTS=tts;PREP=preprocessing;LLM=llm;TOKENIZER=tokenizer
 REFERENCE_WAV=reference_wav;SARVAM_KEY=sarvam_key
 if not SARVAM_KEY:raise ValueError('Sarvam API key required')

def stt_sarvam(wav,lang):
 b=io.BytesIO();sf.write(b,np.asarray(wav,dtype=np.float32),16000,format='WAV')
 data={'model':'saaras:v3','language_code':'en-IN' if lang=='English' else 'ta-IN','mode':'transcribe' if lang=='English' else 'codemix'}
 r=requests.post('https://api.sarvam.ai/speech-to-text',headers={'api-subscription-key':SARVAM_KEY},files={'file':('speech.wav',b.getvalue(),'audio/wav')},data=data,timeout=60)
 r.raise_for_status();j=r.json();text=str(j.get('transcript') or '').strip();code=str(j.get('language_code') or '')
 if re.search(r'[\u0900-\u097f\u0980-\u09ff\u0a80-\u0aff\u0c00-\u0c7f\u0d00-\u0d7f]',text):raise ValueError('Speech was transcribed in another language. Please repeat the selected language clearly.')
 return text,code

def speak(text):
 # Strictly use the user's optimized MOVIO synthesis pipeline, never generic DhVaani.synthesize().
 if not callable(getattr(TTS,'synthesize',None)):
  raise RuntimeError('Custom MOVIO TTS is not initialized')
 group='TAMIL' if re.search(r'[\u0b80-\u0bff]',text) else 'ENGLISH'
 # Tanglish is romanized Tamil mixed with English; the adapter preserves its selected mode.
 if CURRENT_LANGUAGE.get()=='Tanglish':group='TANGLISH'
 with LOCK:
  wav_bytes=TTS.synthesize(text,group)
 return base64.b64encode(wav_bytes).decode()

CURRENT_LANGUAGE=contextvars.ContextVar('movio_selected_language',default='English')

MESSAGES={
 'Tamil':{
  'hello':'வணக்கம்! ஏ ஐ டாக்ஸி முன்பதிவு சேவைக்கு வரவேற்கிறோம். உங்களுக்கு எப்படி உதவலாம்?',
  'intent':'வாகனம் முன்பதிவு செய்ய வேண்டுமா அல்லது ஏற்கனவே உள்ள முன்பதிவை ரத்து செய்ய வேண்டுமா?',
  'count':'எத்தனை பேர் பயணம் செய்யப் போகிறீர்கள்?',
  'vehicle':'பைக், ஆட்டோ, மினி கார், செடான் அல்லது எஸ் யூ வி, எந்த வாகனம் வேண்டும்?',
  'pickup':'எங்கிருந்து உங்களை அழைத்துச் செல்ல வேண்டும்?',
  'destination':'எங்கு செல்ல வேண்டும்?',
  'time':'எந்த நாள், எத்தனை மணிக்கு வாகனம் வேண்டும்?',
  'location':'இந்த இடத்தை சரியாகப் புரிந்துகொண்டேனா: {place}? ஆம் அல்லது இல்லை சொல்லுங்கள்.',
  'location_again':'இடத்தின் பெயரை அல்லது அருகிலுள்ள முக்கிய இடத்தை மீண்டும் சொல்லுங்கள்.',
  'fare_missing':'வரைபடத்தில் சரியான சாலை வழியைப் பெற முடியவில்லை. இடத்தை உறுதிப்படுத்தி மீண்டும் முயற்சி செய்யுங்கள்.',
  'summary':'உங்கள் முன்பதிவு விவரம்: {count} பேர், {vehicle}, {pickup} இலிருந்து {destination} வரை, {when}. சாலை தூரம் சுமார் {km} கிலோமீட்டர், மதிப்பிடப்பட்ட கட்டணம் {fare} ரூபாய். உறுதி செய்யலாமா? ஆம் அல்லது இல்லை சொல்லுங்கள்.',
  'confirmed':'உங்கள் முன்பதிவு கோரிக்கை பதிவு செய்யப்பட்டது. முன்பதிவு எண் {id}. வாகனம் இன்னும் ஒதுக்கப்படவில்லை. நன்றி!',
  'cancelled':'முன்பதிவு ரத்து செய்யப்பட்டது. நன்றி!',
  'which_cancel':'திரையில் உள்ள செயலில் இருக்கும் முன்பதிவுகளில் எந்த எண்ணை ரத்து செய்ய வேண்டும்? ஒன்று, இரண்டு எனச் சொல்லுங்கள்.',
  'no_rides':'ரத்து செய்ய செயலில் இருக்கும் முன்பதிவுகள் இல்லை.',
  'capacity':'{vehicle} வாகனத்தில் அதிகபட்சம் {max} பேர் மட்டுமே பயணம் செய்யலாம். வேறு வாகனம் தேர்ந்தெடுக்கவும்.',
  'retry':'சரியாகக் கேட்கவில்லை. தயவுசெய்து மீண்டும் சொல்லுங்கள்.',
  'wait':'ஒரு நிமிடம், முன்பதிவு தகவலைச் சரிபார்க்கிறேன்.',
 },
 'English':{
  'hello':'Welcome to AI taxi booking. How may I help you today?',
  'intent':'Would you like to book a ride or cancel an existing booking?',
  'count':'How many people will be travelling?',
  'vehicle':'Which vehicle would you like: bike, auto, mini, sedan or SUV?',
  'pickup':'Where should we pick you up?',
  'destination':'Where would you like to go?',
  'time':'What date and time do you need the vehicle?',
  'location':'Did I hear this location correctly: {place}? Please say yes or no.',
  'location_again':'Please repeat the place name or a nearby landmark.',
  'fare_missing':'I could not verify a road route between those locations. Please check the locations and try again.',
  'summary':'Your booking: {count} passengers, {vehicle}, from {pickup} to {destination}, at {when}. Road distance about {km} kilometres, estimated fare {fare} rupees. Shall I confirm? Say yes or no.',
  'confirmed':'Your booking request is recorded. Booking number {id}. A driver has not been assigned yet. Thank you!',
  'cancelled':'Your booking has been cancelled. Thank you!',
  'which_cancel':'Which active booking shown on screen would you like to cancel? Say booking one, two, or its number.',
  'no_rides':'You have no active bookings to cancel.',
  'capacity':'A {vehicle} can carry at most {max} passengers. Please choose a different vehicle.',
  'retry':'I could not understand that. Please repeat.',
  'wait':'One moment while I check the booking details.',
 },
 'Tanglish':{
  'hello':'Vanakkam! AI taxi booking service ku welcome. Ungalukku eppadi help pannalaam?',
  'intent':'Ride book pannanuma, illa existing booking cancel pannanuma?',
  'count':'Ethana peru travel panna poreenga?',
  'vehicle':'Bike, auto, mini car, sedan, SUV, edhu venum?',
  'pickup':'Enga irundhu pickup venum?',
  'destination':'Enga poganum?',
  'time':'Endha naal, ethana manikku vehicle venum?',
  'location':'Neenga sonna place {place}, correct ah? Yes illa no sollunga.',
  'location_again':'Place name illa nearby landmark marubadiyum sollunga.',
  'fare_missing':'Indha route ku map la road distance verify panna mudiyala. Places check pannunga.',
  'summary':'Booking details: {count} peru, {vehicle}, {pickup} la irundhu {destination} ku, {when}. Road distance around {km} kilometres, approximate fare {fare} rupees. Confirm pannalama? Yes illa no sollunga.',
  'confirmed':'Unga booking request record aayiduchu. Booking number {id}. Driver innum assign aagala. Nandri!',
  'cancelled':'Unga booking cancel aayiduchu. Nandri!',
  'which_cancel':'Screen la irukkura active booking la edha cancel pannanum? Booking one, two nu sollunga.',
  'no_rides':'Cancel panna active bookings illa.',
  'capacity':'{vehicle} la maximum {max} peru dhaan pogalaam. Vera vehicle select pannunga.',
  'retry':'Sariya kekkala. Thirumba sollunga.',
  'wait':'Oru nimisham booking details check panren.',
 }}

def say(s,key,**kw):return MESSAGES[s['lang']][key].format(**kw)

def yesno(t):
 x=speech_text(t)
 if not x:return None
 if re.search(r"\b(not sure|maybe|perhaps|don t know|dont know)\b|தெரியவில்லை|தெரியாது",x):return None
 if re.search(r"\b(not correct|not right|don t book|dont book|do not book|do not confirm)\b",x):return False
 boundary=r'[\w\u0b80-\u0bff]'
 def has(phrases):
  return any(re.search(r'(?<!'+boundary+r')'+re.escape(p)+r'(?!'+boundary+r')',x) for p in phrases)
 negative=has(('no','nope','cancel','incorrect','illa','illai','vendam','vendaam','வேண்டாம்','இல்லை','இல்ல','ரத்து','தவறு'))
 positive=has(('yes','yeah','yep','okay','ok','confirm','correct','go ahead','book it','aama','aamaa','amam','aamam','aam','seri','sari','ஆம்','ஆமாம்','ஆமா','ஆமாங்க','சரி','சரிதான்','சரியாக உள்ளது','உறுதி செய்யுங்கள்'))
 if positive and negative:return None
 if negative:return False
 if positive:return True
 return None

def number(t):
 t=t.lower().strip();words={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'ஒரு':1,'ஒன்று':1,'இரண்டு':2,'மூன்று':3,'நான்கு':4,'ஐந்து':5,'ஆறு':6,'ஏழு':7,'எட்டு':8,'oru':1,'rendu':2,'moonru':3,'naalu':4,'anju':5,'aaru':6,'onnu':1,'first':1,'second':2,'third':3}
 m=re.search(r'\b\d{1,2}\b',t)
 if m:return int(m.group())
 for k,v in sorted(words.items(),key=lambda x:-len(x[0])):
  if re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)',t):return v
 return None

def vehicle(t):
 x=speech_text(t)
 patterns=[
  (r'\b(?:bike|bike taxi|two wheeler)\b|பைக்','Bike'),
  (r'\b(?:auto|auto rickshaw)\b|ஆட்டோ','Auto'),
  (r'\bs\s*u\s*v\b|\b(?:six seater|6 seater)\b|எஸ்\s*ய[ுூ]?\s*வி|எஸ்யூவி','SUV'),
  (r'\bsedan\b|செடான்','Sedan'),
  (r'\b(?:mini|car|cab|taxi)\b|மினி|கார்|கேப்|டாக்ஸி','Mini'),
 ]
 found={name for pat,name in patterns if re.search(pat,x)}
 # 'SUV car' remains SUV, while 'SUV or auto' requires clarification.
 if found & {'SUV','Sedan','Bike','Auto'}:found.discard('Mini')
 return next(iter(found)) if len(found)==1 else None

def extract_time(t):
 x=str(t).strip()
 if re.search(r'(?i)\b(now|right now|immediately|asap|ippove|ippo|ippodhu|ippozhudhu)\b|இப்போ|இப்போது|இப்பொழுது|உடனே',x):return 'Now'
 if re.search(r'(?i)\b(today|tomorrow|tonight|morning|evening|night|am|pm|o.clock|naalaiku|innaiku|manikku)\b|இன்று|நாளை|மணி|காலை|மாலை|இரவு',x):return x[:100]
 if re.search(r'\b\d{1,2}:\d{2}\b',x):return x[:100]
 return None

def clean_place(t):
 x=str(t).strip(' .,!?:;')
 x=re.sub(r'(?i)^(?:i want to go to|i need to go to|take me to|going to|go to|my destination is|destination is|pickup from|pick me up from|i am at|i.m at|from)\s+','',x)
 x=re.sub(r'(?i)^(?:naan|nan|enakku|enaku)\s+','',x)
 x=re.sub(r'^(?:நான்|எனக்கு)\s*','',x)
 x=re.sub(r'(?i)\s+(?:poganum|poganu|ponum|poga|venum|irundhu|la irundhu|i am waiting|waiting at the entrance)$','',x)
 x=re.sub(r'\s*(?:போகணும்|போகனும்|போக வேண்டும்|செல்ல வேண்டும்|காத்திருக்கிறேன்|இலிருந்து|லிருந்து|இருந்து)$','',x).strip()
 return canonical_place(x)

def plausible_place(t):
 if not t or len(str(t))>180:return False
 x=clean_place(t)
 if not x or speech_text(x) in VOICE_GENERIC_PLACES:return False
 if re.search(r'[\u0900-\u097f\u0980-\u09ff\u0a80-\u0aff\u0c00-\u0c7f\u0d00-\u0d7f]',x):return False
 if extract_time(x):return False
 if vehicle(x) and x not in VOICE_PLACE_ALIASES and not re.search(r'(?i)\b(from|to|at|near)\b|இலிருந்து|க்கு|போக',x):return False
 return len(x)>=3 and len(x.split())<=12

# Geocoding: request-bound, cached, fail closed. Nominatim usage policy: <=1 request/sec, identify app.
GEOCODE_CACHE={}; GEO_LOCK=threading.Lock(); LAST_GEO=[0.0]
def geocode(q):
    """MOVIO step-3B-v1: match each query to a provider-named place."""
    import copy
    import math
    import unicodedata

    q = clean_place(q)
    if not plausible_place(q):
        return None
    city = os.environ.get('MOVIO_SERVICE_CITY', 'Chennai').strip() or 'Chennai'
    box = os.environ.get('MOVIO_GEO_VIEWBOX', '79.95,13.35,80.45,12.65')
    try:
        west, north, east, south = [float(value) for value in box.split(',')]
        if not all(math.isfinite(value) for value in (west, north, east, south)) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Invalid MOVIO_GEO_VIEWBOX')

    def words(value):
        value = unicodedata.normalize('NFKC', str(value or '')).casefold()
        return tuple(re.findall(r'[a-z0-9]+|[\u0b80-\u0bff]+', value))

    stop = {'the', 'of', 'and', 'at', 'in'}
    city_words = set(words(city))
    variants = {str(q)}
    for canonical, aliases in VOICE_PLACE_ALIASES.items():
        aliases = [value for value in aliases if isinstance(value, str)]
        if words(q) in [words(value) for value in [canonical] + aliases]:
            variants.update([canonical] + aliases)
    targets = []
    for variant in variants:
        tokens = tuple(value for value in words(variant) if value not in stop)
        core = tuple(value for value in tokens if value not in city_words)
        if tokens:
            targets.append((tokens, core or tokens))

    def coordinates(item):
        if not isinstance(item, dict):
            return None
        try:
            lat = float(item.get('lat'))
            lng = float(item.get('lon', item.get('lng')))
            return (lat, lng) if math.isfinite(lat) and math.isfinite(lng) and south <= lat <= north and west <= lng <= east else None
        except (ValueError, TypeError, OverflowError):
            return None

    def match_score(item):
        if coordinates(item) is None:
            return 0
        names = [item.get('name')]
        details = item.get('namedetails')
        if isinstance(details, dict):
            names += [value for value in details.values() if isinstance(value, str)]
        display = str(item.get('display_name') or item.get('address') or '')
        if not item.get('name'):
            names.append(display.split(',')[0])
        best = 0
        for name in names:
            for spelling in str(name or '').split(';'):
                tokens = tuple(value for value in words(spelling) if value not in stop)
                if not tokens:
                    continue
                # Provider-derived acronym matching: e.g. VIT -> Vellore
                # Institute of Technology. No coordinates or aliases invented.
                acronyms = {''.join(value[0] for value in tokens[start:start + length])
                            for start in range(len(tokens)) for length in range(2, 6)
                            if len(tokens[start:start + length]) == length and all(value.isalpha() for value in tokens[start:start + length])}
                for full, core in targets:
                    if full == tokens:
                        best = max(best, 120)
                    elif core == tokens:
                        best = max(best, 110)
                    elif all(value in tokens or len(value) >= 2 and value in acronyms
                             or len(value) == 1 and len(core) > 1 and any(token.startswith(value) for token in tokens)
                             for value in core):
                        best = max(best, 80)
        # Full street addresses may need the provider's address components.
        # A locality-only query never matches merely because a campus address
        # mentions that locality or a road named after it.
        context = set(words(display))
        address = item.get('address')
        if isinstance(address, dict):
            for value in address.values():
                context.update(words(value))
        street_words = {'road', 'street', 'avenue', 'lane', 'salai', 'சாலை', 'தெரு'}
        for full, core in targets:
            if (any(value.isdigit() for value in full) or street_words.intersection(full)) and all(value in context for value in core):
                best = max(best, 60)
        return best

    key = (city.casefold(), box, str(q).casefold())
    # Use the original shared lock and cache. Reject stale mismatched entries
    # lazily, leaving unrelated successful queries intact.
    with GEO_LOCK:
        cached = GEOCODE_CACHE.get(key)
        if cached is not None and match_score(cached):
            return copy.deepcopy(cached)
        GEOCODE_CACHE.pop(key, None)
        delay = 1.1 - (time.monotonic() - LAST_GEO[0])
        if delay > 0:
            time.sleep(delay)
        LAST_GEO[0] = time.monotonic()
        endpoint = os.environ.get('MOVIO_GEOCODER_URL', 'https://nominatim.openstreetmap.org/search')
        # The existing service box already limits geography; appending Chennai
        # can bias a suburb query toward an unrelated Chennai institution.
        response = requests.get(endpoint, params={
            'q': q, 'format': 'json', 'limit': 10, 'countrycodes': 'in',
            'addressdetails': 1, 'namedetails': 1, 'viewbox': box, 'bounded': 1,
        }, headers={'User-Agent': 'MOVIO-Ride-Booking-Research/5.1', 'Accept-Language': 'en'}, timeout=12)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError('Unexpected geocoder response')
        ranked = [(match_score(item), index, item) for index, item in enumerate(payload) if isinstance(item, dict)]
        ranked = [item for item in ranked if item[0] > 0]
        result = None
        if ranked:
            _, _, item = max(ranked, key=lambda item: (item[0], -item[1]))
            lat, lng = coordinates(item)
            name = item.get('name') or str(item.get('display_name', '')).split(',')[0]
            result = dict(name=name, label=q if q in VOICE_PLACE_ALIASES else name,
                address=item.get('display_name', ''), lat=lat, lng=lng,
                namedetails={key: value for key, value in (item.get('namedetails') or {}).items() if isinstance(value, str)})
        GEOCODE_CACHE[key] = copy.deepcopy(result)
        return copy.deepcopy(result)

def road_fare(s):
 a=s['pickup_geo'];b=s['destination_geo']
 if not a or not b:return None
 u=f"https://router.project-osrm.org/route/v1/driving/{a['lng']},{a['lat']};{b['lng']},{b['lat']}"
 r=requests.get(u,params={'overview':'false'},timeout=18);r.raise_for_status();j=r.json()
 if j.get('code')!='Ok' or not j.get('routes'):return None
 km=j['routes'][0]['distance']/1000
 if km<=0 or km>400:return None
 base,rate=RATES[s['vehicle']]
 return {'km':round(km,1),'fare':round((base+km*rate)*1.05)}

def extract_complex(t,s):
 # Optional Qwen slot extraction; never treat generated coordinates or fares as facts.
 if LLM is None or TOKENIZER is None:return {}
 import torch
 prompt=("Extract only explicitly stated taxi ride slots from the message. Output JSON ONLY: "
         '{"pickup":null,"destination":null,"vehicle":null,"time":null,"passengers":null}. '
         "No invented values. Tamil, English and Tanglish are possible. Text: "+t)
 try:
  inputs=TOKENIZER.apply_chat_template([{'role':'user','content':prompt}],add_generation_prompt=True,return_tensors='pt',return_dict=True)
  inputs={k:v.to(next(LLM.parameters()).device) for k,v in inputs.items()}
  with LOCK,torch.inference_mode():out=LLM.generate(**inputs,max_new_tokens=120,do_sample=False,pad_token_id=TOKENIZER.eos_token_id)
  raw=TOKENIZER.decode(out[0][inputs['input_ids'].shape[1]:],skip_special_tokens=True)
  obj=json.loads(re.search(r'\{.*?\}',raw,re.S).group())
  return obj if isinstance(obj,dict) else {}
 except Exception as e:
  logging.warning('Qwen extraction unavailable: %s',str(e)[:120]);return {}

def new_session(lang,mode):
 return {'lang':lang,'mode':mode,'stage':'intent' if mode=='book' else 'cancel_select',
  'count':None,'vehicle':None,'pickup':None,'destination':None,'pickup_geo':None,'destination_geo':None,
  'when':None,'fare':None,'pending':None,'active_rides':[],'created':time.time()}

def next_question(s):
 for key,stage in [('count','count'),('vehicle','vehicle'),('pickup','pickup'),('destination','destination'),('when','time')]:
  if not s[key]:s['stage']=stage;return say(s,stage)
 s['stage']='fare';return say(s,'wait')

def handle(s,text):
 t=text.strip();stage=s['stage'];yn=yesno(t)
 if stage=='intent':
  if re.search(r'(?i)\b(cancel|cancellation)\b|ரத்து|கேன்சல்',t):s['mode']='cancel';s['stage']='cancel_select';return say(s,'which_cancel'),None
  n=number(t) if re.search(r'(?i)\b(people|passengers|persons|peru)\b|பேர்|பயணிகள்',t) else None
  if n and 1<=n<=20:s['count']=n
  v=vehicle(t)
  if v=='Mini' and not re.search(r'(?i)\bmini\b|மினி',t):v=None
  if v and s['count'] and s['count']<=CAPACITY[v]:s['vehicle']=v
  return next_question(s),None
 if stage=='cancel_select':
  n=number(t)
  rides=s['active_rides']
  match=next((r for i,r in enumerate(rides,1) if n in (i,int(r['id']))),None) if n else None
  if not match:return say(s,'which_cancel'),None
  s['selected_cancel']=match;s['stage']='cancel_confirm'
  return say(s,'location',place=f"{match['vehicle']} {match['pickup']} to {match['destination']}"),None
 if stage=='cancel_confirm':
  if yn is True:
   s['stage']='cancel_pending';return say(s,'wait'),{'type':'cancel','ride_id':s['selected_cancel']['id']}
  if yn is False:s['stage']='cancel_select';return say(s,'which_cancel'),None
  return say(s,'retry'),None
 if stage=='count':
  n=number(t)
  if not n or n>20:return say(s,'count'),None
  s['count']=n
  if s['vehicle'] and n>CAPACITY[s['vehicle']]:s['vehicle']=None
  return next_question(s),None
 if stage=='vehicle':
  v=vehicle(t)
  if not v:return say(s,'vehicle'),None
  if s['count']>CAPACITY[v]:return say(s,'capacity',vehicle=v,max=CAPACITY[v])+' '+say(s,'vehicle'),None
  s['vehicle']=v;return next_question(s),None
 if stage in ('pickup','destination'):
  route=route_places(t)
  place=route.get(stage) or clean_place(t)
  if route.get('destination') and stage=='pickup':s['suggested_destination']=route['destination']
  if not plausible_place(place):return say(s,'location_again'),None
  try:g=geocode(place)
  except Exception as e:logging.warning('Geocode error %s',e);g=None
  if not g and len(t.split())>=3:
   extracted=extract_complex(t,s)
   alternative=extracted.get(stage)
   if isinstance(alternative,str) and alternative.strip() and len(alternative)<100:
    place=clean_place(alternative)
    try:g=geocode(place)
    except Exception as e:logging.warning('Qwen place geocode error %s',e)
  if not g:return say(s,'location_again'),None
  s['pending']={'slot':stage,'raw':place,'geo':g};s['stage']='location_confirm'
  return say(s,'location',place=location_label(g)),None
 if stage=='location_confirm':
  if yn is True:
   pending=s.pop('pending');slot=pending['slot'];s[slot]=pending['raw'];s[slot+'_geo']=pending['geo']
   suggested=s.pop('suggested_destination',None) if slot=='pickup' else None
   if suggested and not s.get('destination'):
    try:g=geocode(suggested)
    except Exception:g=None
    if g:
     s['pending']={'slot':'destination','raw':suggested,'geo':g};s['stage']='location_confirm'
     return say(s,'location',place=location_label(g)),None
   return next_question(s),None
  if yn is False:
   slot=s['pending']['slot'];s['pending']=None;s['stage']=slot
   return say(s,'location_again'),None
  return say(s,'retry'),None
 if stage=='time':
  tm=extract_time(t)
  if not tm:return say(s,'time'),None
  s['when']=tm;s['stage']='fare';return say(s,'wait'),None
 if stage=='confirm':
  if yn is True:
   s['stage']='booking_pending';return say(s,'wait'),{'type':'book','details':{k:s[k] for k in ('count','vehicle','pickup','destination','when','fare','pickup_geo','destination_geo')}}
  if yn is False:s['stage']='done';return say(s,'cancelled'),None
  return say(s,'retry'),None
 return say(s,'retry'),None

@app.get('/health')
def health():return {'ok':True,'stt':'Sarvam Saaras v3','tts':'User MOVIO optimized DhVaani (strict)','llm':'Qwen optional','mode':'browser demo'}
@app.get('/call-page')
def call_page():return HTMLResponse(HTML,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})

@app.websocket('/browser-call')
async def browser_call(ws:WebSocket):
 if ws.headers.get('origin','').rstrip('/')!=PUBLIC_URL:
  await ws.close(code=1008);return
 lang=ws.query_params.get('language','Tamil');mode=ws.query_params.get('mode','book')
 if lang not in MESSAGES or mode not in ('book','cancel'):
  await ws.close(code=1008);return
 await ws.accept();language_token=CURRENT_LANGUAGE.set(lang);s=new_session(lang,mode);sid=uuid.uuid4().hex;SESSIONS[sid]=s
 async def reply(text,extra=None):
  payload=await asyncio.to_thread(speak,text)
  await ws.send_json({'event':'reply','text':text,'payload':payload,'stage':s['stage'],**(extra or {})})
 try:
  await ws.send_json({'event':'ready'})
  await reply(say(s,'hello')+' '+(say(s,'which_cancel') if mode=='cancel' else ''))
  while True:
   msg=await ws.receive_json();kind=msg.get('event')
   if kind=='active_rides':
    s['active_rides']=[r for r in msg.get('rides',[]) if isinstance(r,dict) and str(r.get('status')) in ('requested','scheduled','accepted','arriving','in_progress','needs_location')][:30]
    if mode=='cancel' and not s['active_rides']:await reply(say(s,'no_rides'),{'done':True})
    continue
   if kind=='result':
    if s['stage'] not in ('booking_pending','cancel_pending'):continue
    if msg.get('ok'):
     s['stage']='done';await reply(say(s,'confirmed',id=msg.get('id','')) if s['mode']=='book' else say(s,'cancelled'),{'booking_id':msg.get('id'),'done':True,'status':'Booking recorded' if s['mode']=='book' else 'Booking cancelled'})
    else:
     reason=str(msg.get('error') or 'The website rejected the request')[:200]
     logging.warning('Account action rejected: %s',reason)
     s['stage']='blocked'
     await ws.send_json({'event':'error','message':reason,'fatal':True})
     key='active_booking' if 'active ride' in reason.lower() or 'active booking' in reason.lower() else 'booking_failed'
     await reply(say(s,key),{'done':True,'status':'Booking not created'})
    continue
   if kind!='audio' or s['stage']=='done':continue
   try:
    encoded=msg.get('payload','')
    if len(encoded)>3_000_000:raise ValueError('Audio exceeds 3 MB')
    data=base64.b64decode(encoded,validate=True)
    if len(data)>2_250_000:raise ValueError('Audio too long')
    def turn():
     import av
     c=av.open(io.BytesIO(data));frames=[];sr=None
     for f in c.decode(audio=0):
      a=f.to_ndarray().astype(np.float32)
      if a.ndim>1:a=a.mean(axis=0)
      frames.append(a);sr=f.sample_rate
     c.close()
     if not frames or not sr:raise ValueError('No speech audio received')
     a=np.concatenate(frames)
     if len(a)/sr>28:raise ValueError('Please speak for less than 28 seconds')
     a=librosa.resample(a,orig_sr=sr,target_sr=16000) if sr!=16000 else a
     text,code=stt_sarvam(a,lang)
     if not text:return None,None,None
     answer,action=handle(s,text)
     if s['stage']=='fare':
      try:s['fare']=road_fare(s)
      except Exception as e:logging.warning('Route lookup error: %s',e);s['fare']=None
      if not s['fare']:
       s['destination']=None;s['destination_geo']=None;s['stage']='destination';answer=say(s,'fare_missing')+' '+say(s,'destination')
      else:
       s['stage']='confirm';answer=say(s,'summary',count=s['count'],vehicle=s['vehicle'],pickup=s['pickup'],destination=s['destination'],when=s['when'],km=s['fare']['km'],fare=s['fare']['fare'])
     return text,answer,action
    text,answer,action=await asyncio.to_thread(turn)
    if not text:await reply(say(s,'retry'));continue
    await ws.send_json({'event':'heard','text':text})
    if action:await ws.send_json({'event':'action',**action,'request_id':uuid.uuid4().hex})
    else:await reply(answer)
   except Exception as e:
    logging.exception('Voice turn failed');await ws.send_json({'event':'error','message':str(e)[:180]})
 except WebSocketDisconnect:pass
 except Exception as exc:
  logging.exception('Voice call failed')
  try:
   await ws.send_json({'event':'error','message':'Voice server error: '+str(exc)[:160],'fatal':True})
   await ws.close(code=1011)
  except Exception:pass
 finally:
  CURRENT_LANGUAGE.reset(language_token)
  SESSIONS.pop(sid,None)


import unicodedata
VOICE_MESSAGE_UPDATES = {
 'English': {'active_booking':'You already have an active booking. Please cancel it or finish that ride in your dashboard before requesting another vehicle.', 'booking_failed':'The booking could not be saved. Check your dashboard before trying again.', 'vehicle':'Which vehicle would you like: bike, auto, mini, sedan or SUV? For SUV, say S U V clearly.'},
 'Tamil': {'active_booking':'உங்களுக்கு ஏற்கனவே ஒரு முன்பதிவு உள்ளது. புதிய வாகனம் முன்பதிவு செய்வதற்கு முன், உங்கள் டாஷ்போர்டில் பழைய முன்பதிவை ரத்து செய்யவும் அல்லது பயணத்தை முடிக்கவும்.', 'booking_failed':'முன்பதிவை சேமிக்க முடியவில்லை. மீண்டும் முயற்சி செய்வதற்கு முன் உங்கள் டாஷ்போர்டை சரிபார்க்கவும்.', 'vehicle':'பைக், ஆட்டோ, மினி கார், செடான் அல்லது எஸ் யூ வி, எந்த வாகனம் வேண்டும்? எஸ் யூ வி வேண்டுமெனில் மூன்று எழுத்துகளையும் சொல்லுங்கள்.'},
 'Tanglish': {'active_booking':'Ungalukku already oru active booking irukku. Pudhu vehicle book panna, dashboard la pazhaiya booking cancel pannunga illa ride mudiyattum.', 'booking_failed':'Booking save aagala. Thirumba try pannradhukku munnaadi dashboard check pannunga.', 'vehicle':'Bike, auto, mini car, sedan, SUV, edhu venum? SUV na S U V nu moonu letters sollunga.'},
}
VOICE_PLACE_ALIASES = {
 'Chennai Central': ('chennai central','central railway station','சென்னை சென்ட்ரல்','சென்னை சென்ட்ரலில்','சென்ட்ரலில்','சென்ட்ரல்','சென்னை மத்திய'),
 'Chennai Airport': ('chennai airport','chennai international airport','சென்னை ஏர்போர்ட்','சென்னை விமான நிலையம்'),
 'Kottivakkam': ('kottivakkam','கொட்டிவாக்கம்'),
 'Chromepet': ('chromepet','chrome pit','chrompet','குரோம்பேட்டை','குரோம்பேட்'),
 'Velachery': ('velachery','வேளச்சேரி'),
 'T Nagar': ('t nagar','t. nagar','டி நகர்','தியாகராய நகர்'),
 'Anna Nagar': ('anna nagar','அண்ணா நகர்'),
}
VOICE_GENERIC_PLACES = {'gate','entrance','exit','main gate','நுழைவாயில்','வாசல்','நுழைவாயிலில்'}
def speech_text(text):
 x=unicodedata.normalize('NFKC',str(text)).casefold()
 x=re.sub(r'[\u200b-\u200f\u2060\ufeff]','',x)
 x=''.join(' ' if unicodedata.category(c).startswith('P') else c for c in x)
 return re.sub(r'\s+',' ',x).strip()
def canonical_place(t):
 x=str(t).strip(' .,!?:;');normalized=speech_text(x)
 if normalized in VOICE_GENERIC_PLACES:return ''
 matches=[]
 for canonical,aliases in VOICE_PLACE_ALIASES.items():
  if any(re.search(r'(?<![A-Za-z])'+re.escape(a)+r'(?![A-Za-z])',normalized) for a in aliases):matches.append(canonical)
 return matches[0] if len(matches)==1 else x[:120]
def route_places(t):
 x=str(t).strip(' .,!?:;')
 for pattern in (
  r'(?i)^(?:i am going |i want to go |take me )?from\s+(.+?)\s+to\s+(.+)$',
  r'^(.+?)\s+(?:இருந்து|இலிருந்து|லிருந்து)\s+(.+)$',
  r'(?i)^(.+?)\s+(?:la\s+)?irundhu\s+(.+)$',
 ):
  m=re.match(pattern,x)
  if m:return {'pickup':clean_place(m.group(1)),'destination':clean_place(m.group(2))}
 return {}
def location_label(g):
 label=g.get('label') or g.get('name') or 'Selected location'
 if len(label)>65:label=label[:65].rsplit(' ',1)[0]+'…'
 return label

for _lang,_updates in VOICE_MESSAGE_UPDATES.items():
 MESSAGES[_lang].update(_updates)
VOICE_PATCH_VERSION="5.2"

MESSAGES['English']['vehicle'] = 'Which vehicle would you like: bike, auto, mini, sedan or SUV?'
VOICE_MESSAGE_UPDATES['English']['vehicle'] = 'Which vehicle would you like: bike, auto, mini, sedan or SUV?'

MESSAGES['Tamil']['vehicle'] = 'பைக், ஆட்டோ, மினி கார், செடான் அல்லது எஸ் யூ வி, எந்த வாகனம் வேண்டும்?'
VOICE_MESSAGE_UPDATES['Tamil']['vehicle'] = 'பைக், ஆட்டோ, மினி கார், செடான் அல்லது எஸ் யூ வி, எந்த வாகனம் வேண்டும்?'

MESSAGES['Tanglish']['vehicle'] = 'Bike, auto, mini car, sedan, SUV, edhu venum?'
VOICE_MESSAGE_UPDATES['Tanglish']['vehicle'] = 'Bike, auto, mini car, sedan, SUV, edhu venum?'
