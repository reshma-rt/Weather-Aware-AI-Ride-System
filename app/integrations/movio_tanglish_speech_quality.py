"""Speech-copy helpers for the existing MOVIO Tanglish adapter."""
import re

VERSION = 'tanglish-speech-quality-1.3'

# English words stay English. The three requested pronunciation exceptions
# retain their meaning while using Tamil script in the speech copy only.
ENGLISH_WORDS = set(("""
ai welcome help service ride book cancel cancellation existing travel pickup
drop destination place correct yes no vehicle road distance around approximate
estimated fare confirm confirmation details detail passengers passenger
kilometres kilometers kilometer kilometres rupees rupee driver mini car bike
auto sedan suv am pm otp id number request record save saved select selected
screen map route verify continue rain chance forecast please check change
retry tomorrow today morning evening night weather update temperature degrees
degree cloudy sunny pleasant heavy strong wind windy thunderstorm thunderstorms
umbrella belongings bags care cover covered consider keep same time open
protection prepare sun heat warnings booking taxi celsius point zero oh one
two three four five six seven eight nine ten eleven twelve thirteen fourteen
fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty
seventy eighty ninety hundred thousand lakh lakhs crore crores million billion
and a an the to from for at in on by of with your you our my me it is are will
be can have thank thanks wonderful journey comfortable keep retain switch
january february march april may june july august september october november
december monday tuesday wednesday thursday friday saturday sunday
""").split())

ALIASES = dict(
    taxi='டெக்ஸி', auto='ஆட்டோ', booking='புக்கிங்', celsius='செல்சியஸ்',
    temperature='டெம்பரேச்சர்', central='சென்ட்ரல்',
    belongings='பிலாங்கிங்ஸ்', belonging='பிலாங்கிங்',
    iruki='இருக்கு', irukki='இருக்கு', iruku='இருக்கு',
    solluren='சொல்லுறேன்', solluraen='சொல்லுறேன்',
    vanakkam='வணக்கம்', nandri='நன்றி', unga='உங்க', ungal='உங்கள்',
    ungalukku='உங்களுக்கு', neenga='நீங்க', eppadi='எப்படி',
    pannalama='பண்ணலாமா', pannalaama='பண்ணலாமா', pannalaam='பண்ணலாம்',
    pannunga='பண்ணுங்க', pannikkonga='பண்ணிக்கோங்க', pannrom='பண்றோம்',
    sollunga='சொல்லுங்க', sollalaam='சொல்லலாம்', illa='இல்ல', illai='இல்லை',
    vera='வேற', veru='வேறு', aiye='ஐயே', aiyum='ஐயும்', um='உம்',
    adhe='அதே', athe='அதே', idhe='இதே', ithae='இதே', indha='இந்த',
    andha='அந்த', naal='நாள்', naalaiku='நாளைக்கு', innikku='இன்னைக்கு',
    innaiku='இன்னைக்கு', neram='நேரம்', nerathil='நேரத்தில்',
    nerathula='நேரத்துல', kelambura='கிளம்புற', kelambumbodhu='கிளம்பும்போது',
    purappadum='புறப்படும்', purappadumbodhu='புறப்படும்போது',
    irukku='இருக்கு', irukkum='இருக்கும்', irukkura='இருக்குற',
    irukkalaam='இருக்கலாம்', irundhu='இருந்து', ilirundhu='இலிருந்து',
    peru='பேர்', ku='க்கு', la='ல', ah='ஆ',
    mazhai='மழை', peiya='பெய்ய', vaaippu='வாய்ப்பு',
    vaanilai='வானிலை', veppanilai='வெப்பநிலை', sumaar='சுமார்',
    adhigamaaga='அதிகமாக', adhigamaa='அதிகமா', konjam='கொஞ்சம்',
    megamoottam='மேகமூட்டம்', kanamazhai='கனமழை',
    kudai='குடை', kudineer='குடிநீர்', eduthuttu='எடுத்துட்டு',
    eduthukkonga='எடுத்துக்கோங்க', eduthukkondu='எடுத்துக்கொண்டு',
    nanaiyaamal='நனையாமல்', nanaiyama='நனையாம',
    paadhugaathukkollunga='பாதுகாத்துக்கொள்ளுங்க',
    paadhugaappa='பாதுகாப்பா', vachukkonga='வச்சுக்கோங்க',
    erumboadhum='ஏறும்போதும்', irangumboadhum='இறங்கும்போதும்',
    eravum='ஏறவும்', irangavum='இறங்கவும்',
    pakkavaatil='பக்கவாட்டில்', padalaam='படலாம்',
    purappadumun='புறப்படும் முன்', mun='முன்', ulloor='உள்ளூர்',
    paarunga='பாருங்க', thevaiyaana='தேவையான', munnerpaadugal='முன்னேற்பாடுகள்',
    payanathirku='பயணத்திற்கு', payanam='பயணம்', inimaiyaaga='இனிமையாக',
    amaiyattum='அமையட்டும்', nandraagave='நன்றாகவே',
)


