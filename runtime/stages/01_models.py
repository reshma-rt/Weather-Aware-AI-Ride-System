"""Ordered runtime stage: 01_models. Run through pipeline.py only."""


# ---- Source section shared secrets ----
import os, getpass
try:
    from kaggle_secrets import UserSecretsClient
except ImportError:
    UserSecretsClient = None

client = UserSecretsClient() if UserSecretsClient else None

def secret(name):
    value = os.environ.get(name, '').strip()
    if not value:
        try:
            value = client.get_secret(name).strip()
        except Exception:
            value = ''
    if not value:
        value = getpass.getpass(f'Enter {name}: ').strip()
    if not value:
        raise ValueError(f'{name} is required')
    os.environ[name] = value
    return value

SARVAM_API_KEY = secret('SARVAM_API_KEY')
NGROK_AUTHTOKEN = secret('NGROK_AUTHTOKEN')
HF_TOKEN = secret('HF_TOKEN')
os.environ['HUGGING_FACE_HUB_TOKEN'] = HF_TOKEN
print('Sarvam, ngrok and Hugging Face secrets configured. Values are hidden.')


# ---- Source section reference assets ----

from pathlib import Path
import os
MOVIO_ASSETS = '/kaggle/working/MOVIO_TTS'
Path(MOVIO_ASSETS).mkdir(parents=True, exist_ok=True)
REFERENCE_ENGLISH = str(PIPELINE_REPO_ROOT / 'assets/references/english_reference_16k.wav')
REFERENCE_TAMIL = str(PIPELINE_REPO_ROOT / 'assets/references/tamil_reference.wav')
os.environ.setdefault('HF_HOME', str(Path(MOVIO_ASSETS) / 'huggingface_cache'))
Path(os.environ['HF_HOME']).mkdir(parents=True, exist_ok=True)


# ---- Source section runtime configuration ----
import os
import sys
import gc
import re
import time
import math
import random
import warnings
import threading
import subprocess
import importlib
import getpass
import heapq

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import torch
import torchaudio
import transformers
import soundfile as sf

from IPython.display import display, Audio, Markdown
from transformers import AutoModel

warnings.filterwarnings("ignore")

# ============================================================
# KAGGLE + HUGGING FACE AUTHENTICATION
# ============================================================

# Secrets were configured by the shared startup stage.
# ============================================================
# MOVIO MODEL CONFIGURATION
# ============================================================

MODEL_ID = "ARTPARK-IISc/DhVaani-0.5"

DEVICE = "cuda"
TARGET_SR = 24000

SEED = 666
RANDOM_SEED = 42

if not torch.cuda.is_available():
    raise RuntimeError(
        "Enable GPU in Kaggle: Settings > Accelerator > GPU"
    )

# ============================================================
# GPU OPTIMIZATION
# ============================================================

torch.backends.cudnn.benchmark = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

try:
    torch.set_float32_matmul_precision("high")
except Exception:
    pass

# ============================================================
# LATENCY + QUALITY CONFIG
# ============================================================

FIRST_CHUNK_NUM_STEP = 3
REST_CHUNK_NUM_STEP = 4

ENGLISH_SPEED = 1.12
TAMIL_SPEED = 1.12
TANGLISH_SPEED = 1.12

USE_FP16_SAMPLE = False

# ============================================================
# SHORTER SEMANTIC C1
# ============================================================

FIRST_MIN_WORDS = 2
FIRST_TARGET_WORDS = 2
FIRST_MAX_WORDS = 3

NEXT_MIN_WORDS = 3
NEXT_TARGET_WORDS = 5
NEXT_MAX_WORDS = 8

KEEP_WHOLE_IF_WORDS_LE = 4

ENGLISH_SINGLE_CHUNK_WORDS = 10
ENGLISH_MIN_CHUNK_WORDS = 4

# ============================================================
# STREAMING PRIORITIES
# ============================================================

FIRST_AUDIO_PRIORITY = 0
CONTINUATION_PRIORITY = 10

FIRST_AUDIO_DEADLINE_MS = 500.0
ADMISSION_QUEUE_LIMIT = 128

RUN_FULL_80_AUDIO_REVIEW = False

# ============================================================
# RANDOM SEEDS
# ============================================================

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ============================================================
# KAGGLE MODEL CACHE
# ============================================================

MOVIO_ASSETS = "/kaggle/working/MOVIO_TTS"

os.makedirs(MOVIO_ASSETS, exist_ok=True)

# Keep an existing cache configuration if already initialized
os.environ.setdefault(
    "HF_HOME",
    os.path.join(MOVIO_ASSETS, "huggingface_cache")
)

os.makedirs(os.environ["HF_HOME"], exist_ok=True)

