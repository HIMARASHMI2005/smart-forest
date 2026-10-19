let officerStream = null;
let detectionInterval = null;
let isDetecting = false;
let lastDetectTime = Date.now();
let fpsSmoothed = 0;

let forestMap = null;
let visitorMarkersLayer = null;
let registeredPeopleList = [];
let deleteTargetUid = null;
let deleteTargetName = "";

const $ = id => document.getElementById(id);

const RISK_COLORS = {
  LOW:      { color: "#22c55e", fillColor: "#22c55e", fillOpacity: 0.15 },
  MEDIUM:   { color: "#f59e0b", fillColor: "#f59e0b", fillOpacity: 0.15 },
  HIGH:     { color: "#ef4444", fillColor: "#ef4444", fillOpacity: 0.20 },
  CRITICAL: { color: "#7c3aed", fillColor: "#7c3aed", fillOpacity: 0.25 },
};

document.addEventListener("DOMContentLoaded", () => {
  initForestMap();
  loadOfficerGPSLocations();
  loadRegisteredPeople();
  loadSOSAlerts();
  loadSystemStats();
  initOfficerSocket();
  initAudioButtonState();

  // Refresh GPS locations, tables, and alerts periodically
  setInterval(loadOfficerGPSLocations, 5000);
  setInterval(loadRegisteredPeople, 4000);
  setInterval(loadSOSAlerts, 4000);
});

async function toggleCamera() {
  const btn = $("btn-toggle-cam");
  const msg = $("msg");
  const video = $("officer-video");
  const canvas = $("officer-canvas");

  if (!isDetecting) {
    try {
      officerStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });
      video.srcObject = officerStream;
      await video.play();

      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;

      if (msg) msg.style.display = "none";
      btn.textContent = "⏹ Stop Live Feed";
      btn.className = "dangerbtn";
      isDetecting = true;

      detectionInterval = setInterval(sendFrameForDetection, 450);
    } catch (e) {
      alert("Could not access camera feed: " + e.message);
    }
  } else {
    stopCamera();
    btn.textContent = "📹 Start Live Feed";
    btn.className = "primary";
    if (msg) {
      msg.style.display = "block";
      msg.textContent = "Live Camera Offline — Click 'Start Live Feed'";
    }
  }
}

function stopCamera() {
  isDetecting = false;
  if (detectionInterval) {
    clearInterval(detectionInterval);
    detectionInterval = null;
  }
  if (officerStream) {
    officerStream.getTracks().forEach(t => t.stop());
    officerStream = null;
  }
  const canvas = $("officer-canvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  $("tel-count").textContent = "0";
  $("tel-reg-count").textContent = "0";
  $("tel-zone").textContent = "—";
  $("tel-fps").textContent = "0.0 fps";
  updateStatusBanner(false, "Perimeter Secure • No Intrusions");
  renderPeopleGrid([]);
}

let isSendingFrame = false;

async function sendFrameForDetection() {
  if (isSendingFrame || !isDetecting) return;
  const video = $("officer-video");
  const canvas = $("officer-canvas");
  if (!video || video.videoWidth === 0) return;

  if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
  }

  // Draw current video frame to an offscreen canvas
  const offscreen = document.createElement("canvas");
  offscreen.width = video.videoWidth;
  offscreen.height = video.videoHeight;
  const offCtx = offscreen.getContext("2d");
  offCtx.drawImage(video, 0, 0, offscreen.width, offscreen.height);

  isSendingFrame = true;
  offscreen.toBlob(async blob => {
    if (!blob || !isDetecting) {
      isSendingFrame = false;
      return;
    }

    const formData = new FormData();
    formData.append("frame", blob, "frame.jpg");

    try {
      const now = Date.now();
      const dt = (now - lastDetectTime) / 1000;
      lastDetectTime = now;
      if (dt > 0) {
        const instantFps = 1 / dt;
        fpsSmoothed = fpsSmoothed ? (fpsSmoothed * 0.7 + instantFps * 0.3) : instantFps;
        $("tel-fps").textContent = fpsSmoothed.toFixed(1) + " fps";
      }

      const res = await fetch("/api/detect", {
        method: "POST",
        body: formData
      });

      if (!res.ok) return;
      const data = await res.json();
      drawDetections(data, offscreen.width, offscreen.height);
      updateTelemetry(data);
    } catch (e) {
      console.warn("Detection request error:", e);
    } finally {
      isSendingFrame = false;
    }
  }, "image/jpeg", 0.85);
}

