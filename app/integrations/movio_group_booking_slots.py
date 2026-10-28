"""Shared booking-slot extraction; the installed dialogue/booking engine stays in charge."""
import copy
import re
import unicodedata

VERSION='group-slots-1.1'
_ENGINE={}
_DIGITS=str.maketrans('௦௧௨௩௪௫௬௭௮௯','0123456789')
_KEYS=('count','vehicle','pickup','destination')
_LETTERS=r'A-Za-z\u0B80-\u0BFF'
_DEFAULT_PLACES={
 'Tambaram':('tambaram','thambaram','thaambaram','தாம்பரம்','தாம்பரத்தில்','தாம்பரத்திலிருந்து','தாம்பரத்துக்கு','தாம்பரத்திற்கு'),
 'Vandalur':('vandalur','vandaloor','vandallur','வண்டலூர்','வண்டலூரில்','வண்டலூரிலிருந்து','வண்டலூருக்கு','வண்டலூர்க்கு'),
}
_VEHICLES=(
 ('SUV',r'(?<![a-z])s\s*[. -]?u\s*[. -]?v(?![a-z])|எஸ்\s*ய[ுூ]?\s*வி|எஸ்யூவி'),
 ('Sedan',r'(?<![a-z])sedan(?![a-z])|செடான்'),
 ('Mini',r'(?<![a-z])mini(?:\s*(?:car|கார்))?(?![a-z])|மினி(?:\s*(?:கார்|car))?'),
 ('Auto',r'(?<![a-z])(?:auto|aatto|aato)(?![a-z])|ஆட்டோ'),
 ('Bike',r'(?<![a-z])(?:bike|baikku|baik)(?![a-z])|பைக்'),
)
_EN_FROM=re.compile(r'(?<![a-z])(?:pick\s+me\s+up\s+(?:from|at)|pickup(?:\s+(?:is|from|at))?|from)(?![a-z])\s*[:=-]?\s*',re.I)
_EN_TO=re.compile(r'(?<![a-z])(?:destination(?:\s+is)?|drop(?:\s*(?:off|me))?(?:\s+(?:at|is))?|take\s+me\s+to|to)(?![a-z])\s*[:=-]?\s*',re.I)
_TA_FROM=re.compile(r'(?:இல்\s*இருந்து|இலிருந்து|லிருந்து|லேர்ந்து|லருந்து|இருந்து)(?=\s|[-,;.!?]|$)')
_ROMAN_FROM=re.compile(r'(?:(?:\s+|-)la\s*irun[dt]hu|(?:\s+|-)il\s*irun[dt]hu|(?:ili|li|le|la)?run[dt]hu|(?:\s+|-)?irun[dt]hu|(?:\s+|-)?lerndhu|(?:\s+|-)?lerun[dt]hu)(?![a-z])',re.I)
_TA_PICKUP_LABEL=re.compile(r'(?:புறப்படும்\s*இடம்|ஏறும்\s*இடம்|பிக்கப்)\s*[:=-]?\s*')
_TA_DROP_LABEL=re.compile(r'(?:சேரும்\s*இடம்|இறங்கும்\s*இடம்|டிராப்)\s*[:=-]?\s*')
_TO_SUFFIX=re.compile(r'(?:க்கு|வரை)(?=\s|[,;.!?]|$)|(?<![a-z])(?:ku|varai|varaikkum)(?![a-z])|kku(?![a-z])|(?<=[a-z])ku(?![a-z])',re.I)
_GO=re.compile(r'(?<![a-z])(?:poganum|pogannum|poganumnu|poganu|poga|ponum|porom|pog[a]?num|venum|vendum|v[a]?enum|edunga|eduthukkonga|pickup\s+pannu)(?![a-z])|போகணும்|போகனும்|போக\s*வேண்டும்|செல்ல\s*வேண்டும்|செல்லணும்|செல்லனும்|செல்ல|போக|வேணும்|வேண்டும்|எடுங்க|எடுத்துக்கோங்க',re.I)
_CARRIER=re.compile(r'(?<![a-z])(?:naan|nan|naanga|nanga|naangal|naangalum|enakku|enaku|engalukku|namakku|irukkom|irukk[o]?m|irukkirom|irukkomnga|venum|vendum|v[a]?enum)(?![a-z])|நாங்கள்|நாங்க|நான்|எனக்கு|எங்களுக்கு|நமக்கு|இருக்கிறோம்|இருக்கோம்|வேணும்|வேண்டும்',re.I)
_TIME=re.compile(r'(?<![a-z])(?:today|tomorrow|tonight|innaiku|inniku|iniku|indru|naalaiku|naalaikku|naalai|morning|afternoon|evening|night|kaalai|kalai|madhiyam|mathiyam|maalai|iravu)(?![a-z])|இன்று|இன்னைக்கு|நாளைக்கு|நாளை|காலை|மதியம்|மாலை|இரவு|நள்ளிரவு|\d{4}-\d{2}-\d{2}|\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?|மணிக்கு|மணி|manikku|mani)(?![a-z])',re.I)
_FILLER=re.compile(r'^(?:pickup|drop|pannu|pannunga|edunga|please|வேணும்|வேண்டும்|எடுங்க|இருக்கோம்|சரி|ஆம்|yes|no|okay|ok|hello|vanakkam|வணக்கம்)(?:\s|$)',re.I)
_CORRECTION=re.compile(r'(?<![a-z])(?:no|not|change|instead|replace|actually|rather|maathu|maathunga|mathunga|badila|bathila|illa|vendam)(?![a-z])|மாற்ற|பதிலா|பதிலாக|வேண்டாம்|இல்லை',re.I)
_SENTENCE_WORDS=re.compile(r'\b(?:i|we|me|us|you|want|need|take|where|am|is|are|go|going|travel|book|booking|confirm|cancel|please|thanks|thank)\b',re.I)

