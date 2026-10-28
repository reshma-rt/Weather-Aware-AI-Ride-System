"""Shared MOVIO customer-care rules. Pure functions: no network, GPS, DB or TTS.

Call recommend() with a verified context; call remember_delivered() only after
actual display/playback/dismissal. Generation alone never acknowledges advice.
"""
import copy
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    TZ=ZoneInfo('Asia/Kolkata')
except (ImportError,KeyError):
    TZ=timezone(timedelta(hours=5,minutes=30))

VERSION='customer-care-engine-1.0'
RULE_IDS=('rain_preparation','heat_protection','late_night_safety','pickup_guidance',
    'otp_safety','passenger_comfort','destination_reminder','departure_readiness',
    'traffic_awareness','accessibility_assistance','phone_readiness','arrival_care')
DEFAULT_POLICY=dict(rain_probability_pct=60,warm_c=32,hot_c=38,
    weather_max_age_s=1800,weather_hour_tolerance_s=3600,
    location_max_age_s=900,eta_max_age_s=180,traffic_max_age_s=300,
    departure_window_minutes=20,night_start_hour=22,night_end_hour=5,
    trusted_traffic_sources=[],
    capacities={'Bike':1,'Auto':3,'Mini':4,'Sedan':4,'SUV':6})
SCORE_WEIGHTS=dict(urgency=4,safety=3,relevance=2,evidence=1)
RAIN_CODES={51,53,55,56,57,61,63,65,66,67,80,81,82}
STORM_CODES={95,96,99}
STATUS_ACTIVE={'scheduled','requested','accepted','arriving','in_progress'}
LANGUAGES={'english':'English','en':'English','en-in':'English','tamil':'Tamil',
    'ta':'Tamil','ta-in':'Tamil','tanglish':'Tanglish'}


def _text(value,limit=160):
    return re.sub(r'\s+',' ',str(value or '')).strip()[:limit]


def _number(value,low=None,high=None):
    if isinstance(value,bool) or value is None or value=='':return None
    try:result=float(value)
    except (ValueError,TypeError,OverflowError):return None
    return result if math.isfinite(result) and (low is None or result>=low) and (high is None or result<=high) else None


def _time(value):
    try:
        if isinstance(value,datetime):result=value
        elif isinstance(value,(int,float)) and not isinstance(value,bool):result=datetime.fromtimestamp(value,TZ)
        elif isinstance(value,str) and value.strip():result=datetime.fromisoformat(value.strip().replace('Z','+00:00'))
        else:return None
        return (result.replace(tzinfo=TZ) if result.tzinfo is None else result.astimezone(TZ))
    except (ValueError,TypeError,OverflowError,OSError):return None


def _fresh(value,now,seconds):
    instant=_time(value)
    return instant is not None and -60<=(now-instant).total_seconds()<=seconds


def _pick(lang,en,ta,tanglish):return {'English':en,'Tamil':ta,'Tanglish':tanglish}[lang]


def _fmt(value):return format(float(value),'.1f').rstrip('0').rstrip('.')


def _policy(value):
    result=copy.deepcopy(DEFAULT_POLICY)
    if value is not None and not isinstance(value,dict):raise ValueError('policy must be a dictionary')
    for key,value in (value or {}).items():
        if key not in result:raise ValueError('Unknown policy key: '+str(key))
        if key=='capacities':
            if not isinstance(value,dict):raise ValueError('capacities must be a dictionary')
            for vehicle,n in value.items():
                v=_number(n,1,16)
                if vehicle not in result[key] or v is None or not v.is_integer():raise ValueError('Invalid vehicle capacity')
                result[key][vehicle]=int(v)
        elif key=='trusted_traffic_sources':
            if not isinstance(value,(list,tuple)) or not all(isinstance(x,str) and x.strip() for x in value):raise ValueError('Traffic sources must be configured explicitly')
            result[key]=[_text(x,80).casefold() for x in value]
        else:
            number=_number(value,0)
            if number is None:raise ValueError('Invalid policy value: '+key)
            result[key]=number
    if not 0<=result['rain_probability_pct']<=100:raise ValueError('Invalid rain threshold')
    if not 0<=result['night_start_hour']<=23 or not 0<=result['night_end_hour']<=23:raise ValueError('Invalid night hours')
    if result['warm_c']>result['hot_c']:raise ValueError('warm_c must not exceed hot_c')
    return result


