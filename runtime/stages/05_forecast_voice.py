import re as _re

_MOVIO_LETTERS = {
    'A': 'ஏ', 'B': 'பி', 'C': 'சி', 'D': 'டி', 'E': 'ஈ', 'F': 'எஃப்', 'G': 'ஜி', 'H': 'ஹெச்',
    'I': 'ஐ', 'J': 'ஜே', 'K': 'கே', 'L': 'எல்', 'M': 'எம்', 'N': 'என்', 'O': 'ஓ', 'P': 'பி',
    'Q': 'கியூ', 'R': 'ஆர்', 'S': 'எஸ்', 'T': 'டி', 'U': 'யூ', 'V': 'வி', 'W': 'டபிள்யூ',
    'X': 'எக்ஸ்', 'Y': 'வை', 'Z': 'ஸெட்',
}

_MOVIO_CAPS_WORDS = {'AUTO', 'MINI', 'BIKE', 'TAXI', 'SEDAN', 'RAIN', 'HEAT', 'NOTE', 'HIGH',
                     'LOW', 'YES', 'NO', 'OK', 'AND', 'THE', 'FOR'}

_MOVIO_WORDS = (  # spoken with Tamil pronunciation in English, Tanglish and Tamil
    (r'(?<![A-Za-z])temperatures(?![A-Za-z])', 'டெம்பரேச்சர்ஸ்'),
    (r'(?<![A-Za-z])temperature(?![A-Za-z])', 'டெம்பரேச்சர்'),
    (r'(?<![A-Za-z])celsius(?![A-Za-z])', 'செல்சியஸ்'),
    (r'(?<![A-Za-z])autos(?![A-Za-z])', 'ஆட்டோக்கள்'),
    (r'(?<![A-Za-z])auto(?![A-Za-z])', 'ஆட்டோ'),
)

def movio_spell_acronym(letters):
    """ICF -> ஐசிஎஃப்: letter names joined into ONE word, so it is read together."""
    return ''.join(_MOVIO_LETTERS[c] for c in letters if c in _MOVIO_LETTERS)

def movio_prepare_forecast_text(text, language, vocab=None):
    value = _re.sub(r'\s+', ' ', str(text)).strip()
    if language == 'Tamil':   # spoken wording of the opening phrase
        value = _re.sub(
            r'^(?:ஒரு\s+சின்ன\s+வானிலை\s+தகவல்|ஒரு\s+வானிலை\s+அறிவிப்பு|ஒரு\s+அறிவிப்பு)(?![\w\u0B80-\u0BFF])\s*[:;.!?।]?\s*',
            'ஒரு அறிவிப்பு. ',
            value
        )
    elif language == 'Tanglish':
        # These boundaries affect the speech copy only, never the transcript.
        value = _re.sub(
            r'^oru\s+weather\s+update(?![A-Za-z])\s*[:;.!?।]?\s*',
            'Oru weather update. ', value, flags=_re.I
        )
        value = _re.sub(
            r'(?<![A-Za-z])(umbrella\s+eduthukkondu)(?![A-Za-z])\s*[.,;:!?।]?\s*',
            lambda match: match.group(1) + '; ', value, flags=_re.I
        )
        # Phonetic spelling of English "ninety", not a translation of the value.
        # Match only the complete 90% / 90 percent entity; leave 190%, 9.0%,
        # temperatures, times, dates and identifiers unchanged.
        value = _re.sub(
            r'(?<![\w.])90\s*(?:%|percent(?![A-Za-z]))',
            'நைன்டி percent', value, flags=_re.I
        )
    # 28.6°C / 28.6 °C / "degrees Celsius" -> Tamil pronunciation of Celsius
    value = _re.sub(r'\s*°\s*C(?![A-Za-z])',
                    ' டிகிரி செல்சியஸ்' if language == 'Tamil' else ' degrees செல்சியஸ்', value)
    for pattern, spoken in _MOVIO_WORDS:
        value = _re.sub(pattern, spoken, value, flags=_re.I)

    def dotted(match):
        end = match.end()
        tail = value[end:end + 3]
        keep_stop = end >= len(value) or _re.match(r'\s+[A-Z஀-௿]', tail + ' ')
        return movio_spell_acronym(_re.sub(r'[^A-Z]', '', match.group(0))) + ('.' if keep_stop else '')
    value = _re.sub(r'(?<![A-Za-z])(?:[A-Z]\.){2,6}', dotted, value)
    value = _re.sub(r'(?<![A-Za-z0-9])[A-Z]{2,6}(?![A-Za-z0-9])',
                    lambda m: m.group(0) if m.group(0) in _MOVIO_CAPS_WORDS else movio_spell_acronym(m.group(0)),
                    value)
    if language == 'Tanglish':
        value = movio_tanglish_script(value, vocab)
    else:   # English and Tamil: same long-ee spelling so it is never read as 'mani'
        value = _re.sub(r'(?<![A-Za-z])mini(?![A-Za-z])', 'மினீ', value, flags=_re.I)
    # A colon inside a sentence must not break it (time such as 4:02 is kept).
    value = _re.sub(r'(?<!\d):|:(?!\d)', ' ', value)
    return _re.sub(r'\s+', ' ', value).strip()

