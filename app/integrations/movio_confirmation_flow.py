"""State-aware confirmation on the existing authenticated booking protocol."""
import asyncio
import copy
import functools
import hashlib
import json
import logging
import math
import re
import sys
import time
import types
import unicodedata
from datetime import datetime
from pathlib import Path

VERSION='confirmation-flow-1.0'
COLLECTING_DETAILS='COLLECTING_DETAILS'
WEATHER_ADVISORY='WEATHER_ADVISORY'
AWAITING_WEATHER_CONSENT='AWAITING_WEATHER_CONSENT'
AWAITING_BOOKING_CONFIRMATION='AWAITING_BOOKING_CONFIRMATION'
BOOKING_IN_PROGRESS='BOOKING_IN_PROGRESS'
BOOKING_CONFIRMED='BOOKING_CONFIRMED'
AFFIRMATIVES={
 'yes','yeah','yep','yes please','yes confirm','yes please confirm','confirm','confirmed','okay','ok',
 'ஆம்','ஆமாம்','ஆமா','ஆமாங்க','சரி','சரிங்க','உறுதி செய்யுங்கள்','முன்பதிவு செய்யுங்கள்',
 'seri','sari','aama','aamaa','aamam','amam','aam','book pannunga','book pannu','booking pannunga',
 'yes book pannunga','aama book pannunga','seri book pannunga','புக் பண்ணுங்க','புக்கிங் பண்ணுங்க',
 'சரி புக் பண்ணுங்க','ஆம் புக் பண்ணுங்க','yes book it','book it','go ahead',
}

def normalize(text):
    text=unicodedata.normalize('NFKC',str(text or '')).casefold()
    text=''.join('' if unicodedata.category(c)=='Cf' else ' ' if unicodedata.category(c).startswith('P') else c for c in text)
    return re.sub(r'\s+',' ',text).strip()

def logger_for(root):
    path=Path(root)/'confirmation_flow.log';logger=logging.getLogger('movio.confirmation.'+str(path.resolve()))
    if not logger.handlers:
        handler=logging.FileHandler(path,encoding='utf-8');handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO);logger.propagate=False
    return logger

def event(logger,kind,**fields):logger.info(json.dumps({'event':kind,**fields},ensure_ascii=False,default=str))

def phase_for(state,played=False):
    stage=state.get('stage')
    if stage=='done' and (state.get('booking_id') or state.get('ride_id')):return BOOKING_CONFIRMED
    if stage=='booking_pending':return BOOKING_IN_PROGRESS
    if stage=='confirm':return AWAITING_BOOKING_CONFIRMATION
    if stage=='weather_advisory':return AWAITING_WEATHER_CONSENT if played else WEATHER_ADVISORY
    return COLLECTING_DETAILS

def validate_review(state,engine,now=None):
    for key in ('count','vehicle','pickup','destination','pickup_at'):
        if state.get(key) is None or state.get(key)=='':return key
    try:
        count=int(state['count']);vehicle=state['vehicle']
        if vehicle not in engine['CAPACITY'] or not 1<=count<=engine['CAPACITY'][vehicle]:return 'vehicle'
        if not all(engine['valid_geo'](state.get(key+'_geo')) for key in ('pickup','destination')):return 'route'
        fare=state.get('fare') or {}
        if not all(math.isfinite(float(fare[k])) and float(fare[k])>=0 for k in ('km','fare')):return 'route'
        pickup=datetime.fromisoformat(state['pickup_at'])
        if pickup.tzinfo is None or pickup.timestamp()<=(now.timestamp() if now else time.time()):return 'time'
    except (TypeError,ValueError,KeyError,OverflowError):return 'route'
    return None

def record_phase(db,sid,phase,epoch=None,booking_id=None):
    if not sid:return
    with db.connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row=connection.execute('SELECT epoch,state,ride_id FROM wx_calls WHERE id=?',(sid,)).fetchone()
        if row is None or epoch is not None and row['epoch']!=epoch:return
        state=json.loads(row['state'] or '{}')
        if row['ride_id']:
            phase=BOOKING_CONFIRMED;booking_id=row['ride_id'];state['stage']='done'
        elif phase==BOOKING_CONFIRMED:return
        state['dialogue_state']=phase
        if phase==BOOKING_IN_PROGRESS:state['stage']='booking_pending'
        if booking_id:state['booking_id']=int(booking_id)
        connection.execute('UPDATE wx_calls SET state=? WHERE id=?',(json.dumps(state,ensure_ascii=False,separators=(',',':')),sid))

