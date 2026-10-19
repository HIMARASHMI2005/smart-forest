/**
 * sound_alerts.js — Web Audio API Synthesizer for Smart Forest Alert Sounds.
 * 100% Zero external audio files — Generates pure real-time acoustic tones.
 * Compliant with modern browser Autoplay Policy with one-click audio unlock.
 */

const SoundAlerts = (() => {
  let audioCtx = null;
  let isMuted = false;
  let isUnlocked = false;
  const lastPlayTimes = {};

  const COOLDOWNS = {
    sos: 1000,
    critical: 1000,
    geofence: 800,
    warning: 800,
    high: 800,
    intrusion: 800,
    unknown: 800,
    beep: 300,
    test: 200,
    info: 400
  };

  // Check saved preference
  try {
    const saved = localStorage.getItem("sf_sound_enabled");
    if (saved === "false") {
      isMuted = true;
    }
  } catch (e) {}

  /**
   * Initializes or returns active AudioContext.
   */
  function getContext() {
    if (!audioCtx) {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (AudioCtxClass) {
        audioCtx = new AudioCtxClass();
      }
    }
    if (audioCtx && audioCtx.state === "suspended") {
      audioCtx.resume().then(() => {
        isUnlocked = true;
      }).catch(() => {});
    } else if (audioCtx && audioCtx.state === "running") {
      isUnlocked = true;
    }
    return audioCtx;
  }

  /**
   * Unlocks audio on first user gesture (click, tap, keypress).
   */
  function unlock() {
    const ctx = getContext();
    if (ctx && ctx.state === "suspended") {
      ctx.resume().then(() => {
        isUnlocked = true;
        console.log("[SoundAlerts] AudioContext unlocked successfully.");
      }).catch(err => console.warn("[SoundAlerts] Unlock failed:", err));
    } else if (ctx && ctx.state === "running") {
      isUnlocked = true;
    }
  }

  // Bind global unlock listeners on first user interaction
  if (typeof window !== "undefined") {
    ["click", "touchstart", "keydown", "mousedown"].forEach(evt => {
      window.addEventListener(evt, () => unlock(), { once: true, passive: true });
    });
  }

  /**
   * Plays a single synthetic beep tone.
   * @param {number} freq - Frequency in Hz (default 750Hz)
   * @param {number} duration - Duration in seconds (default 0.18s)
   * @param {string} type - Wave type: 'sine', 'sawtooth', 'triangle', 'square'
   * @param {number} volume - Peak volume 0.0 - 1.0 (default 0.35)
   */
  function beep(freq = 750, duration = 0.18, type = "sine", volume = 0.35) {
    if (isMuted) return;
    const ctx = getContext();
    if (!ctx) return;

    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, now);

      gain.gain.setValueAtTime(volume, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + duration);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + duration + 0.02);
    } catch (err) {
      console.warn("[SoundAlerts] Beep error:", err);
    }
  }

  /**
   * Synthesizes and plays an alert sound pattern.
   * @param {string} type - 'sos', 'geofence', 'intrusion', 'test', 'info', 'beep'
   */
  function play(type = "geofence") {
    if (isMuted) {
      console.log(`[SoundAlerts] Sound is muted. Suppressed alert sound: ${type}`);
      return;
    }

    const nowMs = Date.now();
    const cooldown = COOLDOWNS[type] || 500;
    if (lastPlayTimes[type] && (nowMs - lastPlayTimes[type] < cooldown)) {
      return; // throttle repeat sounds cleanly
    }
    lastPlayTimes[type] = nowMs;

    const ctx = getContext();
    if (!ctx) {
      console.warn("[SoundAlerts] Web Audio API not supported on this browser.");
      return;
    }

    try {
      const now = ctx.currentTime;
      console.log(`[SoundAlerts] 🔊 Playing alert audio tone: [${type.toUpperCase()}]`);

      if (type === "sos" || type === "critical") {
        // High-priority alternating siren/alarm: 880Hz / 659Hz (6 pulses)
        const notes = [880, 659, 880, 659, 880, 659];
        notes.forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "sawtooth";
          osc.frequency.setValueAtTime(freq, now + idx * 0.16);

          gain.gain.setValueAtTime(0.38, now + idx * 0.16);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.16 + 0.15);

          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + idx * 0.16);
          osc.stop(now + idx * 0.16 + 0.16);
        });

      } else if (type === "geofence" || type === "warning" || type === "high") {
        // Dual-tone warning beep: 600Hz -> 850Hz
        const notes = [600, 850];
        notes.forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "sine";
          osc.frequency.setValueAtTime(freq, now + idx * 0.18);

          gain.gain.setValueAtTime(0.35, now + idx * 0.18);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.18 + 0.16);

          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + idx * 0.18);
          osc.stop(now + idx * 0.18 + 0.17);
        });

      } else if (type === "intrusion" || type === "unknown") {
        // Rapid 3-chirp perimeter alert: 440Hz -> 660Hz -> 880Hz
        [440, 660, 880].forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "triangle";
          osc.frequency.setValueAtTime(freq, now + idx * 0.12);

          gain.gain.setValueAtTime(0.32, now + idx * 0.12);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.12 + 0.11);

          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + idx * 0.12);
          osc.stop(now + idx * 0.12 + 0.12);
        });

      } else if (type === "test") {
        // Harmonious 3-tone test chime (C5 - E5 - G5): 523Hz -> 659Hz -> 784Hz
        [523.25, 659.25, 783.99].forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "sine";
          osc.frequency.setValueAtTime(freq, now + idx * 0.14);

          gain.gain.setValueAtTime(0.30, now + idx * 0.14);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.14 + 0.20);

          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + idx * 0.14);
          osc.stop(now + idx * 0.14 + 0.22);
        });

      } else {
        // Single gentle notification ping / beep: 650Hz
        beep(650, 0.20, "sine", 0.25);
      }
    } catch (err) {
      console.warn("[SoundAlerts] Audio playback error:", err);
    }
  }

  /**
   * Toggles sound on/off.
   */
  function toggle() {
    unlock();
    isMuted = !isMuted;
    try {
      localStorage.setItem("sf_sound_enabled", isMuted ? "false" : "true");
    } catch (e) {}

    if (!isMuted) {
      play("test");
    }
    return !isMuted;
  }

  return {
    play,
    beep,
    test: () => { unlock(); play("test"); },
    unlock,
    toggle,
    isEnabled: () => !isMuted,
    isUnlocked: () => isUnlocked
  };
})();

if (typeof window !== "undefined") {
  window.SoundAlerts = SoundAlerts;
}