# ============================================================
# RUNTIME STATUS
# ============================================================

print("=" * 88)
print("MOVIO CLEAN RUNTIME — KAGGLE")
print("=" * 88)

print("PyTorch       :", torch.__version__)
print("Transformers  :", transformers.__version__)
print("GPU           :", torch.cuda.get_device_name(0))
print("CUDA          :", torch.version.cuda)

print("Model         :", MODEL_ID)
print("Model cache   :", os.environ["HF_HOME"])

print("C1 step       :", FIRST_CHUNK_NUM_STEP)
print("Rest step     :", REST_CHUNK_NUM_STEP)
print("FP16 sample   :", USE_FP16_SAMPLE)

print("English speed :", ENGLISH_SPEED)
print("Tamil speed   :", TAMIL_SPEED)
print("Tanglish speed:", TANGLISH_SPEED)

print("HF token      :", "CONFIGURED" if HF_TOKEN else "MISSING")

print("=" * 88)
print("MOVIO RUNTIME INITIALIZED SUCCESSFULLY")
print("=" * 88)


# ---- Source section 19 ----
import os
import getpass
from huggingface_hub import login, hf_hub_download

HF_TOKEN = str(
    os.environ.get("HF_TOKEN")
    or globals().get("HF_TOKEN")
    or ""
).strip()

if not HF_TOKEN:
    try:
        from kaggle_secrets import UserSecretsClient
        HF_TOKEN = UserSecretsClient().get_secret("HF_TOKEN").strip()
    except Exception:
        HF_TOKEN = ""

if not HF_TOKEN:
    HF_TOKEN = getpass.getpass(
        "Enter your Hugging Face read token: "
    ).strip()

if not HF_TOKEN:
    raise RuntimeError("A Hugging Face token is required.")

os.environ["HF_TOKEN"] = HF_TOKEN
login(token=HF_TOKEN, add_to_git_credential=False)

# Verify access before downloading the model weights.
hf_hub_download(
    repo_id="ARTPARK-IISc/DhVaani-0.5",
    filename=".gitattributes",
    revision="b079f01592e987042b86f4a01c3909cef569d247",
    token=HF_TOKEN,
)

print("Authenticated model access verified. Rerun the model-loading cell.")


# ---- Source section 20 ----
import sys
import types
import importlib
import importlib.util
import importlib.machinery
from pathlib import Path

import torch
from transformers import AutoModel
from huggingface_hub import snapshot_download

MODEL_ID = "ARTPARK-IISc/DhVaani-0.5"
REVISION = "b079f01592e987042b86f4a01c3909cef569d247"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Find the model files already downloaded in your session
repo_dir = Path(
    snapshot_download(
        repo_id=MODEL_ID,
        revision=REVISION,
        local_files_only=False,
    )
)

backend_files = list(
    repo_dir.rglob("zipvoice/models/zipvoice.py")
)

if len(backend_files) != 1:
    raise RuntimeError(
        f"Expected one DhVaani backend, found {len(backend_files)}. "
        f"Cached model folder: {repo_dir}"
    )

package_dir = backend_files[0].parent.parent
backend_root = package_dir.parent

# Clear previous ZipVoice imports from this Python session
for name in list(sys.modules):
    if name == "zipvoice" or name.startswith("zipvoice."):
        sys.modules.pop(name, None)

backend_path = str(backend_root)
if backend_path in sys.path:
    sys.path.remove(backend_path)
sys.path.insert(0, backend_path)

# Bind 'zipvoice' specifically to DhVaani's backend
init_file = package_dir / "__init__.py"