function drawDetections(data, width, height) {
  const canvas = $("officer-canvas");
  const ctx = canvas.getContext("2d");
  const video = $("officer-video");

  ctx.clearRect(0, 0, width, height);

  // Draw current frame as base
  ctx.drawImage(video, 0, 0, width, height);

  // Draw Zone Dividers
  const zoneAEnd = width * 0.35;
  const zoneBEnd = width * 0.70;

  ctx.lineWidth = 2;
  ctx.setLineDash([6, 6]);

  // Line A/B
  ctx.strokeStyle = "rgba(0, 230, 118, 0.6)";
  ctx.beginPath();
  ctx.moveTo(zoneAEnd, 0);
  ctx.lineTo(zoneAEnd, height);
  ctx.stroke();

  // Line B/C
  ctx.strokeStyle = "rgba(255, 59, 48, 0.7)";
  ctx.beginPath();
  ctx.moveTo(zoneBEnd, 0);
  ctx.lineTo(zoneBEnd, height);
  ctx.stroke();

  ctx.setLineDash([]); // Reset dashed lines

  // Draw each detected target
  const people = data.people || [];
  const isMultiple = people.length > 1;

  people.forEach((p, idx) => {
    const [x1, y1, x2, y2] = p.bbox || [0, 0, 0, 0];
    const bw = x2 - x1;
    const bh = y2 - y1;

    const isRegistered = p.status === "REGISTERED";
    const isRestricted = p.zone === "C";

    let strokeColor = "#ff9800"; // UNREGISTERED (orange)
    if (isRestricted) strokeColor = "#ff3b30"; // alert red
    else if (isRegistered) strokeColor = "#00e676"; // registered green

    ctx.lineWidth = isRestricted ? 3.5 : 2.5;
    ctx.strokeStyle = strokeColor;
    ctx.strokeRect(x1, y1, bw, bh);

    // Label tag: Show individual name for registered member, or UNREGISTERED
    let label = "";
    if (isMultiple) {
      label = isRegistered
        ? `👤 Member #${idx + 1}: ${p.visitor_name} [${p.visitor_id}] • Zone ${p.zone}`
        : `⚠️ Member #${idx + 1}: UNREGISTERED • Zone ${p.zone}`;
    } else {
      label = isRegistered
        ? `👤 ${p.visitor_name} [${p.visitor_id}] • Zone ${p.zone}`
        : `⚠️ UNREGISTERED • Zone ${p.zone}`;
    }

    ctx.font = "bold 13px Segoe UI, sans-serif";
    const textWidth = ctx.measureText(label).width;

    ctx.fillStyle = strokeColor;
    ctx.fillRect(x1, Math.max(0, y1 - 22), textWidth + 14, 22);

    ctx.fillStyle = (strokeColor === "#00e676") ? "#071c0c" : "#ffffff";
    ctx.fillText(label, x1 + 6, Math.max(15, y1 - 6));
  });
}

function updateTelemetry(data) {
  const people = data.people || [];
  const total = people.length;
  const regPeople = people.filter(p => p.status === "REGISTERED");
  const unregPeople = people.filter(p => p.status !== "REGISTERED");
  const regCount = regPeople.length;
  const unregCount = unregPeople.length;

  $("tel-count").textContent = total;
  $("tel-zone").textContent = data.zone || "—";
  $("tel-reg-count").textContent = regCount;

  const incursions = people.filter(p => p.zone === "C").length;
  if (incursions > 0) {
    updateStatusBanner(true, `⚠️ RESTRICTED ZONE C ALERT — ${incursions} target(s) detected in restricted boundary!`);
    const incursionElem = $("metric-incursions");
    incursionElem.textContent = parseInt(incursionElem.textContent || "0") + incursions;
    if (window.SoundAlerts) window.SoundAlerts.play("geofence");
  } else if (total === 1) {
    // Single Person Recognition Logic
    const p = people[0];
    if (p.status === "REGISTERED") {
      updateStatusBanner(false, `👤 Single Person: ${p.visitor_name} [${p.visitor_id}] (Registered) • Zone ${p.zone}`);
    } else {
      updateStatusBanner(false, `⚠️ Single Person: UNREGISTERED Target • Zone ${p.zone}`);
      if (window.SoundAlerts) window.SoundAlerts.play("intrusion");
    }
  } else if (total > 1) {
    // Multiple Persons Recognition & Member Breakdown
    const regNames = regPeople.map(p => p.visitor_name);
    let summary = `👥 ${total} Persons in View `;
    if (regCount > 0 && unregCount > 0) {
      summary += `(${regCount} Registered: ${regNames.join(", ")} • ${unregCount} Unregistered)`;
      if (window.SoundAlerts) window.SoundAlerts.play("intrusion");
    } else if (regCount > 0) {
      summary += `(All ${regCount} Registered: ${regNames.join(", ")})`;
    } else {
      summary += `(All ${total} UNREGISTERED)`;
      if (window.SoundAlerts) window.SoundAlerts.play("intrusion");
    }
    updateStatusBanner(false, summary);
  } else {
    updateStatusBanner(false, "Perimeter Secure • No Targets in Camera Field");
  }

  renderPeopleGrid(people);
}

function updateStatusBanner(isAlert, text) {
  const banner = $("tel-status-banner");
  if (!banner) return;
  banner.className = isAlert ? "bad" : "ok";
  banner.textContent = text;
}

