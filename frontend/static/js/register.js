const $ = id => document.getElementById(id);
let currentRegistration = null;
let gpsWatchId = null;
let currentCoordinates = { lat: 0, lon: 0 };
let faceStream = null;
let capturedPhotos = []; // Array of base64 data URLs (target: 3–5 real photos)

// Utility: HTML escape
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
}

document.addEventListener("DOMContentLoaded", () => {
    // Check for saved session (JWT-based or legacy)
    const savedToken = localStorage.getItem("forest_access_token");
    const savedUser = localStorage.getItem("forest_user_data");
    if (savedToken && savedUser) {
        try {
            currentRegistration = JSON.parse(savedUser);
            showActivePass(currentRegistration);
            enableGPS(true);
        } catch (e) {}
    } else {
        // Legacy support
        const saved = localStorage.getItem("forest_visitor_reg");
        if (saved) {
            try {
                currentRegistration = JSON.parse(saved);
                showActivePass(currentRegistration);
                enableGPS(true);
            } catch (e) {}
        }
    }
});

// Camera & Multi-Photo Face Biometric Capture Handlers
const POSE_GUIDANCE = [
    'Photo 1/5: "Look directly into the camera."',
    'Photo 2/5: "Turn your head slightly to the left."',
    'Photo 3/5: "Turn your head slightly to the right."',
    'Photo 4/5: "Change facial expression slightly."',
    'Photo 5/5: "Adjust distance slightly or tilt your head upward."'
];

async function startFaceCamera() {
    const video = $("face-video");
    const placeholder = $("face-cam-msg");
    const guide = $("face-guide-oval");
    const btnStart = $("btn-start-face-cam");
    const btnCapture = $("btn-capture-face");
    const btnClear = $("btn-clear-photos");
    const badge = $("face-status-badge");
    const feedback = $("face-feedback-text");

    try {
        if (placeholder) placeholder.style.display = "none";
        faceStream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
            audio: false
        });
        video.srcObject = faceStream;
        await video.play();
        video.style.display = "block";
        if ($("face-captured-preview")) $("face-captured-preview").style.display = "none";
        if (guide) guide.style.display = "block";

        btnStart.style.display = "none";
        btnCapture.style.display = "inline-block";
        if (btnClear) btnClear.style.display = capturedPhotos.length > 0 ? "inline-block" : "none";

        badge.className = "badge-status status-active";
        badge.textContent = "Camera Live";
        updateCaptureUI();
    } catch (err) {
        let userMsg = "Camera access failed: " + (err.message || err.name);
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
            userMsg = "Camera permission was denied. Please allow camera access and try again.";
        } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
            userMsg = "No camera was detected. Please connect a webcam to continue.";
        } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
            userMsg = "Camera is already in use by another application. Please close other applications and try again.";
        } else if (err.name === "OverconstrainedError") {
            userMsg = "Requested camera resolution constraints could not be satisfied by your camera hardware.";
        }

        if (placeholder) {
            placeholder.style.display = "block";
            placeholder.textContent = userMsg;
        }
        badge.className = "badge-status status-sos";
        badge.textContent = "Camera Error";
        if (feedback) feedback.textContent = "⚠️ " + userMsg;
    }
}

function captureFace() {
    const video = $("face-video");
    const canvas = $("face-canvas");
    const feedback = $("face-feedback-text");

    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
        if (feedback) feedback.textContent = "Camera is not ready yet. Please wait a moment.";
        return;
    }

    if (capturedPhotos.length >= 5) {
        alert("Target reached: 5 real photos already captured!");
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Client-side quick validation: verify canvas is not completely dark/blank
    try {
        const sampleData = ctx.getImageData(0, 0, Math.min(100, canvas.width), Math.min(100, canvas.height)).data;
        let sum = 0;
        for (let i = 0; i < sampleData.length; i += 4) {
            sum += sampleData[i] + sampleData[i+1] + sampleData[i+2];
        }
        const avg = sum / (sampleData.length / 4 * 3);
        if (avg < 5) {
            if (feedback) feedback.textContent = "Photo capture failed: Video frame appears black or covered. Please check your camera.";
            return;
        }
    } catch (e) {}

    const b64 = canvas.toDataURL("image/jpeg", 0.92);
    capturedPhotos.push(b64);
    updateCaptureUI();

    if (capturedPhotos.length >= 5) {
        if (faceStream) {
            faceStream.getTracks().forEach(t => t.stop());
            faceStream = null;
        }
        video.style.display = "none";
        if ($("face-guide-oval")) $("face-guide-oval").style.display = "none";
        if (feedback) feedback.textContent = "✅ All 5 genuine photographs captured! Ready to submit registration.";
    } else {
        const nextPose = POSE_GUIDANCE[capturedPhotos.length];
        if (feedback) feedback.textContent = `Photo #${capturedPhotos.length} recorded. Next: ${nextPose}`;
    }
}