def call_weather_card(state):
    """MOVIO call weather card v1: presentation data from this bound call only."""
    if not isinstance(state, dict) or state.get('stage') not in ('weather_advisory', 'confirm', 'route_unavailable', 'booking_pending', 'done'):
        return None
    weather = state.get('weather') or {}
    if not isinstance(weather, dict) or weather.get('status') != 'ok' or not state.get('pickup_at'):
        return None
    def finite(value, lower, upper):
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
            return number if math.isfinite(number) and lower <= number <= upper else None
        except (TypeError, ValueError, OverflowError):
            return None
    rows = weather.get('points')
    if not isinstance(rows, list):
        return None
    points = []
    for role in ('pickup', 'destination'):
        point = next((item for item in rows if isinstance(item, dict) and item.get('location') == role), None)
        if point is None:
            continue
        raw_code = finite(point.get('weather_code'), 0, 99)
        code = int(raw_code) if raw_code is not None and raw_code.is_integer() else None
        temperature = finite(point.get('temperature_2m'), -100, 70)
        chance = finite(point.get('precipitation_probability'), 0, 100)
        if code is None and temperature is None and chance is None:
            continue
        points.append(dict(role=role, place=str(state.get(role) or '')[:120], weather_code=code,
            temperature_c=temperature, rain_probability_pct=chance, valid_at=str(point.get('valid_at') or '')[:40]))
    if not points:
        return None
    return dict(version='call-weather-card-v1', source=str(weather.get('source') or '')[:60],
        pickup_at=str(state['pickup_at'])[:40], time_basis='pickup_time', points=points)

