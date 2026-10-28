"""Offline regression checks: real SQLite/HTTP, simulated weather and voice models.

run_tests(server_source=Path('/kaggle/working/MOVIO_MAIN_WEBSITE/server.py'))
uses an isolated copy of the supplied backend; no real accounts are changed.
"""
import asyncio
import contextvars
import copy
import http.client
import importlib.util
import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
import hashlib

import movio_weather_guard as wx


def good_state():
    when = datetime.now(wx.TZ).replace(second=0, microsecond=0) + timedelta(days=1)
    state=dict(lang='English', mode='book', stage='confirm', count=1, vehicle='Bike',
        pickup='Chennai Central', destination='Airport', pickup_geo={'lat':13.08,'lng':80.27},
        destination_geo={'lat':12.99,'lng':80.17}, when=when.strftime('%Y-%m-%d %H:%M'),
        pickup_at=when.isoformat(),fare={'km':20,'fare':168},weather={'status':'ok','condition':'rain'})
    state['_wx_weather_consent']={'scope':wx.weather_consent_scope(state),'accepted_at':time.time()}
    return state


class Reply:
    def __init__(self, payload): self.payload=payload
    def raise_for_status(self): pass
    def json(self): return self.payload


def weather_get(code=61, probability=80, missing=False,temperature=28,feels_like=30):
    def get(url, params, timeout):
        start=params['start_date']
        hours=[f'{start}T{h:02}:00' for h in range(24)]
        row={'hourly':{'time':hours,'weather_code':[None if missing else code]*24,
            'precipitation_probability':[probability]*24,'precipitation':[2]*24,'temperature_2m':[temperature]*24,
            'apparent_temperature':[feels_like]*24}}
        return Reply([copy.deepcopy(row) for _ in params['latitude'].split(',')])
    return get


def manual_payload(lang='English',vehicle='Bike'):
    s=good_state()
    return dict(language=lang,count=1,vehicle=vehicle,pickup=s['pickup'],destination=s['destination'],
        plat=s['pickup_geo']['lat'],plng=s['pickup_geo']['lng'],dlat=s['destination_geo']['lat'],dlng=s['destination_geo']['lng'],
        pickup_at=s['pickup_at'],km=s['fare']['km'],fare=s['fare']['fare'])


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=wx.GuardDB(pathlib.Path(self.tmp.name)/'test.db')
        with self.db.connect() as c:
            c.execute('''CREATE TABLE rides(id INTEGER PRIMARY KEY,customer_id INTEGER,pickup TEXT,destination TEXT,
                plat REAL,plng REAL,dlat REAL,dlng REAL,vehicle TEXT,fare INTEGER,status TEXT,driver_id INTEGER,
                source TEXT,created REAL,updated REAL)''')
        self.db.setup()
        self.binding=self.db.create(7);self.sid=self.binding['call_id'];self.state=good_state()
        self.epoch=self.db.begin(self.sid);self.db.stash(self.sid,self.epoch,self.state)
    def tearDown(self): self.tmp.cleanup()
    def permit(self):
        nonce=self.db.summary(self.sid,self.epoch,self.state)
        self.assertTrue(self.db.played(self.sid,self.epoch,nonce))
        return self.db.permit(self.sid,self.epoch,nonce,self.state)
    def commit(self, token, owner=7):
        with self.db.connect() as c:
            return self.db.commit(c,owner,token,lambda c,rid:None)


class Dates(unittest.TestCase):
    def test_relative_english_and_tamil(self):
        now=datetime(2026,10,17,19,0,tzinfo=wx.TZ)
        for text in ('tomorrow at 9 AM','நாளை காலை 9 மணிக்கு','naalaiku 9 am'):
            self.assertEqual(wx.resolve_pickup(text,now).isoformat(),'2026-10-18T09:00:00+05:30')
    def test_iso_and_evening(self):
        now=datetime(2026,10,17,19,0,tzinfo=wx.TZ)
        self.assertEqual(wx.resolve_pickup('2026-10-18 21:30',now).hour,21)
        self.assertEqual(wx.resolve_pickup('tomorrow evening 9',now).hour,21)
    def test_ambiguous_and_past_are_clarified(self):
        now=datetime(2026,10,17,19,0,tzinfo=wx.TZ)
        for raw in ('tomorrow 9','2026-02-30 09:00','today 9 AM'):
            with self.assertRaises(wx.GuardError): wx.resolve_pickup(raw,now)
    def test_weekday_is_resolved(self):
        now=datetime(2026,10,17,19,0,tzinfo=wx.TZ)
        self.assertEqual(wx.resolve_pickup('Friday at 9 AM',now).isoformat(),'2026-10-23T09:00:00+05:30')
    def test_other_spoken_dates(self):
        now=datetime(2026,10,17,19,0,tzinfo=wx.TZ)
        for raw in ('day after tomorrow 9 AM','நாளை மறுநாள் காலை 9 மணிக்கு','அக்டோபர் 19 தேதி 2026 காலை 9 மணிக்கு','19/10/2026 9 AM','October 19, 2026 9 AM'):
            with self.subTest(raw=raw):
                self.assertEqual(wx.resolve_pickup(raw,now).isoformat(),'2026-10-19T09:00:00+05:30')
    def test_complete_tamil_evening_time_is_not_ambiguous(self):
        now=datetime(2026,10,17,18,0,tzinfo=wx.TZ)
        for raw in ('எனக்கு SUV வேண்டும் இன்று இரவு 07:00 மணிக்கு எனக்கு cab வேணும்','இன்று இரவு ஏழு மணிக்கு'):
            self.assertEqual(wx.resolve_pickup(raw,now).isoformat(),'2026-10-17T19:00:00+05:30')
    def test_tamil_period_only_keeps_date_and_hour(self):
        now=datetime(2026,10,17,18,0,tzinfo=wx.TZ)
        s={'stage':'time'}
        pickup,reason=wx.update_time_memory(s,'இன்று 07:00',now)
        self.assertEqual(reason,'clarify_period')
        pickup,reason=wx.update_time_memory(s,'இரவு',now)
        self.assertIsNone(reason);self.assertEqual(pickup.hour,19);self.assertEqual(pickup.day,17)
    def test_date_and_time_are_spoken_without_numeric_date_or_timezone(self):
        self.assertEqual(wx.spoken_datetime('2025-09-15T19:00:00+05:30'),
                         'September 15, 2025, at 7:00 PM')
        for lang in ('English','Tamil','Tanglish'):
            spoken=wx.spoken_datetime('2026-10-17T22:30:00+05:30',lang)
            self.assertNotRegex(spoken,r'India|இந்திய|05:30');self.assertIn('2026',spoken);self.assertIn('10:30',spoken)
    def test_tamil_yes_keeps_vowel_marks_and_ignores_punctuation(self):
        for raw in ('ஆம்.','ஆமாம்!','சரி.'):
            self.assertIn(wx.reply_normalized(raw),wx.POSITIVE)


class Weather(unittest.TestCase):
    def setUp(self):
        self.points=[good_state()['pickup_geo'],good_state()['destination_geo']]
        self.when=datetime.now(wx.TZ)+timedelta(days=1)
    def test_rain_and_cloud_conditions(self):
        self.assertEqual(wx.WeatherClient(weather_get()).forecast(self.points,self.when)['condition'],'rain')
        self.assertEqual(wx.WeatherClient(weather_get(3,20)).forecast(self.points,self.when)['condition'],'cloudy')
    def test_cache_reuses_payload_but_selects_correct_hour(self):
        client=wx.WeatherClient(weather_get())
        a=client.forecast(self.points,self.when.replace(hour=9))
        b=client.forecast(self.points,self.when.replace(hour=10))
        self.assertEqual(client.requests,1);self.assertEqual(client.hits,1)
        self.assertNotEqual(a['points'][0]['valid_at'],b['points'][0]['valid_at'])
    def test_null_data_is_not_reported_as_clear(self):
        self.assertEqual(wx.WeatherClient(weather_get(missing=True)).forecast(self.points,self.when)['status'],'unavailable')
    def test_api_failure_and_forecast_horizon(self):
        def fail(*a,**k):raise TimeoutError()
        client=wx.WeatherClient(fail)
        self.assertEqual(client.forecast(self.points,self.when)['status'],'unavailable')
        self.assertEqual(client.forecast(self.points,self.when+timedelta(days=30))['status'],'outside_forecast_range')
    def test_capacity_and_language_messages(self):
        s=good_state();s['count']=5
        self.assertIn('SUV',wx.advisory(s));self.assertNotIn('Mini',wx.advisory(s))
        for lang in ('English','Tamil','Tanglish'):
            s['lang']=lang;self.assertTrue(wx.advisory(s))


