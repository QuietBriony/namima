import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const calls = [];
const context = {
  window:{}, document:{readyState:"loading",addEventListener(){},getElementById(){return null;}}, console,
  width:390,height:844,RGB:"RGB",HSB:"HSB",millis:()=>1000,
  colorMode:(mode)=>calls.push(mode),noStroke(){},fill(){},rect(){},
  push(){},pop(){},noFill(){},stroke(){},strokeWeight(){},beginShape(){},vertex(){},endShape(){},
  ellipse(){},circle(){},
};
vm.createContext(context);
vm.runInContext(readFileSync("sketch.js","utf8"),context);
// A previous frame leaves p5 in HSB. The wash must explicitly restore RGB.
vm.runInContext("reducedMotion=true",context);
context.draw();
assert.equal(calls[0],"RGB");
assert.equal(calls.filter(mode=>mode==="HSB").length,2,"Reduced motion draws contours and touch responses without particle drift");
vm.runInContext("sources=[{x:100,y:300,t0:0,kind:'echo'}]",context);
let rings=0;context.ellipse=()=>rings++;
context.drawRippleOutlines(2);
assert.equal(rings,3,"A two-second musical tail remains visible");
context.drawRippleOutlines(5);
assert.equal(rings,3,"Old rings stop drawing rather than accumulating");
let lines=0;
const blends=[];
context.BLEND="BLEND";context.ADD="ADD";context.blendMode=mode=>blends.push(mode);context.line=()=>lines++;
context.fieldAndGrad=()=>({v:0,gx:0,gy:0});
vm.runInContext("particles=[{x:100,y:300,vx:0,vy:0,hue:180,w:1,glow:0.5}]",context);
context.drawWaterMode(1,.1);
assert.equal(lines,0,"Idle particles cannot leave dark dots over a bright scene");
blends.length=0;
context.fieldAndGrad=()=>({v:.2,gx:.1,gy:.1});
context.drawWaterMode(1,.1);
assert.ok(lines>0,"Touch waves still draw moving particles");
assert.deepEqual(blends,["ADD","BLEND"],"Particles add light to the scene, restore normal drawing, and switch blending only twice per frame");
console.log("Namima visuals: RGB frame wash, reduced motion, bounded and fading response rings passed");