class ConfirmationSocket:
    """Order a queued reply after real playback ACK, without inventing an ACK."""
    def __init__(self,websocket,bridge,engine,logger):
        self.websocket,self.bridge,self.engine,self.logger=websocket,bridge,engine,logger
        self.db=bridge._wx_db;self.sid=None;self.pending=None
        self.affirmatives={normalize(x) for x in engine['POSITIVE']}|{normalize(x) for x in AFFIRMATIVES}
    def __getattr__(self,key):return getattr(self.websocket,key)
    def row(self):
        if not self.sid:return None
        try:return self.db.row(self.sid)
        except self.engine['GuardError']:return None
    async def message(self,reason):
        language=self.query_params.get('language','Tamil')
        text=self.engine['localized'](language,
            'Please hear or read the latest booking summary, then confirm.',
            'சமீபத்திய முன்பதிவு விவரங்களைக் கேட்டோ படித்தோ உறுதி செய்யுங்கள்.',
            'Latest booking details kettu illa padichittu confirm pannunga.')
        if reason.startswith('invalid_'):
            field=reason[len('invalid_'):]
            if field in ('time','pickup_at'):
                text=self.engine['localized'](language,'Please give a valid future pickup time.',
                    'இனிவரும் பயண நேரத்தைச் சொல்லுங்கள்.','Future pickup time sollunga.')
            elif field=='route':
                text=self.engine['localized'](language,'Distance and fare need verification. Say retry or correct the locations.',
                    'தூரமும் கட்டணமும் உறுதி செய்யப்பட வேண்டும். மீண்டும் முயற்சிக்கச் சொல்லுங்கள் அல்லது இடங்களைத் திருத்துங்கள்.',
                    'Distance, fare verify pannanum. Retry sollunga illa places correct pannunga.')
            else:
                labels={'pickup':('pickup','புறப்படும் இடம்','pickup'),'destination':('destination','சேரும் இடம்','drop'),
                    'count':('passenger count','பயணிகள் எண்ணிக்கை','passengers count'),'vehicle':('vehicle with enough seats','போதுமான இருக்கைகள் உள்ள வாகனம்','correct vehicle')}
                en,ta,roman=labels.get(field,('booking detail','முன்பதிவு விவரம்','booking detail'))
                text=self.engine['localized'](language,f'Please provide the correct {en}.',f'சரியான {ta} சொல்லுங்கள்.',f'Correct {roman} sollunga.')
        event(self.logger,'confirmation_not_forwarded',reason=reason)
        await self.websocket.send_json({'event':'error','message':text})
    async def receive_json(self):
        while True:
            if self.pending:
                row=self.row();pending=self.pending
                if (not row or row['ride_id'] or row['summary_nonce']!=pending['summary_nonce']
                        or row['summary_expires']<=time.time()):self.pending=None
                elif row['played']:
                    self.pending=None
                    if phase_for(json.loads(row['state']),True)==AWAITING_BOOKING_CONFIRMATION:
                        invalid=validate_review(json.loads(row['state']),self.engine)
                        if invalid:await self.message('invalid_'+invalid);continue
                    event(self.logger,'queued_confirmation_released',phase=json.loads(row['state']).get('dialogue_state'))
                    return pending
            try:
                message=await asyncio.wait_for(self.websocket.receive_json(),90) if self.pending else await self.websocket.receive_json()
            except asyncio.TimeoutError:
                self.pending=None;await self.message('playback_ack_timeout');continue
            kind=message.get('event')
            if kind=='start':self.sid=message.get('call_id');return message
            if kind=='interrupt':self.pending=None;return message
            row=self.row()
            if kind in ('playback_ended','summary_read'):
                # The original endpoint validates the nonce/epoch and stores ACK.
                return message
            if kind not in ('text','audio') or row is None:return message
            affirmative=kind=='text' and normalize(message.get('text')) in self.affirmatives
            if self.pending and kind=='text' and not affirmative:self.pending=None
            if row['ride_id']:
                if affirmative:continue
                return message
            state=json.loads(row['state'] or '{}');phase=phase_for(state,bool(row['played']))
            if phase==BOOKING_IN_PROGRESS and affirmative:continue
            waiting=phase in (WEATHER_ADVISORY,AWAITING_WEATHER_CONSENT,AWAITING_BOOKING_CONFIRMATION)
            if not waiting or not (affirmative or kind=='audio'):return message
            nonce=message.get('summary_nonce')
            if nonce!=row['summary_nonce'] or not nonce:
                if affirmative:await self.message('missing_or_stale_summary_nonce');continue
                return message
            if affirmative and phase==AWAITING_BOOKING_CONFIRMATION:
                invalid=validate_review(state,self.engine)
                if invalid:
                    event(self.logger,'confirmation_invalid_slots',slot=invalid)
                    await self.message('invalid_'+invalid);continue
            if not row['played']:
                # Preserve the existing weather replay protocol. The browser
                # queues early weather replies; only FINAL confirmation needs
                # server-side ACK ordering to prevent the booking loop.
                if phase!=AWAITING_BOOKING_CONFIRMATION:return message
                if self.pending is None:
                    self.pending=dict(message)
                    event(self.logger,'confirmation_queued_for_playback',phase=phase)
                continue
            return message
    async def send_json(self,message):
        message=dict(message);row=self.row();phase=None
        # MOVIO_CALL_WEATHER_CARD_V1: data from this authenticated session only.
        if message.get('event') == 'reply':
            message['weather_card'] = None
            if row and message.get('epoch') is not None and message.get('epoch') == row.get('epoch'):
                try:
                    message['weather_card'] = call_weather_card(json.loads(row.get('state') or '{}'))
                except (TypeError, ValueError, KeyError, OverflowError):
                    message['weather_card'] = None
        if message.get('event') in ('reply','speech_chunk'):
            if message.get('done') and row and row['ride_id']:phase=BOOKING_CONFIRMED
            elif message.get('stage')=='confirm':phase=AWAITING_BOOKING_CONFIRMATION
            elif message.get('stage')=='weather_advisory':phase=WEATHER_ADVISORY
            else:phase=COLLECTING_DETAILS
        elif message.get('event')=='action' and message.get('type')=='weather_book':phase=BOOKING_IN_PROGRESS
        if phase and row:
            record_phase(self.db,self.sid,phase,message.get('epoch'))
            message['dialogue_state']=phase
            if message.get('event') in ('reply','action'):event(self.logger,'confirmation_state',phase=phase)
        await self.websocket.send_json(message)

