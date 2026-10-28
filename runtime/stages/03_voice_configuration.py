import importlib.util, sys

def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, str(file))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

adapter = load_module('movio_original_tts_adapter',
                      TARGET / 'integrations/movio_original_tts_adapter.py')
movio_tts = adapter.OriginalMovioTTS(globals())
print('Original MOVIO TTS adapter ready.')

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from transformers.utils import is_bitsandbytes_available

if not torch.cuda.is_available():
    raise RuntimeError('Enable a GPU in Kaggle Settings.')
if globals().get('llm_model') is not None and globals().get('llm_tokenizer') is not None:
    print('Reusing the existing Qwen model and tokenizer.')
else:
    if not is_bitsandbytes_available():
        raise RuntimeError('bitsandbytes is unavailable. Restart the Kaggle session after installation, then rerun.')
    MODEL_NAME = 'Qwen/Qwen2.5-3B-Instruct'
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True
    )
    llm_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, token=HF_TOKEN)
    llm_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, token=HF_TOKEN, quantization_config=quant_config,
        device_map='auto', dtype=torch.float16, low_cpu_mem_usage=True
    ).eval()
    print('Qwen loaded successfully.')

import re
import psutil

def listener_pids(port):
    return sorted({c.pid for c in psutil.net_connections(kind='inet')
                   if c.status == 'LISTEN' and c.laddr.port == port and c.pid})

voice_active = globals().get('voice_server_thread')
if voice_active is not None and voice_active.is_alive():
    if globals().get('bridge') is None:
        raise RuntimeError('An existing voice thread has no bridge variable. Use its original notebook session.')
    print('Reusing the live Sarvam backend in this session.')
else:
    if listener_pids(8000):
        raise RuntimeError('Port 8000 is occupied by another service. Use the notebook that owns it.')
    bridge = load_module('ai_call_sarvam', TARGET / 'integrations/ai_call_sarvam.py')

# Apply the sedan alias patch once; repeated execution cannot create recursion.
if not hasattr(bridge, '_movio_original_vehicle'):
    bridge._movio_original_vehicle = bridge.vehicle

def movio_vehicle_fixed(text, *args, **kwargs):
    if isinstance(text, str) and re.search(
        r'\b(?:sedan|sudden|sadan|se dan)\b|செடான்|சிடான்', text, re.IGNORECASE
    ):
        return 'Sedan'
    return bridge._movio_original_vehicle(text, *args, **kwargs)

bridge.vehicle = movio_vehicle_fixed
print('Sarvam backend ready:', bridge.app.title)

assert bridge.VOICE_PATCH_VERSION == '5.2', 'Voice patch 5.2 was not installed'

import threading, time, requests, uvicorn
def configure_bridge(public_url):
    bridge.configure(
        public_url, tts=movio_tts, preprocessing=None,
        llm=llm_model, tokenizer=llm_tokenizer,
        reference_wav=REFERENCE_TAMIL, sarvam_key=SARVAM_API_KEY
    )
configure_bridge("")
import re
import json
import torch
import unicodedata

if globals().get("bridge") is None:
    raise RuntimeError("Initialize the voice bridge first.")

if bridge.LLM is None or bridge.TOKENIZER is None:
    raise RuntimeError("Load and configure Qwen before running this cell.")

# Capture the existing functions once.
if not hasattr(bridge, "_context_original_handle"):
    bridge._context_original_handle = bridge.handle
    bridge._context_original_fare = bridge.road_fare

def context_normalize(text):
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return re.sub(r"\s+", " ", text).strip()

def context_is_stated(value, message):
    """Accept a text slot only when it occurs in this reply."""
    return (
        isinstance(value, str)
        and bool(value.strip())
        and context_normalize(value) in context_normalize(message)
    )