function updateCaptureUI() {
    const badgeCounter = $("samples-counter-badge");
    const btnCapture = $("btn-capture-face");
    const btnClear = $("btn-clear-photos");
    const strip = $("photo-strip-container");
    const poseText = $("pose-instruction-text");

    if (poseText) {
        if (capturedPhotos.length < 5) {
            poseText.textContent = POSE_GUIDANCE[capturedPhotos.length];
            poseText.style.color = "#0d3813";
        } else {
            poseText.textContent = "✅ 5/5 Photos Captured — Enrollment Complete!";
            poseText.style.color = "#15803d";
        }
    }

    if (badgeCounter) {
        badgeCounter.textContent = `${capturedPhotos.length} / 5 Photos`;
        badgeCounter.style.background = capturedPhotos.length === 5 ? "#e7f5e9" : "#fff3e0";
        badgeCounter.style.color = capturedPhotos.length === 5 ? "#176b32" : "#b45309";
    }

    if (btnCapture) {
        if (capturedPhotos.length < 5) {
            btnCapture.textContent = `📸 Capture Photo (${capturedPhotos.length + 1}/5)`;
            btnCapture.style.display = "inline-block";
        } else {
            btnCapture.style.display = "none";
        }
    }

    if (btnClear) {
        btnClear.style.display = capturedPhotos.length > 0 ? "inline-block" : "none";
    }

    if (strip) {
        if (capturedPhotos.length === 0) {
            strip.innerHTML = `<small style="color:#77847b; font-size:12px; padding:10px 0;">No photos captured yet. Click "Capture Photo" to record real samples.</small>`;
        } else {
            strip.innerHTML = capturedPhotos.map((src, idx) => `
                <div class="photo-strip-card" style="position:relative; display:inline-block; margin-right:8px; border:1px solid #c8e6c9; border-radius:6px; overflow:hidden; background:#fff;" title="Sample #${idx + 1}">
                    <img src="${src}" alt="Sample ${idx + 1}" style="width:72px; height:72px; object-fit:cover; display:block;">
                    <div style="font-size:10px; text-align:center; background:#e8f5e9; color:#1b5e20; font-weight:700; padding:2px 0;">#${idx + 1}</div>
                    <div style="display:flex; justify-content:space-between; background:#fafafa; border-top:1px solid #eee;">
                        <button type="button" style="border:none; background:transparent; color:#2563eb; font-size:10px; cursor:pointer; padding:2px 4px; font-weight:600;" onclick="retakePhoto(${idx})" title="Retake this photo">Retake</button>
                        <button type="button" style="border:none; background:transparent; color:#dc2626; font-size:10px; cursor:pointer; padding:2px 4px; font-weight:700;" onclick="removePhoto(${idx})" title="Remove">✕</button>
                    </div>
                </div>
            `).join("");
        }
    }
}

function retakePhoto(idx) {
    if (idx >= 0 && idx < capturedPhotos.length) {
        capturedPhotos.splice(idx, 1);
        updateCaptureUI();
        if (!faceStream && $("step-register").style.display !== "none") {
            startFaceCamera();
        }
        if ($("face-feedback-text")) {
            $("face-feedback-text").textContent = `Retaking photo #${idx + 1}: ${POSE_GUIDANCE[idx]}`;
        }
    }
}

function removePhoto(idx) {
    if (idx >= 0 && idx < capturedPhotos.length) {
        capturedPhotos.splice(idx, 1);
        updateCaptureUI();
        if (!faceStream && $("step-register").style.display !== "none") {
            startFaceCamera();
        }
    }
}

function clearAllPhotos() {
    capturedPhotos = [];
    updateCaptureUI();
    if ($("face-feedback-text")) $("face-feedback-text").textContent = "Photos cleared. Please capture 5 real face photographs following the pose guidance.";
    if (!faceStream && $("step-register").style.display !== "none") {
        startFaceCamera();
    }
}

