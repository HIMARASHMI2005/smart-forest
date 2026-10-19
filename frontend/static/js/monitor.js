/**
 * monitor.js — Live AI Detection Monitor page.
 * Captures webcam frames, sends to /api/ai/detect, draws bounding boxes.
 */
(function () {
  Auth.requireLogin();

  const video      = document.getElementById("webcam-video");
  const canvas     = document.getElementById("detection-canvas");
  const overlay    = document.getElementById("camera-overlay");
  const startBtn   = document.getElementById("start-btn");
  const stopBtn    = document.getElementById("stop-btn");
  const snapBtn    = document.getElementById("snapshot-btn");
  const ctx        = canvas.getContext("2d");

  let stream        = null;
  let detectionLoop = null;
  let frameCount    = 0;
  let lastFpsTime   = Date.now();
  let currentLat    = null;
  let currentLon    = null;
  const DETECT_INTERVAL_MS = 1200;  // ~0.8 fps for server-side AI

  // --- Start Webcam ---
  startBtn.addEventListener("click", async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
      video.srcObject = stream;
      await video.play();
      overlay.style.display = "none";
      startBtn.disabled = true;
      stopBtn.disabled  = false;
      snapBtn.disabled  = false;
      document.getElementById("detect-status").textContent = "Active";
      document.getElementById("detect-status").className   = "status-badge badge-success";
      startDetectionLoop();
      acquireGPS();
    } catch (err) {
      Toast.error("Camera error: " + err.message);
    }
  });

  // --- Stop ---
  stopBtn.addEventListener("click", stopAll);

  function stopAll() {
    if (detectionLoop) clearInterval(detectionLoop);
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    startBtn.disabled = false;
    stopBtn.disabled  = true;
    snapBtn.disabled  = true;
    overlay.style.display = "flex";
    document.getElementById("detect-status").textContent = "Inactive";
    document.getElementById("detect-status").className   = "status-badge badge-inactive";
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  // --- Snapshot ---
  snapBtn.addEventListener("click", () => {
    const tmpCanvas = document.createElement("canvas");
    tmpCanvas.width  = video.videoWidth;
    tmpCanvas.height = video.videoHeight;
    tmpCanvas.getContext("2d").drawImage(video, 0, 0);
    const link = document.createElement("a");
    link.download = `sf_snapshot_${Date.now()}.jpg`;
    link.href = tmpCanvas.toDataURL("image/jpeg", 0.92);
    link.click();
  });

  // --- Detection Loop ---
  function startDetectionLoop() {
    detectionLoop = setInterval(runDetection, DETECT_INTERVAL_MS);
  }

  async function runDetection() {
    if (!stream || video.readyState < 2) return;

    // Capture frame
    const tmpCanvas = document.createElement("canvas");
    tmpCanvas.width  = video.videoWidth;
    tmpCanvas.height = video.videoHeight;
    tmpCanvas.getContext("2d").drawImage(video, 0, 0);
    const imageData = tmpCanvas.toDataURL("image/jpeg", 0.75);

    // FPS counter
    frameCount++;
    const now = Date.now();
    if (now - lastFpsTime >= 2000) {
      const fps = (frameCount / ((now - lastFpsTime) / 1000)).toFixed(1);
      document.getElementById("live-fps").textContent = fps;
      frameCount = 0;
      lastFpsTime = now;
    }

    try {
      const res = await API.post("/api/ai/detect", {
        image: imageData,
        latitude:  currentLat,
        longitude: currentLon
      });

      if (!res.success) return;

      const data = res.data;
      document.getElementById("live-person-count").textContent = data.person_count ?? 0;
      document.getElementById("model-status").textContent = data.model_trained ? "ForestPersonNet ✓" : "Not Trained";

      // Draw bounding boxes
      canvas.width  = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      drawBoundingBoxes(data.detections, canvas, ctx);

      // Update detection results panel
      renderDetectionResults(data);
      renderFaceResults(data.faces);
      renderRisk(data.risk, data.zone);

    } catch (e) {
      // Silently continue
    }
  }

  function drawBoundingBoxes(detections, canvas, ctx) {
    if (!detections || !detections.length) return;
    const scaleX = canvas.width / 640;
    const scaleY = canvas.height / 480;

    detections.forEach(det => {
      const [x1, y1, x2, y2] = (det.bbox || []).map((v, i) => i % 2 === 0 ? v * scaleX : v * scaleY);
      const className = det.class_name || det.class || "person";
      const color = className === "person" ? "#34d399" : "#f87171";
      ctx.strokeStyle = color;
      ctx.lineWidth   = 2.5;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.fillStyle = color + "cc";
      ctx.fillRect(x1, y1 - 22, 160, 22);
      ctx.fillStyle = "#000";
      ctx.font = "bold 12px Inter, sans-serif";
      ctx.fillText(`${className} ${(det.confidence * 100).toFixed(0)}%`, x1 + 5, y1 - 6);
    });
  }

  function renderDetectionResults(data) {
    const el = document.getElementById("detection-results");
    if (!el) return;
    if (!data.person_count) {
      el.innerHTML = `<p class="no-data-hint">No persons detected in current frame.</p>`;
      return;
    }
    el.innerHTML = `
      <div class="list-item">
        <div class="list-item-header">
          <span class="list-item-title">👥 ${data.person_count} Person(s) Detected</span>
          <span class="badge ${data.unknown_person_count > 0 ? 'badge-danger' : 'badge-success'}">
            ${data.unknown_person_count > 0 ? `${data.unknown_person_count} Unknown` : "All Identified"}
          </span>
        </div>
        <div class="list-item-meta">${data.detections?.length || 0} bounding boxes | Confidence: ${
          data.detections?.length ? (Math.max(...data.detections.map(d => d.confidence || 0)) * 100).toFixed(1) : 0
        }%</div>
      </div>
    `;
  }

  function renderFaceResults(faces) {
    const el = document.getElementById("face-results");
    if (!el || !faces) return;
    if (!faces.length) {
      el.innerHTML = `<p class="no-data-hint">No faces identified in current frame.</p>`;
      return;
    }
    el.innerHTML = faces.map(f => {
      const isKnown = f.status === "IDENTIFIED";
      return `<div class="list-item">
        <div class="list-item-header">
          <span class="list-item-title">${isKnown ? "✅" : "❓"} ${f.identity || "Unknown Person"}</span>
          <span class="badge ${isKnown ? 'badge-success' : 'badge-danger'}">${f.status || "?"}</span>
        </div>
        <div class="list-item-meta">Similarity: ${f.similarity_pct ?? "—"}%</div>
      </div>`;
    }).join("");
  }

  function renderRisk(risk, zone) {
    const liveAlerts = document.getElementById("live-alerts");
    if (!liveAlerts || !risk) return;
    if (risk.level === "LOW" && !risk.alert_triggered) {
      liveAlerts.innerHTML = `<p class="no-data-hint">No active alerts. Zone is safe.</p>`;
      return;
    }
    const colorMap = { LOW: "badge-success", MEDIUM: "badge-warn", HIGH: "badge-danger", CRITICAL: "badge-danger" };
    liveAlerts.innerHTML = `
      <div class="list-item">
        <div class="list-item-header">
          <span class="list-item-title">⚠️ Risk: ${risk.level}</span>
          <span class="badge ${colorMap[risk.level] || 'badge-info'}">${zone?.zone_name || "General Buffer"}</span>
        </div>
        <div class="list-item-meta">${risk.reasons?.join(" · ") || "Monitoring active"}</div>
      </div>
    `;
  }

  // --- GPS ---
  async function updateGeofenceDisplay(lat, lon) {
    try {
      const res = await API.post("/api/geofence/check", { latitude: lat, longitude: lon });
      if (res.success && res.data) {
        const zoneName = res.data.zone_name || "General Forest Buffer";
        const riskLevel = res.data.risk_level || "LOW";
        const zoneEl = document.getElementById("loc-zone");
        const riskEl = document.getElementById("loc-risk");
        if (zoneEl) zoneEl.textContent = zoneName;
        if (riskEl) {
          riskEl.textContent = riskLevel;
          const riskColors = { LOW: "#34d399", MEDIUM: "#fbbf24", HIGH: "#f87171", CRITICAL: "#c084fc" };
          riskEl.style.color = riskColors[riskLevel] || "#94a3b8";
        }
      }
    } catch (e) {
      console.warn("Geofence check error:", e);
    }
  }

  function acquireGPS() {
    if (!navigator.geolocation) return;
    navigator.geolocation.watchPosition(pos => {
      currentLat = pos.coords.latitude;
      currentLon = pos.coords.longitude;
      const latEl = document.getElementById("loc-lat");
      const lonEl = document.getElementById("loc-lon");
      if (latEl) latEl.textContent = currentLat.toFixed(6);
      if (lonEl) lonEl.textContent = currentLon.toFixed(6);
      updateGeofenceDisplay(currentLat, currentLon);
    }, null, { enableHighAccuracy: true });
  }

  // --- Get Location Button ---
  document.getElementById("get-location-btn")?.addEventListener("click", () => {
    navigator.geolocation.getCurrentPosition(async pos => {
      currentLat = pos.coords.latitude;
      currentLon = pos.coords.longitude;
      const latEl = document.getElementById("loc-lat");
      const lonEl = document.getElementById("loc-lon");
      if (latEl) latEl.textContent = currentLat.toFixed(6);
      if (lonEl) lonEl.textContent = currentLon.toFixed(6);
      await updateGeofenceDisplay(currentLat, currentLon);
      Toast.info("GPS coordinates & forest zone updated.");
    }, () => Toast.error("GPS access denied."));
  });

  // --- AI Status ---
  API.get("/api/ai/status").then(res => {
    if (res.success) {
      const pd = res.data.person_detector;
      document.getElementById("model-status").textContent =
        pd.status === "TRAINED" ? "ForestPersonNet ✓" : "Not Trained Yet";
    }
  }).catch(() => {});
})();
