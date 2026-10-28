def run_backend_checks(api,care):
    import copy
    import json
    import types
    from datetime import datetime,timedelta
    from contextlib import nullcontext
    from pathlib import Path
    checks=[];calls=[]
    def check(value,label):
        if not value:raise AssertionError(label)
        checks.append(label)
    now=datetime(2031,10,19,14,25,tzinfo=care.TZ)
    location=dict(status='granted',lat=12.9123456,lng=80.2123456,observed_at=now.isoformat())
    def reverse(lat,lng):
        calls.append(('reverse',lat,lng))
        return dict(locality='Tambaram',locality_status='ok')
    def forecast(points,pickup,now=None):
        check(len(points)==2 and points[0]==points[1],'existing two-point provider protocol')
        calls.append(('forecast',points,pickup))
        hour=pickup.replace(minute=0,second=0,microsecond=0).isoformat()
        return dict(status='ok',source='Open-Meteo',fetched_at=now.timestamp(),points=[
            dict(location=role,valid_at=hour,weather_code=61,temperature_2m=27,precipitation_probability=75)
            for role in ('pickup','destination')])
    class Handler:
        path='/api/customer-care/recommend'
        role='customer'
        denied=False
        body={}
        def user(self,db):
            if self.denied:raise PermissionError('fixture authentication')
            return dict(id=7,role=self.role)
        def payload(self,limit=0):
            check(limit==32768,'request body has a bounded size')
            return self.body
        def json(self,status,payload):return status,payload
        def do_POST(self):return ('original_post',self.path)
        def do_GET(self):return ('original_get',self.path)
    server=types.SimpleNamespace(ROOT=Path('/not/a/real/project'),Handler=Handler,conn=lambda:nullcontext(object()))
    original_log=api.LOG;api.LOG=types.SimpleNamespace(warning=lambda *args,**kwargs:None)
    try:
        api.install_backend(server,providers=(reverse,forecast),clock=lambda:now,care=care)
        post=Handler.do_POST;get=Handler.do_GET
        api.install_backend(server,providers=(reverse,forecast),clock=lambda:now,care=care)
        check(Handler.do_POST is post and Handler.do_GET is get,'endpoint installation is idempotent')
        h=Handler()
        for language in ('English','Tamil','Tanglish'):
            context=dict(language=language,current_location=location,weather={'status':'ok','temperature_2m':99},
                         locality='Invented area',stage='driver_assigned',driver_id=1,ride_status='accepted')
            h.body=json.dumps({'context':context},ensure_ascii=False).encode('utf-8')
            status,result=h.do_POST()
            check(status==200 and result['language']==language,language+' raw JSON bytes accepted')
            check(result['locality']=='Tambaram' and result['weather']['temperature_c']==27,language+' server lookup overrides browser claims')
            check(result['weather']['rain_probability_pct']==75 and result['weather']['condition']=='rain',language+' actual probability and weather')
            check(len(result['recommendations'])<=2 and all(r['id']!='otp' for r in result['recommendations']),language+' dashboard scope cannot become assigned-driver context')
            check('12.9123456' not in json.dumps(result) and '80.2123456' not in json.dumps(result),language+' precise GPS is not exposed')
            before=copy.deepcopy(context);api.dashboard_response(care,context,{'id':7},reverse,forecast,now)
            check(before==context,language+' browser booking/context data remains unchanged')
        check(calls[0]==('reverse',12.912,80.212),'only approximate area is sent to the existing locality cache')
        for state in ('denied','unavailable','unsupported','timeout'):
            calls.clear();h.body={'context':dict(current_location=dict(location,status=state),weather={'status':'ok','weather_code':61})}
            status,result=h.do_POST()
            check(status==200 and result['weather']['status']=='unavailable' and result['locality'] is None,'neutral response for '+state)
            check(not calls,'no provider calls for '+state)
        for modified in ({'lat':True},{'lng':181},{'observed_at':(now-timedelta(hours=1)).isoformat()},
                         {'observed_at':(now+timedelta(minutes=10)).isoformat()}):
            calls.clear();h.body={'context':dict(current_location=dict(location,**modified))}
            status,result=h.do_POST();check(status==200 and not calls,'invalid/stale position is ignored')
        for body in (b'{',b'[]',b'{"context":[]}',b'{"context":{"n":NaN}}'):
            h.body=body;check(h.do_POST()[0]==400,'malformed request is rejected')
        h.body={'context':{}};h.denied=True;calls.clear()
        check(h.do_POST()[0]==401 and not calls,'signed-out users cannot trigger lookups')
        h.denied=False;h.role='driver'
        check(h.do_POST()[0]==403 and not calls,'driver accounts cannot use the customer endpoint')
        h.role='customer';h.path='/api/rides';check(h.do_POST()==('original_post','/api/rides'),'booking POST handler remains in control')
        h.path='/api/customer-tools/reverse-address';check(h.do_GET()==('original_get',h.path),'existing geocoding GET handler remains in control')
        h.path='/api/customer-care/health';check(h.do_GET()[1]['version']==api.VERSION,'new health endpoint reports the installed version')
        def unavailable(*args,**kwargs):return dict(status='unavailable',source='Open-Meteo')
        result=api.dashboard_response(care,dict(current_location=location),{'id':7},reverse,unavailable,now)
        check(result['ok'] and result['weather']['status']=='unavailable' and result['optional'],'forecast failure is optional')
        def failed(*args,**kwargs):raise LookupError('fixture provider failure')
        result=api.dashboard_response(care,dict(current_location=location),{'id':7},failed,forecast,now)
        check(result['locality'] is None and result['weather']['status']=='ok','locality failure does not discard valid weather')
        result=api.dashboard_response(care,dict(current_location=dict(location,observed_at=now.timestamp()*1000)),{'id':7},reverse,forecast,now)
        check(result['weather']['status']=='ok','browser millisecond timestamp is understood')
        history=care.remember_delivered({},result['recommendations'])
        again=api.dashboard_response(care,dict(current_location=location,delivered=history),{'id':7},reverse,forecast,now)
        check(not again['recommendations'],'displayed recommendations do not rotate into repeated extra tips')
        # Each request uses its own point list; inputs from the provider are not mutated.
        check(care.VERSION=='customer-care-engine-1.1-compatible','existing engine version preserved')
        return dict(passed=True,checks=len(checks),scope='Offline provider and authenticated-handler fixtures; no real user, live GPS, database writes or TTS.')
    finally:api.LOG=original_log