def movio_forecast_parts(text, language, vocab=None):
    """[(sentence, pause_seconds_after)]: pause after every full stop and semicolon."""
    prepared = movio_prepare_forecast_text(text, language, vocab)
    parts = []
    for piece in _re.split(r'(?<=[.;!?।])\s+', prepared):
        piece = piece.strip()
        if not piece:
            continue
        stop = piece[-1]
        body = piece.rstrip('.;!?। ').strip()
        if not _re.search(r'[A-Za-z0-9஀-௿]', body):
            continue
        parts.append((body + ('?' if stop == '?' else '.'), 0.5 if stop == ';' else 0.7))
    if parts:
        parts[-1] = (parts[-1][0], 0.0)
    return parts

def movio_join_wavs(wav_pauses):
    """Join WAV byte strings into one WAV, inserting the given silence after each."""
    import io, wave
    out = io.BytesIO(); writer = None; params = None
    for raw, pause in wav_pauses:
        with wave.open(io.BytesIO(raw), 'rb') as part:
            current = (part.getnchannels(), part.getsampwidth(), part.getframerate())
            frames = part.readframes(part.getnframes())
        if writer is None:
            params = current
            writer = wave.open(out, 'wb')
            writer.setnchannels(current[0]); writer.setsampwidth(current[1]); writer.setframerate(current[2])
        elif current != params:
            raise ValueError('Speech chunks have different audio formats')
        writer.writeframes(frames)
        if pause > 0:
            writer.writeframes(b'\x00' * (int(params[2] * pause) * params[0] * params[1]))
    if writer is None:
        raise ValueError('No speech was generated')
    writer.close()
    return out.getvalue()

