"""Weather-aware manual and voice booking assistance for MOVIO v5.3.

Prototype integration. Weather is supplied by Open-Meteo, not predicted by Qwen.
No credentials, original model weights or real recordings are bundled.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import contextvars
import hashlib
import hmac
import io
import json
import math
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

VERSION = "0.4.0"
NUMERIC_LANGUAGE = contextvars.ContextVar('movio_weather_numeric_language', default=None)
TZ = ZoneInfo("Asia/Kolkata")
CAPACITY = {"Bike": 1, "Auto": 3, "Mini": 4, "Sedan": 4, "SUV": 6}
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 97, 99}
FIELDS = ("count", "vehicle", "pickup", "destination", "pickup_geo", "destination_geo",
          "when", "pickup_at", "fare", "weather", "lang", "_wx_mode", "_wx_weather_consent")
CORE_FIELDS = ("count", "vehicle", "pickup", "destination", "when")


class GuardError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def snapshot(state):
    return {key: copy.deepcopy(state.get(key)) for key in FIELDS}


def localized(lang, en, ta, tanglish):
    return ta if lang == "Tamil" else tanglish if lang == "Tanglish" else en


def reply_normalized(text):
    # Preserve Tamil vowel signs and pulli marks while removing punctuation.
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    text = "".join(" " if unicodedata.category(c).startswith("P") else c for c in text)
    return re.sub(r"\s+", " ", text).strip()


POSITIVE = {"yes", "yeah", "yep", "yes please", "confirm", "book it", "go ahead", "okay", "ok",
            "continue", "ஆம்", "ஆமாம்", "ஆமா", "சரி", "தொடரலாம்", "தொடருங்கள்", "ஆம் தொடரலாம்",
            "ஆம் புக் செய்க", "உறுதி செய்யுங்கள்", "aama", "aamam", "seri", "sari", "continue pannunga"}
POSITIVE.update({"yes continue","yes book it","yes please continue","ஆமாங்க","சரிதான்","சரியாக உள்ளது",
                 "ஆம் தொடருங்கள்","ஆமாம் தொடரலாம்","சரி புக் பண்ணுங்க","aamaa","amam","aam",
                 "keep bike","keep the bike","பைக் தொடரட்டும்","bike continue"})
NEGATIVE = {"no", "nope", "cancel", "do not book", "dont book", "இல்லை", "வேண்டாம்", "illai", "vendam"}
TA_SMALL = ("பூஜ்ஜியம்", "ஒன்று", "இரண்டு", "மூன்று", "நான்கு", "ஐந்து", "ஆறு", "ஏழு", "எட்டு", "ஒன்பது",
            "பத்து", "பதினொன்று", "பன்னிரண்டு", "பதின்மூன்று", "பதினான்கு", "பதினைந்து", "பதினாறு",
            "பதினேழு", "பதினெட்டு", "பத்தொன்பது")
EN_SMALL = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
            "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
MONTHS_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
MONTHS_TA = ("ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்")
TA_ROMAN_SMALL = ("poojjiyam","ondru","irandu","moondru","naangu","aindhu","aaru","ezhu","ettu","onbadhu",
                  "pathu","padhinondru","pannirandu","padhimoondru","padhinaangu","padhinaindhu","padhinaaru",
                  "padhinezhu","padhinettu","padhonbadhu")
VEHICLES_TA = {"Bike":"பைக்","Auto":"ஆட்டோ","Mini":"மினி கார்","Sedan":"செடான்","SUV":"எஸ் யூ வி"}
VEHICLES_ROMAN = {"Bike":"baikku","Auto":"aatto","Mini":"siriya kaar","Sedan":"sedaan kaar","SUV":"es yoo vee"}
AM_RE = r"\ba\.?m\.?\b|\bmorning\b|காலை|அதிகாலை|\b(?:kaalai|kalai)\b"
PM_RE = r"\bp\.?m\.?\b|\b(?:afternoon|evening|night|tonight)\b|மாலை|இரவு|மதியம்|நண்பகல்|\b(?:maalai|malai|iravu|mathiyam|madhiyam)\b"
TODAY_RE = r"\b(?:today|tonight|innaiku|inniku|indru)\b|இன்று|இன்னைக்கு"
TOMORROW_RE = r"\b(?:tomorrow|naalai|nalai|naalaiku|naalaikku)\b|நாளை|நாளைக்கு"


def number_words(value, lang="English"):
    n = int(value)
    if lang == "Tanglish":
        if n < 0:return "minus " + number_words(-n,lang)
        if n < 20:return TA_ROMAN_SMALL[n]
        if n < 100:
            full=("","","irupadhu","muppadhu","naarppadhu","aimbadhu","arubadhu","ezhubadhu","enbadhu","thonnooru")
            join=("","","irupathu","muppathu","naarppathu","aimbathu","arubathu","ezhubathu","enbathu","thonnootru")
            return full[n//10] if not n%10 else join[n//10]+" "+TA_ROMAN_SMALL[n%10]
        if n < 1000:
            full=("","nooru","irunooru","munnooru","naanooru","ainnooru","arunooru","ezhunooru","ennooru","thollaayiram")
            join=("","nootru","irunootru","munnootru","naanoootru","ainnootru","arunootru","ezhunootru","ennootru","thollaayirathu")
            return full[n//100] if not n%100 else join[n//100]+" "+number_words(n%100,lang)
        return number_words(n//1000,lang)+(" aayiram" if not n%1000 else " aayirathu "+number_words(n%1000,lang))
    if n < 0:
        return ("மைனஸ் " if lang == "Tamil" else "minus ") + number_words(-n, lang)
    if lang != "Tamil":
        if n < 20:
            return EN_SMALL[n]
        if n < 100:
            tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
            return tens[n // 10] + (" " + EN_SMALL[n % 10] if n % 10 else "")
        if n < 1000:
            return EN_SMALL[n // 100] + " hundred" + (" " + number_words(n % 100, lang) if n % 100 else "")
        return number_words(n // 1000, lang) + " thousand" + (" " + number_words(n % 1000, lang) if n % 1000 else "")
    if n < 20:
        return TA_SMALL[n]
    if n < 100:
        full = ("", "", "இருபது", "முப்பது", "நாற்பது", "ஐம்பது", "அறுபது", "எழுபது", "எண்பது", "தொண்ணூறு")
        join = ("", "", "இருபத்து", "முப்பத்து", "நாற்பத்து", "ஐம்பத்து", "அறுபத்து", "எழுபத்து", "எண்பத்து", "தொண்ணூற்று")
        return full[n // 10] if not n % 10 else join[n // 10] + " " + TA_SMALL[n % 10]
    if n < 1000:
        full = ("", "நூறு", "இருநூறு", "முந்நூறு", "நானூறு", "ஐந்நூறு", "அறுநூறு", "எழுநூறு", "எண்ணூறு", "தொள்ளாயிரம்")
        join = ("", "நூற்று", "இருநூற்று", "முந்நூற்று", "நானூற்று", "ஐந்நூற்று", "அறுநூற்று", "எழுநூற்று", "எண்ணூற்று", "தொள்ளாயிரத்து")
        return full[n // 100] if not n % 100 else join[n // 100] + " " + number_words(n % 100, lang)
    if n < 10000:
        full = ("", "ஆயிரம்", "இரண்டாயிரம்", "மூன்றாயிரம்", "நான்காயிரம்", "ஐந்தாயிரம்", "ஆறாயிரம்", "ஏழாயிரம்", "எட்டாயிரம்", "ஒன்பதாயிரம்")
        head = full[n // 1000]
        return head if not n % 1000 else head[:-2] + "த்து " + number_words(n % 1000, lang)
    return str(n)


def spoken_datetime(value, lang='English'):
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    if dt.tzinfo is not None:
        dt = dt.astimezone(TZ)
    period = ('நள்ளிரவு' if dt.hour == 0 else 'அதிகாலை' if dt.hour < 5 else 'காலை' if dt.hour < 12
              else 'மதியம்' if dt.hour < 16 else 'மாலை' if dt.hour < 19 else 'இரவு')
    clock = f'{dt.hour % 12 or 12}:{dt.minute:02}'
    if lang == 'Tamil':
        return f'{MONTHS_TA[dt.month-1]} {dt.day}, {dt.year}, {period} {clock}'
    if lang == 'Tanglish':
        months = ('Janavari','Pibravari','Maarch','Epral','Me','Joon','Joolai','Aagast','Septambar','Aktoabar','Navambar','Disambar')
        period = ('nalliravu' if dt.hour == 0 else 'adhikaalai' if dt.hour < 5 else 'kaalai' if dt.hour < 12
                  else 'madhiyam' if dt.hour < 16 else 'maalai' if dt.hour < 19 else 'iravu')
        return f'{months[dt.month-1]} {dt.day}, {dt.year}, {period} {clock}'
    return f'{MONTHS_EN[dt.month-1]} {dt.day}, {dt.year}, at {clock} {"AM" if dt.hour < 12 else "PM"}'


def time_components(raw, now, allow_bare=False):
    text = unicodedata.normalize('NFKC', str(raw or '')).casefold().translate(str.maketrans('௦௧௨௩௪௫௬௭௮௯','0123456789'))
    now = now.astimezone(TZ)
    found, spans = {}, []
    explicit = re.search(r'(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)', text)
    date_match = None
    if explicit:
        try:
            found['date'] = datetime.strptime(explicit[1], '%Y-%m-%d').date().isoformat()
        except ValueError as exc:
            raise GuardError('invalid_datetime') from exc
        spans.append(explicit.span())
    else:
        relative = ((r'\bday after tomorrow\b|நாளை\s*மறுநாள்|நாளைமறுநாள்|\bnaalai marunaal\b', 2),
                    (TOMORROW_RE, 1), (TODAY_RE, 0))
        for pattern, days in relative:
            match = re.search(pattern, text)
            if match:
                found['date'] = (now + timedelta(days=days)).date().isoformat()
                spans.append(match.span()); break
        if not found:
            match = re.search(r'(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)', text)
            if match:
                try:
                    found['date'] = datetime(int(match[3]), int(match[2]), int(match[1])).date().isoformat()
                except ValueError as exc:
                    raise GuardError('invalid_datetime') from exc
                spans.append(match.span())
        if not found:
            days = {word:n for n,word in enumerate(TA_DAY_WORDS) if n}
            days.update({number_words(n,'Tamil'):n for n in range(1,32)})
            day_pattern = r'\d{1,2}(?:st|nd|rd|th|ஆம்|ம்)?|' + '|'.join(re.escape(k) for k in sorted(days,key=len,reverse=True))
            month_map = {name.casefold():n for n,name in enumerate(MONTHS_EN,1)}
            month_map.update({name.casefold()[:3]:n for n,name in enumerate(MONTHS_EN,1)})
            month_map.update({name:n for n,name in enumerate(MONTHS_TA,1)})
            month_pattern = '|'.join(re.escape(k) for k in sorted(month_map,key=len,reverse=True))
            patterns = (
                rf'(?<![\w\u0b80-\u0bff])(?P<day>{day_pattern})\s+(?P<month>{month_pattern})(?:\s*,?\s*(?P<year>\d{{4}}))?',
                rf'(?<![\w\u0b80-\u0bff])(?P<month>{month_pattern})\s+(?P<day>{day_pattern})(?:\s*(?:தேதி|தேதியன்று))?(?:\s*,?\s*(?P<year>\d{{4}}))?')
            for pattern in patterns:
                match = re.search(pattern, text)
                if not match:
                    continue
                day_raw = match['day']; digits = re.match(r'\d+', day_raw)
                day = int(digits[0]) if digits else days[day_raw]
                try:
                    found['date'] = datetime(int(match['year'] or now.year), month_map[match['month']], day).date().isoformat()
                except ValueError as exc:
                    raise GuardError('invalid_datetime') from exc
                spans.append(match.span()); date_match = match; break
        if not found:
            weekdays = (('monday','திங்கள்'),('tuesday','செவ்வாய்'),('wednesday','புதன்'),('thursday','வியாழன்'),
                        ('friday','வெள்ளி'),('saturday','சனி'),('sunday','ஞாயிறு'))
            for weekday,names in enumerate(weekdays):
                match = next((re.search(r'(?<![a-z])'+re.escape(name)+r'(?![a-z])',text) for name in names
                              if re.search(r'(?<![a-z])'+re.escape(name)+r'(?![a-z])',text)),None)
                if match:
                    days = (weekday-now.weekday()) % 7
                    if re.search(r'\bnext\b|அடுத்த',text) and days == 0: days = 7
                    found['date'] = (now+timedelta(days=days)).date().isoformat();spans.append(match.span());break
    chars = list(text)
    for begin,end in spans:
        chars[begin:end] = ' ' * (end-begin)
    clock_text = ''.join(chars)
    lexicon = number_lexicon()
    tokens = '|'.join(re.escape(k) for k in sorted(lexicon,key=len,reverse=True) if not k.isdigit())
    number_pattern = rf'(?P<hour>(?<!\d)\d{{1,2}}|(?<![\w\u0b80-\u0bff])(?:{tokens})(?![\w\u0b80-\u0bff]))'
    clock = re.search(r'(?<!\d)(\d{1,2})[:.](\d{2})(?!\d)',clock_text)
    iso_clock = bool(explicit and re.search(r'\d{4}-\d{2}-\d{2}[ t]\d{2}:\d{2}',text))
    if clock:
        found.update(hour=int(clock[1]),minute=int(clock[2]),clock24=iso_clock or int(clock[1])==0 or int(clock[1])>12)
    else:
        # A clock unit binds its own number. Passenger counts elsewhere are not candidates.
        cue = re.search(number_pattern+r'\s*(?:மணி(?:க்கு|யளவில்)?|manikku|mani|o.clock|a\.?m\.?|p\.?m\.?)(?![a-z])',clock_text)
        if not cue:
            periods = r'காலை|மதியம்|நண்பகல்|மாலை|நள்ளிரவு|இரவு|\b(?:morning|afternoon|evening|night|noon|midnight|kaalai|kalai|madhiyam|mathiyam|maalai|malai|iravu|nalliravu)\b'
            cue = re.search(r'(?:'+periods+r')\s+(?:at\s+)?'+number_pattern,clock_text)
        if not cue and allow_bare:
            cue = re.fullmatch(r'\s*'+number_pattern+r'\s*[.!?]?\s*',clock_text)
        if cue:
            hour = int(cue['hour']) if cue['hour'].isdigit() else lexicon[cue['hour']]
            found.update(hour=hour,minute=0,clock24=hour==0 or hour>12)
    explicit_am = bool(re.search(r'(?<![a-z])a\.?m\.?(?![a-z])',clock_text))
    explicit_pm = bool(re.search(r'(?<![a-z])p\.?m\.?(?![a-z])',clock_text))
    morning = bool(re.search(r'காலை|அதிகாலை|\b(?:morning|kaalai|kalai|adhikaalai)\b',clock_text))
    afternoon = bool(re.search(r'மதியம்|நண்பகல்|மாலை|\b(?:afternoon|evening|madhiyam|mathiyam|maalai|malai|noon)\b',clock_text))
    midnight = bool(re.search(r'நள்ளிரவு|\b(?:midnight|nalliravu)\b',clock_text))
    night = bool(re.search(r'(?<!நள்)இரவு|\b(?:night|tonight|iravu)\b',clock_text))
    if (explicit_am and explicit_pm or morning and afternoon or midnight and afternoon
            or explicit_pm and (morning or midnight) or explicit_am and afternoon):
        raise GuardError('clarify_period')
    if explicit_am or explicit_pm:
        found['period'] = 'am' if explicit_am else 'pm'
        found['day_period'] = found['period']
    elif midnight:
        found['period']='am';found['day_period']='midnight'
        if 'hour' not in found:found.update(hour=12,minute=0,clock24=False)
    elif morning or afternoon:
        found['period']='am' if morning else 'pm';found['day_period']=found['period']
        if 'hour' not in found and re.search(r'\bnoon\b|நண்பகல்',clock_text):found.update(hour=12,minute=0,clock24=False)
    elif night:
        found['day_period']='night'
        if 'hour' in found and 1 <= found['hour'] <= 12:
            found['period']='am' if found['hour']<=5 or found['hour']==12 else 'pm'
    if 'hour' in found and not (0 <= found['hour'] <= 23 and 0 <= found.get('minute',0) <= 59):
        raise GuardError('invalid_datetime')
    return found


def components_datetime(parts, now):
    if not parts.get('date'):raise GuardError('clarify_date')
    if 'hour' not in parts:raise GuardError('clarify_clock')
    hour = parts['hour']; period = parts.get('period')
    if not parts.get('clock24'):
        if parts.get('day_period') == 'night':period='am' if hour<=5 or hour==12 else 'pm'
        if not period and 1 <= hour <= 12:raise GuardError('clarify_period')
        if period:
            if not 1 <= hour <= 12:raise GuardError('invalid_datetime')
            hour = hour % 12 + (12 if period=='pm' else 0)
    try:
        value = datetime.fromisoformat(parts['date']).replace(tzinfo=TZ,hour=hour,minute=parts.get('minute',0))
    except ValueError as exc:
        raise GuardError('invalid_datetime') from exc
    if value <= now.astimezone(TZ):raise GuardError('past_datetime')
    return value


def resolve_pickup(raw, now=None, fallback_date=None):
    now = (now or datetime.now(TZ)).astimezone(TZ)
    parts = time_components(raw, now, allow_bare=True)
    if not parts.get("date") and fallback_date:
        parts["date"] = datetime.fromisoformat(fallback_date).date().isoformat()
    return components_datetime(parts, now)


def update_time_memory(state, text, now):
    parts = copy.deepcopy(state.get('_wx_time') or {})
    if not parts and state.get('pickup_at'):
        dt = datetime.fromisoformat(state['pickup_at']).astimezone(TZ)
        parts.update(date=dt.date().isoformat(),hour=dt.hour,minute=dt.minute,clock24=True)
    elif not parts and state.get('when'):
        try:parts.update(time_components(state['when'],now,allow_bare=True))
        except GuardError:pass
    updates = time_components(text,now,allow_bare=state.get('stage') in ('time','time_period'))
    if updates:
        if 'day_period' in updates and 'period' not in updates:parts.pop('period',None)
        parts.update(updates)
        if ('period' in updates or 'day_period' in updates) and 'hour' not in updates and parts.get('hour',24)<=12:
            parts['clock24']=False
        state.pop('_wx_time_error',None)
        for slot,keys in (('date',('date',)),('time',('hour','minute','period','day_period','clock24'))):
            accepted={key:updates[key] for key in keys if key in updates}
            if accepted:state.setdefault('_wx_slot_evidence',{})[slot]={'text':str(text),'source':'rule','confidence':1.0,'components':accepted}
    elif state.get('_wx_time_error'):
        return None,state['_wx_time_error']
    state['_wx_time']=parts
    try:pickup=components_datetime(parts,now)
    except GuardError as exc:
        if updates:state['when']=canonical(parts)
        return None,str(exc)
    state['when']=state['pickup_at']=pickup.isoformat()
    return pickup,None


class WeatherClient:
    def __init__(self, getter=None, ttl=900, rain_threshold=60, heat_c=38, feels_like_c=40):
        if getter is None:
            import requests
            getter = requests.get
        self.getter, self.ttl, self.rain_threshold = getter, ttl, rain_threshold
        # Application advisory thresholds, not an official heatwave warning.
        self.heat_c,self.feels_like_c=float(heat_c),float(feels_like_c)
        self.cache, self.lock = {}, threading.RLock()
        self.requests = self.hits = 0

    def forecast(self, points, pickup, now=None):
        now = now or datetime.now(TZ)
        horizon = (pickup.date() - now.astimezone(TZ).date()).days
        if not 0 <= horizon < 16:
            return {"status": "outside_forecast_range", "source": "Open-Meteo"}
        key = (tuple((round(float(p["lat"]), 3), round(float(p["lng"]), 3)) for p in points), pickup.date().isoformat())
        with self.lock:
            cached = self.cache.get(key)
            if cached and time.monotonic() - cached[0] < self.ttl:
                self.hits += 1
                payload, fetched = cached[1], cached[2]
            else:
                try:
                    self.requests += 1
                    response = self.getter("https://api.open-meteo.com/v1/forecast", params={
                        "latitude": ",".join(str(p["lat"]) for p in points),
                        "longitude": ",".join(str(p["lng"]) for p in points),
                        "hourly": "weather_code,precipitation_probability,precipitation,temperature_2m,apparent_temperature",
                        "timezone": "Asia/Kolkata", "start_date": pickup.date().isoformat(),
                        "end_date": pickup.date().isoformat()}, timeout=(3, 7))
                    response.raise_for_status()
                    payload = response.json()
                    payload = payload if isinstance(payload, list) else [payload]
                    if len(payload) != len(points):
                        raise ValueError("Unexpected location count")
                    fetched = time.time()
                    self.cache[key] = (time.monotonic(), payload, fetched)
                    if len(self.cache) > 256:
                        self.cache.pop(next(iter(self.cache)))
                except Exception:
                    return {"status": "unavailable", "source": "Open-Meteo"}
        target = pickup.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
        rows = []
        try:
            for name, item in zip(("pickup", "destination"), payload):
                hourly = item["hourly"]
                index = hourly["time"].index(target)
                code = hourly["weather_code"][index]
                if code is None:
                    raise ValueError("Missing condition")
                row = {"location": name, "valid_at": target, "weather_code": int(code)}
                for field in ("precipitation_probability", "precipitation", "temperature_2m", "apparent_temperature"):
                    v = hourly.get(field,[None]*len(hourly["time"]))[index]
                    row[field] = float(v) if v is not None and math.isfinite(float(v)) else None
                rows.append(row)
        except (KeyError, ValueError, TypeError, IndexError):
            return {"status": "unavailable", "source": "Open-Meteo"}
        rain = any(r["weather_code"] in RAIN_CODES or
                   (r["precipitation_probability"] is not None and r["precipitation_probability"] >= self.rain_threshold)
                   for r in rows)
        cloudy = any(r["weather_code"] in (2, 3) for r in rows)
        clear = all(r["weather_code"] in (0, 1) for r in rows)
        heavy=any(r["weather_code"] in (65,67,82) for r in rows)
        storm=any(r["weather_code"] in (95,96,97,99) for r in rows)
        heat=any((r["temperature_2m"] is not None and r["temperature_2m"]>=self.heat_c) or
                 (r["apparent_temperature"] is not None and r["apparent_temperature"]>=self.feels_like_c) for r in rows)
        pleasant=clear and all(r["temperature_2m"] is not None and 18<=r["temperature_2m"]<=32 for r in rows) and not heat
        return {"status": "ok", "condition": "rain" if rain else "cloudy" if cloudy else "clear" if clear else "other",
                "points": rows, "fetched_at": fetched, "source": "Open-Meteo",
                "heavy_rain":heavy,"thunderstorm":storm,"heat":heat,"pleasant":pleasant,
                "advisory_thresholds":{"rain_probability_pct":self.rain_threshold,"heat_c":self.heat_c,"feels_like_c":self.feels_like_c},
                "scope": "pickup_and_destination_at_pickup_hour"}


def spoken_number(value, lang="English"):
    text = f"{float(value):.1f}".rstrip("0").rstrip(".")
    whole, _, decimal = text.partition(".")
    result = number_words(int(whole), lang)
    if decimal:
        result += (" புள்ளி " if lang == "Tamil" else " pulli " if lang == "Tanglish" else " point ") + " ".join(number_words(int(d), lang) for d in decimal)
    return result


def probability_report(state):
    lang, weather = state['lang'], state.get('weather') or {}
    if weather.get('status') != 'ok':
        return localized(lang,'The rain forecast for that journey time is not available. You can still continue with booking.',
            'அந்தப் பயண நேரத்திற்கான மழை முன்னறிவிப்பு கிடைக்கவில்லை. இருப்பினும் முன்பதிவைத் தொடரலாம்.',
            'Andha payana nerathirkaana mazhai munnarivippu kidaikkavillai. Irundhaalum munpadhivai thodaralaam.')
    lines=[]
    for key,en,ta in (('pickup','pickup','புறப்படும்'),('destination','drop','சேரும்')):
        point=next((p for p in weather.get('points',[]) if p.get('location')==key),{})
        probability=point.get('precipitation_probability');name=state.get(key) or en
        if probability is None or not math.isfinite(float(probability)) or not 0<=float(probability)<=100:
            lines.append(localized(lang,f'The rain probability at your {en} location, {name}, is not available.',
                f'{ta} இடமான {name} பகுதியில் மழைக்கான வாய்ப்பு மதிப்பீடு கிடைக்கவில்லை.',
                f'{"Purappadum" if key=="pickup" else "Serum"} idamaana {name} pagudhiyil mazhaikkaana vaaippu madhippeedu kidaikkavillai.'))
        else:
            digits=numeric_text(probability)
            lines.append(localized(lang,f'At your {en} location, {name}, the chance of rain is {digits}%.',
                f'{ta} இடமான {name} பகுதியில் மழைக்கான வாய்ப்பு {digits}%.',
                f'{"Purappadum" if key=="pickup" else "Serum"} idamaana {name} pagudhiyil mazhaikkaana vaaippu {digits}%.'))
    return '\n'.join(lines)


def weather_report(state):
    lang = state["lang"]
    weather = state.get("weather") or {}
    status = weather.get("status")
    if status != "ok":
        return probability_report(state)
    condition = weather["condition"]
    if weather.get("thunderstorm"):
        message=localized(lang,"Thunderstorms are forecast around your selected pickup time.",
            "நீங்கள் தேர்ந்தெடுத்த பயண நேரத்தில் இடியுடன் கூடிய மழை எதிர்பார்க்கப்படுகிறது.",
            "Neenga therndhedutha payana nerathil idiyudan koodiya mazhai edhirpaarkkappadugiradhu.")
    elif weather.get("heavy_rain"):
        message=localized(lang,"Heavy rain is forecast around your selected pickup time.",
            "நீங்கள் தேர்ந்தெடுத்த பயண நேரத்தில் கனமழை எதிர்பார்க்கப்படுகிறது.",
            "Neenga therndhedutha payana nerathil kanamazhai edhirpaarkkappadugiradhu.")
    elif condition == "rain":
        message = localized(lang,
            "Rain is expected at the pickup or destination around your pickup time.",
            "நீங்கள் புறப்படும் நேரத்தில், புறப்படும் இடம் அல்லது சேரும் இடத்தில் மழை எதிர்பார்க்கப்படுகிறது.",
            "Neenga purappadum nerathil purappadum idam alladhu serum idathil mazhai peiya vaaippu irukkiradhu.")
    elif condition == "cloudy":
        message = localized(lang, "Cloudy conditions are expected around your pickup time.",
            "நீங்கள் புறப்படும் நேரத்தில் மேகமூட்டம் எதிர்பார்க்கப்படுகிறது.", "Neenga purappadum nerathil megamoottam edhirpaarkkappadugiradhu.")
    elif condition == "clear":
        message = localized(lang, "The weather looks pleasant around your selected pickup time." if weather.get("pleasant") else "Clear or mainly clear skies are expected around your pickup time.",
            "நீங்கள் தேர்ந்தெடுத்த பயண நேரத்தில் வானிலை நன்றாக இருக்கும் என எதிர்பார்க்கப்படுகிறது." if weather.get("pleasant") else
            "நீங்கள் புறப்படும் நேரத்தில் வானம் தெளிவாக அல்லது பெரும்பாலும் தெளிவாக இருக்கும் என எதிர்பார்க்கப்படுகிறது.",
            "Neenga therndhedutha payana nerathil vaanilai nandraagave irukkum ena edhirpaarkkappadugiradhu." if weather.get("pleasant") else "Neenga purappadum nerathil vaanam thelivaaga irukkum ena edhirpaarkkappadugiradhu.")
    else:
        message = localized(lang,
            "Other weather conditions are forecast. Please check local weather information before travelling.",
            "பிற வானிலை நிலைமைகள் எதிர்பார்க்கப்படுகின்றன. பயணத்திற்கு முன் உள்ளூர் வானிலைத் தகவல்களைப் பாருங்கள்.",
            "Pira vaanilai nilaimaigal edhirpaarkkappadugindrana. Payanathirku mun ulloor vaanilai thagavalgalai paarunga.")
    if weather.get("heat"):
        message += "\n"+localized(lang,
            "Very hot conditions are expected. Please carry water and prepare for high temperatures.",
            "வெப்பநிலை அதிகமாக இருக்கும் என எதிர்பார்க்கப்படுகிறது. குடிநீர் எடுத்துக்கொண்டு வெப்பத்திற்கு ஏற்ற முன்னேற்பாடுகளைச் செய்துகொள்ளுங்கள்.",
            "Veppanilai adhigamaaga irukkum ena edhirpaarkkappadugiradhu. Kudineer eduthukkondu veppathirku etra munnerpaadugalai seidhukollunga.")
    return probability_report(state) + "\n" + message


def advisory(state):
    lang, weather = state["lang"], state.get("weather") or {}
    message = weather_report(state)
    if weather.get("status") == "ok" and weather.get("condition") == "rain":
        if state.get("vehicle") == "Auto":
            precaution=localized(lang,"An auto can have exposed sides. Carry an umbrella and keep your belongings protected from rain.",
                "ஆட்டோவின் பக்கவாட்டில் மழை படலாம். குடை எடுத்துக்கொண்டு உங்கள் உடைமைகளை மழையிலிருந்து பாதுகாத்துக்கொள்ளுங்கள்.",
                "Aattovin pakkavaatil mazhai padalaam. Kudai eduthukkondu unga udaimaigalai mazhaiyilirundhu paadhugaathukkollunga.")
        elif state.get("vehicle") == "Bike":
            precaution=localized(lang,"Please prepare rain protection for yourself and your belongings.",
                "நீங்களும் உங்கள் உடைமைகளும் மழையில் நனையாமல் இருக்கத் தேவையான முன்னேற்பாடுகளைச் செய்துகொள்ளுங்கள்.",
                "Neengalum unga udaimaigalum mazhaiyil nanaiyaamal irukka thevaiyaana munnerpaadugalai seidhukollunga.")
        else:
            precaution=localized(lang,"Please carry an umbrella for boarding and getting out, and make suitable rain preparations.",
                "வாகனத்தில் ஏறும்போதும் இறங்கும்போதும் பயன்படுத்தக் குடை எடுத்துக்கொண்டு மழைக்கு ஏற்ற முன்னேற்பாடுகளைச் செய்துகொள்ளுங்கள்.",
                "Vandiyil erumboadhum irangumboadhum payanpadutha kudai eduthukkondu mazhaikku etra munnerpaadugalai seidhukollunga.")
        message += "\n"+precaution
    if weather.get("condition") == "rain" and state.get("vehicle") == "Bike":
        choices = [v for v in ("Mini", "Sedan", "SUV") if CAPACITY[v] >= int(state["count"])]
        if choices:
            severe=weather.get("heavy_rain") or weather.get("thunderstorm")
            if severe:
                message+="\n"+localized(lang,"A bike may be unsuitable in these conditions.","இந்த வானிலையில் பைக் பயணம் பொருத்தமில்லாமல் இருக்கலாம்.","Indha vaanilaiyil baikku payanam poruthamillaamal irukkalaam.")
            options=", ".join(choices);ta_options=", ".join(VEHICLES_TA[v] for v in choices);roman_options=", ".join(VEHICLES_ROMAN[v] for v in choices)
            message += "\n" + localized(lang,
                f"You may choose a covered vehicle such as {options}, or continue with your selected bike. The choice is yours.",
                f"நீங்கள் விரும்பினால் {ta_options} போன்ற மூடிய வாகனத்தைத் தேர்வு செய்யலாம்; அல்லது நீங்கள் தேர்ந்தெடுத்த பைக்கிலேயே தொடரலாம். முடிவு உங்களுடையது.",
                f"Neenga virumbinaal {roman_options} pondra moodiya vandiyai therndhedukkalaam; alladhu neenga therndhedutha baikkileye thodaralaam. Mudivu ungaludaiyadhu.")
    return message


def display_reply(state, text):
    """MOVIO call weather popup v1: retain full display text before speech conversion."""
    return str(text).strip()


def closing_message(lang):
    return localized(lang,"Thank you! Have a wonderful journey!","நன்றி! உங்கள் பயணம் இனிமையாக அமையட்டும்!","Nandri! Ungal payanam inimaiyaaga amaiyattum!")


def completion_message(lang,ride_id):
    digits=str(int(ride_id))
    return localized(lang,f'Your booking request has been saved. Booking number {digits}.',
        f'உங்கள் முன்பதிவு கோரிக்கை பதிவு செய்யப்பட்டது. முன்பதிவு எண் {digits}.',
        f'Unga munpadhivu korikkai padhivu seiyyappattadhu. Munpadhivu enn {digits}.')+'\n'+closing_message(lang)


def speech_segments(text):
    """Sentence clips stream immediately; decimals and short initials stay intact."""
    candidates=re.split(r"(?<=[.!?。])\s+|\n+",str(text).strip())
    parts=[];pending=""
    for part in candidates:
        if not part.strip():continue
        pending=(pending+" "+part).strip()
        if re.search(r"(?:^|\s)(?:[A-Za-z]|Dr|Mr|Ms|Mrs)\.$",pending):continue
        parts.append(pending);pending=""
    if pending:parts.append(pending)
    return parts[:15]+([" ".join(parts[15:])] if len(parts)>15 else [])


class GuardDB:
    def __init__(self, path):
        self.path = str(path)

    def connect(self):
        c = sqlite3.connect(self.path, timeout=20)
        c.row_factory = sqlite3.Row
        return c

    def setup(self):
        with self.connect() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS wx_calls(
                    id TEXT PRIMARY KEY, owner INTEGER NOT NULL, secret_hash TEXT NOT NULL,
                    expires REAL NOT NULL, epoch INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL DEFAULT '{}', summary_nonce TEXT, summary_hash TEXT,
                    summary_expires REAL, played INTEGER NOT NULL DEFAULT 0, ride_id INTEGER,
                    summary_kind TEXT NOT NULL DEFAULT 'final');
                CREATE TABLE IF NOT EXISTS wx_permits(
                    token_hash TEXT PRIMARY KEY, call_id TEXT NOT NULL, epoch INTEGER NOT NULL,
                    version INTEGER NOT NULL, snapshot TEXT NOT NULL, expires REAL NOT NULL, ride_id INTEGER);
            """)
            call_columns = {r[1] for r in c.execute('PRAGMA table_info(wx_calls)')}
            if 'summary_kind' not in call_columns:
                c.execute("ALTER TABLE wx_calls ADD COLUMN summary_kind TEXT NOT NULL DEFAULT 'final'")
            columns = {r[1] for r in c.execute("PRAGMA table_info(rides)")}
            if columns:
                for name, kind in (("passengers", "INTEGER"), ("pickup_time", "TEXT"),
                                   ("weather_json", "TEXT"), ("journey_version", "INTEGER"), ("voice_call_id", "TEXT")):
                    if name not in columns:
                        c.execute(f"ALTER TABLE rides ADD COLUMN {name} {kind}")

    def create(self, owner):
        sid, secret = secrets.token_hex(16), secrets.token_urlsafe(32)
        with self.connect() as c:
            c.execute("INSERT INTO wx_calls(id,owner,secret_hash,expires) VALUES(?,?,?,?)",
                      (sid, owner, hashlib.sha256(secret.encode()).hexdigest(), time.time() + 3600))
        return {"call_id": sid, "bind_token": secret}

    def bind(self, sid, secret):
        with self.connect() as c:
            r = c.execute("SELECT * FROM wx_calls WHERE id=?", (sid,)).fetchone()
        if not r or r["expires"] <= time.time() or not hmac.compare_digest(r["secret_hash"], hashlib.sha256(str(secret).encode()).hexdigest()):
            raise GuardError("Invalid or expired call session")
        if r["ride_id"]:
            raise GuardError("This call already created a booking")
        return dict(r)

    def row(self, sid):
        with self.connect() as c:
            row = c.execute("SELECT * FROM wx_calls WHERE id=?", (sid,)).fetchone()
        if not row:
            raise GuardError("Unknown call")
        return dict(row)

    def begin(self, sid, interrupt=False):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM wx_calls WHERE id=?", (sid,)).fetchone()
            if not r or r["expires"] <= time.time():
                raise GuardError("Call expired")
            if r["ride_id"]:
                raise GuardError("Booking was already saved; use cancellation to change it")
            epoch = r["epoch"] + 1
            c.execute("UPDATE wx_calls SET epoch=? WHERE id=?", (epoch, sid))
            if interrupt:
                c.execute("UPDATE wx_calls SET summary_nonce=NULL,summary_hash=NULL,played=0 WHERE id=?", (sid,))
            return epoch

    def current(self, sid, epoch):
        r = self.row(sid)
        return r["epoch"] == epoch and r["expires"] > time.time() and not r["ride_id"]

    def stash(self, sid, epoch, state):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM wx_calls WHERE id=?", (sid,)).fetchone()
            if not r or r["epoch"] != epoch or r["ride_id"]:
                raise GuardError("Obsolete turn")
            old = json.loads(r["state"])
            changed = any(old.get(k) != state.get(k) for k in CORE_FIELDS)
            version = r["version"] + int(changed)
            c.execute("UPDATE wx_calls SET state=?,version=? WHERE id=?", (canonical(state), version, sid))
            if changed:
                c.execute("UPDATE wx_calls SET summary_nonce=NULL,summary_hash=NULL,played=0 WHERE id=?", (sid,))
            return version

    def summary(self, sid, epoch, state):
        nonce, sh = secrets.token_hex(16), digest(snapshot(state))
        kind = 'weather' if state.get('stage') == 'weather_advisory' else 'final'
        with self.connect() as c:
            cur = c.execute("UPDATE wx_calls SET summary_nonce=?,summary_hash=?,summary_expires=?,played=0,summary_kind=? WHERE id=? AND epoch=? AND ride_id IS NULL",
                            (nonce, sh, time.time() + 600, kind, sid, epoch))
            if cur.rowcount != 1:
                raise GuardError("Obsolete summary")
        return nonce

    def played(self, sid, epoch, nonce, explicit_read=False):
        with self.connect() as c:
            extra = " AND summary_kind='final'" if explicit_read else ''
            return c.execute("UPDATE wx_calls SET played=1 WHERE id=? AND epoch=? AND summary_nonce=? AND summary_expires>? AND ride_id IS NULL"+extra,
                             (sid, epoch, nonce, time.time())).rowcount == 1

    def accept_weather(self, sid, epoch, nonce, state):
        """The first Yes records consent only. It cannot issue a booking permit."""
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM wx_calls WHERE id=?',(sid,)).fetchone()
            if (not r or r['epoch']!=epoch or r['ride_id'] or r['summary_kind']!='weather'
                    or not r['played'] or r['summary_nonce']!=nonce or r['summary_hash']!=digest(snapshot(state))
                    or r['summary_expires']<=time.time() or r['expires']<=time.time()):
                raise GuardError('Please hear the weather advisory and confirm again')
            state['_wx_weather_consent']={'scope':weather_consent_scope(state),'accepted_at':time.time()}
            state['stage']='fare'
            c.execute('UPDATE wx_calls SET state=?,summary_nonce=NULL,summary_hash=NULL,played=0 WHERE id=?',
                      (canonical(state),sid))
        return state

    def permit(self, sid, epoch, nonce, state):
        token = secrets.token_urlsafe(32)
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM wx_calls WHERE id=?", (sid,)).fetchone()
            if (not r or r["epoch"] != epoch or r["ride_id"] or not r["played"] or r['summary_kind']!='final'
                    or r["summary_nonce"] != nonce or r["summary_hash"] != digest(snapshot(state))
                    or r["summary_expires"] <= time.time()):
                raise GuardError("Please hear or read the updated summary and confirm again")
            if state.get('_wx_mode') != 'manual' and not weather_consented(state):
                raise GuardError('Weather consent is required before final booking confirmation')
            c.execute("INSERT INTO wx_permits VALUES(?,?,?,?,?,?,NULL)",
                      (hashlib.sha256(token.encode()).hexdigest(), sid, epoch, r["version"], canonical(snapshot(state)), time.time() + 90))
        return token

    def commit(self, c, owner, token, ensure_code):
        """One SQLite transaction validates the revision and inserts at most one ride."""
        c.execute("BEGIN IMMEDIATE")
        p = c.execute("SELECT * FROM wx_permits WHERE token_hash=?", (hashlib.sha256(str(token).encode()).hexdigest(),)).fetchone()
        if not p:
            raise GuardError("Unknown confirmation")
        call = c.execute("SELECT * FROM wx_calls WHERE id=?", (p["call_id"],)).fetchone()
        if not call or call["owner"] != owner:
            raise PermissionError("This confirmation belongs to another account")
        if p["ride_id"]:
            return {"ok": True, "id": p["ride_id"], "reused": True}
        if (call["ride_id"] or p["expires"] <= time.time() or call["expires"] <= time.time()
                or call["epoch"] != p["epoch"] or call["version"] != p["version"]):
            raise GuardError("Journey changed or confirmation expired; confirm the latest summary")
        s = json.loads(p["snapshot"])
        if s.get('_wx_mode') != 'manual' and not weather_consented(s):
            raise GuardError('Weather consent is required before booking')
        vehicle, count = s["vehicle"], int(s["count"])
        if vehicle not in CAPACITY or not 1 <= count <= CAPACITY[vehicle]:
            raise GuardError("Invalid vehicle capacity")
        coords = [float(s[k][axis]) for k in ("pickup_geo", "destination_geo") for axis in ("lat", "lng")]
        if not all(math.isfinite(v) and abs(v) <= (90 if i % 2 == 0 else 180) for i, v in enumerate(coords)):
            raise GuardError("Invalid coordinates")
        pickup = datetime.fromisoformat(s["pickup_at"])
        if pickup.tzinfo is None or pickup.timestamp() <= time.time():
            raise GuardError("Pickup time has passed; choose a new time")
        fare = float(s["fare"]["fare"])
        if not math.isfinite(fare) or fare < 0:
            raise GuardError("Invalid route fare")
        status = "scheduled" if pickup.timestamp() > time.time() + 20 * 60 else "requested"
        now = time.time()
        cur = c.execute("""INSERT INTO rides(customer_id,pickup,destination,plat,plng,dlat,dlng,vehicle,fare,status,
                           source,created,updated,passengers,pickup_time,weather_json,journey_version,voice_call_id)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (owner, s["pickup"], s["destination"], *coords, vehicle, round(fare), status,
                         "weather_web" if s.get("_wx_mode")=="manual" else "weather_voice", now, now, count, s["pickup_at"], canonical(s["weather"]), p["version"], p["call_id"]))
        rid = cur.lastrowid
        ensure_code(c, rid)
        c.execute("UPDATE wx_calls SET ride_id=? WHERE id=?", (rid, p["call_id"]))
        c.execute("UPDATE wx_permits SET ride_id=? WHERE token_hash=?", (rid, p["token_hash"]))
        return {"ok": True, "id": rid, "status": status, "reused": False}

    def release_due(self):
        # No late automatic dispatch after a notebook has been offline.
        now = datetime.now(TZ)
        with self.connect() as c:
            for row in c.execute("SELECT id,pickup_time FROM rides WHERE status='scheduled' AND source IN ('weather_voice','weather_web')").fetchall():
                when = datetime.fromisoformat(row["pickup_time"])
                if now.timestamp() <= when.timestamp() <= now.timestamp() + 20 * 60:
                    c.execute("UPDATE rides SET status='requested',updated=? WHERE id=? AND status='scheduled'", (time.time(), row["id"]))


def manual_state(data,weather,now=None):
    """Validate exactly the customer's choices; weather never changes them."""
    now=(now or datetime.now(TZ)).astimezone(TZ)
    lang=data.get("language","English")
    if lang not in ("English","Tamil","Tanglish"):raise GuardError("invalid_language")
    vehicle=data.get("vehicle")
    if vehicle not in CAPACITY:raise GuardError("invalid_vehicle")
    raw_count=str(data.get("count",1))
    if not re.fullmatch(r"[1-6]",raw_count) or int(raw_count)>CAPACITY[vehicle]:raise GuardError("invalid_capacity")
    try:
        pickup=datetime.fromisoformat(str(data.get("pickup_at","")))
        pickup=pickup.replace(tzinfo=TZ) if pickup.tzinfo is None else pickup.astimezone(TZ)
    except ValueError as exc:raise GuardError("invalid_datetime") from exc
    if pickup<=now:raise GuardError("past_datetime")
    places={}
    for key,lat,lng in (("pickup","plat","plng"),("destination","dlat","dlng")):
        name=str(data.get(key,"")).strip()
        if not name or len(name)>180:raise GuardError("missing_locations")
        try:a,b=float(data[lat]),float(data[lng])
        except (KeyError,ValueError,TypeError) as exc:raise GuardError("missing_locations") from exc
        if not (math.isfinite(a) and math.isfinite(b) and -90<=a<=90 and -180<=b<=180):raise GuardError("missing_locations")
        places[key]=name;places[key+"_geo"]={"lat":a,"lng":b}
    try:km,fare=float(data.get("km",0)),float(data["fare"])
    except (KeyError,ValueError,TypeError) as exc:raise GuardError("invalid_fare") from exc
    if not (math.isfinite(km) and math.isfinite(fare) and km>=0 and fare>=0):raise GuardError("invalid_fare")
    state=dict(lang=lang,_wx_mode="manual",mode="book",stage="confirm",count=int(raw_count),vehicle=vehicle,
        when=pickup.isoformat(),pickup_at=pickup.isoformat(),fare={"km":round(km,1),"fare":round(fare)},**places)
    state["weather"]=weather.forecast([state["pickup_geo"],state["destination_geo"]],pickup,now=now)
    return state


def manual_error(lang,code):
    messages={
        "invalid_datetime":("Please select your booking date and time.","பயணத்தின் தேதி மற்றும் நேரத்தைத் தேர்ந்தெடுக்கவும்.","Payanathin thedhi matrum nerathai therndhedukkavum."),
        "past_datetime":("That pickup time has passed. Please choose a later time.","அந்த நேரம் கடந்துவிட்டது. அதற்குப் பிந்தைய நேரத்தைத் தேர்ந்தெடுக்கவும்.","Andha neram kadandhuvittadhu. Adharku pindhaiya nerathai therndhedukkavum."),
        "invalid_capacity":("Please choose a passenger count and vehicle with sufficient seats.","பயணிகளின் எண்ணிக்கைக்கு ஏற்ற இருக்கைகள் உள்ள வாகனத்தைத் தேர்ந்தெடுக்கவும்.","Payanigalin ennikkai-kku etra irukkaigal ulla vandiyai therndhedukkavum."),
        "missing_locations":("Please choose the pickup and destination from the map or address suggestions.","புறப்படும் இடத்தையும் சேரும் இடத்தையும் வரைபடம் அல்லது முகவரி பரிந்துரைகளிலிருந்து தேர்ந்தெடுக்கவும்.","Purappadum idathaiyum serum idathaiyum varaipadam alladhu mugavari parindhuraigalilirundhu therndhedukkavum."),
        "expired_review":("The review has expired. Please check the weather and booking details again.","சுருக்கத்தின் காலம் முடிந்துவிட்டது. வானிலை மற்றும் முன்பதிவு விவரங்களை மீண்டும் சரிபார்க்கவும்.","Surukkathin kaalam mudindhuvittadhu. Vaanilai matrum munpadhivu vivarangalai meendum saripaarunga.")}
    return localized(lang,*messages.get(code,("The request could not be completed. Please check the details and try again.","கோரிக்கையை நிறைவு செய்ய முடியவில்லை. விவரங்களைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.","Korikkaiyai niraivu seiyya mudiyavillai. Vivarangalai saripaarthu meendum muyarchikkavum.")))


def install_backend(module,weather=None):
    if getattr(module.Handler, "_wx_version", None) == VERSION:
        if weather is not None:module._wx_weather_client=weather
        return
    db = GuardDB(module.DB)
    db.setup()
    old_thread=getattr(module,"_wx_dispatch_thread",None)
    if old_thread is not None:
        old_stop=getattr(module,"_wx_stop_event",None)
        if old_stop is not None:old_stop.set()
        old_thread.join(timeout=25)
        if old_thread.is_alive():raise RuntimeError("The previous scheduling worker is still stopping; rerun activation shortly.")
        del module._wx_dispatch_thread
    weather=weather or getattr(module,"_wx_weather_client",None) or WeatherClient(rain_threshold=float(module.os.environ.get("MOVIO_RAIN_THRESHOLD",60)),
        heat_c=float(module.os.environ.get("MOVIO_HEAT_C",38)),feels_like_c=float(module.os.environ.get("MOVIO_FEELS_LIKE_C",40)))
    module._wx_weather_client=weather
    original_get = getattr(module.Handler, "_wx_original_get", module.Handler.do_GET)
    original_post = getattr(module.Handler, "_wx_original_post", module.Handler.do_POST)

    def guarded_post(h):
        path = urlparse(h.path).path
        if not path.startswith("/api/weather-booking/"):
            return original_post(h)
        data={};lang="English"
        try:
            origin = h.headers.get("Origin", "").rstrip("/")
            if origin and origin != module.PUBLIC:
                raise PermissionError("Origin mismatch")
            data = json.loads(h.payload(12000) or b"{}")
            lang=data.get("language","English") if isinstance(data,dict) else "English"
            if not isinstance(data,dict):raise GuardError("Invalid request")
            with module.LOCK,module.conn() as c:
                user=dict(h.user(c))
                if user["role"]!="customer":raise PermissionError("Customer account required")
            if path.endswith("/manual-preview"):
                # External forecast requests never hold the website's DB lock.
                s=manual_state(data,module._wx_weather_client)
                binding=db.create(user["id"]);e=db.begin(binding["call_id"])
                version=db.stash(binding["call_id"],e,s);nonce=db.summary(binding["call_id"],e,s)
                return h.json(200,{"ok":True,**binding,"epoch":e,"version":version,"summary_nonce":nonce,
                    "advisory":advisory(s),"summary":display_reply(s,summary_text(None,s)),"language":s["lang"],
                    "weather_status":s["weather"]["status"],"pickup_at":s["pickup_at"],"vehicle":s["vehicle"],"fare":s["fare"]["fare"]})
            with module.LOCK, module.conn() as c:
                user = h.user(c)
                if user["role"] != "customer":
                    raise PermissionError("Customer account required")
                if path.endswith("/manual-confirm"):
                    row=db.row(data.get("call_id"))
                    if row["owner"]!=user["id"] or not hmac.compare_digest(row["secret_hash"],hashlib.sha256(str(data.get("bind_token","")).encode()).hexdigest()):
                        raise PermissionError("This review belongs to another account")
                    s=json.loads(row["state"]);lang=s["lang"]
                    if s.get("_wx_mode")!="manual":raise GuardError("expired_review")
                    if row["ride_id"]:
                        result={"ok":True,"id":row["ride_id"],"reused":True}
                    else:
                        if not db.played(row["id"],row["epoch"],data.get("summary_nonce")):raise GuardError("expired_review")
                        token=db.permit(row["id"],row["epoch"],data.get("summary_nonce"),s)
                        result=db.commit(c,user["id"],token,module.ensure_pickup_code);c.commit()
                    return h.json(201,{**result,"language":lang,"message":completion_message(lang,result["id"]),"closing":closing_message(lang)})
                if path.endswith("/manual-discard"):
                    row=db.row(data.get("call_id"))
                    if row["owner"]!=user["id"] or not hmac.compare_digest(row["secret_hash"],hashlib.sha256(str(data.get("bind_token","")).encode()).hexdigest()):
                        raise PermissionError("This review belongs to another account")
                    if row["ride_id"]:return h.json(200,{"ok":True,"already_saved":True,"id":row["ride_id"]})
                    db.begin(row["id"],interrupt=True)
                    return h.json(200,{"ok":True})
                if path.endswith("/session"):
                    return h.json(200, db.create(user["id"]))
                if path.endswith("/commit"):
                    result = db.commit(c, user["id"], data.get("token", ""), module.ensure_pickup_code)
                    c.commit()
                    return h.json(201, result)
                if path.endswith("/cancel"):
                    rid = int(data["ride_id"])
                    cur = c.execute("UPDATE rides SET status='cancelled',updated=? WHERE id=? AND customer_id=? AND status='scheduled'",
                                    (time.time(), rid, user["id"]))
                    if cur.rowcount != 1:
                        raise GuardError("Scheduled booking not found; refresh your bookings")
                    c.commit()
                    return h.json(200, {"ok": True, "id": rid})
            return h.json(404, {"error": "Unknown weather-booking endpoint"})
        except PermissionError as exc:
            return h.json(401 if str(exc) == "Log in first" else 403, {"error": str(exc)})
        except (ValueError, KeyError, TypeError) as exc:
            return h.json(409, {"error":manual_error(lang,str(exc)) if "/manual-" in path else str(exc),"code":str(exc)})
        except Exception:
            return h.json(500, {"error": "Weather booking request failed"})

    def guarded_get(h):
        path = urlparse(h.path).path
        if path == "/api/weather-booking/health":
            return h.json(200, {"ok": True, "version": VERSION, "weather": "Open-Meteo", "guard": "sqlite_atomic_revision"})
        if path == "/api/rides":
            db.release_due()
        return original_get(h)

    module.Handler.do_POST, module.Handler.do_GET = guarded_post, guarded_get
    module.Handler._wx_original_get, module.Handler._wx_original_post = original_get, original_post
    module.Handler._wx_installed = True
    module.Handler._wx_version = VERSION
    if not hasattr(module, "_wx_dispatch_thread"):
        stop_event=threading.Event()
        module._wx_stop_event = stop_event
        def dispatch():
            while not stop_event.is_set():
                try:
                    db.release_due()
                except Exception:
                    pass
                stop_event.wait(30)
        module._wx_dispatch_thread = threading.Thread(target=dispatch, daemon=True, name="weather-scheduled-release")
        module._wx_dispatch_thread.start()


def summary_text(bridge, s):
    lang=s['lang'];date=spoken_datetime(s['pickup_at'],lang)
    count=numeric_text(s['count'],0);km=numeric_text(s['fare']['km']);fare=numeric_text(s['fare']['fare'],0,grouped=True)
    return localized(lang,
        f"Your booking: {count} {'passenger' if int(s['count'])==1 else 'passengers'}, {s['vehicle']}, from {s['pickup']} to {s['destination']}, on {date}. "
        f'The road distance is about {km} kilometres and the estimated fare is ₹{fare}. Shall I confirm this booking?',
        f"உங்கள் முன்பதிவு விவரம்: {count} பேர், {VEHICLES_TA.get(s['vehicle'],s['vehicle'])}, {s['pickup']} இலிருந்து {s['destination']} வரை, {date}. "
        f'சாலை தூரம் சுமார் {km} கிலோமீட்டர். மதிப்பிடப்பட்ட கட்டணம் ₹{fare}. இந்த முன்பதிவை உறுதி செய்யலாமா?',
        f"Unga munpadhivu vivaram: {count} peru, {VEHICLES_ROMAN[s['vehicle']]}, {s['pickup']} ilirundhu {s['destination']} varai, {date}. "
        f'Saalai dhooram sumaar {km} kilo meettar. Madhippidappatta kattanam ₹{fare}. Indha munpadhivai urudhi seiyyalaama?')


def clean_spoken_place(bridge,value):
    text=str(value or '').strip(' .,!?:;–—-')
    text=re.sub(r'(?i)^(?:i\s+(?:want|need)\s+to\s+(?:go|travel)\s+|i\s+am\s+|naan\s+|nan\s+|enakku\s+)','',text)
    text=re.sub(r'^(?:நான்|எனக்கு)\s*','',text)
    text=re.split(r'(?<!\b[A-Za-z])\.\s+|[!?;\n]',text,maxsplit=1)[0]
    text=re.split(r'(?i)\s+(?:செல்ல|போக|போகணும்|போகனும்|வேண்டும்|நாங்கள்|எனக்கு|இன்று|நாளை|poganum|ponum|venum|we\s+are|for\s+\d+|at\s+\d|today|tomorrow)\b|\s+(?:செல்ல|போக|நாங்கள்|எனக்கு|இன்று|நாளை)',text,maxsplit=1)[0]
    text=re.split(r',\s*(?=(?:one|two|three|four|five|six|bike|mini|sedan|auto|suv|today|tomorrow)\b)',text,flags=re.I,maxsplit=1)[0]
    canonicalizer=getattr(bridge,'canonical_place',None)
    canonical_value=canonicalizer(text) if callable(canonicalizer) else text
    if canonical_value!=text:return str(canonical_value)[:120]
    text=re.sub(r'[-\s]*(?:இல்\s*இருந்து|இலிருந்து|லிருந்து|இருந்து|க்கு|இல்|\b(?:la\s+irundhu|irundhu|ku)\b)$','',text,flags=re.I)
    return text.strip(' .,!?:;–—-')[:120]


def collect_details(bridge,s,text):
    """Structured updates with explicit evidence; confidence values are rule scores, not calibrated probabilities."""
    stage=s.get('stage');raw=unicodedata.normalize('NFKC',str(text)).strip()
    words=number_lexicon(20);token=r'\d{1,2}|'+'|'.join(re.escape(k) for k in sorted(words,key=len,reverse=True))
    count_match=re.search(r'(?<![\w\u0b80-\u0bff])('+token+r')\s*(?:பேர்|நபர்கள்|பயணிகள்|people\b|persons?\b|passengers?\b|peru\b|per\b)',raw,re.I)
    if not count_match and stage=='count':count_match=re.fullmatch(r'\s*('+token+r')\s*[.!]?\s*',raw,re.I)
    updates={};evidence={};ambiguities=s.setdefault('_wx_slot_conflicts',{})
    def accept(slot,value,span,source='rule',confidence=1.0):
        updates[slot]=value;evidence[slot]={'text':span,'source':source,'confidence':confidence}
        ambiguities.pop(slot,None)
    if count_match:
        value=count_match[1].casefold();accept('count',int(value) if value.isdigit() else words[value],count_match[0])
    patterns=(('SUV',r'\bs\s*u\s*v\b|எஸ்\s*ய[ுூ]?\s*வி|எஸ்யூவி'),('Sedan',r'\bsedan\b|செடான்'),
              ('Mini',r'\bmini(?:\s+car)?\b|மினி(?:\s*கார்)?'),('Auto',r'\bauto\b|ஆட்டோ'),('Bike',r'\bbike\b|பைக்'))
    hits=sorted((m.start(),m.end(),name,m[0]) for name,pattern in patterns for m in re.finditer(pattern,raw,re.I))
    selected=set(h[2] for h in hits)
    correction=bool(re.search(r'\b(?:no|change|instead|replace|not|maathu|mathunga|badila|illa|vendam)\b|மாற்ற|வேண்டாம்|இல்லை',raw,re.I))
    if len(selected)==1:accept('vehicle',hits[-1][2],hits[-1][3])
    elif hits and correction:accept('vehicle',hits[-1][2],raw[hits[0][0]:hits[-1][1]])
    elif len(selected)>1:ambiguities['vehicle']='multiple vehicles stated without an explicit correction'
    places={}
    route=re.search(r'(?i)\bfrom\s+(.+?)\s+to\s+(.+)',raw)
    if not route:route=re.match(r'(.+?)[-\s]*(?:இல்\s*இருந்து|இலிருந்து|லிருந்து|இருந்து)\s+(.+)',raw)
    if not route:route=re.match(r'(?i)(.+?)\s+(?:la\s+)?irundhu\s+(.+)',raw)
    if route:
        destination = route[2]
        # Stop destination capture before unrelated booking details.
        destination = re.split(
            r'(?i)\s+(?:and\s+)?(?:'
            r'i\s+am\b|i\s+need\b|we\s+are\b|'
            r'we\s+need\b|there\s+are\b|'
            r'\d+\s+(?:people|persons?|passengers?)\b|'
            r'book\s+(?:a\s+)?cab\b|'
            r'today\b|tomorrow\b'
            r')',
            destination,
            maxsplit=1
        )[0].strip(' ,.;')
        places={'pickup':route[1],'destination':destination}
    else:
        for slot,pattern in (('pickup',r'(?i)\b(?:pickup(?:\s+is|\s+from)?|pick me up (?:from|at))\s+(.+)'),
                             ('destination',r'(?i)\b(?:destination(?:\s+is)?|drop(?:\s+is|\s+at)?|take me to)\s+(.+)')):
            match=re.search(pattern,raw)
            if match:places[slot]=match[1]
    is_time=bool(re.search(TODAY_RE+'|'+TOMORROW_RE+'|'+AM_RE+'|'+PM_RE+r'|\d[:.]\d|மணி|\d{4}-\d{2}-\d{2}|october|அக்டோபர்',raw,re.I))
    normalized=reply_normalized(raw)
    if not places and stage in ('pickup','destination') and not selected and not count_match and not is_time and normalized not in POSITIVE|NEGATIVE:
        places[stage]=raw
    for slot,span in places.items():
        value=clean_spoken_place(bridge,span)
        if value:accept(slot,value,span)
    # Qwen proposes spans only. Every accepted value is still validated against this utterance.
    extractor=getattr(bridge,'_wx_context_extract',None)
    unresolved=[k for k in ('count','vehicle','pickup','destination') if not updates.get(k) and not s.get(k)]
    if callable(extractor) and unresolved and len(raw.split())>=5 and normalized not in POSITIVE|NEGATIVE:
        try:extracted=extractor(raw,s) or {}
        except Exception:extracted={}
        for slot in ('pickup','destination'):
            value=extracted.get(slot)
            if slot not in updates and isinstance(value,str) and reply_normalized(value) and reply_normalized(value) in normalized:
                cleaned=clean_spoken_place(bridge,value)
                if cleaned:accept(slot,cleaned,value,'qwen_validated_span',0.85)
        value=extracted.get('passengers_text')
        if 'count' not in updates and isinstance(value,str) and reply_normalized(value) in normalized:
            parser=getattr(bridge,'number',None);count=parser(value) if callable(parser) else words.get(value.casefold())
            if count and 1<=int(count)<=20:accept('count',int(count),value,'qwen_validated_span',0.85)
    changed=[]
    for slot,value in updates.items():
        if s.get(slot)!=value:
            s[slot]=value;changed.append(slot)
            if slot in ('pickup','destination'):s[slot+'_geo']=None
    s.setdefault('_wx_slot_evidence',{}).update(evidence)
    if raw:s['_wx_turns']=(s.get('_wx_turns',[])+[{'input':raw,'updates':updates}])[-30:]
    return {'updates':updates,'changed':changed,'evidence':evidence,'ambiguities':copy.deepcopy(ambiguities)}


def time_prompt(lang, reason):
    messages = {
        "clarify_date": ("What day should I book: today, tomorrow, or another date?", "எந்த தேதிக்கு முன்பதிவு செய்ய வேண்டும்? இன்று, நாளை அல்லது வேறு தேதியைச் சொல்லுங்கள்.", "Endha date-ku book pannanum? Innaiku, naalaiku illa vera date sollunga."),
        "clarify_clock": ("What pickup time would you like?", "எத்தனை மணிக்கு வாகனம் வேண்டும்?", "Ethana manikku vehicle venum?"),
        "clarify_period": ("Is that time in the morning, afternoon, evening or at night?", "அந்த நேரம் காலையா, மதியமா, மாலையா அல்லது இரவா?", "Andha time kaalaiya, madhiyama, maalaiya illa irava?"),
        "past_datetime": ("That pickup time has already passed. Please tell me a later time, or a different date.", "நீங்கள் சொன்ன நேரம் ஏற்கனவே கடந்துவிட்டது. அதற்குப் பிந்தைய நேரத்தை அல்லது வேறு தேதியைச் சொல்லுங்கள்.", "Neenga sonna time already kadandhuduchu. Later time illa vera date sollunga."),
        "invalid_datetime": ("I could not read that date or time. Please say it again.", "அந்த தேதி அல்லது நேரம் புரியவில்லை. மீண்டும் சொல்லுங்கள்.", "Andha date illa time puriyala. Thirumba sollunga.")}
    return localized(lang,*messages.get(reason,messages["invalid_datetime"]))


def prepare_turn(bridge,weather,state,text,now=None):
    """Never books. Forecast consent precedes a separate route/fare and final review."""
    now=(now or datetime.now(TZ)).astimezone(TZ)
    before={k:copy.deepcopy(state.get(k)) for k in CORE_FIELDS}
    if str(text).strip():collect_details(bridge,state,text)
    try:pickup,time_error=update_time_memory(state,text,now)
    except GuardError as exc:
        pickup,time_error=None,str(exc);state['_wx_time_error']=time_error
    changed=any(before[k]!=state.get(k) for k in CORE_FIELDS)
    if changed:state['fare']=None
    if state.get('_wx_slot_conflicts',{}).get('vehicle'):
        state['stage']='vehicle'
        return state,localized(state['lang'],'Which one vehicle would you like?', 'எந்த ஒரு வாகனம் வேண்டும்?', 'Endha oru vandi venum?')
    for slot in ('count','vehicle','pickup','destination'):
        if not state.get(slot):state['stage']=slot;return state,bridge.say(state,slot)
    if state['vehicle'] not in CAPACITY or not 1<=int(state['count'])<=6 or int(state['count'])>CAPACITY[state['vehicle']]:
        state['stage']='vehicle' if 1<=int(state['count'])<=6 else 'count'
        choices=[v for v,c in CAPACITY.items() if c>=int(state['count'])]
        return state,localized(state['lang'],
            'Please choose a vehicle with enough seats: '+', '.join(choices)+'.' if choices else 'Please give a passenger count from 1 to 6 for one vehicle.',
            'பயணிகளுக்கு ஏற்ற வாகனத்தைத் தேர்ந்தெடுக்கவும்: '+', '.join(VEHICLES_TA[v] for v in choices)+'.' if choices else 'ஒரு வாகனத்திற்கு 1 முதல் 6 வரை பயணிகள் எண்ணிக்கையைச் சொல்லுங்கள்.',
            'Payanigalukku etra vandiyai therndhedukkavum: '+', '.join(VEHICLES_ROMAN[v] for v in choices)+'.' if choices else 'Oru vandikku 1 mudhal 6 varai payanigal ennikkaiyai sollunga.')
    if time_error:
        state['stage']='time';state.pop('pickup_at',None);state.pop('_wx_weather_consent',None)
        return state,time_prompt(state['lang'],time_error)
    state['pickup_at']=pickup.isoformat()
    for slot in ('pickup','destination'):
        if not valid_geo(state.get(slot+'_geo')):
            try:geo=bridge.geocode(state[slot])
            except Exception:geo=None
            if valid_geo(geo):state[slot+'_geo']=geo
    scope=digest({k:state.get(k) for k in ('pickup','destination','pickup_at','pickup_geo','destination_geo')})
    expired_weather=bool((state.get('weather') or {}).get('fetched_at') and time.time()-state['weather']['fetched_at']>getattr(weather,'ttl',900))
    if state.get('_wx_forecast_scope')!=scope or not state.get('weather') or expired_weather:
        state['weather']=weather.forecast([state['pickup_geo'],state['destination_geo']],pickup,now=now) if all(valid_geo(state.get(k+'_geo')) for k in ('pickup','destination')) else {'status':'unavailable','source':'Open-Meteo','reason':'location_coordinates_unavailable'}
        state['_wx_forecast_scope']=scope
    if not weather_consented(state):
        state.pop('_wx_weather_consent',None);state['stage']='weather_advisory'
        return state,advisory(state)+'\n'+weather_question(state['lang'])
    if not state.get('fare') or not all(valid_geo(state.get(k+'_geo')) for k in ('pickup','destination')):
        route_state=copy.deepcopy(state)
        try:fare=bridge.road_fare(route_state)
        except Exception:fare=None
        try:valid=bool(fare and all(math.isfinite(float(fare[k])) and float(fare[k])>=0 for k in ('km','fare')))
        except (KeyError,ValueError,TypeError):valid=False
        if valid:
            for slot in ('pickup','destination'):
                if valid_geo(route_state.get(slot+'_geo')):state[slot+'_geo']=route_state[slot+'_geo']
        if not valid or not all(valid_geo(state.get(k+'_geo')) for k in ('pickup','destination')):
            state['stage']='route_unavailable';state['fare']=None
            return state,localized(state['lang'],
                'Distance or fare estimation is temporarily unavailable. Your booking details are retained. Say retry, change a detail, or cancel.',
                'தூரம் அல்லது கட்டண மதிப்பீடு தற்காலிகமாகக் கிடைக்கவில்லை. உங்கள் பயண விவரங்கள் உள்ளன. மீண்டும் முயற்சிக்கச் சொல்லுங்கள், விவரங்களை மாற்றுங்கள் அல்லது ரத்து செய்யுங்கள்.',
                'Dhooram alladhu kattanam madhippeedu tharkaaligamaaga kidaikkavillai. Unga payana vivarangal irukku. Meendum muyarchikka sollunga, vivarangalai maathunga alladhu raththu seiyyunga.')
        state['fare']=fare
        if not weather_consented(state):
            return prepare_turn(bridge,weather,state,'',now=now)
    state['stage']='confirm'
    return state,summary_text(bridge,state)


def install_bridge(bridge, db_path, weather=None, _route_wrapper=None):
    """Replace only book-mode sockets; the original cancellation socket is retained."""
    if _route_wrapper is None:
        from starlette.routing import websocket_session
        _route_wrapper = websocket_session
    weather = weather or WeatherClient()
    install_numeric_normalizer(bridge)
    db = GuardDB(db_path)
    db.setup()
    if not hasattr(bridge, "_wx_original_socket"):
        bridge._wx_original_socket = next(r.endpoint for r in bridge.app.routes if getattr(r, "path", "") == "/browser-call")

    async def endpoint(ws):
        if ws.query_params.get("mode", "book") == "cancel":
            return await bridge._wx_original_socket(ws)
        if ws.headers.get("origin", "").rstrip("/") != bridge.PUBLIC_URL:
            await ws.close(code=1008)
            return
        lang = ws.query_params.get("language", "Tamil")
        if lang not in bridge.MESSAGES:
            await ws.close(code=1008)
            return
        await ws.accept()
        tasks, sid, state, epoch = set(), None, None, 0
        pending_action = None
        language_token = bridge.CURRENT_LANGUAGE.set(lang)

        async def send(payload):
            await ws.send_json(payload)

        async def emit(text, e, nonce=None, done=False):
            if not db.current(sid, e) and not done:
                return
            pause_ms=max(0,min(1000,int(getattr(bridge,"_wx_pause_ms",220))))
            pieces=speech_segments(text) if pause_ms else [text]
            for i,piece in enumerate(pieces):
                if not done and not db.current(sid,e):return
                payload=await asyncio.to_thread(tts_reply,bridge,piece)
                if not done and not db.current(sid,e):return
                await send({"event":"reply" if i==0 else "speech_chunk","text":display_reply(state,text) if i==0 else "",
                    "payload":payload,"epoch":e,"stage":state["stage"],"summary_nonce":nonce,
                    "summary_kind":"weather" if state.get('stage')=='weather_advisory' else 'final',"done":done,
                    "streaming":True,"chunk_index":i,"chunk_count":len(pieces),"pause_after_ms":pause_ms if i<len(pieces)-1 else 0,
                    "version":db.row(sid)["version"]})

        async def process(msg, e, prior):
            nonlocal state, pending_action
            try:
                if msg["event"] == "text":
                    text = str(msg.get("text", "")).strip()[:800]
                else:
                    def transcribe():
                        import av
                        import numpy as np
                        import librosa
                        encoded = msg.get("payload", "")
                        if len(encoded) > 3_000_000:
                            raise GuardError("Audio exceeds limit")
                        data = base64.b64decode(encoded, validate=True)
                        frames = []
                        with av.open(io.BytesIO(data)) as container:
                            resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
                            for frame in container.decode(audio=0):
                                for mono in resampler.resample(frame):
                                    frames.append(mono.to_ndarray().astype(np.float32).reshape(-1))
                            for mono in resampler.resample(None):
                                frames.append(mono.to_ndarray().astype(np.float32).reshape(-1))
                        if not frames:
                            raise GuardError("No audio received")
                        a = np.concatenate(frames)
                        if len(a) / 16000 > 28:
                            raise GuardError("Please speak for less than 28 seconds")
                        return bridge.stt_sarvam(a, lang)[0]
                    text = await asyncio.to_thread(transcribe)
                if not db.current(sid, e):
                    return
                await send({"event": "heard", "text": text, "epoch": e})
                positive = reply_normalized(text) in POSITIVE
                if prior.get('stage')=='weather_advisory' and positive:
                    try:
                        prior=db.accept_weather(sid,e,msg.get('summary_nonce'),prior)
                    except GuardError:
                        if not db.current(sid,e):return
                        state=prior;db.stash(sid,e,state)
                        nonce=db.summary(sid,e,state)
                        await emit(advisory(state)+'\n'+weather_question(lang),e,nonce)
                        return
                    state=copy.deepcopy(prior)
                    refreshed,answer=await asyncio.to_thread(prepare_turn,bridge,weather,prior,'')
                    if not db.current(sid,e):return
                    state=refreshed;db.stash(sid,e,state)
                    nonce=db.summary(sid,e,state) if state['stage'] in ('weather_advisory','confirm') else None
                    await emit(answer,e,nonce)
                    return
                if prior.get("stage") == "confirm" and positive:
                    try:
                        token = db.permit(sid, e, msg.get("summary_nonce"), prior)
                    except GuardError:
                        prior["stage"] = "fare"
                        refreshed, answer = await asyncio.to_thread(prepare_turn, bridge, weather, prior, '')
                        if not db.current(sid, e):
                            return
                        db.stash(sid, e, refreshed)
                        state = refreshed
                        nonce = db.summary(sid, e, state) if state["stage"] in ('weather_advisory','confirm') else None
                        await emit(answer, e, nonce)
                        return
                    if not db.current(sid, e):
                        return
                    pending_action = secrets.token_hex(16)
                    state["stage"] = "booking_pending"
                    await send({"event": "action", "type": "weather_book", "token": token,
                                "request_id": pending_action, "epoch": e})
                    return
                if reply_normalized(text) in {'cancel','cancel booking','ரத்து','ரத்து செய்','ரத்து செய்யுங்கள்','cancel pannunga','raththu seiyyunga'}:
                    state["stage"] = "done"
                    await emit(localized(lang,'The booking request was cancelled. No booking was created.',
                        'முன்பதிவு கோரிக்கை ரத்து செய்யப்பட்டது. முன்பதிவு எதுவும் உருவாக்கப்படவில்லை.',
                        'Munpadhivu korikkai raththu seiyyappattadhu. Munpadhivu edhuvum uruvaakkappadavillai.'),e,done=True)
                    return
                if prior.get('stage') in ('weather_advisory','confirm') and reply_normalized(text) in NEGATIVE:
                    state=copy.deepcopy(prior);state['stage']='change_request';state.pop('_wx_weather_consent',None)
                    db.stash(sid,e,state)
                    await emit(localized(lang,'What would you like to change? You can also say cancel.',
                        'எந்த விவரத்தை மாற்ற விரும்புகிறீர்கள்? ரத்து செய்யவும் சொல்லலாம்.',
                        'Endha vivarathai maatra virumbureenga? Raththu seiyyavum sollalaam.'),e)
                    return
                if not text:
                    raise GuardError("Please repeat your request")
                next_state, answer = await asyncio.to_thread(prepare_turn, bridge, weather, prior, text)
                if not db.current(sid, e):
                    return
                db.stash(sid, e, next_state)
                state = next_state
                nonce = db.summary(sid, e, state) if state["stage"] in ('weather_advisory','confirm') else None
                await emit(answer, e, nonce)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if db.current(sid, e):
                    await send({"event": "error", "message": str(exc)[:180], "epoch": e})

        try:
            start = await asyncio.wait_for(ws.receive_json(), timeout=20)
            if start.get("event") != "start":
                raise GuardError("Start the call from the updated logged-in dashboard")
            bound=db.bind(start.get("call_id"), start.get("bind_token"))
            sid = start["call_id"]
            saved=json.loads(bound.get('state') or '{}')
            state = saved if saved else bridge.new_session(lang, "book")
            state.update(lang=lang,mode='book',_wx_mode='voice')
            epoch = db.begin(sid)
            db.stash(sid, epoch, state)
            await send({"event": "ready", "epoch": epoch})
            async def greet(e):
                try:
                    await emit(bridge.say(state, "hello"), e)
                except Exception:
                    await send({"event": "error", "message": "Speech generation failed. Check the original TTS service.", "epoch": e})
            greeting = asyncio.create_task(greet(epoch))
            tasks.add(greeting)
            greeting.add_done_callback(tasks.discard)
            while True:
                msg = await ws.receive_json()
                kind = msg.get("event")
                if kind == "playback_ended":
                    db.played(sid, msg.get("epoch"), msg.get("summary_nonce"))
                elif kind == "summary_read":
                    # Explicit accessible alternative when audio playback is unavailable.
                    # Weather is spoken-only, so a click cannot claim to have read it.
                    db.played(sid, msg.get("epoch"), msg.get("summary_nonce"),explicit_read=True)
                elif kind == "interrupt":
                    try:
                        epoch = db.begin(sid, interrupt=True)
                        # Preserve the phase and all slots until the correction is parsed.
                        db.stash(sid,epoch,state)
                        await send({"event": "interrupted", "epoch": epoch})
                    except GuardError as exc:
                        await send({"event": "error", "message": str(exc), "epoch": epoch})
                elif kind in ("audio", "text"):
                    if pending_action:
                        await send({"event":"error","message":"The booking is still being saved. Please wait for its result.","epoch":epoch})
                        continue
                    try:
                        epoch = db.begin(sid)
                    except GuardError as exc:
                        await send({"event": "error", "message": str(exc), "epoch": epoch})
                        continue
                    await send({"event": "processing", "epoch": epoch})
                    task = asyncio.create_task(process(msg, epoch, copy.deepcopy(state)))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                elif kind == "result" and msg.get("request_id") == pending_action:
                    row = db.row(sid)
                    if row["ride_id"]:
                        pending_action = None
                        state["stage"] = "done"
                        await emit(completion_message(lang,row["ride_id"]), row["epoch"], done=True)
                    else:
                        pending_action = None
                        # Verify storage before claiming success, including when
                        # the browser reports a timeout or an HTTP error.
                        refreshed,answer=await asyncio.to_thread(prepare_turn,bridge,weather,copy.deepcopy(state),'')
                        if not db.current(sid,epoch):continue
                        state=refreshed;db.stash(sid,epoch,state)
                        reason = str(msg.get("error") or "The booking was not saved. Please try confirming again.")[:180]
                        await send({"event":"booking_error","message":reason,"epoch":epoch})
                        nonce = db.summary(sid,epoch,state) if state["stage"] in ('weather_advisory','confirm') else None
                        prefix = localized(lang,"The booking was not saved. ","முன்பதிவு சேமிக்கப்படவில்லை. ","Booking save aagala. ")
                        await emit(prefix+answer,epoch,nonce)
        except Exception as exc:
            try:
                await send({"event": "error", "message": str(exc)[:180], "fatal": True})
            except Exception:
                pass
        finally:
            if sid:
                try:
                    db.begin(sid, interrupt=True)
                except GuardError:
                    pass
            for task in list(tasks):
                task.cancel()
            await asyncio.gather(*list(tasks), return_exceptions=True)
            bridge.CURRENT_LANGUAGE.reset(language_token)

    route = next(r for r in bridge.app.routes if getattr(r, "path", "") == "/browser-call")
    route.endpoint, route.app = endpoint, _route_wrapper(endpoint)
    bridge._wx_weather, bridge._wx_db, bridge._wx_endpoint = weather, db, endpoint
    return {"version": VERSION, "weather": "Open-Meteo", "guard": "installed", "interrupt": "browser control"}






# V04_DIALOGUE_HELPERS
TA_DAY_WORDS = (
    '', 'முதல்', 'இரண்டாம்', 'மூன்றாம்', 'நான்காம்', 'ஐந்தாம்', 'ஆறாம்', 'ஏழாம்', 'எட்டாம்',
    'ஒன்பதாம்', 'பத்தாம்', 'பதினொன்றாம்', 'பன்னிரண்டாம்', 'பதின்மூன்றாம்', 'பதினான்காம்',
    'பதினைந்தாம்', 'பதினாறாம்', 'பதினேழாம்', 'பதினெட்டாம்', 'பத்தொன்பதாம்', 'இருபதாம்',
    'இருபத்தொன்றாம்', 'இருபத்திரண்டாம்', 'இருபத்துமூன்றாம்', 'இருபத்துநான்காம்',
    'இருபத்தைந்தாம்', 'இருபத்தாறாம்', 'இருபத்தேழாம்', 'இருபத்தெட்டாம்',
    'இருபத்தொன்பதாம்', 'முப்பதாம்', 'முப்பத்தொன்றாம்')

def numeric_text(value, decimal_places=1, grouped=False):
    """Canonical numerical entities stay as digits at the TTS adapter boundary."""
    number = float(value)
    if not math.isfinite(number):
        raise GuardError('Invalid numerical value')
    text = f'{number:,.{decimal_places}f}' if grouped else f'{number:.{decimal_places}f}'
    return text.rstrip('0').rstrip('.') if '.' in text else text

def number_lexicon(limit=59):
    result = {str(n): n for n in range(limit + 1)}
    for n in range(limit + 1):
        for lang in ('English', 'Tamil', 'Tanglish'):
            result[number_words(n, lang).casefold()] = n
    result.update({'ஒரு':1, 'ஒன்னு':1,'ரெண்டு':2,'மூணு':3,'நாலு':4,'அஞ்சு':5, 'onnu':1, 'oru':1, 'rendu':2, 'moonru':3, 'moonu':3, 'naalu':4,
                   'naangu':4, 'anju':5, 'aaru':6, 'yelu':7, 'ezhu':7, 'ettu':8,
                   'onbadhu':9, 'pathu':10, 'pannirandu':12})
    return result

def weather_question(lang):
    return localized(lang,'Would you like to continue?', 'முன்பதிவைத் தொடர விரும்புகிறீர்களா?', 'Munpadhivai thodaralaama?')

def weather_consent_scope(state):
    return digest({k:state.get(k) for k in ('pickup','destination','pickup_at','pickup_geo','destination_geo','weather')})

def weather_consented(state):
    consent=state.get('_wx_weather_consent') or {}
    return consent.get('scope')==weather_consent_scope(state) and bool(consent.get('accepted_at'))

def valid_geo(value):
    try:return isinstance(value,dict) and math.isfinite(float(value['lat'])) and math.isfinite(float(value['lng'])) and abs(float(value['lat']))<=90 and abs(float(value['lng']))<=180
    except (KeyError,ValueError,TypeError):return False

def tts_reply(bridge,text):
    """Bypass old outer decimal/number expansion; retain the original DhVaani adapter and its internal normalizer."""
    adapter=getattr(bridge,'TTS',None)
    if not callable(getattr(adapter,'synthesize',None)):
        return bridge.speak(text)  # isolated fixtures, or an existing custom speech backend
    language=bridge.CURRENT_LANGUAGE.get()
    group='TAMIL' if language=='Tamil' else 'TANGLISH' if language=='Tanglish' else 'ENGLISH'
    lock=getattr(bridge,'LOCK',None)
    token=NUMERIC_LANGUAGE.set(language)
    try:
        if lock is None:data=adapter.synthesize(str(text),group)
        else:
            with lock:data=adapter.synthesize(str(text),group)
    finally:NUMERIC_LANGUAGE.reset(token)
    return base64.b64encode(data).decode()

def pronunciation_number(value,lang):
    if lang=='English':return number_words(value,'English')
    n=int(value)
    if n<0:return 'மைனஸ் '+pronunciation_number(-n,lang)
    if n<10000:return number_words(n,'Tamil')
    for scale,full,joined in ((10000000,'கோடி','கோடியே'),(100000,'லட்சம்','லட்சத்து'),(1000,'ஆயிரம்','ஆயிரத்து')):
        if n>=scale:return pronunciation_number(n//scale,lang)+' '+(full if not n%scale else joined+' '+pronunciation_number(n%scale,lang))
    return str(n)

def speech_numeric_normalize(original,text,lang):
    """Acoustic-only verbalization; raw adapter input, transcript and booking values retain digits."""
    text=str(text);protected=[]
    identifiers=[m.span(1) for m in re.finditer(r'(?:booking\s*(?:id|number)|முன்பதிவு\s*எண்|munpadhivu\s*enn|\botp\b|ஓடிபி)\s*[:#-]?\s*(\d+)',text,re.I)]
    def word(n):return pronunciation_number(int(n),lang)
    def decimal(number):
        whole,_,fraction=number.replace(',','').partition('.')
        return word(whole)+((' point ' if lang=='English' else ' புள்ளி ')+' '.join(word(d) for d in fraction) if fraction else '')
    def replace(match):
        raw=match[0].strip()
        if any(a<=match.start() and match.end()<=b for a,b in identifiers):
            spoken=' '.join(word(d) for d in raw)
        elif raw.startswith('₹'):
            value=raw[1:].strip();whole,_,fraction=value.replace(',','').partition('.')
            spoken=word(whole)+(' rupees' if lang=='English' else ' ரூபாய்')
            if fraction and int(fraction[:2].ljust(2,'0')):
                spoken+=' '+word(fraction[:2].ljust(2,'0'))+(' paise' if lang=='English' else ' பைசா')
        elif raw.endswith('%'):
            spoken=decimal(raw[:-1].strip())+(' percent' if lang=='English' else ' சதவீதம்')
        elif ':' in raw:
            clock=re.match(r'(\d{1,2}):(\d{2})(?:\s*(AM|PM))?',raw,re.I)
            hour,minute=int(clock[1]),int(clock[2])
            if lang=='English':spoken=word(hour)+(' '+('oh ' if minute<10 else '')+word(minute) if minute else '')+(' '+clock[3] if clock[3] else '')
            else:spoken=word(hour)+' மணி'+(' '+word(minute)+' நிமிடம்' if minute else '')
        else:spoken=decimal(raw)
        marker=chr(0xE000+len(protected));protected.append((marker,original(spoken)));return marker
    masked=re.sub(r'₹\s*\d[\d,]*(?:\.\d+)?|\d{1,2}:\d{2}(?:\s*(?:AM|PM))?|\d+(?:,\d{3})*(?:\.\d+)?\s*%|\d+(?:,\d{3})*(?:\.\d+)?',replace,text,flags=re.I)
    result=original(masked)
    for marker,spoken in protected:result=result.replace(marker,spoken)
    if any(marker in result for marker,_ in protected):raise GuardError('Numerical speech normalization failed')
    return result

def install_numeric_normalizer(bridge):
    adapter=getattr(bridge,'TTS',None);namespace=getattr(adapter,'ns',None)
    if not isinstance(namespace,dict):return False
    targets=[namespace]
    prepare=namespace.get('prepare_movio_request');function_globals=getattr(prepare,'__globals__',None)
    if isinstance(function_globals,dict) and function_globals is not namespace:targets.append(function_globals)
    for target in targets:
        existing=target.get('normalize_taxi_text')
        if not callable(existing):continue
        original=getattr(existing,'_wx_original_normalizer',existing)
        def normalize(text,_original=original):
            language=NUMERIC_LANGUAGE.get()
            return speech_numeric_normalize(_original,text,language) if language else _original(text)
        normalize._wx_original_normalizer=original
        normalize._wx_scope='weather voice acoustic normalization only; original benchmark calls unchanged'
        target['normalize_taxi_text']=normalize
    return True

# MOVIO_OPTIONAL_WEATHER_BOOTSTRAP_V1
import importlib.util as _mo_import
import sys as _mo_sys
_mo_file=Path(__file__).with_name('movio_optional_weather.py')
_mo_spec=_mo_import.spec_from_file_location('movio_optional_weather',_mo_file)
_mo_module=_mo_import.module_from_spec(_mo_spec)
_mo_sys.modules[_mo_spec.name]=_mo_module
exec(compile(_mo_file.read_text(encoding='utf-8'),str(_mo_file),'exec'),_mo_module.__dict__)
_mo_module.install_namespace(globals())
# MOVIO_OPTIONAL_WEATHER_BOOTSTRAP_END_V1

# MOVIO_CONFIRMATION_FLOW_BOOTSTRAP_V1
import importlib.util as _cf_import
import sys as _cf_sys
_cf_file=Path(__file__).with_name('movio_confirmation_flow.py')
_cf_spec=_cf_import.spec_from_file_location('movio_confirmation_flow',_cf_file)
_cf_module=_cf_import.module_from_spec(_cf_spec)
_cf_sys.modules[_cf_spec.name]=_cf_module
exec(compile(_cf_file.read_text(encoding='utf-8'),str(_cf_file),'exec'),_cf_module.__dict__)
_cf_module.install_namespace(globals())
# MOVIO_CONFIRMATION_FLOW_BOOTSTRAP_END_V1

# MOVIO_TIME_ROUTE_BOOTSTRAP_V1
import importlib.util as _tr_import
import sys as _tr_sys
_tr_file=Path(__file__).with_name('movio_time_route.py')
_tr_spec=_tr_import.spec_from_file_location('movio_time_route',_tr_file)
_tr_module=_tr_import.module_from_spec(_tr_spec)
_tr_sys.modules[_tr_spec.name]=_tr_module
exec(compile(_tr_file.read_text(encoding='utf-8'),str(_tr_file),'exec'),_tr_module.__dict__)
_tr_module.install_namespace(globals())
# MOVIO_TIME_ROUTE_BOOTSTRAP_END_V1

# MOVIO_REQUIRED_WEATHER_BOOTSTRAP_V1
import importlib.util as _rw_import
import sys as _rw_sys
_rw_file=Path(__file__).with_name('movio_required_weather.py')
_rw_spec=_rw_import.spec_from_file_location('movio_required_weather',_rw_file)
_rw_module=_rw_import.module_from_spec(_rw_spec)
_rw_sys.modules[_rw_spec.name]=_rw_module
exec(compile(_rw_file.read_text(encoding='utf-8'),str(_rw_file),'exec'),_rw_module.__dict__)
_rw_module.install_namespace(globals())
# MOVIO_REQUIRED_WEATHER_BOOTSTRAP_END_V1

# MOVIO_BOOKING_RELIABILITY_BOOTSTRAP_V1
import importlib.util as _br_import
_br_path=Path(__file__).with_name('movio_booking_reliability.py')
_br_spec=_br_import.spec_from_file_location('movio_booking_reliability',_br_path)
_br_module=_br_import.module_from_spec(_br_spec)
exec(compile(_br_path.read_text(encoding='utf-8'),str(_br_path),'exec'),_br_module.__dict__)
_br_module.install_namespace(globals(),Path(__file__).resolve().parent.parent)
# MOVIO_BOOKING_RELIABILITY_BOOTSTRAP_END_V1

# MOVIO_FRIENDLY_WEATHER_BOOTSTRAP_V1
import importlib.util as _fw_import
_fw_path=Path(__file__).with_name('movio_friendly_weather.py')
_fw_spec=_fw_import.spec_from_file_location('movio_friendly_weather',_fw_path)
_fw_module=_fw_import.module_from_spec(_fw_spec)
exec(compile(_fw_path.read_text(encoding='utf-8'),str(_fw_path),'exec'),_fw_module.__dict__)
_fw_module.install_namespace(globals(),Path(__file__).resolve().parent.parent)
# MOVIO_FRIENDLY_WEATHER_BOOTSTRAP_END_V1
