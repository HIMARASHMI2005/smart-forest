/**
 * admin.js — Admin Command Center dashboard.
 * Loads stats, SOS events, alerts, detections, users.
 * Listens to SocketIO for real-time updates.
 */
(function () {
  Auth.requireAdmin();

  // Initial data load
  loadStats();
  loadSOSEvents();
  loadAlerts();
  loadDetections();
  loadUsers();

  // Refresh every 30 seconds
  setInterval(() => { loadStats(); }, 30000);

  // SocketIO admin listeners
  const socket = window._sfSocket;
  if (socket) {
    socket.on("sos_triggered", () => { loadSOSEvents(); loadStats(); });
    socket.on("new_alert", () => { loadAlerts(); loadStats(); });
    socket.on("new_detection", () => { loadDetections(); loadStats(); });
  }

  async function loadStats() {
    try {
      const res = await API.get("/api/admin/stats");
      if (!res.success) return;
      const d = res.data;
      document.getElementById("stat-users").textContent      = d.total_users ?? "—";
      document.getElementById("stat-alerts").textContent     = d.active_alerts ?? "—";
      document.getElementById("stat-sos").textContent        = d.open_sos_events ?? "—";
      document.getElementById("stat-zones").textContent      = d.active_zones ?? "—";
      document.getElementById("stat-detections").textContent = d.total_detections ?? "—";
      document.getElementById("stat-unknown").textContent    = d.unknown_detections ?? "—";
    } catch(e) {}
  }

  async function loadSOSEvents() {
    const panel = document.getElementById("sos-panel");
    try {
      const res = await API.get("/api/admin/sos");
      if (!res.success || !res.data.sos_events?.length) {
        panel.innerHTML = `<p class="no-data-hint">No SOS events.</p>`; return;
      }
      panel.innerHTML = res.data.sos_events.slice(0, 10).map(s => {
        const statusColor = { OPEN: "badge-danger", ACKNOWLEDGED: "badge-warn", RESOLVED: "badge-success" };
        return `<div class="list-item">
          <div class="list-item-header">
            <span class="list-item-title">🆘 ${s.emergency_type || "?"} — ${s.user_name || "Unknown User"}</span>
            <span class="badge ${statusColor[s.status] || 'badge-info'}">${s.status}</span>
          </div>
          <div class="list-item-meta">${s.message || ""}</div>
          <div class="list-item-meta" style="color:var(--text-muted)">${s.created_at || ""}</div>
          <div class="action-btns">
            ${s.status === "OPEN" ? `<button class="btn btn-warn btn-sm" onclick="ackSOS(${s.id})">✔ Acknowledge</button>` : ""}
            ${s.status !== "RESOLVED" ? `<button class="btn btn-sm btn-outline" onclick="resolveSOS(${s.id})">✅ Resolve</button>` : ""}
          </div>
        </div>`;
      }).join("");
    } catch(e) { panel.innerHTML = `<p class="no-data-hint">Could not load SOS events.</p>`; }
  }
  window.loadSOSEvents = loadSOSEvents;

  window.ackSOS = async function(id) {
    await API.put(`/api/admin/sos/${id}/acknowledge`);
    Toast.success("SOS acknowledged."); loadSOSEvents(); loadStats();
  };
  window.resolveSOS = async function(id) {
    await API.put(`/api/admin/sos/${id}/resolve`);
    Toast.success("SOS resolved."); loadSOSEvents(); loadStats();
  };

  async function loadAlerts() {
    const panel = document.getElementById("alerts-panel");
    try {
      const res = await API.get("/api/admin/alerts?status=ACTIVE");
      if (!res.success || !res.data.alerts?.length) {
        panel.innerHTML = `<p class="no-data-hint">No active alerts.</p>`; return;
      }
      const sevColor = { CRITICAL: "#f87171", HIGH: "#fb923c", MEDIUM: "#fbbf24", LOW: "#34d399" };
      panel.innerHTML = res.data.alerts.slice(0, 15).map(a => `
        <div class="list-item">
          <div class="list-item-header">
            <span class="list-item-title">${a.alert_type?.replace("_", " ")}</span>
            <span class="badge" style="color:${sevColor[a.severity]||'#94a3b8'};background:${sevColor[a.severity]||'#94a3b8'}22">${a.severity}</span>
          </div>
          <div class="list-item-meta">${a.message || ""}</div>
          <div class="action-btns">
            <button class="btn btn-sm btn-outline" onclick="resolveAlert(${a.id})">✅ Resolve</button>
            <button class="btn btn-sm btn-outline" onclick="ackAlert(${a.id})">✔ Ack</button>
          </div>
        </div>
      `).join("");
    } catch(e) { panel.innerHTML = `<p class="no-data-hint">Could not load alerts.</p>`; }
  }
  window.loadAlerts = loadAlerts;
  window.resolveAlert = async function(id) {
    await API.put(`/api/admin/alerts/${id}/resolve`);
    Toast.success("Alert resolved."); loadAlerts(); loadStats();
  };
  window.ackAlert = async function(id) {
    await API.put(`/api/admin/alerts/${id}/acknowledge`);
    Toast.info("Alert acknowledged."); loadAlerts();
  };

  async function loadDetections() {
    const panel = document.getElementById("detections-panel");
    try {
      const res = await API.get("/api/admin/detections");
      if (!res.success || !res.data.detections?.length) {
        panel.innerHTML = `<p class="no-data-hint">No detections yet.</p>`; return;
      }
      panel.innerHTML = res.data.detections.slice(0, 15).map(d => `
        <div class="list-item">
          <div class="list-item-header">
            <span class="list-item-title">👥 ${d.person_count} Person(s)</span>
            <span class="badge ${d.is_unknown ? 'badge-danger' : 'badge-success'}">${d.is_unknown ? "Unknown" : "Identified"}</span>
          </div>
          <div class="list-item-meta">Confidence: ${d.confidence ? (d.confidence*100).toFixed(1)+"%" : "—"}</div>
          <div class="list-item-meta" style="color:var(--text-muted)">${d.timestamp || ""}</div>
        </div>
      `).join("");
    } catch(e) { panel.innerHTML = `<p class="no-data-hint">Could not load detections.</p>`; }
  }
  window.loadDetections = loadDetections;

  async function loadUsers() {
    const panel = document.getElementById("users-panel");
    try {
      const res = await API.get("/api/admin/users");
      if (!res.success || !res.data.users?.length) {
        panel.innerHTML = `<p class="no-data-hint">No users found.</p>`; return;
      }
      panel.innerHTML = res.data.users.slice(0, 20).map(u => `
        <div class="list-item">
          <div class="list-item-header">
            <span class="list-item-title">${u.name}</span>
            <span class="badge ${u.role === "ADMIN" ? "badge-warn" : "badge-info"}">${u.role}</span>
          </div>
          <div class="list-item-meta">${u.email} · ${u.phone}</div>
          <div class="list-item-meta" style="color:${u.has_face_registered ? 'var(--green-400)' : 'var(--text-muted)'}">
            ${u.has_face_registered ? "✅ Face Registered" : "❌ No Face"}
          </div>
        </div>
      `).join("");
    } catch(e) { panel.innerHTML = `<p class="no-data-hint">Could not load users.</p>`; }
  }
  window.loadUsers = loadUsers;
})();
