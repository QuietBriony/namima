import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync("audio.js", "utf8");
function fixture(search = "") {
  const nodes = [];
  const reverbs = [];
  const param = () => ({ rampTo() {}, cancelScheduledValues() {} });
  class Node {
    constructor() {
      this.gain = param(); this.frequency = param(); this.wet = param(); this.feedback = param();
      this.disposed = false; this.notes = 0; nodes.push(this);
    }
    connect() { return this; }
    toDestination() { return this; }
    triggerAttackRelease() { this.notes++; }
    releaseAll() {}
    dispose() { this.disposed = true; }
  }
  class Reverb extends Node {
    constructor() {
      super();
      this.ready = new Promise((resolve, reject) => { this.finish = resolve; this.fail = reject; });
      reverbs.push(this);
    }
    generate() { throw new Error("Constructor generation must not be duplicated"); }
  }
  const Tone = { start: async () => {}, now: () => 10,
    context: { state:"running" }, Transport: { stop() {} },
    Reverb, Limiter:Node, Gain:Node, Filter:Node, FeedbackDelay:Node,
    PolySynth:Node, Synth:Node, PluckSynth:Node };
  const window = { location:{search}, navigator:{hardwareConcurrency:16,deviceMemory:16},
    setTimeout() { return 1; }, clearTimeout() {} };
  vm.runInNewContext(source, {window,Tone,URLSearchParams,console});
  return { engine:window.AudioEngine,nodes,reverbs };
}
async function flush() { await Promise.resolve(); await Promise.resolve(); }

const single = fixture();
const a = single.engine.start();
const b = single.engine.start();
assert.equal(a, b, "Rapid taps must share the same pending graph");
await flush();
assert.equal(single.reverbs.length, 1);
single.reverbs[0].finish();
assert.equal(await a, true);
assert.equal(single.engine.started, true);
assert.equal(single.engine.starting, false);
const count = single.nodes.length;
await single.engine.start();
assert.equal(single.nodes.length, count, "Repeated START must not allocate another graph");

const cancel = fixture();
const pending = cancel.engine.start();
await flush();
cancel.engine.panic("background during startup");
assert.ok(cancel.nodes.every(n => n.disposed), "Partial startup nodes must be freed");
const next = cancel.engine.start();
await flush();
cancel.reverbs[0].finish();
assert.equal(await pending, false, "Cancelled preparation must not start sound later");
assert.equal(cancel.engine.starting, true, "An old completion must not clear the newer start");
cancel.reverbs[1].finish();
assert.equal(await next, true);

const failure = fixture();
const failed = failure.engine.start();
await flush();
failure.reverbs[0].fail(new Error("render failed"));
await assert.rejects(failed, /render failed/);
assert.equal(failure.engine.starting, false);
assert.equal(failure.engine.started, false);
assert.ok(failure.nodes.every(n => n.disposed));

const light = fixture("?aiLight=1");
assert.equal(await light.engine.start(), true);
assert.equal(light.reverbs.length, 0, "Light startup must avoid convolution rendering");
assert.equal(light.nodes.filter(n => n.maxPolyphony === 8).length, 2);
console.log("Namima audio lifecycle passed: single start, cancellation, failure cleanup and light graph");
