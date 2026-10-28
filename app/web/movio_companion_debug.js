(function(){
 var box=document.createElement('div');
 box.style.cssText='position:fixed;left:0;right:0;bottom:0;z-index:99999;background:#111;color:#9f9;font:11px/1.35 monospace;padding:4px 8px;white-space:pre-wrap;word-break:break-all;max-height:30vh;overflow:auto';
 box.textContent='companion debug: waiting for the card to load...';
 document.addEventListener('DOMContentLoaded',function(){document.body.appendChild(box);});
 if(document.body)document.body.appendChild(box);
 var f=window.fetch;
 window.fetch=function(u,o){
  var url=String(u&&u.url||u),p=f.apply(this,arguments);
  if(url.indexOf('/api/customer-care/recommend')>-1){
   var sent='';try{var b=JSON.parse(o&&o.body||'{}');var l=b.context&&b.context.current_location||{};
    sent=('lat' in l)?'location SENT ('+l.lat+','+l.lng+')':'location NOT sent, status='+l.status;}catch(e){}
   p.then(function(r){return r.clone().json().then(function(j){
    var w=j.weather||{};
    box.textContent='companion debug: HTTP '+r.status+' | backend '+(j.version||'?')+' | weather.status='+(w.status||'none')+(w.reason?(' reason='+w.reason):'')+' | '+sent+(j.error?(' | error='+j.error):'');
   });}).catch(function(e){box.textContent='companion debug: request failed '+e;});
  }
  return p;
 };
})();
