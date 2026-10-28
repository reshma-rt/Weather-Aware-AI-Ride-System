/* MOVIO_FORECAST_LISTEN_V3 - plays the forecast with the existing MOVIO TTS (/weather-speech). Tap only; never autoplays; never touches booking. */
(function(){
 'use strict';
 var ROW_ID='wxForecastListenRow';
 var COPY={
  English:{listen:'\uD83D\uDD0A Listen to Forecast',stop:'\u23F9 Stop forecast',cancel:'Cancel voice',loading:'Preparing forecast voice\u2026',error:'Voice could not play. Tap to retry.',replay:'\uD83D\uDD0A Replay forecast'},
  Tamil:{listen:'\uD83D\uDD0A \u0BB5\u0BBE\u0BA9\u0BBF\u0BB2\u0BC8 \u0BAE\u0BC1\u0BA9\u0BCD\u0BA9\u0BB1\u0BBF\u0BB5\u0BBF\u0BAA\u0BCD\u0BAA\u0BC8\u0B95\u0BCD \u0B95\u0BC7\u0BB3\u0BC1\u0B99\u0BCD\u0B95\u0BB3\u0BCD',stop:'\u23F9 \u0B92\u0BB2\u0BBF\u0BAF\u0BC8 \u0BA8\u0BBF\u0BB1\u0BC1\u0BA4\u0BCD\u0BA4\u0BC1',cancel:'\u0BB0\u0BA4\u0BCD\u0BA4\u0BC1\u0B9A\u0BC6\u0BAF\u0BCD',loading:'\u0BB5\u0BBE\u0BA9\u0BBF\u0BB2\u0BC8 \u0B95\u0BC1\u0BB0\u0BB2\u0BC8\u0BA4\u0BCD \u0BA4\u0BAF\u0BBE\u0BB0\u0BBF\u0B95\u0BCD\u0B95\u0BBF\u0BB1\u0BCB\u0BAE\u0BCD\u2026',error:'\u0B95\u0BC1\u0BB0\u0BB2\u0BC8 \u0B87\u0BAF\u0B95\u0BCD\u0B95 \u0BAE\u0BC1\u0B9F\u0BBF\u0BAF\u0BB5\u0BBF\u0BB2\u0BCD\u0BB2\u0BC8. \u0BAE\u0BC0\u0BA3\u0BCD\u0B9F\u0BC1\u0BAE\u0BCD \u0BAE\u0BC1\u0BAF\u0BB1\u0BCD\u0B9A\u0BBF\u0B95\u0BCD\u0B95\u0BB5\u0BC1\u0BAE\u0BCD.',replay:'\uD83D\uDD0A \u0BAE\u0BC0\u0BA3\u0BCD\u0B9F\u0BC1\u0BAE\u0BCD \u0B95\u0BC7\u0BB3\u0BC1\u0B99\u0BCD\u0B95\u0BB3\u0BCD'},
  Tanglish:{listen:'\uD83D\uDD0A Listen to Forecast',stop:'\u23F9 Forecast niruthunga',cancel:'Voice cancel pannunga',loading:'Forecast voice prepare pannrom\u2026',error:'Voice play aagala. Thirumba tap pannunga.',replay:'\uD83D\uDD0A Forecast thirumba kelunga'}
 };
 var state='idle',epoch=0,controller=null,context=null,sources=[],cacheKey='',cacheParts=[],cacheTotal=0,played=false,activeKey='';
 function $(id){return document.getElementById(id);}
 function isTamil(t){return /[\u0B80-\u0BFF]/.test(t);}
 // MOVIO_FORECAST_BIKE_CHOICE_V1: advisory only; never updates a booking slot.
 var BIKE_CHOICE={
  English:'If you prefer, you can choose another vehicle, or continue with your bike.',
  Tamil:'நீங்கள் விரும்பினால் வேறு வாகனத்தைத் தேர்வு செய்யலாம், அல்லது பைக்கிலேயே பயணத்தைத் தொடரலாம்.',
  Tanglish:'Neenga virumbina vera vehicle choose pannalaam, illa unga bike-la continue pannalaam.'
 };
 function rawForecastText(){var a=$('wxManualAdvice');return a?(a.textContent||'').trim():'';}
 function selectedBike(){
  var selected=typeof vehicle==='string'?vehicle:'';
  if(!selected){var active=document.querySelector('#vehicles .vehicle.active');selected=active&&active.dataset.type||'';}
  return String(selected).trim().toLowerCase()==='bike';
 }
 function forecastText(){
  var text=rawForecastText();
  if(!text||!selectedBike())return text;
  // Do not repeat an equivalent choice already included in the real advisory.
  var already=/keep\s+(?:your\s+|the\s+)?bike|continue\s+with\s+(?:your\s+|the\s+)?bike|bike[- ]la\s+continue|பைக்கிலேயே\s+(?:பயணத்தைத்\s+)?தொடர|முடிவு\s+உங்களுடையது|mudivu\s+unga\s+choice/i.test(text);
  if(already)return text;
  return text+' '+(BIKE_CHOICE[language()]||BIKE_CHOICE.English);
 }
 function language(){
  var sel=$('wxManualLanguage'),v=sel&&sel.value;
  if(v==='Tamil'||v==='Tanglish'||v==='English')return v;
  return isTamil(rawForecastText())?'Tamil':'English';
 }
 function words(){return COPY[language()]||COPY.English;}
 function reviewVisible(){var r=$('wxManualReview');return !!r&&!r.hidden&&r.offsetParent!==null;}
 function setLabel(){
  var b=$('wxForecastListenBtn');if(!b)return;
  var label=state==='loading'?words().cancel:state==='playing'?words().stop:played?words().replay:words().listen;
  if(b.textContent!==label)b.textContent=label;
  b.setAttribute('aria-pressed',String(state==='playing'));b.setAttribute('aria-busy',String(state==='loading'));
 }
 function note(t){var n=$('wxForecastListenNote');if(n&&n.textContent!==(t||''))n.textContent=t||'';}
 function stop(clearCache){
  epoch++;if(controller){controller.abort();controller=null;}
  sources.forEach(function(source){try{source.stop();}catch(e){}});sources=[];
  if(context){var old=context;context=null;old.close().catch(function(){});}
  if(clearCache){cacheParts=[];cacheTotal=0;cacheKey='';played=false;}
  activeKey='';state='idle';note('');setLabel();
 }
 async function play(){
  if(!reviewVisible()||!forecastText())return;
  if(state!=='idle'){stop(false);return;}
  var text=forecastText(),lang=language(),key=lang+'\n'+text,ticket=++epoch;
  var started=performance.now(),firstPlayed=false,nextTime=0,total=0,totalBytes=0;
  try{
   var AudioCtx=window.AudioContext||window.webkitAudioContext;
   if(!AudioCtx)throw new Error('Web Audio is unavailable');
   context=new AudioCtx();var ctx=context;
   // Unlock audio on the customer's tap, before waiting for any network response.
   var resume=ctx.resume();
   activeKey=key;state='loading';setLabel();note(words().loading);
   if(cacheKey!==key){cacheKey=key;cacheParts=[];cacheTotal=0;played=false;}
   controller=new AbortController();var ctl=controller;
   await resume;
   for(var part=0;part<(total||1);part++){
    if(ticket!==epoch)return;
    var raw=cacheParts[part];
    if(!raw){
     var timer=setTimeout(function(){ctl.abort();},120000);
     try{
      var res=await fetch('/weather-speech',{method:'POST',credentials:'same-origin',cache:'no-store',signal:ctl.signal,
       headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text,language:lang,part:part})});
      if(!res.ok)throw new Error('voice '+res.status);
      var data=await res.json();
      if(ticket!==epoch)return;
      if(data.protocol!=='parts-v1'||data.part!==part||!Number.isInteger(data.total_parts)||data.total_parts<1||data.total_parts>14||typeof data.audio!=='string')throw new Error('bad audio protocol');
      if(total&&total!==data.total_parts)throw new Error('changed forecast');
      cacheTotal=data.total_parts;
      var bin=atob(data.audio),bytes=new Uint8Array(bin.length);
      for(var i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);
      raw=bytes.buffer;cacheParts[part]=raw;
     }finally{clearTimeout(timer);}
    }
    total=cacheTotal;totalBytes+=raw.byteLength;
    if(totalBytes>9000000)throw new Error('forecast audio too large');
    var buffer=await ctx.decodeAudioData(raw.slice(0));
    if(ticket!==epoch)return;
    var source=ctx.createBufferSource();source.buffer=buffer;source.connect(ctx.destination);sources.push(source);
    nextTime=Math.max(nextTime,ctx.currentTime+0.02);var scheduled=nextTime;
    nextTime+=buffer.duration;
    if(part===total-1){source.onended=function(){if(ticket!==epoch)return;played=true;stop(false);};}
    source.start(scheduled);
    if(!firstPlayed){
     firstPlayed=true;state='playing';note('');setLabel();
     window.MOVIO_FORECAST_VOICE_TIMING={first_audio_ready_ms:Math.round(performance.now()-started),parts:total,complete:false};
    }
    // Prepare the next sentence while the already scheduled sentence is playing.
    // Deliberate pauses are included in each WAV by the existing pause helper.
   }
   if(ticket!==epoch)return;
   controller=null;
   window.MOVIO_FORECAST_VOICE_TIMING.prepared_ms=Math.round(performance.now()-started);
   window.MOVIO_FORECAST_VOICE_TIMING.complete=true;
   console.info('MOVIO forecast voice timing',window.MOVIO_FORECAST_VOICE_TIMING);
  }catch(e){if(ticket!==epoch)return;stop(true);note(words().error);console.warn('MOVIO forecast playback:',e.message);}
 }
 function ensureRow(){
  var review=$('wxManualReview');if(!review)return;
  var row=$(ROW_ID);
  if(!reviewVisible()||!forecastText()){if(row&&!row.hidden)row.hidden=true;if(state!=='idle')stop(false);return;}
  var actions=review.querySelector('.wx-review-actions');if(!actions)return;
  if(!row){
   row=document.createElement('div');row.id=ROW_ID;
   row.innerHTML='<button type="button" id="wxForecastListenBtn" aria-pressed="false"></button><span id="wxForecastListenNote" role="status" aria-live="polite"></span>';
   row.querySelector('button').addEventListener('click',play);
  }
  if(row.nextElementSibling!==actions||row.parentNode!==actions.parentNode)actions.parentNode.insertBefore(row,actions);
  if(row.hidden)row.hidden=false;
  /* new forecast text or language => drop old audio */
  var currentKey=language()+'\n'+forecastText();
  if(activeKey&&activeKey!==currentKey)stop(true);
  if(cacheKey&&cacheKey!==currentKey&&state==='idle'){cacheParts=[];cacheTotal=0;cacheKey='';played=false;}
  setLabel();
 }
 var st=document.createElement('style');
 st.textContent='#'+ROW_ID+'{margin:12px 0;display:flex;align-items:center;gap:8px;flex-wrap:wrap}#'+ROW_ID+'[hidden]{display:none!important}'
  +'#wxForecastListenBtn{min-height:44px;width:100%;padding:10px 14px;border:1px solid var(--line,#d9d9d9);border-radius:12px;background:var(--yellow,#ffcc29);color:var(--ink,#17191d);font:inherit;font-weight:600;cursor:pointer;white-space:normal}'
  +'#wxForecastListenBtn[aria-pressed="true"]{background:var(--paper,#fff)}#wxForecastListenNote{font-size:12px;color:var(--muted,#667085);overflow-wrap:anywhere}';
 document.head.appendChild(st);
 var queued=false;
 function schedule(){if(queued)return;queued=true;setTimeout(function(){queued=false;ensureRow();},60);}
 new MutationObserver(schedule).observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden'],characterData:true});
 document.addEventListener('change',function(e){if(e.target&&e.target.id==='wxManualLanguage'){stop(true);schedule();}},true);
 document.addEventListener('click',function(e){if(e.target.closest&&e.target.closest('#wxManualContinue,#wxManualChange,#logout,#driverMode,#aiCall,#vehicles,#bookRide'))stop(false);},true);
 window.addEventListener('pagehide',function(){stop(true);});
 document.addEventListener('visibilitychange',function(){if(document.hidden)stop(false);});
 schedule();
})();