def _weather(raw,target,now,policy):
    """Use real, fresh Open-Meteo points for the target hour; never guess values."""
    if not isinstance(raw,dict) or raw.get('status')!='ok' or target is None:return None
    if _text(raw.get('source')).casefold().replace(' ','-')!='open-meteo':return None
    if not _fresh(raw.get('fetched_at'),now,policy['weather_max_age_s']):return None
    rows=raw.get('points');points=[]
    if not isinstance(rows,list):return None
    for row in rows:
        if not isinstance(row,dict):continue
        when=_time(row.get('valid_at'))
        if when is None or abs((when-target).total_seconds())>policy['weather_hour_tolerance_s']:continue
        code=_number(row.get('weather_code'),0,99)
        code=int(code) if code is not None and code.is_integer() else None
        temp=_number(row.get('temperature_2m'),-100,70)
        chance=_number(row.get('precipitation_probability'),0,100)
        wind=_number(row.get('wind_speed_10m'),0,400)
        if code is None and temp is None and chance is None:continue
        points.append(dict(role=_text(row.get('location'),20),weather_code=code,
            temperature_c=temp,rain_probability_pct=chance,wind_kmh=wind,valid_at=when.isoformat()))
    if not points:return None
    codes={p['weather_code'] for p in points}
    temperatures=[p['temperature_c'] for p in points if p['temperature_c'] is not None]
    chances=[p['rain_probability_pct'] for p in points if p['rain_probability_pct'] is not None]
    return dict(source='Open-Meteo',points=points,
        rain=bool(codes&(RAIN_CODES|STORM_CODES)) or any(p>=policy['rain_probability_pct'] for p in chances),
        storm=bool(codes&STORM_CODES),heavy_rain=bool(codes&{65,67,82}),max_temperature_c=max(temperatures) if temperatures else None,
        max_rain_probability_pct=max(chances) if chances else None)


def _locality(context,now,policy):
    location=context.get('current_location') or {}
    if not isinstance(location,dict) or location.get('status')!='granted':return ''
    if location.get('locality_status')!='ok' or not _fresh(location.get('observed_at'),now,policy['location_max_age_s']):return ''
    name=_text(location.get('locality'),100)
    # The existing reverse geocoder performs the real lookup. Refuse fallback
    # labels and administrative zones here as an additional presentation guard.
    if re.search(r'\b(?:zone|ward|division|road|street|selected location|map pin)\b|மண்டலம்|வார்டு',name,re.I):return ''
    return name if any(c.isalpha() for c in name) else ''


def _destination_kind(context):
    category=_text(context.get('destination_category')).casefold()
    if category in {'airport','railway','hospital'} and context.get('destination_category_verified') is True:return category
    name=_text(context.get('destination')).casefold()
    if re.search(r'\b(?:road|street|metro|bus stop)\b|சாலை|தெரு|மெட்ரோ',name):return None
    if name in {'chennai airport','chennai international airport','சென்னை விமான நிலையம்'}:return 'airport'
    if name in {'chennai central','chennai central railway station','tambaram railway station',
            'சென்னை சென்ட்ரல்','தாம்பரம் ரயில் நிலையம்'}:return 'railway'
    # A hospital name identifies a destination, never a diagnosis or emergency.
    if re.search(r'\bhospital\b|மருத்துவமனை',name):return 'hospital'
    return None


