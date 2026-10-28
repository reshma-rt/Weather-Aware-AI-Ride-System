import os, sys, subprocess, time, psutil, requests, threading, uvicorn
from pathlib import Path
def stop_owned_listener(port, allowed_scripts):
    processes = []
    for pid in listener_pids(port):
        if pid == os.getpid():
            raise RuntimeError(f'Port {port} runs inside the notebook; stopping it would unload models.')
        proc = psutil.Process(pid)
        command = proc.cmdline()
        script_args = [arg for arg in command if Path(arg).name in {p.name for p in allowed_scripts}]
        matches = []
        for arg in script_args:
            script = Path(arg)
            if not script.is_absolute():
                script = Path(proc.cwd()) / script
            matches.append(script.resolve())
        if not any(script in allowed_scripts for script in matches):
            raise RuntimeError(f'Port {port} belongs to an unrelated process (PID {pid}); it was not stopped.')
        processes.append(proc)
    for proc in processes:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except psutil.TimeoutExpired:
            raise RuntimeError(f'PID {proc.pid} did not stop; no forced kill performed.')
def start_process(script, cwd, env, log_path):
    offset = log_path.stat().st_size if log_path.exists() else 0
    with log_path.open('a') as log:
        proc = subprocess.Popen([sys.executable, '-u', str(script)], cwd=str(cwd), env=env,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return proc, offset
def wait_http(url, process, log_path, offset):
    for _ in range(60):
        if process.poll() is not None:
            break
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return response
        except requests.RequestException:
            pass
        time.sleep(0.5)
    with log_path.open() as log:
        log.seek(offset)
        print(log.read()[-4000:])
    raise RuntimeError('Service did not start: ' + url)
if not globals().get('voice_server_thread') or not voice_server_thread.is_alive():
    voice_uvicorn_server = uvicorn.Server(uvicorn.Config(
        bridge.app, host='127.0.0.1', port=8000, log_level='warning'
    ))
    voice_server_thread = threading.Thread(target=voice_uvicorn_server.run, daemon=True)
    voice_server_thread.start()

for _ in range(60):
    if not voice_server_thread.is_alive():
        raise RuntimeError('AI server stopped. See the error printed above.')
    try:
        response = requests.get('http://127.0.0.1:8000/health', timeout=2)
        if response.status_code == 200:
            print('AI voice service:', response.json())
            break
    except requests.RequestException:
        pass
    time.sleep(0.5)
else:
    raise RuntimeError('AI service did not become ready on port 8000.')

GATEWAY_FILE=TARGET/'gateway.py'
gateway_log=Path('/kaggle/working/movio_gateway.log')
gateway_env={**os.environ,'MOVIO_SITE_DIR':str(TARGET)}
movio_gateway_process,gateway_offset=start_process(GATEWAY_FILE,TARGET,gateway_env,gateway_log)
wait_http('http://127.0.0.1:8090/gateway-health',movio_gateway_process,gateway_log,gateway_offset)

from pyngrok import ngrok
from urllib.parse import urlparse

# Authenticate ngrok
ngrok.set_auth_token(NGROK_AUTHTOKEN)

# Retrieve existing tunnels
tunnels = ngrok.get_tunnels()

def tunnel_port(tunnel):
    addr = str(tunnel.config.get("addr", ""))
    if addr.isdigit():
        return int(addr)
    try:
        parsed = urlparse(addr if "://" in addr else "http://" + addr)
        return parsed.port
    except (ValueError, TypeError):
        return None

# Reuse existing HTTPS gateway tunnel
existing = [
    t for t in tunnels
    if tunnel_port(t) == 8090
    and t.public_url.startswith("https://")
]

if existing:
    MOVIO_WEBSITE_URL = existing[0].public_url.rstrip("/")
    print("Reusing existing HTTPS gateway tunnel.")

else:
    # Disconnect only this project's previous tunnels
    for tunnel in tunnels:
        if tunnel_port(tunnel) in (8000, 8080, 8090):
            ngrok.disconnect(tunnel.public_url)

    try:
        # Create gateway tunnel without deprecated bind_tls
        tunnel = ngrok.connect(addr=8090, proto="http")
        MOVIO_WEBSITE_URL = tunnel.public_url.rstrip("/")

    except Exception as error:
        raise RuntimeError(
            f"ngrok gateway tunnel creation failed: {error}"
        ) from error

# Verify HTTPS for microphone and GPS permissions
if not MOVIO_WEBSITE_URL.startswith("https://"):
    raise RuntimeError(
        "HTTPS tunnel required for browser microphone and GPS access."
    )

# Configure shared gateway
AI_PUBLIC_URL = MOVIO_WEBSITE_URL
configure_bridge(MOVIO_WEBSITE_URL)

print("Shared HTTPS URL:", MOVIO_WEBSITE_URL)
print("AI Public URL:", AI_PUBLIC_URL)
print("Gateway Port: 8090")

if not (TARGET / 'server.py').is_file():
    raise RuntimeError('Run the website setup cell first.')
stop_owned_listener(8080, {(TARGET / 'server.py').resolve()})
website_env = {
    **os.environ, 'MOVIO_PORT': '8080', 'MOVIO_PUBLIC_URL': MOVIO_WEBSITE_URL,
    'MOVIO_AI_BRIDGE_URL': MOVIO_WEBSITE_URL, 'AI_PUBLIC_URL': MOVIO_WEBSITE_URL,
    'PYTHONUNBUFFERED': '1'
}
website_log = Path('/kaggle/working/movio_website.log')
movio_website_process, website_offset = start_process(
    TARGET / 'server.py', TARGET, website_env, website_log
)
response = wait_http('http://127.0.0.1:8080/api/health',
                     movio_website_process, website_log, website_offset)
print('Website ready: HTTP', response.status_code)
print('Website folder:', TARGET)

import shutil
from IPython.display import display, Markdown

checks = [
    ('Local website', 'http://127.0.0.1:8080/api/health'),
    ('Local AI', 'http://127.0.0.1:8000/health'),
    ('Gateway', 'http://127.0.0.1:8090/gateway-health'),
    ('Public website', MOVIO_WEBSITE_URL + '/'),
    ('Public website health', MOVIO_WEBSITE_URL + '/api/health'),
    ('Public AI health', MOVIO_WEBSITE_URL + '/health'),
    ('Public call page', MOVIO_WEBSITE_URL + '/call-page'),
]
failures = []
for label, url in checks:
    try:
        response = requests.get(url, timeout=(5, 10), headers={'ngrok-skip-browser-warning': 'true'})
        ok = response.status_code == 200
        print(label + ': HTTP ' + str(response.status_code), flush=True)
        if not ok:
            failures.append(label)
    except requests.RequestException as error:
        print(label + ': ' + type(error).__name__)
        failures.append(label)

config = requests.get('http://127.0.0.1:8080/api/browser-voice-config', timeout=5)
if config.status_code not in (401, 403):
    failures.append('Account protection for browser voice configuration')
print('Browser voice configuration requires website login: HTTP', config.status_code)
print('Configured call page:', website_env['MOVIO_AI_BRIDGE_URL'] + '/call-page')

node = shutil.which('node')
for name in ['app.js', 'auth.js', 'movio_enhancements.js']:
    file = TARGET / 'web' / name
    if node:
        result = subprocess.run([node, '--check', str(file)], capture_output=True, text=True)
        print(name, 'VALID' if result.returncode == 0 else result.stderr)
        if result.returncode:
            failures.append(name)
    else:
        print(name, 'FOUND; Node.js unavailable, syntax check skipped')
if failures:
    raise RuntimeError('Checks failed: ' + ', '.join(failures))

display(Markdown(
    f'**Website:** [{MOVIO_WEBSITE_URL}]({MOVIO_WEBSITE_URL})\n\n'
    'Start AI Call using the button on your logged-in dashboard.\n\n'
    'Open the website, register a customer and a driver in separate browser profiles, '
    'choose a matching vehicle type, and test accept/cancel, driver tracking and '
    'the customer location permission popup. Allow microphone/GPS only when prompted.'
))