def install_socket(bridge,engine,root,_route_wrapper=None):
    previous=getattr(bridge,'_wx_endpoint',None)
    if not callable(previous):raise RuntimeError('The original voice/weather endpoint is not active.')
    if getattr(previous,'_movio_confirmation_flow',None)==VERSION:return False
    logger=logger_for(root)
    async def wrapped(ws):
        if ws.query_params.get('mode','book')=='cancel':return await previous(ws)
        return await previous(ConfirmationSocket(ws,bridge,engine,logger))
    # Keep the original guard's globals, so existing notebook add-ons still find
    # prepare_turn/collect_details and the original STT/TTS implementations.
    wrapped=types.FunctionType(wrapped.__code__,engine,wrapped.__name__,wrapped.__defaults__,wrapped.__closure__)
    wrapped._movio_confirmation_flow=VERSION;wrapped._original_endpoint=previous
    # Bridge/engine/logger are closure variables; the proxy class is a global.
    engine['ConfirmationSocket']=ConfirmationSocket
    if _route_wrapper is None:
        from starlette.routing import websocket_session
        _route_wrapper=websocket_session
    route=next(r for r in bridge.app.routes if getattr(r,'path','')=='/browser-call')
    route.endpoint=wrapped;route.app=_route_wrapper(wrapped);bridge._wx_endpoint=wrapped
    bridge._wx_confirmation_flow=VERSION
    return True

def install_namespace(engine,root=None):
    root=Path(root or Path(engine['__file__']).resolve().parent.parent)
    if engine.get('_MOVIO_CONFIRMATION_FLOW_VERSION')==VERSION:return {'version':VERSION,'already_installed':True}
    logger=logger_for(root)
    original={key:engine[key] for key in ('prepare_turn','install_bridge','install_backend','reply_normalized')}
    engine['POSITIVE'].update(normalize(x) for x in AFFIRMATIVES)
    old_played=engine['GuardDB'].played;old_permit=engine['GuardDB'].permit;old_commit=engine['GuardDB'].commit
    def prepare_turn(bridge,weather,state,text,now=None):
        phase=state.get('dialogue_state')
        frozen=(phase in (AWAITING_BOOKING_CONFIRMATION,BOOKING_IN_PROGRESS)
            and state.get('stage') in ('fare','confirm','booking_pending') and (not str(text).strip() or normalize(text) in engine['POSITIVE']))
        if frozen:
            invalid=validate_review(state,engine,now)
            if not invalid:
                state['stage']='confirm';state['dialogue_state']=AWAITING_BOOKING_CONFIRMATION
                return state,engine['summary_text'](bridge,state)
        state,answer=original['prepare_turn'](bridge,weather,state,text,now=now)
        state['dialogue_state']=phase_for(state)
        return state,answer
    def played(db,sid,epoch,nonce,explicit_read=False):
        result=old_played(db,sid,epoch,nonce,explicit_read=explicit_read)
        if result:
            row=db.row(sid)
            phase=AWAITING_WEATHER_CONSENT if row['summary_kind']=='weather' else AWAITING_BOOKING_CONFIRMATION
            record_phase(db,sid,phase,row['epoch'])
        return result
    def permit(db,sid,epoch,nonce,state):
        # User replies are validated by ConfirmationSocket before reaching this
        # method. Keep the existing permit API and backend commit validation.
        try:return old_permit(db,sid,epoch,nonce,state)
        except engine['GuardError'] as exc:
            event(logger,'confirmation_permit_rejected',reason=str(exc));raise
    def commit(db,connection,owner,token,ensure_code):
        result=old_commit(db,connection,owner,token,ensure_code)
        permit=connection.execute('SELECT call_id FROM wx_permits WHERE token_hash=?',(hashlib.sha256(str(token).encode()).hexdigest(),)).fetchone()
        row=connection.execute('SELECT state,ride_id FROM wx_calls WHERE id=?',(permit['call_id'],)).fetchone()
        if row and row['ride_id']==result['id']:
            state=json.loads(row['state'] or '{}');state.update(stage='done',dialogue_state=BOOKING_CONFIRMED,booking_id=result['id'])
            connection.execute('UPDATE wx_calls SET state=? WHERE id=?',(engine['canonical'](state),permit['call_id']))
            event(logger,'booking_persisted',booking_id=result['id'],reused=bool(result.get('reused')))
        return result
    def install_bridge(bridge,db_path,weather=None,_route_wrapper=None):
        result=original['install_bridge'](bridge,db_path,weather=weather,_route_wrapper=_route_wrapper)
        install_socket(bridge,engine,root,_route_wrapper)
        return {**result,'confirmation_flow':VERSION}
    def install_backend(module,weather=None):
        result=original['install_backend'](module,weather=weather)
        previous=module.Handler.do_GET
        if not getattr(previous,'_movio_confirmation_health',False):
            def get(handler):
                if handler.path.split('?',1)[0]=='/api/weather-booking/confirmation-health':
                    return handler.json(200,{'ok':True,'version':VERSION,'final_confirmation_required':True,'duplicate_guard':'atomic_call_transaction'})
                return previous(handler)
            get._movio_confirmation_health=True;module.Handler.do_GET=get
        return result
    engine['GuardDB'].played=played;engine['GuardDB'].permit=permit;engine['GuardDB'].commit=commit
    engine.update(prepare_turn=prepare_turn,install_bridge=install_bridge,install_backend=install_backend,
        reply_normalized=normalize,
        _MOVIO_CONFIRMATION_FLOW_VERSION=VERSION,_movio_confirmation_original={**original,'played':old_played,'permit':old_permit,'commit':old_commit})
    return {'version':VERSION}

