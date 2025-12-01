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
    width = canvas.width = window.innerWidth * window.devicePixelRatio;
    height = canvas.height = window.innerHeight * window.devicePixelRatio;
  }

  function drawLoop(t) {
    if (!ctx) return;
    const time = t * 0.001;

    const warm = state.warm;
    const space = state.space;
    const chaos = state.chaos;

    // 背景グラデ
    const baseHue = 210 + (space - 0.5) * 60; // Spaceで色相少し変化
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

    // 波の輪っか
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

    // マスター
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

    // レイヤーごとのバス
    const warmBus = new Tone.Gain(0.6).connect(masterGain);
    const spaceBus = new Tone.Gain(0.8).connect(masterGain);
    const chaosBus = new Tone.Gain(0.6).connect(masterGain);
    const bassBus = new Tone.Gain(0.9).connect(masterGain);

    nodes.warmBus = warmBus;
    nodes.spaceBus = spaceBus;
    nodes.chaosBus = chaosBus;
    nodes.bassBus = bassBus;

    // --- Warm layer: pad + tape noise + drift ---

    // Pad synth
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

    // Warm noise
    const noise = new Tone.Noise("pink");
    const noiseFilter = new Tone.Filter(800, "lowpass", -24);
    const noiseGain = new Tone.Gain(0.12);

    noise.chain(noiseFilter, noiseGain, warmBus);

    // Wow & flutter: pitch drift via LFO on pad synth detune
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

    // --- Space layer: deep pads + FDN-ish verb ---

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
      envelope: { attack: 2.0, decay: 1.0, sustain: 0.9, release: 6.0 },
    });

    spaceSynth.chain(spaceChorus, spaceDelay, spaceVerb, spaceBus);

    nodes.spaceSynth = spaceSynth;
    nodes.spaceChorus = spaceChorus;
    nodes.spaceDelay = spaceDelay;
    nodes.spaceVerb = spaceVerb;

    // --- Chaos layer: noisy grains / clicks / bitcrush ---

    const chaosNoise = new Tone.Noise("white");
    const chaosCrusher = new Tone.BitCrusher(4);
    const chaosFilter = new Tone.Filter(4000, "bandpass", -12);
    const chaosGain = new Tone.Gain(0.0); // densityで上げる

    chaosNoise.chain(chaosCrusher, chaosFilter, chaosGain, chaosBus);

    nodes.chaosNoise = chaosNoise;
    nodes.chaosCrusher = chaosCrusher;
    nodes.chaosFilter = chaosFilter;
    nodes.chaosGain = chaosGain;

    // --- Bass / Rhythm core ---

    const kick = new Tone.MembraneSynth({
      pitchDecay: 0.02,
      octaves: 5,
      oscillator: { type: "sine" },
      envelope: { attack: 0.001, decay: 0.32, sustain: 0.0, release: 0.05 },
    }).connect(bassBus);

    const hat = new Tone.NoiseSynth({
      noise: { type: "white" },
      envelope: { attack: 0.001, decay: 0.08, sustain: 0.0 },
    }).connect(bassBus);

    const bass = new Tone.MonoSynth({
      oscillator: { type: "sawtooth" },
      filter: { type: "lowpass", frequency: 120, rolloff: -24 },
      envelope: { attack: 0.01, decay: 0.25, sustain: 0.4, release: 0.3 },
      filterEnvelope: {
        attack: 0.01,
        decay: 0.2,
        sustain: 0.2,
        release: 0.3,
        baseFrequency: 60,
        octaves: 2,
      },
    }).connect(bassBus);

    nodes.kick = kick;
    nodes.hat = hat;
    nodes.bass = bass;

    // --- Sequences / loops ---

    // 和声：C系の浮遊コード
    const chords = [
      ["C3", "G3", "D4", "E4"],
      ["A2", "E3", "C4", "G4"],
      ["F2", "C3", "G3", "E4"],
      ["D2", "A2", "E3", "C4"],
    ];

    const padLoop = new Tone.Loop((time) => {
      const idx = Math.floor(Math.random() * chords.length);
      const voices = chords[idx];
      const vel = 0.35 + state.warm * 0.25;

      voices.forEach((note, i) => {
        padSynth.triggerAttackRelease(
          note,
          "2m",
          time + i * 0.03,
          vel * (0.9 + i * 0.02)
        );
      });

      // Space層もまれに鳴らす
      if (Math.random() < 0.4 + state.space * 0.4) {
        const spaceChord = chords[(idx + 1) % chords.length].map((n) =>
          n.replace(/\d/, (d) => String(Number(d) + 1))
        );
        spaceSynth.triggerAttackRelease(spaceChord, "4m", time + 0.4, 0.25);
      }
    }, "4m").start(0);

    nodes.padLoop = padLoop;

    // ベース：ゆるいグルーヴ
    const bassNotes = ["C2", "G1", "A1", "F1"];

    const bassLoop = new Tone.Loop((time) => {
      const idx = Math.floor(Math.random() * bassNotes.length);
      const baseTime = time + (Math.random() * 0.1 - 0.05); // 少し前後にずらす
      const vel = 0.45 + state.density * 0.35;

      bass.triggerAttackRelease(bassNotes[idx], "8n", baseTime, vel);

      // 16分でゴーストノート
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

    // ドラム
    const drumLoop = new Tone.Loop((time) => {
      const dens = state.density;

      // Kick：4つ打ち寄り
      for (let i = 0; i < 4; i++) {
        const t = time + Tone.Time("4n") * i;
        kick.triggerAttackRelease("C1", "8n", t, 0.9);
      }

      // Hat：DensityとChaosでパターン変化
      for (let i = 0; i < 8; i++) {
        const p = 0.2 + dens * 0.4 + state.chaos * 0.2;
        if (Math.random() < p) {
          const off = (Math.random() - 0.5) * 0.04; // ゆらぎ
          hat.triggerAttackRelease("8n", time + Tone.Time("8n") * i + off, 0.4);
        }
      }
    }, "1m").start(0);

    nodes.drumLoop = drumLoop;

    // Chaos: グラニュラーっぽいクリック / burst
    const chaosLoop = new Tone.Loop((time) => {
      const chaos = state.chaos;
      const density = state.density;
      const grains = 2 + Math.floor(6 * density * chaos);

      if (chaos <= 0.02) return;

      for (let i = 0; i < grains; i++) {
        const tOffset = (Math.random() * 0.5 - 0.25) * Tone.Time("4n");
        const dur = (0.01 + Math.random() * 0.06) * (1 + chaos * 1.5);
        const amp = 0.05 + chaos * 0.35;

        // Chaos Noiseゲインを一瞬上げる
        chaosGain.gain.setValueAtTime(amp, time + tOffset);
        chaosGain.gain.exponentialRampToValueAtTime(
          0.0001,
          time + tOffset + dur
        );
      }
    }, "2n").start("0:2");

    nodes.chaosLoop = chaosLoop;

    // Noise起動
    noise.start();
    chaosNoise.start();

    // 最初のパラメータ反映
    applyStateToAudio();
  }

  function applyStateToAudio() {
    const { warm, space, chaos, density } = state;

    if (!nodes.masterGain) return;

    // Warm: padのCutoff / Drift / Noise量
    const baseCut = 900 + warm * 1400;
    nodes.padFilter.frequency.rampTo(baseCut, 1.5);

    nodes.noiseGain.gain.rampTo(0.05 + warm * 0.18, 2.0);
    nodes.driftLFO.min = -4 - warm * 6;
    nodes.driftLFO.max = 4 + warm * 6;

    // Space: reverb / delay / chorus depth
    nodes.spaceVerb.decay = 5 + space * 7;
    nodes.spaceVerb.wet.rampTo(0.35 + space * 0.45, 2.0);
    nodes.spaceDelay.feedback.rampTo(0.2 + space * 0.5, 3.0);
    nodes.spaceChorus.depth = 0.25 + space * 0.4;

    // Chaos: bit crush / bandpass / chaos gain limit
    const bits = 4 - Math.floor(chaos * 2); // 4〜2bit
    nodes.chaosCrusher.bits = Math.max(1, bits);
    nodes.chaosFilter.Q.value = 0.7 + chaos * 10;
    // chaosLoop内で使うのでここでは最大値だけ管理

    // Density: 発音数 / busのバランス
    const masterScale = 0.5 + density * 0.6;
    nodes.masterGain.gain.rampTo(masterScale, 2.0);

    nodes.warmBus.gain.rampTo(0.4 + warm * 0.4, 2.0);
    nodes.spaceBus.gain.rampTo(0.3 + space * 0.6, 2.0);
    nodes.chaosBus.gain.rampTo(chaos * 0.8, 2.0);
  }

  // =========================
  // UI / events
  // =========================

  function bindUI() {
    startBtn = document.getElementById("startBtn");
    stopBtn = document.getElementById("stopBtn");
    warmSlider = document.getElementById("warm");
    spaceSlider = document.getElementById("space");
    chaosSlider = document.getElementById("chaos");
    densitySlider = document.getElementById("density");

    if (!startBtn || !stopBtn) return;

    startBtn.addEventListener("click", handleStart);
    stopBtn.addEventListener("click", handleStop);

    const onSlider = () => {
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
  // Boot
  // =========================

  window.addEventListener("DOMContentLoaded", () => {
    initCanvas();
    bindUI();

    // 初期値を state に同期
    warmSlider && (state.warm = warmSlider.valueAsNumber / 100);
    spaceSlider && (state.space = spaceSlider.valueAsNumber / 100);
    chaosSlider && (state.chaos = chaosSlider.valueAsNumber / 100);
    densitySlider && (state.density = densitySlider.valueAsNumber / 100);
  });
})();
