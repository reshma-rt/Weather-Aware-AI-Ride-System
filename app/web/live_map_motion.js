
/* Show both endpoints and a live connecting line. Own GPS stays local unless sharing is already granted. */
let rideLinkLine=null,rideLinkProvider=null,viewerGPSWatch=null,viewerOwnPosition=null,ridePointHistory=new Map(),rideMarkerFrames=new Map();
function clearRideLink(){
 if(rideLinkLine){if(rideLinkProvider==='google')rideLinkLine.setMap(null);else rideLinkLine.remove()}
 rideLinkLine=null;rideLinkProvider=null;
 for(const frame of rideMarkerFrames.values())cancelAnimationFrame(frame);
 rideMarkerFrames.clear();ridePointHistory.clear();
}
const motionDestroyMap=destroyTrackingMap;
destroyTrackingMap=function(){clearRideLink();motionDestroyMap()};
const motionPreviousUpdate=movioUpdateTracking;
movioUpdateTracking=function(locations){
 const now=Date.now()/1000;
 let points=locations.filter(p=>p.expires>now).map(p=>({...p}));
 if(viewerOwnPosition&&movioMe&&viewerOwnPosition.expires>now){
  points=points.filter(p=>p.user_id!==movioMe.id);
  points.push({...viewerOwnPosition,user_id:movioMe.id,role:movioMe.role});
 }
 if(!movioTrackingOpen||!trackingMap)return;
 motionPreviousUpdate(points);
 const ids=new Set(points.map(p=>p.user_id));
 for(const id of ridePointHistory.keys())if(!ids.has(id)){
  ridePointHistory.delete(id);if(rideMarkerFrames.has(id))cancelAnimationFrame(rideMarkerFrames.get(id));rideMarkerFrames.delete(id);
 }
 for(const point of points){
  const before=ridePointHistory.get(point.user_id),marker=trackingMarkers.get(point.user_id);
  ridePointHistory.set(point.user_id,{lat:point.lat,lng:point.lng});
  if(!before||!marker||(before.lat===point.lat&&before.lng===point.lng))continue;
  if(rideMarkerFrames.has(point.user_id))cancelAnimationFrame(rideMarkerFrames.get(point.user_id));
  const epoch=trackingEpoch,start=performance.now();
  const animate=timestamp=>{
   if(epoch!==trackingEpoch||!movioTrackingOpen||trackingMarkers.get(point.user_id)!==marker)return;
   const fraction=Math.min(1,(timestamp-start)/900);
   const lat=before.lat+(point.lat-before.lat)*fraction,lng=before.lng+(point.lng-before.lng)*fraction;
   if(trackingProvider==='google')marker.position={lat,lng};else marker.setLatLng([lat,lng]);
   if(fraction<1)rideMarkerFrames.set(point.user_id,requestAnimationFrame(animate));else rideMarkerFrames.delete(point.user_id);
  };
  rideMarkerFrames.set(point.user_id,requestAnimationFrame(animate));
 }
 const driver=points.find(p=>p.role==='driver'),customer=points.find(p=>p.role==='customer');
 if(driver&&customer){
  if(rideLinkProvider!==trackingProvider){clearRideLink();rideLinkProvider=trackingProvider}
  const path=trackingProvider==='google'?[{lat:driver.lat,lng:driver.lng},{lat:customer.lat,lng:customer.lng}]:[[driver.lat,driver.lng],[customer.lat,customer.lng]];
  if(!rideLinkLine){
   if(trackingProvider==='google')rideLinkLine=new google.maps.Polyline({map:trackingMap,path,strokeColor:'#e4a900',strokeOpacity:.85,strokeWeight:4,geodesic:true});
   else rideLinkLine=L.polyline(path,{color:'#e4a900',weight:4,opacity:.85,dashArray:'8,8'}).addTo(trackingMap);
   if(trackingProvider==='google'){const bounds=new google.maps.LatLngBounds();path.forEach(p=>bounds.extend(p));trackingMap.fitBounds(bounds,60)}
   else trackingMap.fitBounds(path,{padding:[40,40],maxZoom:17});
  }else if(trackingProvider==='google')rideLinkLine.setPath(path);else rideLinkLine.setLatLngs(path);
  const metres=Math.round(distanceKm(driver,customer)*1000);
  $('trackingStatus').textContent='Driver 🚘 and customer 📍 · '+(metres<1000?metres+' m':(metres/1000).toFixed(1)+' km')+' apart · direct connecting line, not a road route';
 }else{
  if(rideLinkLine){if(rideLinkProvider==='google')rideLinkLine.setMap(null);else rideLinkLine.remove();rideLinkLine=null;rideLinkProvider=null}
  $('trackingStatus').textContent=movioMe?.role==='driver'?'Waiting for customer permission / live GPS. Customer location disappears when access ends.':'Waiting for driver live GPS. The driver must be online with location permission.';
 }
};
function stopViewerGPS(){if(viewerGPSWatch!==null)navigator.geolocation.clearWatch(viewerGPSWatch);viewerGPSWatch=null;viewerOwnPosition=null}
const motionPreviousOpen=movioOpenTracking;
movioOpenTracking=async function(id,target){
 stopViewerGPS();await motionPreviousOpen(id,target);
 if(!movioTrackingOpen||!navigator.geolocation)return;
 const epoch=trackingEpoch;
 viewerGPSWatch=navigator.geolocation.watchPosition(position=>{
  if(epoch!==trackingEpoch||!movioTrackingOpen)return;
  viewerOwnPosition={lat:position.coords.latitude,lng:position.coords.longitude,updated:Date.now()/1000,expires:Date.now()/1000+20};
  // Drawing your own position does not send it to the server.
  movioUpdateTracking(movioLocations);
 },()=>{
  viewerOwnPosition=null;movioUpdateTracking(movioLocations);
  $('trackingProvider').textContent+=' Allow GPS to show your own live position.';
 },{enableHighAccuracy:true,maximumAge:0,timeout:15000});
};
const motionPreviousClose=movioCloseTracking;
movioCloseTracking=function(){stopViewerGPS();clearRideLink();motionPreviousClose()};
$('closeTracking').onclick=movioCloseTracking;
window.addEventListener('beforeunload',stopViewerGPS);
