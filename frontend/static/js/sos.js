/**
 * sos.js — Emergency SOS page logic.
 */
(function () {
  Auth.requireLogin();

  let sosLat = null;
  let sosLon = null;
  let sosHoldTimer = null;

  // Emergency type buttons
  document.querySelectorAll(".emergency-type-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".emergency-type-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("sos-type").value = btn.dataset.type;
    });
  });

  // Get GPS Location
  document.getElementById("get-sos-location-btn").addEventListener("click", acquireLocation);
  acquireLocation(); // Auto-acquire on page load

  function acquireLocation() {
    if (!navigator.geolocation) {
      Toast.error("Geolocation not supported."); return;
    }
    const statusEl = document.getElementById("sos-gps-status");
    statusEl.textContent = "Acquiring...";
    statusEl.className = "status-badge badge-warn";

    navigator.geolocation.getCurrentPosition(pos => {
      sosLat = pos.coords.latitude;
      sosLon = pos.coords.longitude;
      document.getElementById("sos-lat").value = sosLat;
      document.getElementById("sos-lon").value = sosLon;
      document.getElementById("sos-lat-display").textContent = `Lat: ${sosLat.toFixed(6)}`;
      document.getElementById("sos-lon-display").textContent = `Lon: ${sosLon.toFixed(6)}`;
      statusEl.textContent = "✅ Acquired";
      statusEl.className = "status-badge badge-success";
    }, () => {
      statusEl.textContent = "❌ Failed";
      statusEl.className = "status-badge badge-danger";
      Toast.error("Could not get GPS location. Enable permissions.");
    });
  }

  // Big SOS button — hold 2 seconds
  const sosBtn = document.getElementById("main-sos-btn");
  let holdProgress = 0;

  sosBtn.addEventListener("pointerdown", () => {
    holdProgress = 0;
    sosBtn.querySelector(".sos-btn-sub").textContent = "Hold to confirm...";
    sosHoldTimer = setInterval(() => {
      holdProgress += 100;
      if (holdProgress >= 2000) {
        clearInterval(sosHoldTimer);
        triggerSOS();
      }
    }, 100);
  });

  ["pointerup", "pointerleave", "pointercancel"].forEach(ev => {
    sosBtn.addEventListener(ev, () => {
      if (sosHoldTimer) {
        clearInterval(sosHoldTimer);
        sosHoldTimer = null;
        sosBtn.querySelector(".sos-btn-sub").textContent = "Hold 2 seconds to confirm";
      }
    });
  });

  async function triggerSOS() {
    const errEl     = document.getElementById("sos-error");
    const resultEl  = document.getElementById("sos-result");
    errEl.classList.add("hidden");
    resultEl.classList.add("hidden");

    if (!sosLat || !sosLon) {
      errEl.textContent = "GPS coordinates required. Click Get My Location first.";
      errEl.classList.remove("hidden");
      return;
    }

    const emergencyType = document.getElementById("sos-type").value;
    const message       = document.getElementById("sos-message").value.trim();

    sosBtn.disabled = true;
    sosBtn.querySelector(".sos-btn-label").textContent = "SENDING...";

    try {
      const res = await API.post("/api/sos/trigger", {
        latitude: sosLat,
        longitude: sosLon,
        emergency_type: emergencyType,
        message
      });

      if (res.success) {
        resultEl.textContent = "✅ SOS sent! Help is on the way. Stay calm and visible.";
        resultEl.classList.remove("hidden");
        Toast.error("🆘 SOS sent! Emergency services notified.", 8000);
        document.getElementById("sos-message").value = "";
        loadSOSHistory();
      } else {
        errEl.textContent = res.message || "SOS failed.";
        errEl.classList.remove("hidden");
      }
    } catch(e) {
      errEl.textContent = "Network error. Are you connected?";
      errEl.classList.remove("hidden");
    }

    sosBtn.disabled = false;
    sosBtn.querySelector(".sos-btn-label").textContent = "SEND SOS";
    sosBtn.querySelector(".sos-btn-sub").textContent = "Hold 2 seconds to confirm";
  }

  // SOS History
  async function loadSOSHistory() {
    const list = document.getElementById("sos-history-list");
    if (!list) return;
    try {
      const res = await API.get("/api/sos/my-events");
      if (!res.success || !res.data.sos_events?.length) {
        list.innerHTML = `<p class="no-data-hint">No SOS events yet.</p>`;
        return;
      }
      list.innerHTML = res.data.sos_events.map(s => {
        const statusColor = { OPEN: "badge-danger", ACKNOWLEDGED: "badge-warn", RESOLVED: "badge-success" };
        return `<div class="list-item">
          <div class="list-item-header">
            <span class="list-item-title">🆘 ${s.emergency_type || "OTHER"}</span>
            <span class="badge ${statusColor[s.status] || 'badge-info'}">${s.status}</span>
          </div>
          <div class="list-item-meta">${s.message || ""}</div>
          <div class="list-item-meta" style="color:var(--text-muted)">${s.created_at || ""}</div>
        </div>`;
      }).join("");
    } catch(e) {}
  }

  loadSOSHistory();
})();
