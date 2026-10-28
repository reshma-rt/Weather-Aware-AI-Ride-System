/* MOVIO travel companion 1.0. Existing booking, GPS-sharing and voice handlers stay in control. */
(() => {
  'use strict';
  if (window.MOVIOTravelCompanion) return;
  const VERSION = 'travel-companion-1.0';
  const byId = id => document.getElementById(id);
  const state = { userId: null, sequence: 0, busy: false, attempted: false, pending: false,
    controller: null, position: null, response: null, gps: 'unavailable', phase: 'idle', languageDirty: false };
  const labels = {
    English: { title: 'Your Travel Companion', refresh: 'Refresh travel advice',
      greeting: 'Welcome back! Wishing you a comfortable journey.', loading: 'Checking local conditions…',
      rain: 'Rain chance', hourly: 'Forecast for this hour', near: 'Near ',
      clear: 'Clear skies', cloudy: 'Cloudy', rainCondition: 'Rain possible', heavy_rain: 'Heavy rain',
      storm: 'Thunderstorms', fog: 'Foggy', other: 'Local weather', fallback: 'Have a wonderful journey!' },
    Tamil: { title: 'உங்கள் பயணத் துணை', refresh: 'பயணத் தகவலைப் புதுப்பிக்கவும்',
      greeting: 'மீண்டும் வரவேற்கிறோம்! உங்கள் பயணம் இனிதாக அமையட்டும்.', loading: 'வானிலை தகவல் பெறப்படுகிறது…',
      rain: 'மழை வாய்ப்பு', hourly: 'இந்த நேரத்திற்கான முன்னறிவிப்பு', near: '',
      clear: 'தெளிவான வானம்', cloudy: 'மேகமூட்டம்', rainCondition: 'மழை வாய்ப்பு', heavy_rain: 'கனமழை',
      storm: 'இடியுடன் மழை', fog: 'மூடுபனி', other: 'வானிலை', fallback: 'உங்கள் பயணம் இனிமையாக அமையட்டும்!' },
    Tanglish: { title: 'Unga Travel Companion', refresh: 'Travel advice refresh pannunga',
      greeting: 'Welcome back! Unga payanam inimaiyaaga irukkattum.', loading: 'Local weather check pannrom…',
      rain: 'Rain chance', hourly: 'Indha hour forecast', near: '',
      clear: 'Clear skies', cloudy: 'Cloudy', rainCondition: 'Rain chance irukku', heavy_rain: 'Heavy rain',
      storm: 'Thunderstorms', fog: 'Foggy', other: 'Local weather', fallback: 'Unga payanam inimaiyaaga amaiyattum!' }
  };
  function language() {
    const select = byId('language');
    const option = select?.selectedOptions?.[0];
    const value = String(option?.textContent || select?.value || '').toLowerCase();
    if (value.includes('tanglish')) return 'Tanglish';
    if (/tamil|தமிழ்/.test(value) || /^ta(?:-|$)/i.test(select?.value || '')) return 'Tamil';
    return 'English';
  }
  function text(node, value) { const next = String(value ?? ''); if (node.textContent !== next) node.textContent = next; }
  function el(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }
  function mounted() { return byId('movioTravelCompanion'); }
  function mount() {
    const existing = mounted(); if (existing) return existing;
    const panel = byId('riderPanel'); if (!panel) return null;
    const card = el('section', 'movio-companion'); card.id = 'movioTravelCompanion';
    card.setAttribute('aria-labelledby', 'movioCompanionTitle');
    const head = el('div', 'movio-companion-head');
    const title = el('h2'); title.id = 'movioCompanionTitle';
    const refresh = el('button', 'movio-companion-refresh', '↻');
    refresh.id = 'movioCompanionRefresh'; refresh.type = 'button';
    refresh.addEventListener('click', () => void refreshAdvice(true));
    head.append(title, refresh);
    const greeting = el('p', 'movio-companion-greeting'); greeting.id = 'movioCompanionGreeting';
    const weather = el('div', 'movio-companion-weather'); weather.id = 'movioCompanionWeather'; weather.hidden = true;
    const primary = el('div', 'movio-companion-primary');
    const temperature = el('strong'); temperature.id = 'movioCompanionTemperature';
    const summary = el('div', 'movio-companion-summary');
    const condition = el('b'); condition.id = 'movioCompanionCondition';
    const locality = el('span'); locality.id = 'movioCompanionLocality'; summary.append(condition, locality);
    primary.append(temperature, summary);
    const chance = el('div', 'movio-companion-rain');
    const probability = el('b'); probability.id = 'movioCompanionProbability';
    const caption = el('span'); caption.id = 'movioCompanionRainLabel'; chance.append(probability, caption);
    weather.append(primary, chance);
    const tips = el('ul', 'movio-companion-tips'); tips.id = 'movioCompanionTips';
    const note = el('p', 'movio-companion-note'); note.id = 'movioCompanionNote'; note.hidden = true;
    card.append(head, greeting, weather, tips, note);
    const heading = Array.from(panel.children).find(child => child.classList.contains('sheet-head'));
    const anchor = heading?.nextElementSibling?.matches('p.muted') ? heading.nextElementSibling : heading;
    if (anchor) anchor.after(card); else panel.prepend(card);
    return card;
  }
  function display(response = null) {
    const card = mount(); if (!card) return;
    const lang = language(), words = labels[lang];
    text(byId('movioCompanionTitle'), words.title);
    const refresh = byId('movioCompanionRefresh');
    refresh.disabled = state.busy; refresh.title = words.refresh; refresh.setAttribute('aria-label', words.refresh);
    card.setAttribute('aria-busy', String(state.busy));
    text(byId('movioCompanionGreeting'), response?.language === lang ? response.greeting : words.greeting);
    const weather = response?.language === lang ? response.weather : null;
    const available = weather?.status === 'ok';
    byId('movioCompanionWeather').hidden = !available;
    const number = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
    if (available) {
      const temp = number(weather.temperature_c), rain = number(weather.rain_probability_pct);
      text(byId('movioCompanionTemperature'), temp === null ? '—' : `${Number(temp.toFixed(1))}°C`);
      text(byId('movioCompanionCondition'), words[weather.condition === 'rain' ? 'rainCondition' : weather.condition] || words.other);
      const locality = typeof response.locality === 'string' ? response.locality : '';
      text(byId('movioCompanionLocality'), locality ? (lang === 'Tamil' ? locality + ' அருகில்' : lang === 'Tanglish' ? locality + ' arugil' : words.near + locality) : '');
      text(byId('movioCompanionProbability'), rain === null ? '—' : `${Number(rain.toFixed(1))}%`);
      text(byId('movioCompanionRainLabel'), words.rain);
    }
    const tips = byId('movioCompanionTips');
    const rows = response?.language === lang && Array.isArray(response.recommendations)
      ? response.recommendations.filter(row => row && typeof row.text === 'string' && row.text.trim()).slice(0, 2) : [];
    // Weather values already appear above. Keep the engine-selected practical
    // precaution here rather than reading the same percentage twice.
    const messages = rows.length ? rows.map(row => {
      const full = row.text.trim();
      const sentences = full.split(/(?<=[.!?])\s+/);
      return row.group === 'weather' && sentences.length > 1 ? sentences.at(-1) : full;
    }) : [words.fallback];
    const signature = JSON.stringify(messages);
    if (tips.dataset.signature !== signature) {
      tips.replaceChildren(...messages.map(message => el('li', '', message)));
      tips.dataset.signature = signature;
    }
    const note = byId('movioCompanionNote');
    note.hidden = !state.busy && !available;
    text(note, state.busy ? words.loading : available ? words.hourly : '');
  }
  function invalidate() {
    state.sequence++; state.controller?.abort(); state.controller = null; state.busy = false;
  }
  function clear() {
    invalidate(); state.userId = null; state.attempted = false; state.pending = false;
    state.position = null; state.response = null; state.gps = 'unavailable'; state.phase = 'idle'; state.languageDirty = false;
    mounted()?.remove();
  }
  function shown() {
    return byId('appShell') && !byId('appShell').classList.contains('hidden') &&
      byId('riderPanel') && !byId('riderPanel').classList.contains('hidden');
  }
  async function jsonFetch(url, options, token) {
    const controller = new AbortController(); state.controller = controller;
    const timer = setTimeout(() => controller.abort(), 25000);
    try {
      const response = await fetch(url, { ...options, credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
      if (token !== state.sequence) throw new Error('stale_response');
      if (response.status === 401 || response.status === 403) { clear(); throw new Error('signed_out'); }
      if (!response.ok) throw new Error('optional_service_unavailable');
      return await response.json();
    } finally { clearTimeout(timer); if (state.controller === controller) state.controller = null; }
  }
  async function position() {
    if (!navigator.geolocation) throw { code: 0, unsupported: true };
    // Reuse the inspected one-shot utility. locate() reads GPS only; unlike
    // the map's current-location button, it does not select a booking pickup.
    if (typeof locate === 'function') {
      const point = await locate();
      return { lat: point.lat, lng: point.lng, observed_at: Date.now() };
    }
    return await new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(
      point => resolve({ lat: point.coords.latitude, lng: point.coords.longitude, observed_at: point.timestamp }),
      reject, { enableHighAccuracy: true, timeout: 12000, maximumAge: 3000 }));
  }
  async function refreshAdvice(readPosition = true) {
    if (state.busy || state.userId === null || !shown()) return;
    const token = ++state.sequence; state.busy = true; state.phase = 'checking'; display(state.response);
    try {
      const me = await jsonFetch('/api/me', {}, token);
      if (token !== state.sequence) return;
      if (me.role !== 'customer' || String(me.id) !== state.userId) { clear(); return; }
      if (readPosition) {
        state.phase = 'locating'; state.position = null;
        try {
          const point = await position(); if (token !== state.sequence) return;
          if (!Number.isFinite(point.lat) || !Number.isFinite(point.lng)) throw new Error('invalid_position');
          // Only a temporary approximate area stays in this tab's memory.
          state.position = { status: 'granted', lat: Number(point.lat.toFixed(3)), lng: Number(point.lng.toFixed(3)), observed_at: point.observed_at };
          state.gps = 'granted';
        } catch (error) {
          if (token !== state.sequence) return;
          state.gps = error?.unsupported ? 'unsupported' : error?.code === 1 ? 'denied' : error?.code === 3 ? 'timeout' : 'unavailable';
        }
      }
      state.phase = 'weather';
      const location = state.position || { status: state.gps };
      const response = await jsonFetch('/api/customer-care/recommend', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: { language: language(), current_location: location } })
      }, token);
      if (token !== state.sequence) return;
      state.response = response; state.phase = response.weather?.status === 'ok' ? 'ready' : 'neutral';
    } catch (error) {
      if (token === state.sequence) { state.response = null; state.phase = 'neutral'; }
    } finally {
      if (token === state.sequence) {
        state.busy = false; display(state.response);
        if (state.languageDirty && state.userId !== null && shown()) {
          state.languageDirty = false;
          if (!state.response || state.response.language !== language()) void refreshAdvice(false);
        }
      }
    }
  }
  function login(me) {
    if (!me || me.role !== 'customer' || me.id === undefined || me.id === null) { clear(); return; }
    const id = String(me.id);
    if (state.userId !== id) { clear(); state.userId = id; }
    if (!shown()) return;
    display(state.response);
    if (state.attempted) return;
    if (document.visibilityState === 'hidden') { state.pending = true; return; }
    state.pending = false; state.attempted = true; void refreshAdvice(true);
  }
  const publicAPI = Object.freeze({ version: VERSION, login,
    refresh: () => refreshAdvice(true), dispose: clear,
    getStatus: () => ({ phase: state.phase, gps: state.gps, busy: state.busy, mounted: !!mounted() }) });
  window.MOVIOTravelCompanion = publicAPI;
  byId('language')?.addEventListener('change', () => {
    if (state.userId === null) return;
    if (state.busy) { state.languageDirty = true; display(state.response); return; }
    const hadResponse = state.response;
    invalidate(); state.response = null; display();
    if (hadResponse && shown()) void refreshAdvice(false);
  });
  byId('logout')?.addEventListener('click', clear, { capture: true });
  window.addEventListener('pagehide', clear);
  document.addEventListener('visibilitychange', () => {
    if (state.pending && document.visibilityState !== 'hidden' && shown()) {
      state.pending = false; state.attempted = true; void refreshAdvice(true);
    }
  });
  function syncExistingLogin() {
    if (typeof movioMe !== 'undefined' && movioMe && shown()) login(movioMe);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', syncExistingLogin, { once: true });
  else syncExistingLogin();
  window.addEventListener('pageshow', event => { if (event.persisted) syncExistingLogin(); });
})();