_TG_ENGLISH = set(['a', 'ai', 'am', 'an', 'and', 'approximate', 'april', 'are', 'around', 'at', 'august', 'auto', 'bags', 'be', 'belongings', 'bike', 'billion', 'book', 'booking', 'by', 'can', 'cancel', 'cancellation', 'car', 'care', 'celsius', 'chance', 'change', 'check', 'cloudy', 'comfortable', 'confirm', 'confirmation', 'consider', 'continue', 'correct', 'cover', 'covered', 'crore', 'crores', 'december', 'degree', 'degrees', 'destination', 'detail', 'details', 'distance', 'driver', 'drop', 'eight', 'eighteen', 'eighty', 'eleven', 'estimated', 'evening', 'existing', 'fare', 'february', 'fifteen', 'fifty', 'five', 'for', 'forecast', 'forty', 'four', 'fourteen', 'friday', 'from', 'have', 'heat', 'heavy', 'help', 'hundred', 'id', 'in', 'is', 'it', 'january', 'journey', 'july', 'june', 'keep', 'kilometer', 'kilometers', 'kilometres', 'lakh', 'lakhs', 'map', 'march', 'may', 'me', 'million', 'mini', 'monday', 'morning', 'my', 'night', 'nine', 'nineteen', 'ninety', 'no', 'november', 'number', 'october', 'of', 'oh', 'on', 'one', 'open', 'otp', 'our', 'passenger', 'passengers', 'pickup', 'place', 'pleasant', 'please', 'pm', 'point', 'prepare', 'protection', 'rain', 'record', 'request', 'retain', 'retry', 'ride', 'road', 'route', 'rupee', 'rupees', 'same', 'saturday', 'save', 'saved', 'screen', 'sedan', 'select', 'selected', 'september', 'service', 'seven', 'seventeen', 'seventy', 'six', 'sixteen', 'sixty', 'strong', 'sun', 'sunday', 'sunny', 'suv', 'switch', 'taxi', 'temperature', 'ten', 'thank', 'thanks', 'the', 'thirteen', 'thirty', 'thousand', 'three', 'thunderstorm', 'thunderstorms', 'thursday', 'time', 'to', 'today', 'tomorrow', 'travel', 'tuesday', 'twelve', 'twenty', 'two', 'umbrella', 'update', 'vehicle', 'verify', 'warnings', 'weather', 'wednesday', 'welcome', 'will', 'wind', 'windy', 'with', 'wonderful', 'yes', 'you', 'your', 'zero']) | set('''quick possible about should provides provide carry protect side drop off dropoff
selected pickup ride passengers passenger vehicle mini auto sedan suv bike car cover umbrella bags bag
weather update rain chance degrees degree temperature forecast shall confirm booking please'''.split())

_TG_ALIASES = {'taxi': 'டாக்ஸி', 'auto': 'ஆட்டோ', 'booking': 'புக்கிங்', 'celsius': 'செல்சியஸ்', 'temperature': 'டெம்பரேச்சர்', 'central': 'சென்ட்ரல்', 'belongings': 'பிலாங்கிங்ஸ்', 'belonging': 'பிலாங்கிங்', 'iruki': 'இருக்கு', 'irukki': 'இருக்கு', 'iruku': 'இருக்கு', 'solluren': 'சொல்லுறேன்', 'solluraen': 'சொல்லுறேன்', 'vanakkam': 'வணக்கம்', 'nandri': 'நன்றி', 'unga': 'உங்க', 'ungal': 'உங்கள்', 'ungalukku': 'உங்களுக்கு', 'neenga': 'நீங்க', 'eppadi': 'எப்படி', 'pannalama': 'பண்ணலாமா', 'pannalaama': 'பண்ணலாமா', 'pannalaam': 'பண்ணலாம்', 'pannunga': 'பண்ணுங்க', 'pannikkonga': 'பண்ணிக்கோங்க', 'pannrom': 'பண்றோம்', 'sollunga': 'சொல்லுங்க', 'sollalaam': 'சொல்லலாம்', 'illa': 'இல்ல', 'illai': 'இல்லை', 'vera': 'வேற', 'veru': 'வேறு', 'aiye': 'ஐயே', 'aiyum': 'ஐயும்', 'um': 'உம்', 'adhe': 'அதே', 'athe': 'அதே', 'idhe': 'இதே', 'ithae': 'இதே', 'indha': 'இந்த', 'andha': 'அந்த', 'naal': 'நாள்', 'naalaiku': 'நாளைக்கு', 'innikku': 'இன்னைக்கு', 'innaiku': 'இன்னைக்கு', 'neram': 'நேரம்', 'nerathil': 'நேரத்தில்', 'nerathula': 'நேரத்துல', 'kelambura': 'கிளம்புற', 'kelambumbodhu': 'கிளம்பும்போது', 'purappadum': 'புறப்படும்', 'purappadumbodhu': 'புறப்படும்போது', 'irukku': 'இருக்கு', 'irukkum': 'இருக்கும்', 'irukkura': 'இருக்குற', 'irukkalaam': 'இருக்கலாம்', 'irundhu': 'இருந்து', 'ilirundhu': 'இலிருந்து', 'peru': 'பேர்', 'ku': 'க்கு', 'la': 'ல', 'ah': 'ஆ', 'mazhai': 'மழை', 'peiya': 'பெய்ய', 'vaaippu': 'வாய்ப்பு', 'vaanilai': 'வானிலை', 'veppanilai': 'வெப்பநிலை', 'sumaar': 'சுமார்', 'adhigamaaga': 'அதிகமாக', 'adhigamaa': 'அதிகமா', 'konjam': 'கொஞ்சம்', 'megamoottam': 'மேகமூட்டம்', 'kanamazhai': 'கனமழை', 'kudai': 'குடை', 'kudineer': 'குடிநீர்', 'eduthuttu': 'எடுத்துட்டு', 'eduthukkonga': 'எடுத்துக்கோங்க', 'eduthukkondu': 'எடுத்துக்கொண்டு', 'nanaiyaamal': 'நனையாமல்', 'nanaiyama': 'நனையாம', 'paadhugaathukkollunga': 'பாதுகாத்துக்கொள்ளுங்க', 'paadhugaappa': 'பாதுகாப்பா', 'vachukkonga': 'வச்சுக்கோங்க', 'erumboadhum': 'ஏறும்போதும்', 'irangumboadhum': 'இறங்கும்போதும்', 'eravum': 'ஏறவும்', 'irangavum': 'இறங்கவும்', 'pakkavaatil': 'பக்கவாட்டில்', 'padalaam': 'படலாம்', 'purappadumun': 'புறப்படும் முன்', 'mun': 'முன்', 'ulloor': 'உள்ளூர்', 'paarunga': 'பாருங்க', 'thevaiyaana': 'தேவையான', 'munnerpaadugal': 'முன்னேற்பாடுகள்', 'payanathirku': 'பயணத்திற்கு', 'payanam': 'பயணம்', 'inimaiyaaga': 'இனிமையாக', 'amaiyattum': 'அமையட்டும்', 'nandraagave': 'நன்றாகவே'}

