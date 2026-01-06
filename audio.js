// audio.js
window.AudioEngine = (() => {
  let started = false;

  let master, filter, reverb, limiter;
  let pad, pluck;
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
    reverb  = new Tone.Reverb({ decay: 6.5, preDelay: 0.01, wet: 0.22 });

    // Reverbは生成待ちがある（鳴らない/遅延の原因になりやすい）
    await reverb.generate();

    // chain
    filter.connect(reverb);
    reverb.connect(master);
    master.connect(limiter);

    pad = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "sine" },
      envelope: { attack: 0.6, decay: 0.2, sustain: 0.7, release: 2.6 }
    }).connect(filter);

    pluck = new Tone.PluckSynth({
      attackNoise: 0.8,
      dampening: 2500,
      resonance: 0.92
    }).connect(filter);

    // 起動音（小さく）
    const now = Tone.now();
    pad.triggerAttackRelease(["C3","G3","Ab3"], 3.5, now, 0.10);

    started = true;
    console.log("Tone started");
  }

  function onTap(xNorm, intensity=0.6){
    if(!started) return;

    const now = Tone.now();
    const dt = now - lastTapTime;
    lastTapTime = now;

    const n = noteFromX(xNorm);
    const vel = Math.min(0.9, 0.25 + intensity * 0.65);

    pluck.triggerAttackRelease(n, 0.22 + intensity * 0.22, now, vel * 0.85);

    if(dt > 0.18){
      const n2 = noteFromX((xNorm + 0.17) % 1);
      pad.triggerAttackRelease([n, n2], 1.4, now + 0.02, vel * 0.18);
    }
  }

  function updateEnergy(e){
    if(!started) return;
    const energy = Math.max(0, Math.min(1, e));

    filter.frequency.rampTo(600 + energy * 2600, 0.08);
    reverb.wet.rampTo(0.18 + energy * 0.38, 0.12);
    master.gain.rampTo(0.75 + energy * 0.25, 0.12);
  }

  return {
    start,
    onTap,
    updateEnergy,
    get started(){ return started; }
  };
})();