// audio.js
window.AudioEngine = (() => {
  let started = false;

  let master, filter, airFilter, reverb, shimmer, limiter;
  let pad, air, pluck;
  let lastTapTime = 0;
  let currentMood = "water_day";
  let autoOn = false;
  let currentProfileShape = null;

  const scale = ["C", "D", "Eb", "G", "Ab"];
  const MOOD_AUDIO = Object.freeze({
    water_day: {
      gain: 0.72, filterBase: 620, filterRange: 2800, airBase: 320,
      reverbWet: 0.18, shimmerWet: 0.08, tapScale: 0.86, tapMax: 0.62, airChance: 0.48
    },
    garden_morning: {
      gain: 0.70, filterBase: 540, filterRange: 2300, airBase: 280,
      reverbWet: 0.22, shimmerWet: 0.06, tapScale: 0.78, tapMax: 0.56, airChance: 0.52
    },
    family_room: {
      gain: 0.64, filterBase: 500, filterRange: 1900, airBase: 340,
      reverbWet: 0.18, shimmerWet: 0.04, tapScale: 0.64, tapMax: 0.46, airChance: 0.34
    },
    soft_sleep: {
      gain: 0.50, filterBase: 380, filterRange: 1100, airBase: 240,
      reverbWet: 0.28, shimmerWet: 0.035, tapScale: 0.42, tapMax: 0.32, airChance: 0.22
    },
    transparent_evening: {
      gain: 0.68, filterBase: 680, filterRange: 2500, airBase: 380,
      reverbWet: 0.24, shimmerWet: 0.09, tapScale: 0.72, tapMax: 0.52, airChance: 0.42
    }
  });

  function moodAudio(){
    return currentProfileShape ?? MOOD_AUDIO[currentMood] ?? MOOD_AUDIO.water_day;
  }

  function clamp01(value){
    return Math.max(0, Math.min(1, value));
  }

  function levelValue(value){
    return {
      none: 0,
      minimal: 0.08,
      very_low: 0.12,
      low: 0.24,
      low_medium: 0.34,
      low_to_mid: 0.42,
      medium_low: 0.44,
      medium: 0.55,
      medium_high: 0.72,
      high: 0.86,
      very_high: 1,
      gentle: 0.36,
      safe: 0.28,
      soft_warm: 0.5,
      cool: 0.45,
    }[value] ?? 0.5;
  }

  function profileToShape(profile){
    const bias = profile?.input_bias ?? {};
    const brightness = levelValue(bias.brightness);
    const water = levelValue(bias.water_motion);
    const garden = levelValue(bias.garden_air);
    const rhythm = levelValue(bias.rhythm_density);
    const lowEnd = levelValue(bias.low_end_pressure);
    const texture = levelValue(bias.texture_amount);
    const melody = levelValue(bias.melody_presence);
    const sleep = levelValue(bias.sleepiness);
    const familySafe = bias.family_safe !== false;

    const safetyTrim = familySafe ? 0.05 : 0;
    const sleepTrim = sleep * 0.16;

    return {
      gain: clamp01(0.52 + brightness * 0.16 - lowEnd * 0.05 - sleepTrim - safetyTrim * 0.4),
      filterBase: 360 + brightness * 430,
      filterRange: 900 + brightness * 1650 + water * 420,
      airBase: 220 + garden * 260 + brightness * 80,
      reverbWet: Math.min(0.38, 0.16 + garden * 0.08 + sleep * 0.08),
      shimmerWet: Math.min(0.18, 0.035 + water * 0.075 + texture * 0.035),
      tapScale: clamp01(0.34 + water * 0.26 + rhythm * 0.12 + melody * 0.12 - sleep * 0.22),
      tapMax: clamp01(0.30 + brightness * 0.18 + melody * 0.12 - sleep * 0.16),
      airChance: clamp01(0.20 + garden * 0.28 + water * 0.12 + sleep * 0.08),
      melodyChance: clamp01(0.08 + melody * 0.34 + water * 0.10 - sleep * 0.20),
      padChance: clamp01(0.20 + garden * 0.20 + water * 0.12 - sleep * 0.08),
    };
  }

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
    applyMood(0.05);

    started = true;
    console.log("Tone started");
  }

  function onTap(xNorm, intensity=0.6){
    if(!started) return;

    const now = Tone.now();
    const dt = now - lastTapTime;
    lastTapTime = now;

    const shape = moodAudio();
    const n = noteFromX(xNorm);
    const vel = Math.min(shape.tapMax, (0.12 + intensity * 0.45) * shape.tapScale);

    if(Math.random() < (shape.melodyChance ?? 0.32)){
      pluck.triggerAttackRelease(n, 0.22 + intensity * 0.22, now, vel * 0.85);
    }

    if(dt > 0.18 && Math.random() < (shape.padChance ?? 0.36)){
      const n2 = noteFromX((xNorm + 0.17) % 1);
      pad.triggerAttackRelease([n, n2], 1.4, now + 0.02, vel * 0.14);
    }

    if(Math.random() < shape.airChance){
      const n2 = noteFromX((xNorm + 0.2) % 1);
      air.triggerAttackRelease([n, n2], 2.8, now + 0.02, vel * 0.16);
    }
  }

  function applyMood(ramp=0.6){
    if(!started) return;
    const shape = moodAudio();
    filter.frequency.rampTo(shape.filterBase + shape.filterRange * 0.18, ramp);
    airFilter.frequency.rampTo(shape.airBase, ramp);
    reverb.wet.rampTo(shape.reverbWet, ramp);
    shimmer.wet.rampTo(shape.shimmerWet, ramp);
    master.gain.rampTo(shape.gain, ramp);
  }

  function setMood(mood){
    if(!MOOD_AUDIO[mood]) return currentMood;
    currentMood = mood;
    currentProfileShape = null;
    applyMood(1.2);
    return currentMood;
  }

  function setMoodProfile(profile){
    if(!profile || profile.id !== currentMood) return currentMood;
    currentProfileShape = profileToShape(profile);
    applyMood(1.2);
    return currentMood;
  }

  function setAuto(enabled){
    autoOn = Boolean(enabled);
    return autoOn;
  }

  function updateEnergy(e){
    if(!started) return;
    const energy = Math.max(0, Math.min(1, e));
    const shape = moodAudio();
    const autoLift = autoOn ? 0.03 : 0;

    filter.frequency.rampTo(shape.filterBase + energy * shape.filterRange, 0.12);
    airFilter.frequency.rampTo(shape.airBase + energy * 420, 0.16);
    reverb.wet.rampTo(Math.min(0.42, shape.reverbWet + energy * 0.16 + autoLift), 0.18);
    shimmer.wet.rampTo(Math.min(0.22, shape.shimmerWet + energy * 0.11), 0.18);
    master.gain.rampTo(Math.min(0.78, shape.gain + energy * 0.08), 0.18);
  }

  return {
    start,
    onTap,
    updateEnergy,
    setMood,
    setMoodProfile,
    setAuto,
    get mood(){ return currentMood; },
    get auto(){ return autoOn; },
    get started(){ return started; }
  };
})();
