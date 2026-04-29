// audio.js
window.AudioEngine = (() => {
  let started = false;

  let master, filter, airFilter, reverb, shimmer, limiter;
  let pad, air, pluck;
  let lastTapTime = 0;

  const scale = ["C", "D", "Eb", "G", "Ab"];

  function noteFromX(xNorm){
    const octave = 3 + Math.floor(xNorm * 3); // 3..5
    const idx = Math.floor(xNorm * scale.length) % scale.length;
    return `${scale[idx]}${octave}`;
  }

  async function start(){
    if(started) return;

    await Tone.start();
    // iOSで念のため
    if (Tone.context.state !== "running") await Tone.context.resume();

    limiter = new Tone.Limiter(-1).toDestination();
    master  = new Tone.Gain(0.9);
    filter  = new Tone.Filter({ type:"lowpass", frequency: 900, Q: 0.6 });
    airFilter = new Tone.Filter({ type:"highpass", frequency: 360, Q: 0.5 });
    reverb  = new Tone.Reverb({ decay: 6.5, preDelay: 0.01, wet: 0.22 });
    shimmer = new Tone.FeedbackDelay({ delayTime: "8n", feedback: 0.20, wet: 0.05 });

    // Reverbは生成待ちがある（鳴らない/遅延の原因になりやすい）
    await reverb.generate();

    // chain
    filter.connect(reverb);
    airFilter.connect(reverb);
    reverb.connect(shimmer);
    shimmer.connect(master);
    master.connect(limiter);

    pad = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "sine" },
      envelope: { attack: 0.6, decay: 0.2, sustain: 0.7, release: 2.6 }
    }).connect(filter);

    air = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "sine" },
      envelope: { attack: 1.6, decay: 0.4, sustain: 0.72, release: 5.0 }
    }).connect(airFilter);

    pluck = new Tone.PluckSynth({
      attackNoise: 0.8,
      dampening: 2500,
      resonance: 0.92
    }).connect(filter);

    // 起動音（小さく）
    const now = Tone.now();
    pad.triggerAttackRelease(["C3","G3","Ab3"], 3.5, now, 0.10);
    air.triggerAttackRelease(["C4","G4","Ab4"], 5.5, now + 0.05, 0.035);

    started = true;
    console.log("Tone started");
  }

  function onTap(xNorm, intensity=0.6){
    if(!started) return;

    const now = Tone.now();
    const dt = now - lastTapTime;
    lastTapTime = now;

    const n = noteFromX(xNorm);
    const vel = Math.min(0.72, 0.12 + intensity * 0.45);

    pluck.triggerAttackRelease(n, 0.22 + intensity * 0.22, now, vel * 0.85);

    if(dt > 0.18){
      const n2 = noteFromX((xNorm + 0.17) % 1);
      pad.triggerAttackRelease([n, n2], 1.4, now + 0.02, vel * 0.14);
    }

    if(Math.random() < 0.45){
      const n2 = noteFromX((xNorm + 0.2) % 1);
      air.triggerAttackRelease([n, n2], 2.8, now + 0.02, vel * 0.16);
    }
  }

  function updateEnergy(e){
    if(!started) return;
    const energy = Math.max(0, Math.min(1, e));

    filter.frequency.rampTo(580 + energy * 2800, 0.12);
    airFilter.frequency.rampTo(300 + energy * 520, 0.16);
    reverb.wet.rampTo(0.16 + energy * 0.34, 0.18);
    shimmer.wet.rampTo(0.04 + energy * 0.20, 0.18);
    master.gain.rampTo(0.72 + energy * 0.12, 0.18);
  }

  return {
    start,
    onTap,
    updateEnergy,
    get started(){ return started; }
  };
})();