class CustomerAdvice(unittest.TestCase):
    def state(self,code=61,probability=80,temperature=28,feels_like=30,vehicle='Bike',lang='English'):
        s=good_state();s.update(vehicle=vehicle,lang=lang)
        s['weather']=wx.WeatherClient(weather_get(code,probability,temperature=temperature,feels_like=feels_like)).forecast(
            [s['pickup_geo'],s['destination_geo']],datetime.fromisoformat(s['pickup_at']))
        return s
    def test_heavy_rain_is_based_on_condition_not_probability(self):
        ordinary=self.state(61,99);heavy=self.state(65,30)
        self.assertFalse(ordinary['weather']['heavy_rain']);self.assertTrue(heavy['weather']['heavy_rain'])
        self.assertNotIn('Heavy rain',wx.advisory(ordinary));self.assertIn('Heavy rain',wx.advisory(heavy))
        self.assertIn('bike may be unsuitable',wx.advisory(heavy))
    def test_auto_and_covered_car_have_distinct_precautions(self):
        self.assertIn('exposed sides',wx.advisory(self.state(vehicle='Auto')))
        for vehicle in ('Mini','Sedan','SUV'):
            text=wx.advisory(self.state(vehicle=vehicle));self.assertIn('umbrella for boarding',text)
            self.assertNotIn('bike may be unsuitable',text)
    def test_high_temperature_is_not_labelled_pleasant(self):
        s=self.state(0,0,41,44)
        self.assertTrue(s['weather']['heat']);self.assertFalse(s['weather']['pleasant'])
        text=wx.advisory(s);self.assertIn('Very hot',text);self.assertIn('carry water',text);self.assertNotIn('pleasant',text)
    def test_feels_like_threshold_alone_can_trigger_heat_advice(self):
        self.assertTrue(self.state(0,0,34,42)['weather']['heat'])
    def test_pleasant_weather_message(self):
        s=self.state(0,0,28,29);self.assertTrue(s['weather']['pleasant']);self.assertIn('looks pleasant',wx.advisory(s))
    def test_rain_and_heat_precautions_can_both_be_present(self):
        s=self.state(61,90,39,43,vehicle='Auto');text=wx.advisory(s)
        self.assertIn('Rain is expected',text);self.assertIn('Very hot',text);self.assertIn('exposed sides',text)
    def test_advice_never_modifies_customer_choices(self):
        s=self.state(65,99,40,44);before=copy.deepcopy(s)
        wx.advisory(s);wx.summary_text(None,s)
        self.assertEqual(s,before)
    def test_tamil_weather_has_no_english_templates(self):
        s=self.state(65,90,40,44,lang='Tamil');s.update(pickup='சென்னை',destination='தாம்பரம்')
        text=wx.advisory(s);self.assertNotRegex(text,r'[A-Za-z]');self.assertIn('குடிநீர்',text)
    def test_tanglish_weather_and_date_use_latin_script(self):
        s=self.state(65,90,40,44,lang='Tanglish');text=wx.advisory(s)+' '+wx.summary_text(None,s)
        self.assertNotRegex(text,r'[\u0b80-\u0bff]');self.assertIn('mazhai',text);self.assertNotIn('Rain is expected',text)
    def test_successful_booking_closes_in_selected_language(self):
        expected={'Tamil':'நன்றி! உங்கள் பயணம் இனிமையாக அமையட்டும்!','Tanglish':'Nandri! Ungal payanam inimaiyaaga amaiyattum!','English':'Thank you! Have a wonderful journey!'}
        for lang,closing in expected.items():
            self.assertEqual(wx.closing_message(lang),closing);self.assertTrue(wx.completion_message(lang,123).endswith(closing))
    def test_sentence_clips_preserve_decimal_and_place_initial(self):
        parts=wx.speech_segments('At T. Nagar. Distance 3.5 kilometres. Thank you! Have a wonderful journey!')
        self.assertEqual(parts,['At T. Nagar.','Distance 3.5 kilometres.','Thank you!','Have a wonderful journey!'])


class Confirmation(Fixtures):
    def test_binding_requires_secret(self):
        self.assertEqual(self.db.bind(self.sid,self.binding['bind_token'])['owner'],7)
        with self.assertRaises(wx.GuardError):self.db.bind(self.sid,'wrong')
    def test_playback_or_explicit_read_ack_required(self):
        nonce=self.db.summary(self.sid,self.epoch,self.state)
        with self.assertRaises(wx.GuardError):self.db.permit(self.sid,self.epoch,nonce,self.state)
        self.assertFalse(self.db.played(self.sid,self.epoch,'old-nonce'))
    def test_interrupt_rejects_outdated_confirmation(self):
        token=self.permit();self.db.begin(self.sid,interrupt=True)
        with self.assertRaises(wx.GuardError):self.commit(token)
    def test_late_worker_cannot_overwrite_newer_turn(self):
        old=self.epoch;self.db.begin(self.sid)
        with self.assertRaises(wx.GuardError):self.db.stash(self.sid,old,self.state)
    def test_changed_details_revoke_previous_summary(self):
        token=self.permit();self.state['vehicle']='Mini';self.db.stash(self.sid,self.epoch,self.state)
        with self.assertRaises(wx.GuardError):self.commit(token)
    def test_different_snapshot_cannot_reuse_ack(self):
        nonce=self.db.summary(self.sid,self.epoch,self.state);self.db.played(self.sid,self.epoch,nonce)
        self.state['fare']['fare']+=1
        with self.assertRaises(wx.GuardError):self.db.permit(self.sid,self.epoch,nonce,self.state)
    def test_other_account_cannot_redeem(self):
        token=self.permit()
        with self.assertRaises(PermissionError):self.commit(token,owner=8)
    def test_retry_creates_one_ride(self):
        token=self.permit()
        with ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(lambda _:self.commit(token),range(24)))
        self.assertEqual(len({r['id'] for r in rows}),1)
        with self.db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM rides').fetchone()[0],1)
    def test_stored_fields_and_scheduled_status(self):
        result=self.commit(self.permit())
        with self.db.connect() as c:row=c.execute('SELECT * FROM rides WHERE id=?',(result['id'],)).fetchone()
        self.assertEqual(row['passengers'],1);self.assertEqual(row['pickup_time'],self.state['pickup_at'])
        self.assertEqual(row['status'],'scheduled');self.assertEqual(json.loads(row['weather_json'])['condition'],'rain')
    def test_commit_wins_then_interrupt_reports_saved_booking(self):
        self.commit(self.permit())
        with self.assertRaisesRegex(wx.GuardError,'already saved'):self.db.begin(self.sid,interrupt=True)
    def test_expired_permit_and_capacity_are_rejected(self):
        token=self.permit()
        with self.db.connect() as c:c.execute('UPDATE wx_permits SET expires=0')
        with self.assertRaises(wx.GuardError):self.commit(token)
        self.state['count']=2;token=self.permit()
        with self.assertRaisesRegex(wx.GuardError,'capacity'):self.commit(token)
    def test_release_only_within_dispatch_window(self):
        result=self.commit(self.permit())
        with self.db.connect() as c:c.execute('UPDATE rides SET pickup_time=? WHERE id=?',((datetime.now(wx.TZ)+timedelta(minutes=10)).isoformat(),result['id']))
        self.db.release_due()
        with self.db.connect() as c:self.assertEqual(c.execute('SELECT status FROM rides WHERE id=?',(result['id'],)).fetchone()[0],'requested')


