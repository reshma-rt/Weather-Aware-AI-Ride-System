/* Customer booking details and one selection/route path for search, GPS and map. */
(function installCustomerBookingTools(){
 'use strict';
 if(window.MOVIOCustomerBookingUI)return;
 const el=id=>document.getElementById(id);
 if(!el('riderPanel')||typeof setPlace!=='function'||typeof updateRoute!=='function')return;
 const book=el('bookRide'),oldPreview=book?.onclick;
 if(typeof oldPreview!=='function'||!el('weatherManual'))return;
 const state={field:'pickup',routeKey:null,routePromise:null,routeSeq:0,routeController:null,previewBusy:false,lastPreview:null,previewTimer:null,searchSeq:0,dialogSeq:0,dialogId:null,dialogTimer:null,returnFocus:null};
 // MOVIO_MAIN_LOCALITY_V1: use the existing selection/route/preview state.
 state.pinSeq={pickup:0,destination:0};state.pinPending={pickup:null,destination:null};state.pinControllers={pickup:null,destination:null};
 function invalidatePin(id){
  state.pinSeq[id]++;state.pinControllers[id]?.abort();state.pinControllers[id]=null;state.pinPending[id]=null;
 }
 function pendingPins(){return Object.values(state.pinPending).filter(Boolean);}
 function pinLabel(id){
  const lang=el('wxManualLanguage')?.value;
  if(lang==='Tamil')return id==='pickup'?'தேர்ந்தெடுத்த புறப்படும் இடம்':'தேர்ந்தெடுத்த சேரும் இடம்';
  return id==='pickup'?'Selected pickup':'Selected drop-off';
 }
 function pinPlace(id,point){
  if(!['pickup','destination'].includes(id)||locked()||!customer())return Promise.resolve(false);
  const lat=Number(point.lat),lng=Number(point.lng);
  if(!Number.isFinite(lat)||Math.abs(lat)>90||!Number.isFinite(lng)||Math.abs(lng)>180)return Promise.resolve(false);
  invalidatePin(id);state.searchSeq++;state.lastPreview=null;clearTimeout(state.previewTimer);
  if(typeof searchTimer!=='undefined')clearTimeout(searchTimer);
  el('suggestions')?.replaceChildren();
  const ticket=state.pinSeq[id],controller=new AbortController();state.pinControllers[id]=controller;
  let owner=null;
  const initial={lat,lng,name:pinLabel(id)};
  const task=(async()=>{
   let resolved=initial;
   try{
    const data=await request('reverse-address?'+new URLSearchParams({lat,lng}),{signal:controller.signal});
    const p=data.place;
    if(p&&p.locality_status!=='unavailable'&&String(p.locality||p.name||'').trim()){
     // Ignore the provider feature's coordinates. Routing uses the original pin.
     resolved={lat,lng,name:String(p.locality||p.name).trim(),full_address:String(p.full_address||'')};
    }else if(!controller.signal.aborted)console.warn('MOVIO: locality label unavailable; selected coordinates kept.');
   }catch(error){if(!controller.signal.aborted)console.warn('MOVIO: reverse lookup failed; selected coordinates kept.');}
   if(ticket!==state.pinSeq[id])return false;
   state.pinPending[id]=null;state.pinControllers[id]=null;
   if(locked()||!customer())return false;
   if(selected(id)!==owner||el(id).value.trim()!==owner?.name){updateRoute();return false;}
   const ok=applyPlace(id,resolved);if(ok)status('');return ok;
  })();
  state.pinPending[id]=task;
  setPlace(id,initial);owner=selected(id);
  return task;
 }
 const words=()=>({Tamil:{searching:'முகவரியைத் தேடுகிறோம்…',choose:'பட்டியலில் சரியான முகவரியைத் தேர்ந்தெடுக்கவும்.',none:'முகவரி கிடைக்கவில்லை. தெரு, பகுதி அல்லது அஞ்சல் குறியீட்டுடன் மீண்டும் தேடுங்கள்.',locating:'உங்கள் தற்போதைய இடத்தைப் பெறுகிறோம்…',gps:'உலாவியில் இருப்பிட அனுமதியை வழங்கி மீண்டும் முயற்சிக்கவும்.',route:'சாலை தூரத்தைச் சரிபார்க்கிறோம்…',retry:'சாலை வழியை மீண்டும் சரிபார்க்க, பயணச் சரிபார்ப்பு பொத்தானை அழுத்தவும்.',address:'முகவரி அல்லது அருகிலுள்ள இடத்தின் பெயரை உள்ளிடுங்கள்.'},Tanglish:{searching:'Address search pannrom…',choose:'List-la correct address select pannunga.',none:'Street, area illa postcode serthu thirumba search pannunga.',locating:'Unga current location edukkrom…',gps:'Browser location permission allow pannittu retry pannunga.',route:'Road distance check pannrom…',retry:'Road route retry panna Review ride press pannunga.',address:'Address illa landmark type pannunga.'}}[el('wxManualLanguage')?.value]||{searching:'Searching addresses…',choose:'Choose the correct address from the results.',none:'No address matched. Try a street, area or postcode.',locating:'Getting your current location…',gps:'Allow browser location permission, then try again.',route:'Checking the road route…',retry:'Press Review ride to retry the road route.',address:'Enter an address or nearby landmark.'});
 function status(text){if(el('wxManualStatus'))el('wxManualStatus').textContent=text;}
 function locked(){return ['wxManualDate','wxManualLanguage','wxManualCount'].some(id=>el(id)?.disabled);}
 function customer(){return typeof role==='undefined'||role==='customer';}
 function validPlace(p){return p&&Number.isFinite(Number(p.lat))&&Math.abs(Number(p.lat))<=90&&Number.isFinite(Number(p.lng))&&Math.abs(Number(p.lng))<=180&&String(p.name||'').trim();}
 function selected(id){return id==='pickup'?pickup:destination;}
 function matches(id){const p=selected(id);return validPlace(p)&&el(id).value.trim()===String(p.name).trim();}
 function placesKey(){return JSON.stringify([pickup?.name,pickup?.lat,pickup?.lng,destination?.name,destination?.lat,destination?.lng]);}
 function previewKey(){return JSON.stringify([placesKey(),el('wxManualDate')?.value,el('wxManualLanguage')?.value,el('wxManualCount')?.value,vehicle,km]);}
 async function request(path,options={}){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),path.startsWith('reverse-address?')?30000:16000);
  const cancel=()=>controller.abort();if(options.signal){if(options.signal.aborted)controller.abort();else options.signal.addEventListener('abort',cancel,{once:true});}
  try{const response=await fetch('/api/customer-tools/'+path,{credentials:'same-origin',cache:'no-store',...options,signal:controller.signal});
   const data=await response.json();if(!response.ok||!data.ok)throw Error(data.error||'Please retry this request.');return data;
  }catch(error){if(error.name==='AbortError')throw Error('The request timed out. Please retry.');throw error;}finally{clearTimeout(timer);options.signal?.removeEventListener('abort',cancel);}
 }
 function clearRoute(){state.routeKey=null;km=0;minutes=0;routeData=null;if(routeLine){map.removeLayer(routeLine);routeLine=null;}if(typeof fares==='function')fares();}
 function schedulePreview(){
  clearTimeout(state.previewTimer);
  state.previewTimer=setTimeout(()=>{
   if(customer()&&!locked()&&!book.disabled&&!state.previewBusy&&matches('pickup')&&matches('destination')&&el('wxManualDate')?.value&&state.routeKey===placesKey()&&state.lastPreview!==previewKey())preview();
  },650);
 }
 updateRoute=function(){
  const ticket=++state.routeSeq;state.routeController?.abort();state.routeKey=null;
  if(pendingPins().length||!matches('pickup')||!matches('destination')){clearRoute();state.routePromise=Promise.resolve(false);return state.routePromise;}
  const key=placesKey(),a={...pickup},b={...destination};const controller=new AbortController();state.routeController=controller;
  clearRoute();el('routeInfo').textContent=words().route;
  status(words().route);
  state.routePromise=(async()=>{
   try{const params=new URLSearchParams({plat:a.lat,plng:a.lng,dlat:b.lat,dlng:b.lng});
    const data=await request('route?'+params,{signal:controller.signal});
    if(ticket!==state.routeSeq||key!==placesKey())return false;
    const route=data.route;if(!route||!Number.isFinite(Number(route.km))||Number(route.km)<=0)throw Error('The road distance needs another check.');
    km=Number(route.km);minutes=Number(route.minutes)||0;routeData=Array.isArray(route.geometry)&&route.geometry.length>1?route.geometry:null;
    if(routeLine){map.removeLayer(routeLine);routeLine=null;}
    if(routeData){routeLine=L.polyline(routeData,{color:'#15191e',weight:5,opacity:.85}).addTo(map);map.fitBounds(routeLine.getBounds(),{padding:[45,45]});}
    el('routeInfo').textContent=km.toFixed(1)+' km'+(minutes?' · ~'+minutes+' min':'')+' · Road route · Fare is an estimate';
    state.routeKey=key;fares();schedulePreview();return true;
   }catch(error){if(ticket===state.routeSeq&&key===placesKey()){clearRoute();el('routeInfo').textContent=words().retry;status(error.message);}return false;}
  })();return state.routePromise;
 };
 function applyPlace(id,p){
  if(locked()||!customer()||!validPlace(p))return false;
  invalidatePin(id);
  setPlace(id,{lat:Number(p.lat),lng:Number(p.lng),name:String(p.name).trim()},false);
  el(id).title=p.full_address||p.name;el('suggestions')?.replaceChildren();state.lastPreview=null;
  return matches(id);
 }
 async function searchAddress(id=state.field,autoChoose=true){
  if(locked()||!customer())return false;
  const input=el(id),query=input.value.trim();state.field=id;
  if(query.length<3){status(words().address);input.focus();return false;}
  const seq=++state.searchSeq;const holder=el('suggestions');holder.textContent=words().searching;status(words().searching);
  try{const data=await request('address-search?'+new URLSearchParams({q:query}));
   if(seq!==state.searchSeq||query!==input.value.trim()||locked())return false;
   const places=Array.isArray(data.places)?data.places.filter(validPlace):[];holder.replaceChildren();
   if(places.length===1&&autoChoose){const ok=applyPlace(id,places[0]);if(ok)status('');return ok;}
   for(const p of places){const button=document.createElement('button');button.type='button';button.className='movio-address-result';button.textContent=p.full_address||p.name;
    button.onclick=()=>{if(seq!==state.searchSeq||query!==input.value.trim()||locked())return;if(applyPlace(id,p))status('');};holder.append(button);}
   holder.setAttribute('aria-live','polite');status(places.length?words().choose:words().none);return false;
  }catch(error){if(seq===state.searchSeq){holder.textContent=error.message;status(error.message);}return false;}
 }
 async function currentPickup(){
  if(locked()||!customer())return;state.searchSeq++;const seq=state.searchSeq,button=el('useCurrentPickup');if(button)button.disabled=true;status(words().locating);
  try{const position=typeof locate==='function'?await locate():await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(p=>resolve({lat:p.coords.latitude,lng:p.coords.longitude}),reject,{enableHighAccuracy:true,timeout:12000,maximumAge:3000}));
   if(seq!==state.searchSeq||locked())return;
   if(await pinPlace('pickup',position))state.field='destination';
  }catch{status(words().gps);}finally{if(button)button.disabled=locked();}
 }
 async function preview(event){
  event?.preventDefault();if(!customer()||locked()||book.disabled||state.previewBusy)return;
  clearTimeout(state.previewTimer);state.previewBusy=true;
  try{
   const resolving=pendingPins();if(resolving.length)await Promise.allSettled(resolving);
   if(locked()||!customer())return;
   for(const id of ['pickup','destination'])if(!matches(id)&&!await searchAddress(id,true))return;
   if(!el('wxManualDate')?.value){await oldPreview.call(book,event);return;}
   const key=placesKey();
   if(state.routeKey!==key){
    if(state.routePromise)await state.routePromise;
    if(state.routeKey!==placesKey()&&!await updateRoute())return;
   }
   if(locked()||!matches('pickup')||!matches('destination')||state.routeKey!==placesKey())return;
   const captured=previewKey();await oldPreview.call(book,event);
   if(captured===previewKey()&&el('wxManualReview')&&!el('wxManualReview').hidden)state.lastPreview=captured;
  }catch(error){status(error.message);}finally{state.previewBusy=false;}
 }
 book.onclick=preview;
 for(const id of ['pickup','destination']){
  el(id).addEventListener('focus',()=>state.field=id);
  el(id).addEventListener('input',()=>{
   invalidatePin(id);state.field=id;state.searchSeq++;state.lastPreview=null;clearTimeout(state.previewTimer);
   if(!matches(id)){state.routeController?.abort();state.routeSeq++;clearRoute();}
  });
  el(id).addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();event.stopImmediatePropagation();searchAddress(id);}},true);
 }
 if(el('searchAddress'))el('searchAddress').onclick=()=>searchAddress(state.field);
 if(el('useCurrentPickup'))el('useCurrentPickup').onclick=currentPickup;
 for(const id of ['wxManualDate','wxManualLanguage','wxManualCount','wxPickupDay','wxPickupTime'])el(id)?.addEventListener('change',()=>{state.lastPreview=null;schedulePreview();});
 el('vehicles')?.addEventListener('click',()=>{state.lastPreview=null;schedulePreview();});

 // Details use the authenticated single-booking API, never a stale card's data.
 const dialog=document.createElement('dialog');dialog.id='movioBookingDetails';dialog.setAttribute('aria-labelledby','movioDetailsTitle');
 dialog.innerHTML='<div class="movio-detail-head"><div><span class="movio-detail-eyebrow">YOUR BOOKING</span><h2 id="movioDetailsTitle">Booking details</h2></div><button type="button" class="movio-detail-close" aria-label="Close booking details">×</button></div><div class="movio-detail-content" aria-live="polite"></div><div class="movio-detail-footer"><button type="button" class="outline" data-refresh-details>Refresh details</button><button type="button" data-close-details>Done</button></div>';
 document.body.append(dialog);const content=dialog.querySelector('.movio-detail-content');
 function node(tag,className,text){const n=document.createElement(tag);if(className)n.className=className;if(text!==undefined)n.textContent=String(text);return n;}
 function shown(value){return value!==null&&value!==undefined&&value!==''?String(value):'Not recorded';}
 function date(value){if(value===null||value===undefined||value==='')return 'Not recorded';
  const raw=typeof value==='number'?value*1000:/^\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?$/.test(value)?value+'+05:30':value;
  const d=new Date(raw);return Number.isNaN(d.getTime())?String(value):new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'long',year:'numeric',hour:'numeric',minute:'2-digit',hour12:true}).format(d);}
 function field(parent,label,value,className=''){const box=node('div','movio-detail-field '+className);box.append(node('dt','',label),node('dd','',shown(value)));parent.append(box);}
 function renderDetails(r){
  content.replaceChildren();el('movioDetailsTitle').textContent='Booking #'+r.id;
  content.append(node('span','movio-detail-status',String(r.status||'').replaceAll('_',' ')));
  const addresses=node('dl','movio-detail-addresses');field(addresses,'Pickup',r.pickup);field(addresses,'Drop-off',r.destination);content.append(addresses);
  const facts=node('dl','movio-detail-grid');
  field(facts,'Pickup date & time',date(r.pickup_time),'movio-detail-wide');field(facts,'Vehicle',r.vehicle);field(facts,'Passengers',r.passengers);
  const money=r.fare!==null&&r.fare!==undefined&&Number.isFinite(Number(r.fare))?new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(Number(r.fare)):null;
  field(facts,'Estimated fare',r.status==='needs_location'&&Number(r.fare)===0?'Awaiting route':money);
  field(facts,'Road distance',r.distance_km!==null&&r.distance_km!==undefined&&Number.isFinite(Number(r.distance_km))?Number(r.distance_km).toFixed(1)+' kilometres':null);
  field(facts,'Booked on',date(r.created),'movio-detail-wide');field(facts,'Booked through',/voice|ai_call/i.test(r.source||'')?'AI Call':'Website');content.append(facts);
  const driver=node('section','movio-detail-section');driver.append(node('h3','','Driver details'));
  if(r.driver_id){const d=node('dl','movio-detail-grid');field(d,'Driver',r.driver_name||'Assigned driver');field(d,'Vehicle registration',r.driver_vehicle_number);
   const phone=String(r.driver_phone||'');const box=node('div','movio-detail-field');box.append(node('dt','','Phone'));
   const value=node('dd');if(/^\+?[0-9]{7,15}$/.test(phone)){const link=node('a','',phone);link.href='tel:'+phone;value.append(link);}else value.textContent=shown(phone);box.append(value);d.append(box);driver.append(d);
  }else driver.append(node('p','movio-detail-muted','A matching driver has not accepted this booking yet.'));
  content.append(driver);
  const otp=node('section','movio-detail-otp');otp.append(node('span','movio-detail-eyebrow','PICKUP OTP'));
  otp.append(node('strong','',r.pickup_otp|| (r.pickup_verified?'Verified':r.status==='scheduled'?'Available nearer pickup':'Not active')));content.append(otp);
  const w=r.weather||{};
  if(w.status==='ok'&&Array.isArray(w.points)&&w.points.length){const weather=node('details','movio-detail-section');weather.append(node('summary','','Weather recorded for your journey'));
   for(const role of ['pickup','destination']){const point=w.points.find(p=>p.location===role);if(point&&point.precipitation_probability!==null&&point.precipitation_probability!==undefined)weather.append(node('p','movio-detail-muted',(role==='pickup'?'Pickup':'Drop-off')+' · '+point.precipitation_probability+'% rain chance'));}
   content.append(weather);}
  if(r.location_share_until)content.append(node('p','movio-detail-muted','Location sharing ends: '+date(r.location_share_until)));
 }
 async function loadDetails(){
  const id=state.dialogId,seq=++state.dialogSeq;if(!id)return;
  try{const data=await request('booking/'+id);if(dialog.open&&id===state.dialogId&&seq===state.dialogSeq)renderDetails(data.booking);}
  catch(error){if(dialog.open&&id===state.dialogId&&seq===state.dialogSeq){content.replaceChildren(node('p','movio-detail-muted',error.message));}}
 }
 function closeDetails(){
  state.dialogId=null;state.dialogSeq++;clearInterval(state.dialogTimer);content.replaceChildren();
  if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');state.returnFocus?.focus();
 }
 function openDetails(id){
  id=Number(id);if(!Number.isInteger(id)||id<1||!customer())return;
  state.dialogId=id;state.returnFocus=document.activeElement;el('movioDetailsTitle').textContent='Booking #'+id;content.replaceChildren(node('p','movio-detail-muted','Loading booking details…'));
  if(!dialog.open){if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');}
  dialog.querySelector('.movio-detail-close').focus();loadDetails();clearInterval(state.dialogTimer);
  state.dialogTimer=setInterval(()=>{if(dialog.open&&!document.hidden)loadDetails();},12000);
 }
 dialog.querySelector('.movio-detail-close').onclick=closeDetails;dialog.querySelector('[data-close-details]').onclick=closeDetails;dialog.querySelector('[data-refresh-details]').onclick=loadDetails;
 dialog.addEventListener('cancel',event=>{event.preventDefault();closeDetails();});
 function bookingId(card){const heading=card?.querySelector('h3,strong,h4');const m=String(heading?.textContent||card?.textContent||'').match(/#\s*(\d+)/);return m?Number(m[1]):null;}
 function decorateBookings(){
  for(const card of document.querySelectorAll('#aiRideHistory .ride-card,#weatherScheduledRides .ride-card')){
   const id=bookingId(card);if(!id)continue;card.dataset.bookingDetailId=String(id);card.classList.add('movio-booking-clickable');
   if(card.querySelector('[data-open-booking]'))continue;
   const button=node('button','outline','Booking details');button.type='button';button.dataset.openBooking=String(id);button.setAttribute('aria-label','View booking '+id+' details');
   (card.querySelector('.movio-card-actions')||card).append(button);
  }
  if(el('riderTrip')&&!el('movioCurrentBookingDetails')){const button=node('button','outline','View full booking details');button.type='button';button.id='movioCurrentBookingDetails';button.onclick=()=>openDetails(typeof rideId!=='undefined'?rideId:null);el('riderTrip').append(button);}
 }
 document.addEventListener('click',event=>{
  const button=event.target.closest?.('[data-open-booking]');if(button){event.preventDefault();openDetails(button.dataset.openBooking);return;}
  const card=event.target.closest?.('[data-booking-detail-id]');if(card&&!event.target.closest('button,a,input,select,textarea,summary,label'))openDetails(card.dataset.bookingDetailId);
 });
 el('activeRideSelect')?.addEventListener('change',()=>{if(el('activeRideSelect').value)openDetails(el('activeRideSelect').value);});
 for(const root of [el('aiRideHistory'),el('weatherScheduledRides')].filter(Boolean))new MutationObserver(decorateBookings).observe(root,{childList:true,subtree:true});
 decorateBookings();
 window.MOVIOCustomerBookingUI={version:'customer-booking-tools-1.0',localityVersion:'main-locality-1.1',openDetails,closeDetails,searchAddress,currentPickup,pinPlace,preview,state};
 if(matches('pickup')&&matches('destination'))updateRoute();
})();
