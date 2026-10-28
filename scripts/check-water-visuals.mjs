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
console.log("Namima visuals: RGB frame wash, reduced motion, bounded and fading response rings passed");
