"""Exercise the merged website in an isolated temporary database over real HTTP."""
from pathlib import Path
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    checks = 0
    def check(value, label):
        nonlocal checks
        if not value:
            raise AssertionError(label)
        checks += 1
    with tempfile.TemporaryDirectory() as directory:
        site = Path(directory) / 'site'
        shutil.copytree(ROOT / 'app', site, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.db', '*.db-*', '*.log'))
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        env = {**os.environ, 'MOVIO_PORT': str(port), 'MOVIO_PUBLIC_URL': 'https://fixture.invalid',
               'MOVIO_AI_BRIDGE_URL': 'https://fixture.invalid', 'PYTHONUNBUFFERED': '1'}
        with (site / 'fixture.log').open('w+') as log:
            process = subprocess.Popen([sys.executable, str(site / 'server.py')], cwd=site,
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            sessions = []
            def session():
                client = requests.Session()
                client.trust_env = False
                client.headers['Origin'] = 'https://fixture.invalid'
                sessions.append(client)
                return client
            anonymous = session()
            base = f'http://127.0.0.1:{port}'
            try:
                for _ in range(60):
                    if process.poll() is not None:
                        log.seek(0)
                        raise RuntimeError('Isolated website stopped: ' + log.read()[-1200:])
                    try:
                        response = anonymous.get(base + '/api/health', timeout=1)
                        if response.status_code == 200:
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError('Isolated website did not start.')
                check(response.status_code == 200, 'website health')
                check(anonymous.get(base + '/', timeout=3).status_code == 200, 'dashboard HTML')
                check(anonymous.get(base + '/api/browser-voice-config', timeout=3).status_code in (401, 403), 'signed-out voice configuration')
                check(anonymous.post(base + '/api/customer-care/recommend', json={'context': {}}, timeout=3).status_code == 401, 'signed-out care API')
                def account(role, phone, vehicle=None):
                    client = session()
                    payload = dict(name='Fixture ' + role, phone=phone, password='Fixture-password-42', role=role)
                    if vehicle:
                        payload.update(vehicle_type=vehicle, vehicle_number='TN09AB1234')
                    registered = client.post(base + '/api/register', json=payload, timeout=5)
                    check(registered.status_code == 201, role + ' registration: HTTP ' + str(registered.status_code) + ' ' + registered.text[:200])
                    check(client.post(base + '/api/login', json=payload, timeout=5).status_code == 200, role + ' login')
                    return client
                customer = account('customer', '+919000000001')
                driver = account('driver', '+919000000002', 'Mini')
                other = account('customer', '+919000000003')
                payload = dict(pickup='Chennai Central', destination='Tambaram', vehicle='Mini', fare=300,
                               plat=13.0827, plng=80.2707, dlat=12.9249, dlng=80.1000, request_key='fixture_request_001')
                response = customer.post(base + '/api/rides', json=payload, timeout=5)
                check(response.status_code == 201, 'authenticated ride creation')
                ride_id = response.json()['id']
                duplicate = customer.post(base + '/api/rides', json=payload, timeout=5)
                check(duplicate.status_code == 201 and duplicate.json()['id'] == ride_id, 'duplicate request reuses ride')
                suv = customer.post(base + '/api/rides', json={**payload, 'vehicle': 'SUV', 'request_key': 'fixture_request_002'}, timeout=5).json()['id']
                rides = driver.get(base + '/api/rides', timeout=5).json()['rides']
                check(any(r['id'] == ride_id for r in rides), 'Mini driver sees Mini request')
                check(all(r['id'] != suv for r in rides), 'Mini driver does not see SUV request')
                check(not other.get(base + '/api/rides', timeout=5).json()['rides'], 'account-owned ride visibility')
                owned = customer.get(base + '/api/rides', timeout=5).json()['rides']
                check(any(r['id'] == ride_id and len(str(r.get('pickup_otp', ''))) == 4 for r in owned), 'customer pickup OTP')
                now = time.time()
                pickup = (datetime.now(ZoneInfo('Asia/Kolkata')) + timedelta(days=1)).isoformat()
                with sqlite3.connect(site / 'movio_demo.db') as db:
                    owner = db.execute("SELECT id FROM users WHERE phone='+919000000001'").fetchone()[0]
                    scheduled = db.execute('INSERT INTO rides(customer_id,pickup,destination,plat,plng,dlat,dlng,vehicle,fare,status,source,created,updated,pickup_time) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (owner, 'Chennai Central', 'Tambaram', 13.0827, 80.2707, 12.9249, 80.1000, 'Mini', 300, 'scheduled', 'weather_web', now, now, pickup)).lastrowid
                rides = driver.get(base + '/api/rides', timeout=5).json()['rides']
                check(any(r['id'] == scheduled and r['status'] == 'scheduled' for r in rides), 'scheduled Mini is listed for the informational panel')
                check(driver.post(base + f'/api/rides/{scheduled}/status', json={'status': 'accepted'}, timeout=5).status_code == 409, 'scheduled listing does not allow early acceptance')
                status_url = base + f'/api/rides/{ride_id}/status'
                check(driver.post(status_url, json={'status': 'accepted'}, timeout=5).status_code == 200, 'matching driver acceptance')
                check(other.post(status_url, json={'status': 'cancelled'}, timeout=5).status_code == 403, 'other customer cannot cancel the ride')
                check(driver.post(status_url, json={'status': 'in_progress'}, timeout=5).status_code == 400, 'ride start requires OTP')
                otp = next(r['pickup_otp'] for r in owned if r['id'] == ride_id)
                check(driver.post(status_url, json={'status': 'in_progress', 'otp': str(otp)}, timeout=5).status_code == 200, 'correct OTP starts ride')
                check(driver.post(status_url, json={'status': 'completed'}, timeout=5).status_code == 200, 'assigned driver completes ride')
                check(customer.post(base + f'/api/rides/{suv}/status', json={'status': 'cancelled'}, timeout=5).status_code == 200, 'customer cancels own pending ride')
                saved = customer.get(base + '/api/rides', timeout=5).json()['rides']
                check(any(r['id'] == ride_id and r['status'] == 'completed' for r in saved), 'completed status persists')
                care = customer.post(base + '/api/customer-care/recommend', json={'context': {'language': 'English'}}, timeout=5)
                check(care.status_code == 200, 'signed-in care request without GPS/provider call')
                check(customer.get(base + '/movio_forecast_listen.js', timeout=3).status_code == 200, 'forecast playback script served')
                check(customer.get(base + '/movio_driver_upcoming.js', timeout=3).status_code == 200, 'upcoming panel script served')
            except Exception as error:
                log.flush()
                log.seek(0)
                raise RuntimeError(str(error) + '\nIsolated server log:\n' + log.read()[-2000:]) from None
            finally:
                for client in sessions:
                    client.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    print(json.dumps({'passed': True, 'checks': checks,
                      'scope': 'Merged website startup, real local HTTP, temporary accounts/SQLite, owner and vehicle filters, idempotency, OTP visibility, care auth and asset delivery. No external providers, GPU or real browser.'}, indent=2))


if __name__ == '__main__':
    main()