// Registration Submission — Unified with JWT auth
async function submitRegistration() {
    const name = $("visitor-name").value.trim();
    const email = $("visitor-email") ? $("visitor-email").value.trim() : "";
    const phone = $("visitor-phone").value.trim();
    const password = $("visitor-password") ? $("visitor-password").value : "";
    const confirmPassword = $("visitor-confirm-password") ? $("visitor-confirm-password").value : "";
    const emergencyName = $("emergency-name") ? $("emergency-name").value.trim() : "";
    const emergencyPhone = $("emergency-phone") ? $("emergency-phone").value.trim() : "";
    const btn = $("btn-submit-reg");
    const errorBanner = $("reg-error-banner");

    // Clear previous errors
    if (errorBanner) { errorBanner.style.display = "none"; errorBanner.textContent = ""; }

    // Validation
    if (!name) return showRegError("Please enter your full name.");
    if (!email) return showRegError("Please enter your email address.");
    if (!phone) return showRegError("Please enter your phone number.");
    if (!password) return showRegError("Please enter a password.");
    if (password.length < 6) return showRegError("Password must be at least 6 characters.");
    if (password !== confirmPassword) return showRegError("Passwords do not match.");

    if (capturedPhotos.length < 5) {
        return showRegError(`Face enrollment requires exactly 5 real photographs (${capturedPhotos.length}/5 captured). Please complete all 5 required poses.`);
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Creating Account & Computing Biometrics...";
    }

    try {
        const payload = {
            name,
            email,
            phone,
            password,
            emergency_contact_name: emergencyName,
            emergency_contact_phone: emergencyPhone,
            face_images: capturedPhotos
        };

        const res = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const json = await res.json();

        if (!res.ok) {
            throw new Error(json.message || json.error || "Registration failed");
        }

        // Extract data from response
        const data = json.data || json;

        // Store JWT token and user data
        if (data.access_token) {
            localStorage.setItem("forest_access_token", data.access_token);
        }
        if (data.user) {
            localStorage.setItem("forest_user_data", JSON.stringify(data.user));
        }

        // Build registration object for pass display
        currentRegistration = {
            unique_id: data.forest_user_id || data.unique_id || (data.user && data.user.forest_user_id) || "FOR-0000",
            name: data.user ? data.user.name : name,
            phone: data.user ? data.user.phone : phone,
            email: data.user ? data.user.email : email,
            registered_at: data.registered_at || (data.user && data.user.created_at) || new Date().toLocaleString(),
            face_registered: data.face_registered || true,
            samples_count: data.samples_count || capturedPhotos.length,
            face_thumbnail: data.face_thumbnail || (capturedPhotos.length > 0 ? capturedPhotos[0] : "")
        };

        // Also save to legacy storage for backward compat
        localStorage.setItem("forest_visitor_reg", JSON.stringify(currentRegistration));

        showActivePass(currentRegistration);
        enableGPS();

        if ($("face-reg-success-msg")) {
            $("face-reg-success-msg").textContent = "Face registration completed successfully. 5 biometric samples enrolled into recognition index.";
            $("face-reg-success-msg").style.display = "block";
        } else {
            console.log("Face registration completed successfully.");
        }

    } catch (e) {
        showRegError(e.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "✅ Register & Generate Forest ID Pass";
        }
    }
}

function showRegError(msg) {
    const banner = $("reg-error-banner");
    if (banner) {
        banner.textContent = "⚠️ " + msg;
        banner.style.display = "block";
    } else {
        alert(msg);
    }
}

function showActivePass(data) {
    $("step-register").style.display = "none";
    $("step-active").style.display = "block";
    $("card-uid").textContent = data.unique_id || "FOR-0000";
    $("card-name").textContent = data.name || "--";
    
    const contactLine = [data.phone, data.email].filter(Boolean).join(" • ");
    if ($("card-contact")) $("card-contact").textContent = contactLine;

    const thumbImg = $("card-face-thumb");
    const placeholder = $("card-thumb-placeholder");
    const bioBadge = $("card-biometric-badge");
    const samplesBadge = $("card-samples-badge");

    const sampleCount = data.samples_count || (capturedPhotos.length > 0 ? capturedPhotos.length : 0);

    if (data.face_thumbnail || data.face_registered || sampleCount > 0) {
        if (thumbImg) {
            thumbImg.src = data.face_thumbnail || (capturedPhotos.length > 0 ? capturedPhotos[0] : "");
            thumbImg.style.display = "block";
        }
        if (placeholder) placeholder.style.display = "none";
        if (bioBadge) {
            bioBadge.textContent = "BIOMETRIC ENROLLED";
            bioBadge.style.color = "#72f796";
        }
        if (samplesBadge) {
            samplesBadge.textContent = `Centroid Profile: ${sampleCount} real photo${sampleCount > 1 ? 's' : ''}`;
        }
    } else {
        if (thumbImg) thumbImg.style.display = "none";
        if (placeholder) placeholder.style.display = "flex";
        if (bioBadge) {
            bioBadge.textContent = "STANDARD PASS";
            bioBadge.style.color = "#fbd38d";
        }
        if (samplesBadge) samplesBadge.textContent = "";
    }

    $("pass-date").textContent = "Registered: " + (data.registered_at || new Date().toLocaleTimeString());
}