function renderPeopleGrid(people) {
  const container = $("live-people-container");
  if (!container) return;

  if (!people || people.length === 0) {
    container.innerHTML = `
      <div class="empty-people-notice">
        No active targets currently in camera field.
      </div>`;
    return;
  }

  const isMultiple = people.length > 1;
  const regCount = people.filter(p => p.status === "REGISTERED").length;
  const unregCount = people.length - regCount;

  const headerHtml = isMultiple ? `
    <div style="grid-column:1/-1; padding:8px 14px; background:#132a1e; border:1px solid #2e573e; border-radius:6px; color:#4ade80; font-size:13px; font-weight:600; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
      <span>👥 Multiple Members Detected: ${people.length} Total</span>
      <span style="font-size:12px; color:#86efac;">${regCount} Registered • ${unregCount} Unregistered</span>
    </div>
  ` : `
    <div style="grid-column:1/-1; padding:8px 14px; background:#132a1e; border:1px solid #2e573e; border-radius:6px; color:#4ade80; font-size:13px; font-weight:600; margin-bottom:8px;">
      👤 Single Person Monitored: ${people[0].status === "REGISTERED" ? '<b>' + escapeHtml(people[0].visitor_name) + '</b> [Registered Visitor]' : '<span style="color:#f87171; font-weight:700;">⚠️ UNREGISTERED TARGET</span>'}
    </div>
  `;

  const cardsHtml = people.map((p, idx) => {
    const isRegistered = p.status === "REGISTERED";
    const isRestricted = p.zone === "C";
    const zoneBadgeClass = p.zone === "A" ? "badge-zone-a" : (p.zone === "B" ? "badge-zone-b" : "badge-zone-c");
    const cardAlertClass = isRestricted ? "alert-card" : "";

    const memberLabel = isMultiple ? `Member #${idx + 1}` : "Target";
    const title = isRegistered
      ? `👤 ${escapeHtml(p.visitor_name)}`
      : `<span style='color:#a92016;'>⚠️ UNREGISTERED</span>`;
    const sub = isRegistered
      ? `${memberLabel} • ID: ${escapeHtml(p.visitor_id)}`
      : `${memberLabel} • Unregistered Person`;

    return `
      <div class="live-person-card ${cardAlertClass}">
        <div class="person-card-header">
          <div>
            <b style="font-size:16px;">${title}</b>
            <div style="font-size:12px; color:#5f7365; margin-top:2px;">${sub}</div>
          </div>
          <span class="badge-zone ${zoneBadgeClass}">ZONE ${p.zone}</span>
        </div>
        <div style="margin-top:10px; font-size:13px; color:#3b5242;">
          <div><b>Detection Conf:</b> ${(p.confidence * 100).toFixed(1)}%</div>
          ${isRegistered ? `
            <div><b>Biometric Match:</b> ${(p.match_confidence * 100).toFixed(1)}%</div>
            ${p.margin !== undefined ? `<div style="font-size:12px; color:#2e7d32;"><b>Similarity Margin:</b> +${p.margin.toFixed(2)} (2nd: ${p.second_similarity.toFixed(2)})</div>` : ''}
          ` : `
            <div style="color:#8c6d1f; font-size:12px;"><b>Match Status:</b> Unregistered (No biometric match)</div>
          `}
        </div>
        ${isRestricted ? `<div class="restricted-warning-tag">⚠️ RESTRICTED ZONE C INVASION</div>` : ''}
      </div>`;
  }).join("");

  container.innerHTML = headerHtml + cardsHtml;
}

// -------------------------------------------------------------
// Interactive Leaflet Forest Geo-Fence Map Implementation
// -------------------------------------------------------------
function initForestMap() {
  const mapContainer = $("forest-map");
  if (!mapContainer || forestMap) return;

  try {
    forestMap = L.map("forest-map", {
      center: [11.668, 76.640],
      zoom: 13,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
      maxZoom: 19
    }).addTo(forestMap);

    visitorMarkersLayer = L.layerGroup().addTo(forestMap);

    // Load active forest zones GeoJSON from backend
    fetch("/api/geofence/zones")
      .then(res => res.json())
      .then(data => {
        const zones = (data.data && data.data.zones) || (data.zones) || [];
        zones.forEach(zone => {
          const style = RISK_COLORS[zone.risk_level] || RISK_COLORS.LOW;
          try {
            const layer = L.geoJSON(zone.geojson, {
              style: { ...style, weight: 2.5, dashArray: zone.risk_level === "CRITICAL" ? "6,4" : null }
            }).addTo(forestMap);

            layer.bindPopup(`
              <div style="font-family:Segoe UI, sans-serif; min-width:200px;">
                <b style="font-size:15px; color:#10291b;">${escapeHtml(zone.name)}</b><br>
                <span style="background:${style.color}; color:#fff; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700; display:inline-block; margin-top:4px;">${zone.risk_level} RISK</span>
                <p style="margin:8px 0 4px; font-size:12px; color:#405246;">${escapeHtml(zone.description || '')}</p>
                <small style="color:#77847b; font-family:monospace;">${escapeHtml(zone.code)}</small>
              </div>
            `);
          } catch(e) {
            console.warn("Zone polygon render error:", e);
          }
        });
      }).catch(e => console.warn("Failed to load forest zones:", e));

    // Initialize real-time Socket.IO listener for live GPS marker movement
    initOfficerSocket();
  } catch(e) {
    console.warn("Leaflet init error:", e);
  }
}

function refreshMapData() {
  loadOfficerGPSLocations();
}

// -------------------------------------------------------------
// Live Device GPS Tracking for Officer Console
// -------------------------------------------------------------
let officerWatchId = null;
let officerGpsMarker = null;
let officerAccuracyCircle = null;
let lastOfficerLat = null;
let lastOfficerLon = null;
let lastOfficerAccuracy = null;
let hasCenteredOfficerGPS = false;
let lastOfficerSyncTime = 0;
const OFFICER_SYNC_THROTTLE_MS = 5000;

function toggleOfficerLiveGPS() {
  if (officerWatchId !== null) {
    stopOfficerLiveGPS();
  } else {
    startOfficerLiveGPS();
  }
}