_TG_OVERRIDES = dict(peiya='பெய்ய', peyya='பெய்ய', umbrella='அம்ப்ரெல்லா', umbrellas='அம்ப்ரெல்லாக்கள்', mini='மினீ',
                     ninety='நைன்டி', forecast='ஃபோர்காஸ்ட்')

_TG_ALIASES.update(virumbina='விரும்பினா', oru='ஒரு', ana='ஆனா', aana='ஆனா', thaan='தான்', than='தான்', enna='என்ன', mela='மேல',
                   kelunga='கேளுங்க', irukkunga='இருக்குங்க', irukkumnu='இருக்கும்னு')

_TG_SIGNS = ('zh', 'dh', 'aa', 'oa', 'ae', 'nga', 'ngu', 'kk', 'rr', 'nj', 'ai', 'ei', 'au', 'ee', 'oo')

_TG_STRONG = ('zh', 'dh', 'aa', 'oa', 'ae', 'kk', 'rr', 'nj', 'ngu', 'nga')

_TG_SUFFIX = ('kku', 'aal', 'udan', 'nga', 'ngal', 'ndu', 'adhu', 'athu', 'aama', 'aamal', 'aaga', 'irukku', 'irukkum', 'kollunga')

_TG_C = [('ng', 'ங்'), ('nj', 'ஞ்'), ('zh', 'ழ்'), ('th', 'த்'), ('dh', 'த்'), ('ch', 'ச்'), ('sh', 'ஷ்'),
         ('kk', 'க்க்'), ('pp', 'ப்ப்'), ('tt', 'ட்ட்'), ('mm', 'ம்ம்'), ('nn', 'ன்ன்'), ('ll', 'ல்ல்'), ('rr', 'ற்ற்'),
         ('vv', 'வ்வ்'), ('yy', 'ய்ய்'), ('ss', 'ஸ்ஸ்'),
         ('k', 'க்'), ('g', 'க்'), ('p', 'ப்'), ('b', 'ப்'), ('m', 'ம்'), ('y', 'ய்'), ('r', 'ர்'), ('l', 'ல்'),
         ('v', 'வ்'), ('w', 'வ்'), ('s', 'ச்'), ('j', 'ஜ்'), ('h', 'ஹ்'), ('n', 'ன்'), ('t', 'ட்'), ('d', 'ட்'),
         ('f', 'ஃப்'), ('x', 'க்ஸ்'), ('q', 'க்'), ('z', 'ஸ்')]

