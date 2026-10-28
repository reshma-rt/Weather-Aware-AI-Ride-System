/* Assigned-ride matching, consent and live tracking. Loaded after app.js. */
let movioMe=null, movioPromptRide=null, movioPromptKey=null, movioSelectedRide=null;
let movioCustomerGrants=new Map(),movioGPSPaused=false;
let movioLocations=[], movioTrackingOpen=false;
const movioBtn=(text,fn,cls='outline')=>{const b=document.createElement('button');b.type='button';b.className=cls;b.textContent=text;b.onclick=fn;return b};
const movioP=(parent,text)=>{const p=document.createElement('p');p.textContent=text;parent.append(p)};
const movioActive=r=>['accepted','arriving','in_progress'].includes(r.status);
function clearLiveMarkers(){for(const k of ['liveDriver','liveCustomer'])if(markers[k]){map.removeLayer(markers[k]);delete markers[k]}}
const movioRefreshProfile=async()=>{
 movioMe=await api('/me');$('accountLabel').textContent=`${movioMe.name} · ${movioMe.role}`;
 if(movioMe.role==='driver')$('driverProfile').textContent=`${movioMe.name} · ${movioMe.phone} · ${movioMe.vehicle_type||'Choose vehicle type'} · ${movioMe.vehicle_number||'Add vehicle number'}`;
 setRole(movioMe.role);
};
function movioClosePrompt(){movioPromptRide=null;movioPromptKey=null;$('locationConsentDialog').classList.add('hidden')}
renderRider=function(r){
 $('riderTrip').classList.remove('hidden');$('riderStatus').textContent=r.status.replaceAll('_',' ').toUpperCase();
 $('tripSummary').textContent=`#${r.id} · ${r.vehicle} · ₹${r.fare}`;
 $('driverDetails').textContent=r.driver_id?`Driver: ${r.driver_name||'Assigned'} · Phone: ${r.driver_phone||'—'} · Vehicle ID: ${r.driver_vehicle_number||'—'} · ${r.vehicle}`:'Waiting for a matching driver';
 $('cancelRide').disabled=!['needs_location','requested','accepted','arriving'].includes(r.status);
 $('bookRide').disabled=movioBookingBusy;
 $('trackDriver').classList.toggle('hidden',!r.driver_id||!movioActive(r));
 const selected=movioActive(r)?r.id:null;
 if(movioSelectedRide!==selected){clearLiveMarkers();if(movioTrackingOpen)movioCloseTracking()}
 movioSelectedRide=selected;
 const pending=movioActive(r)&&r.location_request?.status==='pending';
 const key=`${r.id}:${r.location_request?.requested}`;
 if(pending&&movioPromptKey!==key){movioPromptRide=r.id;movioPromptKey=key;
  $('locationConsentText').textContent=`${r.driver_name||'Your assigned driver'} (${r.driver_vehicle_number||r.vehicle}) wants your live location for up to 15 minutes. Share only if you agree. You can stop at any time; sharing also stops when the ride ends. Google Maps receives coordinates when its live map is opened.`;
  $('locationConsentDialog').classList.remove('hidden');$('denyLocation').focus();
 }
 if(!pending)movioClosePrompt();
 const until=r.location_share_until*1000;
 if(shareUntil>Date.now()&&!movioGPSPaused){
  if(watchId===null)startWatch('customer');
 }else if(watchId!==null&&!driverOnline){stopLocalGPS('customer')}
 $('customerGPS').textContent=movioGPSPaused?'Retry stop sharing':`Stop sharing #${r.id}`;
 $('customerGPS').disabled=!(until>Date.now());
 if(!movioActive(r)){clearLiveMarkers();if(movioTrackingOpen)movioCloseTracking()}
};
renderDriver=function(rides){
 const holder=$('driverRides');holder.replaceChildren();
 const list=rides.filter(r=>r.status==='requested'||(r.driver_id===movioMe?.id&&movioActive(r)));
 const assigned=list.find(r=>r.driver_id===movioMe?.id&&movioActive(r));
 movioSelectedRide=assigned?.id||null;
 if(!assigned){clearLiveMarkers();if(movioTrackingOpen)movioCloseTracking()}
 if(!list.length){movioP(holder,`No ${movioMe?.vehicle_type||'matching'} ride requests at the moment.`);return}
 for(const r of list){
  const card=document.createElement('div');card.className='ride-card';
  const h=document.createElement('h3');h.textContent=`#${r.id} · ${r.vehicle} · ₹${r.fare}`;card.append(h);
  movioP(card,`Customer: ${r.customer_name}`);movioP(card,`Pickup: ${r.pickup}`);movioP(card,`Destination: ${r.destination}`);movioP(card,`Status: ${r.status.replaceAll('_',' ')}`);
  const actions=document.createElement('div');actions.className='actions';
  const change=async status=>{try{await post(`/rides/${r.id}/status`,{status,...(status==='in_progress'?{otp:document.getElementById('driverPickupOTP_'+r.id)?.value||''}:{})});toast(`Ride #${r.id}: ${status}`);await refreshRides();await refreshLocations()}catch(e){toast(e.message)}};
  if(r.status==='requested'){
   actions.append(movioBtn('Accept',()=>change('accepted'),'primary'));
   actions.append(movioBtn('Cancel request',async()=>{try{await post(`/rides/${r.id}/decline`,{});toast('Request removed from your dashboard');await refreshRides()}catch(e){toast(e.message)}},'secondary'));
   movioP(card,'Cancel removes this request for you. Another matching driver can accept it.');
  }else{
   const transitions={accepted:[['arriving','On my way'],['in_progress','Start ride'],['cancelled','Cancel ride']],arriving:[['in_progress','Start ride'],['cancelled','Cancel ride']],in_progress:[['completed','Complete ride']]};
   for(const [st,label] of transitions[r.status]||[])actions.append(movioBtn(label,()=>change(st),st==='cancelled'?'secondary':'primary'));
   const st=r.location_request?.status;
   if(st==='granted'&&r.location_share_until*1000>Date.now()){
    const left=Math.max(0,Math.ceil(r.location_share_until-Date.now()/1000));
    movioP(card,`Customer live location: ${Math.floor(left/60)}:${String(left%60).padStart(2,'0')} remaining`);
    actions.append(movioBtn('View Customer location',()=>movioOpenTracking(r.id,'customer')));
   }else if(['expired','revoked'].includes(st)){movioP(card,st==='expired'?'Customer location sharing expired.':'Customer stopped sharing location.');}
   else{
    const b=movioBtn(st==='pending'?'Location request sent':'Request customer location',async()=>{try{await post(`/rides/${r.id}/location-request`,{});toast('Location request sent');await refreshRides()}catch(e){toast(e.message)}});
    b.disabled=st==='pending';actions.append(b);
    if(st==='denied')movioP(card,'Customer declined location access.');
   }
  }
  card.append(actions);holder.append(card);
 }
};
refreshRides=async function(){
 if(!movioMe)return;
 try{const {rides}=await api('/rides');
  if(movioMe.role==='driver')renderDriver(rides);
  else{
   movioCustomerGrants=new Map(rides.filter(r=>r.location_share_until*1000>Date.now()).map(r=>[r.id,r.location_share_until*1000]));
   shareUntil=Math.max(0,...movioCustomerGrants.values());
   const active=rides.filter(r=>!['completed','cancelled'].includes(r.status));
   const picker=$('activeRideSelect');picker.replaceChildren();
   for(const r of active){const option=document.createElement('option');option.value=String(r.id);option.textContent=`#${r.id} · ${r.vehicle} · ${r.pickup} → ${r.destination} · ${r.status.replaceAll('_',' ')}`;picker.append(option)}
   const pending=active.find(r=>r.id===movioPromptRide&&r.location_request?.status==='pending')||active.find(r=>r.location_request?.status==='pending');
   const current=pending||active.find(r=>r.id===rideId)||active[0]||rides[0];
   if(current)picker.value=String(current.id);

   if(current){rideId=current.id;latestRide=current;renderRider(current)}
   else{$('riderTrip').classList.add('hidden');$('bookRide').disabled=false;movioSelectedRide=null;movioClosePrompt();clearLiveMarkers()}
  }
 }catch(e){console.warn('Ride refresh',e)}
};
refreshLocations=async function(){
 if(!movioMe)return;
 try{
  const selected=movioSelectedRide;
  const {locations:received}=await api('/locations'+(selected?`?ride_id=${selected}`:''));
  const locations=selected?received:received.filter(p=>p.user_id===movioMe.id);
  if(selected!==movioSelectedRide)return;
  movioLocations=locations;
  for(const [who,key] of [['driver','liveDriver'],['customer','liveCustomer']]){
   const loc=locations.find(p=>p.role===who&&p.user_id!==movioMe.id);
   if(loc)mark(key,[loc.lat,loc.lng],who==='driver'?'driver':'me');
   else if(markers[key]){map.removeLayer(markers[key]);delete markers[key]}
  }
  if(movioTrackingOpen)movioUpdateTracking(locations);
 }catch(e){clearLiveMarkers();movioLocations=[];if(movioTrackingOpen)movioUpdateTracking([]);console.warn('Location refresh',e)}
};
$('trackDriver').onclick=()=>movioOpenTracking(rideId,'driver');
let movioResponding=false;
async function movioRespondLocation(allow){
 const id=movioPromptRide;if(!id||movioResponding)return;
 movioResponding=true;$('allowLocation').disabled=true;$('denyLocation').disabled=true;
 try{
  const position=allow?await locate():null;
  const result=await post(`/rides/${id}/location-response`,{allow});movioClosePrompt();
  if(allow){movioGPSPaused=false;shareUntil=Math.max(shareUntil,result.expires*1000);$('customerGPS').textContent='Stop sharing';await publish('customer',position);startWatch('customer');toast('Live location shared for up to 15 minutes')}
  else toast('Location access declined');
  await refreshRides();await refreshLocations();
 }catch(e){toast('Location access: '+e.message);if(allow&&shareUntil)await revoke('customer',id)}
 finally{movioResponding=false;$('allowLocation').disabled=false;$('denyLocation').disabled=false}
}
$('allowLocation').onclick=()=>movioRespondLocation(true);
$('denyLocation').onclick=()=>movioRespondLocation(false);
$('customerGPS').onclick=async()=>{if(shareUntil>Date.now()){await revoke('customer',rideId);await refreshRides();await refreshLocations();toast('Location sharing updated for booking #'+rideId)}};
$('shareToggle').onclick=()=>movioMe?.role==='driver'?$('driverGPS').click():$('customerGPS').click();
function movioEditProfile(){
 $('profileName').value=movioMe.name;$('profilePhone').value=movioMe.phone;$('profileVehicleType').value=movioMe.vehicle_type||'Mini';$('profileVehicleNumber').value=movioMe.vehicle_number||'';
 $('profileDialog').classList.remove('hidden');$('profileName').focus();
}
$('editDriverProfile').onclick=movioEditProfile;
$('profileForm').onsubmit=async e=>{e.preventDefault();$('profileError').textContent='';try{
 await post('/driver-profile',{name:$('profileName').value,vehicle_type:$('profileVehicleType').value,vehicle_number:$('profileVehicleNumber').value});
 $('profileDialog').classList.add('hidden');await movioRefreshProfile();await refreshRides();
}catch(e){$('profileError').textContent=e.message}};

$('refreshRides').onclick=()=>refreshRides();

async function movioSelectBooking(id){
 if(movioTrackingOpen)movioCloseTracking();clearLiveMarkers();rideId=Number(id);
 await refreshRides();await refreshLocations();
}
$('activeRideSelect').onchange=()=>movioSelectBooking($('activeRideSelect').value);
