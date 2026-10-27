import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

let time=0; const played=[], handlers={}, captures=new Set();
const canvas={style:{},addEventListener:(name,fn)=>handlers[name]=fn,
  getBoundingClientRect:()=>({left:10,top:20,width:300,height:600}),
  setPointerCapture:id=>captures.add(id),hasPointerCapture:id=>captures.has(id),releasePointerCapture:id=>captures.delete(id)};
const sb={window:{addEventListener(){},AudioEngine:{onTap:(x,s,c)=>{played.push({x,s,c});return true;}}},
  document:{readyState:"loading",addEventListener(){}}, console,
  width:300,height:600, millis:()=>time,random:()=>0.5,
  constrain:(v,min,max)=>Math.max(min,Math.min(max,v))};
vm.createContext(sb);vm.runInContext(readFileSync("sketch.js","utf8"),sb);
sb.setupCanvasGestures(canvas);
const event=(x=20,id=1,extra={})=>({clientX:x,clientY:300,pointerId:id,pointerType:"touch",preventDefault(){},...extra});
handlers.pointerdown(event());assert.equal(played.length,0,"Canvas cannot unlock audio before START");
vm.runInContext("started=true",sb);time=1000;
handlers.pointerdown(event());assert.equal(played.length,1);assert.equal(captures.has(1),true);
handlers.pointerdown(event(100,2));handlers.pointermove(event(200,2));assert.equal(played.length,1,"A secondary finger cannot hijack the phrase");
time+=200;handlers.pointermove(event(21));assert.equal(played.length,1,"Holding one pitch leaves space");
handlers.pointermove(event(100));assert.equal(played.length,2);assert.ok(played[1].x>played[0].x);
time+=30;handlers.pointermove(event(210));assert.equal(played.length,2,"Dense pointer streams do not flood voices");
time+=200;handlers.pointermove(event(250));assert.equal(played.length,3);
handlers.pointerup(event(250));assert.equal(captures.size,0);
time+=200;handlers.pointermove(event(280));assert.equal(played.length,3,"Releasing the finger ends the stroke");
handlers.pointerdown(event(150));assert.equal(played.length,4);
handlers.pointercancel(event(150));assert.equal(captures.size,0);
handlers.pointerdown(event(150));sb.endWaterGesture();assert.equal(captures.size,0,"Lifecycle cancellation releases capture");
const count=played.length;handlers.pointerdown(event(150,3,{pointerType:"mouse",button:2}));assert.equal(played.length,count,"Secondary mouse buttons are not musical touches");
assert.equal(sb.touchStarted({target:{closest:()=>true}}),true,"Native startup/control clicks remain available");
console.log("Namima water gestures: manual start, pitch steps, density bound, one pointer, release/cancel and native UI passed");