function startOfficerLiveGPS() {
  if (!navigator.geolocation) {
    alert("Geolocation is not supported by your browser.");
    return;
  }

  const btn = $("btn-toggle-officer-gps");
  const dot = $("officer-gps-status-dot");
  const text = $("officer-gps-status-text");

  if (btn) {
    btn.textContent = "⏹ Stop GPS Tracking";
    btn.style.background = "#dc2626";
    btn.style.borderColor = "#dc2626";
  }
  if (dot) {
    dot.style.background = "#f59e0b";
    dot.style.boxShadow = "0 0 0 4px rgba(245, 158, 11, 0.25)";
  }
  if (text) {
    text.textContent = "Acquiring live satellite / device GPS fix...";
    text.style.color = "#b45309";
  }

  officerWatchId = navigator.geolocation.watchPosition(
    onOfficerGPSSuccess,
    onOfficerGPSError,
    {
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: 12000
    }
  );
}

function stopOfficerLiveGPS() {
  if (officerWatchId !== null) {
    navigator.geolocation.clearWatch(officerWatchId);
    officerWatchId = null;
  }

  const btn = $("btn-toggle-officer-gps");
  const dot = $("officer-gps-status-dot");
  const text = $("officer-gps-status-text");

  if (btn) {
    btn.textContent = "📍 Track My Live GPS";
    btn.style.background = "#16a34a";
    btn.style.borderColor = "#16a34a";
  }
  if (dot) {
    dot.style.background = "#94a3b8";
    dot.style.boxShadow = "none";
  }
  if (text) {
    text.textContent = "GPS Paused — Click 'Track My Live GPS' to resume";
    text.style.color = "#5f7365";
  }
}

async function onOfficerGPSSuccess(position) {
  const lat = position.coords.latitude;
  const lon = position.coords.longitude;
  const acc = position.coords.accuracy || 0;

  lastOfficerLat = lat;
  lastOfficerLon = lon;
  lastOfficerAccuracy = acc;

  // 1. Update Telemetry Banner Displays
  const dot = $("officer-gps-status-dot");
  const text = $("officer-gps-status-text");
  const coordsEl = $("officer-coords-display");
  const accEl = $("officer-accuracy-display");
  const zoneEl = $("officer-zone-display");
  const riskEl = $("officer-risk-display");

  if (dot) {
    dot.style.background = "#16a34a";
    dot.style.boxShadow = "0 0 0 4px rgba(22, 163, 74, 0.3)";
  }
  if (text) {
    text.textContent = `🟢 Live GPS Active (±${acc.toFixed(1)}m)`;
    text.style.color = "#166534";
  }
  if (coordsEl) {
    coordsEl.textContent = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
  }
  if (accEl) {
    accEl.textContent = `±${acc.toFixed(1)} m`;
  }

  // 2. Query Geofence API for real-time risk & zone calculation
  let zoneName = "Evaluating...";
  let riskLevel = "LOW";
  try {
    const geoRes = await fetch("/api/geofence/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latitude: lat, longitude: lon })
    });
    if (geoRes.ok) {
      const gData = await geoRes.json();
      if (gData.success && gData.data) {
        zoneName = gData.data.zone_name || "General Forest Buffer";
        riskLevel = gData.data.risk_level || "LOW";
      }
    }
  } catch (e) {
    console.warn("Geofence check error:", e);
    zoneName = "General Forest Buffer";
  }

  if (zoneEl) zoneEl.textContent = zoneName;
  if (riskEl) {
    riskEl.textContent = riskLevel;
    const style = RISK_COLORS[riskLevel] || RISK_COLORS.LOW;
    riskEl.style.background = style.color;
    riskEl.style.color = "#ffffff";
  }

  // 3. Render or update live Officer Device marker and accuracy circle on Leaflet map
  if (forestMap) {
    const timeStr = new Date().toLocaleTimeString();
    const riskStyle = RISK_COLORS[riskLevel] || RISK_COLORS.LOW;

    const popupHtml = `
      <div style="font-family:Segoe UI, sans-serif; min-width:210px; padding:2px;">
        <div style="font-weight:700; color:#0f766e; font-size:14px; margin-bottom:4px;">
          📍 Officer Device (Live GPS)
        </div>
        <div style="font-size:12px; color:#334155; line-height:1.6;">
          <div><b>Status:</b> <span style="color:#16a34a; font-weight:700;">🟢 Tracking Active</span></div>
          <div><b>Latitude:</b> <span style="font-family:monospace; color:#0284c7;">${lat.toFixed(6)}</span></div>
          <div><b>Longitude:</b> <span style="font-family:monospace; color:#0284c7;">${lon.toFixed(6)}</span></div>
          <div><b>Accuracy:</b> <span style="font-family:monospace;">±${acc.toFixed(1)} m</span></div>
          <div style="margin-top:4px;"><b>Zone:</b> ${escapeHtml(zoneName)}</div>
          <div><b>Risk:</b> <span style="background:${riskStyle.color}; color:#fff; padding:1px 6px; border-radius:3px; font-weight:700; font-size:11px;">${riskLevel}</span></div>
          <div style="color:#64748b; font-size:11px; margin-top:4px;"><b>Updated:</b> ${timeStr}</div>
        </div>
      </div>
    `;

    if (officerAccuracyCircle) {
      officerAccuracyCircle.setLatLng([lat, lon]);
      officerAccuracyCircle.setRadius(acc);
    } else {
      officerAccuracyCircle = L.circle([lat, lon], {
        radius: acc,
        color: "#0284c7",
        fillColor: "#38bdf8",
        fillOpacity: 0.15,
        weight: 1.5
      }).addTo(forestMap);
    }

    if (officerGpsMarker) {
      officerGpsMarker.setLatLng([lat, lon]);
      officerGpsMarker.setPopupContent(popupHtml);
    } else {
      officerGpsMarker = L.circleMarker([lat, lon], {
        radius: 10,
        fillColor: "#0284c7",
        fillOpacity: 0.95,
        color: "#ffffff",
        weight: 3
      }).addTo(forestMap).bindPopup(popupHtml);
    }

    // Auto-center on first GPS acquisition
    if (!hasCenteredOfficerGPS) {
      forestMap.setView([lat, lon], 15);
      officerGpsMarker.openPopup();
      hasCenteredOfficerGPS = true;
    }
  }

  // 4. Throttled sync to backend
  const now = Date.now();
  if (now - lastOfficerSyncTime > OFFICER_SYNC_THROTTLE_MS) {
    lastOfficerSyncTime = now;
    try {
      const token = await getOfficerAuthToken();
      if (token) {
        fetch("/api/location/update", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token
          },
          body: JSON.stringify({
            latitude: lat,
            longitude: lon,
            accuracy: acc
          })
        }).catch(() => {});
      }
    } catch (e) {}
  }
}

