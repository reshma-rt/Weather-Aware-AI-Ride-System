'use strict';
const $=id=>document.getElementById(id), DEFAULT=[13.0827,80.2707];
let role='customer',pickup=null,destination=null,selecting='pickup',vehicle='Mini',km=0,minutes=0,routeLine=null,routeData=null,markers={},rideId=null,latestRide=null,driverOnline=false,shareUntil=0,watchId=null,gpsInterval=null,searchTimer=null,ttsEndpoint=localStorage.getItem('movio_tts_url')||'';
let movioBookingBusy=false;
let refreshRides=async()=>{},refreshLocations=async()=>{},renderRider=()=>{},renderDriver=()=>{};
const map=L.map('map',{zoomControl:false}).setView(DEFAULT,13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map);
L.control.zoom({position:'bottomright'}).addTo(map);
function toast(msg){$('toast').textContent=msg;$('toast').classList.remove('hidden');clearTimeout(window._toastTimer);window._toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),4200)}
async function api(path,opts={}){const r=await fetch('/api'+path,{...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});const j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j}
let post=(path,data)=>api(path,{method:'POST',body:JSON.stringify(data)});
function icon(color,label){return L.divIcon({html:`<div style="background:${color};color:white;border:3px solid white;box-shadow:0 2px 12px #0004;width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-size:17px">${label}</div>`,className:'',iconSize:[34,34],iconAnchor:[17,17]})}
function mark(key,latlng,kind){if(markers[key])markers[key].setLatLng(latlng);else markers[key]=L.marker(latlng,{icon:kind==='pickup'?icon('#20b77a','●'):kind==='destination'?icon('#f15c4e','■'):kind==='driver'?icon('#20242b','🚘'):icon('#efaf13','📍')}).addTo(map);}
function setPlace(which,place,move=true){const obj={lat:place.lat,lng:place.lng,name:place.name};if(which==='pickup'){pickup=obj;$('pickup').value=obj.name;mark('pickup',[obj.lat,obj.lng],'pickup');selecting='destination'}else{destination=obj;$('destination').value=obj.name;mark('destination',[obj.lat,obj.lng],'destination')}if(move)map.panTo([obj.lat,obj.lng]);updateRoute()}
map.on('click',e=>{if(role==='driver')return;const which=selecting;if(window.MOVIOCustomerBookingUI?.pinPlace){void window.MOVIOCustomerBookingUI.pinPlace(which,e.latlng);return;}setPlace(which,{lat:e.latlng.lat,lng:e.latlng.lng,name:`Map pin (${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)})`});toast(which==='pickup'?'Pickup pinned. Tap map again for destination.':'Destination pinned.');});
async function geocode(query){const u='https://nominatim.openstreetmap.org/search?format=json&limit=5&addressdetails=1&q='+encodeURIComponent(query);const r=await fetch(u,{headers:{'Accept-Language':'en'}});if(!r.ok)throw Error('Address search unavailable');return r.json()}

for (const id of ['pickup', 'destination']) {
    $(id).addEventListener('focus', () => selecting = id);
    $(id).addEventListener('input', () => {
        selecting = id;
        $('suggestions').replaceChildren();
    });
    $(id).addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            searchDetailedAddress();
        }
    });
}

