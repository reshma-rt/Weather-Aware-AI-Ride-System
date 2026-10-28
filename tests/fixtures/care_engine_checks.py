def run_care_checks(care):
    import copy
    import json
    import re
    from datetime import datetime,timedelta
    now=datetime(2031,10,19,14,0,tzinfo=care.TZ)
    checks=[];covered=set()
    def check(condition,name):
        if not condition:raise AssertionError(name)
        checks.append(name)
    def weather(code=3,chance=10,temp=27,target=None):
        return dict(status='ok',source='Open-Meteo',fetched_at=now.timestamp(),points=[
            dict(location='pickup',weather_code=code,precipitation_probability=chance,temperature_2m=temp,valid_at=(target or now).isoformat())])
    def context(stage='booking_details',**values):
        result=dict(stage=stage,lang='English',now=now.isoformat(),session_id='fixture-session',
            pickup='Tambaram',destination='Vandalur',pickup_at=now.isoformat(),vehicle='Mini',count=1)
        result.update(values);return result
    def evaluate(value,**kwargs):
        result=care.recommend(value,**kwargs);covered.update(result['candidate_ids'])
        check(len(result['recommendations'])<=2,'at most two recommendations')
        check(all(not row['question'] and '?' not in row['text'] for row in result['recommendations']),'optional advice asks no follow-up question')
        return result
    def selected(result):return {r['id'] for r in result['recommendations']}
    def candidates(result):return set(result['candidate_ids'])
    def location(status='granted',name='Tambaram'):
        return dict(status=status,locality=name,locality_status='ok',observed_at=now.isoformat())

    for lang in ('English','Tamil','Tanglish'):
        rainy=context(lang=lang,weather=weather(61,75))
        before=copy.deepcopy(rainy);r=evaluate(rainy)
        check('rain_preparation' in selected(r),lang+' rain preparation selected')
        check('75%' in r['recommendations'][0]['text'],lang+' actual rain percentage retained')
        check(rainy==before,lang+' booking slots and weather remain unchanged')
        texts=r['greeting']+' '+''.join(x['text'] for x in r['recommendations'])
        check(bool(re.search(r'[\u0B80-\u0BFF]',texts))==(lang=='Tamil'),lang+' display script is correct')
        for failed in ('unavailable','pending','outside_forecast_range'):
            r=evaluate(context('before_confirmation',lang=lang,weather=dict(status=failed)))
            check(r['weather'] is None and 'rain_preparation' not in candidates(r),lang+' '+failed+' cannot invent a forecast')
            check(r['optional'] is True,lang+' weather failure does not require consent')
        for state in ('denied','unavailable','unsupported','timeout'):
            r=evaluate(context('dashboard',lang=lang,current_location=location(state),current_weather=weather(61,95)))
            check(r['locality'] is None and r['weather'] is None and not r['recommendations'],lang+' '+state+' has a neutral greeting')
    r=evaluate(context('dashboard',current_location=location(),current_weather=weather(0,0,27)))
    check(r['locality']=='Tambaram' and 'Tambaram' in r['greeting'],'actual locality in dashboard greeting')
    check('phone_readiness' in selected(r),'phone readiness is available for dashboard travel preparation')
    for name in ('Zone 14','Ward 8','Map pin (12.9,80.2)','Selected location','Kottivakkam Kuppam Road'):
        r=evaluate(context('dashboard',current_location=location(name=name),current_weather=weather()))
        check(r['locality'] is None,'administrative/road/fallback label is not a locality: '+name)
    old_location=location();old_location['observed_at']=(now-timedelta(hours=2)).isoformat()
    r=evaluate(context('dashboard',current_location=old_location,current_weather=weather(61,95)))
    check(r['locality'] is None and r['weather'] is None and not r['recommendations'],'stale GPS does not become current-locality evidence')

    r=evaluate(context(weather=weather(0,0,35)));check('heat_protection' in selected(r),'heat protection uses measured forecast temperature')
    for h in (0,1,23):
        target=now.replace(hour=h)+timedelta(days=1)
        r=evaluate(context(pickup_at=target.isoformat(),weather=weather(61,80,target=target)))
        check('late_night_safety' in selected(r),'late-night advice for hour '+str(h))
    r=evaluate(context(pickup_at=now.astimezone(care.timezone.utc).replace(hour=18).isoformat()))
    check('late_night_safety' in candidates(r),'UTC input is converted to Asia/Kolkata')
    r=evaluate(context('before_confirmation'))
    check('pickup_guidance' in selected(r),'accessible pickup guidance before confirmation')
    assigned=context('driver_assigned',ride_id=7,ride_status='accepted',driver_id=9,pickup_verified=False)
    r=evaluate(assigned);check('otp_safety' in selected(r),'OTP safety requires an assigned driver')
    for driver,status,verified in ((None,'accepted',False),(9,'requested',False),(9,'in_progress',True),(9,'accepted',True)):
        r=evaluate(context('driver_assigned',ride_status=status,driver_id=driver,pickup_verified=verified))
        check('otp_safety' not in candidates(r),'OTP stage and driver association are respected')
    r=evaluate(context(count=4,vehicle='Mini'));check('passenger_comfort' in selected(r),'group comfort uses passenger count')
    r=evaluate(context(count=4,vehicle='Auto'));check('passenger_comfort' in selected(r),'over-capacity vehicle gets preparation guidance')
    for place in ('Chennai Airport','Chennai Central','Apollo Hospital'):
        r=evaluate(context(destination=place));check('destination_reminder' in selected(r),'destination reminder: '+place)
    for place in ('Airport Road','Chennai Airport Metro','Hospital Street'):
        r=evaluate(context(destination=place));check('destination_reminder' not in candidates(r),'road/metro is not assumed to be a terminal or hospital visit')
    due=now+timedelta(minutes=10)
    r=evaluate(context('before_pickup',ride_status='scheduled',pickup_at=due.isoformat()))
    check('departure_readiness' in selected(r),'scheduled pickup readiness without invented driver ETA')
    check(all('ETA' not in row['text'] for row in r['recommendations']),'schedule reminder does not claim driver arrival')
    eta=dict(minutes=4,updated_at=now.isoformat(),source='tracking-route-fixture',verified=True,live_driver_position=True)
    approach=context('driver_approaching',ride_id=7,ride_status='arriving',driver_id=9,pickup_verified=False,driver_eta=eta)
    r=evaluate(approach);check('departure_readiness' in selected(r),'fresh ETA backed by live driver position')
    for change in ({'updated_at':(now-timedelta(minutes=10)).isoformat()},{'live_driver_position':False},{'verified':False}):
        bad=context('driver_approaching',ride_status='arriving',driver_id=9,driver_eta={**eta,**change},pickup_at=(now+timedelta(hours=2)).isoformat())
        r=evaluate(bad);check('departure_readiness' not in candidates(r),'stale/unverified/static route ETA is not announced')

    traffic=dict(extra_minutes=8,live=True,verified=True,source='fixture-live-provider',updated_at=now.isoformat())
    r=evaluate(context(traffic=traffic));check('traffic_awareness' not in candidates(r),'traffic disabled without configured reliable source')
    r=evaluate(context(traffic=traffic),policy={'trusted_traffic_sources':['fixture-live-provider']})
    check('traffic_awareness' in selected(r),'traffic advice with explicitly configured live fixture evidence')
    for name in ('OSRM','straight-line route','static_route'):
        r=evaluate(context(traffic={**traffic,'source':name}),policy={'trusted_traffic_sources':[name]})
        check('traffic_awareness' not in candidates(r),'static route data is not live traffic: '+name)
    r=evaluate(context('before_confirmation',accessibility_requested=True));check('accessibility_assistance' in selected(r),'optional requested boarding support')
    r=evaluate(context('before_confirmation'));check('accessibility_assistance' not in candidates(r),'no disability or accessibility need is inferred')
    r=evaluate(context('ride_completed',ride_id=7,ride_status='completed'))
    check(selected(r)=={'arrival_care'},'belongings reminder after actual ride completion')
    for stage,status in (('done','requested'),('ride_completed','requested'),('confirm','cancelled')):
        r=evaluate(context(stage,ride_status=status));check('arrival_care' not in candidates(r),'booking completion is not journey completion')
    r=evaluate(context('before_confirmation',ride_status='cancelled',weather=weather(61,90)))
    check(not r['recommendations'],'cancelled booking has no preparation advice')

    # Delivery is explicit: interrupted/generated-only speech cannot consume it.
    request=context('before_confirmation',weather=weather(61,80),pickup_at=now.replace(hour=23).isoformat())
    request['weather']=weather(61,80,target=now.replace(hour=23));prior=copy.deepcopy(request)
    first=care.recommend(request);again=care.recommend(request)
    check(first==again,'recommendation generation alone never marks advice as heard')
    history={};updated=care.remember_delivered(history,first['recommendations'],'acknowledged')
    check(history=={} and request==prior,'history and context inputs are not mutated')
    check(not care.recommend(request,delivered=updated)['recommendations'],'at most two delivered suggestions per stage; polling cannot drip all rules')
    next_stage={**request,'stage':'driver_assigned','ride_status':'accepted','driver_id':9,'pickup_verified':False}
    r=evaluate(next_stage,delivered=updated)
    check('otp_safety' in selected(r),'new ride stage enables its own relevant safety advice')
    check('rain_preparation' not in candidates(r),'acknowledged weather advice is not repeated at another stage')
    check(care.remember_delivered(updated,first['recommendations'],'acknowledged')==updated,'repeated delivery does not append duplicate records')
    preparation=context('before_confirmation',care_scope_id='stable-fixture-journey')
    shown=care.recommend(preparation)
    ledger=care.remember_delivered({},shown['recommendations'])
    later={**preparation,'stage':'driver_assigned','ride_id':99,'driver_id':9,'ride_status':'accepted','pickup_verified':False}
    r=evaluate(later,delivered=ledger)
    check('phone_readiness' not in candidates(r),'stable care scope survives allocation of a database booking ID')
    for v,phrase in (('Bike','covered vehicle'),('Auto','open sides')):
        r=evaluate(context(vehicle=v,weather=weather(61,80)))
        check(any(phrase in row['text'].casefold() for row in r['recommendations']),'vehicle-specific rain preparation for '+v)
    limited=care.remember_delivered({str(i):'delivered' for i in range(300)},first['recommendations'],max_items=32)
    check(len(limited)==32,'bounded delivery history')

    base_weather=weather(3,0,0);r=evaluate(context(weather=base_weather))
    check(r['weather']['max_temperature_c']==0 and r['weather']['max_rain_probability_pct']==0,'zero is preserved as a real weather value')
    for raw in (
        {**weather(),'fetched_at':(now-timedelta(hours=2)).timestamp()},
        {**weather(),'fetched_at':(now+timedelta(hours=1)).timestamp()},
        {**weather(),'source':'Unverified guess'},
        weather(target=now+timedelta(hours=3))):
        check(evaluate(context(weather=raw))['weather'] is None,'stale, future-fetched, wrong-source or wrong-hour forecast rejected')
    r=evaluate(context(weather=weather(temp=float('nan'),chance=float('nan'),code=None)))
    check(r['weather'] is None,'non-finite weather does not become a forecast')
    storm_time=now.replace(hour=23)
    r=evaluate(context(pickup_at=storm_time.isoformat(),weather=weather(95,95,40,target=storm_time)))
    check('rain_preparation' in selected(r) and 'late_night_safety' in selected(r),'severe weather and late-night safety outrank general tips')
    check(len([row for row in r['recommendations'] if row['group']=='weather'])<=1,'weather recommendations do not crowd the card')
    secret=context('before_confirmation',pickup_geo={'lat':12.9,'lng':80.2},destination_geo={'lat':13.0,'lng':80.3},pickup_otp='SECRET_OTP',driver_phone='SECRET_PHONE')
    encoded=json.dumps(evaluate(secret),ensure_ascii=False)
    check('SECRET_OTP' not in encoded and 'SECRET_PHONE' not in encoded and '12.9' not in encoded,'precise GPS, OTP and phone are not emitted in recommendation output')
    for limit in (0,1,2):check(len(care.recommend(context('before_confirmation'),limit=limit)['recommendations'])<=limit,'explicit output limit '+str(limit))
    for bad in ({'lang':'unsupported'},{'now':'bad timestamp'}):
        try:care.recommend(context(**bad))
        except ValueError:pass
        else:raise AssertionError('invalid context must be rejected')
        checks.append('invalid context is rejected')
    check(covered==set(care.RULE_IDS),'all twelve rule families exercised')
    return dict(passed=True,checks=len(checks),rule_families=sorted(covered),
        scope='Offline deterministic fixtures; no real GPS, external APIs, speech generation or live booking actions.')
