"""MOVIO v5 educational prototype: authenticated rides, consent-limited GPS, optional Twilio calls."""
import math
import base64, hashlib, hmac, json, os, re, secrets, sqlite3, threading, time, urllib.parse, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parent
DB=ROOT/'movio_demo.db'; LOCK=threading.RLock()
PUBLIC=os.environ.get('MOVIO_PUBLIC_URL','').rstrip('/')
TWILIO_SID=os.environ.get('TWILIO_ACCOUNT_SID','')
TWILIO_TOKEN=os.environ.get('TWILIO_AUTH_TOKEN','')
TWILIO_FROM=os.environ.get('TWILIO_FROM_NUMBER','')
VOICE_STREAM_URL=os.environ.get('MOVIO_VOICE_STREAM_URL','').strip()
AI_BRIDGE_URL=os.environ.get('MOVIO_AI_BRIDGE_URL','').rstrip('/')
AI_BRIDGE_KEY=os.environ.get('MOVIO_BRIDGE_KEY','')

def conn():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;return c

def setup():
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('customer','driver')));
  CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
  CREATE TABLE IF NOT EXISTS rides(id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, pickup TEXT, destination TEXT, plat REAL, plng REAL, dlat REAL, dlng REAL, vehicle TEXT, fare INTEGER, status TEXT, driver_id INTEGER, source TEXT DEFAULT 'web', created REAL, updated REAL);
  CREATE TABLE IF NOT EXISTS locations(user_id INTEGER PRIMARY KEY, lat REAL, lng REAL, expires REAL, updated REAL);
  CREATE TABLE IF NOT EXISTS consents(user_id INTEGER PRIMARY KEY, expires REAL NOT NULL);
  CREATE TABLE IF NOT EXISTS driver_profiles(user_id INTEGER PRIMARY KEY,vehicle_type TEXT NOT NULL,vehicle_number TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS location_requests(ride_id INTEGER PRIMARY KEY,driver_id INTEGER NOT NULL,customer_id INTEGER NOT NULL,requested REAL NOT NULL,status TEXT NOT NULL DEFAULT 'pending',expires REAL NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS booking_requests(customer_id INTEGER NOT NULL,request_key TEXT NOT NULL,ride_id INTEGER NOT NULL,created REAL NOT NULL,PRIMARY KEY(customer_id,request_key));
  CREATE TABLE IF NOT EXISTS driver_declines(ride_id INTEGER NOT NULL,driver_id INTEGER NOT NULL,PRIMARY KEY(ride_id,driver_id));
  CREATE TABLE IF NOT EXISTS calls(call_sid TEXT PRIMARY KEY, user_id INTEGER, phone TEXT, pickup TEXT, destination TEXT, vehicle TEXT, stage TEXT, updated REAL);''')

  c.execute("CREATE TABLE IF NOT EXISTS ride_pickup_codes(ride_id INTEGER PRIMARY KEY,code TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,locked_until REAL NOT NULL DEFAULT 0,verified REAL NOT NULL DEFAULT 0)")
  for row in c.execute("SELECT id FROM rides WHERE status NOT IN ('completed','cancelled')").fetchall():ensure_pickup_code(c,row['id'])
  # Migration preserves accounts, rides, AI settings and existing database files.
  columns={row['name'] for row in c.execute('PRAGMA table_info(location_requests)')}
  if 'expires' not in columns:c.execute('ALTER TABLE location_requests ADD COLUMN expires REAL NOT NULL DEFAULT 0')
  # Old user-wide grants cannot be assigned safely to a particular ride.
  c.execute("UPDATE location_requests SET status='expired' WHERE status='granted' AND expires=0")
  c.execute('DELETE FROM consents')

def ensure_pickup_code(c,ride_id):
 c.execute('INSERT OR IGNORE INTO ride_pickup_codes(ride_id,code) VALUES(?,?)',(ride_id,f'{secrets.randbelow(10000):04d}'))

def sweep_locations(c):
 now=time.time()
 c.execute("UPDATE location_requests SET status='expired' WHERE status='granted' AND expires<=?",(now,))
 c.execute('DELETE FROM locations WHERE expires<=?',(now,))
 c.execute("DELETE FROM locations WHERE user_id IN (SELECT id FROM users WHERE role='customer') AND NOT EXISTS (SELECT 1 FROM location_requests lr JOIN rides r ON r.id=lr.ride_id WHERE lr.customer_id=locations.user_id AND lr.driver_id=r.driver_id AND lr.status='granted' AND lr.expires>? AND r.status IN ('accepted','arriving','in_progress'))",(now,))
 c.commit()

def live_grant(c,user_id):
 return c.execute("SELECT MAX(lr.expires) expires FROM location_requests lr JOIN rides r ON r.id=lr.ride_id WHERE lr.customer_id=? AND lr.driver_id=r.driver_id AND lr.status='granted' AND lr.expires>? AND r.status IN ('accepted','arriving','in_progress') HAVING COUNT(*)>0",(user_id,time.time())).fetchone()

def vehicle_details(p):
 vt=str(p.get('vehicle_type',''))
 vn=str(p.get('vehicle_number','')).strip().upper()
 if vt not in ('Mini','Auto','Sedan','SUV','Bike') or not re.fullmatch(r'[A-Z0-9 -]{4,20}',vn):raise ValueError('Choose a vehicle type and enter its registration number')
 return vt,vn

def pw_hash(p,s):return hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(s),230000).hex()
def clean_phone(p):
 p=str(p).strip().replace(' ','').replace('-','')
 if not re.fullmatch(r'\+[1-9]\d{7,14}',p):raise ValueError('Use international phone format, e.g. +91XXXXXXXXXX')
 return p

def send_json(h,status,obj,cookie=None):
 data=json.dumps(obj,ensure_ascii=False).encode();h.send_response(status);h.send_header('Content-Type','application/json; charset=utf-8');h.send_header('Content-Length',str(len(data)));h.send_header('Cache-Control','no-store');h.send_header('X-Content-Type-Options','nosniff')
 if cookie:h.send_header('Set-Cookie',cookie)
 h.end_headers();h.wfile.write(data)

def xml(h,body):
 data=('<?xml version="1.0" encoding="UTF-8"?><Response>'+body+'</Response>').encode();h.send_response(200);h.send_header('Content-Type','text/xml; charset=utf-8');h.send_header('Content-Length',str(len(data)));h.end_headers();h.wfile.write(data)

def auth(h,c):
 cookies=dict(x.strip().split('=',1) for x in h.headers.get('Cookie','').split(';') if '=' in x)
 token=cookies.get('movio_session','');th=hashlib.sha256(token.encode()).hexdigest()
 return c.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires>?',(th,time.time())).fetchone() if token else None

def twilio_signature_valid(h,params):
 if not (TWILIO_TOKEN and PUBLIC):return False
 signature=h.headers.get('X-Twilio-Signature','')
 url=PUBLIC+urllib.parse.urlparse(h.path).path
 calculated=base64.b64encode(hmac.new(TWILIO_TOKEN.encode(),(url+''.join(k+params[k] for k in sorted(params))).encode(),hashlib.sha1).digest()).decode()
 return hmac.compare_digest(signature,calculated)

def say(message):return '<Say voice="alice" language="en-IN">'+escape(message)+'</Say>'
def gather(prompt,stage):
 return '<Gather input="speech" action="/twilio/voice/'+stage+'" method="POST" speechTimeout="auto" language="en-IN" timeout="8">'+say(prompt)+'</Gather>'+say('I did not hear you. Goodbye.')

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'web'),**kw)
 def json(self,status,obj,cookie=None):send_json(self,status,obj,cookie)
 def payload(self,limit=2500000):
  n=int(self.headers.get('Content-Length','0'))
  if n>limit:raise ValueError('Request too large')
  return self.rfile.read(n)
 def user(self,c):
  u=auth(self,c)
  if not u:raise PermissionError('Log in first')
  return u
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path
  if not path.startswith('/api/'):return super().do_GET()
  try:
   with LOCK,conn() as c:
    if path=='/api/browser-voice-config':
     self.user(c)  # Only logged-in users may launch account-linked voice calls.
     base=os.environ.get('MOVIO_AI_BRIDGE_URL','').rstrip('/')
     return self.json(200,{'url':base+'/call-page' if base.startswith('https://') else None})
    if path=='/api/health':return self.json(200,{'ok':True,'version':'5.3','calling_configured':bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and PUBLIC),'tts_configured':bool(os.environ.get('MOVIO_TTS_URL')),'stt_configured':bool(os.environ.get('MOVIO_STT_URL')),'stream_configured':bool(VOICE_STREAM_URL),'ai_call_configured':bool(AI_BRIDGE_URL and AI_BRIDGE_KEY)})
    u=self.user(c)
    sweep_locations(c)
    if path=='/api/maps-config':return self.json(200,{'key':os.environ.get('GOOGLE_MAPS_API_KEY',''),'map_id':os.environ.get('GOOGLE_MAPS_MAP_ID','DEMO_MAP_ID')})
    if path=='/api/me':return self.json(200,{'id':u['id'],'name':u['name'],'phone':u['phone'],'role':u['role'],'vehicle_type':(c.execute('SELECT vehicle_type FROM driver_profiles WHERE user_id=?',(u['id'],)).fetchone() or {'vehicle_type':None})['vehicle_type'],'vehicle_number':(c.execute('SELECT vehicle_number FROM driver_profiles WHERE user_id=?',(u['id'],)).fetchone() or {'vehicle_number':None})['vehicle_number']})
    if path=='/api/ai-call-status':
     sid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('sid',[''])[0]
     if not re.fullmatch(r'CA[a-fA-F0-9]{32}',sid):raise ValueError('Invalid call id')
     record=c.execute('SELECT * FROM calls WHERE call_sid=? AND user_id=?',(sid,u['id'])).fetchone()
     if not record:return self.json(404,{'error':'Call not found'})
     if not (AI_BRIDGE_URL and AI_BRIDGE_KEY):return self.json(503,{'error':'AI bridge not configured'})
     req=urllib.request.Request(AI_BRIDGE_URL+'/api/call-status/'+sid,headers={'X-MOVIO-Bridge-Key':AI_BRIDGE_KEY})
     try:
      with urllib.request.urlopen(req,timeout=20) as response:state=json.load(response)
     except Exception as exc:return self.json(502,{'error':'AI bridge unreachable: '+str(exc)[:150]})
     if str(state.get('user_id'))!=str(u['id']):return self.json(403,{'error':'Call owner mismatch'})
     status=state.get('status')
     if status=='demo_confirmed' and record['stage']!='synced':
      # No map coordinates from voice; record needs_location, not dispatched.
      c.execute('INSERT INTO rides(customer_id,pickup,destination,vehicle,fare,status,source,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
        (u['id'],str(state.get('pickup') or '')[:180],str(state.get('destination') or '')[:180],str(state.get('vehicle_type') or 'Mini')[:40],0,'needs_location','ai_voice',time.time(),time.time()))
      c.execute('UPDATE calls SET stage=?,updated=? WHERE call_sid=?',('synced',time.time(),sid));c.commit()
     if status=='cancelled' and record['stage']!='cancelled':
      c.execute("UPDATE rides SET status='cancelled',updated=? WHERE customer_id=? AND source='ai_voice' AND status='needs_location' AND id=(SELECT MAX(id) FROM rides WHERE customer_id=? AND source='ai_voice')",(time.time(),u['id'],u['id']))
      c.execute('UPDATE calls SET stage=?,updated=? WHERE call_sid=?',('cancelled',time.time(),sid));c.commit()
     return self.json(200,state)
    if path=='/api/rides':
     if u['role']=='customer':
      rows=c.execute('SELECT r.*, d.name driver_name,d.phone driver_phone,dp.vehicle_number driver_vehicle_number FROM rides r LEFT JOIN users d ON r.driver_id=d.id LEFT JOIN driver_profiles dp ON r.driver_id=dp.user_id WHERE r.customer_id=? ORDER BY r.id DESC LIMIT 100',(u['id'],)).fetchall()
     else:
      rows=c.execute("SELECT r.*,u.name customer_name FROM rides r JOIN users u ON u.id=r.customer_id JOIN driver_profiles dp ON dp.user_id=? WHERE (r.status IN ('requested','scheduled') AND r.vehicle=dp.vehicle_type AND r.driver_id IS NULL AND NOT EXISTS (SELECT 1 FROM driver_declines dd WHERE dd.ride_id=r.id AND dd.driver_id=?) AND NOT EXISTS (SELECT 1 FROM rides busy WHERE busy.driver_id=? AND busy.status IN ('accepted','arriving','in_progress'))) OR r.driver_id=? ORDER BY r.id DESC LIMIT 100",(u['id'],u['id'],u['id'],u['id'])).fetchall()
     items=[dict(r) for r in rows]
     for item in items:
      if item['status'] not in ('completed','cancelled'):
       ensure_pickup_code(c,item['id'])
      code=c.execute('SELECT code,verified FROM ride_pickup_codes WHERE ride_id=?',(item['id'],)).fetchone()
      item['pickup_verified']=bool(code and code['verified'])
      if u['role']=='customer' and item['status'] in ('requested','accepted','arriving') and code:item['pickup_otp']=code['code']
      req=c.execute('SELECT status,requested,expires FROM location_requests WHERE ride_id=? AND driver_id=?',(item['id'],item['driver_id'])).fetchone()
      item['location_request']=dict(req) if req else None
      item['location_share_until']=req['expires'] if req and req['status']=='granted' and req['expires']>time.time() and item['status'] in ('accepted','arriving','in_progress') else 0
     c.commit();return self.json(200,{'rides':items})
    if path=='/api/locations':
     now=time.time()
     query=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
     active=c.execute("SELECT * FROM rides WHERE (customer_id=? OR driver_id=?) AND status IN ('accepted','arriving','in_progress')",(u['id'],u['id'])).fetchall()
     if query.get('ride_id'):
      rid=int(query['ride_id'][0]);active=[r for r in active if r['id']==rid]
      if not active:raise PermissionError('You are not assigned to this active ride')
     allowed={u['id']}
     for r in active:
      if u['role']=='customer':allowed.add(r['driver_id'])
      else:
       req=c.execute("SELECT 1 FROM location_requests WHERE ride_id=? AND driver_id=? AND status='granted' AND expires>?",(r['id'],u['id'],now)).fetchone()
       if req:allowed.add(r['customer_id'])
     visible=[]
     for uid in allowed:
      loc=c.execute('SELECT l.*,u.role FROM locations l JOIN users u ON u.id=l.user_id WHERE l.user_id=? AND l.expires>?',(uid,now)).fetchone()
      if loc:visible.append(dict(loc))
     return self.json(200,{'locations':visible,'server_time':now})
    if path=='/api/consent':
     grant=live_grant(c,u['id']) if u['role']=='customer' else None
     return self.json(200,{'expires':grant['expires'] if grant else 0})
   return self.json(404,{'error':'Not found'})
  except PermissionError as e:return self.json(401 if str(e)=='Log in first' else 403,{'error':str(e)})
  except (ValueError,KeyError,TypeError) as e:return self.json(400,{'error':str(e)})
  except Exception as e:return self.json(500,{'error':str(e)})
 def do_POST(self):
  path=urllib.parse.urlparse(self.path).path
  if path.startswith('/twilio/'):return self.twilio(path)
  try:
   raw=self.payload();p=json.loads(raw or b'{}')
   with LOCK,conn() as c:
    if path=='/api/register':
     phone=clean_phone(p.get('phone',''));name=str(p.get('name','')).strip()[:60];password=str(p.get('password',''));role=p.get('role')
     if len(name)<2 or len(password)<8 or role not in ('customer','driver'):raise ValueError('Name, password (8+ chars) and role required')
     salt=secrets.token_hex(16)
     vehicle_type,vehicle_number=vehicle_details(p) if role=='driver' else ('','')
     try:
      cur=c.execute('INSERT INTO users(name,phone,password_salt,password_hash,role) VALUES(?,?,?,?,?)',(name,phone,salt,pw_hash(password,salt),role))
      if role=='driver':c.execute('INSERT INTO driver_profiles VALUES(?,?,?)',(cur.lastrowid,vehicle_type,vehicle_number))
      c.commit()
     except sqlite3.IntegrityError:raise ValueError('Phone already registered')
     return self.json(201,{'ok':True})
    if path=='/api/login':
     phone=clean_phone(p.get('phone',''));u=c.execute('SELECT * FROM users WHERE phone=?',(phone,)).fetchone()
     if not u or not hmac.compare_digest(pw_hash(str(p.get('password','')),u['password_salt']),u['password_hash']):return self.json(401,{'error':'Invalid phone or password'})
     token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],time.time()+7*86400));c.commit()
     return self.json(200,{'ok':True,'role':u['role']},f'movio_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800')
    if path=='/api/logout':
     u=self.user(c);cookies=dict(x.strip().split('=',1) for x in self.headers.get('Cookie','').split(';') if '=' in x)
     c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(cookies.get('movio_session','').encode()).hexdigest(),));c.commit()
     return self.json(200,{'ok':True},'movio_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0')
    u=self.user(c)
    sweep_locations(c)
    if path=='/api/driver-profile':
     if u['role']!='driver':raise PermissionError('Driver account required')
     if c.execute("SELECT 1 FROM rides WHERE driver_id=? AND status IN ('accepted','arriving','in_progress')",(u['id'],)).fetchone():return self.json(409,{'error':'Finish or cancel the current ride before editing vehicle details'})
     vt,vn=vehicle_details(p)
     name=str(p.get('name',u['name'])).strip()[:60]
     if len(name)<2:raise ValueError('Full name required')
     c.execute('UPDATE users SET name=? WHERE id=?',(name,u['id']))
     c.execute('INSERT INTO driver_profiles VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET vehicle_type=excluded.vehicle_type,vehicle_number=excluded.vehicle_number',(u['id'],vt,vn))
     c.commit();return self.json(200,{'ok':True})
    if path=='/api/rides':
     if u['role']!='customer':raise PermissionError('Customer account required')
     request_key=str(p.get('request_key','')).strip()
     if request_key:
      if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}',request_key):raise ValueError('Invalid booking request key')
      existing=c.execute('SELECT ride_id FROM booking_requests WHERE customer_id=? AND request_key=?',(u['id'],request_key)).fetchone()
      if existing:return self.json(201,{'ok':True,'id':existing['ride_id'],'reused':True})
     for key in ('pickup','destination','vehicle','plat','plng','dlat','dlng'):
      if key not in p:raise ValueError('Missing '+key)
     if p['vehicle'] not in ('Bike','Mini','Sedan','SUV','Auto'):raise ValueError('Invalid vehicle')
     coords=[float(p[k]) for k in ('plat','plng','dlat','dlng')]
     if not all(math.isfinite(coords[i]) and (-90<=coords[i]<=90 if i%2==0 else -180<=coords[i]<=180) for i in range(4)):raise ValueError('Invalid coordinates')
     cur=c.execute('INSERT INTO rides(customer_id,pickup,destination,plat,plng,dlat,dlng,vehicle,fare,status,source,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(u['id'],str(p['pickup'])[:180],str(p['destination'])[:180],*coords,p['vehicle'],max(0,int(p.get('fare',0))),'requested','web',time.time(),time.time()))
     ensure_pickup_code(c,cur.lastrowid)
     if request_key:c.execute('INSERT INTO booking_requests VALUES(?,?,?,?)',(u['id'],request_key,cur.lastrowid,time.time()))
     c.commit();return self.json(201,{'ok':True,'id':cur.lastrowid})
    if path.startswith('/api/rides/') and path.endswith('/decline'):
     rid=int(path.split('/')[3]);r=c.execute('SELECT * FROM rides WHERE id=?',(rid,)).fetchone()
     profile=c.execute('SELECT * FROM driver_profiles WHERE user_id=?',(u['id'],)).fetchone()
     if u['role']!='driver' or not r or not profile or profile['vehicle_type']!=r['vehicle'] or r['status']!='requested' or r['driver_id'] is not None:raise PermissionError('Only matching drivers can decline an unassigned request')
     c.execute('INSERT OR IGNORE INTO driver_declines VALUES(?,?)',(rid,u['id']));c.commit()
     return self.json(200,{'ok':True})
    if path.startswith('/api/rides/') and path.endswith('/location-request'):
     rid=int(path.split('/')[3]);r=c.execute('SELECT * FROM rides WHERE id=?',(rid,)).fetchone()
     if u['role']!='driver' or not r or r['driver_id']!=u['id'] or r['status'] not in ('accepted','arriving','in_progress'):raise PermissionError('Only the assigned driver can request location during an active ride')
     req=c.execute('SELECT * FROM location_requests WHERE ride_id=?',(rid,)).fetchone()
     if req and req['status'] in ('pending','granted'):return self.json(200,{'ok':True,'status':req['status'],'expires':req['expires']})
     if req and req['status'] in ('expired','revoked'):return self.json(409,{'error':'The 15-minute sharing window has ended for this ride'})
     c.execute("INSERT INTO location_requests(ride_id,driver_id,customer_id,requested,status,expires) VALUES(?,?,?,?, 'pending',0) ON CONFLICT(ride_id) DO UPDATE SET requested=excluded.requested,status='pending',expires=0",(rid,u['id'],r['customer_id'],time.time()))
     c.commit();return self.json(200,{'ok':True})
    if path.startswith('/api/rides/') and path.endswith('/location-response'):
     rid=int(path.split('/')[3]);r=c.execute('SELECT * FROM rides WHERE id=?',(rid,)).fetchone()
     req=c.execute('SELECT * FROM location_requests WHERE ride_id=?',(rid,)).fetchone()
     if u['role']!='customer' or not r or r['customer_id']!=u['id'] or not req or req['driver_id']!=r['driver_id'] or req['status']!='pending' or r['status'] not in ('accepted','arriving','in_progress'):raise PermissionError('No pending request from your assigned driver')
     allow=p.get('allow') is True
     expiry=time.time()+900 if allow else 0
     c.execute('UPDATE location_requests SET status=?,expires=? WHERE ride_id=?',('granted' if allow else 'denied',expiry,rid))
     if not allow and not live_grant(c,u['id']):c.execute('DELETE FROM locations WHERE user_id=?',(u['id'],))
     c.commit();return self.json(200,{'ok':True,'expires':expiry})
    if path.startswith('/api/rides/') and path.endswith('/status'):
     rid=int(path.split('/')[3]);status=p.get('status');r=c.execute('SELECT * FROM rides WHERE id=?',(rid,)).fetchone()
     if not r:return self.json(404,{'error':'Ride not found'})
     allowed={'needs_location':['cancelled'],'requested':['accepted','cancelled'],'accepted':['arriving','in_progress','cancelled'],'arriving':['in_progress','cancelled'],'in_progress':['completed'],'completed':[],'cancelled':[]}
     if status not in allowed.get(r['status'],[]):return self.json(409,{'error':'Invalid status transition'})
     if u['role']=='driver':
      profile=c.execute('SELECT vehicle_type FROM driver_profiles WHERE user_id=?',(u['id'],)).fetchone()
      if not profile or profile['vehicle_type']!=r['vehicle']:raise PermissionError('Vehicle type does not match this ride')
      if status=='accepted' and c.execute("SELECT 1 FROM rides WHERE driver_id=? AND status IN ('accepted','arriving','in_progress')",(u['id'],)).fetchone():return self.json(409,{'error':'Finish or cancel your current ride first'})
      if status=='accepted' and c.execute('SELECT 1 FROM driver_declines WHERE ride_id=? AND driver_id=?',(rid,u['id'])).fetchone():return self.json(409,{'error':'You declined this request'})
      if status=='cancelled' and r['driver_id'] is None:raise PermissionError('Cannot cancel an unassigned request; decline it locally')
      if r['driver_id'] not in (None,u['id']) or (r['driver_id'] is None and status!='accepted'):raise PermissionError('Driver not assigned')
      if status=='accepted':ensure_pickup_code(c,rid)
      if status=='in_progress':
       ensure_pickup_code(c,rid)
       code=c.execute('SELECT * FROM ride_pickup_codes WHERE ride_id=?',(rid,)).fetchone()
       now=time.time()
       if code['locked_until']>now:return self.json(429,{'error':'Too many incorrect OTP attempts. Wait one minute and try again.'})
       entered=str(p.get('otp','')).strip()
       if not re.fullmatch(r'\d{4}',entered):return self.json(400,{'error':'Enter the customer four-digit pickup OTP to start the ride'})
       attempts=0 if code['locked_until'] and code['locked_until']<=now else code['attempts']
       if not hmac.compare_digest(entered,code['code']):
        attempts+=1
        c.execute('UPDATE ride_pickup_codes SET attempts=?,locked_until=? WHERE ride_id=?',(attempts,now+60 if attempts>=5 else 0,rid));c.commit()
        return self.json(400,{'error':'Incorrect pickup OTP. Ask the customer for the code shown on this booking.'})
       c.execute('UPDATE ride_pickup_codes SET verified=?,attempts=0,locked_until=0 WHERE ride_id=?',(now,rid))
      driver_id=u['id']
     else:
      if r['customer_id']!=u['id'] or status!='cancelled':raise PermissionError('Customer can only cancel own ride')
      driver_id=r['driver_id']
     cur=c.execute('UPDATE rides SET status=?,driver_id=?,updated=? WHERE id=? AND status=? AND (driver_id IS NULL OR driver_id=?)',(status,driver_id,time.time(),rid,r['status'],u['id'] if u['role']=='driver' else driver_id))
     if cur.rowcount!=1:return self.json(409,{'error':'Ride already accepted or changed'})
     if status in ('cancelled','completed'):
      c.execute('DELETE FROM consents WHERE user_id=?',(r['customer_id'],))
      c.execute('DELETE FROM location_requests WHERE ride_id=?',(rid,))
      if not live_grant(c,r['customer_id']):c.execute('DELETE FROM locations WHERE user_id=?',(r['customer_id'],))
     c.commit();return self.json(200,{'ok':True})
    if path=='/api/consent':
     # A generic endpoint must never silently renew a ride-scoped grant.
     return self.json(409,{'error':'Approve the assigned driver request in the customer dashboard'})
    if path=='/api/locations/revoke':
     rid=p.get('ride_id')
     if u['role']=='customer' and rid is not None:
      rid=int(rid)
      if not c.execute('SELECT 1 FROM rides WHERE id=? AND customer_id=?',(rid,u['id'])).fetchone():raise PermissionError('Not your booking')
      c.execute("UPDATE location_requests SET status='revoked' WHERE ride_id=? AND customer_id=? AND status='granted'",(rid,u['id']))
     elif u['role']=='customer':
      c.execute("UPDATE location_requests SET status='revoked' WHERE customer_id=? AND status='granted'",(u['id'],))
     if u['role']=='driver' or not live_grant(c,u['id']):c.execute('DELETE FROM locations WHERE user_id=?',(u['id'],))
     c.commit();return self.json(200,{'ok':True})
    if path=='/api/locations':
     lat=float(p['lat']);lng=float(p['lng']);now=time.time()
     if not (math.isfinite(lat) and math.isfinite(lng) and -90<=lat<=90 and -180<=lng<=180):raise ValueError('Invalid coordinates')
     if u['role']=='customer':
      grant=live_grant(c,u['id'])
      if not grant:raise PermissionError('Location sharing is inactive or expired')
      expires=min(grant['expires'],now+25)
     else:expires=now+25
     c.execute('INSERT INTO locations VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET lat=excluded.lat,lng=excluded.lng,expires=excluded.expires,updated=excluded.updated',(u['id'],lat,lng,expires,now));c.commit();return self.json(200,{'ok':True,'expires':expires})
    if path=='/api/ai-call':
     if u['role']!='customer':raise PermissionError('Customer account required')
     if not (AI_BRIDGE_URL.startswith('https://') and AI_BRIDGE_KEY):
      return self.json(503,{'error':'Configure MOVIO_AI_BRIDGE_URL and MOVIO_BRIDGE_KEY in the local server environment.'})
     payload=json.dumps({'phone':u['phone'],'user_id':u['id']}).encode()
     req=urllib.request.Request(AI_BRIDGE_URL+'/api/outbound-call',data=payload,
      headers={'Content-Type':'application/json','X-MOVIO-Bridge-Key':AI_BRIDGE_KEY},method='POST')
     try:
      with urllib.request.urlopen(req,timeout=40) as response:result=json.load(response)
     except urllib.error.HTTPError as exc:
      detail=exc.read(500).decode('utf-8','replace')
      return self.json(502,{'error':'AI call rejected: '+detail[:300]})
     except Exception as exc:return self.json(502,{'error':'AI bridge unreachable: '+str(exc)[:220]})
     sid=result.get('call_sid','')
     if not re.fullmatch(r'CA[a-fA-F0-9]{32}',sid):return self.json(502,{'error':'Unexpected call ID from bridge'})
     c.execute('INSERT OR REPLACE INTO calls(call_sid,user_id,phone,stage,updated) VALUES(?,?,?,?,?)',(sid,u['id'],u['phone'],'ai_start',time.time()));c.commit()
     return self.json(200,{'ok':True,'call_sid':sid,'message':'AI call requested. Answer your registered phone. Demo only.'})
    if path=='/api/call-me':
     if u['role']!='customer':raise PermissionError('Customer account required')
     if not all((TWILIO_SID,TWILIO_TOKEN,TWILIO_FROM,PUBLIC)):return self.json(503,{'error':'Phone calls not configured. See README: Twilio credentials and public HTTPS webhook are required.'})
     url='https://api.twilio.com/2010-04-01/Accounts/'+TWILIO_SID+'/Calls.json'
     form=urllib.parse.urlencode({'To':u['phone'],'From':TWILIO_FROM,'Url':PUBLIC+'/twilio/voice/start','Method':'POST'}).encode()
     req=urllib.request.Request(url,data=form,headers={'Authorization':'Basic '+base64.b64encode((TWILIO_SID+':'+TWILIO_TOKEN).encode()).decode()})
     try:
      with urllib.request.urlopen(req,timeout=20) as response:result=json.load(response)
     except Exception as e:return self.json(502,{'error':'Call provider rejected request: '+str(e)[:250]})
     c.execute('INSERT OR REPLACE INTO calls(call_sid,user_id,phone,stage,updated) VALUES(?,?,?,?,?)',(result['sid'],u['id'],u['phone'],'start',time.time()));c.commit()
     return self.json(200,{'ok':True,'call_sid':result['sid'],'message':'Call requested. Answer your phone.'})
   return self.json(404,{'error':'Unknown endpoint'})
  except PermissionError as e:return self.json(403,{'error':str(e)})
  except (ValueError,KeyError,TypeError) as e:return self.json(400,{'error':str(e)})
  except Exception as e:return self.json(500,{'error':str(e)})
 def twilio(self,path):
  raw=self.payload(30000);form=urllib.parse.parse_qs(raw.decode(),keep_blank_values=True);p={k:v[-1] for k,v in form.items()}
  if not twilio_signature_valid(self,p):return self.json(403,{'error':'Invalid Twilio signature or missing public URL'})
  sid=p.get('CallSid','');speech=p.get('SpeechResult','').strip()[:180]
  with LOCK,conn() as c:
   call=c.execute('SELECT * FROM calls WHERE call_sid=?',(sid,)).fetchone()
   if not call:return xml(self,say('Call not recognized. Goodbye.'))
   if path.endswith('/start'):
    if VOICE_STREAM_URL:
     if not VOICE_STREAM_URL.startswith('wss://'):return xml(self,say('Voice streaming is not configured securely.'))
     return xml(self,'<Connect><Stream url="'+escape(VOICE_STREAM_URL)+'"><Parameter name="auth" value="'+escape(os.environ.get('MOVIO_STREAM_SECRET',''))+'" /></Stream></Connect>')
    return xml(self,gather('Welcome to MOVIO. Tell me your pickup location.','pickup'))
   if path.endswith('/pickup'):
    if not speech:return xml(self,gather('Please repeat your pickup location.','pickup'))
    c.execute('UPDATE calls SET pickup=?,stage=?,updated=? WHERE call_sid=?',(speech,'destination',time.time(),sid));c.commit()
    return xml(self,gather('Your pickup is '+speech+'. Tell me your destination.','destination'))
   if path.endswith('/destination'):
    if not speech:return xml(self,gather('Please repeat your destination.','destination'))
    c.execute('UPDATE calls SET destination=?,stage=?,updated=? WHERE call_sid=?',(speech,'confirm',time.time(),sid));c.commit()
    return xml(self,gather('From '+call['pickup']+' to '+speech+'. Say yes to confirm this booking request, or no to cancel.','confirm'))
   if path.endswith('/confirm'):
    if not re.search(r'\b(yes|confirm|okay|ok)\b|ஆம்|சரி|aama|seri',speech,re.I):return xml(self,say('Booking was not confirmed. No ride requested. Goodbye.'))
    # Phone speech gives place names, not validated coordinates. Keep request unassigned until location resolution.
    c.execute('INSERT INTO rides(customer_id,pickup,destination,vehicle,fare,status,source,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',(call['user_id'],call['pickup'],call['destination'],'Mini',0,'needs_location','phone',time.time(),time.time()))
    c.execute('UPDATE calls SET stage=?,updated=? WHERE call_sid=?',('done',time.time(),sid));c.commit()
    return xml(self,say('Your request has been recorded. Please open MOVIO to confirm map locations before a driver is assigned. Thank you.'))
  return xml(self,say('Goodbye.'))

# Initialize the base schema before weather migrations inspect the rides table.
if __name__ == '__main__':
    setup()

# WEATHER_BOOKING_BOOTSTRAP_V1
if __name__ == '__main__':
    import sys as _wx_sys
    import importlib.util as _wx_import
    _wx_spec = _wx_import.spec_from_file_location('movio_weather_guard', ROOT / 'integrations/movio_weather_guard.py')
    _wx_mod = _wx_import.module_from_spec(_wx_spec)
    _wx_sys.modules[_wx_spec.name] = _wx_mod
    _wx_spec.loader.exec_module(_wx_mod)
    # Activate the optional forecast implementation before installing routes.
    _opt_path = ROOT / 'integrations/movio_optional_weather.py'
    _opt_spec = _wx_import.spec_from_file_location('movio_optional_weather', _opt_path)
    _opt_mod = _wx_import.module_from_spec(_opt_spec)
    _wx_sys.modules[_opt_spec.name] = _opt_mod
    _opt_spec.loader.exec_module(_opt_mod)
    _opt_mod.install_namespace(_wx_mod.__dict__, root=ROOT)
    _wx_mod.install_backend(_wx_sys.modules[__name__])
# WEATHER_BOOKING_BOOTSTRAP_END_V2

# MOVIO_CUSTOMER_TOOLS_BOOTSTRAP_V1
if __name__ == '__main__':
    import importlib.util as _ct_import
    import sys as _ct_sys
    _ct_path=ROOT/'integrations/movio_customer_tools.py'
    _ct_spec=_ct_import.spec_from_file_location('movio_customer_tools',_ct_path)
    _ct_module=_ct_import.module_from_spec(_ct_spec)
    _ct_sys.modules[_ct_spec.name]=_ct_module
    exec(compile(_ct_path.read_text(encoding='utf-8'),str(_ct_path),'exec'),_ct_module.__dict__)
    _ct_module.install_backend(_ct_sys.modules[__name__])
# MOVIO_CUSTOMER_TOOLS_BOOTSTRAP_END_V1

# MOVIO_BOOKING_RELIABILITY_BOOTSTRAP_V1
if __name__ == '__main__':
    import importlib.util as _br_import
    import sys as _br_sys
    _br_path=ROOT/'integrations/movio_booking_reliability.py'
    _br_spec=_br_import.spec_from_file_location('movio_booking_reliability',_br_path)
    _br_module=_br_import.module_from_spec(_br_spec)
    exec(compile(_br_path.read_text(encoding='utf-8'),str(_br_path),'exec'),_br_module.__dict__)
    _br_engine=getattr(globals().get('_wx_mod'),'__dict__',None)
    if not isinstance(_br_engine,dict) or not callable(_br_engine.get('manual_state')):
        _br_engine=Handler.do_POST.__globals__
    _br_module.install_namespace(_br_engine,ROOT)
    _br_module.install_http(_br_sys.modules[__name__],_br_engine,ROOT)
# MOVIO_BOOKING_RELIABILITY_BOOTSTRAP_END_V1

# MOVIO_FRIENDLY_WEATHER_BOOTSTRAP_V1
if __name__ == '__main__':
    import importlib.util as _fw_import
    import sys as _fw_sys
    _fw_path=ROOT/'integrations/movio_friendly_weather.py'
    _fw_spec=_fw_import.spec_from_file_location('movio_friendly_weather',_fw_path)
    _fw_module=_fw_import.module_from_spec(_fw_spec)
    exec(compile(_fw_path.read_text(encoding='utf-8'),str(_fw_path),'exec'),_fw_module.__dict__)
    _fw_engine=getattr(globals().get('_wx_mod'),'__dict__',None)
    if not isinstance(_fw_engine,dict) or not callable(_fw_engine.get('prepare_turn')):
        _fw_engine=Handler.do_POST.__globals__
    _fw_module.install_namespace(_fw_engine,ROOT)
    _fw_module.install_http(_fw_sys.modules[__name__])
# MOVIO_FRIENDLY_WEATHER_BOOTSTRAP_END_V1

# MOVIO_CARE_API_BOOTSTRAP_V1
if __name__ == '__main__':
    import importlib.util as _cc_import
    import sys as _cc_sys
    _cc_path = ROOT / 'integrations/movio_customer_care_api.py'
    _cc_spec = _cc_import.spec_from_file_location('movio_customer_care_api', _cc_path)
    _cc_module = _cc_import.module_from_spec(_cc_spec)
    _cc_sys.modules[_cc_spec.name] = _cc_module
    exec(compile(_cc_path.read_text(encoding='utf-8-sig'), str(_cc_path), 'exec'), _cc_module.__dict__)
    _cc_module.install_backend(_cc_sys.modules[__name__])
    if getattr(Handler, '_customer_care_api_version', None) != 'customer-care-api-1.0':
        raise RuntimeError('Customer-care API v1.0 was not installed; website startup stopped.')
# MOVIO_CARE_API_BOOTSTRAP_END_V1

if __name__=='__main__':
 port=int(os.environ.get('MOVIO_PORT','8080'));print(f'MOVIO v5 at http://localhost:{port}');ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
