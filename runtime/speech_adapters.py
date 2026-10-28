"""Runtime-only speech configuration; no project-file rewriting."""

def configure_wordwise_speech():
    import base64
    import contextvars
    import inspect
    import re
    import threading
    from collections import deque

    b = globals().get("bridge")
    adapter = getattr(b, "TTS", None)
    ns = getattr(adapter, "ns", None)
    wx = getattr(
        getattr(b, "_wx_endpoint", None),
        "__globals__",
        {},
    )

    if (
        not isinstance(ns, dict)
        or not callable(wx.get("speech_numeric_normalize"))
    ):
        raise RuntimeError(
            "Run your existing voice/weather activation first."
        )

    if getattr(b, "_tg_wordwise_v2", False):
        print("Word-by-word Tanglish speech is already enabled.")
        return

    # Bypass the earlier whole-sentence translation wrapper.
    base_synthesize = adapter.synthesize

    if getattr(b, "_tanglish_native_speech_v1", False):
        enclosed = inspect.getclosurevars(
            base_synthesize
        ).nonlocals

        required = (
            "original_synthesize",
            "speech_text",
            "active",
        )

        if not all(key in enclosed for key in required):
            raise RuntimeError(
                "Unexpected TTS wrapper. No changes were installed."
            )

        base_synthesize = enclosed["original_synthesize"]

    active = contextvars.ContextVar(
        "movio_tanglish_wordwise",
        default=False,
    )

    lock = threading.RLock()
    places = set(getattr(b, "VOICE_PLACE_ALIASES", {}))

    if not hasattr(b, "TANGLISH_SPEECH_LOG"):
        b.TANGLISH_SPEECH_LOG = deque(maxlen=50)

    # Preserve English vocabulary as English.
    english = set((
        "ai taxi booking service welcome help ride book existing "
        "cancel travel pickup drop place correct yes no vehicle "
        "road distance around approximate fare confirm details "
        "passengers passenger kilometres kilometers rupees driver "
        "mini car bike auto sedan suv am pm otp id number request "
        "record save select screen map route verify continue "
        "rain chance forecast please check change retry "
        "tomorrow today morning evening night"
    ).split())

    words = {
        str(key).lower(): str(value)
        for key, value in ns.get("TANGLISH_WORDS", {}).items()
        if (
            re.search(r"[\u0b80-\u0bff]", str(value))
            and str(key).lower() not in english
        )
    }

    # Tamil-origin words: change script, retain the wording.
    words.update(dict(
        vanakkam="வணக்கம்",
        ungalukku="உங்களுக்கு",
        unga="உங்க",
        ungal="உங்கள்",
        eppadi="எப்படி",
        pannalaam="பண்ணலாம்",
        pannalaama="பண்ணலாமா",
        pannalama="பண்ணலாமா",
        pannunga="பண்ணுங்க",
        panna="பண்ண",
        pannanuma="பண்ணணுமா",
        pannum="பண்ணும்",
        neenga="நீங்க",
        naan="நான்",
        enakku="எனக்கு",
        ku="க்கு",
        la="ல",
        ah="ஆ",
        ethana="எத்தனை",
        peru="பேர்",
        poreenga="போறீங்க",
        enga="எங்க",
        endha="எந்த",
        naal="நாள்",
        manikku="மணிக்கு",
        venum="வேணும்",
        poganum="போகணும்",
        irundhu="இருந்து",
        ilirundhu="இலிருந்து",
        sonna="சொன்ன",
        illa="இல்ல",
        illai="இல்லை",
        sollunga="சொல்லுங்க",
        sariya="சரியா",
        kekkala="கேட்கல",
        thirumba="திரும்ப",
        marubadiyum="மறுபடியும்",
        nimisham="நிமிஷம்",
        oru="ஒரு",
        panren="பண்றேன்",
        aayiduchu="ஆயிடுச்சு",
        innum="இன்னும்",
        aagala="ஆகல",
        nandri="நன்றி",
        payanam="பயணம்",
        inimaiyaaga="இனிமையாக",
        amaiyattum="அமையட்டும்",
        irukku="இருக்கு",
        irukkura="இருக்குற",
        irukkum="இருக்கும்",
        innaiku="இன்னைக்கு",
        inniku="இன்னைக்கு",
        naalaiku="நாளைக்கு",
        mazhai="மழை",
        vaaippu="வாய்ப்பு",
        thodaralaama="தொடரலாமா",
        munpadhivu="முன்பதிவு",
        munpadhivai="முன்பதிவை",
        vivaram="விவரம்",
        urudhi="உறுதி",
        seiyyalaama="செய்யலாமா",
        varai="வரை",
        madhippidappatta="மதிப்பிடப்பட்ட",
        kattanam="கட்டணம்",
        saalai="சாலை",
        dhooram="தூரம்",
    ))

    # Weather and correction vocabulary.
    words.update(dict(
        indha="இந்த", andha="அந்த", alladhu="அல்லது",
        adhigamaaga="அதிகமாக", irukka="இருக்க",
        irukkalaam="இருக்கலாம்", irukkiradhu="இருக்கிறது",
        irundhaalum="இருந்தாலும்", vaanilai="வானிலை",
        vaanilaiyil="வானிலையில்", vaanam="வானம்",
        kanamazhai="கனமழை", megamoottam="மேகமூட்டம்",
        idiyudan="இடியுடன்", koodiya="கூடிய",
        edhirpaarkkappadugiradhu="எதிர்பார்க்கப்படுகிறது",
        edhirpaarkkappadugindrana="எதிர்பார்க்கப்படுகின்றன",
        therndhedutha="தேர்ந்தெடுத்த", purappadum="புறப்படும்",
        serum="சேரும்", payana="பயண", nerathil="நேரத்தில்",
        nerathirkaana="நேரத்திற்கான", idam="இடம்",
        idamaana="இடமான", idathil="இடத்தில்",
        pagudhiyil="பகுதியில்", mazhaikkaana="மழைக்கான",
        peiya="பெய்ய", madhippeedu="மதிப்பீடு",
        munnarivippu="முன்னறிவிப்பு",
        kidaikkavillai="கிடைக்கவில்லை", thodaralaam="தொடரலாம்",
        neengalum="நீங்களும்", udaimaigalum="உடைமைகளும்",
        udaimaigalai="உடைமைகளை", mazhaiyil="மழையில்",
        mazhaiyilirundhu="மழையிலிருந்து", mazhaikku="மழைக்கு",
        nanaiyaamal="நனையாமல்", thevaiyaana="தேவையான",
        munnerpaadugalai="முன்னேற்பாடுகளை",
        seidhukollunga="செய்துகொள்ளுங்க", kudai="குடை",
        kudineer="குடிநீர்", eduthukkondu="எடுத்துக்கொண்டு",
        paadhugaathukkollunga="பாதுகாத்துக்கொள்ளுங்க",
        vandiyil="வண்டியில்", erumboadhum="ஏறும்போதும்",
        irangumboadhum="இறங்கும்போதும்",
        payanpadutha="பயன்படுத்த", etra="ஏற்ற", ena="என",
        nandraagave="நன்றாகவே", veppanilai="வெப்பநிலை",
        veppathirku="வெப்பத்திற்கு", pakkavaatil="பக்கவாட்டில்",
        padalaam="படலாம்", aattovin="Auto-வின்",
        baikku="Bike", baikkileye="Bike-லேயே",
        poruthamillaamal="பொருத்தமில்லாமல்",
        virumbinaal="விரும்பினால்", moodiya="மூடிய",
        vandiyai="வண்டியை", pondra="போன்ற",
        therndhedukkalaam="தேர்ந்தெடுக்கலாம்",
        mudivu="முடிவு", ungaludaiyadhu="உங்களுடையது",
        pira="பிற", nilaimaigal="நிலைமைகள்",
        payanathirku="பயணத்திற்கு", mun="முன்",
        ulloor="உள்ளூர்", thagavalgalai="தகவல்களை",
        paarunga="பாருங்க", thelivaaga="தெளிவாக",
        vivarangal="விவரங்கள்", vivarangalai="விவரங்களை",
        vivarathai="விவரத்தை", enn="எண்",
        ennikkaiyai="எண்ணிக்கையை", mudhal="முதல்",
        meendum="மீண்டும்", maatra="மாற்ற",
        maathunga="மாத்துங்க", sollalaam="சொல்லலாம்",
        muyarchikka="முயற்சிக்க",
        tharkaaligamaaga="தற்காலிகமாக",
        uruvaakkappadavillai="உருவாக்கப்படவில்லை",
        seiyyavum="செய்யவும்", seiyyunga="செய்யுங்க",
        edhuvum="எதுவும்", raththu="ரத்து",
        therndhedukkavum="தேர்ந்தெடுக்கவும்",
        virumbureenga="விரும்புறீங்க",
        vandi="வண்டி", vandikku="வண்டிக்கு",
        payanigal="பயணிகள்", payanigalukku="பயணிகளுக்கு",
        korikkai="கோரிக்கை", padhivu="பதிவு",
        seiyyappattadhu="செய்யப்பட்டது", sumaar="சுமார்",
    ))

    pattern = re.compile(
        r"(?<![A-Za-z])("
        + "|".join(
            re.escape(key)
            for key in sorted(words, key=len, reverse=True)
        )
        + r")(?![A-Za-z])",
        re.I,
    )

    def speech_text(text):
        text = str(text)

        with lock:
            protected_places = sorted(
                places, key=len, reverse=True
            )

        protected = {}

        for name in protected_places:
            if name and name in text:
                marker = chr(0xF000 + len(protected))
                text = text.replace(name, marker)
                protected[marker] = name

        text = pattern.sub(
            lambda match: words[match[0].lower()],
            text,
        )

        for marker, name in protected.items():
            text = text.replace(marker, name)

        text = re.sub(
            r"(?i)\bkilo\s+meettar\b|\bkm\b",
            "kilometers",
            text,
        )

        # Standardize time suffixes before number verbalization.
        text = re.sub(
            r"(?i)\b(\d{1,2}(?::\d{2})?)\s*(AM|PM)\b",
            lambda match: (
                match[1] + " " + match[2].upper()
            ),
            text,
        )

        # English numbers: thirty five point four, etc.
        text = wx["speech_numeric_normalize"](
            lambda value: value,
            text,
            "English",
        )

        # Speech-only pronunciation aliases.
        text = re.sub(
            r"\b(?:SUV|S\s+U\s+V|es yoo vee)\b",
            "ess you vee",
            text,
            flags=re.I,
        )

        aliases = {
            "AI": "ay eye",
            "AM": "ay em",
            "PM": "pee em",
            "OTP": "oh tee pee",
            "ID": "eye dee",
        }

        text = re.sub(
            r"\b(?:AI|AM|PM|OTP|ID)\b",
            lambda match: aliases[match[0]],
            text,
        )

        return re.sub(r"\s+", " ", text).strip()

    # Prevent the old normalizer from translating this speech copy.
    targets = [ns]

    prepare_globals = getattr(
        ns.get("prepare_movio_request"),
        "__globals__",
        None,
    )

    if (
        isinstance(prepare_globals, dict)
        and prepare_globals is not ns
    ):
        targets.append(prepare_globals)

    if not all(
        callable(target.get("normalize_taxi_text"))
        for target in targets
    ):
        raise RuntimeError(
            "The original TTS normalizer is missing. "
            "No changes were installed."
        )

    for target in targets:
        previous = target["normalize_taxi_text"]

        def normalize(text, _previous=previous):
            if active.get():
                return str(text)
            return _previous(text)

        target["normalize_taxi_text"] = normalize

    def synthesize(text, group):
        if b.CURRENT_LANGUAGE.get() != "Tanglish":
            return base_synthesize(text, group)

        spoken = speech_text(text)

        b.TANGLISH_SPEECH_LOG.append({
            "version": "wordwise-v2",
            "source_text": str(text),
            "tts_text": spoken,
        })

        token = active.set(True)

        try:
            return base_synthesize(spoken, "TANGLISH")
        finally:
            active.reset(token)

    previous_speak = b.speak

    def speak(text):
        if b.CURRENT_LANGUAGE.get() != "Tanglish":
            return previous_speak(text)

        with b.LOCK:
            data = adapter.synthesize(
                str(text), "TANGLISH"
            )

        return base64.b64encode(data).decode()

    # Restore the conversational mixed-language summary.
    previous_summary = wx["summary_text"]

    def summary(bridge_object, state):
        if state.get("lang") != "Tanglish":
            return previous_summary(bridge_object, state)

        with lock:
            places.update(
                str(state[key])
                for key in ("pickup", "destination")
                if state.get(key)
            )

        date = wx["spoken_datetime"](
            state["pickup_at"], "English"
        )
        km = wx["numeric_text"](state["fare"]["km"])
        fare = wx["numeric_text"](
            state["fare"]["fare"], 0
        )

        return (
            f"Booking details: {int(state['count'])} peru, "
            f"{state['vehicle']}, "
            f"{state['pickup']} la irundhu "
            f"{state['destination']} ku, {date}. "
            f"Road distance around {km} kilometers, "
            f"approximate fare {fare} rupees. "
            "Confirm pannalama? Yes illa no sollunga."
        )

    wx["summary_text"] = summary

    if callable(wx.get("weather_question")):
        previous_question = wx["weather_question"]

        def weather_question(lang):
            if lang == "Tanglish":
                return "Booking continue pannalama?"
            return previous_question(lang)

        wx["weather_question"] = weather_question

    previous_completion = wx["completion_message"]

    def completion(lang, ride_id):
        if lang != "Tanglish":
            return previous_completion(lang, ride_id)

        return (
            "Unga booking request save aayiduchu. "
            f"Booking number {int(ride_id)}. "
            "Nandri! Unga payanam inimaiyaaga amaiyattum!"
        )

    wx["completion_message"] = completion

    b.MESSAGES["Tanglish"]["hello"] = (
        "Vanakkam! AI taxi booking service ku welcome. "
        "Ungalukku eppadi help pannalaam?"
    )

    adapter.synthesize = synthesize
    b.speak = speak
    b.tanglish_speech_text = speech_text
    b._tg_wordwise_v2 = True

    print("Conversational Tanglish speech enabled.")
    print("SUV → ess you vee | AM → ay em | PM → pee em")
    print("35.4 → thirty five point four")
    print("Close the old popup and start a NEW Tanglish call.")