def normalize(value):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value or '')).translate(_DIGITS).casefold()).strip()

def place_key(value):
    value=normalize(value)
    return re.sub(r'\s+',' ',''.join(' ' if unicodedata.category(c).startswith('P') else c for c in value)).strip()

def tamil_place_forms(alias):
    """Inflect registered names, rather than guessing an unknown Tamil stem."""
    if not re.fullmatch(r'[\u0B80-\u0BFF ]+',alias):return ()
    forms={alias+' வரை',alias+'வரை'}
    if alias.endswith('ம்'):
        stem=alias[:-2]
        forms.update(stem+suffix for suffix in ('த்தில்','த்திலிருந்து','த்தில் இருந்து','த்துக்கு','த்திற்கு'))
    elif alias.endswith('்'):
        stem=alias[:-1]
        forms.update(stem+suffix for suffix in ('ில்','ிலிருந்து','ில் இருந்து','ுக்கு','்க்கு'))
    elif alias.endswith(('ி','ீ','ை')):
        forms.update(alias+suffix for suffix in ('யில்','யிலிருந்து','யில் இருந்து','க்கு'))
    elif alias.endswith(('ா','ூ')):
        forms.update(alias+suffix for suffix in ('வில்','விலிருந்து','வில் இருந்து','வுக்கு'))
    return forms

def number_words(engine):
    fn=engine.get('number_lexicon')
    table=dict(fn(20)) if callable(fn) else {}
    for n,words in enumerate((('zero','பூஜ்ஜியம்'),('one','ஒரு','ஒன்று','ஒன்னு','oru','onnu'),('two','இரண்டு','ரெண்டு','rendu','rendu','irandu'),('three','மூன்று','மூணு','moonru','moondru','moonu'),('four','நான்கு','நாலு','naalu','naangu'),('five','ஐந்து','அஞ்சு','aindhu','anju'),('six','ஆறு','aaru'),('seven','ஏழு','ezhu','yelu'),('eight','எட்டு','ettu'),('nine','ஒன்பது','onbadhu'),('ten','பத்து','pathu'))):
        for word in words:table[word]=n
    return {normalize(k):int(v) for k,v in table.items()}

