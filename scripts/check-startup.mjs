import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source=readFileSync('startup.js','utf8');
function fixture(controlled=false){
  const handlers={},timers=new Map();let id=0;
  const button={disabled:true},reload={hidden:false},title={},sub={},note={},attrs={};
  const overlay={style:{display:'flex'},querySelector:s=>({'.start-title':title,'.start-sub':sub,'.start-sync-note':note}[s]),
    setAttribute:(k,v)=>attrs[k]=v,removeAttribute:k=>delete attrs[k],addEventListener:(k,f)=>handlers[k]=f};
  const window={setTimeout:(f,ms)=>{timers.set(++id,{f,ms});return id;},clearTimeout:id=>timers.delete(id),addEventListener:(k,f)=>handlers['window:'+k]=f};
  window.navigator={serviceWorker:{controller:controlled,addEventListener:(k,f)=>handlers['worker:'+k]=f}};
  let reloads=0;window.location={reload(){reloads++;}};
  const document={getElementById:id=>({startOverlay:overlay,startButton:button,startReload:reload}[id])};
  vm.runInNewContext(source,{window,document,console:{warn(){}}});
  const click=()=>handlers.click({target:{closest:()=>null},preventDefault(){},stopPropagation(){}});
  const fire=ms=>{for(const [id,t]of timers)if(t.ms===ms){timers.delete(id);t.f();}};
  return{window,handlers,timers,button,reload,title,sub,note,overlay,attrs,click,fire,reloads:()=>reloads};
}
const f=fixture();let starts=0,cancels=0,finish;
assert.equal(f.handlers.pointerdown,undefined,'Do not request audio on touch down');
await f.click();assert.equal(starts,0);assert.equal(f.button.disabled,true);
f.fire(20000);assert.equal(f.reload.hidden,false);assert.match(f.sub.textContent,/準備ができません/);
f.window.NamimaStartup.ready(()=>{starts++;return new Promise(r=>finish=r);},()=>cancels++);
assert.equal(starts,0,'Ready and metadata cannot auto-start');assert.equal(f.reload.hidden,true);
const pending=f.click();assert.equal(starts,1,'Start runs synchronously within the click');
assert.equal(f.attrs['aria-busy'],'true');await f.click();assert.equal(starts,1);
f.fire(10000);await pending;assert.equal(cancels,1);assert.equal(f.button.disabled,false);assert.equal(f.attrs['aria-busy'],undefined);
assert.match(f.note.textContent,/もう一度タップ/);
finish(true);await Promise.resolve();assert.equal(f.overlay.style.display,'flex','Late timeout completion must not hide retry UI');
const second=f.click();assert.equal(starts,2);f.window.NamimaStartup.reset('background');await second;
assert.equal(f.button.disabled,false);assert.equal(f.attrs['aria-busy'],undefined);
const third=f.click();finish(true);await third;assert.equal(f.overlay.style.display,'none');
f.window.NamimaStartup.reset();f.window.NamimaStartup.ready(()=>{throw Error('missing dependency');},()=>cancels++);
await f.click();assert.equal(f.overlay.style.display,'flex');assert.equal(f.button.disabled,false);assert.equal(cancels,2);
assert.equal(f.timers.size,0,'Completed/cancelled attempts leave no watchdog timers');

assert.equal(f.handlers['worker:controllerchange'],undefined,'First install must not reload');
const upgrade=fixture(true);
upgrade.handlers['worker:controllerchange']();assert.equal(upgrade.reloads(),1,'An idle old shell reloads after cache upgrade');
const playing=fixture(true);playing.window.AudioEngine={started:true};
playing.handlers['worker:controllerchange']();assert.equal(playing.reloads(),0,'Update must not interrupt playback');
const starting=fixture(true);starting.window.AudioEngine={starting:true};
starting.handlers['worker:controllerchange']();assert.equal(starting.reloads(),0,'Update must not interrupt a pending gesture');

// Execute the actual p5 touch hook: UI gestures must reach native click synthesis.
const sketch=readFileSync('sketch.js','utf8'),sb={window:{addEventListener(){}},document:{readyState:'loading',addEventListener(){}},console};
vm.createContext(sb);vm.runInContext(sketch,sb);
assert.equal(sb.touchStarted({target:{closest:()=>true}}),true);
assert.equal(sb.touchStarted({target:{closest:()=>false}}),false);
console.log('Namima startup: completed gesture, no autoplay, loading failure, timeout retry, duplicate taps and cancelled completion passed');