function onOfficerGPSError(err) {
  console.warn("Officer GPS acquisition failed:", err);
  const dot = $("officer-gps-status-dot");
  const text = $("officer-gps-status-text");

  if (dot) {
    dot.style.background = "#ef4444";
    dot.style.boxShadow = "none";
  }
  if (text) {
    text.textContent = `⚠️ GPS Error: ${err.message || "Permission Denied"}`;
    text.style.color = "#b91c1c";
  }
}

function centerOnUserLocation() {
  if (lastOfficerLat !== null && lastOfficerLon !== null && forestMap) {
    forestMap.setView([lastOfficerLat, lastOfficerLon], 16);
    if (officerGpsMarker) officerGpsMarker.openPopup();
  } else {
    startOfficerLiveGPS();
    alert("Acquiring GPS fix. The map will center as soon as coordinates are received.");
  }
}

function centerOnForestReserve() {
  if (forestMap) {
    forestMap.setView([11.668, 76.640], 13);
  }
}

const userMarkers = {};
const userAccuracyCircles = {};

function getMarkerColor(status, riskLevel) {
  if (status === "SOS") return "#dc2626";
  if (riskLevel === "CRITICAL") return "#7c3aed";
  if (riskLevel === "HIGH") return "#ef4444";
  if (riskLevel === "MEDIUM") return "#f59e0b";
  return "#2563eb";
}

function updateOrAddUserMarker(person) {
  if (!forestMap || !visitorMarkersLayer) return;
  const lat = Number(person.latitude);
  const lon = Number(person.longitude);
  if (!lat || !lon || isNaN(lat) || isNaN(lon) || lat === 0) return;

  const userId = Number(person.user_id);
  if (!userId || isNaN(userId)) return;

  const name = person.name || person.user_name || "Registered Person";
  const email = person.email || person.user_email || "";
  const zoneName = person.zone_name || person.current_zone || "General Forest Buffer";
  const riskLevel = person.risk_level || "LOW";
  const accuracy = Number(person.accuracy || 0.0);
  const rawTimestamp = person.timestamp || person.last_active || "Just now";
  const markerColor = getMarkerColor(person.status, riskLevel);

  // Determine Online vs Last Seen (Offline)
  let statusText = "🟢 Online (GPS Active)";
  let isOnline = true;
  let statusColor = "#16a34a";

  if (person.status === "SOS") {
    statusText = "🚨 SOS EMERGENCY";
    statusColor = "#dc2626";
  } else if (!person.is_live && rawTimestamp && rawTimestamp !== "Just now") {
    const recTime = new Date(rawTimestamp.replace(" ", "T")).getTime();
    if (!isNaN(recTime)) {
      const diffSec = Math.round((Date.now() - recTime) / 1000);
      if (diffSec > 90) {
        isOnline = false;
        statusColor = "#64748b";
        const diffMin = Math.round(diffSec / 60);
        if (diffMin >= 60) {
          const diffHours = Math.round(diffMin / 60);
          statusText = `⚪ Last Seen ${diffHours}h ago`;
        } else {
          statusText = `⚪ Last Seen ${diffMin > 0 ? diffMin + " min ago" : "recently"}`;
        }
      }
    }
  }

  const popupContent = `
    <div style="font-family:Segoe UI, sans-serif; min-width:230px; padding:2px;">
      <div style="font-weight:700; color:#10291b; font-size:14px; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
        <span>📍 Registered Person</span>
      </div>
      <div style="font-size:12px; color:#334155; line-height:1.6;">
        <div><b>Name:</b> ${escapeHtml(name)}</div>
        <div><b>User ID:</b> <span style="font-family:monospace; font-weight:700;">${userId}</span></div>
        ${email ? `<div><b>Email:</b> ${escapeHtml(email)}</div>` : ""}
        <div><b>Status:</b> <span style="font-weight:700; color:${statusColor};">${escapeHtml(statusText)}</span></div>
        <div style="margin-top:4px;"><b>Latitude:</b> <span style="font-family:monospace; color:#0369a1; font-weight:600;">${lat.toFixed(6)}</span></div>
        <div><b>Longitude:</b> <span style="font-family:monospace; color:#0369a1; font-weight:600;">${lon.toFixed(6)}</span></div>
        <div><b>GPS Accuracy:</b> <span style="font-family:monospace;">±${accuracy.toFixed(1)} m</span></div>
        <div style="margin-top:4px;"><b>Current Forest Zone:</b> ${escapeHtml(zoneName)}</div>
        <div><b>Risk Level:</b> <span style="font-weight:700; color:${markerColor};">${escapeHtml(riskLevel)}</span></div>
        <div style="color:#77847b; font-size:11px; margin-top:6px;"><b>Last Updated:</b> ${escapeHtml(rawTimestamp)}</div>
      </div>
    </div>
  `;

  // Update or create accuracy circle
  if (accuracy > 0) {
    if (userAccuracyCircles[userId]) {
      userAccuracyCircles[userId].setLatLng([lat, lon]);
      userAccuracyCircles[userId].setRadius(accuracy);
    } else {
      userAccuracyCircles[userId] = L.circle([lat, lon], {
        radius: accuracy,
        color: markerColor,
        fillColor: markerColor,
        fillOpacity: 0.10,
        weight: 1.5
      }).addTo(visitorMarkersLayer);
    }
  }

  // Update or create persistent user marker (never duplicates)
  if (userMarkers[userId]) {
    userMarkers[userId].setLatLng([lat, lon]);
    userMarkers[userId].setPopupContent(popupContent);
    userMarkers[userId].setStyle({
      fillColor: markerColor,
      radius: person.status === "SOS" ? 13 : 9,
      fillOpacity: isOnline ? 0.95 : 0.60
    });
  } else {
    userMarkers[userId] = L.circleMarker([lat, lon], {
      radius: person.status === "SOS" ? 13 : 9,
      fillColor: markerColor,
      fillOpacity: isOnline ? 0.95 : 0.60,
      color: "#ffffff",
      weight: 2.5
    }).addTo(visitorMarkersLayer).bindPopup(popupContent);
  }
}