CLIENT_JS=r"""
// MOVIO_CONFIRMATION_CLIENT_V1 — behaviour only; existing layout/theme retained.
(()=>{
 'use strict';
 if(window.__movioConfirmationFlow)return;window.__movioConfirmationFlow=true;
 const affirmative=new Set(__AFFIRMATIVES_JSON__);
 const norm=s=>String(s||'').normalize('NFKC').toLowerCase().replace(/\p{Cf}/gu,'').replace(/\p{P}/gu,' ').replace(/\s+/g,' ').trim();
 const yes=s=>affirmative.has(norm(s));
 const oldSend=send,oldTyped=typed;
 let observed=null,latest=null,acknowledged=null,queued=null,saving=false;
 const submitted=new Set();
 function observe(){
  if(!socket||socket===observed)return;
  observed=socket;latest=null;acknowledged=null;queued=null;saving=false;submitted.clear();
  socket.addEventListener('message',e=>{
   let m;try{m=JSON.parse(e.data);}catch{return;}
   if(m.event==='reply'){
    latest=m.summary_nonce?{nonce:m.summary_nonce,epoch:m.epoch,kind:m.summary_kind||'final'}:null;
    if(queued&&(!latest||queued.nonce!==latest.nonce))queued=null;
    if(m.done){saving=false;queued=null;}
   }
   if(m.event==='action'&&m.type==='weather_book'){saving=true;queued=null;}
   if(m.event==='error'||m.event==='booking_error'){saving=false;if(latest)submitted.delete(latest.nonce);}
   if(m.event==='interrupted'){queued=null;latest=null;acknowledged=null;}
  });
 }
 function flush(){
  const item=queued;
  if(!item||saving||!connected||busy||playing)return;
  if(!latest||item.nonce!==latest.nonce||summaryNonce!==item.nonce){queued=null;return;}
  if(acknowledged!==item.nonce)return;
  queued=null;oldTyped(item.text);
 }
 send=function(message){
  observe();
  if(message.event==='playback_ended'||message.event==='summary_read'){
   if(latest&&message.summary_nonce===latest.nonce)acknowledged=message.summary_nonce;
   oldSend(message);setTimeout(flush,0);return;
  }
  if(message.event==='interrupt'){queued=null;latest=null;acknowledged=null;}
  if(message.event==='text'&&yes(message.text)&&message.summary_nonce){
   if(submitted.has(message.summary_nonce))return;
   submitted.add(message.summary_nonce);
  }
  oldSend(message);
 };
 typed=function(text){
  observe();
  if(yes(text)&&latest&&summaryNonce===latest.nonce){
   if(saving||submitted.has(latest.nonce))return;
   if(playing||busy||acknowledged!==latest.nonce){queued={text:String(text),nonce:latest.nonce};return;}
  }else queued=null;
  oldTyped(text);
 };
})();
"""

def patch_html(html,affirmatives):
    start='<!-- MOVIO_CONFIRMATION_CLIENT_START_V1 -->';end='<!-- MOVIO_CONFIRMATION_CLIENT_END_V1 -->'
    if start in html:
        a=html.index(start);b=html.find(end,a)
        if b<0:raise RuntimeError('Incomplete previous confirmation client patch.')
        tail=html[b+len(end):]
        if tail.startswith('\n'):tail=tail[1:]
        html=html[:a]+tail
    required=('function typed(', 'function send(', 'summaryNonce','commitBooking','</body>')
    if any(token not in html for token in required):raise RuntimeError('The active call-page script is not the expected MOVIO version; no UI replacement was made.')
    js=CLIENT_JS.replace('__AFFIRMATIVES_JSON__',json.dumps(sorted({normalize(x) for x in affirmatives}|{normalize(x) for x in AFFIRMATIVES}),ensure_ascii=False))
    return html.replace('</body>',start+'\n<script>\n'+js+'</script>\n'+end+'\n</body>',1)