_TG_V = [('aa', 'ஆ', 'ா'), ('ae', 'ஏ', 'ே'), ('ai', 'ஐ', 'ை'), ('au', 'ஔ', 'ௌ'), ('ee', 'ஈ', 'ீ'), ('ii', 'ஈ', 'ீ'),
         ('oo', 'ஊ', 'ூ'), ('uu', 'ஊ', 'ூ'), ('oa', 'ஓ', 'ோ'), ('oe', 'ஓ', 'ோ'),
         ('a', 'அ', ''), ('i', 'இ', 'ி'), ('u', 'உ', 'ு'), ('e', 'எ', 'ெ'), ('o', 'ஒ', 'ொ')]

def movio_roman_to_tamil(word):
    """Rule-based Tanglish -> Tamil script for words missing from the dictionary."""
    w = word.lower().replace("'", '')
    out, i = [], 0                                       # out[-1] ends with a virama while a consonant is open
    def open_consonant():
        return bool(out) and out[-1].endswith('\u0BCD')
    while i < len(w):
        if w.startswith('ei', i):                       # peiya -> பெய்ய
            if open_consonant():out[-1] = out[-1][:-1] + '\u0BC6'
            else:out.append('\u0B8E')
            out.append('\u0BAF\u0BCD'); i += 2; continue
        vowel = next((v for v in _TG_V if w.startswith(v[0], i)), None)
        if vowel:
            if open_consonant():out[-1] = out[-1][:-1] + vowel[2]
            else:out.append(vowel[1])
            i += len(vowel[0]); continue
        cons = next((c for c in _TG_C if w.startswith(c[0], i)), None)
        if not cons:
            return word                                  # unknown letter: leave untouched
        text = cons[1]
        nxt = w[i + len(cons[0]):i + len(cons[0]) + 1]
        if cons[0] in ('ng', 'nj') and nxt and nxt in 'aeiou':
            text += '\u0B95\u0BCD' if cons[0] == 'ng' else '\u0B9A\u0BCD'   # nga -> ங்க, nja -> ஞ்ச
        elif cons[0] == 'n' and i == 0:
            text = '\u0BA8\u0BCD'
        out.append(text); i += len(cons[0])
    result = ''.join(out)
    return result if _re.search(r'[\u0B80-\u0BFF]', result) else word

def movio_runtime_vocab(b):
    """Tamil-script spellings already used by the running Tanglish voice (optional)."""
    try:
        speech = getattr(b, 'tanglish_speech_text', None)
        cells = dict(zip(speech.__code__.co_freevars, speech.__closure__ or ()))
        return {k: v for k, v in cells['words'].cell_contents.items()
                if isinstance(v, str) and _re.search(r'[\u0B80-\u0BFF]', v)}
    except Exception:
        return {}

def movio_tanglish_script(value, vocab=None):
    """Tamil words -> Tamil script. English words, names and numbers stay as they are."""
    vocab = vocab or {}

    def token(match):
        raw = match.group(0); low = raw.lower()
        before = value[:match.start()].rstrip()
        sentence_start = not before or before[-1] in '.;!?'
        if low in _TG_OVERRIDES:
            return _TG_OVERRIDES[low]
        if low in _TG_ALIASES:
            return _TG_ALIASES[low]
        if low in vocab:
            return vocab[low]
        if low in _TG_ENGLISH:
            return raw
        if raw[0].isupper() and not sentence_start:
            return raw                                   # place names such as Tondiarpet
        if any(sign in low for sign in _TG_STRONG) or (len(low) > 4 and low.endswith(_TG_SUFFIX)):
            return movio_roman_to_tamil(raw)
        return raw
    return _re.sub(r"[A-Za-z][A-Za-z']*", token, value)

import contextvars as _cv

_MOVIO_ONE_CHUNK = _cv.ContextVar('movio_forecast_one_chunk', default=False)

