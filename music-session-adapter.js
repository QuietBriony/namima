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

  function intentTokens(value){
    if(Array.isArray(value)) return value.map((item) => String(item || "").toLowerCase());
    if(value && typeof value === "object") {
      return Object.values(value).map((item) => String(item || "").toLowerCase());
    }
    return String(value || "").toLowerCase().split(/[\s,;/|]+/).filter(Boolean);
  }

  function moodIntent(value){
    const obj = object(value);
    const tokens = intentTokens(value);
    const mood = String(obj.mood || tokens.find((token) => (
      token.includes("water") ||
      token.includes("garden") ||
      token.includes("transparent") ||
      token.includes("family") ||
      token.includes("sleep")
    )) || "").toLowerCase();
    return {
      mood,
      safeEnergyCap: obj.safe_energy_cap,
      tokens
    };
  }

  function destinationFromTargetRepo(targetRepo){
    const map = {
      Music: "music",
      "drum-floor": "drum_floor",
      namima: "namima",
      chill: "chill",
      OpenClaw: "openclaw"
    };
    return map[targetRepo] || "openclaw";
  }

  function hazamaContext(packet){
    const performance = object(packet?.performance_state);
    const hazama = object(performance.hazama_fm);
    const routing = object(packet?.routing);
    const nextAction = object(object(routing.openclaw).next_action);
    const cue = object(hazama.review_cue || nextAction.fm_review_cue);
    const trace = object(hazama.listening_trace);
    return {
      active: hazama.active === true,
      genre: String(trace.current_genre || hazama.genre || "").toLowerCase(),
      source: String(hazama.source || "").toLowerCase(),
      role: String(hazama.role || "").toLowerCase(),
      cue_label: String(cue.short_label || cue.label || "").toLowerCase(),
      next_task: String(cue.next_task || "").toLowerCase(),
      target_repo: String(cue.target_repo || cue.destination || nextAction.destination || "").toLowerCase(),
      metadata_only: hazama.integration_mode === "metadata-only" || cue.metadata_only !== false
    };
  }

  function sourceContext(packet){
    const hazama = hazamaContext(packet);
    const mode = String(packet?.mode || "").toLowerCase();
    const radio = object(object(packet?.performance_state).radio_brain);
    const openclaw = object(object(packet?.routing).openclaw);
    const nextAction = object(openclaw.next_action);
    const sourceSurface = mode === "band_room" || String(radio.program || "").toLowerCase() === "band-room"
      ? "band_room"
      : (hazama.active || hazama.genre || hazama.cue_label)
        ? "hazama_fm"
        : "music_core";
    return {
      source_surface: sourceSurface,
      route_destination: String(nextAction.destination || ""),
      review_hint: String(nextAction.label || nextAction.reason || ""),
      hazama_fm: hazama,
      band_room: sourceSurface === "band_room"
        ? {
            section: String(packet?.performance_state?.active_pad || ""),
            review_only: true,
            metadata_only: true
          }
        : null
    };
  }

  function hazamaMoodOverride(context, energy){
    const hazama = context.hazama_fm || {};
    const text = `${hazama.genre} ${hazama.source} ${hazama.role} ${hazama.cue_label} ${hazama.next_task} ${hazama.target_repo}`;
    if(!text.trim()) return "";
    if(text.includes("ambient") || text.includes("namima") || text.includes("safe ambient")) {
      return energy > 0.46 ? "water_day" : "garden_morning";
    }
    if(text.includes("piano foreground")) {
      return "transparent_evening";
    }
    if(text.includes("chill") || text.includes("piano")) {
      return energy < 0.24 ? "soft_sleep" : "transparent_evening";
    }
    if(text.includes("techno balance") || text.includes("drum") || text.includes("funk")) {
      return energy > 0.5 ? "family_room" : "water_day";
    }
    return "";
  }

  function normalizeMusicPacket(packet){
    if(!packet || packet.version !== "music-orchestra-packet.v1") return packet;
    const musicState = object(packet.music_state);
    const performance = object(musicState.performance_summary);
    const routing = object(packet.routing);
    const namima = object(routing.namima);
    const openclaw = object(routing.openclaw);
    const promotion = object(packet.promotion);
    return {
      version: 1,
      source_repo: "Music",
      created_at: packet.created_at,
      session_id: packet.session_id,
      mode: musicState.mode || "orchestra",
      reference_gradient: {
        weights: object(packet.reference_gradient)
      },
      ucm_state: object(musicState.ucm_state),
      performance_state: {
        active_pad: performance.active_pad || null,
        recent_pads: Array.isArray(performance.recent_pads) ? performance.recent_pads : [],
        automix_enabled: !!performance.automix_enabled,
        mic_follow: object(packet.mic_follow),
        radio_brain: { program: performance.radio_program || null, metadata_only: true },
        hazama_fm: performance.hazama_fm_genre ? { genre: performance.hazama_fm_genre, integration_mode: "metadata-only" } : null
      },
      routing: {
        namima: {
          enabled: namima.enabled !== false,
          mood_intent: {
            mood: String(namima.intent || "").toLowerCase().includes("garden") ? "garden_haze" : "calm_water",
            review_only: true
          },
          family_safe: true,
          review_reason: namima.intent || namima.next_action || "Music orchestra packetから作るsafe mood候補。",
          review_only: true
        },
        openclaw: {
          enabled: true,
          promotion_status: promotion.status || "draft",
          human_review_required: true,
          next_action: {
            destination: destinationFromTargetRepo(promotion.target_repo),
            label: promotion.target_repo || "OpenClaw",
            reason: promotion.reviewer_note || openclaw.intent || "",
            action: openclaw.next_action || promotion.rollback || "",
            metadata_only: true
          },
          review_only: true
        }
      },
      safety: {
        stores_audio: false,
        stores_samples: false,
        stores_lyrics: false,
        metadata_only: true,
        human_review_required: true
      }
    };
  }

  function micFollow(packet){
    const mic = object(object(packet?.performance_state).mic_follow);
    const confidence = unit(mic.confidence);
    return {
      enabled: mic.enabled === true && confidence > 0.08,
      gesture: String(mic.gesture || "silent").toLowerCase(),
      drive: unit(mic.drive),
      pulse: unit(mic.pulse),
      clap: unit(mic.clap),
      hum: unit(mic.hum),
      air: unit(mic.air),
      noisy: unit(mic.noisy),
      bpm_lock: clamp(Number(mic.bpm_lock) || 0, 0, 240),
      confidence
    };
  }

  function chooseMood(packet, namima, gradient, mic, context){
    const intent = moodIntent(namima.mood_intent);
    const mood = intent.mood;
    const ucm = object(packet?.ucm_state);
    const energy = percent(ucm.energy, 0) / 100;
    const voidness = percent(ucm.void, 0) / 100;
    const circle = percent(ucm.circle, 0) / 100;
    const observer = percent(ucm.observer, 0) / 100;
    const calm = circle * 0.3 + observer * 0.28 + voidness * 0.2 + unit(gradient.haze) * 0.22;
    const hazamaMood = hazamaMoodOverride(context, energy);

    if(namima.family_safe === false) return "family_room";
    if(mic?.enabled && mic.confidence > 0.16){
      if(mic.gesture === "breath" || mic.gesture === "hum" || mic.air > 0.32) return "garden_morning";
      if(mic.gesture === "silent" && mic.air > 0.42) return "soft_sleep";
      if(mic.gesture === "clap" || mic.gesture === "pulse") return "water_day";
      if(mic.gesture === "noisy") return "family_room";
    }
    if(hazamaMood) return hazamaMood;
    if(mood.includes("transparent") || voidness > 0.58) return energy < 0.28 ? "soft_sleep" : "transparent_evening";
    if(mood.includes("garden") || calm > 0.62) return "garden_morning";
    if((mood.includes("family") && !intent.tokens.includes("water_day")) || energy > 0.52) return "family_room";
    if(mood.includes("sleep")) return "soft_sleep";
    return "water_day";
  }

  function translateMusicSessionPacket(packet){
    packet = normalizeMusicPacket(packet);
    const routing = object(packet?.routing);
    const namima = object(routing.namima);
    const gradient = object(packet?.reference_gradient?.weights);
    const ucm = object(packet?.ucm_state);
    const mic = micFollow(packet);
    const context = sourceContext(packet);
    const micWater = mic.enabled ? Math.max(mic.pulse, mic.clap, mic.drive * 0.48) * mic.confidence : 0;
    const micAir = mic.enabled ? Math.max(mic.air, mic.hum * 0.72) * mic.confidence : 0;
    const moodId = chooseMood(packet, namima, gradient, mic, context);
    const brightness = unit(namima.brightness, unit(gradient.chrome, 0.42));
    const waterMotion = unit(namima.water_motion, clamp(percent(ucm.wave, 35) / 100 + micWater * 0.16 + micAir * 0.08, 0, 1));
    const calmContinuity = unit((percent(ucm.circle, 0) + percent(ucm.observer, 0)) / 200, 0.45);
    const energy = percent(ucm.energy, 0) / 100;
    const safeEnergyCap = unit(moodIntent(namima.mood_intent).safeEnergyCap, 0.54);

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
        brightness: Number(Math.min(brightness + micAir * 0.06 - mic.noisy * 0.08, 0.78).toFixed(3)),
        calm_continuity: Number(Math.min(calmContinuity + micAir * 0.08, 0.92).toFixed(3)),
        energy_cap: Number(Math.min(safeEnergyCap - mic.noisy * 0.08, 0.62).toFixed(3)),
        foreground_energy: Number(Math.min(energy + micWater * 0.06, 0.52).toFixed(3)),
        mic_follow: {
          enabled: mic.enabled,
          gesture: mic.gesture,
          drive: Number(mic.drive.toFixed(3)),
          confidence: Number(mic.confidence.toFixed(3)),
          bpm_lock: Math.round(mic.bpm_lock)
        }
      },
      source_context: context,
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