class FakeBridge:
    PUBLIC_URL='https://test.invalid'
    MESSAGES={'English':{},'Tamil':{},'Tanglish':{}}
    CURRENT_LANGUAGE=contextvars.ContextVar('test_language',default='English')
    def __init__(self):
        async def original(ws):raise RuntimeError('legacy route used unexpectedly')
        self.app=types.SimpleNamespace(routes=[types.SimpleNamespace(path='/browser-call',endpoint=original)])
        self.block=threading.Event();self.block.set();self.started=threading.Event()
        self.spoken=[]
    def new_session(self,lang,mode):
        s=good_state();s.update(lang=lang,stage='time');return s
    def say(self,s,key,**kwargs):
        return 'summary '+str(kwargs) if key=='summary' else key
    def speak(self,text):
        self.spoken.append(text)
        if 'At your pickup' in text:self.started.set();self.block.wait(3)
        return 'FAKE_AUDIO'
    def handle(self,s,text):
        if text in wx.CAPACITY:s['vehicle']=text
        elif 'tomorrow' in text:s['when']=text
        s['stage']='fare';return 'wait',None
    def road_fare(self,s):
        s['pickup_geo']=s.get('pickup_geo') or {'lat':13.08,'lng':80.27}
        s['destination_geo']=s.get('destination_geo') or {'lat':12.92,'lng':80.12}
        return {'km':20,'fare':168 if s['vehicle']=='Bike' else 336}
    def geocode(self,text):return {'lat':13.08 if 'Central' in text else 12.92,'lng':80.27 if 'Central' in text else 80.12}


class TurnPreparation(unittest.TestCase):
    def test_spoken_complete_date_does_not_skip_missing_ride_details(self):
        s=good_state();s['count']=None
        out,answer=wx.prepare_turn(FakeBridge(),wx.WeatherClient(weather_get()),s,s['when'])
        self.assertEqual(out['stage'],'count');self.assertEqual(answer,'count')
    def test_vehicle_change_recalculates_fare_preserves_locations(self):
        bridge=FakeBridge();weather=wx.WeatherClient(weather_get());s=good_state();s['_wx_forecast_scope']=wx.digest({k:s.get(k) for k in ('pickup','destination','pickup_at','pickup_geo','destination_geo')})
        out,_=wx.prepare_turn(bridge,weather,s,'Mini')
        self.assertEqual(out['vehicle'],'Mini');self.assertEqual(out['fare']['fare'],336)
        self.assertEqual(out['pickup'],'Chennai Central');self.assertEqual(out['destination'],'Airport')
    def test_rain_bike_keeps_selection_and_uses_one_weather_question(self):
        s=good_state();s['stage']='time'
        s,answer=wx.prepare_turn(FakeBridge(),wx.WeatherClient(weather_get()),s,'tomorrow 9 AM')
        self.assertEqual(s['stage'],'weather_advisory');self.assertEqual(s['vehicle'],'Bike')
        self.assertIn('choice is yours',answer);self.assertEqual(answer.count('?'),1)
    def test_exact_tamil_conversation_preserves_every_slot(self):
        s={'lang':'Tamil','stage':'intent'};b=FakeBridge();weather=wx.WeatherClient(weather_get())
        now=datetime(2026,10,17,18,0,tzinfo=wx.TZ)
        s,_=wx.prepare_turn(b,weather,s,'நான் Chennai Central-இல் இருந்து Tambaram செல்ல வேண்டும் நாங்கள் நான்கு பேர் இருக்கிறோம்',now)
        self.assertEqual((s['count'],s['pickup'],s['destination']),(4,'Chennai Central','Tambaram'))
        self.assertEqual(s['stage'],'vehicle')
        s,answer=wx.prepare_turn(b,weather,s,'எனக்கு SUV வேண்டும் இன்று இரவு 07:00 மணிக்கு எனக்கு cab வேணும்',now)
        self.assertEqual(s['stage'],'weather_advisory');self.assertEqual(s['vehicle'],'SUV')
        self.assertEqual(s['pickup_at'],'2026-10-17T19:00:00+05:30')
        self.assertEqual(s['count'],4);self.assertIn('தொடர விரும்புகிறீர்களா',answer)
        self.assertNotRegex(answer,r'\d{4}-\d{2}-\d{2}|India time|இந்திய நேரம்')
    def test_past_today_time_is_explained_and_later_time_retains_today(self):
        b=FakeBridge();weather=wx.WeatherClient(weather_get());s=good_state();s.update(lang='Tamil',vehicle='SUV',count=4,when=None)
        now=datetime(2026,10,17,20,30,tzinfo=wx.TZ)
        s,answer=wx.prepare_turn(b,weather,s,'இன்று இரவு 07:00 மணிக்கு',now)
        self.assertEqual(s['stage'],'time');self.assertIn('கடந்துவிட்டது',answer)
        self.assertNotIn('பெட்டி',answer)
        s,answer=wx.prepare_turn(b,weather,s,'இரவு 10 மணிக்கு',now)
        self.assertEqual(s['stage'],'weather_advisory');self.assertEqual(s['pickup_at'],'2026-10-17T22:00:00+05:30')
        self.assertEqual((s['count'],s['vehicle'],s['pickup']),(4,'SUV','Chennai Central'))
    def test_today_alone_then_clock_only_does_not_reask_date(self):
        b=FakeBridge();weather=wx.WeatherClient(weather_get());s=good_state();s.update(lang='Tamil',vehicle='SUV',when=None,pickup_at=None)
        now=datetime(2026,10,17,18,0,tzinfo=wx.TZ)
        s,answer=wx.prepare_turn(b,weather,s,'இன்று',now)
        self.assertEqual(s['stage'],'time');self.assertIn('எத்தனை மணிக்கு',answer)
        s,answer=wx.prepare_turn(b,weather,s,'இரவு ஏழு மணிக்கு',now)
        self.assertEqual(s['stage'],'weather_advisory');self.assertEqual(s['pickup_at'],'2026-10-17T19:00:00+05:30')
    def test_both_probabilities_spoken_before_question_and_printed_in_display(self):
        s=good_state();s['weather']={'status':'ok','condition':'rain','points':[
            {'location':'pickup','precipitation_probability':98},
            {'location':'destination','precipitation_probability':99}]}
        answer=wx.advisory(s)+'\n'+wx.weather_question(s['lang'])
        self.assertIn('98%',answer);self.assertIn('99%',answer)
        self.assertLess(answer.index('99%'),answer.index('Would you like'))
        display=wx.display_reply(s,answer)
        # Current requirement: print the same complete advisory that is spoken.
        self.assertEqual(display,answer)
        self.assertIn('98%',display);self.assertIn('99%',display)
        self.assertIn('Would you like to continue',display)
    def test_missing_probability_is_not_spoken_as_zero(self):
        s=good_state();s['weather']={'status':'ok','condition':'cloudy','points':[
            {'location':'pickup','precipitation_probability':0},
            {'location':'destination','precipitation_probability':None}]}
        answer=wx.probability_report(s)
        self.assertEqual(answer.count('0%'),1);self.assertIn('drop location, Airport, is not available',answer)
    def test_time_is_not_mistaken_for_passengers_or_plain_cab_for_mini(self):
        s=good_state();s.update(count=4,vehicle='SUV',lang='Tamil')
        s,_=wx.prepare_turn(FakeBridge(),wx.WeatherClient(weather_get()),s,'நாளை இரவு 07:00 மணிக்கு எனக்கு cab வேணும்')
        self.assertEqual((s['count'],s['vehicle']),(4,'SUV'))
    def test_capacity_checked_before_final_confirmation(self):
        s=good_state();s['count']=4
        s,answer=wx.prepare_turn(FakeBridge(),wx.WeatherClient(weather_get()),s,'Bike')
        self.assertEqual(s['stage'],'vehicle');self.assertIn('SUV',answer)