def _scope(context,stage,now,locality):
    opaque=_text(context.get('care_scope_id'),120)
    if opaque:return hashlib.sha256(('care:'+opaque).encode()).hexdigest()[:24]
    ride=context.get('ride_id',context.get('id'))
    ride=_number(ride,1)
    if ride is not None and ride.is_integer():return 'ride:'+str(int(ride))
    if stage=='dashboard':parts=['dashboard',now.date().isoformat(),locality]
    else:parts=['journey',context.get('session_id',''),context.get('pickup',''),context.get('destination',''),context.get('pickup_at','')]
    # Scope hashes exclude GPS coordinates and pronunciation text.
    return hashlib.sha256(json.dumps(parts,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()[:24]


def _seen(delivered):
    if isinstance(delivered,dict):
        return {key for key,value in delivered.items() if value in ('delivered','acknowledged','dismissed')}
    if isinstance(delivered,(str,bytes)):raise ValueError('delivered must contain complete delivery keys')
    result=set(delivered or ())
    if not all(isinstance(key,str) for key in result):raise ValueError('Delivery keys must be strings')
    return result


def recommend(context,delivered=(),limit=2,policy=None):
    """Return at most two suggestions. Never mutate context or delivery history.

    Accepted stages: dashboard, booking_details, before_confirmation,
    driver_assigned, driver_approaching, before_pickup, ride_completed. Existing confirm and
    weather_advisory stages are accepted as aliases. Booking stage done does
    NOT mean the ride is completed. All optional advice is declarative.
    """
    if not isinstance(context,dict):raise ValueError('context must be a dictionary')
    policy=_policy(policy);now=_time(context.get('now')) if context.get('now') is not None else datetime.now(TZ)
    if now is None:raise ValueError('Invalid context time')
    lang=LANGUAGES.get(_text(context.get('lang',context.get('language','English'))).casefold())
    if lang is None:raise ValueError('Choose English, Tamil or Tanglish')
    stage=_text(context.get('care_stage',context.get('stage','dashboard')))
    stage={'confirm':'before_confirmation','weather_advisory':'booking_details'}.get(stage,stage)
    allowed={'dashboard','booking_details','before_confirmation','driver_assigned','driver_approaching','before_pickup','ride_completed'}
    if stage not in allowed:stage='inactive'
    status=_text(context.get('ride_status',context.get('status',''))).casefold()
    locality=_locality(context,now,policy) if stage=='dashboard' else ''
    location=context.get('current_location') or {}
    # Permission denial produces a neutral dashboard greeting. Existing booked
    # journey reminders remain eligible through their OWN verified ride events.
    dashboard_location=(stage=='dashboard' and isinstance(location,dict) and location.get('status')=='granted'
        and _fresh(location.get('observed_at'),now,policy['location_max_age_s']))
    target=now if stage=='dashboard' else _time(context.get('pickup_at',context.get('pickup_time')))
    weather=_weather(context.get('current_weather') if stage=='dashboard' else context.get('weather'),target,now,policy)
    if stage=='dashboard' and not dashboard_location:weather=None
    hour=now.hour if stage=='dashboard' else target.hour if target is not None else None
    night=hour is not None and (hour>=policy['night_start_hour'] or hour<policy['night_end_hour'])
    period='morning' if 5<=now.hour<12 else 'afternoon' if 12<=now.hour<17 else 'evening'
    greeting=_pick(lang,{'morning':'Good morning!','afternoon':'Good afternoon!','evening':'Hello!'}[period],
        {'morning':'காலை வணக்கம்!','afternoon':'வணக்கம்!','evening':'வணக்கம்!'}[period],
        {'morning':'Kaalai vanakkam!','afternoon':'Vanakkam!','evening':'Vanakkam!'}[period])
    if locality:greeting+=' '+_pick(lang,'Travel tips for '+locality+'.',locality+' பகுதியில் உங்கள் பயணத்திற்கான குறிப்புகள்.',locality+'-la unga travel tips.')
    scope=_scope(context,stage,now,locality);seen=_seen(delivered);candidates=[]
    stage_prefix=scope+':stage:'+stage+':'
    remaining=max(0,2-sum(key.startswith(stage_prefix) for key in seen))
    def add(rule,en,ta,tg,evidence,urgency=2,safety=2,relevance=4,group='preparation'):
        # One rule may be relevant at several stages; its stable journey key
        # prevents repeated announcements after actual delivery/acknowledgment.
        key=scope+':'+rule
        if key in seen:return
        strength=5 if evidence else 3
        score=sum(SCORE_WEIGHTS[k]*v for k,v in dict(urgency=urgency,safety=safety,relevance=relevance,evidence=strength).items())
        candidates.append(dict(id=rule,delivery_key=key,stage_delivery_key=stage_prefix+rule,text=_pick(lang,en,ta,tg),language=lang,
            score=score,group=group,evidence=evidence,question=False))
    preparation=stage in {'booking_details','before_confirmation'} or dashboard_location
    vehicle=_text(context.get('vehicle'));count=_number(context.get('count',context.get('passengers')),1,16)
    if count is not None and not count.is_integer():count=None
    driver_id=_number(context.get('driver_id'),1)
    assigned=driver_id is not None and driver_id.is_integer() and status in {'accepted','arriving','in_progress'}

    if preparation and weather and weather['rain']:
        chance=weather['max_rain_probability_pct'];chance_en=(' Rain chance is '+_fmt(chance)+'%.') if chance is not None else ''
        chance_ta=(' மழை வாய்ப்பு '+_fmt(chance)+'%.') if chance is not None else ''
        chance_tg=(' Rain chance '+_fmt(chance)+'%.') if chance is not None else ''
        if weather['storm']:
            messages=('Thunderstorms are forecast around this time.'+chance_en+' Wait in a sheltered pickup area and check local warnings.',
                'அந்த நேரத்தில் இடியுடன் மழை எதிர்பார்க்கப்படுகிறது.'+chance_ta+' பாதுகாப்பான நிழற்குடை உள்ள இடத்தில் காத்திருந்து உள்ளூர் எச்சரிக்கைகளைச் சரிபாருங்கள்.',
                'Andha time-la thunderstorms expected.'+chance_tg+' Sheltered pickup place-la wait pannunga; local warnings-a check pannunga.')
        else:
            en='Heavy rain is forecast around this time.' if weather['heavy_rain'] else 'Rain is forecast around this time.'
            ta='அந்த நேரத்தில் கனமழை எதிர்பார்க்கப்படுகிறது.' if weather['heavy_rain'] else 'அந்த நேரத்தில் மழை எதிர்பார்க்கப்படுகிறது.'
            tg='Andha time-la heavy rain expected.' if weather['heavy_rain'] else 'Andha time-la rain expected.'
            messages=(en+chance_en+' Carry an umbrella and protect your belongings.',
                ta+chance_ta+' குடை எடுத்துக்கொண்டு உங்கள் பொருட்களைப் பாதுகாத்துக்கொள்ளுங்கள்.',
                tg+chance_tg+' Umbrella eduthukkonga; unga belongings-a protect pannikkonga.')
        if vehicle=='Bike':
            suffix=(' A covered vehicle can provide rain protection; the choice is yours.',
                ' மூடிய வாகனம் மழையிலிருந்து பாதுகாப்பளிக்கலாம்; முடிவு உங்களுடையது.',
                ' Covered vehicle rain protection kudukkum; unga choice.')
            messages=tuple(a+b for a,b in zip(messages,suffix))
        elif vehicle=='Auto':
            suffix=(' Protect yourself and your bags from rain entering through open sides.',
                ' திறந்த பக்கங்கள் வழியே வரும் மழையிலிருந்து உங்களையும் உடைமைகளையும் பாதுகாத்துக்கொள்ளுங்கள்.',
                ' Open sides-la varra rain-la irundhu ungalaiyum bags-aiyum protect pannikkonga.')
            messages=tuple(a+b for a,b in zip(messages,suffix))
        severity=5 if weather['storm'] else 4 if weather['heavy_rain'] else 3
        add('rain_preparation',*messages,['Open-Meteo target-hour points'],urgency=severity,safety=severity,group='weather')
    if preparation and weather and weather['max_temperature_c'] is not None and weather['max_temperature_c']>=policy['warm_c']:
        temp=_fmt(weather['max_temperature_c'])
        add('heat_protection','The forecast temperature reaches '+temp+'°C. Carry drinking water and use sun protection.',
            'முன்னறிவிப்பில் வெப்பநிலை '+temp+'°C வரை உள்ளது. குடிநீர் எடுத்துக்கொண்டு வெயிலிலிருந்து பாதுகாத்துக்கொள்ளுங்கள்.',
            'Forecast temperature '+temp+'°C varaikkum irukku. Drinking water eduthukkonga; sun protection use pannunga.',
            ['Open-Meteo temperature', 'application preparation threshold'],urgency=4 if float(temp)>=policy['hot_c'] else 2,safety=4,group='weather')
    if preparation and night:
        add('late_night_safety','For late-night travel, wait in a well-lit pickup area and verify the driver and vehicle before boarding.',
            'இரவு நேரப் பயணத்தில் வெளிச்சமுள்ள இடத்தில் காத்திருங்கள். ஏறும் முன் ஓட்டுநரையும் வாகனத்தையும் சரிபாருங்கள்.',
            'Late-night travel-ku well-lit pickup place-la wait pannunga. Era munnaadi driver-um vehicle-um verify pannunga.',
            ['Asia/Kolkata travel hour'],urgency=4,safety=5,group='safety')
    if stage in {'before_confirmation','driver_assigned','driver_approaching','before_pickup'} and status!='completed':
        add('pickup_guidance','Wait where your assigned vehicle can safely stop, and keep the pickup point easy to find.',
            'வாகனம் பாதுகாப்பாக நிற்கக்கூடிய இடத்தில் காத்திருங்கள். உங்களை எளிதில் கண்டுபிடிக்கக்கூடிய இடத்தைத் தேர்வு செய்யுங்கள்.',
            'Vehicle safe-ah stop panna mudiyura pickup place-la wait pannunga. Easy-ah kandupidikka mudiyura idathula irunga.',
            ['journey preparation stage'],urgency=2,safety=3)
    if stage in {'driver_assigned','driver_approaching','before_pickup'} and assigned and status in {'accepted','arriving'} and context.get('pickup_verified') is False:
        add('otp_safety','Verify the assigned driver and vehicle. Share your pickup OTP only with that driver when you board.',
            'ஒதுக்கப்பட்ட ஓட்டுநரையும் வாகனத்தையும் சரிபாருங்கள். வாகனத்தில் ஏறும்போது அந்த ஓட்டுநரிடம் மட்டும் பயணக் குறியீட்டைப் பகிருங்கள்.',
            'Assigned driver-um vehicle-um verify pannunga. Board pannumbodhu andha driver-kitta mattum pickup OTP share pannunga.',
            ['assigned driver', 'active ride', 'pickup not verified'],urgency=4,safety=5,group='safety')
    if stage in {'booking_details','before_confirmation'} and count is not None and vehicle in policy['capacities']:
        capacity=policy['capacities'][vehicle];n=int(count)
        if n>capacity:
            tamil_vehicle={'Bike':'பைக்','Auto':'ஆட்டோ','Mini':'மினி கார்','Sedan':'செடான்','SUV':'எஸ் யூ வி'}[vehicle]
            add('passenger_comfort',f'The configured {vehicle} passenger capacity is {capacity}; your group has {n}. Please review the vehicle choice.',
                f'{tamil_vehicle} வாகனத்தின் பயணிகள் கொள்ளளவு {capacity}; உங்கள் குழுவில் {n} பேர் உள்ளனர். வாகனத் தேர்வைச் சரிபாருங்கள்.',
                f'{vehicle} passenger capacity {capacity}; unga group-la {n} peru. Vehicle choice-a review pannunga.',
                ['passenger count','configured vehicle capacity'],urgency=5,safety=5)
        elif n>=3:
            add('passenger_comfort',f'For your group of {n}, keep luggage within the vehicle\'s available space and leave comfortable seating room.',
                f'உங்கள் குழுவில் {n} பேர் இருப்பதால், வாகனத்தில் உள்ள இடத்திற்கேற்ப உடைமைகளை வைத்துக்கொண்டு வசதியாக அமருங்கள்.',
                f'Unga group-la {n} peru; available space-ku etha maari luggage-a vachuttu comfortable-ah ukkarunga.',
                ['passenger count','chosen vehicle capacity'],urgency=1,safety=2)
    kind=_destination_kind(context)
    if stage in {'booking_details','before_confirmation'} and kind:
        messages={
            'airport':('Before leaving for the airport, check your luggage, travel documents and booking details.',
                'விமான நிலையத்திற்குக் கிளம்பும் முன் உடைமைகள், பயண ஆவணங்கள், முன்பதிவு விவரங்களைச் சரிபாருங்கள்.',
                'Airport-ku kelambura munnaadi luggage, travel documents, booking details-a check pannunga.'),
            'railway':('Before leaving for the railway station, keep your ticket and luggage ready.',
                'ரயில் நிலையத்திற்குக் கிளம்பும் முன் பயணச்சீட்டையும் உடைமைகளையும் தயாராக வைத்துக்கொள்ளுங்கள்.',
                'Railway station-ku kelambura munnaadi ticket-um luggage-um ready-ah vachukkonga.'),
            'hospital':('If needed for your hospital visit, keep appointment details, relevant documents and essentials ready.',
                'மருத்துவமனைப் பயணத்திற்குத் தேவைப்பட்டால் சந்திப்பு விவரங்கள், தொடர்புடைய ஆவணங்கள், அத்தியாவசியப் பொருட்களைத் தயாராக வைத்துக்கொள்ளுங்கள்.',
                'Hospital visit-ku thevaippatta appointment details, relevant documents, essentials-a ready-ah vachukkonga.')}
        add('destination_reminder',*messages[kind],['confirmed destination: '+kind],urgency=3,safety=2)
    if stage in {'driver_assigned','driver_approaching','before_pickup'} and status in STATUS_ACTIVE:
        eta=context.get('driver_eta') or {};eta_minutes=_number(eta.get('minutes'),0,180) if isinstance(eta,dict) else None
        has_eta=(assigned and eta_minutes is not None and eta.get('verified') is True and eta.get('live_driver_position') is True
            and _text(eta.get('source')) and _fresh(eta.get('updated_at'),now,policy['eta_max_age_s']))
        until=(target-now).total_seconds()/60 if target is not None else None
        if has_eta and eta_minutes<=10:
            value=_fmt(eta_minutes)
            add('departure_readiness',f'The latest driver ETA is about {value} minutes. Please be ready at your pickup point.',
                f'சமீபத்திய கணிப்பின்படி ஓட்டுநர் வர சுமார் {value} நிமிடங்கள் ஆகலாம். புறப்படும் இடத்தில் தயாராக இருங்கள்.',
                f'Latest driver ETA around {value} minutes. Pickup point-la ready-ah irunga.',
                ['verified driver ETA',_text(eta['source'])],urgency=5,safety=3)
        elif until is not None and 0<=until<=policy['departure_window_minutes']:
            add('departure_readiness','Your scheduled pickup time is approaching. Please have your essentials ready.',
                'நீங்கள் முன்பதிவு செய்த புறப்படும் நேரம் நெருங்குகிறது. தேவையான பொருட்களைத் தயாராக வைத்துக்கொள்ளுங்கள்.',
                'Scheduled pickup time nerungudhu. Unga essentials-a ready-ah vachukkonga.',
                ['scheduled pickup time'],urgency=4,safety=2)
    traffic=context.get('traffic') or {};delay=_number(traffic.get('extra_minutes'),1,240) if isinstance(traffic,dict) else None
    traffic_source=_text(traffic.get('source')).casefold() if isinstance(traffic,dict) else ''
    trusted_traffic=traffic_source in policy['trusted_traffic_sources'] and not re.search(r'osrm|straight.?line|static.?route',traffic_source)
    if stage in {'booking_details','before_confirmation','driver_approaching'} and delay is not None and traffic.get('live') is True and traffic.get('verified') is True and trusted_traffic and _fresh(traffic.get('updated_at'),now,policy['traffic_max_age_s']):
        value=_fmt(delay)
        add('traffic_awareness',f'The live traffic estimate indicates about {value} extra minutes. Allow time for your journey.',
            f'நேரடி போக்குவரத்துக் கணிப்பில் சுமார் {value} கூடுதல் நிமிடங்கள் காட்டப்படுகின்றன. பயணத்திற்கு நேரம் ஒதுக்குங்கள்.',
            f'Live traffic estimate-la around {value} extra minutes kaattudhu. Journey-ku time allow pannikkonga.',
            ['verified live traffic',_text(traffic['source'])],urgency=4,safety=2)
    if stage in {'before_confirmation','driver_assigned'} and context.get('accessibility_requested') is True:
        add('accessibility_assistance','If you need boarding assistance, contact the service or assigned driver in advance to check what support is available.',
            'வாகனத்தில் ஏற உதவி தேவைப்பட்டால், கிடைக்கக்கூடிய உதவியை முன்கூட்டியே சேவை மையம் அல்லது ஒதுக்கப்பட்ட ஓட்டுநரிடம் சரிபாருங்கள்.',
            'Boarding assistance thevaippatta service illa assigned driver-kitta advance-ah available support-a check pannunga.',
            ['customer requested assistance'],urgency=3,safety=4)
    if dashboard_location or stage in {'before_confirmation','driver_assigned'}:
        add('phone_readiness','Keep your phone charged for driver calls and trip tracking.',
            'ஓட்டுநருடன் பேசவும் பயணத்தைக் கண்காணிக்கவும் உங்கள் கைப்பேசியில் போதுமான மின்சக்தி இருக்குமாறு பார்த்துக்கொள்ளுங்கள்.',
            'Driver calls-ukkum trip tracking-ukkum phone charge-a vachukkonga.',
            ['travel preparation stage'],urgency=1,safety=1)
    if stage=='ride_completed' and status=='completed':
        add('arrival_care','Before leaving the vehicle, check that you have your phone, bags and other belongings. Thank you, and take care!',
            'வாகனத்திலிருந்து இறங்கும் முன் கைப்பேசி, பைகள், மற்ற உடைமைகளை எடுத்துக்கொண்டீர்களா என்று சரிபாருங்கள். நன்றி! நலமாகப் பயணியுங்கள்!',
            'Vehicle-la irundhu erangura munnaadi phone, bags, matha belongings-a check pannunga. Nandri! Take care!',
            ['ride status is completed'],urgency=4,safety=3,group='arrival')
    if status=='cancelled' or stage=='inactive':candidates=[]
    # Rank policy: 4*urgency + 3*safety + 2*relevance + evidence.
    candidates.sort(key=lambda r:(-r['score'],RULE_IDS.index(r['id'])))
    selected=[];weather_count=0
    maximum=_number(limit,0,2)
    if maximum is None or not maximum.is_integer():raise ValueError('limit must be 0, 1 or 2')
    for item in candidates:
        if len(selected)>=min(int(maximum),remaining):break
        if item['group']=='weather' and weather_count:continue
        selected.append(item);weather_count+=item['group']=='weather'
    # Only minimal presentation data is exposed; GPS/OTP/phone/driver IDs remain
    # in the caller's existing protected booking/location architecture.
    return dict(version=VERSION,stage=stage,language=lang,greeting=greeting,locality=locality or None,
        weather=weather,recommendations=selected,
        candidate_ids=[item['id'] for item in candidates],remaining_stage_budget=remaining,optional=True)


def remember_delivered(history,recommendations,status='delivered',max_items=256):
    """Return a bounded copy; caller invokes this after real delivery/ack only."""
    if status not in {'delivered','acknowledged','dismissed'}:raise ValueError('Invalid delivery status')
    if not isinstance(history,dict):raise ValueError('history must be a dictionary')
    result=dict(history)
    for item in recommendations:
        key=item.get('delivery_key') if isinstance(item,dict) else None
        if not isinstance(key,str) or not key:raise ValueError('Missing recommendation delivery key')
        result[key]=status
        stage_key=item.get('stage_delivery_key')
        if isinstance(stage_key,str) and stage_key:result[stage_key]=status
    while len(result)>max(1,int(max_items)):result.pop(next(iter(result)))
    return result


MESSAGES = {
    "rain": (
        "Rain is possible. Carry an umbrella and keep your belongings dry.",
        "மழை பெய்ய வாய்ப்புள்ளது. குடை எடுத்துச் செல்லுங்கள்; உடைமைகளை நனையாமல் பாதுகாத்துக்கொள்ளுங்கள்.",
        "Mazhai peiya vaaippu irukku. Umbrella eduthuttu ponga; belongings nanaiyaama paathukkonga."
    ),
    "heat": (
        "It's quite warm. Carry drinking water and stay hydrated.",
        "வெப்பம் அதிகமாக உள்ளது. குடிநீர் எடுத்துச் சென்று உடலில் நீர்ச்சத்து குறையாமல் பார்த்துக்கொள்ளுங்கள்.",
        "Veyil adhigama irukku. Thanni eduthuttu ponga; hydrated ah irunga."
    ),
    "night": (
        "For late-night travel, wait in a well-lit area and verify your driver before boarding.",
        "இரவு நேரப் பயணத்தில் வெளிச்சமான இடத்தில் காத்திருந்து, ஏறும் முன் ஓட்டுநர் விவரங்களைச் சரிபாருங்கள்.",
        "Night travel ku velichamaana place la wait pannunga. Erurathukku munnaadi driver details verify pannunga."
    ),
    "otp": (
        "Share your pickup OTP only with your assigned driver when boarding.",
        "வாகனத்தில் ஏறும்போது மட்டும் ஒதுக்கப்பட்ட ஓட்டுநரிடம் உங்கள் OTP-ஐ பகிருங்கள்.",
        "Board pannumbodhu mattum assigned driver kitta pickup OTP share pannunga."
    ),
    "capacity": (
        "Please select a vehicle that comfortably accommodates everyone travelling.",
        "பயணம் செய்யும் அனைவருக்கும் வசதியான வாகனத்தைத் தேர்ந்தெடுக்கவும்.",
        "Travel panra ellaarukkum comfortable ah irukkura vehicle select pannunga."
    ),
    "airport": (
        "Before leaving for the airport, check your travel documents and luggage.",
        "விமான நிலையத்திற்குச் செல்லும் முன் பயண ஆவணங்களையும் உடைமைகளையும் சரிபாருங்கள்.",
        "Airport ku kilamburathukku munnaadi documents um luggage um check pannunga."
    ),
    "railway": (
        "Keep your train ticket and travel essentials ready.",
        "ரயில் பயணச்சீட்டையும் தேவையான பொருட்களையும் தயாராக வைத்துக்கொள்ளுங்கள்.",
        "Train ticket um travel essentials um ready ah vechukkonga."
    ),
    "hospital": (
        "Remember any medical documents and essential items you need.",
        "தேவையான மருத்துவ ஆவணங்களையும் அத்தியாவசியப் பொருட்களையும் எடுத்துக்கொள்ளுங்கள்.",
        "Thevaiyaana medical documents um essentials um eduthukkonga."
    ),
    "phone": (
        "Keep your phone charged so you can contact and track your driver.",
        "ஓட்டுநரைத் தொடர்புகொள்ளவும் கண்காணிக்கவும் கைப்பேசியில் போதுமான சார்ஜ் வைத்திருங்கள்.",
        "Driver ah contact pannavum track pannavum phone charge vechukkonga."
    ),
    "arrival": (
        "Before leaving the vehicle, please check that you have all your belongings.",
        "வாகனத்திலிருந்து இறங்கும் முன் உங்கள் உடைமைகள் அனைத்தும் இருப்பதைச் சரிபாருங்கள்.",
        "Vehicle la irundhu erangurathukku munnaadi belongings ellaam irukka nu check pannunga."
    ),
    "pickup": (
        "Choose a safe, accessible pickup point where your driver can stop.",
        "ஓட்டுநர் நிறுத்தக்கூடிய பாதுகாப்பான, எளிதில் அணுகக்கூடிய இடத்தைத் தேர்ந்தெடுக்கவும்.",
        "Driver stop panna mudiyura safe ah accessible ah irukkura pickup point choose pannunga."
    ),
    "accessibility": (
        "If you need boarding assistance, please coordinate with your assigned driver.",
        "ஏறுவதற்கு உதவி தேவைப்பட்டால் ஒதுக்கப்பட்ட ஓட்டுநருடன் தொடர்புகொள்ளுங்கள்.",
        "Boarding assistance venumna assigned driver kitta coordinate pannunga."
    ),
    "ready": (
        "Your driver is approaching. Please get ready at your pickup point.",
        "உங்கள் ஓட்டுநர் நெருங்கிக்கொண்டிருக்கிறார். ஏறும் இடத்தில் தயாராக இருங்கள்.",
        "Unga driver nerungittu irukkaaru. Pickup point la ready ah irunga."
    ),
}

CAPACITY = {"bike": 1, "auto": 3, "mini": 4, "sedan": 4, "suv": 6}

# MOVIO_CUSTOMER_CARE_COMPAT_V1
# The legacy public API delegates to the SAME pure recommendation engine.
VERSION='customer-care-engine-1.1-compatible'
_CARE_LEGACY_STAGES={'details':'booking_details','pre_confirmation':'before_confirmation'}
_CARE_LEGACY_IDS={'rain_preparation':'rain','heat_protection':'heat',
    'late_night_safety':'night','pickup_guidance':'pickup','otp_safety':'otp',
    'passenger_comfort':'capacity','departure_readiness':'ready',
    'traffic_awareness':'traffic','accessibility_assistance':'accessibility',
    'phone_readiness':'phone','arrival_care':'arrival'}


def _care_legacy_context(context,stage=None):
    c=copy.deepcopy(context) if isinstance(context,dict) else {}
    lang=LANGUAGES.get(_text(c.get('lang',c.get('language','English'))).casefold(),'English')
    c['lang']=lang
    chosen=stage or c.get('care_stage',c.get('stage','dashboard'))
    c['care_stage']=_CARE_LEGACY_STAGES.get(chosen,chosen)
    if 'count' not in c and 'passenger_count' in c:c['count']=c['passenger_count']
    vehicle=_text(c.get('vehicle')).casefold()
    canonical={'bike':'Bike','auto':'Auto','mini':'Mini','mini car':'Mini','sedan':'Sedan','suv':'SUV'}
    if vehicle in canonical:c['vehicle']=canonical[vehicle]
    if 'pickup_at' not in c and c.get('pickup_time'):c['pickup_at']=c['pickup_time']
    # A bare locality or status='ok' is NOT proof of GPS permission or freshness.
    # Current dashboard callers must provide the existing verified-location
    # object and timestamp. Never infer permission from a string or coordinates.
    if not isinstance(c.get('current_location'),dict):c['current_location']={}
    raw=c.get('current_weather') if c['care_stage']=='dashboard' else c.get('weather')
    if c['care_stage']=='dashboard' and raw is None:raw=c.get('weather')
    if isinstance(raw,dict) and 'points' not in raw:
        # Accept the old flat shape ONLY when it already carries provider,
        # fetch timestamp and forecast-valid timestamp. Add no invented data.
        keys=('weather_code','precipitation_probability','temperature_2m','wind_speed_10m')
        raw=dict(raw,points=[dict(location='pickup',valid_at=raw.get('valid_at'),
                                 **{key:raw.get(key) for key in keys})])
    if c['care_stage']=='dashboard':c['current_weather']=raw
    else:c['weather']=raw
    return c


def _care_legacy_id(rule,context):
    if rule=='destination_reminder':return _destination_kind(context) or 'destination'
    return _CARE_LEGACY_IDS.get(rule,rule)


def _care_legacy_result(context,stage=None):
    c=_care_legacy_context(context,stage)
    history=c.get('delivered',())
    if not isinstance(history,(dict,list,tuple,set)):history=()
    # Legacy acknowledged rule IDs remain understood; generation alone never
    # creates a delivery record. New clients can retain complete delivery keys.
    acknowledged=c.get('acknowledged') or []
    if not isinstance(acknowledged,(list,tuple,set)):acknowledged=[]
    acknowledged={item for item in acknowledged if isinstance(item,str)}
    initial=recommend(c,delivered=history,limit=0)
    now=_time(c.get('now')) if c.get('now') is not None else datetime.now(TZ)
    scope=_scope(c,initial['stage'],now,initial['locality'] or '')
    seen=_seen(history)
    for rule in RULE_IDS:
        if rule in acknowledged or _care_legacy_id(rule,c) in acknowledged:
            seen.add(scope+':'+rule)
    return c,recommend(c,delivered=seen,limit=2)


def evaluate(context):
    """Legacy API: a list of at most two recommendations, with stable IDs."""
    c,result=_care_legacy_result(context)
    return [dict(row,id=_care_legacy_id(row['id'],c),rule_id=row['id'],
                 evidence='; '.join(row['evidence'])) for row in result['recommendations']]


def dashboard_greeting(context):
    """Legacy greeting dictionary, using only verified current context."""
    c,result=_care_legacy_result(context,'dashboard')
    weather=result['weather'];locality=result['locality'];lang=result['language']
    if weather is None:
        return dict(text=result['greeting'],weather_verified=False,
                    locality_verified=bool(locality))
    codes={point['weather_code'] for point in weather['points']}
    temp=weather['max_temperature_c'];chance=weather['max_rain_probability_pct']
    hot=temp is not None and temp>=DEFAULT_POLICY['warm_c']
    pleasant=bool(codes&{0,1,2}) and temp is not None and 18<=temp<=32 and not weather['rain']
    condition=('rain' if weather['rain'] else 'heat' if hot else
               'cloudy' if 3 in codes else 'pleasant' if pleasant else 'normal')
    messages={
        'rain':('Rain is forecast around this time.','அந்த நேரத்தில் மழை எதிர்பார்க்கப்படுகிறது.',
                'Andha time-la rain expected.'),
        'heat':('It is warm around your area.','உங்கள் பகுதியில் வெப்பம் அதிகமாக உள்ளது.',
                'Unga area-la veyil adhigama irukku.'),
        'cloudy':('Cloudy weather is expected around your area.','உங்கள் பகுதியில் மேகமூட்டம் எதிர்பார்க்கப்படுகிறது.',
                  'Unga area-la cloudy weather expected.'),
        'pleasant':('The weather looks comfortable for your journey.','பயணத்திற்கு வானிலை இனிமையாக உள்ளது.',
                    'Unga journey-ku weather comfortable-ah irukku.'),
        'normal':('Here is your local weather update.','உங்கள் பகுதியின் வானிலை தகவல்.',
                  'Unga area weather update.')}
    text=result['greeting']+' '+_pick(lang,*messages[condition])
    if temp is not None:
        value=_fmt(temp)
        text+=' '+_pick(lang,f'Temperature is around {value}°C.',f'வெப்பநிலை சுமார் {value}°C.',
                       f'Temperature around {value}°C.')
    if chance is not None:
        value=_fmt(chance)
        text+=' '+_pick(lang,f'Rain chance is {value}%.',f'மழை வாய்ப்பு {value}%.',f'Rain chance {value}%.')
    return dict(text=text,weather_verified=True,locality_verified=bool(locality),
                condition=condition,temperature_c=temp,rain_probability_pct=chance)
