/* Refreshes bookings saved by the call page; also supports older call pages. */
(function installWeatherAction(){
  'use strict';
  if(typeof handleMovioVoiceMessage!=='function'||typeof post!=='function'){
    console.error('Weather booking: load after the existing dashboard app.js.');return;
  }
  if(window.__weatherActionVersion==='0.3.0')return;
  window.__weatherActionVersion='0.3.0';
  const original=handleMovioVoiceMessage,completed=new Map();
  handleMovioVoiceMessage=async function(m){
    if(!m||m.channel!=='ai-ride-call'||m.nonce!==aiNonce)return;
    if(m.type==='booking_saved'){
      toast('Ride request #'+m.id+' saved');await renderVoiceHistory();await refreshRides();await scheduled();return;
    }
    if(m.type!=='action'||m.action?.type!=='weather_book')return original(m);
    const a=m.action,id=a.request_id;
    if(!id||!a.token)return;
    if(!completed.has(id))completed.set(id,(async()=>{
      try{return await post('/weather-booking/commit',{token:a.token});}
      catch(e){return {ok:false,error:e.message};}
    })());
    const result=await completed.get(id);
    sendVoice('result',{...result,request_id:id});
    if(result.ok){toast('Ride request #'+result.id+' saved');await renderVoiceHistory();await refreshRides();await scheduled();}
    else toast(result.error||'Booking was not saved');
  };
  async function scheduled(){
    let root=document.getElementById('weatherScheduledRides');
    try{const data=await api('/rides'),rides=data.rides.filter(r=>r.status==='scheduled');
      if(!rides.length){root?.replaceChildren();return;}
      if(!root){root=document.createElement('section');root.id='weatherScheduledRides';(document.getElementById('aiRideHistory')||document.body).append(root);}
      root.replaceChildren();const heading=document.createElement('h3');heading.textContent='Scheduled rides';root.append(heading);
      for(const r of rides){const item=document.createElement('div');item.className='ride-card';const p=document.createElement('p');p.textContent=`#${r.id} · ${r.vehicle} · ${r.pickup} → ${r.destination} · ${r.pickup_time} · ₹${r.fare}`;
        const b=document.createElement('button');b.type='button';b.textContent='Cancel #'+r.id;b.onclick=async()=>{try{await post('/weather-booking/cancel',{ride_id:r.id});await scheduled();await refreshRides();}catch(e){toast(e.message);}};
        item.append(p,b);root.append(item);}
    }catch(e){/* The existing sign-in flow handles expired accounts. */}
  }
  scheduled();setInterval(scheduled,10000);
})();