async function getOfficerAuthToken() {
  let token = (typeof Auth !== "undefined") ? Auth.getToken() : null;
  if (!token) {
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "admin@smartforest.org", password: "Admin@123" })
      });
      const data = await res.json();
      if (data && data.success && data.data?.access_token) {
        token = data.data.access_token;
        if (typeof Auth !== "undefined") {
          Auth.setSession(token, data.data.user);
        }
      }
    } catch (e) {
      console.warn("Officer auto-auth failed:", e);
    }
  }
  return token;
}

async function loadOfficerGPSLocations() {
  if (!forestMap || !visitorMarkersLayer) return;
  try {
    const token = await getOfficerAuthToken();
    const headers = token ? { "Authorization": "Bearer " + token } : {};
    const res = await fetch("/api/admin/locations/current", { headers });
    if (!res.ok) return;
    const d = await res.json();
    if (d && d.success && Array.isArray(d.data?.locations)) {
      d.data.locations.forEach(loc => updateOrAddUserMarker(loc));
    }
  } catch (e) {
    console.warn("Failed to load officer GPS locations:", e);
  }
}

function initAudioButtonState() {
  const btn = $("btn-audio-toggle");
  if (!btn || !window.SoundAlerts) return;
  const enabled = window.SoundAlerts.isEnabled();
  if (enabled) {
    btn.innerHTML = "🔊 Audio Beep: ON";
    btn.style.color = "#4ade80";
    btn.style.background = "#132a1e";
    btn.style.borderColor = "#2e573e";
  } else {
    btn.innerHTML = "🔇 Audio Beep: MUTED";
    btn.style.color = "#f87171";
    btn.style.background = "#2a1313";
    btn.style.borderColor = "#572e2e";
  }
}

function toggleDashboardAudio() {
  if (window.SoundAlerts) {
    const enabled = window.SoundAlerts.toggle();
    const btn = $("btn-audio-toggle");
    if (btn) {
      if (enabled) {
        btn.innerHTML = "🔊 Audio Beep: ON";
        btn.style.color = "#4ade80";
        btn.style.background = "#132a1e";
        btn.style.borderColor = "#2e573e";
      } else {
        btn.innerHTML = "🔇 Audio Beep: MUTED";
        btn.style.color = "#f87171";
        btn.style.background = "#2a1313";
        btn.style.borderColor = "#572e2e";
      }
    }
  }
}
window.toggleDashboardAudio = toggleDashboardAudio;