class FakeSocket:
    headers={'origin':'https://test.invalid'}
    query_params={'language':'English','mode':'book'}
    def __init__(self):self.inbox=asyncio.Queue();self.outbox=asyncio.Queue();self.accepted=False
    async def accept(self):self.accepted=True
    async def close(self,code):pass
    async def receive_json(self):
        msg=await self.inbox.get()
        if msg is None:raise RuntimeError('test disconnect')
        return msg
    async def send_json(self,value):await self.outbox.put(value)
    async def until(self,event,timeout=3):
        while True:
            m=await asyncio.wait_for(self.outbox.get(),timeout)
            if m['event']==event:return m


class SocketRaces(unittest.TestCase):
    async def final_review(self,socket,advisory):
        await socket.inbox.put({'event':'playback_ended','epoch':advisory['epoch'],'summary_nonce':advisory['summary_nonce']})
        await socket.inbox.put({'event':'text','text':'yes','summary_nonce':advisory['summary_nonce']})
        final=await socket.until('reply')
        self.assertEqual(final['stage'],'confirm');self.assertEqual(final['summary_kind'],'final')
        return final
    def test_first_sentence_is_delivered_before_later_generation_and_interrupt_clears_rest(self):
        async def scenario():
            fixture=Fixtures();fixture.setUp();entered,release=threading.Event(),threading.Event()
            try:
                bridge=FakeBridge();original=bridge.speak
                def speak(text):
                    if text.startswith('At your drop'):
                        entered.set();release.wait(3)
                    return original(text)
                bridge.speak=speak
                wx.install_bridge(bridge,fixture.db.path,wx.WeatherClient(weather_get(0,0)),_route_wrapper=lambda f:f)
                socket=FakeSocket();task=asyncio.create_task(bridge._wx_endpoint(socket))
                await socket.inbox.put({'event':'start',**fixture.binding});await socket.until('reply')
                await socket.inbox.put({'event':'text','text':fixture.state['when']});first=await socket.until('reply')
                self.assertTrue(first['streaming']);self.assertEqual(first['chunk_index'],0);self.assertGreater(first['chunk_count'],2)
                self.assertEqual(first['pause_after_ms'],220);self.assertFalse(fixture.db.row(fixture.sid)['played'])
                for _ in range(100):
                    if entered.is_set():break
                    await asyncio.sleep(.005)
                self.assertTrue(entered.is_set())
                await socket.inbox.put({'event':'interrupt'});interrupt=await socket.until('interrupted');release.set();await asyncio.sleep(.04)
                rest=[]
                while not socket.outbox.empty():rest.append(socket.outbox.get_nowait())
                self.assertFalse(any(m['event']=='speech_chunk' and m['epoch']<interrupt['epoch'] for m in rest))
                await socket.inbox.put(None);await task
            finally:release.set();fixture.tearDown()
        asyncio.run(scenario())
    def test_late_forecast_cannot_restore_old_date(self):
        async def scenario():
            fixture=Fixtures();fixture.setUp()
            entered,release=threading.Event(),threading.Event()
            original=weather_get(3,10);calls=[0]
            def delayed(*a,**k):
                calls[0]+=1
                if calls[0]==1:entered.set();release.wait(3)
                return original(*a,**k)
            try:
                bridge=FakeBridge();wx.install_bridge(bridge,fixture.db.path,wx.WeatherClient(delayed),_route_wrapper=lambda f:f)
                socket=FakeSocket();task=asyncio.create_task(bridge._wx_endpoint(socket))
                await socket.inbox.put({'event':'start',**fixture.binding});await socket.until('reply')
                await socket.inbox.put({'event':'text','text':fixture.state['when']});await socket.until('heard')
                for _ in range(100):
                    if entered.is_set():break
                    await asyncio.sleep(.01)
                self.assertTrue(entered.is_set())
                await socket.inbox.put({'event':'interrupt'});await socket.until('interrupted')
                new=(datetime.now(wx.TZ)+timedelta(days=2)).strftime('%Y-%m-%d %H:%M')
                await socket.inbox.put({'event':'text','text':new});await socket.until('heard');release.set()
                reply=await socket.until('reply');self.assertEqual(reply['stage'],'weather_advisory')
                self.assertEqual(json.loads(fixture.db.row(fixture.sid)['state'])['when'],wx.resolve_pickup(new).isoformat())
                await socket.inbox.put(None);await task
            finally:release.set();fixture.tearDown()
        asyncio.run(scenario())
    def test_interrupted_tts_is_not_delivered(self):
        async def scenario():
            fixture=Fixtures();fixture.setUp()
            try:
                bridge=FakeBridge();bridge.block.clear()
                wx.install_bridge(bridge,fixture.db.path,wx.WeatherClient(weather_get(3,10)),_route_wrapper=lambda f:f)
                socket=FakeSocket();task=asyncio.create_task(bridge._wx_endpoint(socket))
                await socket.inbox.put({'event':'start',**fixture.binding})
                await socket.until('reply')
                await socket.inbox.put({'event':'text','text':fixture.state['when']})
                await socket.until('heard')
                for _ in range(100):
                    if bridge.started.is_set():break
                    await asyncio.sleep(.01)
                self.assertTrue(bridge.started.is_set())
                await socket.inbox.put({'event':'interrupt'});await socket.until('interrupted')
                bridge.block.set();await asyncio.sleep(.06)
                messages=[]
                while not socket.outbox.empty():messages.append(socket.outbox.get_nowait())
                self.assertFalse(any(m['event']=='reply' and m.get('summary_nonce') for m in messages))
                await socket.inbox.put(None);await task
            finally:fixture.tearDown()
        asyncio.run(scenario())
    def test_confirm_without_ack_cannot_send_booking_action(self):
        async def scenario():
            fixture=Fixtures();fixture.setUp()
            try:
                bridge=FakeBridge();wx.install_bridge(bridge,fixture.db.path,wx.WeatherClient(weather_get(3,10)),_route_wrapper=lambda f:f)
                socket=FakeSocket();task=asyncio.create_task(bridge._wx_endpoint(socket))
                await socket.inbox.put({'event':'start',**fixture.binding});await socket.until('reply')
                await socket.inbox.put({'event':'text','text':fixture.state['when']});summary=await socket.until('reply')
                self.assertTrue(summary['summary_nonce'])
                await socket.inbox.put({'event':'text','text':'yes','summary_nonce':summary['summary_nonce']})
                refreshed=await socket.until('reply')
                self.assertNotEqual(refreshed['summary_nonce'],summary['summary_nonce'])
                final=await self.final_review(socket,refreshed)
                with fixture.db.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM rides').fetchone()[0],0)
                await socket.inbox.put({'event':'playback_ended','epoch':final['epoch'],'summary_nonce':final['summary_nonce']})
                await socket.inbox.put({'event':'text','text':'ஆம்.','summary_nonce':final['summary_nonce']})
                action=await socket.until('action');self.assertEqual(action['type'],'weather_book')
                await socket.inbox.put(None);await task
            finally:fixture.tearDown()
        asyncio.run(scenario())
    def test_failed_http_commit_returns_a_fresh_confirmation(self):
        async def scenario():
            fixture=Fixtures();fixture.setUp()
            try:
                bridge=FakeBridge();wx.install_bridge(bridge,fixture.db.path,wx.WeatherClient(weather_get(3,10)),_route_wrapper=lambda f:f)
                socket=FakeSocket();task=asyncio.create_task(bridge._wx_endpoint(socket))
                await socket.inbox.put({'event':'start',**fixture.binding});await socket.until('reply')
                await socket.inbox.put({'event':'text','text':fixture.state['when']});summary=await socket.until('reply')
                summary=await self.final_review(socket,summary)
                await socket.inbox.put({'event':'playback_ended','epoch':summary['epoch'],'summary_nonce':summary['summary_nonce']})
                await socket.inbox.put({'event':'text','text':'yes','summary_nonce':summary['summary_nonce']})
                action=await socket.until('action')
                await socket.inbox.put({'event':'result','request_id':action['request_id'],'ok':False,'error':'HTTP timeout'})
                error=await socket.until('booking_error');self.assertEqual(error['message'],'HTTP timeout')
                refreshed=await socket.until('reply');self.assertTrue(refreshed['summary_nonce']);self.assertFalse(refreshed['done'])
                self.assertIn('not saved',refreshed['text']);self.assertNotIn('weather',refreshed)
                await socket.inbox.put(None);await task
            finally:fixture.tearDown()
        asyncio.run(scenario())
    def test_saved_ride_is_confirmed_even_if_http_response_timed_out(self):
        async def scenario():
            fixture=Fixtures();fixture.setUp()
            try:
                bridge=FakeBridge();wx.install_bridge(bridge,fixture.db.path,wx.WeatherClient(weather_get(3,10)),_route_wrapper=lambda f:f)
                socket=FakeSocket();task=asyncio.create_task(bridge._wx_endpoint(socket))
                await socket.inbox.put({'event':'start',**fixture.binding});await socket.until('reply')
                await socket.inbox.put({'event':'text','text':fixture.state['when']});summary=await socket.until('reply')
                summary=await self.final_review(socket,summary)
                await socket.inbox.put({'event':'playback_ended','epoch':summary['epoch'],'summary_nonce':summary['summary_nonce']})
                await socket.inbox.put({'event':'text','text':'yes','summary_nonce':summary['summary_nonce']})
                action=await socket.until('action');result=fixture.commit(action['token'])
                await socket.inbox.put({'event':'result','request_id':action['request_id'],'ok':False,'error':'HTTP timeout'})
                reply=await socket.until('reply');self.assertTrue(reply['done']);self.assertIn(wx.closing_message('English'),reply['text'])
                last=reply
                while last['chunk_index']<last['chunk_count']-1:last=await socket.until('speech_chunk')
                self.assertEqual(last['pause_after_ms'],0);self.assertIn('Have a wonderful journey!',bridge.spoken)
                self.assertEqual(fixture.db.row(fixture.sid)['ride_id'],result['id'])
                await socket.inbox.put(None);await task
            finally:fixture.tearDown()
        asyncio.run(scenario())