def movio_install_single_chunk(b):
    """While a forecast sentence is spoken, give the voice engine ONE speech chunk per sentence
    (up to 28 words) so it never breaks inside e.g. 'ஒரு தகவல்'. Other speech is unaffected."""
    adapter = getattr(b, 'TTS', None)
    ns = getattr(adapter, 'ns', None)
    targets = []
    if isinstance(ns, dict):
        targets.append(ns)
        stream = ns.get('movio_stream_response')
        stream_globals = getattr(stream, '__globals__', None)
        if isinstance(stream_globals, dict) and stream_globals is not ns:
            targets.append(stream_globals)
    wrapped = 0
    for target in targets:
        previous = target.get('prepare_movio_request')
        if not callable(previous):
            continue
        if getattr(previous, '_movio_one_chunk', False):
            wrapped += 1
            continue
        def make(prev):
            def prepare(*args, **kwargs):
                plan = prev(*args, **kwargs)
                if not _MOVIO_ONE_CHUNK.get() or not isinstance(plan, dict):
                    return plan
                chunks = [str(c).strip() for c in plan.get('chunks', []) if str(c).strip()]
                groups, current = [], ''
                for chunk in chunks:
                    if current and len((current + ' ' + chunk).split()) > 28:
                        groups.append(current); current = chunk
                    else:
                        current = (current + ' ' + chunk).strip()
                if current:
                    groups.append(current)
                return {**plan, 'chunks': groups or chunks}
            prepare._movio_one_chunk = True
            return prepare
        target['prepare_movio_request'] = make(previous)
        wrapped += 1
    return wrapped