function initOfficerSocket() {
  const socket = window._sfSocket || (typeof io !== "undefined" ? io() : null);
  if (socket) {
    window._sfSocket = socket;
    socket.on("connect", () => {
      console.log("[Officer Map] Socket.IO connected. Joining admin_room...");
      socket.emit("join_admin", {});
    });
    socket.on("location_update", (data) => {
      console.log("[Officer Map] Real-time location_update received:", data);
      updateOrAddUserMarker({ ...data, is_live: true });
      if (data.is_restricted || data.risk_level === "CRITICAL" || data.risk_level === "HIGH" || data.alert_triggered) {
        if (window.SoundAlerts) window.SoundAlerts.play("geofence");
      }
    });
    socket.on("sos_triggered", (data) => {
      console.log("[Officer Map] Emergency SOS received:", data);
      if (window.SoundAlerts) window.SoundAlerts.play("sos");
      if (data && data.latitude && data.longitude) {
        updateOrAddUserMarker({ ...data, status: "SOS", risk_level: "CRITICAL", is_live: true });
      }
      loadSOSAlerts();
    });
    socket.on("new_alert", (data) => {
      console.log("[Officer Map] Real-time new_alert received:", data);
      const sev = (data.severity || data.risk_level || "").toUpperCase();
      if (window.SoundAlerts) {
        if (sev === "CRITICAL") {
          window.SoundAlerts.play("sos");
        } else {
          window.SoundAlerts.play("geofence");
        }
      }
    });
    socket.on("new_detection", (data) => {
      if (data && (data.intruder_count > 0 || data.unknown_count > 0 || (data.people && data.people.some(p => p.status !== "REGISTERED")))) {
        if (window.SoundAlerts) window.SoundAlerts.play("intrusion");
      }
    });
  } else {
    setTimeout(initOfficerSocket, 500);
  }
}

// -------------------------------------------------------------
// Registered People Management Table & Actions
// -------------------------------------------------------------
async function loadRegisteredPeople() {
  try {
    const res = await fetch("/api/registered-people");
    if (!res.ok) return;
    registeredPeopleList = await res.json();

    $("metric-visitors").textContent = registeredPeopleList.filter(v => (v.status || "Active").toLowerCase() === "active").length;
    const enrolled = registeredPeopleList.filter(v => v.face_registered || v.samples_count > 0).length;
    $("tel-enrolled").textContent = enrolled;

    filterPeopleTable();
  } catch (e) {
    console.warn("Failed to load registered people:", e);
  }
}

function filterPeopleTable() {
  const query = ($("registry-search") ? $("registry-search").value : "").toLowerCase().trim();
  const statusFilter = ($("registry-filter-status") ? $("registry-filter-status").value : "ALL").toUpperCase();

  const filtered = registeredPeopleList.filter(v => {
    const nameMatch = (v.name || "").toLowerCase().includes(query);
    const uidMatch = (v.unique_id || "").toLowerCase().includes(query);
    const matchesQuery = !query || nameMatch || uidMatch;

    const vStatus = (v.status || "Active").toUpperCase();
    let matchesStatus = true;
    if (statusFilter === "ACTIVE") matchesStatus = (vStatus === "ACTIVE");
    else if (statusFilter === "DISABLED") matchesStatus = (vStatus === "DISABLED");
    else if (statusFilter === "SOS") matchesStatus = (vStatus === "SOS");

    return matchesQuery && matchesStatus;
  });

  renderPeopleTable(filtered);
}

function renderPeopleTable(list) {
  const tbody = $("registrations-tbody");
  if (!tbody) return;

  if (!list || list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#6d786f; padding:24px;">No matching registered people found.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(v => {
    const statusVal = (v.status || "Active").trim();
    const isAct = statusVal.toLowerCase() === "active";
    const isDis = statusVal.toLowerCase() === "disabled";
    const isSOS = statusVal === "SOS";

    let statusBadgeClass = "status-active";
    if (isDis) statusBadgeClass = "status-disabled";
    else if (isSOS) statusBadgeClass = "status-sos";

    const samplesCount = v.samples_count || (v.face_registered ? 1 : 0);
    const hasPhoto = !!v.face_thumbnail;

    const photoCol = hasPhoto
      ? `<img src="${v.face_thumbnail}" alt="Face" class="table-avatar">`
      : `<div class="table-avatar-placeholder">👤</div>`;

    const gpsDisplay = (v.latitude && v.longitude && Number(v.latitude) !== 0)
      ? `${Number(v.latitude).toFixed(4)}, ${Number(v.longitude).toFixed(4)}`
      : "Pending GPS";

    return `
      <tr>
        <td>${photoCol}</td>
        <td><b>${escapeHtml(v.name)}</b></td>
        <td><code style="color:#19733b; font-weight:700;">${escapeHtml(v.unique_id)}</code></td>
        <td style="font-size:13px; color:#55665b;">
          <div>${escapeHtml(v.phone || '—')}</div>
          <small style="color:#809486;">${escapeHtml(v.email || '')}</small>
        </td>
        <td>
          <span class="badge-status ${samplesCount > 0 ? 'status-active' : 'status-unconf'}">
            ${samplesCount > 0 ? `📸 ${samplesCount} real photo${samplesCount > 1 ? 's' : ''}` : 'Standard Pass'}
          </span>
        </td>
        <td style="font-size:12px; color:#405246;">
          <div><b>${escapeHtml(v.current_zone || 'General Buffer')}</b></div>
          <small style="color:#77847b;">📍 ${gpsDisplay}</small>
        </td>
        <td><span class="badge-status ${statusBadgeClass}">${escapeHtml(statusVal)}</span></td>
        <td style="font-size:12px; color:#77847b;">${escapeHtml(v.registered_at || '—')}</td>
        <td style="text-align:right; white-space:nowrap;">
          <button type="button" class="btn-sm action-toggle" onclick="toggleVisitorStatus('${escapeHtml(v.unique_id)}')">
            ${isAct ? '⏸️ Disable' : '▶️ Enable'}
          </button>
          <button type="button" class="btn-sm action-delete" style="margin-left:6px;" onclick="openDeleteModal('${escapeHtml(v.unique_id)}', '${escapeHtml(v.name)}')">
            🗑️ Delete
          </button>
        </td>
      </tr>`;
  }).join("");
}

