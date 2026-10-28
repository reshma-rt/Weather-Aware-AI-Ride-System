/* Weather review in the existing manual booking form. No autonomous edits. */
(function installManualWeather(){
 'use strict';
 if(window.__weatherManualVersion==='0.3.0')return;
 const book=document.getElementById('bookRide');
 if(!book||typeof api!=='function'||typeof fare!=='function')return;
 window.__weatherManualVersion='0.3.0';book.type='button';
 // MOVIO_CUSTOMER_UI_V1
 const section=document.createElement('section');section.id='weatherManual';section.className='ride-card';
 section.innerHTML=`<h3 class="wx-form-heading" id="wxFormHeading"></h3>
<div class="wx-field-grid">
 <label class="wx-field" for="wxManualLanguage"><span id="wxLanguageLabel"></span><select id="wxManualLanguage"><option value="Tamil">தமிழ்</option><option value="Tanglish">Tanglish</option><option value="English">English</option></select></label>
 <label class="wx-field" for="wxManualCount"><span id="wxCountLabel"></span><select id="wxManualCount"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option></select></label>
</div>
<fieldset class="wx-schedule"><legend id="wxDateLabel"></legend>
 <div class="wx-day-shortcuts"><button type="button" id="wxToday" aria-pressed="false"></button><button type="button" id="wxTomorrow" aria-pressed="false"></button></div>
 <div class="wx-field-grid">
  <label class="wx-field" for="wxPickupDay"><span id="wxDayLabel"></span><input id="wxPickupDay" type="date" required></label>
  <label class="wx-field" for="wxPickupTime"><span id="wxTimeLabel"></span><input id="wxPickupTime" type="time" step="60" required></label>
 </div>
 <input id="wxManualDate" type="datetime-local" hidden tabindex="-1" aria-hidden="true">
</fieldset>
<div id="wxPreviewAction"></div>
<p id="wxManualStatus" role="status" aria-live="polite"></p>
<div id="wxManualReview" hidden>
 <div class="wx-review-panel">
  <div class="wx-review-head"><h3 id="wxWeatherTitle"></h3><span id="wxCondition" class="wx-condition"></span></div>
  <p class="wx-rain-label" id="wxRainLabel"></p>
  <div class="wx-weather-points">
   <div class="wx-point"><span class="wx-point-label" id="wxPickupLabel"></span><span class="wx-place" id="wxPickupName"></span><strong class="wx-probability" id="wxPickupRain"></strong></div>
   <div class="wx-point"><span class="wx-point-label" id="wxDropLabel"></span><span class="wx-place" id="wxDropName"></span><strong class="wx-probability" id="wxDropRain"></strong></div>
  </div>
  <p class="wx-tip" id="wxShortAdvice"></p>
  <div class="wx-trip-panel">
   <div class="wx-route-row" hidden><span id="wxTripPickupLabel"></span><strong class="wx-place" id="wxTripPickup"></strong></div>
   <div class="wx-route-row" hidden><span id="wxTripDropLabel"></span><strong class="wx-place" id="wxTripDrop"></strong></div>
   <p class="wx-trip-date" id="wxTripDate"></p>
   <div class="wx-trip-facts" id="wxTripFacts"></div>
  </div>
  <details class="wx-details"><summary id="wxFullDetailsLabel"></summary><p id="wxManualAdvice"></p><p id="wxManualSummary"></p></details>
  <div class="wx-review-actions"><button type="button" id="wxManualContinue"></button><button type="button" id="wxManualChange" class="secondary"></button></div>
  <p class="wx-source"><span id="wxForecastScope"></span><a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a></p>
 </div>
</div>
`;
 const bookingActions=book.closest('.actions')||book.parentElement;
 bookingActions.parentNode.insertBefore(section,bookingActions);
 section.querySelector('#wxPreviewAction').append(book);
 const el=id=>document.getElementById(id),langBox=el('wxManualLanguage'),dateBox=el('wxManualDate'),countBox=el('wxManualCount');
 const messages={English:{language:'Language',date:'Booking date and time',count:'Passengers',review:'Check weather and review booking',title:'Weather for your selected journey',continue:'Continue with this booking',change:'Change my details',loading:'Checking the weather for your selected journey…',saving:'Saving your booking…',ready:'Review the advice and booking details, then choose whether to continue.',changed:'Your details changed. Please review the latest weather and booking details.',locations:'Choose pickup and destination from the map or address suggestions.',time:'Please choose your booking date and time.',failed:'The request could not be completed. Please try again.',unknown:'The booking result could not be verified. Retry here to check the same booking, or check your booking list.',retry:'Check this booking again'},
 Tamil:{language:'மொழி',date:'பயணத்தின் தேதி மற்றும் நேரம்',count:'பயணிகளின் எண்ணிக்கை',review:'வானிலையையும் முன்பதிவையும் சரிபார்',title:'உங்கள் பயணத்திற்கான வானிலை',continue:'இந்த முன்பதிவைத் தொடரவும்',change:'விவரங்களை மாற்று',loading:'உங்கள் பயணத்திற்கான வானிலையைச் சரிபார்க்கிறோம்…',saving:'உங்கள் முன்பதிவைச் சேமிக்கிறோம்…',ready:'வானிலை மற்றும் முன்பதிவு விவரங்களைப் பார்த்துவிட்டுத் தொடர விரும்புகிறீர்களா என்பதைத் தேர்ந்தெடுக்கவும்.',changed:'உங்கள் விவரங்கள் மாறியுள்ளன. புதிய வானிலை மற்றும் முன்பதிவு விவரங்களை மீண்டும் சரிபார்க்கவும்.',locations:'புறப்படும் இடத்தையும் சேரும் இடத்தையும் வரைபடம் அல்லது முகவரி பரிந்துரைகளிலிருந்து தேர்ந்தெடுக்கவும்.',time:'பயணத்தின் தேதி மற்றும் நேரத்தைத் தேர்ந்தெடுக்கவும்.',failed:'கோரிக்கையை நிறைவு செய்ய முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',unknown:'முன்பதிவின் முடிவைச் சரிபார்க்க முடியவில்லை. இதே முன்பதிவை மீண்டும் சரிபார்க்கவும் அல்லது உங்கள் முன்பதிவுப் பட்டியலைப் பாருங்கள்.',retry:'இதே முன்பதிவை மீண்டும் சரிபார்'},
 Tanglish:{language:'Mozhi',date:'Payanathin thedhi matrum neram',count:'Payanigalin ennikkai',review:'Vaanilaiyaiyum munpadhivaiyum saripaar',title:'Unga payanathirkaana vaanilai',continue:'Indha munpadhivai thodaravum',change:'Vivarangalai maatru',loading:'Unga payanathirkaana vaanilaiyai saripaarkkirom…',saving:'Unga munpadhivai semikkirom…',ready:'Vaanilai matrum munpadhivu vivarangalai paarthuvittu thodara virumbureengalaa enbadhai therndhedukkavum.',changed:'Unga vivarangal maariyullana. Pudhiya vaanilai matrum munpadhivu vivarangalai meendum saripaarunga.',locations:'Purappadum idathaiyum serum idathaiyum varaipadam alladhu mugavari parindhuraigalilirundhu therndhedukkavum.',time:'Payanathin thedhi matrum nerathai therndhedukkavum.',failed:'Korikkaiyai niraivu seiyya mudiyavillai. Meendum muyarchikkavum.',unknown:'Munpadhivin mudivai saripaarkka mudiyavillai. Idhe munpadhivai meendum saripaarunga alladhu unga munpadhivu pattiyalai paarunga.',retry:'Idhe munpadhivai meendum saripaar'}};
 // MOVIO_CUSTOMER_UI_V1: presentation helpers; no booking/API/voice replacement.
 const uiMessages={
  English:{heading:'Plan your ride',language:'Language',count:'Passengers',date:'Pickup schedule',review:'Review ride',title:'Journey weather',continue:'Confirm booking',change:'Edit details',loading:'Checking weather…',ready:'Review your ride, then confirm.',changed:'Details changed. Review again.',today:'Today',tomorrow:'Tomorrow',day:'Date',timeLabel:'Time',rain:'Chance of rain',pickup:'Pickup',drop:'Drop-off',details:'Full details',scope:'At pickup time ·',passengers:'Passengers',vehicle:'Vehicle',distance:'Road distance',fare:'Estimated fare',missing:'Unavailable',forecast:'Forecast ready',rainy:'Rain expected',heavy:'Heavy rain',storm:'Thunderstorms',cloudy:'Cloudy',clear:'Clear skies',heat:'High heat',unavailable:'Forecast unavailable',notYet:'Forecast not yet available',canContinue:'You can still book this ride.',bikeTip:'Consider a covered car. The choice is yours.',severeBike:'Bike travel may be unsuitable. Consider a covered car.',rainTip:'Carry an umbrella for pickup and drop-off.',autoTip:'Protect yourself and your bags from side rain.',heatTip:'Carry water and prepare for high temperatures.',ai:'Book by AI call'},
  Tamil:{heading:'உங்கள் பயணம்',language:'மொழி',count:'பயணிகள்',date:'புறப்படும் தேதி, நேரம்',review:'பயணத்தைச் சரிபார்',title:'பயண வானிலை',continue:'முன்பதிவை உறுதிசெய்',change:'விவரங்களை மாற்று',loading:'வானிலையைச் சரிபார்க்கிறோம்…',ready:'விவரங்களைப் பார்த்து உறுதிசெய்யவும்.',changed:'விவரங்கள் மாறியுள்ளன. மீண்டும் சரிபார்க்கவும்.',today:'இன்று',tomorrow:'நாளை',day:'தேதி',timeLabel:'நேரம்',rain:'மழைக்கான வாய்ப்பு',pickup:'புறப்படும் இடம்',drop:'சேரும் இடம்',details:'முழு விவரங்கள்',scope:'புறப்படும் நேரத்தில் ·',passengers:'பயணிகள்',vehicle:'வாகனம்',distance:'சாலை தூரம்',fare:'கட்டண மதிப்பீடு',missing:'கிடைக்கவில்லை',forecast:'வானிலை தகவல்',rainy:'மழை எதிர்பார்ப்பு',heavy:'கனமழை',storm:'இடியுடன் மழை',cloudy:'மேகமூட்டம்',clear:'தெளிவான வானம்',heat:'அதிக வெப்பம்',unavailable:'வானிலை கிடைக்கவில்லை',notYet:'இந்தத் தேதிக்கு வானிலை இன்னும் கிடைக்கவில்லை',canContinue:'முன்பதிவைத் தொடரலாம்.',bikeTip:'மூடிய காரைத் தேர்வு செய்யலாம். முடிவு உங்களுடையது.',severeBike:'பைக் பயணம் பொருத்தமில்லாமல் இருக்கலாம். மூடிய காரைப் பரிசீலிக்கவும்.',rainTip:'ஏறும்போதும் இறங்கும்போதும் பயன்படுத்தக் குடை எடுத்துக்கொள்ளவும்.',autoTip:'பக்கவாட்டு மழையிலிருந்து உங்களையும் உடைமைகளையும் பாதுகாக்கவும்.',heatTip:'குடிநீர் எடுத்துக்கொண்டு வெப்பத்திற்கு ஏற்ற முன்னேற்பாடுகளைச் செய்யவும்.',ai:'AI அழைப்பு மூலம் முன்பதிவு'},
  Tanglish:{heading:'Unga ride details',language:'Language',count:'Passengers',date:'Pickup date & time',review:'Ride review pannunga',title:'Journey weather',continue:'Booking confirm pannunga',change:'Details maathunga',loading:'Weather check pannrom…',ready:'Details paarthu confirm pannunga.',changed:'Details maariduchu. Thirumba review pannunga.',today:'Today',tomorrow:'Tomorrow',day:'Date',timeLabel:'Time',rain:'Rain chance',pickup:'Pickup',drop:'Drop-off',details:'Full details',scope:'Pickup nerathula ·',passengers:'Passengers',vehicle:'Vehicle',distance:'Road distance',fare:'Estimated fare',missing:'Kidaikkavillai',forecast:'Weather details',rainy:'Rain expected',heavy:'Heavy rain',storm:'Thunderstorms',cloudy:'Cloudy',clear:'Clear skies',heat:'High heat',unavailable:'Forecast kidaikkavillai',notYet:'Indha date-ku forecast innum varala',canContinue:'Booking continue pannalaam.',bikeTip:'Covered car consider pannunga. Unga choice.',severeBike:'Bike suitable illaama irukkalaam. Covered car consider pannunga.',rainTip:'Pickup, drop-off-ku umbrella eduthukkonga.',autoTip:'Side rain-la irundhu ungalaiyum bags-aiyum protect pannunga.',heatTip:'Water eduthukkonga; heat-ku prepare pannikkonga.',ai:'AI call-la book pannunga'}
 };
 for(const lang of Object.keys(uiMessages))Object.assign(messages[lang],uiMessages[lang]);
 function uiWords(){return uiMessages[langBox.value]||uiMessages.English;}
 function compactLabels(){
  const m=uiWords();
  for(const [id,key] of [['wxFormHeading','heading'],['wxToday','today'],['wxTomorrow','tomorrow'],['wxDayLabel','day'],['wxTimeLabel','timeLabel'],['wxRainLabel','rain'],['wxPickupLabel','pickup'],['wxDropLabel','drop'],['wxTripPickupLabel','pickup'],['wxTripDropLabel','drop'],['wxFullDetailsLabel','details'],['wxForecastScope','scope']])el(id).textContent=m[key];
  const ai=el('aiCall');if(ai)ai.textContent=m.ai;
 }
 function indiaDay(offset=0){
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
  const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
  return new Date(Date.UTC(Number(p.year),Number(p.month)-1,Number(p.day)+offset)).toISOString().slice(0,10);
 }
 function syncDayButtons(){
  for(const [id,offset] of [['wxToday',0],['wxTomorrow',1]])el(id).setAttribute('aria-pressed',String(el('wxPickupDay').value===indiaDay(offset)));
 }
 function setupDateInputs(){
  const day=el('wxPickupDay'),clock=el('wxPickupTime');
  function fromLegacy(){
   const v=dateBox.value.split('T');
   day.value=v[0]||day.value||indiaDay();clock.value=v[1]?.slice(0,5)||'';syncDayButtons();
  }
  function toLegacy(){
   if(dateBox.disabled)return fromLegacy();
   dateBox.value=day.value&&clock.value?day.value+'T'+clock.value:'';
   syncDayButtons();dateBox.dispatchEvent(new Event('change',{bubbles:true}));
  }
  fromLegacy();day.min=indiaDay();
  for(const node of [day,clock])node.addEventListener('change',toLegacy);
  dateBox.addEventListener('change',()=>{if(dateBox.value)fromLegacy();else if(!day.value||!clock.value)syncDayButtons();});
  for(const [id,offset] of [['wxToday',0],['wxTomorrow',1]])el(id).onclick=()=>{if(dateBox.disabled)return;day.value=indiaDay(offset);day.min=indiaDay();toLegacy();};
  // Keep the min-date current if the dashboard stays open overnight.
  day.addEventListener('focus',()=>{day.min=indiaDay();syncDayButtons();});
 }
 function shortPlace(value){
  const name=String(value||'').trim();
  // A pinned coordinate pair must remain intact; addresses can use the first part.
  return /^Map pin\s*\(/i.test(name)?name:(name.split(',')[0].trim()||name);
 }
 function placeLabel(id,value){const node=el(id);node.textContent=shortPlace(value);node.title=String(value||'');}
 function actualWeather(result){
  const lines=String(result.advisory||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  const weather=result.weather||{};
  const status=weather.status||result.weather_status;
  const ok=status==='ok';
  // v0.4 supplies the two probabilities as the first two advisory lines.
  // Read each endpoint separately: a missing pickup value must not become drop-off's.
  // Do not infer probabilities from weather type or turn missing values into zero.
  function probability(key,index){
   if(!ok)return null;
   const point=Array.isArray(weather.points)?weather.points.find(p=>p.location===key):null;
   let value=point?point.precipitation_probability:null;
   if(!point){const matches=[...(lines[index]||'').matchAll(/(\d+(?:\.\d+)?)\s*%/g)];value=matches.length?Number(matches.at(-1)[1]):null;}
   return value!==null&&value!==''&&Number.isFinite(Number(value))&&Number(value)>=0&&Number(value)<=100?Number(value):null;
  }
  // Legacy manual responses contain the weather description after both locations.
  // Match the server's actual descriptions; percentage alone is not a condition.
  const report=ok?lines.slice(2).join('\n'):'';
  const storm=!!weather.thunderstorm||/Thunderstorms are forecast|இடியுடன் கூடிய மழை|idiyudan koodiya mazhai/i.test(report);
  const heavy=!!weather.heavy_rain||/Heavy rain is forecast|கனமழை|kanamazhai/i.test(report);
  const heat=!!weather.heat||/Very hot conditions|வெப்பநிலை அதிகமாக|Veppanilai adhigamaaga/i.test(report);
  const rain=weather.condition==='rain'||storm||heavy||/Rain is expected|மழை எதிர்பார்க்கப்படுகிறது|mazhai peiya vaaippu irukkiradhu/i.test(report);
  const cloudy=weather.condition==='cloudy'||/Cloudy conditions|மேகமூட்டம்|megamoottam/i.test(report);
  const clear=weather.condition==='clear'||/Clear or mainly clear|weather looks pleasant|வானம் தெளிவாக|வானிலை நன்றாக|vaanam thelivaaga|vaanilai nandraagave/i.test(report);
  return {ok,status,pickup:probability('pickup',0),destination:probability('destination',1),storm,heavy,heat,rain,cloudy,clear};
 }
 function compactReview(result,data){
  const m=uiWords(),w=actualWeather(result),condition=el('wxCondition');
  const type=!w.ok?'unavailable':w.storm?'storm':w.heavy?'heavy':w.rain?'rainy':w.cloudy?'cloudy':w.clear?'clear':'forecast';
  condition.textContent=w.status==='outside_forecast_range'?m.notYet:m[type];
  if(w.heat)condition.textContent=type==='forecast'?m.heat:condition.textContent+' · '+m.heat;
  condition.dataset.tone=w.storm||w.heavy||w.rain?'rain':w.heat?'heat':w.clear?'clear':'neutral';
  for(const [id,key] of [['wxPickupRain','pickup'],['wxDropRain','destination']]){
   const node=el(id),value=w[key];node.textContent=value===null?m.missing:String(value)+'%';node.dataset.missing=String(value===null);
  }
  placeLabel('wxPickupName',data.pickup);placeLabel('wxDropName',data.destination);
  placeLabel('wxTripPickup',data.pickup);placeLabel('wxTripDrop',data.destination);
  const tips=[];
  if(!w.ok)tips.push(m.canContinue);
  else if(w.rain)tips.push(data.vehicle==='Bike'?(w.storm||w.heavy?m.severeBike:m.bikeTip):data.vehicle==='Auto'?m.autoTip:m.rainTip);
  if(w.heat)tips.push(m.heatTip);
  el('wxShortAdvice').textContent=tips.join(' ');
  const raw=String(result.pickup_at||data.pickup_at||'');
  const match=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(raw);
  if(match){
   // Display the selected Indian wall time as entered, even in another browser timezone.
   const d=new Date(Number(match[1]),Number(match[2])-1,Number(match[3]),Number(match[4]),Number(match[5]));
   const locale=data.language==='Tamil'?'ta-IN':'en-IN';
   el('wxTripDate').textContent=new Intl.DateTimeFormat(locale,{day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit',hour12:true}).format(d);
  }else el('wxTripDate').textContent=raw;
  const facts=el('wxTripFacts');facts.replaceChildren();
  const amount=result.fare??data.fare;
  const money=amount!==null&&amount!==''&&Number.isFinite(Number(amount))?new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(Number(amount)):m.missing;
  const distance=data.km!==null&&data.km!==undefined&&Number.isFinite(Number(data.km))?Number(data.km).toFixed(1)+' km':m.missing;
  for(const [label,value] of [[m.passengers,String(data.count)],[m.vehicle,result.vehicle||data.vehicle],[m.distance,distance],[m.fare,money]]){
   const box=document.createElement('div'),caption=document.createElement('small'),text=document.createElement('strong');
   caption.textContent=label;text.textContent=value;box.append(caption,text);facts.append(box);
  }
  el('wxManualAdvice').textContent=result.advisory||'';el('wxManualSummary').textContent=result.summary||'';
  el('wxManualReview').querySelector('details').open=false;
 }
 function tidyCustomerActions(){
  const row=el('aiCall')?.closest('.actions');if(row)row.classList.add('movio-voice-actions');
  const mic=el('voiceBook');if(mic){mic.setAttribute('aria-label','Dictate destination');mic.title='Dictate destination';}
  const address=el('searchAddress')?.parentElement;if(address)address.classList.add('movio-address-actions');
  for(const card of document.querySelectorAll('#aiRideHistory .ride-card')){
   const direct=[...card.children].filter(n=>n.tagName==='BUTTON');if(!direct.length)continue;
   let actions=[...card.children].find(n=>n.classList.contains('movio-card-actions'));
   if(!actions){actions=document.createElement('div');actions.className='movio-card-actions';card.append(actions);}
   actions.append(...direct);
  }
 }
 function watchCustomerCards(){
  tidyCustomerActions();const history=el('aiRideHistory');
  if(history)new MutationObserver(tidyCustomerActions).observe(history,{childList:true,subtree:true});
 }

 let review=null,serial=0,previewBusy=false,saving=false,uncertain=false;
 function words(){return messages[langBox.value]||messages.English;}
 function labels(){const m=words();for(const [id,key] of [['wxLanguageLabel','language'],['wxDateLabel','date'],['wxCountLabel','count'],['wxWeatherTitle','title'],['wxManualChange','change']])el(id).textContent=m[key];
  el('wxManualContinue').textContent=uncertain?m.retry:m.continue;if(!saving&&!previewBusy)book.textContent=m.review;compactLabels();}
 function status(text){el('wxManualStatus').textContent=text;}
 function mainLanguage(){const value=el('language')?.value||'en';return /tanglish|^auto$/i.test(value)?'Tanglish':/^ta|tamil/i.test(value)?'Tamil':'English';}
 langBox.value=mainLanguage();
 function payload(){return {language:langBox.value,count:Number(countBox.value),pickup_at:dateBox.value,pickup:pickup?.name,destination:destination?.name,
  plat:pickup?.lat,plng:pickup?.lng,dlat:destination?.lat,dlng:destination?.lng,vehicle,km,fare:fare(vehicle)};}
 function fingerprint(){return JSON.stringify(payload());}
 async function request(path,data,retry=false){
  for(let attempt=0;attempt<(retry?2:1);attempt++){
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),path==='manual-preview'?45000:15000);
   try{const response=await fetch('/api/weather-booking/'+path,{method:'POST',credentials:'same-origin',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    const body=await response.json();if(!response.ok||!body.ok){const e=Error(body.error||words().failed);e.http=response.status;throw e;}return body;
   }catch(e){if(e.http||attempt===(retry?1:0))throw e;}finally{clearTimeout(timer);}
  }
 }
 function discard(old){if(old)request('manual-discard',old.binding).catch(()=>{});}
 function invalidate(){if(saving||uncertain)return;serial++;if(review)discard(review);review=null;el('wxManualReview').hidden=true;status(words().changed);labels();}
 function checkChanges(){if(review&&!saving&&!uncertain&&review.fingerprint!==fingerprint())invalidate();labels();}
 for(const control of [langBox,dateBox,countBox])control.addEventListener('change',()=>{if(control===langBox)labels();invalidate();});
 el('language')?.addEventListener('change',()=>{if(!saving&&!uncertain){langBox.value=mainLanguage();labels();invalidate();}});
 for(const id of ['pickup','destination'])el(id)?.addEventListener('input',invalidate);
 // Retain the original map/address/route code, then invalidate only a stale review.
 const originalPlace=setPlace;setPlace=function(...args){if(saving||uncertain)return;const result=originalPlace(...args);checkChanges();return result;};
 const originalFares=fares;fares=function(...args){const result=originalFares(...args);checkChanges();return result;};
 const vehicleRoot=el('vehicles');vehicleRoot?.addEventListener('click',e=>{if(saving||uncertain){e.preventDefault();e.stopImmediatePropagation();}},true);
 function lock(on){
  const controls=[book,langBox,dateBox,countBox,el('wxPickupDay'),el('wxPickupTime'),el('wxToday'),el('wxTomorrow'),el('pickup'),el('destination'),el('wxManualContinue'),el('wxManualChange'),el('useCurrentPickup'),el('searchAddress'),el('pinPickup'),el('pinDestination')].filter(Boolean); // MOVIO_CUSTOMER_ADDRESS_LOCK_V1
  if(on){if(!section._disabled)section._disabled=controls.map(e=>[e,e.disabled]);for(const e of controls)e.disabled=true;
   const mapNode=el('map');if(mapNode){if(section._mapPointer==null)section._mapPointer=mapNode.style.pointerEvents;mapNode.style.pointerEvents='none';}}
  else{for(const [e,disabled] of section._disabled||[])e.disabled=disabled;const mapNode=el('map');if(mapNode)mapNode.style.pointerEvents=section._mapPointer||'';
   if(uncertain){book.disabled=true;el('wxManualChange').disabled=true;langBox.disabled=true;dateBox.disabled=true;countBox.disabled=true;for(const id of ['wxPickupDay','wxPickupTime','wxToday','wxTomorrow'])el(id).disabled=true;el('wxManualContinue').disabled=false;}
   else{delete section._disabled;delete section._mapPointer;}}
 }
 book.onclick=async e=>{
  e?.preventDefault();if(saving||previewBusy||uncertain||role!=='customer')return;
  if(!pickup||!destination||el('pickup').value!==pickup.name||el('destination').value!==destination.name){status(words().locations);return;}
  if(!dateBox.value){status(words().time);(el('wxPickupDay').value?el('wxPickupTime'):el('wxPickupDay')).focus();return;}
  const data=payload(),captured=JSON.stringify(data),ticket=++serial;
  const old=review;review=null;discard(old);el('wxManualReview').hidden=true;previewBusy=true;book.disabled=true;status(words().loading);
  try{const result=await request('manual-preview',data);
   if(ticket!==serial||captured!==fingerprint()){discard({binding:result});status(words().changed);return;}
   // MOVIO_MANUAL_FORECAST_VALIDATION_V1
   if(result.weather){
    const w=result.weather,points=w.points||[];
    const complete=w.status==='ok'&&['pickup','destination'].every(role=>{
     const p=points.find(row=>row.location===role),n=p?.precipitation_probability;
     return n!==null&&n!==undefined&&Number.isFinite(Number(n))&&Number(n)>=0&&Number(n)<=100;
    });
    if(!complete){discard({binding:result});const error=Error(result.forecast_error?.message||words().failed);error.http=503;throw error;}
   }

   review={fingerprint:captured,binding:{call_id:result.call_id,bind_token:result.bind_token,summary_nonce:result.summary_nonce,language:data.language}};
   compactReview(result,data);el('wxManualReview').hidden=false;status(words().ready);
  }catch(error){if(ticket===serial)status(error.http?error.message:words().failed);}
  finally{previewBusy=false;book.disabled=uncertain;labels();}
 };
 el('wxManualChange').onclick=()=>{invalidate();el('wxPickupDay').focus();};
 el('wxManualContinue').onclick=async()=>{
  if(saving||!review)return;if(!uncertain&&review.fingerprint!==fingerprint()){invalidate();return;}
  saving=true;lock(true);status(words().saving);
  try{const result=await request('manual-confirm',review.binding,true);

   // MOVIO_VERIFIED_BOOKING_RESET_V1
   if(!result.ok||!Number.isInteger(Number(result.id))||Number(result.id)<1){
    const error=Error(words().unknown);error.http=502;throw error;
   }
   uncertain=false;review=null;el('wxManualReview').hidden=true;rideId=Number(result.id);serial++;
   // Abort only draft lookups. Preserve saved rides, driver tracking and OTPs.
   const draft=window.MOVIOCustomerBookingUI?.state;
   if(draft){clearTimeout(draft.previewTimer);draft.routeController?.abort();draft.routeSeq++;draft.searchSeq++;
    draft.routeKey=null;draft.routePromise=null;draft.lastPreview=null;draft.field='pickup';}
   if(typeof searchTimer!=='undefined')clearTimeout(searchTimer);
   pickup=null;destination=null;km=0;minutes=0;routeData=null;selecting='pickup';
   for(const id of ['pickup','destination']){const node=el(id);if(node){node.value='';node.removeAttribute('title');}}
   el('suggestions')?.replaceChildren();
   if(routeLine){try{map.removeLayer(routeLine);}catch{}routeLine=null;}
   if(typeof markers!=='undefined')for(const key of ['pickup','destination']){
    if(markers[key]){try{map.removeLayer(markers[key]);}catch{}delete markers[key];}
   }
   vehicle='Mini';countBox.value='1';
   document.querySelectorAll('.vehicle').forEach(node=>node.classList.toggle('active',node.dataset.type==='Mini'));
   dateBox.value='';
   for(const id of ['wxPickupDay','wxPickupTime'])if(el(id))el(id).value='';
   if(el('wxPickupDay'))el('wxPickupDay').min=indiaDay();syncDayButtons();
   for(const id of ['wxPickupName','wxDropName','wxTripPickup','wxTripDrop','wxTripDate','wxShortAdvice','wxManualAdvice','wxManualSummary','wxPickupRain','wxDropRain','wxCondition']){
    const node=el(id);if(node){node.textContent='';node.removeAttribute('title');}
   }
   el('wxTripFacts')?.replaceChildren();
   if(el('routeInfo'))el('routeInfo').textContent=langBox.value==='Tamil'?'புறப்படும் இடத்தையும் சேரும் இடத்தையும் தேர்ந்தெடுக்கவும்.':langBox.value==='Tanglish'?'Pickup, destination select pannunga.':'Choose pickup and destination for a new ride.';
   try{fares();}catch{}status(result.message);toast(result.message);
   // Refresh failures must not turn a successful save into a failed booking.
   await Promise.allSettled([refreshRides(),renderVoiceHistory()]);
  }catch(error){uncertain=!error.http||error.http>=500;status(uncertain?words().unknown:error.message);}
  finally{saving=false;lock(false);labels();}
 };
 setupDateInputs();watchCustomerCards();labels();
})();