def register_forecast_audio(app, bridge_object, engine, public_origin):
    """Reuse the existing endpoint, or add one authenticated TTS-only route."""
    import asyncio
    import base64
    import inspect
    import json
    import threading
    import time
    import hashlib
    from collections import OrderedDict
    import requests
    from fastapi import HTTPException, Request

    version='forecast-voice-3.0-progressive'
    existing=[r for r in app.routes if getattr(r,'path',None)=='/weather-speech']
    replaced=[]
    for route in existing:
        if getattr(route.endpoint,'_movio_forecast_voice',None) is None:
            raise RuntimeError('A different /weather-speech endpoint exists. Share its source before modifying it.')
    if len(existing)==1 and existing[0].endpoint._movio_forecast_voice==version and 'POST' in (getattr(existing[0],'methods',set()) or set()):
        return dict(added=False,replaced=[],route=existing[0],endpoint=existing[0].endpoint)
    replaced=list(existing)  # older MOVIO forecast-voice route: replaced by this version
    if replaced:app.routes[:]=[r for r in app.routes if r not in replaced]
    tts=engine.get('tts_reply')
    language_scope=getattr(bridge_object,'CURRENT_LANGUAGE',None)
    if not callable(tts) or not callable(getattr(language_scope,'set',None)):
        raise RuntimeError('The existing optimized DhVaani reply handler is missing.')
    register=None
    advisory=engine.get('advisory')
    if callable(advisory):
        try:register=inspect.getclosurevars(advisory).nonlocals.get('register')
        except (TypeError,ValueError):pass
    if not callable(register):
        # Fallback: write straight into the weather-profile registry used by tts_reply.
        try:
            profile_for=inspect.getclosurevars(tts).nonlocals.get('profile_for')
            profiles=inspect.getclosurevars(profile_for).nonlocals.get('profiles')
            guard=inspect.getclosurevars(profile_for).nonlocals.get('registry_lock')
            if profiles is not None and guard is not None:
                def register(text,kind):
                    with guard:
                        profiles[str(text).strip()]=kind;profiles.move_to_end(str(text).strip())
        except (TypeError,ValueError,AttributeError):pass
    busy=threading.BoundedSemaphore(1)
    cache=OrderedDict()
    cache_lock=threading.Lock()
    cache_bytes=0
    CACHE_LIMIT=32*1024*1024
    CACHE_TTL=900  # In-memory only; never write forecast audio or location data to disk.
    class Busy(Exception):pass
    def clear_cache():
        nonlocal cache_bytes
        with cache_lock:cache.clear();cache_bytes=0
    def render(text,language,part=None):
        nonlocal cache_bytes
        started=time.perf_counter()
        parts=movio_forecast_parts(text,language,movio_runtime_vocab(bridge_object) if language=='Tanglish' else None)
        if not parts or len(parts)>14:raise ValueError('Forecast text cannot be spoken')
        if part is not None and (type(part) is not int or not 0<=part<len(parts)):
            raise ValueError('Invalid forecast part')
        selected=parts if part is None else [parts[part]]
        if not busy.acquire(blocking=False):raise Busy()
        token=language_scope.set(language)
        quality=getattr(bridge_object,'WX_SPEECH_QUALITY',None)
        old_min=quality.get('min_words') if isinstance(quality,dict) else None
        had_min=isinstance(quality,dict) and 'min_words' in quality
        if isinstance(quality,dict):quality['min_words']=max(int(old_min or 8),16)
        one=None
        try:
            pieces=[];hits=0
            movio_install_single_chunk(bridge_object)
            one=_MOVIO_ONE_CHUNK.set(True)
            ns=getattr(getattr(bridge_object,'TTS',None),'ns',{})
            voice_settings={k:ns.get(k) for k in ('FIRST_CHUNK_NUM_STEP','REST_CHUNK_NUM_STEP',
                'ENGLISH_SPEED','TAMIL_SPEED','TANGLISH_SPEED','USE_FP16_SAMPLE','SEED','MODEL_ID','REVISION')} if isinstance(ns,dict) else {}
            signature=repr((version,id(tts),quality,voice_settings,globals().get('MOVIO_FORECAST_CACHE_REVISION','1')))
            for sentence,pause in selected:
                key=hashlib.sha256((signature+'\n'+language+'\n'+sentence).encode()).hexdigest()
                raw=None;now=time.monotonic()
                with cache_lock:
                    # Expire inactive entries too, so retained speech stays bounded by age.
                    for old_key,(created,old_raw) in list(cache.items()):
                        if now-created>CACHE_TTL:
                            cache_bytes-=len(old_raw);del cache[old_key]
                    entry=cache.get(key)
                    if entry is not None:raw=entry[1];cache.move_to_end(key);hits+=1
                if raw is None:
                    if callable(register):register(sentence,'weather')
                    audio=tts(bridge_object,sentence)
                    if not isinstance(audio,str):raise ValueError('Invalid speech response')
                    raw=base64.b64decode(audio,validate=True)
                    if len(raw)<44 or raw[:4]!=b'RIFF' or raw[8:12]!=b'WAVE':raise ValueError('Invalid WAV response')
                    # Validate before caching; the same working pronunciation/TTS path is used.
                    movio_join_wavs([(raw,0)])
                    if len(raw)>9000000:raise ValueError('Speech response too large')
                    with cache_lock:
                        cache[key]=(time.monotonic(),raw);cache_bytes+=len(raw)
                        while cache_bytes>CACHE_LIMIT or len(cache)>256:
                            _,(_,removed)=cache.popitem(last=False);cache_bytes-=len(removed)
                pieces.append((raw,pause))
            joined=movio_join_wavs(pieces)
            if len(joined)>9000000:raise ValueError('Speech response too large')
            return dict(audio=base64.b64encode(joined).decode(),format='wav',
                part=part,total_parts=len(parts),cached_parts=hits,
                generation_ms=round((time.perf_counter()-started)*1000,1),protocol='parts-v1')
        finally:
            if one is not None:_MOVIO_ONE_CHUNK.reset(one)
            if isinstance(quality,dict):
                if had_min:quality['min_words']=old_min
                else:quality.pop('min_words',None)
            language_scope.reset(token);busy.release()
    def authenticate(cookie):
        # Reuse website authentication without exposing account data or keys.
        with requests.Session() as session:
            session.trust_env=False
            response=session.get('http://127.0.0.1:8080/api/me',headers={'Cookie':cookie},
                                 timeout=(2,5),allow_redirects=False)
            if response.status_code!=200:raise PermissionError()
            account=response.json()
            if account.get('role')!='customer':raise PermissionError()

    async def manual_forecast_voice(request:Request):
        origin=request.headers.get('origin','').rstrip('/')
        if origin and origin!=public_origin.rstrip('/'):
            raise HTTPException(403,'Origin not allowed')
        cookie=request.headers.get('cookie','')
        if not cookie:raise HTTPException(401,'Sign in to listen to this forecast')
        try:await asyncio.to_thread(authenticate,cookie)
        except PermissionError:raise HTTPException(403,'Customer login required')
        except Exception:raise HTTPException(503,'Account verification is temporarily unavailable')
        try:
            body=await request.body()
            if len(body)>16000:raise ValueError()
            data=json.loads(body)
            if not isinstance(data,dict):raise ValueError()
            text=data.get('text');language=data.get('language')
            if not isinstance(text,str) or not text.strip() or len(text)>1500:raise ValueError()
            if language not in ('English','Tamil','Tanglish'):raise ValueError()
            part=data.get('part')
            if part is not None and (type(part) is not int or not 0<=part<14):raise ValueError()
        except (ValueError,TypeError,UnicodeError):raise HTTPException(400,'Invalid forecast voice request')
        try:
            return await asyncio.to_thread(render,text.strip(),language,part)
        except Busy:raise HTTPException(429,'Forecast voice is busy; please retry')
        except ValueError:raise HTTPException(400,'Invalid forecast speech part or audio')
        except Exception:raise HTTPException(503,'Forecast voice could not be generated')
    manual_forecast_voice._movio_forecast_clear_cache=clear_cache
    manual_forecast_voice._movio_forecast_voice=version
    manual_forecast_voice.__annotations__['request']=Request
    app.add_api_route('/weather-speech',manual_forecast_voice,methods=['POST'])
    route=next(r for r in app.routes if getattr(r,'endpoint',None) is manual_forecast_voice)
    app.openapi_schema=None
    return dict(added=True,replaced=replaced,route=route,endpoint=manual_forecast_voice)

