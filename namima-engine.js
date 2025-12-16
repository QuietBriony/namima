// =======================================================
// NAMIMA ENGINE — iOS確定動作版（2025-12）
// =======================================================

// -------------------------------
// iOS Safari：AudioContext 解除専用
// -------------------------------

let audioUnlocked = false;

// iOS Safari は page load 時に AudioContext を作れない。
// 必ず "最初のユーザー操作（touch/click）" で解除する必要がある。
function setupIOSAudioUnlock() {
  const unlock = async () => {
    if (audioUnlocked) return;

    try {
      await Tone.start();        // AudioContext を「許可状態」に
      audioUnlocked = true;
      console.log("🔓 AudioContext unlocked (iOS OK)");

    } catch (err) {
      console.warn("⚠️ Unlock failed:", err);
    }

    // 一回で解除するので remove 必須
    document.body.removeEventListener("touchstart", unlock);
    document.body.removeEventListener("touchend", unlock);
    document.body.removeEventListener("click", unlock);
  };

  document.body.addEventListener("touchstart", unlock, { once: true });
  document.body.addEventListener("touchend", unlock, { once: true });
  document.body.addEventListener("click", unlock, { once: true });
}


// =======================================================
// GENERATIVE ENGINE CORE
// =======================================================

let synth = null;
let filter = null;
let noise = null;
let running = false;

function createEngineNodes() {
  // Warm Pad (Synth)
  synth = new Tone.PolySynth(Tone.Synth, {
    oscillator: { type: "sine" },
    envelope: { attack: 1.5, decay: 1.2, sustain: 0.7, release: 4 }
  }).toDestination();

  // Space Filter
  filter = new Tone.AutoFilter({
    frequency: 0.05,
    depth: 0.7,
    baseFrequency: 400,
    octaves: 2,
    type: "sine"
  }).start().toDestination();

  synth.connect(filter);

  // Chaos Noise
  noise = new Tone.Noise("pink").start();
  const noiseFilter = new Tone.Filter(800, "bandpass");
  const noiseGain = new Tone.Gain(0.05);

  noise.connect(noiseFilter);
  noiseFilter.connect(noiseGain);
  noiseGain.toDestination();
}

function parameterUpdate() {
  const warm = Number(document.querySelector("#warm").value) / 100;
  const space = Number(document.querySelector("#space").value) / 100;
  const chaos = Number(document.querySelector("#chaos").value) / 100;
  const density = Number(document.querySelector("#density").value) / 100;

  if (!synth || !filter) return;

  filter.depth = space * 0.9;
  filter.frequency.value = 0.03 + space * 0.15;

  noise.volume.value = Tone.gainToDb(chaos * 0.15);

  // 発音の頻度（密度）
  Tone.Transport.bpm.value = 40 + density * 50;
}

function loopEvent() {
  if (!running || !synth) return;

  const warm = Number(document.querySelector("#warm").value) / 100;
  const chaos = Number(document.querySelector("#chaos").value) / 100;

  const notes = ["C3", "Eb3", "G3", "Bb2", "F3"];
  const pick = notes[Math.floor(Math.random() * notes.length)];

  const detune = (Math.random() - 0.5) * chaos * 40;

  synth.triggerAttackRelease(pick, "2n", undefined, warm * 0.7);

  parameterUpdate();
}


// =======================================================
// START / STOP
// =======================================================

async function handleStart() {
  if (!audioUnlocked) {
    alert("画面を 1 回タップしてから START を押してください。");
    return;
  }

  if (!synth) createEngineNodes();

  if (!running) {
    running = true;

    // Transport 起動
    Tone.Transport.scheduleRepeat(loopEvent, "1m");
    Tone.Transport.start();

    console.log("▶ Engine Started");
  }
}

function handleStop() {
  running = false;
  Tone.Transport.stop();
  console.log("■ Engine Stopped");
}


// =======================================================
// INIT
// =======================================================

window.addEventListener("DOMContentLoaded", () => {
  setupIOSAudioUnlock(); // ← これが最重要（先に AudioContext を解放）

  document.getElementById("startBtn").addEventListener("click", handleStart);
  document.getElementById("stopBtn").addEventListener("click", handleStop);

  document.querySelectorAll("input[type='range']").forEach(el => {
    el.addEventListener("input", parameterUpdate);
  });

  console.log("NAMIMA Ready (iOS Safe Mode)");
});
