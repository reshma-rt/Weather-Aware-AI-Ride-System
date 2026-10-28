"""Bind the already-applied weather modules to this kernel's voice engine.

No source installers are replayed and no frontend files are rewritten.
"""
from pathlib import Path
import inspect
import re
import threading

WX_ROOT = TARGET
schema = load_module('movio_schema_bootstrap', TARGET / 'server.py')
schema.setup()
wx_module = load_module('movio_weather_guard', TARGET / 'integrations/movio_weather_guard.py')
bridge._wx_context_extract = context_extract
bridge._wx_pause_ms = 220
WX_FORECAST_CLIENT = wx_module.WeatherClient(rain_threshold=60, heat_c=38, feels_like_c=40)
WX_STATUS = wx_module.install_bridge(bridge, TARGET / 'movio_demo.db', weather=WX_FORECAST_CLIENT)
WX_ENGINE = bridge._wx_endpoint.__globals__

# Preserve the final source-owned conversational functions while the runtime
# adapters attach their speech copies and quality profiles.
final_advisory = WX_ENGINE['advisory']
final_summary = WX_ENGINE['summary_text']
final_segments = WX_ENGINE['speech_segments']
friendly_namespace = final_advisory.__globals__
if Path(friendly_namespace.get('__file__', '')).resolve() != (TARGET / 'integrations/movio_friendly_weather.py').resolve():
    raise RuntimeError('The final friendly-weather source was not activated.')

adapter_source = PIPELINE_REPO_ROOT / 'runtime/speech_adapters.py'
exec(compile(adapter_source.read_text(encoding='utf-8'), str(adapter_source), 'exec'), globals(), globals())
configure_wordwise_speech()
configure_audio_profiles()

register = inspect.getclosurevars(WX_ENGINE['advisory']).nonlocals.get('register')
profile_for = inspect.getclosurevars(WX_ENGINE['tts_reply']).nonlocals.get('profile_for')
if not callable(register) or not callable(profile_for):
    raise RuntimeError('Weather/closing speech profiles were not configured.')

# The final summary wrapper keeps its duplicate-Yes/No protection and delegates
# to the conversational summary created by the existing wordwise adapter.
summary_bindings = inspect.getclosurevars(final_summary).nonlocals
previous = summary_bindings.get('previous')
if not isinstance(previous, dict):
    raise RuntimeError('The final summary does not expose its expected delegation state.')
previous['summary_text'] = WX_ENGINE['summary_text']

# Preserve stable grouping for closing messages without a recursion through the
# saved final speech_segments function.
segment_bindings = inspect.getclosurevars(final_segments).nonlocals
segment_previous = segment_bindings.get('previous')
if not isinstance(segment_previous, dict):
    raise RuntimeError('The final sentence segmentation state is missing.')
ordinary_segments = segment_previous['speech_segments']


def profiled_segments(text):
    return [str(text).strip()] if profile_for(text) else ordinary_segments(text)


segment_previous['speech_segments'] = profiled_segments
advisory_cells = dict(zip(final_advisory.__code__.co_freevars, final_advisory.__closure__ or ()))
if 'register' not in advisory_cells:
    raise RuntimeError('The final advisory does not expose its speech-profile registrar.')
advisory_cells['register'].cell_contents = register
WX_ENGINE.update(advisory=final_advisory, summary_text=final_summary, speech_segments=final_segments)

# Use the actual exported pronunciation helper instead of writing an older copy
# into the current project folder.
quality = load_module('movio_tanglish_speech_quality', TARGET / 'integrations/movio_tanglish_speech_quality.py')
speech = bridge.tanglish_speech_text
speech_cells = dict(zip(speech.__code__.co_freevars, speech.__closure__ or ()))
expected = {'lock', 'pattern', 'places', 're', 'words', 'wx'}
if set(speech_cells) != expected:
    raise RuntimeError('The wordwise speech-copy closure is not the expected implementation.')
values = {name: cell.cell_contents for name, cell in speech_cells.items()}
words = dict(values['words'])
for word in quality.ENGLISH_WORDS:
    words.pop(word, None)
words.update(quality.ALIASES)
words['auto'] = 'ஆட்டோ'
pattern = re.compile(r'(?<![A-Za-z])(' + '|'.join(re.escape(key) for key in sorted(words, key=len, reverse=True)) + r')(?![A-Za-z])', re.I)
candidate = quality.make_speech_text(values['lock'], pattern, values['places'], values['re'], words, values['wx'])
if candidate.__code__.co_freevars != speech.__code__.co_freevars:
    raise RuntimeError('The exported pronunciation helper is incompatible with the wordwise adapter.')
speech_cells['words'].cell_contents = words
speech_cells['pattern'].cell_contents = pattern
speech.__code__ = candidate.__code__
speech.__doc__ = candidate.__doc__
speech._movio_tanglish_quality = quality.VERSION
friendly_namespace['_MOVIO_TG_SPEECH_RUNTIME'] = dict(
    version=quality.VERSION, bridge=bridge, phrases=quality.phrases,
    register=register, profile_for=profile_for, lock=values['lock'], places=values['places'])

print('Bound the exported booking/weather modules and current speech helper.')
print('Current frontend assets preserved; no old source installers executed.')