def clause_ranges(text):
    start=0;out=[]
    for m in re.finditer(r'[.!?;\n]',text):
        if m[0]=='.':
            if m.start() and m.end()<len(text) and text[m.start()-1].isdigit() and text[m.end()].isdigit():continue
            before=text[start:m.start()].split()
            if before and re.fullmatch(r'(?:[A-Za-z]|Mr|Mrs|Dr|Ms)',before[-1],re.I):continue
            if m.end()<len(text) and not text[m.end()].isspace():continue
        out.append((start,m.start()));start=m.end()
    out.append((start,len(text)))
    return [(a,b) for a,b in out if text[a:b].strip()]

class Parser:
    def __init__(self,bridge,state,text,engine):
        self.bridge,self.state,self.engine=bridge,state,engine
        self.raw=unicodedata.normalize('NFKC',str(text or '')).strip()
        self.scan=self.raw.translate(_DIGITS)
        self.updates={};self.evidence={};self.conflicts={};self.noise=[]
        aliases={k:tuple(v) for k,v in getattr(bridge,'VOICE_PLACE_ALIASES',{}).items()}
        for source in (_DEFAULT_PLACES,getattr(bridge,'GROUP_PLACE_ALIASES',{})):
            for key,values in source.items():aliases[key]=aliases.get(key,())+tuple(values)+(key,)
        self.places={}
        for canonical,variants in aliases.items():
            for alias in (canonical,)+tuple(variants):
                self.places[place_key(alias)]=canonical
                for form in tamil_place_forms(alias):self.places[place_key(form)]=canonical
                for suffix in (' இலிருந்து',' லிருந்து','இலிருந்து','லிருந்து',' வரை',' varai',' varaikkum'):
                    self.places[place_key(alias+suffix)]=canonical
                if re.fullmatch(r'[A-Za-z ]+',alias):
                    for suffix in ('la',' ku',' kku','ku','kku',' la',' la irundhu','la irundhu',' il irundhu','ilirundhu','lirundhu',' lirundhu',' lerndhu','lerndhu',' lerundhu'):
                        self.places[place_key(alias+suffix)]=canonical

    def accept(self,slot,value,span,source='rule',confidence=1.0):
        self.updates[slot]=value;self.conflicts.pop(slot,None)
        self.evidence[slot]={'text':span,'source':source,'confidence':confidence}

    def count(self):
        """MOVIO slot-suffix-1.0: recognize explicit inflected passenger nouns."""
        words=number_words(self.engine)
        token=r'\d{1,2}|'+'|'.join(re.escape(k) for k in sorted(words,key=len,reverse=True) if not k.isdigit())
        unit=r'(?:பேருக்காக|பேருக்கும்|பேருக்கு|பேருடன்|பேரோடு|பேரும்|பேரை|பயணிகள்|நபர்கள்|பேர்கள்|நபர்|பேரு|பேர்|passengers?|people|persons?|pax|peru|paeru|per)'
        pattern=r'(?<!['+_LETTERS+r'\d])(?P<n>'+token+r')\s*'+unit+r'(?!['+_LETTERS+r'])'
        found=list(re.finditer(pattern,self.scan,re.I))
        if not found:
            m=re.search(r'(?<![a-z])(?:we\s+are|there\s+are|for)\s+(?P<n>'+token+r')(?=\s*(?:of\s+us\b|$))',self.scan,re.I)
            if m:found=[m]
        if not found and self.state.get('stage')=='count':
            m=re.fullmatch(r'\s*(?P<n>'+token+r')\s*[.!]?\s*',self.scan,re.I)
            if m:found=[m]
        if not found:return
        choices=[]
        for m in found:
            value=normalize(m['n']);n=int(value) if value.isdigit() else words[value]
            self.noise.append(m.span())
            if not re.search(r'\bnot\s*$',self.scan[max(0,m.start()-12):m.start()],re.I):choices.append((n,m))
        if not choices:return
        if len({n for n,_ in choices})>1 and not _CORRECTION.search(self.scan):
            self.conflicts['count']='More than one passenger count stated';return
        n,m=choices[-1];self.accept('count',n,self.raw[m.start():m.end()])

    def vehicle(self):
        hits=[]
        for value,pattern in _VEHICLES:
            for m in re.finditer(pattern,self.scan,re.I):
                if re.match(r'\s+(?:nagar|market|bazaar|road|street|நகர்|சாலை)\b',self.scan[m.end():],re.I):continue
                self.noise.append(m.span());hits.append((m.start(),m.end(),value))
        if not hits:return
        hits.sort();positive=[]
        for a,b,value in hits:
            left=self.scan[max(0,a-15):a];right=self.scan[b:]
            if re.search(r'\bnot\s*$',left,re.I) or re.match(r'[\s-]*(?:வேண்டாம்|இல்லை|vendam|illa)(?![a-z])',right,re.I):continue
            positive.append((a,b,value))
        if len({v for _,_,v in positive})==1:
            a,b,value=positive[-1];self.accept('vehicle',value,self.raw[a:b]);return
        if positive and _CORRECTION.search(self.scan):
            instead=re.search(r'\binstead\s+of\b',self.scan,re.I)
            before=[h for h in positive if instead and h[1]<=instead.start()]
            a,b,value=before[-1] if before else positive[-1]
            self.accept('vehicle',value,self.raw[a:b]);return
        self.conflicts['vehicle']='Choose one vehicle' if positive else 'The stated vehicle was rejected'

    def clean_place(self,value,role):
        """MOVIO slot-suffix-1.0: a grammatical suffix is never a location."""
        text=str(value or '').strip(' \t\r\n.,;:!?-–—')
        if normalize(text) in {'க்கு','கு','க்கே','க்கும்','க்குப்','ல','இல்','இருந்து','வரை'}:return None
        text=re.sub(r'(?i)^(?:i\s+(?:want|need)(?:\s+to\s+(?:go|travel))?|i\s+am|my\s+pickup\s+is|my\s+destination\s+is|please|naan|nan|enakku|enaku|நான்|எனக்கு)\s+','',text).strip()
        text=re.sub(r'(?i)\s+(?:for|with|and|at|from|to)\s*$','',text).strip(' ,-')
        # Match complete known names/case forms, not a place hidden inside a sentence.
        if place_key(text) in self.places:return self.places[place_key(text)]
        # Separate case markers can be removed without changing the spoken name.
        text=re.sub(r'(?i)(?:[-\s]+(?:இல்\s*இருந்து|இலிருந்து|லிருந்து|இருந்து|க்கு|வரை|la\s*irun[dt]hu|il\s*irun[dt]hu|irun[dt]hu|la|ku|kku|varai|varaikkum))$','',text).strip(' ,-')
        if place_key(text) in self.places:return self.places[place_key(text)]
        if not text or len(text)>180 or not re.search(r'[A-Za-z\u0B80-\u0BFF]',text):return None
        if normalize(text) in {'time','date','fare','vehicle','booking','car','cab','taxi','நேரம்','தேதி','இடம்'}:return None
        if _FILLER.match(text) or re.fullmatch(r'(?:இரண்டு|ரெண்டு|\d+)',text):return None
        if any(re.fullmatch(pattern,text,re.I) for _,pattern in _VEHICLES):return None
        if _TIME.search(text) or re.search(r'(?<![a-z])(?:poganum|venum|irukkom|we are|passengers?|people)(?![a-z])|வேணும்|வேண்டும்|இருக்கோம்|பேர்',text,re.I):return None
        canonicalizer=getattr(self.bridge,'canonical_place',None)
        canonical=canonicalizer(text) if callable(canonicalizer) else text
        return str(canonical).strip()[:120] if canonical else None

    def add_place(self,role,a,b,clause_start,source='rule',prefix=False,commit=True):
        if a>=b:return
        # Discard preceding booking/count/time phrases, retaining the nearby place.
        if prefix:
            cuts=[end for begin,end in self.noise if a<=begin<end<=b]
            cuts.extend(m.end() for m in _CARRIER.finditer(self.scan,a,b))
            if cuts:a=max(a,max(cuts))
        stop=[begin for begin,end in self.noise if a<=begin<b]
        stop.extend(m.start() for m in _GO.finditer(self.scan,a,b))
        stop.extend(m.start() for m in _TIME.finditer(self.scan,a,b))
        stop.extend(m.start() for m in _CARRIER.finditer(self.scan,a,b) if m.start()>a and self.scan[m.start()-1].isspace())
        # Commas before another explicit slot separate details, not addresses.
        for m in re.finditer(r',\s*(?=(?:pickup|drop|destination|vehicle|passengers?|today|tomorrow)\b)',self.scan[a:b],re.I):stop.append(a+m.start())
        if stop:b=min(b,min(stop))
        value=self.clean_place(self.raw[a:b],role)
        if not value:return
        if re.search(r'\bor\b|அல்லது|\balladhu\b',self.raw[a:b],re.I):
            if commit:self.conflicts[role]='More than one location stated'
            return
        span=self.raw[a:b].strip()
        if commit:self.accept(role,value,span,source)
        return value,span

    def route(self):
        for match in _TIME.finditer(self.scan):self.noise.append(match.span())
        for ca,cb in clause_ranges(self.scan):
            part=self.scan[ca:cb]
            # A bare "A to B" is a route only when BOTH sides validate as
            # places. Do not turn "change Bike to Mini" into a location update.
            explicit=any(pattern.search(part) for pattern in (_EN_FROM,_TA_FROM,_ROMAN_FROM,_TA_PICKUP_LABEL,_TA_DROP_LABEL))
            explicit=explicit or any(normalize(m[0])!='to' for m in _EN_TO.finditer(part))
            labelled=bool(re.search(r'\b(?:destination|drop|pickup)\b',part,re.I))
            if not explicit and not labelled and not _CORRECTION.search(part):
                joins=list(re.finditer(r'(?<![a-z])to(?![a-z])\s*',part,re.I))
                if len(joins)==1:
                    join=joins[0]
                    pickup=self.add_place('pickup',ca,ca+join.start(),ca,prefix=True,commit=False)
                    destination=self.add_place('destination',ca+join.end(),cb,ca,commit=False)
                    name_like=lambda item:bool(item and (place_key(item[1]) in self.places or not _SENTENCE_WORDS.search(item[1])))
                    if name_like(pickup) and name_like(destination):
                        self.accept('pickup',*pickup)
                        self.accept('destination',*destination)
            prefixes=[]
            for role,pattern in (('pickup',_EN_FROM),('destination',_EN_TO),('pickup',_TA_PICKUP_LABEL),('destination',_TA_DROP_LABEL)):
                for m in pattern.finditer(part):
                    if role=='destination' and normalize(m[0])=='to':
                        allowed=bool(_EN_FROM.search(part) or re.search(r'\b(?:go|going|travel|ride|take)\b',part[:m.start()],re.I) or not part[:m.start()].strip() or self.state.get('stage')=='destination')
                        if not allowed:continue
                    prefixes.append((ca+m.start(),ca+m.end(),role))
            prefixes.sort()
            for index,(start,end,role) in enumerate(prefixes):
                finish=prefixes[index+1][0] if index+1<len(prefixes) else cb
                self.add_place(role,end,finish,ca)
            # Tamil/Tanglish express FROM after the pickup name, often attached.
            suffixes=sorted((ca+m.start(),ca+m.end()) for pat in (_TA_FROM,_ROMAN_FROM) for m in pat.finditer(part))
            # Prefer the widest operator when patterns overlap.
            unique=[]
            for a,b in suffixes:
                if unique and a<unique[-1][1]:
                    if b>unique[-1][1]:unique[-1]=(unique[-1][0],b)
                else:unique.append((a,b))
            for start,end in unique:
                left=ca
                prior_to=[ca+m.end() for m in _TO_SUFFIX.finditer(part) if ca+m.end()<=start]
                prior_pickup=[b for a,b,role in prefixes if role=='pickup' and b<=start]
                if prior_to or prior_pickup:left=max([left]+prior_to+prior_pickup)
                # A prior TO/destination phrase ends at its travel verb.
                previous_go=[m.end() for m in _GO.finditer(self.scan,ca,start)]
                if previous_go:left=max(previous_go)
                # Keep the inflected word in evidence for exact alias lookup.
                self.add_place('pickup',left,end,ca,prefix=True)
                right=min([p[0] for p in prefixes if p[0]>=end]+[cb])
                self.add_place('destination',end,right,ca)
            # TO may be an attached case suffix, or a destination followed by "go".
            for m in _TO_SUFFIX.finditer(part):
                a,b=ca+m.start(),ca+m.end()
                if not (_GO.search(part) or unique or self.state.get('stage')=='destination'):continue
                left=max([end for start,end in unique if end<=a]+[ca])
                self.add_place('destination',left,b,ca,prefix=True)
            for m in _GO.finditer(part):
                if not re.match(r'(?i)(?:poga|ponum|porom|போக|செல்ல)',m[0]):continue
                end=ca+m.start();left=max([b for a,b in unique if b<=end]+[ca])
                if 'destination' not in self.updates:self.add_place('destination',left,end,ca,prefix=True)

    def parse(self,use_qwen=False):
        norm=normalize(self.raw)
        excluded=self.engine.get('POSITIVE',set())|self.engine.get('NEGATIVE',set())
        if not norm or norm in excluded:return self.result()
        self.count();self.vehicle();self.route()
        stage=self.state.get('stage')
        if stage in ('pickup','destination') and stage not in self.updates and not self.updates and not self.conflicts and not _TIME.search(self.scan):
            value=self.clean_place(self.raw,stage)
            if value:self.accept(stage,value,self.raw,'rule')
        missing=[key for key in _KEYS if key not in self.updates and not self.state.get(key) and key not in self.conflicts]
        extractor=getattr(self.bridge,'_wx_context_extract',None)
        if use_qwen and missing and callable(extractor) and len(self.raw.split())>=5:
            try:proposed=extractor(self.raw,copy.deepcopy(self.state)) or {}
            except Exception:proposed={}
            if isinstance(proposed,dict):
                for role in ('pickup','destination'):
                    span=proposed.get(role)
                    if role not in missing or not isinstance(span,str) or normalize(span) not in norm:continue
                    value=self.clean_place(span,role)
                    if value:self.accept(role,value,span,'qwen_validated_span',0.85)
                span=proposed.get('passengers_text')
                group_cue=re.search(r'\b(?:people|persons?|passengers?|pax|peru|per)\b|பேர்|பேரு|பயணிகள்|நபர்',self.scan,re.I)
                if 'count' in missing and group_cue and isinstance(span,str) and normalize(span) and normalize(span) in norm:
                    n=number_words(self.engine).get(normalize(span))
                    if n is not None:self.accept('count',n,span,'qwen_validated_span',0.85)
        return self.result()

    def result(self):
        return {'updates':dict(self.updates),'evidence':copy.deepcopy(self.evidence),'ambiguities':dict(self.conflicts)}