function registerAnotherVisitor() {
    if (faceStream) {
        faceStream.getTracks().forEach(t => t.stop());
        faceStream = null;
    }
    if (gpsWatchId && "geolocation" in navigator) navigator.geolocation.clearWatch(gpsWatchId);

    // Clear all stored session data
    localStorage.removeItem("forest_visitor_reg");
    localStorage.removeItem("forest_access_token");
    localStorage.removeItem("forest_user_data");
    currentRegistration = null;
    capturedPhotos = [];
    currentCoordinates = { lat: 0, lon: 0 };

    // Reset form fields
    $("visitor-name").value = "";
    if ($("visitor-email")) $("visitor-email").value = "";
    $("visitor-phone").value = "";
    if ($("visitor-password")) $("visitor-password").value = "";
    if ($("visitor-confirm-password")) $("visitor-confirm-password").value = "";
    if ($("emergency-name")) $("emergency-name").value = "";
    if ($("emergency-phone")) $("emergency-phone").value = "";

    updateCaptureUI();

    if ($("face-captured-preview")) $("face-captured-preview").style.display = "none";
    if ($("face-video")) $("face-video").style.display = "none";
    if ($("face-guide-oval")) $("face-guide-oval").style.display = "none";
    if ($("face-cam-msg")) {
        $("face-cam-msg").style.display = "block";
        $("face-cam-msg").textContent = "Click 'Start Camera' to capture enrollment photos";
    }
    if ($("btn-start-face-cam")) $("btn-start-face-cam").style.display = "inline-block";
    if ($("btn-capture-face")) $("btn-capture-face").style.display = "none";
    if ($("btn-clear-photos")) $("btn-clear-photos").style.display = "none";

    const badge = $("face-status-badge");
    if (badge) {
        badge.className = "badge-status status-pending";
        badge.textContent = "Camera Idle";
    }
    if ($("face-feedback-text")) $("face-feedback-text").textContent = "";
    if ($("reg-error-banner")) { $("reg-error-banner").style.display = "none"; }

    $("step-active").style.display = "none";
    $("step-register").style.display = "block";
}

function enableGPS(silent = false) {
    if (gpsWatchId) navigator.geolocation.clearWatch(gpsWatchId);
    const dot = $("gps-dot"), title = $("gps-title"), coords = $("gps-coords"), btn = $("btn-gps");
    if (!("geolocation" in navigator)) {
        if (title) title.textContent = "❌ Geolocation not supported on this browser";
        return silent || alert("Geolocation not supported on this browser.");
    }

    if (title) title.textContent = "Acquiring Device GPS Signal...";
    if (dot) dot.className = "gps-status-dot";

    function updateLocation(lat, lon, accuracy = 10.0) {
        currentCoordinates = { lat, lon };
        if (dot) dot.className = "gps-status-dot active";
        if (title) title.textContent = "🟢 GPS Safety Tracking Active";
        if (coords) coords.innerHTML = `<b>Lat:</b> ${lat.toFixed(5)} | <b>Lon:</b> ${lon.toFixed(5)} | <b>Acc:</b> ±${Math.round(accuracy)}m`;
        if (btn) btn.style.display = "none";
        sendGPSLocation(lat, lon, "Tracking Live", accuracy);
    }

    function handleGPSError(err) {
        let msg = "Live GPS unavailable. Please enable browser location permissions.";
        if (err && err.code === 1) {
            msg = "Live GPS unavailable. Location permission denied in browser.";
        } else if (err && err.code === 2) {
            msg = "Live GPS unavailable. Position unavailable.";
        } else if (err && err.code === 3) {
            msg = "Live GPS unavailable. Request timed out.";
        }
        if (title) title.textContent = "❌ " + msg;
        if (coords) coords.innerHTML = `<span style="color:#ef4444; font-weight:600;">${msg}</span>`;
        if (dot) dot.className = "gps-status-dot error";
        if (btn) btn.style.display = "inline-block";
    }

    navigator.geolocation.getCurrentPosition(
        p => updateLocation(p.coords.latitude, p.coords.longitude, p.coords.accuracy || 10.0),
        handleGPSError,
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
    );

    gpsWatchId = navigator.geolocation.watchPosition(
        p => updateLocation(p.coords.latitude, p.coords.longitude, p.coords.accuracy || 10.0),
        handleGPSError,
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
    );
}

