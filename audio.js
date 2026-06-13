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

  // 自走する優しい声 (bloom): namima の役割「soft continuous listening」。
  let bloomOn = true;       // start 後、タップ無しでも穏やかに鳴り続ける
  let bloomTimer = null;
  let bloomX = 0.42;        // 音名 / レジスタ位置。隣へ歩く小旋律 (= ランダム回避)
  let bloomDir = 1;         // 歩く向き (端で反転)
  let bloomCount = 0;

  // 潮 (tide) v2: home → deep → bright の 3 区間を ~3.2 分で一巡。区間ごとに
  // 音名プールだけでなく音場 (filter / reverb / tail) も傾き、変わり目には
  // 淡い告知和音が一度鳴る — v1「あまり変化ない」への増幅。
  const TIDE_SECTIONS = Object.freeze([
    Object.freeze({ name: "home",   pool: Object.freeze(["C", "D", "Eb", "G", "Ab"]), filt: 1.0,  verb: 1.0,  tail: 1.0  }),
    Object.freeze({ name: "deep",   pool: Object.freeze(["C", "Eb", "F", "G", "Bb"]), filt: 0.86, verb: 1.14, tail: 0.92 }),
    Object.freeze({ name: "bright", pool: Object.freeze(["C", "D", "F", "G", "A"]),   filt: 1.16, verb: 0.92, tail: 1.12 }),
  ]);
  const TIDE_PERIOD_MS = 192000;

  function tidePhase(){
    return (Date.now() % TIDE_PERIOD_MS) / TIDE_PERIOD_MS;
  }

  function tideSection(){
    const phase = tidePhase();
    return TIDE_SECTIONS[phase < 0.5 ? 0 : phase < 0.75 ? 1 : 2];
  }

  function tideScale(){
    return tideSection().pool;
  }

  let lastTideName = null;

  // 区間が変わって最初の便で一度だけ、その潮のトライアドを淡く告知する。
  function announceTideTurn(){
    const section = tideSection();
    if(lastTideName === section.name) return;
    const wasFirst = lastTideName === null;
    lastTideName = section.name;
    if(wasFirst || !started) return;
    try {
      const now = Tone.now();
      const p = section.pool;
      pad.triggerAttackRelease([`${p[0]}3`, `${p[3]}3`, `${p[4]}3`], 5.5, now + 0.05, 0.055);
      air.triggerAttackRelease([`${p[0]}4`, `${p[4]}4`], 7, now + 0.4, 0.028);
    } catch (error) {
      console.warn("[Namima] tide announce failed", error);
    }
  }
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

  function releaseVoices(reason="release"){
    const now = typeof Tone !== "undefined" && typeof Tone.now === "function" ? Tone.now() : 0;
    [pad, air, pluck].forEach((voice) => {
      try {
        if(typeof voice?.releaseAll === "function") voice.releaseAll(now);
        else if(typeof voice?.triggerRelease === "function") voice.triggerRelease(now);
      } catch (error) {
        console.warn(`[Namima] ${reason} release failed`, error);
      }
    });
  }

  function disposeNodes(nodes){
    nodes.forEach((node) => {
      try { node?.dispose?.(); } catch (error) {
        console.warn("[Namima] dispose failed", error);
      }
    });
  }

  function panic(reason="panic"){
    stopBloom();
    if(!started) return { started:false, reason };
    const nodes = [pad, air, pluck, shimmer, reverb, tailGain, tailDelay, tailFilter, airFilter, filter, master, limiter];
    releaseVoices(reason);
    try { Tone.Transport?.stop?.(); } catch (_error) {}
    try {
      const now = Tone.now();
      master?.gain?.cancelScheduledValues?.(now);
      master?.gain?.rampTo?.(0.0001, 0.08);
    } catch (_error) {}

    started = false;
    master = filter = airFilter = tailFilter = tailDelay = tailGain = reverb = shimmer = limiter = null;
    pad = air = pluck = null;
    window.setTimeout(() => disposeNodes(nodes), 360);
    return { started:false, reason };
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
    const pool = tideScale();
    const octave = 3 + Math.floor(xNorm * 3); // 3..5
    const idx = Math.floor(xNorm * pool.length) % pool.length;
    return `${pool[idx]}${octave}`;
  }

  // 相方ノート: 同じ位置から scale を stepUp 度ぶん上る。旧実装の
  // (x + 0.17) % 1 は wrap 時に register が飛んで dyad が他人になっていた。
  function companionNote(xNorm, stepUp){
    const pool = tideScale();
    const octave = 3 + Math.floor(xNorm * 3);
    const idx = Math.floor(xNorm * pool.length) % pool.length;
    const lifted = idx + stepUp;
    return `${pool[lifted % pool.length]}${Math.min(5, octave + Math.floor(lifted / pool.length))}`;
  }

  // 自走する優しい声。pitch は隣へ歩く小旋律で潮プールから採り、family-safe な
  // 小音量。人間がタップ中 (直近 ~5s) は身を引き、静かになると戻る。
  function bloomIntervalMs(){
    const shape = moodAudio();
    // 活気 (tapScale) が高い mood ほどやや忙しく、sleep 系はゆったり。
    const base = 5200 - shape.tapScale * 2200;   // ~3.0s..4.9s
    return base + Math.random() * 1600;          // + ゆらぎ
  }

  function stepBloomX(){
    // 下降グラビティ付きの小さなランダムウォーク。端で反転。
    const stride = 0.12 + Math.random() * 0.1;
    bloomX += bloomDir * stride - 0.03;          // 軽い下降バイアス
    if(bloomX > 0.96){ bloomX = 0.96; bloomDir = -1; }
    if(bloomX < 0.06){ bloomX = 0.06; bloomDir = 1; }
    return clamp01(bloomX);
  }

  function emitBloom(){
    if(!started || !pad) return;
    const shape = moodAudio();
    const now = Tone.now();
    const sinceTap = now - lastTapTime;
    // 人間がタップ中は自走を控える。完全には消さず確率で間引く。
    if(sinceTap < 5 && Math.random() > 0.2) return;

    const x = stepBloomX();
    const n = noteFromX(x);
    const baseVel = 0.05 + shape.tapScale * 0.05; // ~0.05..0.1 (family-safe)
    bloomCount += 1;

    // 主音: 柔らかい pad sine (filter + reverb 経由)。
    pad.triggerAttackRelease(n, 2.0 + shape.tapScale * 1.2, now, baseVel * 0.9);

    // 4 音に 1 回、companion で淡い dyad (倍音の広がり)。
    if(bloomCount % 4 === 0){
      const n2 = companionNote(x, 2);
      air.triggerAttackRelease([n, n2], 3.4, now + 0.18, baseVel * 0.5);
    }

    // たまに pluck の「ピロ」を一粒。sleep 系の静けさでは出さない。
    if(shape.tapScale > 0.5 && Math.random() < 0.34){
      pluck.triggerAttackRelease(companionNote(x, 1), 0.3, now + 0.12, baseVel * 0.7);
    }
  }

  function stopBloom(){
    window.clearTimeout(bloomTimer);
    bloomTimer = null;
  }

  function scheduleBloom(){
    stopBloom();
    if(!started || !bloomOn) return;
    bloomTimer = window.setTimeout(() => {
      try { emitBloom(); }
      catch(error){ console.warn("[Namima] bloom failed", error); }
      scheduleBloom();
    }, bloomIntervalMs());
  }

  function setBloom(enabled){
    bloomOn = Boolean(enabled);
    if(bloomOn && started) scheduleBloom();
    else stopBloom();
    return bloomOn;
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
    // PingPong は tail の echo 成分だけを L/R に振る (水面の反射)。
    // Tone build に無ければ従来のモノ delay へ fallback。
    tailDelay = typeof Tone.PingPongDelay === "function"
      ? new Tone.PingPongDelay({ delayTime: "4n", feedback: 0.14, wet: 0.06 })
      : new Tone.FeedbackDelay({ delayTime: "4n", feedback: 0.14, wet: 0.06 });
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

    // 起動音（小さく・その時の潮のトライアド）
    const now = Tone.now();
    const p = tideScale();
    lastTideName = tideSection().name;
    pad.triggerAttackRelease([`${p[0]}3`, `${p[3]}3`, `${p[4]}3`], 3.5, now, 0.10);
    air.triggerAttackRelease([`${p[0]}4`, `${p[3]}4`, `${p[4]}4`], 5.5, now + 0.05, 0.035);
    applyMood(0.05);

    started = true;
    console.log("Tone started");
    scheduleBloom();
  }

  function onTap(xNorm, intensity=0.6, conceptInput=null){
    if(!started) return;
    announceTideTurn();

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
      const n2 = companionNote(clamp01(xNorm), 2);
      pad.triggerAttackRelease([n, n2], 1.2 + concept.fade_back_time * 0.36, now + 0.02, vel * 0.12);
    }

    if(Math.random() < airChance){
      const n2 = companionNote(clamp01(xNorm), 3);
      air.triggerAttackRelease([n, n2], 2.2 + concept.fade_back_time * 0.72, now + 0.02, vel * 0.14);
    }
  }

  function applyMood(ramp=0.6){
    if(!started) return;
    const shape = moodAudio();
    const tide = tideSection();
    filter.frequency.rampTo((shape.filterBase + shape.filterRange * 0.18) * tide.filt, ramp);
    airFilter.frequency.rampTo(shape.airBase, ramp);
    tailFilter.frequency.rampTo((shape.tailCutoff ?? 1450) * tide.tail, ramp);
    reverb.wet.rampTo(Math.min(0.40, shape.reverbWet * tide.verb), ramp);
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
    announceTideTurn();
    const concept = normalizeAmbientConcept(input, 0);
    lastAmbientConcept = concept;
    const shape = moodAudio();
    const autoLift = autoOn ? 0.03 : 0;
    const tide = tideSection();

    filter.frequency.rampTo((shape.filterBase + concept.water_shimmer * shape.filterRange * 0.86) * tide.filt, 0.16);
    airFilter.frequency.rampTo(shape.airBase + concept.air_lift * 360, 0.18);
    tailFilter.frequency.rampTo(((shape.tailCutoff ?? 1450) + concept.water_shimmer * 260 + concept.air_lift * 120) * tide.tail, 0.22);
    reverb.wet.rampTo(Math.min(0.40, (shape.reverbWet + concept.air_lift * 0.11 + autoLift) * tide.verb), 0.22);
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
    setBloom,
    releaseVoices,
    panic,
    get mood(){ return currentMood; },
    get auto(){ return autoOn; },
    get bloomOn(){ return bloomOn; },
    get bloom(){ return { on: bloomOn, x: Number(bloomX.toFixed(3)), scheduled: bloomTimer !== null }; },
    get tide(){ const s = tideSection(); return { phase: Number(tidePhase().toFixed(3)), section: s.name, pool: s.pool.slice() }; },
    get ambientConcept(){ return lastAmbientConcept; },
    get started(){ return started; }
  };
})();