def make_speech_text(lock, pattern, places, re, words, wx):
    def speech_text(text):
        """MOVIO call weather card v1: Celsius is pronounced செல்சியஸ்."""
        text = str(text)
        with lock:
            names = sorted(places, key=len, reverse=True)
        protected = {}
        for name in names:
            if name and name in text:
                marker = chr(0xF000 + len(protected))
                text = text.replace(name, marker)
                protected[marker] = name
        text = re.sub(r'(?i)\bkilo\s+meettar\b|\bkm\b', 'kilometers', text)
        # Convert clock times to speakable English BEFORE numeric normalization.
        # Avoid opaque placeholders, which may be spoken literally or lost.
        def speak_clock(match):
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            period = match.group(3).lower().replace('.', '')
            ones = ('zero','one','two','three','four','five','six','seven','eight','nine',
                    'ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen',
                    'seventeen','eighteen','nineteen')
            tens = ('','','twenty','thirty','forty','fifty')
            def number(n):
                return ones[n] if n < 20 else tens[n // 10] + (' ' + ones[n % 10] if n % 10 else '')
            spoken = number(hour)
            if minute:
                spoken += ' ' + ('oh ' + number(minute) if minute < 10 else number(minute))
            return spoken + (' pee em' if period == 'pm' else ' ay em')
        text = re.sub(
            r'(?i)\b(0?[1-9]|1[0-2])(?::([0-5][0-9]))?\s*([ap]\.?m\.?)(?=\W|$)',
            speak_clock, text)
        text = wx['speech_numeric_normalize'](lambda value: value, text, 'English')
        text = re.sub(r'(?i)\bunga\s+ride\s+details\s+(?:sollalaam|solluren|solluraen|solren|sollren)\b',
                      'உங்க ride details சொல்லுறேன்', text)
        text = pattern.sub(lambda match: words[match[0].lower()], text)
        text = re.sub(r'\b(?:SUV|S\s+U\s+V|es yoo vee)\b', 'ess you vee', text, flags=re.I)
        aliases = {'AI':'ay eye', 'AM':'ay em', 'PM':'pee em', 'OTP':'oh tee pee', 'ID':'eye dee'}
        text = re.sub(r'\b(?:AI|AM|PM|OTP|ID)\b', lambda match: aliases[match[0]], text)
        # Punctuation affects speech only. The displayed response is untouched.
        text = re.sub(r';\s*', '. ', text)
        text = re.sub(r':(?=\s)', ',', text)
        for marker, name in protected.items():
            spoken_name = wx['speech_numeric_normalize'](lambda value: value, name, 'English')
            spoken_name = re.sub(r'(?i)\bcentral\b', 'சென்ட்ரல்', spoken_name)
            spoken_name = re.sub(r'(?i)\btambaram\b', 'தாம்பரம்', spoken_name)
            text = text.replace(marker, spoken_name)
        return re.sub(r'\s+', ' ', text).strip()
    return speech_text


def phrases(text, protected_places=(), minimum_words=8):
    """Complete clauses, retaining decimal values and protected place names."""
    value = str(text).strip()
    if not value:
        return []
    protected = {}
    for name in sorted(set(protected_places), key=len, reverse=True):
        if name and name in value:
            marker = chr(0xF000 + len(protected))
            value = value.replace(name, marker)
            protected[marker] = name
    clauses = re.split(r'(?<=[.!?;])\s+|\n+', value)
    parts, pending = [], ''
    for clause in clauses:
        if not clause.strip():
            continue
        pending = (pending + ' ' + clause.strip()).strip()
        if re.search(r'(?:^|\s)(?:[A-Za-z]|Dr|Mr|Ms|Mrs|St)\.$', pending):
            continue
        if len(pending.split()) >= minimum_words:
            parts.append(pending);pending = ''
    if pending:
        if parts:
            parts[-1] += ' ' + pending
        else:
            parts.append(pending)
    for index, part in enumerate(parts):
        for marker, name in protected.items():
            part = part.replace(marker, name)
        parts[index] = part
    return parts
