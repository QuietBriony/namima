import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync("music-session-adapter.js", "utf8");
const context = { window: {} };
context.window.window = context.window;
vm.createContext(context);
vm.runInContext(source, context);

const adapter = context.window.NamimaMusicSessionAdapter;
assert.equal(typeof adapter?.translateMusicSessionPacket, "function", "adapter should expose translateMusicSessionPacket");

const basePacket = {
  version: 1,
  source_repo: "Music",
  session_id: "adapter-check",
  ucm_state: { energy: 28, wave: 38, circle: 72, observer: 68, void: 34 },
  reference_gradient: { weights: { haze: 0.4, chrome: 0.42 } },
  performance_state: { mic_follow: { enabled: false } },
  routing: {
    namima: {
      enabled: true,
      family_safe: true,
      water_motion: 0.38,
      brightness: 0.42,
      mood_intent: {
        mood: "calm_water",
        safe_energy_cap: 0.54,
        air: 0.42,
        review_only: true
      }
    }
  }
};

assert.equal(adapter.translateMusicSessionPacket(basePacket).mood_id, "water_day", "object mood_intent should keep calm_water on water_day");
assert.equal(adapter.translateMusicSessionPacket(basePacket).source_context.source_surface, "music_core", "base Music packet should identify music_core");

const legacyArrayPacket = structuredClone(basePacket);
legacyArrayPacket.routing.namima.mood_intent = ["water_day", "family_safe", "soft air"];
assert.equal(adapter.translateMusicSessionPacket(legacyArrayPacket).mood_id, "water_day", "legacy array mood_intent should prefer water_day over family_safe");

const familyPacket = structuredClone(basePacket);
familyPacket.routing.namima.mood_intent = ["family_safe", "soft air"];
familyPacket.ucm_state.energy = 62;
assert.equal(adapter.translateMusicSessionPacket(familyPacket).mood_id, "family_room", "family-safe high energy fallback should remain family_room");

const hazamaPianoPacket = structuredClone(basePacket);
hazamaPianoPacket.performance_state.hazama_fm = {
  active: true,
  genre: "piano",
  review_cue: {
    short_label: "piano foreground",
    target_repo: "chill",
    metadata_only: true
  },
  integration_mode: "metadata-only",
  review_only: true
};
assert.equal(adapter.translateMusicSessionPacket(hazamaPianoPacket).mood_id, "transparent_evening", "Hazama piano cue should become transparent evening air");
assert.equal(adapter.translateMusicSessionPacket(hazamaPianoPacket).source_context.source_surface, "hazama_fm", "Hazama packet should identify hazama_fm");

const bandRoomPacket = structuredClone(basePacket);
bandRoomPacket.mode = "band_room";
bandRoomPacket.routing.namima.enabled = false;
bandRoomPacket.performance_state.radio_brain = { program: "band-room", metadata_only: true };
assert.equal(adapter.translateMusicSessionPacket(bandRoomPacket).enabled, false, "Band Room drum handoff should stay disabled for namima");
assert.equal(adapter.translateMusicSessionPacket(bandRoomPacket).source_context.source_surface, "band_room", "Band Room packet should identify band_room");

console.log("Namima music session adapter check passed");
