// Namima v0.5 – warm / space / chaos / density engine
// 依存: Tone.js（index.htmlで読み込み済）

(() => {
  const state = {
    warm: 0.6,
    space: 0.7,
    chaos: 0.3,
    density: 0.5,
    started: false,
    initializing: false,
  };

  // DOM refs
  let canvas, ctx, width, height;
  let startBtn, stopBtn;
  let warmSlider, spaceSlider, chaosSlider, densitySlider;

  // Tone nodes
  const nodes = {};

  // =========================
  // Canvas / background
  // =========================
  function initCanvas() {
    canvas = document.getElementById("bg");
    if (!canvas) return;
    ctx = canvas.getContext("2d");
    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);
    requestAnimationFrame(drawLoop);
  }

  function resizeCanvas() {
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = window.innerWidth * dpr;
    canvas.height = window.innerHeight * dpr;
    width = canvas.width;
    height = canvas.height;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function drawLoop(t) {
    if (!ctx) return;
    const time = t * 0.001;

    const warm = state.warm;
    const space = state.space;
    const chaos = state.chaos;

    const baseHue = 210 + (space - 0.5) * 60;
    const grad = ctx.createRadialGradient(
      width * 0.2,
      height * 0.1,
      0,
      width * 0.5,
      height * 0.8,
      Math.max(width, height) * 0.7
    );
    grad.addColorStop(
      0,
      `hsla(${baseHue}, 80%, ${25 + warm * 15}%, 1)`
    );
    grad.addColorStop(
      1,
      `hsla(${baseHue + chaos * 40}, 95%, 4%, 1)`
    );
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    const cx = width / 2;
    const cy = height / 2;
    const rings = 6 + Math.floor(6 * state.density);
    const baseR = Math.min(width, height) * 0.18;
    const chaosAmp = 10 + chaos * 60;
    const warmGlow = 0.4 + warm * 0.4;

    for (let i = 0; i < rings; i++) {
      const ratio = i / rings;
      const radius =
        baseR * (1 + ratio * 2.4) +
        Math.sin(time * 0.5 + ratio * 6.28) * chaosAmp;
      const alpha = 0.08 + ratio * 0.12 * warmGlow;

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${baseHue + ratio * 50}, 90%, ${
        40 + ratio * 20
      }%, ${alpha})`;
      ctx.lineWidth = 2 + ratio * 3;
      ctx.stroke();
    }

    requestAnimationFrame(drawLoop);
  }

  // =========================
  // Tone.js graph
  // =========================

  function initAudioGraph() {
    // 基本設定
    Tone.Transport.bpm.value = 82;
    Tone.Transport.swing = 0.12;
    Tone.Transport.swingSubdivision = "16n";

    const masterGain = new Tone.Gain(0.9);
    const masterComp = new Tone.Compressor({
      threshold: -18,
      ratio: 3,
      attack: 0.01,
      release: 0.15,
    });
    const masterLimit = new Tone.Limiter(-0.5);

    masterGain.chain(masterComp, masterLimit, Tone.Destination);
    nodes.masterGain = masterGain;

    const warmBus = new Tone.Gain(0.6).connect(masterGain);
    const spaceBus = new Tone.Gain(0.8).connect(masterGain);
    const chaosBus = new Tone.Gain(0.6).connect(masterGain);
    const bassBus = new Tone.Gain(0.9).connect(masterGain);

    nodes.warmBus = warmBus;
    nodes.spaceBus = spaceBus;
    nodes.chaosBus = chaosBus;
    nodes.bassBus = bassBus;

    // --- Warm layer ---

    const padReverb = new Tone.Reverb({
      decay: 5,
      preDelay: 0.15,
      wet: 0.5,
    });
    const padFilter = new Tone.Filter(1500, "lowpass", -12);

    const padSynth = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "triangle" },
      envelope: { attack: 1.2, decay: 0.6, sustain: 0.8, release: 4.5 },
    });

    padSynth.chain(padFilter, padReverb, warmBus);

    const noise = new Tone.Noise("pink");
    const noiseFilter = new Tone.Filter(800, "lowpass", -24);
    const noiseGain = new Tone.Gain(0.12);

    noise.chain(noiseFilter, noiseGain, warmBus);

    const driftLFO = new Tone.LFO({
      frequency: 0.12,
      min: -8,
      max: 8,
    }).start();
    driftLFO.connect(padSynth.detune);

    nodes.padSynth = padSynth;
    nodes.padFilter = padFilter;
    nodes.padReverb = padReverb;
    nodes.noise = noise;
    nodes.noiseFilter = noiseFilter;
    nodes.noiseGain = noiseGain;
    nodes.driftLFO = driftLFO;

    // --- Space layer ---

    const spaceChorus = new Tone.Chorus({
      frequency: 0.15,
      delayTime: 4,
      depth: 0.5,
      spread: 180,
    }).start();

    const spaceDelay = new Tone.FeedbackDelay({
      delayTime: "8n",
      feedback: 0.35,
      wet: 0.5,
    });

    const spaceVerb = new Tone.Reverb({
      decay: 8,
      preDelay: 0.25,
      wet: 0.7,
    });

    const spaceSynth = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "sine" },
      envelope: { attack: 2.0, decay: 1.0, sustain: 0.8, release: 6.0 },
    });

    spaceSynth.chain(spaceChorus, spaceDelay, spaceVerb, spaceBus);

    nodes.spaceSynth = spaceSynth;
    nodes.spaceChorus = spaceChorus;
    nodes.spaceDelay = spaceDelay;
    nodes.spaceVerb = spaceVerb;

    // --- Chaos layer ---

    const chaosNoise = new Tone.Noise("white");
    const chaosBit = new Tone.BitCrusher(4);
    const chaosFilter = new Tone.Filter(1200, "bandpass", -12);
    const chaosGain = new Tone.Gain(0.05);

    chaosNoise.chain(chaosBit, chaosFilter, chaosGain, chaosBus);

    nodes.chaosNoise = chaosNoise;
    nodes.chaosBit = chaosBit;
    nodes.chaosFilter = chaosFilter;
    nodes.chaosGain = chaosGain;

    // --- Bass layer ---

    const bassFilter = new Tone.Filter(120, "lowpass", -24);
    const bass = new Tone.MonoSynth({
      oscillator: { type: "sawtooth" },
      envelope: { attack: 0.02, decay: 0.3, sustain: 0.5, release: 0.8 },
      filterEnvelope: {
        attack: 0.01,
        decay: 0.2,
        sustain: 0.2,
        release: 0.4,
        baseFrequency: 60,
        octaves: 3,
      },
    });

    bass.chain(bassFilter, bassBus);

    nodes.bass = bass;
    nodes.bassFilter = bassFilter;

    // --- Patterns ---

    const padChords = [
      ["C4", "G4", "Bb4", "D5"],
      ["F4", "C5", "Eb5", "G5"],
      ["D4", "A4", "C5", "E5"],
      ["Bb3", "F4", "A4", "C5"],
    ];

    const padLoop = new Tone.Loop((time) => {
      const idx = Math.floor(Math.random() * padChords.length);
      const chord = padChords[idx];
      const vel = 0.5 + state.warm * 0.4;

      padSynth.triggerAttackRelease(chord, "2m", time, vel);

      if (Math.random() < 0.4 + state.space * 0.4) {
        const up = chord.map((n) =>
          Tone.Frequency(n).transpose(7).toNote()
        );
        padSynth.triggerAttackRelease(up, "1m", time + Tone.Time("1m"), vel * 0.7);
      }
    }, "4m").start(0);

    nodes.padLoop = padLoop;

    const bassNotes = ["C2", "G1", "A1", "F1"];

    const bassLoop = new Tone.Loop((time) => {
      const idx = Math.floor(Math.random() * bassNotes.length);
      const baseTime = time + (Math.random() * 0.1 - 0.05);
      const vel = 0.45 + state.density * 0.35;

      bass.triggerAttackRelease(bassNotes[idx], "8n", baseTime, vel);

      if (Math.random() < 0.3 + state.chaos * 0.3) {
        bass.triggerAttackRelease(
          bassNotes[idx],
          "16n",
          baseTime + Tone.Time("16n"),
          vel * 0.6
        );
      }
    }, "2m").start("1m");

    nodes.bassLoop = bassLoop;

    const drumLoop = new Tone.Loop((time) => {
      const dens = state.density;

      if (Math.random() < 0.85) {
        const kick = new Tone.MembraneSynth().connect(bassBus);
        kick.triggerAttackRelease("C1", "8n", time, 0.8 + dens * 0.2);
      }

      if (Math.random() < 0.35 + dens * 0.25) {
        const hat = new Tone.MetalSynth({
          frequency: 450,
          envelope: { attack: 0.001, decay: 0.1, release: 0.01 },
          harmonicity: 5.1,
          modulationIndex: 32,
          resonance: 4000,
          octaves: 1.5,
        }).connect(spaceBus);
        hat.triggerAttackRelease("16n", time + Tone.Time("8n"), 0.3 + dens * 0.3);
      }

      if (Math.random() < state.chaos * 0.7) {
        chaosNoise.start(time).stop(time + 0.05 + state.chaos * 0.15);
      }
    }, "1m").start("2m");

    nodes.drumLoop = drumLoop;

    noise.start();
    chaosNoise.start();
  }

  function applyStateToAudio() {
    if (!nodes.masterGain) return;

    const warm = state.warm;
    const space = state.space;
    const chaos = state.chaos;
    const density = state.density;

    nodes.noiseGain &&
      nodes.noiseGain.gain.rampTo(0.05 + warm * 0.25, 0.2);
    nodes.padFilter &&
      nodes.padFilter.frequency.rampTo(1200 + warm * 800, 0.5);
    nodes.padReverb &&
      (nodes.padReverb.wet.value = 0.3 + space * 0.4);
    nodes.spaceDelay &&
      (nodes.spaceDelay.feedback.value = 0.1 + space * 0.3);
    nodes.spaceVerb &&
      (nodes.spaceVerb.wet.value = 0.4 + space * 0.5);
    nodes.chaosBit &&
      (nodes.chaosBit.bits = 2 + Math.floor(4 * chaos));
    nodes.chaosGain &&
      nodes.chaosGain.gain.rampTo(0.01 + chaos * 0.18, 0.3);

    const baseGain = 0.7 + density * 0.2;
    nodes.masterGain.gain.rampTo(baseGain, 0.4);
  }

  // =========================
  // UI binding
  // =========================

  function bindUI() {
    startBtn = document.getElementById("startBtn");
    stopBtn = document.getElementById("stopBtn");
    warmSlider = document.getElementById("warm");
    spaceSlider = document.getElementById("space");
    chaosSlider = document.getElementById("chaos");
    densitySlider = document.getElementById("density");

    if (startBtn) {
      startBtn.addEventListener("click", handleStart);
    }
    if (stopBtn) {
      stopBtn.addEventListener("click", handleStop);
    }

    const onSlider = () => {
      if (!warmSlider || !spaceSlider || !chaosSlider || !densitySlider)
        return;
      state.warm = warmSlider.valueAsNumber / 100;
      state.space = spaceSlider.valueAsNumber / 100;
      state.chaos = chaosSlider.valueAsNumber / 100;
      state.density = densitySlider.valueAsNumber / 100;
      applyStateToAudio();
    };

    [warmSlider, spaceSlider, chaosSlider, densitySlider].forEach((el) => {
      if (!el) return;
      el.addEventListener("input", onSlider);
    });
  }

  async function handleStart() {
    if (state.initializing) return;
    state.initializing = true;

    try {
      await Tone.start(); // iOS / Safari 含めて AudioContext 起動
      if (!state.started) {
        initAudioGraph();
        state.started = true;
      }

      Tone.Transport.start("+0.05");
      startBtn.textContent = "▶ PLAYING";
    } catch (e) {
      console.warn(e);
      alert(
        "オーディオの開始に失敗しました。\n画面を一度タップしてから、もう一度 START を押してください。"
      );
    } finally {
      state.initializing = false;
    }
  }

  function handleStop() {
    if (!state.started) {
      Tone.Transport.stop();
      startBtn.textContent = "▶ START";
      return;
    }
    Tone.Transport.stop();
    startBtn.textContent = "▶ START";
  }

  // =========================
  // Global AudioContext unlock (iOS / mobile)
  // =========================
  function setupGlobalUnlock() {
    const tryUnlock = async () => {
      try {
        await Tone.start();
      } catch (e) {
        console.warn("Tone.start() unlock failed", e);
      } finally {
        document.body.removeEventListener("touchstart", tryUnlock);
        document.body.removeEventListener("touchend", tryUnlock);
        document.body.removeEventListener("mousedown", tryUnlock);
        document.body.removeEventListener("click", tryUnlock);
      }
    };

    document.body.addEventListener("touchstart", tryUnlock, { once: true });
    document.body.addEventListener("touchend", tryUnlock, { once: true });
    document.body.addEventListener("mousedown", tryUnlock, { once: true });
    document.body.addEventListener("click", tryUnlock, { once: true });
  }

  // =========================
  // Boot
  // =========================

  window.addEventListener("DOMContentLoaded", () => {
    setupGlobalUnlock();
    initCanvas();
    bindUI();

    warmSlider && (state.warm = warmSlider.valueAsNumber / 100);
    spaceSlider && (state.space = spaceSlider.valueAsNumber / 100);
    chaosSlider && (state.chaos = chaosSlider.valueAsNumber / 100);
    densitySlider && (state.density = densitySlider.valueAsNumber / 100);
  });
})();