def extract_fields(bridge,text,state=None,use_qwen=False,engine=None):
    """Read-only diagnostic using exactly the same parser as the live collector."""
    return Parser(bridge,state or {},text,engine if engine is not None else _ENGINE).parse(use_qwen)

def collect_details(bridge,state,text):
    if state.get('mode')=='cancel' or state.get('stage') in ('done','booking_pending','cancel_pending','cancel_select','cancel_confirm'):
        return {'updates':{},'changed':[],'evidence':{},'ambiguities':{}}
    parsed=extract_fields(bridge,text,state,use_qwen=True)
    updates=parsed['updates'];conflicts=state.setdefault('_wx_slot_conflicts',{})
    conflicts.update(parsed['ambiguities']);changed=[]
    for key in parsed['ambiguities']:
        if key in ('count','pickup','destination') and state.get(key) is not None:
            state[key]=None;changed.append(key)
            if key in ('pickup','destination'):state[key+'_geo']=None
    for key,value in updates.items():
        conflicts.pop(key,None)
        if state.get(key)!=value:
            state[key]=value;changed.append(key)
            if key in ('pickup','destination'):state[key+'_geo']=None
    if changed:
        state['fare']=None;state.pop('pending',None);state.pop('suggested_destination',None)
    state.setdefault('_wx_slot_evidence',{}).update(parsed['evidence'])
    if str(text).strip():state['_wx_turns']=(state.get('_wx_turns',[])+[{'input':str(text),'updates':updates}])[-30:]
    return {**parsed,'changed':changed,'ambiguities':copy.deepcopy(conflicts)}

collect_details._movio_shared_group_slots=VERSION