# Shared pronunciation correction — English, Tamil and Tanglish
# Run after your existing voice/pronunciation setup.

import re
import functools

def movio_install_common_pronunciation():
    namespace = globals()
    current = namespace.get("normalize_taxi_text")

    if not callable(current):
        raise RuntimeError(
            "Run the original TTS setup first: "
            "normalize_taxi_text is not available."
        )

    # Re-running this cell does not add another wrapper.
    if getattr(current, "_movio_place_celsius_v1", False):
        print("Pronunciation correction is already installed.")
        return

    replacements = (
        (
            re.compile(
                r"(?<![A-Za-z])(?:vandaloor|vandalur)(?![A-Za-z])",
                re.IGNORECASE,
            ),
            "வண்டலூர்",
        ),
        (
            re.compile(
                r"(?<![A-Za-z])celsius(?![A-Za-z])",
                re.IGNORECASE,
            ),
            "செல்சியஸ்",
        ),
    )

    def correct_pronunciation(text):
        for pattern, spoken_form in replacements:
            text = pattern.sub(spoken_form, text)
        return text

    @functools.wraps(current)
    def corrected_normalizer(*args, **kwargs):
        # Preserve all existing normalization first.
        result = current(*args, **kwargs)

        # Apply independently of the selected language.
        if isinstance(result, str):
            return correct_pronunciation(result)

        return result

    corrected_normalizer._movio_place_celsius_v1 = True
    corrected_normalizer._movio_original = current

    # Verify the replacement rules without generating speech.
    assert correct_pronunciation("Vandaloor") == "வண்டலூர்"
    assert correct_pronunciation("Vandalur") == "வண்டலூர்"
    
    assert correct_pronunciation("degrees Celsius") == "degrees செல்சியஸ்"
    assert correct_pronunciation("28.5 Celsius") == "28.5 செல்சியஸ்"
    assert correct_pronunciation("வண்டலூர் செல்சியஸ்") == "வண்டலூர் செல்சியஸ்"

    namespace["normalize_taxi_text"] = corrected_normalizer

    print("Pronunciation rules installed; replacement checks passed.")
    print("Vandaloor / Vandalur → வண்டலூர்")
    print("Celsius → செல்சியஸ்")
    print("Rules apply regardless of the selected language.")
    print("Close the old AI Call popup and start a new call.")

movio_install_common_pronunciation()