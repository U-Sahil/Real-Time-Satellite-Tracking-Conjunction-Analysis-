/*
  app.js (v2)
  -----------
  Adds to the original dashboard logic:
   - a "swarm" poll that feeds thousands of satellites into the globe's
     point cloud (Globe.setSwarmData), for the "alive" overview look
   - a "highlight" poll for selected + saved satellites, using the same
     current+lookahead trick so THOSE markers glide too, not just jump
   - the location/pass-finder panel: geocode a typed city (or use the
     browser's own geolocation), then turn the raw pass-prediction JSON
     into a plain-English sentence instead of raw timestamps
*/

const API_BASE = "";

const state = {
  token: localStorage.getItem("token") || null,
  username: localStorage.getItem("username") || null,
  satellites: [],
  savedIds: new Set(),
  selectedNoradId: null,
  lastConjunctionIds: new Set(),
  userLocation: null, // { lat, lon, label }
};

// ---------- API helpers ----------
async function api(path, options = {}) {
  const headers = options.headers || {};
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  if (options.body && !(options.body instanceof URLSearchParams)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(API_BASE + path, { ...options, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ---------- auth ----------
function setSession(token, username) {
  state.token = token;
  state.username = username;
  localStorage.setItem("token", token || "");
  localStorage.setItem("username", username || "");
  refreshAuthUI();
}

function refreshAuthUI() {
  const loggedIn = !!state.token;
  document.getElementById("btn-login").style.display = loggedIn ? "none" : "inline-block";
  document.getElementById("btn-register").style.display = loggedIn ? "none" : "inline-block";
  document.getElementById("btn-logout").style.display = loggedIn ? "inline-block" : "none";
  const label = document.getElementById("user-label");
  label.style.display = loggedIn ? "inline" : "none";
  label.textContent = loggedIn ? `Signed in as ${state.username}` : "";
  if (loggedIn) loadSavedSatellites();
}

async function loadSavedSatellites() {
  try {
    const saved = await api("/api/satellites/saved");
    state.savedIds = new Set(saved.map((s) => s.norad_id));
    renderSatList();
  } catch (e) {
    setSession(null, null);
  }
}

// ---------- modal ----------
let modalMode = "login";

function openModal(mode) {
  modalMode = mode;
  document.getElementById("modal-error").textContent = "";
  document.getElementById("modal-title").textContent = mode === "login" ? "Log in" : "Create account";
  document.getElementById("modal-submit").textContent = mode === "login" ? "Log in" : "Create account";
  document.getElementById("modal-email").style.display = mode === "login" ? "none" : "block";
  document.getElementById("modal-switch").textContent =
    mode === "login" ? "Need an account? Create one" : "Already have an account? Log in";
  document.getElementById("modal-backdrop").classList.add("open");
}

function closeModal() {
  document.getElementById("modal-backdrop").classList.remove("open");
  document.getElementById("modal-username").value = "";
  document.getElementById("modal-email").value = "";
  document.getElementById("modal-password").value = "";
}

async function submitModal() {
  const username = document.getElementById("modal-username").value.trim();
  const password = document.getElementById("modal-password").value;
  const email = document.getElementById("modal-email").value.trim();
  const errorEl = document.getElementById("modal-error");
  errorEl.textContent = "";

  try {
    if (modalMode === "register") {
      await api("/api/auth/register", { method: "POST", body: JSON.stringify({ username, email, password }) });
    }
    const body = new URLSearchParams({ username, password });
    const tokenResponse = await api("/api/auth/login", { method: "POST", body });
    setSession(tokenResponse.access_token, username);
    closeModal();
  } catch (e) {
    errorEl.textContent = e.message;
  }
}

// ---------- satellite list / search ----------
let searchDebounce;

async function loadSatelliteList(search) {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  state.satellites = await api(`/api/satellites${query}`);
  document.getElementById("hud-count").textContent = state.satellites.length;
  renderSatList();
}

function renderSatList() {
  const container = document.getElementById("sat-list");
  container.innerHTML = "";
  state.satellites.slice(0, 200).forEach((sat) => {
    const row = document.createElement("div");
    row.className = "sat-item" + (sat.norad_id === state.selectedNoradId ? " active" : "");

    const left = document.createElement("div");
    left.innerHTML = `${sat.name}<br/><span class="norad">NORAD ${sat.norad_id}</span>`;
    row.appendChild(left);

    const saveBtn = document.createElement("button");
    saveBtn.className = "save-btn" + (state.savedIds.has(sat.norad_id) ? " saved" : "");
    saveBtn.textContent = state.savedIds.has(sat.norad_id) ? "★" : "☆";
    saveBtn.title = "Save satellite (requires login)";
    saveBtn.onclick = (e) => { e.stopPropagation(); toggleSaveSatellite(sat.norad_id); };
    row.appendChild(saveBtn);

    row.onclick = () => selectSatellite(sat.norad_id);
    container.appendChild(row);
  });
}

async function toggleSaveSatellite(noradId) {
  if (!state.token) { openModal("login"); return; }
  try {
    if (state.savedIds.has(noradId)) {
      await api(`/api/satellites/saved/${noradId}`, { method: "DELETE" });
      state.savedIds.delete(noradId);
    } else {
      await api("/api/satellites/saved", {
        method: "POST",
        body: JSON.stringify({ norad_id: noradId, email_alerts_enabled: true }),
      });
      state.savedIds.add(noradId);
    }
    renderSatList();
  } catch (e) {
    alert(e.message);
  }
}

// ---------- selection + telemetry ----------
async function selectSatellite(noradId) {
  state.selectedNoradId = noradId;
  renderSatList();
  await refreshSelectedTelemetry();
}

async function refreshSelectedTelemetry() {
  if (!state.selectedNoradId) return;
  try {
    const pos = await api(`/api/satellites/${state.selectedNoradId}/position`);
    document.getElementById("telemetry-title").textContent = pos.name;
    document.getElementById("hud-selected").textContent = `${pos.name} (${pos.norad_id})`;
    document.getElementById("telemetry-body").innerHTML = `
      <div class="telemetry-row"><span class="k">NORAD ID</span><span class="v">${pos.norad_id}</span></div>
      <div class="telemetry-row"><span class="k">Latitude</span><span class="v">${pos.latitude_deg.toFixed(3)}°</span></div>
      <div class="telemetry-row"><span class="k">Longitude</span><span class="v">${pos.longitude_deg.toFixed(3)}°</span></div>
      <div class="telemetry-row"><span class="k">Altitude</span><span class="v">${pos.altitude_km.toFixed(1)} km</span></div>
      <div class="telemetry-row"><span class="k">Speed</span><span class="v">${pos.velocity_km_s.toFixed(3)} km/s</span></div>
      <div class="telemetry-row"><span class="k">As of</span><span class="v">${new Date(pos.timestamp).toLocaleTimeString()}</span></div>
    `;
  } catch (e) { /* satellite may have dropped out of the catalog */ }
}

// ---------- swarm (mass overview) ----------
async function refreshSwarm() {
  try {
    const entries = await api("/api/satellites/positions/bulk?limit=1500");
    Globe.setSwarmData(entries);
  } catch (e) { /* backend may still be loading its first TLE batch */ }
}

// ---------- highlighted satellites (selected + saved + in a live conjunction) ----------
async function refreshHighlights() {
  const ids = new Set(state.savedIds);
  if (state.selectedNoradId) ids.add(state.selectedNoradId);
  state.lastConjunctionIds.forEach((id) => ids.add(id));
  if (ids.size === 0) return;
  try {
    const entries = await api(`/api/satellites/positions/bulk?ids=${[...ids].join(",")}`);
    Globe.setHighlightData(entries, state.selectedNoradId);
  } catch (e) { /* ignore */ }
}

// ---------- conjunction screening panel ----------
async function refreshConjunctions() {
  try {
    const results = await api("/api/conjunctions?threshold_km=25&min_km=0.5");
    renderConjunctionList(results);

    const involved = new Set();
    results.slice(0, 15).forEach((c) => { involved.add(c.norad_id_1); involved.add(c.norad_id_2); });
    state.lastConjunctionIds = involved;

    await plotConjunctionLines(results.slice(0, 15));
  } catch (e) { /* ignore */ }
}

function renderConjunctionList(results) {
  const container = document.getElementById("conjunction-list");
  if (!results.length) {
    container.innerHTML = `<div class="empty-state">No independent close approaches detected right now under the 25&nbsp;km screening radius. (Permanently docked spacecraft, like ISS modules, are filtered out automatically.)</div>`;
    return;
  }
  container.innerHTML = "";
  results.slice(0, 30).forEach((c) => {
    const el = document.createElement("div");
    el.className = "conjunction-item";
    el.innerHTML = `<div class="pair">${c.name_1} ↔ ${c.name_2}</div><div class="distance">${c.distance_km.toFixed(2)} km separation</div>`;
    container.appendChild(el);
  });
}

async function plotConjunctionLines(results) {
  const involvedIds = new Set();
  results.forEach((c) => { involvedIds.add(c.norad_id_1); involvedIds.add(c.norad_id_2); });

  const positions = {};
  await Promise.all([...involvedIds].map(async (id) => {
    try {
      const pos = await api(`/api/satellites/${id}/position`);
      positions[id] = { lat: pos.latitude_deg, lon: pos.longitude_deg, alt: pos.altitude_km };
    } catch (e) { /* ignore */ }
  }));

  const linePairs = results
    .filter((c) => positions[c.norad_id_1] && positions[c.norad_id_2])
    .map((c) => ({ posA: positions[c.norad_id_1], posB: positions[c.norad_id_2] }));
  Globe.drawConjunctionLines(linePairs);
}

// ---------- location / pass finder ----------
function setLocationStatus(text, isError) {
  const el = document.getElementById("location-status");
  el.textContent = text;
  el.className = isError ? "error" : "";
}

async function geocodeCity(cityName) {
  const result = await api(`/api/location/geocode?city=${encodeURIComponent(cityName)}`);
  state.userLocation = { lat: result.latitude_deg, lon: result.longitude_deg, label: result.display_name };
}

function useBrowserLocation() {
  if (!navigator.geolocation) {
    setLocationStatus("Your browser doesn't support location access.", true);
    return;
  }
  setLocationStatus("Getting your location…");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      state.userLocation = { lat: pos.coords.latitude, lon: pos.coords.longitude, label: "your current location" };
      setLocationStatus(`Using your current location.`);
    },
    () => setLocationStatus("Couldn't get your location — try typing a city instead.", true)
  );
}

function formatClockTime(date) {
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function dayLabel(date) {
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const tomorrow = new Date(now); tomorrow.setDate(now.getDate() + 1);
  const isTomorrow = date.toDateString() === tomorrow.toDateString();
  if (isToday) return "today";
  if (isTomorrow) return "tomorrow";
  return date.toLocaleDateString([], { weekday: "long" });
}

function formatPassAsSentence(pass, satelliteName) {
  const rise = new Date(pass.rise_time);
  const set = new Date(pass.set_time);
  const durationSec = Math.round((set - rise) / 1000);
  const minutes = Math.floor(durationSec / 60);
  const seconds = durationSec % 60;
  const durationText = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

  return {
    headline: `${satelliteName} passes over ${dayLabel(rise)} at ${formatClockTime(rise)}`,
    sub: `Visible for about ${durationText}, reaching a maximum height of ${Math.round(pass.max_elevation_deg)}° above the horizon around ${formatClockTime(new Date(pass.culminate_time))}, then sets at ${formatClockTime(set)}.`,
  };
}

async function findNextPass() {
  if (!state.selectedNoradId) {
    setLocationStatus("Select a satellite from the list on the left first.", true);
    return;
  }
  const cityInput = document.getElementById("city-input").value.trim();

  try {
    if (cityInput) {
      setLocationStatus(`Looking up "${cityInput}"…`);
      await geocodeCity(cityInput);
    }
    if (!state.userLocation) {
      setLocationStatus("Enter a city, or tap 📍 to use your current location.", true);
      return;
    }

    setLocationStatus(`Calculating passes over ${state.userLocation.label}…`);
    const passes = await api(
      `/api/satellites/${state.selectedNoradId}/passes?lat=${state.userLocation.lat}&lon=${state.userLocation.lon}&days=5`
    );

    const container = document.getElementById("location-status");
    if (!passes.length) {
      container.innerHTML = `No visible passes over ${state.userLocation.label} in the next 5 days for this satellite.`;
      return;
    }

    const satName = state.satellites.find((s) => s.norad_id === state.selectedNoradId)?.name || "This satellite";
    const { headline, sub } = formatPassAsSentence(passes[0], satName);
    container.innerHTML = `<div class="pass-card"><div class="headline">${headline}</div><div class="sub">${sub}</div></div>`;

    Globe.focusOn(state.userLocation.lat, state.userLocation.lon);
  } catch (e) {
    setLocationStatus(e.message, true);
  }
}

// ---------- status line ----------
async function refreshStatus() {
  try {
    const health = await api("/api/health");
    document.getElementById("status-line").textContent = `LIVE — ${health.satellites_loaded} objects in catalog`;
  } catch (e) {
    document.getElementById("status-line").textContent = "BACKEND UNREACHABLE";
  }
}

// ---------- wire everything up ----------
function init() {
  Globe.init(document.getElementById("globe-canvas"));

  document.getElementById("btn-login").onclick = () => openModal("login");
  document.getElementById("btn-register").onclick = () => openModal("register");
  document.getElementById("btn-logout").onclick = () => {
    setSession(null, null);
    state.savedIds = new Set();
    renderSatList();
  };
  document.getElementById("modal-close").onclick = closeModal;
  document.getElementById("modal-submit").onclick = submitModal;
  document.getElementById("modal-switch").onclick = () => openModal(modalMode === "login" ? "register" : "login");

  document.getElementById("sat-search").addEventListener("input", (e) => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => loadSatelliteList(e.target.value.trim()), 300);
  });

  document.getElementById("btn-use-location").onclick = useBrowserLocation;
  document.getElementById("btn-find-pass").onclick = findNextPass;

  refreshAuthUI();
  refreshStatus();
  loadSatelliteList("");
  refreshConjunctions();
  refreshSwarm();

  setInterval(refreshStatus, 15000);
  setInterval(refreshConjunctions, 20000);
  setInterval(refreshSelectedTelemetry, 5000);
  setInterval(refreshSwarm, 8000);
  setInterval(refreshHighlights, 6000);
  refreshHighlights();
}

document.addEventListener("DOMContentLoaded", init);