// -------------------------------------------------------------
// Deletion & Status Toggle Actions
// -------------------------------------------------------------
function openDeleteModal(uniqueId, name) {
  deleteTargetUid = uniqueId;
  deleteTargetName = name;
  $("delete-modal-name").textContent = name;
  $("delete-modal-uid").textContent = uniqueId;
  $("delete-modal").style.display = "flex";
}

function closeDeleteModal() {
  deleteTargetUid = null;
  deleteTargetName = "";
  $("delete-modal").style.display = "none";
}

async function executeDeleteVisitor() {
  if (!deleteTargetUid) return;
  const btn = $("btn-confirm-delete");
  btn.disabled = true;
  btn.textContent = "⏳ Purging Data & Disk Photos...";

  try {
    const res = await fetch(`/api/visitor/${encodeURIComponent(deleteTargetUid)}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Deletion failed");

    closeDeleteModal();
    await loadRegisteredPeople();
    alert(`Visitor ${deleteTargetUid} successfully deleted. Database record, embeddings, enrollment photos, and cache have been purged.`);
  } catch (e) {
    alert("Delete error: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "🗑️ Permanently Delete";
  }
}

async function toggleVisitorStatus(uniqueId) {
  try {
    const res = await fetch(`/api/visitor/${encodeURIComponent(uniqueId)}/toggle-status`, {
      method: "POST"
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Status update failed");

    await loadRegisteredPeople();
  } catch (e) {
    alert("Status toggle error: " + e.message);
  }
}

async function refreshRecognitionCache() {
  try {
    const res = await fetch("/api/refresh-cache", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Cache reload failed");

    alert(`Recognition cache successfully reloaded. Active enrolled identities: ${data.cached_identities}.`);
    await loadRegisteredPeople();
  } catch (e) {
    alert("Cache refresh error: " + e.message);
  }
}

let lastSeenSOSCount = -1;

async function loadSOSAlerts() {
  try {
    const res = await fetch("/api/sos-alerts");
    if (!res.ok) return;
    const alerts = await res.json();

    if (lastSeenSOSCount !== -1 && alerts.length > lastSeenSOSCount) {
      if (window.SoundAlerts) window.SoundAlerts.play("sos");
    }
    lastSeenSOSCount = alerts.length;

    $("metric-sos").textContent = alerts.length;
    const container = $("sos-alerts-container");
    if (!container) return;

    if (alerts.length === 0) {
      container.innerHTML = `<p style="color:#6d786f; margin:10px 0;">No emergency beacon alerts reported.</p>`;
      return;
    }

    container.innerHTML = alerts.map(a => {
      const hasVideo = !!a.video_filename;
      return `
        <div class="alert" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
          <div>
            <b style="color:#a32118; font-size:15px;">🚨 EMERGENCY SOS: ${escapeHtml(a.name)} [${escapeHtml(a.unique_id || 'ID?')}]</b>
            <div style="font-size:13px; color:#5f7365; margin-top:3px;">
              <b>Time:</b> ${a.timestamp} | <b>GPS:</b> Lat ${Number(a.latitude).toFixed(5)}, Lon ${Number(a.longitude).toFixed(5)}
            </div>
          </div>
          <div>
            ${hasVideo ? `
              <button type="button" class="primary" style="padding:6px 14px; font-size:13px;" onclick="openSOSModal('${escapeHtml(a.name)}', '${escapeHtml(a.timestamp)}', '${escapeHtml(a.video_filename)}')">
                ▶ Watch 5s Video
              </button>` : `<span style="font-size:12px; color:#888;">(Location Only)</span>`}
          </div>
        </div>`;
    }).join("");
  } catch (e) {}
}

async function loadSystemStats() {
  try {
    const res = await fetch("/api/dataset-stats");
    if (!res.ok) return;
    const data = await res.json();
    if (data.total_real_images) {
      $("metric-ai-status").textContent = "ForestFaceNet Active (100% Real)";
    }
  } catch (e) {}
}

async function resetPerimeterTracker() {
  if (!confirm("Reset perimeter object tracking state and alarm cooldowns?")) return;
  try {
    await fetch("/api/reset-tracker", { method: "POST" });
    alert("Perimeter tracker successfully reset.");
  } catch (e) {
    alert("Reset failed: " + e.message);
  }
}

function openSOSModal(name, time, videoFilename) {
  const modal = $("sos-modal");
  const meta = $("modal-sos-meta");
  const video = $("modal-sos-video");

  meta.textContent = `Visitor: ${name} • Recorded: ${time}`;
  video.src = `/static/uploads/sos/${videoFilename}`;
  modal.style.display = "flex";
  video.play().catch(() => {});
}

function closeSOSModal() {
  const modal = $("sos-modal");
  const video = $("modal-sos-video");
  video.pause();
  video.src = "";
  modal.style.display = "none";
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/[&<>"']/g, m => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[m]);
}
