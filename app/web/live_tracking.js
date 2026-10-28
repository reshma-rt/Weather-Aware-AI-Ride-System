/* Google Maps shows live, authorized coordinates; Leaflet is the no-key fallback. */
let trackingMap=null,trackingProvider=null,trackingMarkers=new Map(),trackingFit=true;
let googleReady=null,trackingTarget='driver',trackingEpoch=0;
function googleMapsReady(key){
 if(window.google?.maps?.importLibrary)return Promise.resolve();
 if(googleReady)return googleReady;
 googleReady=new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('Google Maps timed out')),18000);
  window.movioGoogleReady=()=>{clearTimeout(timer);resolve()};
  window.gm_authFailure=()=>{clearTimeout(timer);reject(Error('Google Maps key or billing is unavailable'));if(movioTrackingOpen)movioTrackingFallback('Google Maps unavailable; using the live OpenStreetMap.')};
  const script=document.createElement('script');const query=new URLSearchParams({key,v:'weekly',loading:'async',libraries:'maps,marker',callback:'movioGoogleReady'});
  script.src='https://maps.googleapis.com/maps/api/js?'+query.toString();script.async=true;
  script.onerror=()=>{clearTimeout(timer);reject(Error('Google Maps could not load'))};document.head.append(script);
 });
 return googleReady;
}
function destroyTrackingMap(){
 for(const marker of trackingMarkers.values()){if(trackingProvider==='google')marker.map=null;else marker.remove()}
 trackingMarkers.clear();if(trackingProvider==='leaflet'&&trackingMap)trackingMap.remove();
 trackingMap=null;trackingProvider=null;$('trackingMap').replaceChildren();
}
function movioTrackingFallback(reason){
 destroyTrackingMap();trackingProvider='leaflet';trackingFit=true;
 trackingMap=L.map('trackingMap').setView(DEFAULT,13);
 L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(trackingMap);
 $('trackingProvider').textContent=reason||'Live OpenStreetMap. Configure the Google Maps key in the deployment notebook to use Google Maps.';
 movioUpdateTracking(movioLocations);
}
async function movioOpenTracking(id,target){
 if(!id)return;movioSelectedRide=id;trackingTarget=target;movioTrackingOpen=true;trackingFit=true;
 const epoch=++trackingEpoch;
 $('trackingTitle').textContent=target==='driver'?'Track driver · Live ride map':'View Customer location · Live ride map';
 $('trackingDialog').classList.remove('hidden');$('closeTracking').focus();$('trackingStatus').textContent='Loading live locations…';
 try{
  const cfg=await api('/maps-config');if(epoch!==trackingEpoch)return;
  if(!cfg.key){movioTrackingFallback();await refreshLocations();return}
  await googleMapsReady(cfg.key);
  const {Map}=await google.maps.importLibrary('maps');await google.maps.importLibrary('marker');
  if(epoch!==trackingEpoch)return;
  destroyTrackingMap();trackingProvider='google';
  trackingMap=new Map($('trackingMap'),{center:{lat:DEFAULT[0],lng:DEFAULT[1]},zoom:13,mapId:cfg.map_id||'DEMO_MAP_ID',streetViewControl:false,mapTypeControl:false});
  $('trackingProvider').textContent='Google Maps · Live positions from the assigned ride';
  await refreshLocations();
 }catch(e){if(epoch!==trackingEpoch)return;movioTrackingFallback('Google Maps unavailable; live OpenStreetMap is shown. '+e.message);await refreshLocations()}
}
function movioUpdateTracking(locations){
 if(!movioTrackingOpen||!trackingMap)return;
 const now=Date.now()/1000;const points=locations.filter(p=>p.expires>now);
 const liveIds=new Set(points.map(p=>p.user_id));
 for(const [id,marker] of trackingMarkers){if(!liveIds.has(id)){if(trackingProvider==='google')marker.map=null;else marker.remove();trackingMarkers.delete(id)}}
 for(const p of points){
  const label=`${p.role==='driver'?'Driver':'Customer'}${p.user_id===movioMe.id?' (you)':''}`;
  let marker=trackingMarkers.get(p.user_id);
  if(trackingProvider==='google'){
   const pos={lat:p.lat,lng:p.lng};
   if(!marker){const content=document.createElement('div');content.textContent=p.role==='driver'?'🚘':'📍';content.style.cssText='font-size:30px;background:white;border-radius:50%;padding:4px;box-shadow:0 2px 8px #0004';
    marker=new google.maps.marker.AdvancedMarkerElement({map:trackingMap,position:pos,title:label,content});trackingMarkers.set(p.user_id,marker);
   }else marker.position=pos;
  }else{
   if(!marker){marker=L.marker([p.lat,p.lng],{icon:icon(p.role==='driver'?'#20242b':'#efaf13',p.role==='driver'?'🚘':'📍')}).addTo(trackingMap).bindTooltip(label);trackingMarkers.set(p.user_id,marker)}
   else marker.setLatLng([p.lat,p.lng]);
  }
 }
 const target=points.find(p=>p.role===trackingTarget&&p.user_id!==movioMe.id);
 $('trackingStatus').textContent=target?`Live ${trackingTarget} position · updated ${Math.max(0,Math.round(now-target.updated))}s ago`:`Waiting for ${trackingTarget} GPS, or location access has stopped.`;
 if(points.length&&trackingFit){
  if(trackingProvider==='google'){
   const bounds=new google.maps.LatLngBounds();for(const p of points)bounds.extend({lat:p.lat,lng:p.lng});
   if(points.length===1){trackingMap.setCenter({lat:points[0].lat,lng:points[0].lng});trackingMap.setZoom(16)}else trackingMap.fitBounds(bounds,60);
  }else{trackingMap.invalidateSize();if(points.length===1)trackingMap.setView([points[0].lat,points[0].lng],16);else trackingMap.fitBounds(points.map(p=>[p.lat,p.lng]),{padding:[35,35],maxZoom:16})}
  trackingFit=false;
 }
}
function movioCloseTracking(){movioTrackingOpen=false;++trackingEpoch;$('trackingDialog').classList.add('hidden');destroyTrackingMap()}
$('closeTracking').onclick=movioCloseTracking;
// Modal keyboard navigation, including consent: Escape never grants access.
document.addEventListener('keydown',e=>{
 const modal=Array.from(document.querySelectorAll('.modal:not(.hidden)')).pop();if(!modal)return;
 if(e.key==='Escape'&&modal.id==='trackingDialog'){movioCloseTracking();return}
 if(e.key!=='Tab')return;
 const focusable=Array.from(modal.querySelectorAll('button,input,select,a[href]')).filter(el=>!el.disabled&&el.offsetParent!==null);
 if(!focusable.length)return;const first=focusable[0],last=focusable.at(-1);
 if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
 else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
});