class CallPage(unittest.TestCase):
    def test_no_manual_date_control_or_forecast_card(self):
        html=pathlib.Path(__file__).with_name('weather_call_page.html').read_text()
        for old in ('datetime-local','pickupDate','sendDate','id="weather"','showWeather','India time','இந்திய நேரம்'):
            self.assertNotIn(old,html)
    def test_authenticated_commit_in_popup_has_timeout_and_result_id(self):
        html=pathlib.Path(__file__).with_name('weather_call_page.html').read_text()
        for required in ("fetch('/api/weather-booking/commit'","credentials:'same-origin'","AbortController","request_id:request"):
            self.assertIn(required,html)


class AcceptanceBridge(FakeBridge):
    def __init__(self):super().__init__();self.route_calls=0
    def canonical_place(self,text):
        return 'Chennai Central' if 'சென்ட்ர' in text else text
    def road_fare(self,state):
        self.route_calls+=1
        return super().road_fare(state)


class VoiceAcceptance(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,18,7,15,tzinfo=wx.TZ)
        self.bridge=AcceptanceBridge();self.weather=wx.WeatherClient(weather_get(61,70))
    def turn(self,text,state=None,lang='Tamil'):
        return wx.prepare_turn(self.bridge,self.weather,state if state is not None else {'lang':lang,'stage':'intent'},text,self.now)
    def consented(self,state):
        state['_wx_weather_consent']={'scope':wx.weather_consent_scope(state),'accepted_at':time.time()}
        return state
    def test_all_six_slots_in_one_tamil_utterance(self):
        s,answer=self.turn('நான் Chennai Central-இல் இருந்து Tambaram செல்ல வேண்டும். நான்கு பேர். SUV வேண்டும். இன்று மதியம் பன்னிரண்டு மணிக்கு.')
        self.assertEqual((s['pickup'],s['destination'],s['count'],s['vehicle']),('Chennai Central','Tambaram',4,'SUV'))
        self.assertEqual(s['pickup_at'],'2026-10-18T12:00:00+05:30');self.assertEqual(s['stage'],'weather_advisory')
        self.assertEqual(self.bridge.route_calls,0);self.assertNotIn('எத்தனை மணிக்கு',answer)
    def test_native_tamil_central_and_count_do_not_confuse_clock(self):
        s,_=self.turn('நான் சென்னை சென்ட்ரலில் இருந்து தாம்பரம் செல்ல வேண்டும் நாங்கள் நான்கு பேர் இருக்கிறோம் எனக்கு SUV வேண்டும் இன்று மதியம் பன்னிரண்டு மணிக்கு வேண்டும்')
        self.assertEqual(s['count'],4);self.assertEqual(s['pickup'],'Chennai Central');self.assertEqual(s['vehicle'],'SUV')
        self.assertEqual(s['stage'],'weather_advisory');self.assertEqual(s['pickup_at'],'2026-10-18T12:00:00+05:30')
    def test_all_six_slots_in_one_english_utterance(self):
        s,_=self.turn('I need a Mini from Chennai Central to Tambaram. Four passengers, tomorrow at 6 PM.',lang='English')
        self.assertEqual((s['pickup'],s['destination'],s['count'],s['vehicle']),('Chennai Central','Tambaram',4,'Mini'))
        self.assertEqual(s['pickup_at'],'2026-10-19T18:00:00+05:30');self.assertEqual(s['stage'],'weather_advisory')
    def test_mixed_tamil_english_slots_in_same_sentence(self):
        s,_=self.turn('நான் Chennai Central-இல் இருந்து Tambaram செல்ல வேண்டும். One person, bike, today at 12 PM.')
        self.assertEqual((s['count'],s['vehicle'],s['pickup'],s['destination']),(1,'Bike','Chennai Central','Tambaram'))
        self.assertEqual(s['pickup_at'],'2026-10-18T12:00:00+05:30')
    def test_all_six_slots_in_tanglish(self):
        s,_=self.turn('Naan Chennai Central la irundhu Tambaram poganum. Naalu peru, SUV venum, innaiku madhiyam pannirandu mani.',lang='Tanglish')
        self.assertEqual((s['count'],s['vehicle'],s['pickup'],s['destination']),(4,'SUV','Chennai Central','Tambaram'))
        self.assertEqual(s['pickup_at'],'2026-10-18T12:00:00+05:30')
    def test_named_dates_and_spoken_tamil_day(self):
        for text,expected in (('20th October 6 PM','2026-10-20T18:00:00+05:30'),
                              ('அக்டோபர் இருபதாம் தேதி மாலை ஆறு மணிக்கு','2026-10-20T18:00:00+05:30'),
                              ('October 20, 2026 at 6 PM','2026-10-20T18:00:00+05:30')):
            with self.subTest(text=text):self.assertEqual(wx.resolve_pickup(text,self.now).isoformat(),expected)
    def test_noon_midnight_night_and_evening(self):
        for text,hour in (('tomorrow afternoon 12 PM',12),('tomorrow midnight 12 AM',0),('tomorrow night 1',1),
                           ('நாளைக்கு இரவு ஒரு மணிக்கு',1),('நாளை நள்ளிரவு பன்னிரண்டு மணிக்கு',0),
                           ('நாளை மாலை ஆறு மணிக்கு',18)):
            with self.subTest(text=text):self.assertEqual(wx.resolve_pickup(text,self.now).hour,hour)
    def test_compact_numeric_clock_and_conflicting_period(self):
        for text,hour in (('tomorrow 12PM',12),('tomorrow 07PM',19),('நாளை மதியம்12மணிக்கு',12)):
            with self.subTest(text=text):self.assertEqual(wx.resolve_pickup(text,self.now).hour,hour)
        for text in ('tomorrow morning 6 PM','tomorrow midnight 12 PM'):
            with self.assertRaisesRegex(wx.GuardError,'clarify_period'):wx.resolve_pickup(text,self.now)
    def test_past_today_is_corrected_without_losing_other_slots(self):
        s,answer=self.turn('from Chennai Central to Tambaram, one person, Bike, today 6 AM')
        self.assertEqual(s['stage'],'time');self.assertIn('கடந்துவிட்டது',answer)
        s,_=self.turn('இன்று மதியம் 12 மணி',s)
        self.assertEqual(s['pickup_at'],'2026-10-18T12:00:00+05:30');self.assertEqual(s['vehicle'],'Bike')
    def test_bike_to_mini_recalculates_and_preserves_other_slots(self):
        s,_=self.turn('from Chennai Central to Tambaram. One person, Bike, tomorrow 12 PM',lang='English')
        self.consented(s);s,_=self.turn('',s)
        self.assertEqual(s['stage'],'confirm');old={k:s[k] for k in ('count','pickup','destination','pickup_at')}
        s,answer=self.turn('No, change my bike to mini car.',s)
        self.assertEqual(s['vehicle'],'Mini');self.assertEqual(s['fare']['fare'],336)
        self.assertEqual({k:s[k] for k in old},old);self.assertEqual(s['stage'],'confirm')
        self.assertIn('Mini',answer);self.assertNotIn('Bike',answer);self.assertEqual(self.bridge.route_calls,2)
    def test_changed_time_requires_new_weather_consent(self):
        s,_=self.turn('from Chennai Central to Tambaram. One person, Bike, tomorrow 12 PM',lang='English')
        self.consented(s);s,_=self.turn('',s);s,_=self.turn('tomorrow at 6 PM',s)
        self.assertEqual(s['stage'],'weather_advisory');self.assertFalse(wx.weather_consented(s))
        self.assertEqual(s['pickup'],'Chennai Central');self.assertEqual(s['count'],1)
    def test_route_failure_cannot_erase_slots_and_retry_works(self):
        s,_=self.turn('from Chennai Central to Tambaram. One person, Bike, tomorrow 12 PM',lang='English')
        self.consented(s);old={k:s[k] for k in ('count','vehicle','pickup','destination','pickup_at')}
        original=self.bridge.road_fare
        def bad_route(working):working.update(pickup=None,destination=None,when=None);return None
        self.bridge.road_fare=bad_route;s,answer=self.turn('',s)
        self.assertEqual(s['stage'],'route_unavailable');self.assertIsNone(s['fare'])
        self.assertEqual({k:s[k] for k in old},old);self.assertNotIn('₹',answer)
        self.bridge.road_fare=original;s,_=self.turn('retry',s)
        self.assertEqual(s['stage'],'confirm');self.assertEqual({k:s[k] for k in old},old)
    def test_invalid_route_numbers_are_not_quoted_as_real_fares(self):
        for fare in ({'fare':float('nan'),'km':35.4},{'fare':'unknown','km':35.4},{'fare':100}):
            s,_=self.turn('from Chennai Central to Tambaram. One person, Bike, tomorrow 12 PM',lang='English')
            self.consented(s);self.bridge.road_fare=lambda working,fare=fare:fare;s,answer=self.turn('',s)
            self.assertEqual(s['stage'],'route_unavailable');self.assertNotIn('₹',answer)
    def test_unavailable_weather_still_allows_review_after_first_consent(self):
        self.weather=wx.WeatherClient(lambda *a,**kw:(_ for _ in ()).throw(TimeoutError()))
        s,answer=self.turn('from Chennai Central to Tambaram. One person, Bike, tomorrow 12 PM',lang='English')
        self.assertEqual(s['weather']['status'],'unavailable');self.assertNotIn('%',answer)
        self.consented(s);s,_=self.turn('',s);self.assertEqual(s['stage'],'confirm')
    def test_outside_forecast_horizon_does_not_move_the_date(self):
        s,answer=self.turn('from Chennai Central to Tambaram. One person, Bike, 30th November 12 PM',lang='English')
        self.assertEqual(s['weather']['status'],'outside_forecast_range');self.assertNotIn('%',answer)
        self.consented(s);s,_=self.turn('',s);self.assertTrue(s['pickup_at'].startswith('2026-11-30'));self.assertEqual(s['stage'],'confirm')
    def test_tts_templates_keep_numeric_entities_as_digits(self):
        for lang in ('Tamil','Tanglish'):
            s=good_state();s.update(lang=lang,count=4,vehicle='SUV',fare={'km':35.4,'fare':1126})
            s['weather']={'status':'ok','condition':'rain','points':[{'location':'pickup','precipitation_probability':70},{'location':'destination','precipitation_probability':60}]}
            text=wx.summary_text(None,s)
            for value in ('4','35.4','₹1,126'):self.assertIn(value,text)
            self.assertIn('70%',wx.probability_report(s));self.assertIn('60%',wx.probability_report(s))
            self.assertIn('48291',wx.completion_message(lang,48291));self.assertNotIn('நான்கு பேர்',text)
    def test_adapter_receives_digits_and_selected_language(self):
        captured=[];bridge=AcceptanceBridge()
        bridge.TTS=types.SimpleNamespace(synthesize=lambda text,group:(captured.append((text,group)) or b'audio'))
        for lang,group in (('Tamil','TAMIL'),('Tanglish','TANGLISH'),('English','ENGLISH')):
            token=bridge.CURRENT_LANGUAGE.set(lang)
            try:wx.tts_reply(bridge,'35.4, ₹1,126, 70%, 48291')
            finally:bridge.CURRENT_LANGUAGE.reset(token)
            self.assertEqual(captured[-1],('35.4, ₹1,126, 70%, 48291',group))
    def test_numeric_normalizer_handles_decimal_percent_currency_and_id(self):
        text='35.4 கிலோமீட்டர், ₹1,126, 70%, முன்பதிவு எண் 48291.'
        result=wx.speech_numeric_normalize(lambda s:s,text,'Tamil')
        for value in ('முப்பத்து ஐந்து புள்ளி நான்கு','ஆயிரத்து நூற்று இருபத்து ஆறு ரூபாய்','எழுபது சதவீதம்','நான்கு எட்டு இரண்டு ஒன்பது ஒன்று'):
            self.assertIn(value,result)
        self.assertNotIn('%',result);self.assertNotRegex(result,r'\d')
    def test_numeric_scope_leaves_legacy_normalization_unchanged(self):
        original=lambda text:'ORIGINAL '+text
        namespace={'normalize_taxi_text':original};bridge=AcceptanceBridge()
        captured=[]
        bridge.TTS=types.SimpleNamespace(ns=namespace,synthesize=lambda text,group:(captured.append(namespace['normalize_taxi_text'](text)) or b'audio'))
        wx.install_numeric_normalizer(bridge)
        self.assertEqual(namespace['normalize_taxi_text']('35.4, 70%'),original('35.4, 70%'))
        token=bridge.CURRENT_LANGUAGE.set('English')
        try:wx.tts_reply(bridge,'35.4, 70%')
        finally:bridge.CURRENT_LANGUAGE.reset(token)
        self.assertIn('point',captured[-1]);self.assertIn('percent',captured[-1])
        self.assertEqual(namespace['normalize_taxi_text']('35.4, 70%'),original('35.4, 70%'))
    def test_repeated_details_do_not_trigger_missing_slot_questions(self):
        request='from Chennai Central to Tambaram. Four people, SUV, tomorrow 12 PM'
        s,_=self.turn(request,lang='English');s,answer=self.turn(request,s)
        self.assertEqual(s['stage'],'weather_advisory');self.assertEqual(s['count'],4)
        self.assertNotIn('What pickup',answer);self.assertNotIn('How many',answer)
    def test_ambiguous_vehicle_is_clarified_then_resolved(self):
        s,_=self.turn('from Chennai Central to Tambaram. One person, Bike or Mini, tomorrow 12 PM',lang='English')
        self.assertEqual(s['stage'],'vehicle');s,_=self.turn('Mini',s);self.assertEqual(s['stage'],'weather_advisory')
    def test_qwen_cannot_invent_places_or_overwrite_valid_slots(self):
        self.bridge._wx_context_extract=lambda raw,s:{'pickup':'Mars','destination':'Moon','passengers_text':'six'}
        s,_=self.turn('One person wants a bike tomorrow 12 PM',lang='English')
        self.assertFalse(s.get('pickup'));self.assertFalse(s.get('destination'));self.assertEqual(s['count'],1)
        self.assertEqual(s['_wx_slot_evidence']['count']['source'],'rule')


