
/* Driver dashboard: assigned trip first, then matching incoming requests. */
const driverDashboardPreviousRender=renderDriver;
function driverUIElement(tag,cls,text){const node=document.createElement(tag);node.className=cls;if(text!==undefined)node.textContent=text;return node}
function installDriverDashboard(){
 const panel=$('driverPanel');panel.classList.add('driver-dashboard-panel');
 const heading=panel.querySelector('.sheet-head h1');if(heading)heading.textContent='Your driving day';
 const subtitle=panel.querySelector('.sheet-head .muted');if(subtitle)subtitle.textContent='Your assigned trip and matching requests, in one place.';
 const profile=$('driverProfile');profile.classList.add('driver-dashboard-profile');
 if(!$('driverDashboardCounts')){const counts=driverUIElement('div','driver-dashboard-counts');counts.id='driverDashboardCounts';profile.after(counts)}
 const gps=$('driverGPS').closest('.gps-card');if(gps)gps.classList.add('driver-online-card');
 const title=panel.querySelector('.section-row h2');if(title)title.textContent='Trips & requests';
}
renderDriver=function(rides){
 installDriverDashboard();
 const sorted=[...rides].sort((a,b)=>Number(movioActive(b))-Number(movioActive(a))||b.id-a.id);
 driverDashboardPreviousRender(sorted);
 const assigned=sorted.find(r=>r.driver_id===movioMe?.id&&movioActive(r));
 const incoming=sorted.filter(r=>r.status==='requested');
 const counts=$('driverDashboardCounts');counts.replaceChildren();
 for(const [value,label] of [[assigned?'1':'0','Active trip'],[String(incoming.length),'Matching requests']]){
  const tile=driverUIElement('div','driver-count-tile');tile.append(driverUIElement('strong','',value),driverUIElement('span','',label));counts.append(tile)
 }
 const holder=$('driverRides');
 for(const card of [...holder.children]){
  const heading=card.querySelector('h3');if(!heading)continue;
  const id=Number(heading.textContent.match(/^#(\d+)/)?.[1]);const ride=sorted.find(r=>r.id===id);if(!ride)continue;
  card.classList.add('driver-trip-card');card.dataset.stage=ride.status;
  const badge=driverUIElement('span','driver-trip-badge',ride.status==='requested'?'NEW REQUEST':ride.status==='accepted'?'ACCEPTED':ride.status==='arriving'?'ON THE WAY':'RIDE IN PROGRESS');
  const top=driverUIElement('div','driver-trip-top');top.append(badge,driverUIElement('span','driver-trip-id','Booking #'+ride.id));card.insertBefore(top,heading);
  heading.textContent=ride.vehicle+' · ₹'+ride.fare;
  const route=driverUIElement('div','driver-route');
  for(const [label,name,cls] of [['PICKUP',ride.pickup,'pickup'],['DROP-OFF',ride.destination,'dropoff']]){
   const row=driverUIElement('div','driver-route-row '+cls);const dot=driverUIElement('span','driver-route-dot');const text=driverUIElement('div','');text.append(driverUIElement('small','',label),driverUIElement('p','',name));row.append(dot,text);route.append(row)
  }
  const customer=driverUIElement('div','driver-customer');customer.append(driverUIElement('span','customer-avatar',(ride.customer_name||'C').slice(0,1).toUpperCase()),driverUIElement('strong','',ride.customer_name||'Customer'));
  for(const paragraph of [...card.children].filter(n=>n.tagName==='P')){
   if(/^(Customer:|Pickup:|Destination:|Status:)/.test(paragraph.textContent))paragraph.remove();
  }
  heading.after(customer);customer.after(route);
  const otp=card.querySelector('.driver-otp-label');if(otp){otp.classList.add('driver-otp-panel');const hint=driverUIElement('small','','Ask the customer for their 4-digit code at pickup.');otp.append(hint)}
  const actions=card.querySelector('.actions');if(actions){
   actions.classList.add('driver-trip-actions');
   for(const button of actions.querySelectorAll('button')){
    const label=button.textContent;
    if(label==='Start ride')button.textContent='Verify OTP & start ride';
    if(label==='Accept')button.textContent='Accept request';
    if(label==='Cancel request')button.textContent='Decline request';
    if(label==='View Customer location')button.textContent='View customer on map';
    if(label==='Request customer location')button.textContent='Request 15-min location access';
    if(label.includes('location')||label==='Location request sent')button.classList.add('driver-location-action');
   }
  }
 }
 if(!assigned&&!incoming.length){
  holder.replaceChildren();const empty=driverUIElement('div','driver-empty');empty.append(driverUIElement('span','','↗'),driverUIElement('h3','','Ready for your next ride'),driverUIElement('p','','Matching '+(movioMe?.vehicle_type||'vehicle')+' requests will appear here.'));holder.append(empty)
 }
};
installDriverDashboard();
if(movioMe?.role==='driver')refreshRides();
