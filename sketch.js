// sketch.js

let particles = [];
let sources = []; // ripple sources
let started = false;

const SETTINGS = {
  particleCountMobile: 260,   // 650→260
  particleCountDesktop: 900,  // 1100→900
  maxSources: 5,              // 10→5
  waveFreq: 0.05,
  timeFreq: 2.2,
  distDecay: 0.0026,
  timeDecay: 1.1,
  forceScale: 18,             // 26→18
  friction: 0.93,
};

function isMobile(){
  return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
}

function setup(){
  createCanvas(windowWidth, windowHeight);
  pixelDensity(1);
  background(0);

  const n = isMobile() ? SETTINGS.particleCountMobile : SETTINGS.particleCountDesktop;
  particles = [];
  for(let i=0;i<n;i++){
    particles.push(makeParticle(random(width), random(height)));
  }

  // overlay click/tap
  const overlay = document.getElementById("startOverlay");
  overlay.addEventListener("pointerdown", async () => {
    await startAudio();
    overlay.style.display = "none";
    started = true;

    // create a first gentle source in center
    addSource(width*0.5, height*0.5, 0.55);
  }, {passive:true});
}

async function startAudio(){
  if(AudioEngine.started) return;
  await AudioEngine.start();
}

function windowResized(){
  resizeCanvas(windowWidth, windowHeight);
}

function makeParticle(x,y){
  return {
    x, y,
    vx: random(-0.2,0.2),
    vy: random(-0.2,0.2),
    hue: random(170, 290),
    w: random(0.8, 2.0),
    glow: random(0.35, 0.85),
  };
}

function addSource(x,y, strength=0.7){
  sources.push({
    x, y,
    t0: millis()/1000,
    strength
  });
  if(sources.length > SETTINGS.maxSources){
    sources.shift();
  }
}

function pointerToCanvas(){
  // p5 uses mouseX/mouseY for touches too, but let's clamp
  const x = constrain(mouseX, 0, width);
  const y = constrain(mouseY, 0, height);
  return {x,y};
}

function mousePressed(){
  if(!started) return;
  const p = pointerToCanvas();
  const s = 0.55 + 0.45 * random(); // vary
  addSource(p.x, p.y, s);
  AudioEngine.onTap(p.x / width, s);
}

function touchStarted(){
  // prevent scroll
  return false;
}

// field value at (x,y): sum of ripple contributions
function field(x,y, tNow){
  let v = 0;
  for(const src of sources){
    const dt = tNow - src.t0;
    if(dt < 0) continue;

    const dx = x - src.x;
    const dy = y - src.y;
    const d = Math.sqrt(dx*dx + dy*dy);

    // traveling wave: phase depends on distance and time
    const phase = (d * SETTINGS.waveFreq) - (dt * SETTINGS.timeFreq);

    // amplitude decay
    const amp = src.strength
      * Math.exp(-d * SETTINGS.distDecay)
      * Math.exp(-dt / SETTINGS.timeDecay);

    // smooth wave
    v += amp * Math.sin(phase);
  }
  return v;
}

// approximate gradient of field (for particle force direction)
function fieldGrad(x,y,tNow){
  const e = SETTINGS.sampleEps;
  const fx1 = field(x+e, y, tNow);
  const fx0 = field(x-e, y, tNow);
  const fy1 = field(x, y+e, tNow);
  const fy0 = field(x, y-e, tNow);
  return { gx: (fx1-fx0)/(2*e), gy: (fy1-fy0)/(2*e) };
}

function draw(){
  // subtle trail
  noStroke();
  fill(5, 6, 10, 28);
  rect(0,0,width,height);

  const tNow = millis()/1000;

  // compute global energy for audio (cheap)
  let energy = 0;
  for(const s of sources){
    const dt = tNow - s.t0;
    if(dt < 0) continue;
    energy += s.strength * Math.exp(-dt / SETTINGS.timeDecay);
  }
  energy = Math.min(1, energy / 2.2);
  AudioEngine.updateEnergy(energy);

  // draw particles
  for(const p of particles){
    // force from field gradient
    const g = fieldGrad(p.x, p.y, tNow);
    // rotate gradient slightly for swirl feel
    const fx = -g.gy * SETTINGS.forceScale;
    const fy =  g.gx * SETTINGS.forceScale;

    // apply + tiny drift
    p.vx = (p.vx + fx * 0.016) * SETTINGS.friction;
    p.vy = (p.vy + fy * 0.016) * SETTINGS.friction;

    p.x += p.vx;
    p.y += p.vy;

    // wrap
    if(p.x < 0) p.x += width;
    if(p.x > width) p.x -= width;
    if(p.y < 0) p.y += height;
    if(p.y > height) p.y -= height;

    // brightness from field magnitude
    const fv = field(p.x, p.y, tNow);
    const b = 40 + 140 * Math.min(1, Math.abs(fv) * 1.6);

    // draw
    colorMode(HSB, 360, 255, 255, 255);
    fill(p.hue, 160, b, 170 * p.glow);
    circle(p.x, p.y, p.w + Math.abs(fv)*2.4);
  }

  // prune old sources (so it doesn't bloat)
  sources = sources.filter(s => (tNow - s.t0) < 6.5);
}