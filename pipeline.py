"""One ordered startup path for the supplied Kaggle implementation."""
from pathlib import Path
import json
import os
import shutil
import time

REPO_ROOT = Path(__file__).resolve().parent
STAGES = tuple(path.stem for path in sorted((REPO_ROOT / 'runtime/stages').glob('*.py')))


def _listeners():
    import psutil
    return sorted({c.laddr.port for c in psutil.net_connections(kind='inet')
                   if c.status == 'LISTEN' and c.laddr.port in {8000, 8080, 8090}})


def prepare_site(namespace):
    """Deploy one seed app, preserving any existing database in a backup."""
    if namespace.get('bridge') is not None or namespace.get('SCHEDULER') is not None:
        raise RuntimeError('Use a fresh Kaggle kernel; a voice runtime is already loaded.')
    ports = _listeners()
    if ports:
        raise RuntimeError(f'Services are already listening on {ports}. Stop the old session before a fresh startup.')
    import importlib.util
    if importlib.util.find_spec('torch') is None:
        raise RuntimeError('A Kaggle GPU environment with PyTorch is required.')
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('Enable a Kaggle GPU before running the voice pipeline.')
    work = Path('/kaggle/working')
    work.mkdir(parents=True, exist_ok=True)
    target = work / 'MOVIO_MAIN_WEBSITE'
    if target.is_symlink():
        raise RuntimeError('The website destination must be a normal directory, not a symlink.')
    backup = None
    if target.exists():
        from datetime import datetime
        backup = work / ('MOVIO_PRE_PIPELINE_BACKUP_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        shutil.move(str(target), str(backup))
    shutil.copytree(REPO_ROOT / 'app', target)
    if backup:
        # The services have already been confirmed stopped. Keep database sidecars
        # together if a previous SQLite session left a WAL to be recovered.
        for name in ('movio_demo.db', 'movio_demo.db-wal', 'movio_demo.db-shm'):
            if (backup / name).is_file():
                shutil.copy2(backup / name, target / name)
        print('Previous website preserved at:', backup)
    namespace.update(PIPELINE_REPO_ROOT=REPO_ROOT, TARGET=target, SITE_ROOT=target)
    namespace['_movio_pipeline_state'] = {'completed': [], 'failed': None}
    print('Installed the single bundled website source:', target)


def _wait_website():
    import requests
    with requests.Session() as session:
        session.trust_env = False
        for _ in range(40):
            try:
                if session.get('http://127.0.0.1:8080/api/health', timeout=2).status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(0.25)
    raise RuntimeError('The website did not become healthy after the stage; inspect its log before proceeding.')


def run_stage(name, namespace):
    if name not in STAGES:
        raise ValueError(f'Unknown stage: {name}')
    state = namespace.get('_movio_pipeline_state')
    if state is None:
        prepare_site(namespace)
        state = namespace['_movio_pipeline_state']
    if state['failed']:
        raise RuntimeError(f"Stage {state['failed']} previously failed. Use a fresh session to avoid partial reinstallation.")
    if name in state['completed']:
        print('Already completed:', name)
        return
    expected = STAGES[len(state['completed'])]
    if name != expected:
        raise RuntimeError(f'Run {expected} before {name}.')
    source = REPO_ROOT / 'runtime/stages' / (name + '.py')
    namespace['_movio_pipeline_current_stage'] = name
    print('\nStarting:', name, flush=True)
    try:
        exec(compile(source.read_text(encoding='utf-8'), str(source), 'exec'), namespace, namespace)
        if name == '06_services':
            _wait_website()
    except BaseException:
        state['failed'] = name
        raise
    state['completed'].append(name)
    print('Completed:', name, flush=True)


def finalize(namespace):
    target = namespace['TARGET']
    print('\nPipeline setup finished. Open the website and verify the browser workflows.')
    print('Website:', namespace.get('MOVIO_WEBSITE_URL', 'See the routing stage output.'))
    print('Generated live application:', target)
    print('GPU speech and real-account browser behaviour still need your acceptance test.')


def run_pipeline(namespace=None):
    if namespace is None:
        namespace = {'__name__': '__main__', '__builtins__': __builtins__}
    for name in STAGES:
        run_stage(name, namespace)
    finalize(namespace)
    return namespace


if __name__ == '__main__':
    run_pipeline(globals())
