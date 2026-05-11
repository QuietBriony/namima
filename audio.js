// audio.js
window.AudioEngine = (() => {
  let started = false;

  let master, filter, airFilter, tailFilter, tailDelay, tailGain, reverb, shimmer, limiter;
  let pad, air, pluck;
  let lastTapTime = 0;
  let currentMood = "water_day";
  let autoOn = false;
  let currentProfileShape = null;
  let lastAmbientConcept = null;

  const scale = ["C", "D", "Eb", "G", "Ab"];
  const MOOD_AUDIO = Object.freeze({
    water_day: {
      gain: 0.72, filterBase: 620, filterRange: 2800, airBase: 320,
      reverbWet: 0.18, shimmerWet: 0.08, tailWet: 0.07, tailGain: 0.1, tailCutoff: 1650,
      tapScale: 0.86, tapMax: 0.62, airChance: 0.48
    },
    garden_morning: {
      gain: 0.70, filterBase: 540, filterRange: 2300, airBase: 280,
      reverbWet: 0.22, shimmerWet: 0.06, tailWet: 0.08, tailGain: 0.11, tailCutoff: 1500,
      tapScale: 0.78, tapMax: 0.56, airChance: 0.52
    },
    family_room: {
      gain: 0.64, filterBase: 500, filterRange: 1900, airBase: 340,
      reverbWet: 0.18, shimmerWet: 0.04, tailWet: 0.045, tailGain: 0.075, tailCutoff: 1320,
      tapScale: 0.64, tapMax: 0.46, airChance: 0.34
    },
    soft_sleep: {
      gain: 0.50, filterBase: 380, filterRange: 1100, airBase: 240,
      reverbWet: 0.28, shimmerWet: 0.035, tailWet: 0.055, tailGain: 0.065, tailCutoff: 980,
      tapScale: 0.42, tapMax: 0.32, airChance: 0.22
    },
    transparent_evening: {
      gain: 0.68, filterBase: 680, filterRange: 2500, airBase: 380,
      reverbWet: 0.24, shimmerWet: 0.09, tailWet: 0.095, tailGain: 0.12, tailCutoff: 1780,
      tapScale: 0.72, tapMax: 0.52, airChance: 0.42
    }
  });

  function moodAudio(){
    return currentProfileShape ?? MOOD_AUDIO[currentMood] ?? MOOD_AUDIO.water_day;
  }

  function clamp01(value){
    return Math.max(0, Math.min(1, value));
  }

  function masteredGain(value){
    return Math.min(0.8, value * 1.08 + 0.02);
  }

  function numberOr(value, fallback){
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function normalizeAmbientConcept(input, fallbackEnergy=0){
    if(!input || typeof input !== "object"){
      const energy = clamp01(numberOr(input, fallbackEnergy));
      return {
        safe_energy: energy,
        water_shimmer: energy,
        air_lift: energy * 0.74,
        soft_pulse_visibility: energy * 0.34,
        melody_fragment_probability: energy * 0.12,
        fade_back_time: 1.8,
        audio_energy: energy,
      };
    }

    const safeEnergy = clamp01(numberOr(input.safe_energy ?? input.ripple_energy, fallbackEnergy));
    const waterShimmer = clamp01(numberOr(input.water_shimmer, safeEnergy));
    const airLift = clamp01(numberOr(input.air_lift, safeEnergy * 0.74));
    const softPulse = clamp01(numberOr(input.soft_pulse_visibility, safeEnergy * 0.34));
    const melodyProbability = clamp01(numberOr(input.melody_fragment_probability, safeEnergy * 0.12));
    return {
      safe_energy: safeEnergy,
      water_shimmer: waterShimmer,
      air_lift: airLift,
      soft_pulse_visibility: softPulse,
      melody_fragment_probability: melodyProbability,
      fade_back_time: Math.max(1.25, Math.min(3.8, numberOr(input.fade_back_time, 1.8))),
      audio_energy: clamp01(numberOr(input.audio_energy, waterShimmer * 0.42 + airLift * 0.38 + softPulse * 0.16 + melodyProbability * 0.04)),
    };
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
      tailWet: Math.min(0.15, 0.035 + water * 0.055 + garden * 0.045 + sleep * 0.025),
      tailGain: Math.min(0.14, 0.055 + garden * 0.04 + water * 0.04 - lowEnd * 0.02),
      tailCutoff: 920 + brightness * 760 + water * 360 + garden * 180,
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

    limiter = new Tone.Limiter(-0.8).toDestination();
    master  = new Tone.Gain(0.9);
    filter  = new Tone.Filter({ type:"lowpass", frequency: 900, Q: 0.6 });
    airFilter = new Tone.Filter({ type:"highpass", frequency: 360, Q: 0.5 });
    tailFilter = new Tone.Filter({ type:"lowpass", frequency: 1450, Q: 0.45 });
    tailDelay = new Tone.FeedbackDelay({ delayTime: "4n", feedback: 0.14, wet: 0.06 });
    tailGain = new Tone.Gain(0.09);
    reverb  = new Tone.Reverb({ decay: 6.5, preDelay: 0.01, wet: 0.22 });
    shimmer = new Tone.FeedbackDelay({ delayTime: "8n", feedback: 0.20, wet: 0.05 });

    // Reverbは生成待ちがある（鳴らない/遅延の原因になりやすい）
    await reverb.generate();

    // chain
    filter.connect(reverb);
    airFilter.connect(reverb);
    filter.connect(tailFilter);
    airFilter.connect(tailFilter);
    tailFilter.connect(tailDelay);
    tailDelay.connect(tailGain);
    tailGain.connect(master);
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

  function onTap(xNorm, intensity=0.6, conceptInput=null){
    if(!started) return;

    const now = Tone.now();
    const dt = now - lastTapTime;
    lastTapTime = now;

    const shape = moodAudio();
    const concept = normalizeAmbientConcept(conceptInput, intensity);
    lastAmbientConcept = concept;
    const n = noteFromX(clamp01(xNorm));
    const vel = Math.min(shape.tapMax, (0.10 + concept.safe_energy * 0.30 + concept.soft_pulse_visibility * 0.05) * shape.tapScale);
    const melodyChance = Math.min(0.36, (shape.melodyChance ?? 0.28) * 0.55 + concept.melody_fragment_probability * 0.62);
    const padChance = Math.min(0.52, (shape.padChance ?? 0.32) * 0.56 + concept.soft_pulse_visibility * 0.34);
    const airChance = Math.min(0.76, shape.airChance * 0.58 + concept.air_lift * 0.42);

    if(Math.random() < melodyChance){
      pluck.triggerAttackRelease(n, 0.20 + concept.safe_energy * 0.16, now, vel * 0.82);
    }

    if(dt > 0.18 && Math.random() < padChance){
      const n2 = noteFromX((clamp01(xNorm) + 0.17) % 1);
      pad.triggerAttackRelease([n, n2], 1.2 + concept.fade_back_time * 0.36, now + 0.02, vel * 0.12);
    }

    if(Math.random() < airChance){
      const n2 = noteFromX((clamp01(xNorm) + 0.2) % 1);
      air.triggerAttackRelease([n, n2], 2.2 + concept.fade_back_time * 0.72, now + 0.02, vel * 0.14);
    }
  }

  function applyMood(ramp=0.6){
    if(!started) return;
    const shape = moodAudio();
    filter.frequency.rampTo(shape.filterBase + shape.filterRange * 0.18, ramp);
    airFilter.frequency.rampTo(shape.airBase, ramp);
    tailFilter.frequency.rampTo(shape.tailCutoff ?? 1450, ramp);
    reverb.wet.rampTo(shape.reverbWet, ramp);
    shimmer.wet.rampTo(shape.shimmerWet, ramp);
    tailDelay.wet.rampTo(shape.tailWet ?? 0.06, ramp);
    tailDelay.feedback.value = Math.min(0.24, 0.11 + (shape.tailWet ?? 0.06) * 0.85);
    tailGain.gain.rampTo(shape.tailGain ?? 0.09, ramp);
    master.gain.rampTo(masteredGain(shape.gain), ramp);
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

  function updateEnergy(input){
    if(!started) return;
    const concept = normalizeAmbientConcept(input, 0);
    lastAmbientConcept = concept;
    const shape = moodAudio();
    const autoLift = autoOn ? 0.03 : 0;

    filter.frequency.rampTo(shape.filterBase + concept.water_shimmer * shape.filterRange * 0.86, 0.16);
    airFilter.frequency.rampTo(shape.airBase + concept.air_lift * 360, 0.18);
    tailFilter.frequency.rampTo((shape.tailCutoff ?? 1450) + concept.water_shimmer * 260 + concept.air_lift * 120, 0.22);
    reverb.wet.rampTo(Math.min(0.40, shape.reverbWet + concept.air_lift * 0.11 + autoLift), 0.22);
    shimmer.wet.rampTo(Math.min(0.21, shape.shimmerWet + concept.water_shimmer * 0.09), 0.22);
    tailDelay.wet.rampTo(Math.min(0.16, (shape.tailWet ?? 0.06) + concept.soft_pulse_visibility * 0.028), 0.22);
    tailGain.gain.rampTo(Math.min(0.135, (shape.tailGain ?? 0.09) + concept.soft_pulse_visibility * 0.018), 0.22);
    master.gain.rampTo(masteredGain(shape.gain + concept.air_lift * 0.026), 0.22);
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
    get ambientConcept(){ return lastAmbientConcept; },
    get started(){ return started; }
  };
})();