function distanceKm(a,b){const R=6371,rad=Math.PI/180,dlat=(b.lat-a.lat)*rad,dlng=(b.lng-a.lng)*rad,h=Math.sin(dlat/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(dlng/2)**2;return 2*R*Math.asin(Math.sqrt(h))}
function fare(type){return Math.round(({'Mini':40,'Sedan':65,'SUV':95,'Auto':25,'Bike':20}[type]+km*{'Mini':14,'Sedan':20,'SUV':27,'Auto':11,'Bike':7}[type])*1.05)}
function fares(){for(const v of ['Mini','Sedan','SUV','Auto','Bike'])$('fare'+v).textContent=km?'₹'+fare(v):'—';$('bookRide').innerHTML=`Request ${vehicle} <span>→</span>`}
async function updateRoute(){if(!pickup||!destination){fares();return}if(routeLine){map.removeLayer(routeLine);routeLine=null}km=distanceKm(pickup,destination)*1.25;minutes=Math.round(km/22*60);routeData=null;try{const url=`https://router.project-osrm.org/route/v1/driving/${pickup.lng},${pickup.lat};${destination.lng},${destination.lat}?overview=full&geometries=geojson`;const r=await fetch(url);const j=await r.json();if(j.code==='Ok'&&j.routes?.length){const rt=j.routes[0];km=rt.distance/1000;minutes=Math.max(1,Math.round(rt.duration/60));routeData=rt.geometry.coordinates.map(c=>[c[1],c[0]])}}catch(e){}if(!routeData)routeData=[[pickup.lat,pickup.lng],[destination.lat,destination.lng]];routeLine=L.polyline(routeData,{color:'#15191e',weight:5,opacity:.85,dashArray:'12,8'}).addTo(map);map.fitBounds(routeLine.getBounds(),{padding:[60,65]});$('routeInfo').textContent=`${km.toFixed(1)} km · ~${minutes} min ${routeData.length===2?'(straight-line estimate)':'(road route)'} · Fares are estimates only`;fares()}
$('vehicles').addEventListener('click',e=>{const b=e.target.closest('.vehicle');if(!b)return;vehicle=b.dataset.type;document.querySelectorAll('.vehicle').forEach(el=>el.classList.toggle('active',el===b));fares()});
$('bookRide').onclick=async()=>{
 if(!pickup||!destination)return toast('Choose pickup and destination first.');
 if(movioBookingBusy)return;
 movioBookingBusy=true;$('bookRide').disabled=true;
 try{
  const j=await post('/rides',{pickup:pickup.name,destination:destination.name,plat:pickup.lat,plng:pickup.lng,dlat:destination.lat,dlng:destination.lng,vehicle,fare:fare(vehicle),request_key:crypto.randomUUID()});
  rideId=j.id;toast('Booking #'+j.id+' requested. You can create another booking.');await refreshRides();await renderVoiceHistory();
 }catch(e){toast(e.message)}
 finally{movioBookingBusy=false;$('bookRide').disabled=false}
};
$('riderMode').onclick=()=>setRole('customer');$('driverMode').onclick=()=>setRole('driver');
function setRole(r){role=r;$('riderMode').classList.toggle('selected',r==='customer');$('driverMode').classList.toggle('selected',r==='driver');$('riderPanel').classList.toggle('hidden',r!=='customer');$('driverPanel').classList.toggle('hidden',r!=='driver');setTimeout(()=>map.invalidateSize(),120);refreshRides()}
$('refreshRides').onclick=refreshRides;$('cancelRide').onclick=async()=>{if(!rideId)return;try{await post(`/rides/${rideId}/status`,{status:'cancelled'});toast('Ride cancelled');refreshRides()}catch(e){toast(e.message)}};
async function locate(){return new Promise((resolve,reject)=>{if(!navigator.geolocation)return reject(Error('Geolocation not supported'));navigator.geolocation.getCurrentPosition(p=>resolve({lat:p.coords.latitude,lng:p.coords.longitude}),reject,{enableHighAccuracy:true,timeout:12000,maximumAge:3000})})}
$('centerMap').onclick=async()=>{try{const p=await locate();map.setView([p.lat,p.lng],16);mark('me',[p.lat,p.lng],'me');if(role==='customer'&&!pickup)setPlace('pickup',{...p,name:'My current location'},false)}catch(e){toast('Location unavailable: allow GPS permission in your browser.')}};
let lastGPS=null,lastPublish=0,gpsPublishing=false,gpsEpoch=0,gpsFixPending=false;
function stopLocalGPS(actor){
 ++gpsEpoch;gpsFixPending=false;
 if(watchId!==null){navigator.geolocation.clearWatch(watchId);watchId=null}
 if(gpsInterval){clearInterval(gpsInterval);gpsInterval=null}
 lastGPS=null;
 if(markers[actor]){map.removeLayer(markers[actor]);delete markers[actor]}
 if(actor==='customer'){shareUntil=0;$('customerGPS').textContent='Stop sharing';$('customerGPS').disabled=true;$('gpsTimer').textContent='Not sharing'}
 else{driverOnline=false;$('driverGPS').textContent='Go online';$('driverGpsStatus').textContent='Offline'}
}
async function revoke(actor,scopedRide=null){
 if(actor==='customer'&&scopedRide){
  try{await post('/locations/revoke',{ride_id:scopedRide});movioGPSPaused=false;await refreshRides()}
  catch(e){movioGPSPaused=true;stopLocalGPS(actor);toast('GPS paused. Retry Stop sharing to confirm revocation.')}
  return;
 }
 if(actor==='customer')movioGPSPaused=true;
 stopLocalGPS(actor);
 try{await post('/locations/revoke',{})}catch(e){toast('Sharing stopped on this device. Server access expires automatically.');}
}

async function publish(actor,p){
 if(actor==='customer'&&Date.now()>=shareUntil){await revoke(actor);return}
 await post('/locations',{lat:p.lat,lng:p.lng});lastPublish=Date.now();
}
function startWatch(actor){
 const epoch=++gpsEpoch;
 if(watchId!==null)navigator.geolocation.clearWatch(watchId);
 if(gpsInterval)clearInterval(gpsInterval);
 const flush=async()=>{
  if(epoch!==gpsEpoch||!lastGPS||gpsPublishing)return;
  // Never republish a stale device fix. Fixed-position fresh fixes may repeat.
  if(Date.now()-lastGPS.at>20000)return;
  gpsPublishing=true;
  try{await publish(actor,lastGPS)}catch(e){
   if(/inactive|expired|Log in/.test(e.message))stopLocalGPS(actor);
   else console.warn('GPS update failed',e);
  }finally{gpsPublishing=false}
 };
 const receive=p=>{
  if(epoch!==gpsEpoch)return;
  lastGPS={lat:p.coords.latitude,lng:p.coords.longitude,at:p.timestamp||Date.now()};
  mark(actor,[lastGPS.lat,lastGPS.lng],actor==='driver'?'driver':'me');flush();
 };
 const gpsError=async e=>{if(epoch!==gpsEpoch)return;toast('GPS error: '+e.message);if(e.code===1){await revoke(actor);await refreshRides()}};
 watchId=navigator.geolocation.watchPosition(receive,gpsError,{enableHighAccuracy:true,maximumAge:0,timeout:15000});
 gpsInterval=setInterval(()=>{
  if(actor==='customer'){
   const left=Math.max(0,Math.ceil((shareUntil-Date.now())/1000));const selectedLeft=Math.max(0,Math.ceil(((movioCustomerGrants.get(rideId)||0)-Date.now())/1000));$('gpsTimer').textContent=selectedLeft?`${Math.floor(selectedLeft/60)}:${String(selectedLeft%60).padStart(2,'0')} remaining for #${rideId}`:left?'Sharing for another booking':'Expired';
   if(!left){revoke(actor);refreshLocations();return}
  }else $('driverGpsStatus').textContent=lastGPS&&Date.now()-lastGPS.at<=20000?'Online · GPS sharing':'Waiting for fresh GPS';
  if(Date.now()-lastPublish>=5000&&!gpsFixPending){
   gpsFixPending=true;
   navigator.geolocation.getCurrentPosition(p=>{if(epoch!==gpsEpoch)return;gpsFixPending=false;receive(p)},e=>{if(epoch!==gpsEpoch)return;gpsFixPending=false;gpsError(e)},{enableHighAccuracy:true,maximumAge:0,timeout:15000});
  }
 },1000);
}
$('customerGPS').onclick=()=>toast('Wait for your assigned driver to request location access.');
$('driverGPS').onclick=async()=>{
 if(driverOnline){await revoke('driver');toast('Driver GPS stopped.');return}
 try{const p=await locate();await publish('driver',p);driverOnline=true;$('driverGPS').textContent='Go offline';startWatch('driver');toast('Driver location sharing started.')}
 catch(e){toast('GPS permission required: '+e.message)}
};
$('shareToggle').onclick=()=>role==='customer'?$('customerGPS').click():$('driverGPS').click();
function speak(text){const lang=$('language').value;if(ttsEndpoint){fetch(ttsEndpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,language:lang})}).then(async r=>{if(!r.ok)throw Error('TTS API returned '+r.status);const blob=await r.blob();if(!blob.type.startsWith('audio/'))throw Error('TTS API did not return audio');const url=URL.createObjectURL(blob);const audio=new Audio(url);audio.onended=()=>URL.revokeObjectURL(url);await audio.play()}).catch(e=>{toast(e.message+' — using browser speech');browserSpeak(text,lang)})}else browserSpeak(text,lang)}
function browserSpeak(text,lang){if(!('speechSynthesis' in window))return toast('Speech playback not supported in this browser.');speechSynthesis.cancel();const utter=new SpeechSynthesisUtterance(text);utter.lang=lang;utter.rate=.95;speechSynthesis.speak(utter)}
$('readHelp').onclick=()=>speak('Welcome to AI call booking service. Choose a pickup and destination, select your ride, and request a driver.');$('speakStatus').onclick=()=>speak(latestRide?`Your ${latestRide.vehicle} ride is ${latestRide.status.replace('_',' ')}. Fare estimate ${latestRide.fare} rupees.`:'No active ride.');
$('voiceBook').onclick=()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR)return toast('Speech recognition unavailable. Use Chrome or type destination.');const rec=new SR();rec.lang=$('language').value;rec.interimResults=false;rec.onresult=e=>{const txt=e.results[0][0].transcript;$('destination').value=txt;selecting='destination';$('destination').dispatchEvent(new Event('input'));toast('Heard: '+txt+'. Choose an address suggestion to confirm.')};rec.onerror=e=>toast('Voice input error: '+e.error);rec.start();toast('Listening… say your destination')};
$('apiSettings').onclick=()=>{$('ttsUrl').value=ttsEndpoint;$('modal').classList.remove('hidden')};$('closeModal').onclick=()=>$('modal').classList.add('hidden');$('saveApi').onclick=()=>{const url=$('ttsUrl').value.trim();if(url&&!/^https:\/\//.test(url))return toast('Use an HTTPS URL for remote TTS.');ttsEndpoint=url;localStorage.setItem('movio_tts_url',url);$('modal').classList.add('hidden');toast('TTS endpoint saved. It will be tested on first playback.')};$('clearApi').onclick=()=>{ttsEndpoint='';localStorage.removeItem('movio_tts_url');$('modal').classList.add('hidden');toast('Using browser speech.')};$('help').onclick=()=>toast('Tap map for pickup and destination, or search addresses. Driver mode is available in a second tab.');
// Location consent is restored from the server only, with the original expiry.
fares();refreshRides();refreshLocations();setInterval(()=>{refreshRides();refreshLocations()},3500);setTimeout(()=>map.invalidateSize(),500);

// Authenticated cross-origin bridge: credentials remain on the local app origin.
// The Colab popup never receives login cookies, passwords or session tokens.
let aiPopup=null,aiOrigin=null,aiNonce=null;
async function voiceRides(){const data=await api('/rides');return data.rides.filter(r=>['requested','accepted','arriving','in_progress','needs_location'].includes(r.status));}
const movioVoiceChannel=('BroadcastChannel' in window)?new BroadcastChannel('movio-ai-booking'):null;
function sendVoice(type,extra={}){const msg={channel:'ai-ride-call',nonce:aiNonce,type,...extra};if(aiPopup&&!aiPopup.closed&&aiOrigin&&aiNonce)aiPopup.postMessage(msg,aiOrigin);if(movioVoiceChannel&&aiNonce)movioVoiceChannel.postMessage(msg)}
async function renderVoiceHistory(){
 const root=$('aiRideHistory');if(!root)return;
 try{const {rides}=await api('/rides');root.replaceChildren();
  if(!rides.length){root.textContent='No bookings yet.';return}
  rides.forEach(r=>{const item=document.createElement('div');item.className='ride-card';
   const h=document.createElement('strong');h.textContent=`#${r.id} · ${r.vehicle} · ${r.status.toUpperCase()}`;item.append(h);
   const p=document.createElement('p');p.textContent=`${r.pickup} → ${r.destination} · ₹${r.fare} (estimate) · ${r.source}`;item.append(p);
   if(['scheduled','requested','accepted','arriving','needs_location'].includes(r.status)){
    const b=document.createElement('button');b.className='secondary';b.textContent='Cancel #'+r.id;
    b.onclick=async()=>{try{await post(`/rides/${r.id}/status`,{status:'cancelled'});await renderVoiceHistory();refreshRides()}catch(e){toast(e.message)}};item.append(b)}
   if(['requested','accepted','arriving','in_progress','needs_location'].includes(r.status)){const view=document.createElement('button');view.type='button';view.className='outline';view.textContent='View / track booking #'+r.id;view.onclick=()=>movioSelectBooking(r.id);item.append(view)}
   root.append(item)})
 }catch(e){root.textContent='Sign in to view your bookings.'}
}
async function handleMovioVoiceMessage(m){
 if(!m||m.channel!=='ai-ride-call'||m.nonce!==aiNonce)return;
 if(m.type==='hello'||m.type==='get_rides'){
  try{sendVoice(m.type==='hello'?'ready':'rides',{rides:await voiceRides()})}
  catch(err){sendVoice('rides',{rides:[]});toast(err.message)}return;
 }
 if(m.type!=='action')return;
 const a=m.action||{};
 try{
  if(a.type==='book'){
   const d=a.details||{},p=d.pickup_geo,q=d.destination_geo;
   if(!p||!q||!d.fare||!Number.isFinite(d.fare.fare))throw Error('Verified route required before booking');
   if(!['Bike','Auto','Mini','Sedan','SUV'].includes(d.vehicle))throw Error('Invalid vehicle');
   const j=await post('/rides',{customer:'Customer',pickup:d.pickup,destination:d.destination,
    plat:p.lat,plng:p.lng,dlat:q.lat,dlng:q.lng,vehicle:d.vehicle,fare:d.fare.fare,
    pickup_time:d.when,passengers:d.count,request_key:a.request_id||crypto.randomUUID()});
   sendVoice('result',{ok:true,id:j.id});toast('Ride request #'+j.id+' created');
  }else if(a.type==='cancel'){
   const id=Number(a.ride_id),rides=await voiceRides();
   if(!rides.some(r=>r.id===id))throw Error('Booking is not active or does not belong to this account');
   await post(`/rides/${id}/status`,{status:'cancelled'});
   sendVoice('result',{ok:true,id});toast('Booking #'+id+' cancelled');
  }else throw Error('Unsupported voice action');
 }catch(err){sendVoice('result',{ok:false,error:err.message});toast(err.message)}
 await renderVoiceHistory();await refreshRides();sendVoice('rides',{rides:await voiceRides().catch(()=>[])})
}
window.addEventListener('message',e=>{if(!aiPopup||e.source!==aiPopup||e.origin!==aiOrigin)return;handleMovioVoiceMessage(e.data)});
if(movioVoiceChannel)movioVoiceChannel.onmessage=e=>handleMovioVoiceMessage(e.data);
$('aiCall').onclick=async()=>{
 try{
  await api('/me'); // Login is required before starting a call.
  const cfg=await api('/browser-voice-config');
  if(!cfg.url)throw Error('Set MOVIO_AI_BRIDGE_URL to the active Colab tunnel and restart local server.');
  const u=new URL(cfg.url);if(u.protocol!=='https:')throw Error('HTTPS bridge required');
  aiOrigin=u.origin;aiNonce=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
  u.hash=aiNonce;
  aiPopup=window.open(u.toString(),'ai_booking_call');
  if(!aiPopup)throw Error('Allow pop-ups for this website');
  await renderVoiceHistory();
 }catch(err){toast(err.message)}
};
renderVoiceHistory();setInterval(renderVoiceHistory,12000);

// Detailed address selection.
const addressCache = new Map();
let addressSearchBusy = false;

async function searchDetailedAddress() {
    if (addressSearchBusy) return;
    const field = selecting === 'destination'
        ? 'destination' : 'pickup';
    const typed = $(field).value.trim();
    if (typed.length < 3) {
        toast('Enter a street, area or landmark first.');
        return;
    }

    addressSearchBusy = true;
    $('searchAddress').disabled = true;
    $('suggestions').textContent = 'Searching…';

    try {
        const query = /chennai/i.test(typed)
            ? typed : typed + ', Chennai, Tamil Nadu';

        let places = addressCache.get(query);
        if (!places) {
            const params = new URLSearchParams({
                format: 'json',
                limit: '6',
                addressdetails: '1',
                countrycodes: 'in',
                viewbox: '79.95,13.35,80.45,12.65',
                bounded: '1',
                q: query
            });

            const response = await fetch(
                'https://nominatim.openstreetmap.org/search?' + params,
                {headers: {'Accept-Language': 'en'}}
            );
            if (!response.ok) throw Error('Address search unavailable');
            places = await response.json();
            addressCache.set(query, places);
        }

        $('suggestions').replaceChildren();
        for (const place of places) {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = place.display_name;
            button.onclick = () => {
                setPlace(field, {
                    lat: Number(place.lat),
                    lng: Number(place.lon),
                    name: place.display_name
                });
                $('suggestions').replaceChildren();
                toast('Check the map pin for the exact entrance.');
            };
            $('suggestions').append(button);
        }

        if (!places.length) {
            $('suggestions').textContent =
                'Address not found. Try street + area + postcode, ' +
                'or use current location / select an exact map point.';
        }
    } catch (error) {
        $('suggestions').textContent =
            error.message + '. You can still select a point on the map.';
    } finally {
        addressSearchBusy = false;
        // Limit consecutive searches.
        setTimeout(() => {
            $('searchAddress').disabled = false;
        }, 1100);
    }
}

$('searchAddress').onclick = searchDetailedAddress;

$('useCurrentPickup').onclick = async () => {
    const button = $('useCurrentPickup');
    button.disabled = true;
    try {
        const position = await locate();
        setPlace('pickup', {
            ...position,
            name: 'Current pickup location'
        }, false);
        map.setView([position.lat, position.lng], 18);
        toast('Pickup set. Check the pin before booking.');
    } catch (error) {
        toast('Allow location permission and enable phone GPS, ' +
              'or select your pickup on the map.');
    } finally {
        button.disabled = false;
    }
};

$('pinPickup').onclick = () => {
    selecting = 'pickup';
    $('pickup').focus();
    toast('Tap your exact pickup or building entrance on the map.');
};

$('pinDestination').onclick = () => {
    selecting = 'destination';
    $('destination').focus();
    toast('Tap your exact destination entrance on the map.');
};
