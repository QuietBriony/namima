import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync("audio.js", "utf8");
function fixture(randomValue=0.999){
  let now = 10, id = 0;
  const nodes = [], timers = new Map();
  const param = () => ({value:0, rampTo(){}, cancelScheduledValues(){}});
  class Node {
    constructor(first, options){
      this.options = options ?? first;
      this.notes = []; this.released = false; this.disposed = false;
      this.frequency = param(); this.gain = param(); this.feedback = param(); this.wet = param();
      nodes.push(this);
    }
    connect(){ return this; } toDestination(){ return this; }
    triggerAttackRelease(note, duration, time, velocity){ this.notes.push({note,duration,time,velocity}); }
    releaseAll(){ this.released = true; } dispose(){ this.disposed = true; }
  }
  const window = {location:{search:"?aiLight=1"}, navigator:{},
    setTimeout(fn, ms){timers.set(++id,{fn,at:now+ms/1000});return id;},
    clearTimeout(key){timers.delete(key);}};
  const Tone = {start:async()=>{}, now:()=>now, context:{state:"running"}, Transport:{stop(){}},
    Limiter:Node,Gain:Node,Filter:Node,FeedbackDelay:Node,PolySynth:Node,Synth:Node,PluckSynth:Node};
  const math = Object.create(Math); math.random = () => randomValue;
  class ClockDate extends Date { static now(){return now*1000;} }
  vm.runInNewContext(source,{window,Tone,URLSearchParams,console,Math:math,Date:ClockDate});
  const engine = window.AudioEngine;
  engine.setBloom(false);
  function advance(seconds){
    const end = now + seconds;
    while(true){
      const next = [...timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];
      if(!next) break;
      now = next[1].at; timers.delete(next[0]); next[1].fn();
    }
    now = end;
  }
  return {engine,nodes,timers,advance,droplet:()=>nodes.findLast(n=>n.options?.oscillator?.type==="triangle")};
}
const midi = note => {
  const [,name,octave] = /([A-G]b?)(\d)/.exec(note);
  return (Number(octave)+1)*12 + ({C:0,D:2,Eb:3,F:5,G:7,Ab:8,A:9,Bb:10}[name]);
};

const f = fixture();
assert.equal(f.engine.onTap(0.5),false,"A gesture cannot create notes before START");
assert.equal(f.timers.size,0);
await f.engine.start();
const voice = f.droplet();
assert.equal(voice.maxPolyphony,6,"Immediate touch voice has a bounded independent release pool");
const pitches = [];
for(let i=0;i<15;i++){
  f.advance(0.2);
  assert.equal(f.engine.onTap(i/14),true);
  pitches.push(midi(voice.notes.at(-1).note));
  assert.equal(f.engine.phrase.pending,2);
}
assert.equal(voice.notes.length,15,"Even when optional layers all miss, every deliberate touch sounds");
assert.ok(pitches.every((p,i)=>i===0||p>pitches[i-1]),"Left to right must rise without octave wrap");
assert.ok(pitches[0]>=48 && pitches.at(-1)<84,"Edges stay within C3 through B5");
assert.equal(f.engine.phrase.remembered,4,"Phrase memory is bounded to four derived notes");
assert.equal(f.engine.onTap(0.3),false,"Very fast duplicate events do not add voices or timers");
f.advance(0.5); assert.equal(voice.notes.length,15,"Answer leaves space after the touch");
f.advance(1); assert.equal(voice.notes.length,17,"Only the newest touch gets a two-note answer");
assert.equal(f.engine.phrase.pending,0);
assert.ok(voice.notes.at(-1).velocity < voice.notes.at(-2).velocity,"Answer recedes into the tail");