async function sendGPSLocation(latitude, longitude, status, accuracy = 10.0) {
    if (!currentRegistration?.unique_id) return;

    // Build headers (include JWT if available)
    const headers = { "Content-Type": "application/json" };
    const token = localStorage.getItem("forest_access_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
        const res = await fetch("/api/gps-update", {
            method: "POST",
            headers,
            body: JSON.stringify({
                unique_id: currentRegistration.unique_id,
                latitude,
                longitude,
                accuracy,
                gps_status: status
            })
        });

        if (res.ok) {
            const data = await res.json();
            const banner = $("gps-zone-banner");
            if (banner && data.zone) {
                const z = data.zone;
                const isRestricted = z.is_restricted || data.risk_level === "CRITICAL" || data.risk_level === "HIGH";
                banner.style.display = "block";
                banner.style.color = isRestricted ? "#dc2626" : "#15803d";
                banner.innerHTML = `🌲 Current Zone: <b>${escapeHtml(z.name)}</b> (${escapeHtml(z.risk_level)} RISK) ${isRestricted ? '⚠️ RESTRICTED' : '✅ Open Trail'}`;
                if (data.alert_triggered || isRestricted) {
                    if (window.SoundAlerts) window.SoundAlerts.play("geofence");
                }
            }
        }
    } catch (e) {}
}

async function triggerSOS() {
    if (window.SoundAlerts) window.SoundAlerts.play("sos");
    const btn = $("btn-sos"), count = $("sos-countdown"), fb = $("sos-feedback"), prev = $("sos-preview");
    btn.disabled = true; btn.style.opacity = "0.6";
    fb.style.color = "#a32118"; fb.textContent = "📹 Initializing emergency video...";
    let stream = null, recorder = null; const chunks = [];
    try {
        try { stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true }); }
        catch { stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false }); }
        prev.srcObject = stream; prev.style.display = "block"; await prev.play();
        const recOptions = { videoBitsPerSecond: 400000 };
        try { recorder = new MediaRecorder(stream, recOptions); }
        catch (e) { recorder = new MediaRecorder(stream); }
        recorder.ondataavailable = e => { if (e.data && e.data.size > 0) chunks.push(e.data); };
        recorder.onstop = async () => {
            stream.getTracks().forEach(t => t.stop()); prev.style.display = "none";
            fb.textContent = "📡 Sending 5s video & location to Forest Officer...";
            await sendSOS(new Blob(chunks, { type: chunks[0]?.type || "video/webm" }), fb);
            btn.disabled = false; btn.style.opacity = "1";
        };
        recorder.start();
        let sec = 5; count.style.display = "block"; count.textContent = sec;
        const timer = setInterval(() => {
            sec--;
            if (sec > 0) count.textContent = sec;
            else { clearInterval(timer); count.style.display = "none"; if (recorder.state === "recording") recorder.stop(); }
        }, 1000);
    } catch (e) {
        const mobileCam = $("sos-mobile-cam");
        if (mobileCam) {
            fb.textContent = "📱 Opening Phone Camera for Emergency Video...";
            mobileCam.click();
        } else {
            fb.textContent = "⚠️ Camera unavailable. Sending location-only SOS...";
            await sendSOS(null, fb);
            btn.disabled = false; btn.style.opacity = "1";
        }
    }
}

async function handleMobileVideo(input) {
    const btn = $("btn-sos"), fb = $("sos-feedback");
    if (input.files && input.files[0]) {
        fb.textContent = "📡 Sending video clip & location to Forest Officer...";
        await sendSOS(input.files[0], fb);
    } else {
        await sendSOS(null, fb);
    }
    btn.disabled = false; btn.style.opacity = "1";
}

async function sendSOS(videoBlob, feedback) {
    const lat = currentCoordinates.lat || 0;
    const lon = currentCoordinates.lon || 0;
    const form = new FormData();
    form.append("unique_id", currentRegistration?.unique_id || "UNREGISTERED");
    form.append("name", currentRegistration?.name || "Unknown Visitor");
    form.append("latitude", lat);
    form.append("longitude", lon);
    if (videoBlob) form.append("video", videoBlob, "sos_clip.webm");
    try {
        const res = await fetch("/api/sos", { method: "POST", body: form });
        if (!res.ok) throw new Error("SOS failed");
        feedback.style.color = "#176b32";
        feedback.innerHTML = "🚨 <b>SOS SENT!</b> Emergency clip & location sent to Officer.";
    } catch (e) {
        feedback.style.color = "#a32118";
        feedback.textContent = "❌ SOS Error: " + e.message;
    }
}