def configure_audio_profiles():
    import base64
    import contextvars
    import inspect
    import io
    import threading
    import wave
    from collections import OrderedDict, deque
    import numpy as np

    b = globals().get("bridge")
    adapter = getattr(b, "TTS", None)
    ns = getattr(adapter, "ns", None)
    wx = getattr(
        getattr(b, "_wx_endpoint", None),
        "__globals__",
        {},
    )

    required = (
        "advisory",
        "completion_message",
        "speech_segments",
        "tts_reply",
    )

    if (
        not isinstance(ns, dict)
        or not callable(getattr(adapter, "synthesize", None))
        or not all(callable(wx.get(key)) for key in required)
    ):
        raise RuntimeError(
            "Run your current voice/weather activation "
            "and earlier fixes first."
        )

    if getattr(b, "_wx_stable_audio_v1", False):
        print("Weather/closing audio patch is already enabled.")
        return

    original_stream = ns.get("movio_stream_response")

    if not callable(original_stream):
        raise RuntimeError("The original TTS stream is unavailable.")

    stream_globals = getattr(
        original_stream, "__globals__", {}
    )
    scheduler = stream_globals.get(
        "SCHEDULER", ns.get("SCHEDULER")
    )
    previous_submit = getattr(scheduler, "submit", None)

    if not callable(previous_submit):
        raise RuntimeError(
            "The existing TTS scheduler is unavailable."
        )

    submit_signature = inspect.signature(previous_submit)

    if "step" not in submit_signature.parameters:
        raise RuntimeError(
            "Unexpected scheduler signature. "
            "No changes were installed."
        )

    scope = contextvars.ContextVar(
        "movio_weather_closing_audio",
        default=None,
    )

    profiles = OrderedDict()
    registry_lock = threading.RLock()

    b.WX_SPEECH_QUALITY = {
        "weather_steps": 8,
        "closing_steps": 8,
        "min_words": 8,
    }

    # Keep the latest actual audio in memory for listening.
    b.WX_SPEECH_AUDIO = deque(maxlen=6)

    def register(text, kind):
        text = str(text).strip()

        with registry_lock:
            profiles[text] = kind
            profiles.move_to_end(text)

            while len(profiles) > 256:
                profiles.popitem(last=False)

        return text

    def profile_for(text):
        text = str(text).strip()

        with registry_lock:
            candidates = list(profiles.items())

        for prefix, kind in reversed(candidates):
            if (
                text == prefix
                or text.startswith(prefix + "\n")
                or text.startswith(prefix + " ")
            ):
                return kind

        return None

    previous_advisory = wx["advisory"]
    previous_completion = wx["completion_message"]
    previous_segments = wx["speech_segments"]
    previous_tts = wx["tts_reply"]
    previous_say = getattr(b, "say", None)
    previous_speak = b.speak

    def advisory(state):
        return register(
            previous_advisory(state),
            "weather",
        )

    def completion(lang, ride_id):
        return register(
            previous_completion(lang, ride_id),
            "closing",
        )

    def segments(text):
        if profile_for(text):
            return [str(text).strip()]

        return previous_segments(text)

    def say(state, key, **values):
        text = previous_say(state, key, **values)

        if key in ("cancelled", "confirmed"):
            return register(text, "closing")

        return text

    # Give short chunks neighbouring text for context.
    # Every normalized word remains in the synthesis plan.
    def wrap_prepare(previous):
        def prepare(*args, **kwargs):
            plan = previous(*args, **kwargs)

            if scope.get() is None:
                return plan

            chunks = plan.get("chunks", [])

            if not chunks:
                raise RuntimeError(
                    "The TTS plan contains no speech chunks."
                )

            result = []
            pending = ""

            minimum = max(
                6,
                int(b.WX_SPEECH_QUALITY["min_words"]),
            )

            for chunk in chunks:
                pending = (
                    pending + " " + str(chunk).strip()
                ).strip()

                if len(pending.split()) >= minimum:
                    result.append(pending)
                    pending = ""

            if pending:
                if result and len(pending.split()) < 4:
                    result[-1] += " " + pending
                else:
                    result.append(pending)

            return {**plan, "chunks": result}

        return prepare

    targets = [ns]

    if stream_globals is not ns:
        targets.append(stream_globals)

    preparations = [
        (target, target.get("prepare_movio_request"))
        for target in targets
    ]

    if not any(
        callable(previous)
        for _, previous in preparations
    ):
        raise RuntimeError(
            "The existing TTS preparation function is missing."
        )

    # Apply extra steps only inside weather/closing synthesis.
    def submit(*args, **kwargs):
        current = scope.get()

        if current is None:
            return previous_submit(*args, **kwargs)

        bound = submit_signature.bind(*args, **kwargs)
        bound.arguments["step"] = current["steps"]

        return previous_submit(
            *bound.args,
            **bound.kwargs,
        )

    class InvalidAudio(RuntimeError):
        pass

    def stream(*args, **kwargs):
        for event in original_stream(*args, **kwargs):
            current = scope.get()

            if current is not None:
                audio = np.asarray(event["audio"])

                if (
                    not audio.size
                    or not np.isfinite(audio).all()
                ):
                    raise InvalidAudio(
                        "TTS returned empty or nonfinite audio."
                    )

                current["chunks"].append(
                    event.get("chunk_text", "")
                )
                current.setdefault(
                    "model_text",
                    event.get("normalized", ""),
                )

            yield event

    def clean_wav(payload):
        try:
            raw = base64.b64decode(payload)

            with wave.open(io.BytesIO(raw), "rb") as reader:
                if (
                    reader.getsampwidth() != 2
                    or reader.getnchannels() != 1
                ):
                    raise InvalidAudio(
                        "Expected mono PCM16 TTS audio."
                    )

                rate = reader.getframerate()

                audio = np.frombuffer(
                    reader.readframes(reader.getnframes()),
                    dtype="<i2",
                ).astype(np.float32) / 32768

        except (wave.Error, EOFError, ValueError) as error:
            raise InvalidAudio(
                "TTS did not return a usable WAV."
            ) from error

        if (
            rate <= 0
            or len(audio) < rate * 0.06
            or not np.isfinite(audio).all()
        ):
            raise InvalidAudio(
                "Invalid or incomplete TTS waveform."
            )

        peak = float(np.max(np.abs(audio)))

        if peak < 1e-5:
            raise InvalidAudio("TTS returned silent audio.")

        # Reduce excessive peaks; never amplify quiet audio.
        if peak > 0.92:
            audio *= 0.92 / peak

        # Short fades soften start/end clicks without trimming words.
        fade = min(
            int(rate * 0.004),
            len(audio) // 2,
        )

        if fade:
            audio[:fade] *= np.linspace(0, 1, fade)
            audio[-fade:] *= np.linspace(1, 0, fade)

        output = io.BytesIO()

        with wave.open(output, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(rate)
            writer.writeframes(
                (
                    np.clip(audio, -1, 1) * 32767
                ).astype("<i2").tobytes()
            )

        return (
            output.getvalue(),
            rate,
            len(audio) / rate,
        )

    def tts_reply(bridge_object, text):
        kind = profile_for(text)

        # Final confirmation follows its existing path.
        if kind is None:
            return previous_tts(bridge_object, text)

        steps = max(
            4,
            min(
                32,
                int(
                    b.WX_SPEECH_QUALITY[
                        kind + "_steps"
                    ]
                ),
            ),
        )

        # Retry unusable audio once with more generation steps.
        for attempt_steps in (steps, max(16, steps)):
            current = {
                "steps": attempt_steps,
                "chunks": [],
            }
            token = scope.set(current)

            try:
                payload = previous_tts(
                    bridge_object, text
                )
                wav, rate, duration = clean_wav(payload)

                b.WX_SPEECH_AUDIO.append({
                    "kind": kind,
                    "language": b.CURRENT_LANGUAGE.get(),
                    "text": str(text),
                    "model_text": current.get(
                        "model_text", ""
                    ),
                    "steps": attempt_steps,
                    "chunks": current["chunks"],
                    "sample_rate": rate,
                    "duration_s": duration,
                    "wav": wav,
                })

                return base64.b64encode(wav).decode()

            except InvalidAudio:
                if attempt_steps == max(16, steps):
                    raise

            finally:
                scope.reset(token)

    def speak(text):
        if profile_for(text):
            return tts_reply(b, text)

        return previous_speak(text)

    for target, previous in preparations:
        if callable(previous):
            target["prepare_movio_request"] = (
                wrap_prepare(previous)
            )

    scheduler.submit = submit
    ns["movio_stream_response"] = stream

    wx.update(
        advisory=advisory,
        completion_message=completion,
        speech_segments=segments,
        tts_reply=tts_reply,
    )

    if callable(previous_say):
        b.say = say

    b.speak = speak
    b._wx_stable_audio_v1 = True

    print(
        "Installed: grouped weather/closing speech, "
        "8-step generation and WAV checks."
    )
    print(
        "Final confirmation retains its current speech settings."
    )
    print(
        "Close the old popup and start a NEW call."
    )
