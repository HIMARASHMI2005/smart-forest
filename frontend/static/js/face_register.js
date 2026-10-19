/**
 * face_register.js — Face registration page webcam capture and API submission.
 */
(function () {
  Auth.requireLogin();

  const video      = document.getElementById("face-video");
  const canvas     = document.getElementById("face-canvas");
  const faceOvr    = document.getElementById("face-camera-overlay");
  const startBtn   = document.getElementById("start-face-cam-btn");
  const captureBtn = document.getElementById("capture-register-btn");
  const stopBtn    = document.getElementById("stop-face-cam-btn");
  const resultEl   = document.getElementById("face-reg-result");
  const errorEl    = document.getElementById("face-reg-error");
  let stream       = null;
  let sampleCount  = 0;

  // Load AI model status
  API.get("/api/ai/status").then(res => {
    if (res.success) {
      const fi = res.data.face_identifier;
      document.getElementById("face-model-status").textContent = fi.status === "TRAINED" ? "✅ Trained" : "❌ Not Trained";
      document.getElementById("face-model-status").className = `badge ${fi.status === "TRAINED" ? "badge-success" : "badge-danger"}`;
    }
  }).catch(() => {});

  // Start Camera
  startBtn.addEventListener("click", async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: 480, height: 360, facingMode: "user" }, audio: false });
      video.srcObject = stream;
      await video.play();
      faceOvr.style.pointerEvents = "none";
      faceOvr.style.opacity = "0.3";
      startBtn.disabled   = true;
      captureBtn.disabled = false;
      stopBtn.disabled    = false;
    } catch(err) {
      Toast.error("Camera error: " + err.message);
    }
  });

  // Stop Camera
  stopBtn.addEventListener("click", () => {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    startBtn.disabled   = false;
    captureBtn.disabled = true;
    stopBtn.disabled    = true;
    faceOvr.style.opacity = "1";
  });

  // Capture & Register
  captureBtn.addEventListener("click", async () => {
    if (!stream || video.readyState < 2) {
      Toast.warn("Camera not ready."); return;
    }

    // Capture frame
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const imageData = canvas.toDataURL("image/jpeg", 0.92);

    captureBtn.disabled = true;
    captureBtn.textContent = "⏳ Registering...";
    resultEl.classList.add("hidden");
    errorEl.classList.add("hidden");

    try {
      const res = await API.post("/api/ai/register-face", { image: imageData });
      if (res.success) {
        sampleCount = res.data.samples_count;
        document.getElementById("samples-count").textContent = sampleCount;
        document.getElementById("samples-count").className  = "badge badge-success";
        document.getElementById("registration-status").textContent = "Registered ✅";
        document.getElementById("registration-status").className = "badge badge-success";
        resultEl.textContent = `✅ Sample ${sampleCount} registered! ${sampleCount < 3 ? "Capture more for better accuracy." : "Face profile complete."}`;
        resultEl.classList.remove("hidden");
        Toast.success(`Face sample ${sampleCount} saved!`);
      } else {
        errorEl.textContent = res.message || "Registration failed.";
        errorEl.classList.remove("hidden");
        Toast.error(res.message || "Registration failed.");
      }
    } catch(e) {
      errorEl.textContent = "Network error.";
      errorEl.classList.remove("hidden");
    }

    captureBtn.disabled = false;
    captureBtn.textContent = "✅ Capture & Register";
  });
})();