class TwoConsentGuard(Fixtures):
    def test_weather_nonce_cannot_be_redeemed_as_booking_permit(self):
        self.state.pop('_wx_weather_consent',None);self.state['stage']='weather_advisory'
        self.db.stash(self.sid,self.epoch,self.state);nonce=self.db.summary(self.sid,self.epoch,self.state)
        self.db.played(self.sid,self.epoch,nonce)
        with self.assertRaises(wx.GuardError):self.db.permit(self.sid,self.epoch,nonce,self.state)
    def test_first_yes_records_consent_but_creates_no_permit_or_ride(self):
        self.state.pop('_wx_weather_consent',None);self.state['stage']='weather_advisory'
        self.db.stash(self.sid,self.epoch,self.state);nonce=self.db.summary(self.sid,self.epoch,self.state)
        self.db.played(self.sid,self.epoch,nonce);state=self.db.accept_weather(self.sid,self.epoch,nonce,self.state)
        self.assertTrue(wx.weather_consented(state))
        with self.db.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM rides').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM wx_permits').fetchone()[0],0)
    def test_first_consent_requires_weather_audio_ack(self):
        self.state.pop('_wx_weather_consent',None);self.state['stage']='weather_advisory'
        self.db.stash(self.sid,self.epoch,self.state);nonce=self.db.summary(self.sid,self.epoch,self.state)
        self.assertFalse(self.db.played(self.sid,self.epoch,nonce,explicit_read=True))
        with self.assertRaises(wx.GuardError):self.db.accept_weather(self.sid,self.epoch,nonce,self.state)
    def test_final_review_requires_a_separate_fresh_ack(self):
        self.state.pop('_wx_weather_consent',None);self.state['stage']='weather_advisory'
        self.db.stash(self.sid,self.epoch,self.state);first=self.db.summary(self.sid,self.epoch,self.state)
        self.db.played(self.sid,self.epoch,first);self.db.accept_weather(self.sid,self.epoch,first,self.state)
        self.state['stage']='confirm';self.db.stash(self.sid,self.epoch,self.state);final=self.db.summary(self.sid,self.epoch,self.state)
        with self.assertRaises(wx.GuardError):self.db.permit(self.sid,self.epoch,first,self.state)
        with self.assertRaises(wx.GuardError):self.db.permit(self.sid,self.epoch,final,self.state)
        self.db.played(self.sid,self.epoch,final);self.assertTrue(self.commit(self.db.permit(self.sid,self.epoch,final,self.state))['ok'])
    def test_missing_first_consent_blocks_even_an_acknowledged_final_summary(self):
        self.state.pop('_wx_weather_consent',None);self.db.stash(self.sid,self.epoch,self.state)
        final=self.db.summary(self.sid,self.epoch,self.state);self.db.played(self.sid,self.epoch,final)
        with self.assertRaisesRegex(wx.GuardError,'Weather consent'):self.db.permit(self.sid,self.epoch,final,self.state)
    def test_old_database_schema_is_migrated_without_losing_call_state(self):
        with self.db.connect() as c:
            c.execute('CREATE TABLE old_calls AS SELECT * FROM wx_calls');c.execute('DROP TABLE wx_calls')
            c.execute("CREATE TABLE wx_calls(id TEXT PRIMARY KEY,owner INTEGER,secret_hash TEXT,expires REAL,epoch INTEGER,version INTEGER,state TEXT,summary_nonce TEXT,summary_hash TEXT,summary_expires REAL,played INTEGER,ride_id INTEGER)")
            c.execute('INSERT INTO wx_calls SELECT id,owner,secret_hash,expires,epoch,version,state,summary_nonce,summary_hash,summary_expires,played,ride_id FROM old_calls')
        self.db.setup();self.assertEqual(json.loads(self.db.row(self.sid)['state'])['pickup'],'Chennai Central')
        self.assertEqual(self.db.row(self.sid)['summary_kind'],'final')
    def test_changed_weather_location_cannot_reuse_first_consent(self):
        self.state['destination']='Other destination';self.db.stash(self.sid,self.epoch,self.state)
        final=self.db.summary(self.sid,self.epoch,self.state);self.db.played(self.sid,self.epoch,final)
        with self.assertRaisesRegex(wx.GuardError,'Weather consent'):self.db.permit(self.sid,self.epoch,final,self.state)


