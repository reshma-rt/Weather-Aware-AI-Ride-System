"""Validate runtime wiring with a fake synthesizer; never load GPU models."""
from pathlib import Path
import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / 'site'
        shutil.copytree(ROOT / 'app', target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.db', '*.db-*', '*.log'))
        before = {p: p.read_bytes() for p in target.rglob('*') if p.is_file()}
        bridge = load('movio_fixture_bridge', target / 'integrations/ai_call_sarvam.py')

        class Scheduler:
            def submit(self, kind, route, group, text, step, **kwargs):
                raise AssertionError('This fixture must not synthesize audio.')

        ns = {'__name__': '__main__', 'TARGET': target, 'PIPELINE_REPO_ROOT': ROOT,
              'bridge': bridge, 'load_module': load, 'context_extract': lambda *args: {},
              'SCHEDULER': Scheduler(), 'normalize_taxi_text': str}
        exec('def movio_stream_response(text, group="ENTITY"):\n    raise AssertionError("No audio generation in wiring fixtures")\n'
             'def prepare_movio_request(text, group="ENTITY"):\n    return {"chunks": [str(text)], "group": group, "route": "TAMIL", "normalized": str(text)}\n', ns)

        class Adapter:
            def __init__(self):
                self.ns = ns

            def synthesize(self, *args, **kwargs):
                raise AssertionError('No audio generation in wiring fixtures.')

        bridge.configure('https://fixture.invalid', tts=Adapter(), preprocessing=None,
                         llm=object(), tokenizer=object(), reference_wav='', sarvam_key='fixture-only')
        source = ROOT / 'runtime/stages/04_weather_voice_binding.py'
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(source.read_text(), str(source), 'exec'), ns, ns)
        engine = ns['WX_ENGINE']
        assert sum(getattr(route, 'path', '') == '/browser-call' for route in bridge.app.routes) == 1
        assert engine['summary_text'].__globals__['__file__'].endswith('movio_friendly_weather.py')
        assert engine['advisory'] is ns['final_advisory']
        assert callable(bridge.tanglish_speech_text)
        spoken = bridge.tanglish_speech_text('Vanakkam! AI taxi booking service ku welcome.')
        assert any('\u0b80' <= c <= '\u0bff' for c in spoken)
        pickup = datetime.now(ZoneInfo('Asia/Kolkata')) + timedelta(days=1)
        state = dict(lang='Tanglish', count=4, vehicle='SUV', pickup='Chennai Central',
                     destination='Tambaram', pickup_at=pickup.isoformat(), fare={'km': 35.4, 'fare': 1104})
        summary = engine['summary_text'](bridge, state)
        assert summary.lower().count('yes illa no sollunga') == 1
        closing = engine['completion_message']('Tanglish', 123)
        assert ns['profile_for'](closing) == 'closing'
        assert engine['speech_segments'](closing) == [closing]
        ns['register']('fixture weather message', 'weather')
        assert ns['profile_for']('fixture weather message') == 'weather'
        forecast_source = ROOT / 'runtime/stages/05_forecast_voice.py'
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(forecast_source.read_text(), str(forecast_source), 'exec'), ns, ns)
        result = ns['register_forecast_audio'](bridge.app, bridge, engine, 'https://fixture.invalid')
        assert getattr(result['endpoint'], '_movio_forecast_voice', None)
        assert sum(getattr(route, 'path', '') == '/weather-speech' for route in bridge.app.routes) == 1
        assert ns['normalize_taxi_text']('Vandaloor Celsius') == 'வண்டலூர் செல்சியஸ்'
        assert all(p.read_bytes() == data for p, data in before.items())
        print(json.dumps({'passed': True, 'checks': 13,
                          'scope': 'Temporary SQLite setup, one socket route, source-owned summary/advice, shared audio registry, text conversion, no source rewrites. Fake synthesizer; no speech or external APIs.'}, indent=2))


if __name__ == '__main__':
    main()