f.engine.setBloom(true); f.advance(10);
assert.equal(f.engine.phrase.role,"memory","Quiet-time ambient voice recalls the played motif");
f.advance(30);
assert.equal(f.engine.phrase.role,"drift","Played material fades out of memory after 24 seconds");
assert.equal(f.engine.phrase.remembered,0,"Expired phrase is discarded");
f.engine.setBloom(false);
f.engine.onTap(0.25);
const obsolete = [...f.timers.values()].map(t=>t.fn);
f.engine.setMood("soft_sleep");
assert.equal(f.engine.phrase.pending,0,"Mood change cancels answers from the previous mood");
assert.equal(f.engine.phrase.remembered,0);
f.advance(0.1);f.engine.onTap(0.6);
assert.equal(f.engine.phrase.pending,1,"Sleep mood has only one restrained answer");
f.engine.panic("background");
assert.equal(f.engine.phrase.pending,0);assert.equal(f.engine.phrase.remembered,0);
assert.equal(voice.released,true,"Background stop releases the touch voice with the other voices");
await f.engine.start();
const count = f.droplet().notes.length;
for(const complete of obsolete) complete();
assert.equal(f.droplet().notes.length,count,"Cancelled callbacks cannot play after a new START");
f.engine.panic("end");f.advance(1);
assert.ok(f.nodes.every(n=>n.disposed),"Both old and restarted graphs release their nodes");
assert.equal(f.timers.size,0,"No answer/bloom/disposal timers remain after stopping");

const busy = fixture(0);
await busy.engine.start();
const background = busy.nodes.filter(n=>n.maxPolyphony===8);
const before = background.map(n=>n.notes.length);
background.forEach(n=>n.activeVoices=8);
busy.engine.onTap(0.5);
assert.equal(busy.droplet().notes.length,1,"Touch stays audible while background voices are occupied");
assert.deepEqual(background.map(n=>n.notes.length),before,"Optional background layers wait for free voices");
busy.engine.panic("end");busy.advance(1);

const pace = fixture(); await pace.engine.start();
pace.engine.onTap(0.2);
for(let i=0;i<4;i++){pace.advance(0.2);pace.engine.onTap(0.3+i*0.1);}
const fastPace = pace.engine.phrase.rhythm_ms;
assert.ok(fastPace>=280 && fastPace<=400,"Rapid playing has a restrained short answer spacing");
for(let i=0;i<4;i++){pace.advance(0.9);pace.engine.onTap(0.7-i*0.1);}
assert.ok(pace.engine.phrase.rhythm_ms>fastPace && pace.engine.phrase.rhythm_ms<=900,"Answer pace follows slower playing within bounds");
const events=[];pace.engine.setBloomListener((x,note)=>events.push(note));
pace.engine.setBloom(true);pace.advance(18);
assert.ok(events.some(e=>e.kind==="memory"),"Quiet-time voice retains the original motif");
assert.ok(events.some(e=>e.kind==="variation"),"Remembered material gets a bounded musical turn and return");
assert.ok(pace.engine.phrase.pending<=2);
pace.engine.setMood("soft_sleep");events.length=0;
pace.advance(0.3);pace.engine.onTap(0.3);pace.advance(0.6);pace.engine.onTap(0.6);pace.advance(18);
assert.ok(!events.some(e=>e.kind==="variation"),"Sleep mood keeps sparse recall without extra variation");
pace.engine.panic("end");pace.advance(1);assert.equal(pace.timers.size,0);

const turn = fixture(); await turn.engine.start();
turn.engine.onTap(0.54);turn.advance(0.4);turn.engine.onTap(0.61);
const variations=[];turn.engine.setBloomListener((x,note)=>{if(note.kind==="variation")variations.push(x);});
turn.engine.setBloom(true);turn.advance(18);
assert.ok(variations.length>=2);
assert.notEqual(variations[0],variations[1],"A variation chooses another neighbor when its first turn would repeat home");
turn.engine.panic("end");turn.advance(1);
console.log("Namima water phrases: guaranteed touch, rising pitch, bounded echoes/memory, sleep restraint and lifecycle cancellation passed");
