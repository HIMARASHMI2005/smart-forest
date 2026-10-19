/**
 * Toast notification system.
 */
const Toast = (() => {
  let container;

  function getContainer() {
    if (!container) container = document.getElementById("toast-container");
    return container;
  }

  function show(message, type = "info", duration = 4000) {
    const c = getContainer();
    if (!c) return;
    const t = document.createElement("div");
    t.className = `toast toast-${type}`;
    t.textContent = message;
    c.appendChild(t);
    setTimeout(() => {
      t.style.opacity = "0";
      t.style.transform = "translateX(120%)";
      t.style.transition = "all 0.3s";
      setTimeout(() => t.remove(), 350);
    }, duration);
  }

  return {
    success: (msg, ms = 3500) => show(msg, "success", ms),
    error:   (msg, ms = 5000) => show(msg, "error",   ms),
    warn:    (msg, ms = 4000) => show(msg, "warn",    ms),
    info:    (msg, ms = 3500) => show(msg, "info",    ms),
  };
})();
