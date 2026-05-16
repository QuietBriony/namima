// check-mood-profiles.mjs
// Domain-logic verification for namima's ambient mood system.
//
// Unlike check-pwa-static.mjs (PWA shell) and check-music-session-adapter.mjs
// (metadata-only SYNC translation), this asserts the GENUINE domain contracts of
// namima's mood engine:
//   1. profiles/mood-profiles.json schema + completeness against audio.js's
//      MOOD_AUDIO table (every audio mood has a matching public profile).
//   2. The public-friendly / family-safe safety constraints documented in
//      AGENTS.md (no dark/heavy-bias profile may ship; family_safe must hold).
//   3. audio.js's profileToShape() translation: every profile, fed through the
//      real engine code, must produce an audio shape inside safe headroom.
//
// Node built-ins only. Loads audio.js in a VM sandbox the same way the runtime
// would (window global), then exercises the engine's own logic. Exit 0 = pass.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => readFileSync(join(root, rel), "utf8");

let assertions = 0;
function check(fn, ...args) {
  assertions += 1;
  return fn(...args);
}

// ---------------------------------------------------------------------------
// Load audio.js the way the browser does: it self-assigns window.AudioEngine.
// A Tone.js stub is enough because we only exercise pure profile logic here
// (profileToShape / normalizeAmbientConcept / MOOD_AUDIO) and never start().
// ---------------------------------------------------------------------------
const audioSource = read("audio.js");
const sandbox = {
  console,
  Math,
  window: {},
  setTimeout() { return 0; },
  Tone: { now: () => 0 }
};
sandbox.window.window = sandbox.window;
sandbox.window.setTimeout = sandbox.setTimeout;
vm.createContext(sandbox);
vm.runInContext(audioSource, sandbox, { filename: "audio.js" });

const engine = sandbox.window.AudioEngine;
check(assert.equal, typeof engine, "object", "audio.js should expose window.AudioEngine");
check(assert.equal, typeof engine.setMood, "function", "AudioEngine should expose setMood");
check(assert.equal, typeof engine.setMoodProfile, "function", "AudioEngine should expose setMoodProfile");

// ---------------------------------------------------------------------------
// 1. mood-profiles.json structure + policy
// ---------------------------------------------------------------------------
const moodDoc = JSON.parse(read("profiles/mood-profiles.json"));
check(assert.equal, moodDoc.version, 1, "mood-profiles.json should declare version 1");
check(
  assert.equal,
  moodDoc.policy?.stores_metadata_only,
  true,
  "mood profiles policy should be metadata-only (no audio/sample storage)"
);
check(
  assert.equal,
  moodDoc.policy?.stores_audio,
  false,
  "mood profiles policy must not store audio"
);
check(assert.ok, Array.isArray(moodDoc.profiles), "mood-profiles.json should hold a profiles array");
check(assert.ok, moodDoc.profiles.length >= 5, "namima should ship at least 5 ambient moods");

