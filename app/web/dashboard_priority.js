/* Prioritize the assigned ride without changing existing booking/voice controls. */
const priorityPreviousRenderRider=renderRider;
const priorityPreviousRenderDriver=renderDriver;
let priorityAutoRide=null;
function priorityElement(tag,className,text){const node=document.createElement(tag);node.className=className;if(text!==undefined)node.textContent=text;return node}
function priorityInstallLayout(){
 const panel=$('riderPanel'),trip=$('riderTrip');
 if(!panel||!trip)return;
 panel.classList.add('priority-panel');trip.classList.add('priority-trip');
 const handle=panel.querySelector('.handle');
 panel.insertBefore(trip,handle?handle.nextSibling:panel.firstChild);
 const gps=$('customerGPS')?.closest('.gps-card');if(gps)trip.append(gps);
 if(!$('pickupOTPCard')){
  const otp=priorityElement('section','pickup-otp');otp.id='pickupOTPCard';
  otp.append(priorityElement('span','eyebrow','PICKUP VERIFICATION'));
  const digits=priorityElement('strong','otp-digits');digits.id='pickupOTPDigits';otp.append(digits);
  otp.append(priorityElement('p','muted','Give this code to your assigned driver only when you are ready to start the ride.'));
  $('driverDetails').after(otp);
 }
 if(!$('priorityRoute')){const route=priorityElement('div','priority-route');route.id='priorityRoute';$('tripSummary').after(route)}
 if(!$('priorityTimeline')){const timeline=priorityElement('div','ride-timeline');timeline.id='priorityTimeline';trip.querySelector('.section-row').after(timeline)}
 if(!$('reviewLocationRequest')){
  const button=movioBtn('Review 15-minute location request',()=>{
   if(!latestRide||latestRide.location_request?.status!=='pending')return;
   movioPromptRide=latestRide.id;$('locationConsentDialog').classList.remove('hidden');$('denyLocation').focus();
  });button.id='reviewLocationRequest';trip.append(button);
 }
 $('tripSummary').classList.add('priority-summary');
 $('driverDetails').classList.add('priority-driver');
 $('trackDriver').textContent='Track driver on map';
 const shortcut=$('joinDriver');if(shortcut)shortcut.style.display='none';
}
renderRider=function(r){
 priorityInstallLayout();priorityPreviousRenderRider(r);
 const names={requested:'Finding your driver',accepted:'Driver accepted your ride',arriving:'Your driver is on the way',in_progress:'Your ride is in progress',completed:'Ride completed',cancelled:'Ride cancelled',needs_location:'Pickup details needed'};
 $('riderStatus').textContent=names[r.status]||r.status;
 const title=$('riderTrip').querySelector('h2');if(title)title.textContent=r.driver_id?'Your driver & ride':'Your booking';
 $('riderTrip').dataset.stage=r.status;
 const timeline=$('priorityTimeline');timeline.replaceChildren();
 const steps=['requested','accepted','arriving','in_progress'];const current=steps.indexOf(r.status);
 for(const [index,label] of ['Requested','Accepted','On the way','Ride started'].entries())timeline.append(priorityElement('span',index<=current?'step complete':'step',label));
 const driver=$('driverDetails');driver.replaceChildren();
 if(r.driver_id){
  const avatar=priorityElement('div','driver-avatar',(r.driver_name||'D').slice(0,1).toUpperCase());driver.append(avatar);
  const details=priorityElement('div','driver-identity');
  details.append(priorityElement('small','eyebrow','YOUR ASSIGNED DRIVER'),priorityElement('h3','',r.driver_name||'Assigned driver'));
  details.append(priorityElement('p','',r.vehicle+' · '+(r.driver_vehicle_number||'Registration unavailable')));
  const phone=String(r.driver_phone||'');
  if(/^\+?[0-9]{7,15}$/.test(phone)){const call=priorityElement('a','driver-call','Call '+phone);call.href='tel:'+phone;details.append(call)}
  else details.append(priorityElement('p','',phone||'Phone unavailable'));
  driver.append(details);
 }else{driver.append(priorityElement('p','','Your request is visible to matching '+r.vehicle+' drivers. Driver details will appear here after acceptance.'))}
 const otp=$('pickupOTPCard');otp.classList.toggle('hidden',!r.driver_id||!r.pickup_otp||!['accepted','arriving'].includes(r.status));$('pickupOTPDigits').textContent=r.pickup_otp||'';
 const route=$('priorityRoute');route.replaceChildren();route.append(priorityElement('p','','Pickup · '+r.pickup),priorityElement('p','','Drop-off · '+r.destination));
 const request=$('reviewLocationRequest'),state=r.location_request?.status;
 request.classList.toggle('hidden',!r.driver_id||!movioActive(r));
 request.disabled=state!=='pending';
 request.textContent=state==='pending'?'Review 15-minute location request':state==='granted'?'Location permission granted':state==='expired'?'15-minute access expired':state==='revoked'?'Location sharing stopped':'Location access: awaiting driver request';
};
renderDriver=function(rides){
 priorityPreviousRenderDriver(rides);
 for(const r of rides.filter(r=>r.driver_id===movioMe?.id&&['accepted','arriving'].includes(r.status))){
  const card=Array.from($('driverRides').children).find(node=>node.querySelector('h3')?.textContent.startsWith('#'+r.id+' ·'));
  if(!card)continue;
  const label=priorityElement('label','driver-otp-label','Customer pickup OTP');
  const input=document.createElement('input');input.id='driverPickupOTP_'+r.id;input.type='text';input.inputMode='numeric';input.maxLength=4;input.pattern='[0-9]{4}';input.autocomplete='off';input.placeholder='4 digits';
  input.value=window.priorityOTPInputs?.[r.id]||'';
  input.oninput=()=>{window.priorityOTPInputs??={};window.priorityOTPInputs[r.id]=input.value.replace(/\D/g,'').slice(0,4);input.value=window.priorityOTPInputs[r.id]};
  label.append(input);card.querySelector('.actions').before(label);
 }
};
// Promote a newly accepted booking once; keep the user's explicit selection thereafter.
const priorityRefreshRides=refreshRides;
refreshRides=async function(){
 await priorityRefreshRides();
 if(movioMe?.role!=='customer')return;
 try{
  const {rides}=await api('/rides');
  const assigned=rides.filter(r=>r.driver_id&&movioActive(r)).sort((a,b)=>b.updated-a.updated)[0];
  if(assigned&&assigned.id!==priorityAutoRide){priorityAutoRide=assigned.id;rideId=assigned.id;latestRide=assigned;renderRider(assigned);$('activeRideSelect').value=String(assigned.id);await refreshLocations()}
 }catch(error){console.warn('Assigned ride refresh',error)}
};
priorityInstallLayout();
