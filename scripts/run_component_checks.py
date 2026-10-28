"""Isolated core-guard and current care fixtures; no external providers/models."""
from pathlib import Path
import importlib.util
import json
import shutil
import sys
import tempfile
import types
from component_fixtures import run_care_checks, run_backend_checks

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def main():
    with tempfile.TemporaryDirectory() as directory:
        site = Path(directory) / 'site'
        shutil.copytree(ROOT / 'app', site, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.db', '*.db-*', '*.log'))
        care = load('movio_care_fixture', site / 'integrations/movio_customer_care.py')
        api = load('movio_care_api_fixture', site / 'integrations/movio_customer_care_api.py')
        care_result = run_care_checks(care)
        api_result = run_backend_checks(api, care)
        path = site / 'integrations/movio_weather_guard.py'
        core_source = path.read_text().split('# MOVIO_OPTIONAL_WEATHER_BOOTSTRAP_V1', 1)[0]
        core = types.ModuleType('movio_weather_guard')
        core.__file__ = str(path)
        sys.modules[core.__name__] = core
        exec(compile(core_source, str(path), 'exec'), core.__dict__)
        tests = load('test_weather_guard', site / 'integrations/test_weather_guard.py')
        guard_result = tests.run_tests(server_source=site / 'server.py')
        result = dict(care_engine=care_result, care_api=api_result, core_weather_guard=guard_result,
                      scope='Current care functions and core guard before advanced integration bootstraps. Not a full-stack, GPU or browser test. See docs/VALIDATION.md for the separate legacy full-stack failures.')
        print(json.dumps(result, indent=2, default=str))
        return 0 if guard_result['passed'] else 1

if __name__ == '__main__':
    sys.exit(main())
