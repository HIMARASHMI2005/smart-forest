/**
 * app.js — Global initialization: navbar, auth state rendering,
 * SocketIO SOS/alert listeners.
 */
document.addEventListener("DOMContentLoaded", () => {
  renderNavAuth();
  initNavHamburger();
  initSocketIO();
});

// --- Navbar Auth State ---
function renderNavAuth() {
  const group = document.getElementById("nav-auth-group");
  if (!group) return;
  const user = Auth.getUser();

  if (Auth.isLoggedIn() && user) {
    group.innerHTML = `
      <span style="color:var(--text-secondary); font-size:0.82rem; margin-right:4px;">👤 ${user.name.split(" ")[0]}</span>
      ${user.role === "ADMIN" ? '<a href="/admin" class="nav-link">Admin</a>' : ""}
      <a href="${user.role === "ADMIN" ? "/officer" : "/officer"}" class="nav-link">Command Dashboard</a>
      <a href="/profile" class="nav-link">Profile</a>
      <button class="btn btn-outline btn-sm" onclick="Auth.logout()">Logout</button>
    `;
  } else {
    group.innerHTML = `
      <a href="/login"    class="nav-link">Sign In</a>
      <a href="/register" class="btn btn-primary btn-sm">Register</a>
    `;
  }
}

// --- Hamburger ---
function initNavHamburger() {
  const btn   = document.getElementById("nav-hamburger");
  const links = document.getElementById("nav-links");
  if (!btn || !links) return;
  btn.addEventListener("click", () => links.classList.toggle("open"));
}

// --- SocketIO Global Listeners ---
function initSocketIO() {
  try {
    const socket = io({ transports: ["websocket", "polling"] });

    socket.on("connect", () => {
      console.log("[SocketIO] Connected:", socket.id);
      const statusEl = document.getElementById("socket-status");
      if (statusEl) statusEl.textContent = "Live — Connected";
      if (Auth.isLoggedIn()) socket.emit("join_admin");
    });

    socket.on("disconnect", () => {
      const statusEl = document.getElementById("socket-status");
      if (statusEl) statusEl.textContent = "Disconnected";
    });

    socket.on("sos_triggered", (data) => {
      if (window.SoundAlerts) {
        window.SoundAlerts.play("sos");
      }
      const overlay = document.getElementById("sos-overlay");
      const title   = document.getElementById("sos-overlay-title");
      const msg     = document.getElementById("sos-overlay-msg");
      if (overlay) {
        title.textContent = `🆘 SOS — ${data.emergency_type || "EMERGENCY"}`;
        msg.textContent   = `${data.message || "Emergency triggered!"} | ${data.user_name || ""}`;
        overlay.classList.remove("hidden");
      }
      Toast.error(`🆘 SOS ALERT: ${data.message || "Emergency!"}`, 10000);
    });

    socket.on("new_alert", (data) => {
      const severity = (data.severity || data.risk_level || "MEDIUM").toUpperCase();
      const msg = data.message || "New forest alert!";
      if (window.SoundAlerts) {
        if (severity === "CRITICAL") {
          window.SoundAlerts.play("sos");
        } else {
          window.SoundAlerts.play("geofence");
        }
      }
      if (severity === "CRITICAL" || severity === "HIGH") {
        Toast.error(`⚠️ ${msg}`, 7000);
      } else {
        Toast.warn(`⚠️ ${msg}`, 5000);
      }
    });

    socket.on("new_detection", (data) => {
      if (data && (data.intruder_count > 0 || data.unknown_count > 0)) {
        if (window.SoundAlerts) window.SoundAlerts.play("intrusion");
      }
      const countEl = document.getElementById("hero-persons");
      if (countEl && data.person_count !== undefined) {
        countEl.textContent = data.person_count;
      }
    });

    // Store socket globally for page-specific modules
    window._sfSocket = socket;
  } catch (e) {
    console.warn("[SocketIO] Could not connect:", e.message);
  }
}