if init_file.is_file():
    spec = importlib.util.spec_from_file_location(
        "zipvoice",
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules["zipvoice"] = package
    spec.loader.exec_module(package)
else:
    package = types.ModuleType("zipvoice")
    package.__package__ = "zipvoice"
    package.__path__ = [str(package_dir)]
    package.__spec__ = importlib.machinery.ModuleSpec(
        "zipvoice",
        loader=None,
        is_package=True,
    )
    package.__spec__.submodule_search_locations = [
        str(package_dir)
    ]
    sys.modules["zipvoice"] = package

importlib.invalidate_caches()

# Verify the backend before loading weights
backend = importlib.import_module(
    "zipvoice.models.zipvoice"
)
print("Backend found:", backend.__file__)

model = AutoModel.from_pretrained(
    MODEL_ID,
    revision=REVISION,
    trust_remote_code=True,
    local_files_only=False,
).to(DEVICE).eval()

print("DhVaani loaded on:", DEVICE)
print("Sampling rate:", model.sampling_rate)


# ---- Source section 23 ----
import torch
import sys
import types
import time

# Use the backend of the already-loaded DhVaani model
rt = model._runtime()

helper_names = (
    "load_prompt_wav",
    "remove_silence",
    "rms_norm",
    "add_punctuation",
)

namespaces = [
    fn.__globals__
    for fn in rt.values()
    if isinstance(fn, types.FunctionType)
]

for name, module in list(sys.modules.items()):
    if isinstance(module, types.ModuleType):
        if any(
            tag in name.lower()
            for tag in ("dhvaani", "zipvoice", "_backend")
        ):
            namespaces.append(vars(module))

helpers = next(
    (
        namespace
        for namespace in namespaces
        if all(
            callable(namespace.get(name))
            for name in helper_names
        )
    ),
    None,
)

if helpers is None:
    raise RuntimeError(
        "Cache helpers were not found in this DhVaani version. "
        f"Runtime keys: {list(rt.keys())}. "
        "Share this output so the cell can be adapted."
    )

load_prompt_wav = helpers["load_prompt_wav"]
remove_silence = helpers["remove_silence"]
rms_norm = helpers["rms_norm"]
add_punctuation = helpers["add_punctuation"]

tokenizer = rt["tokenizer"]
feature_extractor = rt["feature"]

DEVICE = model.device
SAMPLING_RATE = model.sampling_rate

TARGET_RMS = 0.1
FEAT_SCALE = 0.1


@torch.inference_mode()
def prepare_prompt_cache(prompt_wav_path, prompt_text):
    """Cache the fixed reference audio and transcript conditioning."""

    start = time.perf_counter()

    # Load and clean reference audio
    wav = load_prompt_wav(
        str(prompt_wav_path),
        sampling_rate=SAMPLING_RATE,
    )

    wav = remove_silence(
        wav,
        SAMPLING_RATE,
        only_edge=False,
        trail_sil=200,
    )

    wav, prompt_rms = rms_norm(wav, TARGET_RMS)

    prompt_duration = wav.shape[-1] / SAMPLING_RATE

    # Extract and retain reference features
    features = feature_extractor.extract(
        wav,
        sampling_rate=SAMPLING_RATE,
    )

    features = (
        features.to(DEVICE).unsqueeze(0) * FEAT_SCALE
    ).contiguous()

    # Tokenize the reference transcript
    clean_prompt_text = add_punctuation(prompt_text)

    prompt_tokens_str = tokenizer.texts_to_tokens(
        [clean_prompt_text]
    )[0]

    prompt_tokens = tokenizer.tokens_to_token_ids(
        [prompt_tokens_str]
    )

    cache = {
        "wav": wav,
        "rms": prompt_rms,
        "duration": prompt_duration,
        "features": features,
        "text": clean_prompt_text,
        "tokens_str": prompt_tokens_str,
        "tokens": prompt_tokens,
        "wav_path": str(prompt_wav_path),
    }

    elapsed_ms = (time.perf_counter() - start) * 1000.0

    print(f"Prompt cache created in {elapsed_ms:.2f} ms")
    print(f"Duration: {prompt_duration:.3f} sec")
    print(f"Feature shape: {tuple(features.shape)}")

    return cache


print("DhVaani prompt-cache function ready.")
print("Next: run your English and Tamil cache creation cell.")
import torch

print("========== MOVIO DHVAANI META REPAIR ==========")

fixed = 0
remaining = []

for name, module in model.model.named_modules():
    if not hasattr(module, "pe"):
        continue

    pe = getattr(module, "pe")

    if not isinstance(pe, torch.Tensor):
        continue

    if pe.device.type != "meta":
        continue

    print("Found meta positional encoding:", name)
    print("Shape:", tuple(pe.shape))

    if not hasattr(module, "extend_pe"):
        remaining.append(name)
        continue

    # The Zipformer positional encoder regenerates its
    # sinusoidal encoding when pe is initially empty.
    # Preserve its original registered-buffer status.
    old_pe = pe

    try:
        module.pe = torch.empty(
            0,
            device="cpu",
            dtype=torch.float32
        )

        fixed += 1
        print("Reinitialized:", name)

    except Exception as e:
        module.pe = old_pe
        remaining.append(name)
        print("Failed:", repr(e))

print("\nReinitialized positional buffers:", fixed)
print("Unresolved buffers:", remaining)

print("\nChecking remaining meta tensors:")

meta_params = [
    n for n, p in model.model.named_parameters()
    if p.device.type == "meta"
]

meta_buffers = [
    n for n, b in model.model.named_buffers()
    if b.device.type == "meta"
]

print("Meta parameters:", meta_params[:20])
print("Meta buffers:", meta_buffers[:20])

if meta_params or meta_buffers:
    raise RuntimeError("Unresolved meta tensors remain. Stop before starting voice calls.")
else:
    print("No remaining meta tensors detected.")

print("==============================================")
