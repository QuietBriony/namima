import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

function context(){
  const calls=[];
  return new Proxy({calls},{
    get(target,key){
      if(key in target)return target[key];
      if(String(key).startsWith("create"))return (...args)=>{calls.push([key,...args]);return {addColorStop(){}};};
      return (...args)=>calls.push([key,...args.map(value=>typeof value==="object" ? "canvas" : value)]);
    },
    set(target,key,value){target[key]=value;return true;}
  });
}
const sandbox={window:{}};vm.createContext(sandbox);
vm.runInContext(readFileSync(process.argv[2] || "scenery.js","utf8"),sandbox);
const lib=sandbox.window.NamimaScenery,canvases=[];
const makeCanvas=()=>{const ctx=context();const canvas={width:0,height:0,getContext:()=>ctx};canvases.push(canvas);return canvas;};
const renderer=lib.create(makeCanvas),target=context();
renderer.draw(target,"water_day",390,844,0);
const first=canvases.length;
for(let i=0;i<60;i++)renderer.draw(target,"water_day",390,844,i/30);
assert.equal(canvases.length,first,"Frames reuse a backdrop instead of generating gradients/canvases every frame");
renderer.draw(target,"garden_morning",390,844,3);
assert.equal(renderer.snapshot().buffers,2);
renderer.draw(target,"transparent_evening",390,844,3.3);
assert.equal(canvases.filter(c=>c.width>1).length,2,"Rapid scene switching releases the superseded backdrop");
renderer.draw(target,"transparent_evening",390,844,6);
assert.equal(canvases.filter(c=>c.width>1).length,1,"A completed transition releases the previous scene");
renderer.draw(target,"soft_sleep",390,844,7,{reducedMotion:true,opacity:.1});
assert.equal(renderer.snapshot().buffers,1,"Reduced motion completes a scene change immediately");
assert.equal(target.globalAlpha,1,"The reduced-motion replacement is opaque, with no fading old scene");
renderer.draw(target,"soft_sleep",4000,3000,8);
assert.equal(canvases.at(-1).width,1600,"Large displays cannot allocate unbounded backdrop textures");
assert.equal(canvases.filter(c=>c.width>1).length,1,"Resize releases old buffers");

const shapes=new Set();
for(const mood of ["water_day","garden_morning","family_room","transparent_evening","soft_sleep"]){
  const before=canvases.length,r=lib.create(makeCanvas);r.draw(target,mood,390,844,0);
  shapes.add(JSON.stringify(canvases[before].getContext().calls));
}
assert.equal(shapes.size,5,"All five scenes draw different geometry, beyond a palette change");

if(!process.argv.includes("--renderer-only")){
  let clock=0;const nodes=new Map();
  const ui=id=>{if(!nodes.has(id))nodes.set(id,{textContent:"",value:0,hidden:false,setAttribute(){}});return nodes.get(id);};
  const sb={window:{NamimaScenery:lib,AudioEngine:{setMood(){},setMoodProfile(){},setAuto(){},start(){throw Error("Scene controls cannot start audio");}}},
    document:{readyState:"loading",addEventListener(){},getElementById:ui,body:{setAttribute(){}}},console,
    millis:()=>clock,random:(a,b)=>(a+b)/2,windowWidth:390,navigator:{userAgent:"Desktop test"}};
  vm.createContext(sb);vm.runInContext(readFileSync("sketch.js","utf8"),sb);
  sb.setAuto(true);
  assert.equal(sb.namimaSnapshot().active_mood,"garden_morning","Enabling auto responds immediately");
  assert.equal(sb.namimaSnapshot().started,false,"Choosing a scene never unlocks playback");
  clock=34999;sb.advanceAutoMood(clock);assert.equal(sb.namimaSnapshot().active_mood,"garden_morning");
  clock=35000;sb.advanceAutoMood(clock);assert.equal(sb.namimaSnapshot().active_mood,"transparent_evening");
  sb.setMood("family_room",{manual:true});clock=69999;sb.advanceAutoMood(clock);
  assert.equal(sb.namimaSnapshot().active_mood,"family_room","Manual selection gets a fresh interval");
  clock=70000;sb.advanceAutoMood(clock);assert.equal(sb.namimaSnapshot().active_mood,"soft_sleep");
  sb.setAuto(false);clock=1000000;sb.advanceAutoMood(clock);assert.equal(sb.namimaSnapshot().active_mood,"soft_sleep","Auto off holds the selected scene");
  sb.cycleScene();assert.equal(sb.namimaSnapshot().active_mood,"water_day");
  assert.equal(sb.isMobile(),true,"Narrow desktop-browser viewports use the mobile particle budget too");
}
console.log("Namima scenery: 5 geometries, cached frames, bounded transitions, reduced motion, resize and direct/auto controls passed");