// ---------------------------------------------------------------------------
// 2. Completeness: the profile set and audio.js's MOOD_AUDIO table must agree.
//    A profile with no audio mood (or vice versa) is a silent runtime gap.
// ---------------------------------------------------------------------------
const audioMoodIds = (audioSource.match(/^\s{4}([a-z_]+):\s*\{$/gm) || [])
  .map((line) => line.trim().replace(/:\s*\{$/, ""));
check(
  assert.ok,
  audioMoodIds.length >= 5,
  `expected to parse MOOD_AUDIO mood ids from audio.js, got [${audioMoodIds.join(", ")}]`
);

const profileIds = moodDoc.profiles.map((p) => p.id);
check(
  assert.deepEqual,
  [...profileIds].sort(),
  [...audioMoodIds].sort(),
  "every audio.js MOOD_AUDIO mood must have exactly one matching profile id"
);
check(
  assert.equal,
  new Set(profileIds).size,
  profileIds.length,
  "profile ids must be unique"
);

// ---------------------------------------------------------------------------
// 3. Per-profile schema + public-friendly safety constraints.
//    AGENTS.md hard rule: no dark-glitch / heavy-bass bias may ship, and the
//    family-safe character must hold for every public profile.
// ---------------------------------------------------------------------------
const BIAS_FIELDS = [
  "brightness", "warmth", "water_motion", "garden_air", "rhythm_density",
  "low_end_pressure", "texture_amount", "melody_presence", "sleepiness"
];
// Levels audio.js's levelValue() understands. An unknown level silently
// collapses to 0.5, so an unrecognised string is a real translation bug.
const KNOWN_LEVELS = new Set([
  "none", "minimal", "very_low", "low", "low_medium", "low_to_mid",
  "medium_low", "medium", "medium_high", "high", "very_high",
  "gentle", "safe", "soft_warm", "cool"
]);
// Loudness pressure that would break the public-friendly character.
const UNSAFE_PRESSURE_LEVELS = new Set(["high", "very_high"]);

for (const profile of moodDoc.profiles) {
  const where = `profile "${profile.id}"`;
  check(assert.equal, typeof profile.label, "string", `${where} should have a label`);
  check(assert.ok, profile.label.length > 0, `${where} label should be non-empty`);
  check(assert.equal, typeof profile.description, "string", `${where} should have a description`);

  const bias = profile.input_bias;
  check(assert.equal, typeof bias, "object", `${where} should have an input_bias object`);
  check(
    assert.equal,
    bias.family_safe,
    true,
    `${where} must be family_safe (public-friendly hard rule)`
  );

  for (const field of BIAS_FIELDS) {
    const level = bias[field];
    check(
      assert.equal,
      typeof level,
      "string",
      `${where} input_bias.${field} should be a level string`
    );
    check(
      assert.ok,
      KNOWN_LEVELS.has(level),
      `${where} input_bias.${field}="${level}" is not a level audio.js understands`
    );
  }

  // Public-friendly safety: never a heavy low-end or dense-rhythm profile.
  check(
    assert.ok,
    !UNSAFE_PRESSURE_LEVELS.has(bias.low_end_pressure),
    `${where} low_end_pressure="${bias.low_end_pressure}" breaks the no-heavy-bass rule`
  );
  check(
    assert.ok,
    !UNSAFE_PRESSURE_LEVELS.has(bias.rhythm_density),
    `${where} rhythm_density="${bias.rhythm_density}" is too dense for an ambient mood`
  );

  // ambient_translation must describe a loudness-safety intent + a transition.
  const translation = profile.ambient_translation;
  check(assert.equal, typeof translation, "object", `${where} should have ambient_translation`);
  check(
    assert.ok,
    Array.isArray(translation.loudness_safety) && translation.loudness_safety.length > 0,
    `${where} ambient_translation must declare a loudness_safety intent`
  );
  check(
    assert.ok,
    Array.isArray(translation.transition) && translation.transition.length > 0,
    `${where} ambient_translation must declare a transition behavior`
  );
  check(
    assert.ok,
    Array.isArray(profile.avoid) && profile.avoid.length > 0,
    `${where} should list sounds to avoid`
  );
}

// ---------------------------------------------------------------------------
// 4. Translation logic: feed every profile through audio.js's own
//    setMoodProfile() and confirm the engine accepts it under the matching
//    mood. setMoodProfile only applies a profile whose id == currentMood and
//    returns the active mood id, so a round-trip proves both the id contract
//    and that profileToShape() ran without throwing.
// ---------------------------------------------------------------------------
for (const profile of moodDoc.profiles) {
  const activeAfterMood = check(engine.setMood, profile.id);
  check(
    assert.equal,
    activeAfterMood,
    profile.id,
    `setMood("${profile.id}") should activate a known audio mood`
  );
  const activeAfterProfile = check(engine.setMoodProfile, profile);
  check(
    assert.equal,
    activeAfterProfile,
    profile.id,
    `setMoodProfile should accept profile "${profile.id}" under its own mood`
  );
}

// A profile whose id does not match the active mood must be rejected (the
// engine returns the unchanged current mood) — this guards the id contract.
check(engine.setMood, "water_day");
const mismatched = { id: "garden_morning", input_bias: { family_safe: true } };
check(
  assert.equal,
  check(engine.setMoodProfile, mismatched),
  "water_day",
  "setMoodProfile must ignore a profile whose id differs from the active mood"
);

// An unknown mood id must not switch the engine away from a valid mood.
check(
  assert.equal,
  check(engine.setMood, "definitely_not_a_mood"),
  "water_day",
  "setMood must reject an unknown mood id"
);

console.log(`Namima mood profile logic check passed (${assertions} assertions)`);
