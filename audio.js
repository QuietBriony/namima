// audio.js
// 重要：AudioEngine を window に生やす（let だと window.AudioEngine にならない）
// さらに Reverb は Freeverb にして iPhone 安定化

window.AudioEngine = (() => {
  let started = false;

  let master, filter, reverb, limiter;
  let pad, pluck;
  let lastTapTime = 0;

  const scale = ["C", "D", "Eb", "G", "Ab"]; // minor-ish pentatonic
  function noteFromX(xNorm) {
    const octave = 3 + Math.floor(xNorm * 3); // 3..5
    const idx = Math.floor(xNorm * scale.length) % scale.length;
    return `${scale[idx]}${octave}`;
  }

  async function start() {
    if (started) return;

    await Tone.start();

    limiter = new Tone.Limiter(-1).toDestination();

    // iPhone向けに軽いリバーブ
    reverb = new Tone.Freeverb({
      roomSize: 0.75,
      dampening: 2500,
      wet: 0.22,
    });

    filter = new Tone.Filter({
      type: "lowpass",
      frequency: 900,
      Q: 0.6,
    });

    master = new Tone.Gain(0.9);

    // chain: synths -> filter -> reverb -> master -> limiter
    filter.connect(reverb);
    reverb.connect(master);
    master.connect(limiter);

    pad = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "sine" },
      envelope: { attack: 0.6, decay: 0.2, sustain: 0.7, release: 2.6 },
    }).connect(filter);

    pluck = new Tone.PluckSynth({
      attackNoise: 0.8,
      dampening: 2500,
      resonance: 0.92,
    }).connect(filter);

    // gentle background chord
    const now = Tone.now();
    pad.triggerAttackRelease(["C3", "G3", "Ab3"], 6, now, 0.08);

    started = true;
  }

  function onTap(xNorm, intensity = 0.6) {
    if (!started) return;

    const now = Tone.now();
    const dt = now - lastTapTime;
    lastTapTime = now;

    const n = noteFromX(xNorm);
    const vel = Math.min(0.9, 0.25 + intensity * 0.65);

    pluck.triggerAttackRelease(n, 0.25 + intensity * 0.25, now, vel * 0.8);

    // occasional pad sparkle
    if (dt > 0.18) {
      const n2 = noteFromX((xNorm + 0.17) % 1);
      pad.triggerAttackRelease([n, n2], 1.8, now + 0.02, vel * 0.18);
    }
  }

  function updateEnergy(e) {
    if (!started) return;
    const energy = Math.max(0, Math.min(1, e));

    const f = 600 + energy * 2600;
    filter.frequency.rampTo(f, 0.08);

    const w = 0.18 + energy * 0.38;
    reverb.wet.rampTo(w, 0.12);

    const g = 0.75 + energy * 0.25;
    master.gain.rampTo(g, 0.12);
  }

  return {
    start,
    onTap,
    updateEnergy,
    get started() {
      return started;
    },
  };
})();