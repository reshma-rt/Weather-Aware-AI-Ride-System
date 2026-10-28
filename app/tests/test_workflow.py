"""Standard-library HTTP integration tests, isolated from the user's database."""
import concurrent.futures, hashlib, importlib.util, json, sqlite3, tempfile, threading, time, unittest, urllib.request, urllib.error
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from pathlib import Path
spec=importlib.util.spec_from_file_location('movio_server',Path(__file__).resolve().parents[1]/'server.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class QuietHandler(s.Handler):
 def log_message(self,*args):pass
class Workflow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();s.DB=Path(self.tmp.name)/'test.db';s.setup()
  self.server=ThreadingHTTPServer(('127.0.0.1',0),QuietHandler)
  threading.Thread(target=self.server.serve_forever,daemon=True).start();self.base=f'http://127.0.0.1:{self.server.server_port}/api'
  self.a=self.account('customer',1);self.b=self.account('customer',2)
  self.suv=self.account('driver',3,'SUV');self.mini=self.account('driver',4,'Mini');self.suv2=self.account('driver',5,'SUV')
 def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
 def call(self,client,path,p=None,code=200):
  req=urllib.request.Request(self.base+path,data=json.dumps(p).encode() if p is not None else None,headers={'Content-Type':'application/json'})
  try:
   with client.open(req) as r:status=r.status;data=json.load(r)
  except urllib.error.HTTPError as e:status=e.code;data=json.load(e)
  self.assertEqual(status,code,data);return data
 def account(self,role,n,vt=None):
  client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
  p=dict(name=f'Person {n}',phone=f'+91900000000{n}',password='demo12345',role=role)
  if role=='driver':p.update(vehicle_type=vt,vehicle_number=f'TN09AB000{n}')
  self.call(client,'/register',p,201);self.call(client,'/login',p);return client
 def ride(self,client=None,vehicle='SUV'):
  return self.call(client or self.a,'/rides',dict(pickup='Chennai Central',destination='Airport',plat=13.08,plng=80.27,dlat=12.99,dlng=80.17,vehicle=vehicle,fare=500),201)['id']
 def accept(self,rid,driver=None):self.call(driver or self.suv,f'/rides/{rid}/status',{'status':'accepted'})
 def request(self,rid):self.call(self.suv,f'/rides/{rid}/location-request',{})
 def grant(self,rid):return self.call(self.a,f'/rides/{rid}/location-response',{'allow':True})['expires']
 def visible(self,client,rid):return self.call(client,f'/locations?ride_id={rid}')['locations']
 def test_vehicle_filter_decline_and_race(self):
  rid=self.ride();self.assertEqual(self.call(self.mini,'/rides')['rides'],[])
  self.call(self.mini,f'/rides/{rid}/status',{'status':'accepted'},403)
  self.call(self.suv,f'/rides/{rid}/decline',{});self.assertEqual(self.call(self.suv,'/rides')['rides'],[])
  self.assertEqual(self.call(self.suv2,'/rides')['rides'][0]['id'],rid)
  self.accept(rid,self.suv2)
  self.call(self.suv,f'/rides/{rid}/status',{'status':'accepted'},409)
  self.call(self.mini,f'/locations?ride_id={rid}',code=403)
  # Fresh same-type request, two competitors: exactly one accept wins.
  rid2=self.ride(self.b,'Mini');mini2=self.account('driver',6,'Mini')
  def attempt(c):
   req=urllib.request.Request(self.base+f'/rides/{rid2}/status',data=b'{"status":"accepted"}',headers={'Content-Type':'application/json'})
   try:
    with c.open(req) as r:return r.status
   except urllib.error.HTTPError as e:return e.code
  with concurrent.futures.ThreadPoolExecutor() as pool:codes=list(pool.map(attempt,[self.mini,mini2]))
  self.assertEqual(sorted(codes),[200,409])
 def test_consent_bidirectional_expiry_no_renewal(self):
  rid=self.ride();self.accept(rid)
  self.call(self.a,'/locations',dict(lat=13,lng=80),403)
  self.call(self.a,f'/rides/{rid}/location-response',{'allow':True},403)
  self.call(self.suv2,f'/rides/{rid}/location-request',{},403)
  self.call(self.suv,'/locations',dict(lat=13.1,lng=80.2))
  self.assertEqual(self.visible(self.a,rid)[0]['role'],'driver')
  self.request(rid);expiry=self.grant(rid)
  self.assertAlmostEqual(expiry-time.time(),900,delta=2)
  self.call(self.a,'/locations',dict(lat=13.2,lng=80.3))
  self.assertEqual({p['role'] for p in self.visible(self.suv,rid)},{'driver','customer'})
  details=self.call(self.a,'/rides')['rides'][0]
  self.assertEqual(details['driver_vehicle_number'],'TN09AB0003');self.assertEqual(details['driver_name'],'Person 3')
  self.call(self.b,f'/rides/{rid}/location-response',{'allow':True},403)
  self.call(self.a,'/consent',{},409)
  self.request(rid);self.assertEqual(self.call(self.a,'/consent')['expires'],expiry)
  self.call(self.suv,f'/rides/{rid}/status',{'status':'in_progress'})
  self.assertIn('customer',{p['role'] for p in self.visible(self.suv,rid)})
  with s.conn() as c:c.execute('UPDATE location_requests SET expires=? WHERE ride_id=?',(time.time()-1,rid))
  self.assertNotIn('customer',{p['role'] for p in self.visible(self.suv,rid)})
  self.call(self.a,'/locations',dict(lat=13.2,lng=80.3),403)
  self.request_expired(rid)
  with s.conn() as c:self.assertIsNone(c.execute('SELECT * FROM locations WHERE user_id=1').fetchone())
 def request_expired(self,rid):self.call(self.suv,f'/rides/{rid}/location-request',{},409)
 def test_denial_reprompt_revocation_and_end(self):
  rid=self.ride();self.accept(rid);self.request(rid)
  self.call(self.a,f'/rides/{rid}/location-response',{'allow':False})
  self.call(self.a,'/locations',dict(lat=13,lng=80),403)
  old=self.call(self.a,'/rides')['rides'][0]['location_request']['requested']
  self.request(rid);new=self.call(self.a,'/rides')['rides'][0]['location_request']['requested'];self.assertGreater(new,old)
  self.grant(rid);self.call(self.a,'/locations',dict(lat=13,lng=80))
  self.call(self.a,'/locations/revoke',{})
  self.assertEqual(self.call(self.a,'/consent')['expires'],0)
  self.assertEqual(self.visible(self.suv,rid),[]);self.request_expired(rid)
  self.call(self.suv,f'/rides/{rid}/status',{'status':'cancelled'})
  self.call(self.suv,f'/locations?ride_id={rid}',code=403)
  self.assertEqual(self.call(self.a,'/rides')['rides'][0]['location_share_until'],0)
 def test_completion_ends_access(self):
  rid=self.ride();self.accept(rid);self.request(rid);self.grant(rid)
  self.call(self.a,'/locations',dict(lat=13,lng=80))
  self.call(self.suv,f'/rides/{rid}/status',{'status':'in_progress'})
  self.call(self.suv,f'/rides/{rid}/status',{'status':'completed'})
  self.assertEqual(self.call(self.a,'/consent')['expires'],0)
  self.call(self.a,'/locations',dict(lat=13,lng=80),403)
  self.call(self.suv,f'/locations?ride_id={rid}',code=403)
 def test_driver_busy_and_customer_duplicate(self):
  rid=self.ride();self.accept(rid);rid2=self.ride(self.b)
  self.assertEqual([r['id'] for r in self.call(self.suv,'/rides')['rides']],[rid])
  self.call(self.suv,f'/rides/{rid2}/status',{'status':'accepted'},409)
  self.call(self.a,'/rides',dict(pickup='A',destination='B',plat=13,plng=80,dlat=14,dlng=81,vehicle='SUV'),409)
  self.call(self.suv,'/driver-profile',dict(name='New driver',vehicle_type='Mini',vehicle_number='TN09A1234'),409)
 def test_legacy_profile_migration(self):
  # Existing driver accounts can complete their vehicle profile after login.
  with s.conn() as c:c.execute('DELETE FROM driver_profiles WHERE user_id=3')
  self.assertIsNone(self.call(self.suv,'/me')['vehicle_type'])
  self.call(self.suv,'/driver-profile',dict(name='Driver name',vehicle_type='SUV',vehicle_number='TN 09 AB 1234'))
  self.assertEqual(self.call(self.suv,'/me')['vehicle_number'],'TN 09 AB 1234')
  with s.conn() as c:
   c.execute('DROP TABLE location_requests')
   c.execute("CREATE TABLE location_requests(ride_id INTEGER PRIMARY KEY,driver_id INTEGER,customer_id INTEGER,requested REAL,status TEXT)")
   c.execute("INSERT INTO location_requests VALUES(1,3,1,0,'granted')")
  s.setup()
  with s.conn() as c:
   row=c.execute('SELECT * FROM location_requests').fetchone();self.assertEqual(row['expires'],0);self.assertEqual(row['status'],'expired')
if __name__=='__main__':unittest.main(verbosity=2)