class BackendHTTP(unittest.TestCase):
    server_source=None
    @classmethod
    def setUpClass(cls):
        if not cls.server_source:raise unittest.SkipTest('Backend source was not supplied')
        cls.tmp=tempfile.TemporaryDirectory()
        source=pathlib.Path(cls.server_source).read_text(encoding='utf-8').split('# WEATHER_BOOKING_BOOTSTRAP_V1',1)[0]
        cls.name='wx_isolated_backend_fixture'
        cls.backend=types.ModuleType(cls.name);cls.backend.__file__=str(pathlib.Path(cls.tmp.name)/'server.py')
        sys.modules[cls.name]=cls.backend
        exec(compile(source,cls.backend.__file__,'exec'),cls.backend.__dict__)
        cls.backend.DB=pathlib.Path(cls.tmp.name)/'fixture.db';cls.backend.PUBLIC='https://test.invalid';cls.backend.setup()
        with cls.backend.conn() as c:
            for uid,role in ((7,'customer'),(8,'customer'),(9,'driver')):
                c.execute('INSERT INTO users(id,name,phone,password_salt,password_hash,role) VALUES(?,?,?,?,?,?)',
                          (uid,'Fixture '+str(uid),'+9100000000'+str(uid),'0'*32,'unused',role))
                c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(('fixture-'+str(uid)).encode()).hexdigest(),uid,time.time()+600))
        wx.install_backend(cls.backend,weather=wx.WeatherClient(weather_get(65,95)))
        cls.backend.Handler.log_message=lambda *a:None
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),cls.backend.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'server'):
            cls.server.shutdown();cls.server.server_close();cls.thread.join(2)
        if hasattr(cls,'backend') and hasattr(cls.backend,'_wx_stop_event'):cls.backend._wx_stop_event.set()
        if hasattr(cls,'tmp'):cls.tmp.cleanup()
    def request(self,path,data=None,uid=7,origin='https://test.invalid'):
        headers={'Content-Type':'application/json','Origin':origin}
        if uid is not None:headers['Cookie']='movio_session=fixture-'+str(uid)
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_address[1],timeout=5)
        conn.request('POST',path,body=json.dumps(data or {}),headers=headers)
        response=conn.getresponse();status=response.status;result=json.loads(response.read());conn.close();return status,result
    def test_account_and_origin_checks(self):
        self.assertEqual(self.request('/api/weather-booking/session',uid=None)[0],401)
        self.assertEqual(self.request('/api/weather-booking/session',uid=9)[0],403)
        self.assertEqual(self.request('/api/weather-booking/session',origin='https://other.invalid')[0],403)
    def test_authenticated_commit_retry_and_cancel(self):
        status,binding=self.request('/api/weather-booking/session');self.assertEqual(status,200)
        db=wx.GuardDB(self.backend.DB);sid=binding['call_id'];e=db.begin(sid);s=good_state();db.stash(sid,e,s)
        nonce=db.summary(sid,e,s);db.played(sid,e,nonce);token=db.permit(sid,e,nonce,s)
        self.assertEqual(self.request('/api/weather-booking/commit',{'token':token},uid=8)[0],403)
        status,result=self.request('/api/weather-booking/commit',{'token':token});self.assertEqual(status,201)
        status,retry=self.request('/api/weather-booking/commit',{'token':token});self.assertEqual(status,201);self.assertEqual(result['id'],retry['id'])
        self.assertEqual(self.request('/api/weather-booking/cancel',{'ride_id':result['id']},uid=8)[0],409)
        self.assertEqual(self.request('/api/weather-booking/cancel',{'ride_id':result['id']})[0],200)
    def test_running_older_handler_can_be_upgraded_without_nesting(self):
        original=self.backend.Handler._wx_original_post
        self.backend.Handler._wx_version='0.1.0'
        wx.install_backend(self.backend)
        self.assertEqual(self.backend.Handler._wx_version,wx.VERSION)
        self.assertIs(self.backend.Handler._wx_original_post,original)
        self.assertEqual(self.request('/api/weather-booking/session')[0],200)
    def test_manual_preview_does_not_create_a_booking(self):
        status,review=self.request('/api/weather-booking/manual-preview',manual_payload())
        self.assertEqual(status,200);self.assertIn('Heavy rain',review['advisory']);self.assertEqual(review['vehicle'],'Bike')
        with self.backend.conn() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM rides WHERE voice_call_id=?',(review['call_id'],)).fetchone()[0],0)
    def test_manual_preview_requires_customer_and_same_origin(self):
        for uid in (None,9):self.assertIn(self.request('/api/weather-booking/manual-preview',manual_payload(),uid=uid)[0],(401,403))
        self.assertEqual(self.request('/api/weather-booking/manual-preview',manual_payload(),origin='https://other.invalid')[0],403)
    def test_manual_confirmation_keeps_choices_and_closes_politely(self):
        p=manual_payload('Tamil');status,review=self.request('/api/weather-booking/manual-preview',p)
        self.assertEqual(status,200)
        status,result=self.request('/api/weather-booking/manual-confirm',review)
        self.assertEqual(status,201);self.assertTrue(result['message'].endswith(wx.closing_message('Tamil')))
        with self.backend.conn() as c:ride=c.execute('SELECT * FROM rides WHERE id=?',(result['id'],)).fetchone()
        self.assertEqual((ride['vehicle'],ride['fare'],ride['pickup_time'],ride['source']),('Bike',p['fare'],p['pickup_at'],'weather_web'))
        self.assertEqual(ride['passengers'],1);self.assertEqual(ride['status'],'scheduled')
    def test_manual_confirmation_cannot_use_another_account_or_secret(self):
        _,review=self.request('/api/weather-booking/manual-preview',manual_payload())
        self.assertEqual(self.request('/api/weather-booking/manual-confirm',review,uid=8)[0],403)
        self.assertEqual(self.request('/api/weather-booking/manual-confirm',{**review,'bind_token':'wrong'})[0],403)
    def test_simultaneous_manual_confirmations_create_one_ride(self):
        _,review=self.request('/api/weather-booking/manual-preview',manual_payload())
        with ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(lambda _:self.request('/api/weather-booking/manual-confirm',review),range(12)))
        self.assertTrue(all(status==201 for status,result in results));self.assertEqual(len({r['id'] for _,r in results}),1)
        with self.backend.conn() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM rides WHERE voice_call_id=?',(review['call_id'],)).fetchone()[0],1)
    def test_discarded_manual_review_cannot_be_confirmed(self):
        _,review=self.request('/api/weather-booking/manual-preview',manual_payload())
        self.assertEqual(self.request('/api/weather-booking/manual-discard',review)[0],200)
        self.assertEqual(self.request('/api/weather-booking/manual-confirm',review)[0],409)
    def test_past_manual_time_is_rejected_without_moving_date(self):
        p=manual_payload('Tamil');p['pickup_at']='2025-09-15T19:00:00+05:30'
        status,error=self.request('/api/weather-booking/manual-preview',p)
        self.assertEqual(status,409);self.assertEqual(error['code'],'past_datetime');self.assertIn('கடந்துவிட்டது',error['error'])
    def test_unavailable_future_forecast_does_not_force_a_date_change(self):
        p=manual_payload('Tanglish');p['pickup_at']=(datetime.now(wx.TZ)+timedelta(days=30)).replace(second=0,microsecond=0).isoformat()
        status,review=self.request('/api/weather-booking/manual-preview',p)
        self.assertEqual(status,200);self.assertEqual(review['weather_status'],'outside_forecast_range');self.assertEqual(review['pickup_at'],p['pickup_at'])
        status,result=self.request('/api/weather-booking/manual-confirm',review)
        self.assertEqual(status,201);self.assertTrue(result['message'].endswith(wx.closing_message('Tanglish')))
    def test_payload_cannot_replace_reviewed_vehicle_on_confirmation(self):
        _,review=self.request('/api/weather-booking/manual-preview',manual_payload())
        status,result=self.request('/api/weather-booking/manual-confirm',{**review,'vehicle':'SUV','fare':1})
        self.assertEqual(status,201)
        with self.backend.conn() as c:ride=c.execute('SELECT * FROM rides WHERE id=?',(result['id'],)).fetchone()
        self.assertEqual(ride['vehicle'],'Bike');self.assertEqual(ride['fare'],168)
    def test_manual_forecast_request_does_not_hold_the_website_lock(self):
        entered,release=threading.Event(),threading.Event();previous=self.backend._wx_weather_client
        class Delayed:
            def forecast(self,*args,**kwargs):
                entered.set();release.wait(3);return {'status':'unavailable'}
        self.backend._wx_weather_client=Delayed()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                forecast=pool.submit(self.request,'/api/weather-booking/manual-preview',manual_payload())
                self.assertTrue(entered.wait(1))
                other=pool.submit(self.request,'/api/weather-booking/session')
                try:self.assertEqual(other.result(timeout=1)[0],200)
                finally:release.set()
                self.assertEqual(forecast.result()[0],200)
        finally:release.set();self.backend._wx_weather_client=previous
    def test_manual_scheduled_ride_uses_existing_release_and_cancel(self):
        _,review=self.request('/api/weather-booking/manual-preview',manual_payload())
        _,result=self.request('/api/weather-booking/manual-confirm',review)
        with self.backend.conn() as c:c.execute('UPDATE rides SET pickup_time=? WHERE id=?',((datetime.now(wx.TZ)+timedelta(minutes=10)).isoformat(),result['id']))
        wx.GuardDB(self.backend.DB).release_due()
        with self.backend.conn() as c:self.assertEqual(c.execute('SELECT status FROM rides WHERE id=?',(result['id'],)).fetchone()[0],'requested')


def _run_tests(server_source=None):
    BackendHTTP.server_source=server_source
    suite=unittest.defaultTestLoader.loadTestsFromNames([__name__+'.'+name for name in
        ('Dates','Weather','CustomerAdvice','Confirmation','TurnPreparation','SocketRaces','CallPage','BackendHTTP','VoiceAcceptance','TwoConsentGuard')])
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    return {'version':wx.VERSION,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'passed':result.wasSuccessful(),'scope':'offline weather/model stubs + real SQLite + async socket protocol; isolated HTTP when source supplied'}


def run_tests(server_source=None):
    """Keep asyncio.run() scenarios off a notebook's already-running loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run_tests(server_source)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='weather-regression') as pool:
        return pool.submit(_run_tests, server_source).result()


if __name__=='__main__':
    print(json.dumps(run_tests(sys.argv[1] if len(sys.argv)>1 else None),indent=2))
