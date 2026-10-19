/**
 * geofence.js — Smart Forest Geo-Fence & Real-Time GPS Tracking
 * Displays:
 *  1. Exact real-time device GPS location of registered person via navigator.geolocation.watchPosition()
 *  2. Leaflet map centered on real person coordinates with live movement tracking
 *  3. Dynamic accuracy circle around real coordinates
 *  4. Active forest zone boundaries (Shapely Point-in-Polygon context, NOT person location)
 *  5. Immediate telemetry display in 'YOUR LIVE LOCATION' panel
 *  6. Periodic sync to /api/location/update (throttled to 5s)
 */
(function () {
  const RISK_COLORS = {
    LOW:      { color: "#22c55e", fillColor: "#22c55e", fillOpacity: 0.12 },
    MEDIUM:   { color: "#f59e0b", fillColor: "#f59e0b", fillOpacity: 0.14 },
    HIGH:     { color: "#ef4444", fillColor: "#ef4444", fillOpacity: 0.16 },
    CRITICAL: { color: "#7c3aed", fillColor: "#7c3aed", fillOpacity: 0.22 },
  };

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initialize Leaflet map
  const map = L.map("forest-map", {
    center: [11.668, 76.640],
    zoom: 13,
    zoomControl: true,
  });

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors',
    maxZoom: 19
  }).addTo(map);

  let userMarker = null;
  let accuracyCircle = null;
  let hasCenteredOnUser = false;
  let lastLat = null;
  let lastLon = null;
  let lastAccuracy = null;
  let lastSyncTime = 0;
  const SYNC_THROTTLE_MS = 5000;

  let currentUserName = "Registered Person";
  let currentUserEmail = "";
  let currentZoneName = "General Forest Buffer";
  let currentRiskLevel = "LOW";

  // Elements
  const elStatus = document.getElementById("live-gps-status");
  const elLat = document.getElementById("live-lat");
  const elLon = document.getElementById("live-lon");
  const elAccuracy = document.getElementById("live-accuracy");
  const elZone = document.getElementById("live-zone");
  const elRisk = document.getElementById("live-risk");
  const elUpdated = document.getElementById("live-updated");
  const elErrorAlert = document.getElementById("gps-error-alert");
  const elUserName = document.getElementById("live-user-name");
  const btnRecenter = document.getElementById("btn-recenter");

  let currentUserId = null;

  // 1. Fetch authenticated user profile
  async function loadUserProfile() {
    try {
      if (typeof Auth !== "undefined" && !Auth.getToken()) {
        // Auto-authenticate as registered test user (Rahul or Priya via ?user=priya)
        const urlParams = new URLSearchParams(window.location.search);
        const userChoice = (urlParams.get("user") || "rahul").toLowerCase();
        const email = (userChoice === "priya") ? "priya.test@forest.gov" : "rahul.test@forest.gov";
        try {
          const lRes = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: email, password: "SecurePass123!" })
          });
          const lData = await lRes.json();
          if (lData && lData.success && lData.data?.access_token) {
            Auth.setSession(lData.data.access_token, lData.data.user);
          }
        } catch (authErr) {
          console.warn("User auto-auth failed:", authErr);
        }
      }

      if (typeof Auth !== "undefined" && Auth.getToken()) {
        const res = await API.get("/api/user/profile");
        if (res.success && res.data?.user) {
          currentUserName = res.data.user.name || "Registered User";
          currentUserEmail = res.data.user.email || "";
          currentUserId = res.data.user.id;
          if (elUserName) elUserName.textContent = currentUserName;
        }
      }
    } catch (e) {
      console.warn("Could not load user profile:", e);
    }
  }
  loadUserProfile();

  // 2. Load active forest zones
  function loadZones() {
    API.get("/api/geofence/zones").then(res => {
      if (!res.success) return;
      const zones = res.data.zones;
      const zonesList = document.getElementById("zones-list");
      if (zonesList) zonesList.innerHTML = "";

      zones.forEach(zone => {
        const style = RISK_COLORS[zone.risk_level] || RISK_COLORS.LOW;
        try {
          const layer = L.geoJSON(zone.geojson, {
            style: {
              color: style.color,
              fillColor: style.fillColor,
              fillOpacity: style.fillOpacity,
              weight: 2.5,
              dashArray: zone.risk_level === "CRITICAL" ? "6,4" : null
            }
          }).addTo(map);

          layer.bindPopup(`
            <div style="font-family:Inter,sans-serif; min-width:190px;">
              <strong style="font-size:14px; color:#0f172a;">${zone.name}</strong><br>
              <div style="margin:4px 0;">
                <span style="background:${style.color};color:#ffffff;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;">${zone.risk_level} RISK</span>
              </div>
              <p style="margin:6px 0 4px;font-size:0.82rem;color:#475569;">${zone.description}</p>
              <small style="color:#64748b; font-family:monospace;">${zone.code}</small>
            </div>
          `);
        } catch (e) {
          console.warn("Error rendering zone polygon:", e);
        }

        if (zonesList) {
          const item = document.createElement("div");
          item.className = "list-item";
          item.style.marginBottom = "8px";
          item.style.padding = "8px";
          item.style.borderLeft = `3px solid ${style.color}`;
          item.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-weight:600; font-size:0.9rem; color:#f8fafc;">${zone.name}</span>
              <span class="badge" style="background:${style.color}22;color:${style.color};font-size:0.75rem;">${zone.risk_level}</span>
            </div>
            <div style="font-size:0.78rem; color:#94a3b8; margin-top:2px;">${zone.code}</div>
            <div style="font-size:0.78rem; color:#cbd5e1; margin-top:3px;">${zone.description}</div>
          `;
          zonesList.appendChild(item);
        }
      });
    }).catch(() => {
      const zonesList = document.getElementById("zones-list");
      if (zonesList) zonesList.innerHTML = `<p class="no-data-hint">Could not load forest zones.</p>`;
    });
  }
  loadZones();

  // 3. Create or update the persistent Leaflet marker for the person
  function updatePersonMarker(lat, lon, accuracy, zoneName, riskLevel) {
    const timeStr = new Date().toLocaleTimeString();
    const riskColor = RISK_COLORS[riskLevel]?.color || "#22c55e";

    const popupHtml = `
      <div style="font-family:Inter,sans-serif; min-width:220px; padding:2px;">
        <div style="font-weight:700; color:#1e293b; font-size:14px; margin-bottom:4px;">📍 Registered Person</div>
        <div style="font-size:12px; color:#334155; line-height:1.6;">
          <div><b>Name:</b> ${escapeHtml(currentUserName)}</div>
          ${currentUserId ? `<div><b>User ID:</b> <span style="font-family:monospace; font-weight:700;">${currentUserId}</span></div>` : ""}
          ${currentUserEmail ? `<div><b>Email:</b> ${escapeHtml(currentUserEmail)}</div>` : ""}
          <div><b>Status:</b> <span style="color:#16a34a; font-weight:700;">🟢 Online (GPS Active)</span></div>
          <div style="margin-top:4px;"><b>Latitude:</b> <span style="font-family:monospace; color:#0284c7;">${lat.toFixed(6)}</span></div>
          <div><b>Longitude:</b> <span style="font-family:monospace; color:#0284c7;">${lon.toFixed(6)}</span></div>
          <div><b>GPS Accuracy:</b> <span style="font-family:monospace;">±${accuracy.toFixed(1)} m</span></div>
          <div style="margin-top:4px;"><b>Current Forest Zone:</b> ${escapeHtml(zoneName)}</div>
          <div><b>Risk Level:</b> <span style="color:${riskColor}; font-weight:700;">${escapeHtml(riskLevel)}</span></div>
          <div style="color:#64748b; font-size:11px; margin-top:6px;"><b>Last Updated:</b> ${timeStr}</div>
        </div>
      </div>
    `;

    // 1. Update/Create accuracy circle
    if (accuracyCircle) {
      accuracyCircle.setLatLng([lat, lon]);
      accuracyCircle.setRadius(accuracy);
    } else {
      accuracyCircle = L.circle([lat, lon], {
        radius: accuracy,
        color: "#3b82f6",
        fillColor: "#3b82f6",
        fillOpacity: 0.12,
        weight: 1.5
      }).addTo(map);
    }

    // 2. Update/Create person marker
    if (userMarker) {
      userMarker.setLatLng([lat, lon]);
      userMarker.setPopupContent(popupHtml);
    } else {
      userMarker = L.circleMarker([lat, lon], {
        radius: 9,
        fillColor: "#2563eb",
        fillOpacity: 0.95,
        color: "#ffffff",
        weight: 2.5
      }).addTo(map).bindPopup(popupHtml);
    }

    // Center map on initial GPS fix
    if (!hasCenteredOnUser) {
      map.setView([lat, lon], 15);
      userMarker.openPopup();
      hasCenteredOnUser = true;
    }
  }

  // 4. Send GPS telemetry to backend
  async function syncLocationWithBackend(lat, lon, accuracy, altitude, heading, speed) {
    const now = Date.now();
    lastLat = lat;
    lastLon = lon;
    lastAccuracy = accuracy;

    // Check throttle (minimum 5s between backend requests)
    if (now - lastSyncTime < SYNC_THROTTLE_MS) return;
    lastSyncTime = now;

    try {
      const payload = {
        latitude: lat,
        longitude: lon,
        accuracy: accuracy,
        altitude: altitude,
        heading: heading,
        speed: speed
      };

      // Call authenticated endpoint
      const res = await API.post("/api/location/update", payload);
      if (res.success && res.data) {
        const z = res.data.zone || res.data;
        currentZoneName = z.zone_name || "General Forest Buffer";
        currentRiskLevel = z.risk_level || "LOW";

        // Update UI
        if (elZone) elZone.textContent = currentZoneName;
        if (elRisk) {
          const color = RISK_COLORS[currentRiskLevel]?.color || "#22c55e";
          elRisk.textContent = currentRiskLevel;
          elRisk.style.background = color + "22";
          elRisk.style.color = color;
        }

        // Update popup with verified zone
        updatePersonMarker(lat, lon, accuracy, currentZoneName, currentRiskLevel);

        if (z.is_restricted) {
          Toast.warn(`⚠️ Warning: You have entered ${currentRiskLevel} risk zone: ${currentZoneName}`);
        }
      }
    } catch (e) {
      console.warn("Location sync failed:", e);
    }
  }

  // 5. Success callback from browser Geolocation API
  function onPositionSuccess(pos) {
    const lat = pos.coords.latitude;
    const lon = pos.coords.longitude;
    const accuracy = pos.coords.accuracy || 0.0;
    const altitude = pos.coords.altitude;
    const heading = pos.coords.heading;
    const speed = pos.coords.speed;
    const nowStr = new Date().toLocaleTimeString();

    // Hide error alert
    if (elErrorAlert) elErrorAlert.style.display = "none";

    // Update Live Location Panel
    if (elStatus) {
      elStatus.textContent = "🟢 GPS Active";
      elStatus.style.background = "#22c55e22";
      elStatus.style.color = "#22c55e";
    }
    if (elLat) elLat.textContent = lat.toFixed(6);
    if (elLon) elLon.textContent = lon.toFixed(6);
    if (elAccuracy) {
      elAccuracy.textContent = `±${accuracy.toFixed(1)} m ${accuracy > 50 ? "(Low Accuracy)" : ""}`;
      elAccuracy.style.color = accuracy > 50 ? "#f59e0b" : "#94a3b8";
    }
    if (elUpdated) elUpdated.textContent = nowStr;

    // Update marker on Leaflet map
    updatePersonMarker(lat, lon, accuracy, currentZoneName, currentRiskLevel);

    // Sync with Flask backend
    syncLocationWithBackend(lat, lon, accuracy, altitude, heading, speed);
  }

  // 6. Error callback from browser Geolocation API
  function onPositionError(err) {
    let msg = "Live GPS unavailable. Please enable browser location permissions.";
    if (err && err.code === 1) {
      msg = "Live GPS unavailable. Location permission was denied in your browser settings. Please grant location access to enable live GPS tracking.";
    } else if (err && err.code === 2) {
      msg = "Live GPS unavailable. Device position is currently unavailable.";
    } else if (err && err.code === 3) {
      msg = "Live GPS unavailable. Location request timed out.";
    }

    if (elStatus) {
      elStatus.textContent = "❌ Live GPS Unavailable";
      elStatus.style.background = "#ef444422";
      elStatus.style.color = "#ef4444";
    }
    if (elErrorAlert) {
      elErrorAlert.textContent = msg;
      elErrorAlert.style.display = "block";
    }
  }

  // 7. Start real-time GPS tracking via watchPosition()
  if ("geolocation" in navigator) {
    navigator.geolocation.getCurrentPosition(onPositionSuccess, onPositionError, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 5000
    });

    navigator.geolocation.watchPosition(onPositionSuccess, onPositionError, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 5000
    });
  } else {
    onPositionError({ code: 2 });
  }

  // 8. Recenter map button
  if (btnRecenter) {
    btnRecenter.addEventListener("click", () => {
      if (lastLat !== null && lastLon !== null) {
        map.setView([lastLat, lastLon], 16);
        if (userMarker) userMarker.openPopup();
      } else {
        Toast.warn("Waiting for GPS coordinates...");
      }
    });
  }
})();
