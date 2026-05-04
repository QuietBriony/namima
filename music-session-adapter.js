// Music session packet -> Namima safe mood translation.
window.NamimaMusicSessionAdapter = (() => {
  function clamp(value, min, max){
    const number = Number(value);
    if(!Number.isFinite(number)) return min;
    return Math.max(min, Math.min(max, number));
  }

  function unit(value, fallback=0){
    const number = Number(value);
    if(!Number.isFinite(number)) return fallback;
    return clamp(number, 0, 1);
  }

  function percent(value, fallback=0){
    const number = Number(value);
    if(!Number.isFinite(number)) return fallback;
    return clamp(number, 0, 100);
  }

  function object(value){
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function chooseMood(packet, namima, gradient){
    const moodIntent = object(namima.mood_intent);
    const mood = String(moodIntent.mood || namima.mood_intent || "").toLowerCase();
    const ucm = object(packet?.ucm_state);
    const energy = percent(ucm.energy, 0) / 100;
    const voidness = percent(ucm.void, 0) / 100;
    const circle = percent(ucm.circle, 0) / 100;
    const observer = percent(ucm.observer, 0) / 100;
    const calm = circle * 0.3 + observer * 0.28 + voidness * 0.2 + unit(gradient.haze) * 0.22;

    if(namima.family_safe === false) return "family_room";
    if(mood.includes("transparent") || voidness > 0.58) return energy < 0.28 ? "soft_sleep" : "transparent_evening";
    if(mood.includes("garden") || calm > 0.62) return "garden_morning";
    if(mood.includes("family") || energy > 0.52) return "family_room";
    if(mood.includes("sleep")) return "soft_sleep";
    return "water_day";
  }

  function translateMusicSessionPacket(packet){
    const routing = object(packet?.routing);
    const namima = object(routing.namima);
    const gradient = object(packet?.reference_gradient?.weights);
    const ucm = object(packet?.ucm_state);
    const moodId = chooseMood(packet, namima, gradient);
    const brightness = unit(namima.brightness, unit(gradient.chrome, 0.42));
    const waterMotion = unit(namima.water_motion, percent(ucm.wave, 35) / 100);
    const calmContinuity = unit((percent(ucm.circle, 0) + percent(ucm.observer, 0)) / 200, 0.45);
    const energy = percent(ucm.energy, 0) / 100;
    const safeEnergyCap = unit(object(namima.mood_intent).safe_energy_cap, 0.54);

    return {
      schema: "namima.music-session-mood-adapter.v1",
      source_repo: "Music",
      source_session_id: packet?.session_id || "",
      enabled: namima.enabled !== false,
      review_only: true,
      mood_id: moodId,
      intent: {
        family_safe: namima.family_safe !== false,
        water_motion: Number(waterMotion.toFixed(3)),
        brightness: Number(Math.min(brightness, 0.78).toFixed(3)),
        calm_continuity: Number(calmContinuity.toFixed(3)),
        energy_cap: Number(Math.min(safeEnergyCap, 0.62).toFixed(3)),
        foreground_energy: Number(Math.min(energy, 0.52).toFixed(3))
      },
      visual_hint: {
        mode: moodId === "transparent_evening" ? "orbit" : "water",
        ripple_response: Number(Math.min(0.72, 0.28 + waterMotion * 0.34 + calmContinuity * 0.1).toFixed(3))
      },
      safety: {
        stores_audio: false,
        stores_samples: false,
        metadata_only: true,
        human_review_required: true,
        dark_glitch: false,
        bass_pressure: false,
        auto_upload: false
      }
    };
  }

  function applyMusicSessionPacket(packet, options={}){
    const translation = translateMusicSessionPacket(packet);
    window.NamimaMusicSessionAdapter.last = translation;
    if(!translation.enabled || options.previewOnly === true) return translation;
    if(typeof window.setMood === "function") window.setMood(translation.mood_id, { manual: true });
    return translation;
  }

  return {
    translateMusicSessionPacket,
    applyMusicSessionPacket,
    last: null
  };
})();