def context_extract(message, session):
    known = {
        key: session.get(key)
        for key in ("count", "vehicle", "pickup", "destination", "when")
    }

    instruction = """
Extract explicitly stated taxi-booking details from the NEW MESSAGE.
The message may be English, Tamil or Tanglish.

Return exactly one JSON object:
{
  "passengers_text": null,
  "vehicle": null,
  "pickup": null,
  "destination": null,
  "time": null
}

Rules:
- passengers_text: copy the passenger number/words from the message.
- vehicle: Bike, Auto, Mini, Sedan or SUV; only if explicitly selected.
- "cab", "taxi" or "car" alone does NOT select Mini.
- pickup, destination and time: copy exact spans from the NEW MESSAGE.
- Never invent, translate, correct or replace a place name.
- Do not copy already-known values into the output.
- An explicit correction replaces the corresponding known value.
- Use the current question to interpret a short answer.
- If a detail is absent or ambiguous, return null.
- Return JSON only.
"""

    prompt = (
        instruction
        + "\nKNOWN DETAILS: "
        + json.dumps(known, ensure_ascii=False)
        + "\nCURRENT QUESTION SLOT: "
        + str(session.get("stage"))
        + "\nNEW MESSAGE: "
        + message
    )

    with bridge.LOCK, torch.inference_mode():
        inputs = bridge.TOKENIZER.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )

        device = next(bridge.LLM.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}

        output = bridge.LLM.generate(
            **inputs,
            max_new_tokens=220,
            do_sample=False,
            pad_token_id=bridge.TOKENIZER.eos_token_id,
        )

        generated = bridge.TOKENIZER.decode(
            output[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

    match = re.search(r"\{.*?\}", generated, re.S)
    if not match:
        return {}

    try:
        result = json.loads(match.group())
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        return {}

def context_next_question(session):
    count = session.get("count")
    vehicle = session.get("vehicle")

    if count and vehicle and count > bridge.CAPACITY[vehicle]:
        session["vehicle"] = None
        session["stage"] = "vehicle"
        return (
            bridge.say(
                session,
                "capacity",
                vehicle=vehicle,
                max=bridge.CAPACITY[vehicle],
            )
            + " "
            + bridge.say(session, "vehicle")
        )

    for slot, stage in (
        ("count", "count"),
        ("vehicle", "vehicle"),
        ("pickup", "pickup"),
        ("destination", "destination"),
        ("when", "time"),
    ):
        if not session.get(slot):
            session["stage"] = stage
            return bridge.say(session, stage)

    # Existing WebSocket code calculates fare and reads the summary.
    session["stage"] = "fare"
    return bridge.say(session, "wait")

def context_handle(session, text):
    text = str(text).strip()
    stage = session.get("stage")

    # Preserve the existing cancellation and account-save flow.
    if session.get("mode") == "cancel" or stage in (
        "cancel_select", "cancel_confirm",
        "booking_pending", "cancel_pending", "done",
    ):
        return bridge._context_original_handle(session, text)

    # Only a short explicit confirmation can submit the booking.
    simple_reply = re.sub(
        r"[^\w\s]", "", context_normalize(text)
    ).strip()

    confirmation_replies = {
        "yes", "yeah", "yep", "yes please", "confirm",
        "book it", "go ahead", "okay", "ok",
        "no", "nope", "cancel", "dont book", "do not book",
        "ஆம்", "ஆமாம்", "ஆமா", "சரி", "இல்லை", "வேண்டாம்",
        "aama", "aamam", "seri", "sari", "illai", "vendam",
    }

    if stage == "confirm" and simple_reply in confirmation_replies:
        return bridge._context_original_handle(session, text)

    # Preserve previously collected details.
    try:
        extracted = context_extract(text, session)
    except Exception as error:
        print("Context extraction failed:", type(error).__name__)
        return bridge.say(session, "retry"), None

    changed = False

    passenger_span = extracted.get("passengers_text")
    if context_is_stated(passenger_span, text):
        count = bridge.number(passenger_span)
        if count and 1 <= count <= 20:
            changed |= session.get("count") != count
            session["count"] = count

    selected_vehicle = extracted.get("vehicle")
    detected_vehicle = bridge.vehicle(text)

    explicit_mini = bool(
        re.search(r"(?i)\bmini\b|மினி", text)
    )

    if (
        selected_vehicle in bridge.CAPACITY
        and selected_vehicle == detected_vehicle
        and (selected_vehicle != "Mini" or explicit_mini)
    ):
        changed |= session.get("vehicle") != selected_vehicle
        session["vehicle"] = selected_vehicle

    for extracted_key, slot in (
        ("pickup", "pickup"),
        ("destination", "destination"),
        ("time", "when"),
    ):
        value = extracted.get(extracted_key)

        if context_is_stated(value, text):
            value = value.strip()

            if session.get(slot) != value:
                session[slot] = value
                changed = True

                if slot in ("pickup", "destination"):
                    session[slot + "_geo"] = None

    if changed:
        session["fare"] = None
        session.pop("pending", None)
        session.pop("suggested_destination", None)

    if stage == "confirm" and not changed:
        # An unclear reply does not create a booking.
        return bridge.say(session, "retry"), None

    return context_next_question(session), None

def context_road_fare(session):
    # Resolve locations only after all booking details are available.
    for slot in ("pickup", "destination"):
        if not session.get(slot + "_geo"):
            geo = bridge.geocode(session[slot])
            if not geo:
                return None
            session[slot + "_geo"] = geo

    return bridge._context_original_fare(session)

bridge.handle = context_handle
bridge.road_fare = context_road_fare

print("Context-aware booking enabled for English, Tamil and Tanglish.")
print("Close the current call and start a new call.")