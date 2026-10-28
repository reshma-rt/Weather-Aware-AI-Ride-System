/* MOVIO account authentication. Driver registration requires vehicle details. */
let movioRegister=false;
function movioAuthMode(register){movioRegister=register;$('showLogin').classList.toggle('selected',!register);$('showRegister').classList.toggle('selected',register);$('nameWrap').classList.toggle('hidden',!register);$('roleWrap').classList.toggle('hidden',!register);$('authSubmit').textContent=register?'Create account →':'Sign in →';movioRoleFields()}
function movioRoleFields(){const driver=movioRegister&&$('authRole').value==='driver';$('driverFields').classList.toggle('hidden',!driver);$('authVehicleNumber').required=driver;$('authName').required=movioRegister;$('authPassword').autocomplete=movioRegister?'new-password':'current-password'}
$('joinDriver').onclick=()=>{movioAuthMode(true);$('authRole').value='driver';movioRoleFields()};
$('showLogin').onclick=()=>movioAuthMode(false);$('showRegister').onclick=()=>movioAuthMode(true);$('authRole').onchange=movioRoleFields;
async function movioLoggedIn(){await movioRefreshProfile();$('authGate').classList.add('hidden');$('appShell').classList.remove('hidden');await refreshRides();await refreshLocations();setTimeout(()=>map.invalidateSize(),150);if(movioMe.role==='driver'&&(!movioMe.vehicle_type||!movioMe.vehicle_number))movioEditProfile();/* MOVIO_TRAVEL_COMPANION_LOGIN_V1 */window.MOVIOTravelCompanion?.login(movioMe)}
$('authForm').onsubmit=async e=>{e.preventDefault();$('authError').textContent='';const payload={phone:$('authPhone').value.trim(),password:$('authPassword').value};
 try{if(movioRegister){payload.name=$('authName').value.trim();payload.role=$('authRole').value;if(payload.role==='driver'){payload.vehicle_type=$('authVehicleType').value;payload.vehicle_number=$('authVehicleNumber').value.trim()}await post('/register',payload)}
 await post('/login',{phone:payload.phone,password:payload.password});await movioLoggedIn();
 }catch(err){$('authError').textContent=err.message}
};
$('logout').onclick=async()=>{await revoke(role);try{await post('/logout',{})}catch(e){}location.reload()};
(async()=>{try{await movioLoggedIn()}catch(e){$('authGate').classList.remove('hidden');$('appShell').classList.add('hidden')}})();
