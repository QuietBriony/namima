// sketch.js
let particles = [];
let sources = [];
let started = false;

const SETTINGS = {
  particleCountMobile: 220,
  particleCountDesktop: 820,
  maxSources: 6,
  waveFreq: 0.055,
  timeFreq: 2.0,
  distDecay: 0.0024,
  timeDecay: 1.25,
  forceScale: 22,
  friction: 0.925,
  trailAlpha: 18,
  lineScale: 10,
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

  const overlay = document.getElementById("startOverlay");
  overlay.addEventListener("pointerdown", async (e) => {
    e.preventDefault();
    // iOS対策：ここで確実にユーザー操作として音を開始
    await startAudio();
    overlay.style.display = "none";
    started = true;

    addSource(width*0.5, height*0.5, 0.55);
  }, {passive:false});
}

async function startAudio(){
  if(!window.AudioEngine) {
    console.log("AudioEngine missing");
    return;
  }
  if(window.AudioEngine.started) return;
  await window.AudioEngine.start();
  console.log("Audio started");
}

function windowResized(){
  resizeCanvas(windowWidth, windowHeight);
}

function makeParticle(x,y){
  return {
    x, y,
    vx: random(-0.2,0.2),
    vy: random(-0.2,0.2),
    hue: random(190, 285),
    w: random(0.6, 1.8),
    glow: random(0.25, 0.85),
  };
}

function addSource(x,y, strength=0.7){
  sources.push({ x, y, t0: millis()/1000, strength });
  if(sources.length > SETTINGS.maxSources) sources.shift();
}

function handleTap(x, y){
  if(!started) return;
  const s = 0.55 + 0.45 * random();
  addSource(x, y, s);

  // ★ここが鳴らす本体
  if(window.AudioEngine) window.AudioEngine.onTap(x / width, s);
}

// PCクリック
function mousePressed(){
  handleTap(constrain(mouseX,0,width), constrain(mouseY,0,height));
}

// ★スマホタップ（これが重要）
function touchStarted(){
  if(!started) return false;
  const tx = touches?.[0]?.x ?? mouseX;
  const ty = touches?.[0]?.y ?? mouseY;
  handleTap(constrain(tx,0,width), constrain(ty,0,height));
  return false; // スクロール防止
}

// field + gradient
function fieldAndGrad(x, y, tNow){
  let v = 0, gx = 0, gy = 0;

  for(const src of sources){
    const dt = tNow - src.t0;
    if(dt < 0) continue;

    const dx = x - src.x;
    const dy = y - src.y;
    const d  = Math.sqrt(dx*dx + dy*dy) + 1e-6;

    const amp = src.strength
      * Math.exp(-d * SETTINGS.distDecay)
      * Math.exp(-dt / SETTINGS.timeDecay);

    const phase = (d * SETTINGS.waveFreq) - (dt * SETTINGS.timeFreq);

    const s = Math.sin(phase);
    const c = Math.cos(phase);
    v += amp * s;

    const k = amp * c * SETTINGS.waveFreq / d;
    gx += k * dx;
    gy += k * dy;
  }
  return { v, gx, gy };
}

function draw(){
  noStroke();
  fill(5, 6, 10, SETTINGS.trailAlpha);
  rect(0,0,width,height);

  const tNow = millis()/1000;

  // prune
  sources = sources.filter(s => (tNow - s.t0) < 7.2);

  // energy → audio
  let energy = 0;
  for(const s of sources){
    const dt = tNow - s.t0;
    if(dt < 0) continue;
    energy += s.strength * Math.exp(-dt / SETTINGS.timeDecay);
  }
  energy = Math.min(1, energy / 2.0);
  if(window.AudioEngine) window.AudioEngine.updateEnergy(energy);

  colorMode(HSB, 360, 255, 255, 255);
  blendMode(BLEND);

  for(const p of particles){
    const fg = fieldAndGrad(p.x, p.y, tNow);
    const fx = -fg.gy * SETTINGS.forceScale;
    const fy =  fg.gx * SETTINGS.forceScale;

    p.vx = (p.vx + fx * 0.016) * SETTINGS.friction;
    p.vy = (p.vy + fy * 0.016) * SETTINGS.friction;

    const px = p.x;
    const py = p.y;

    p.x += p.vx;
    p.y += p.vy;

    if(p.x < 0) p.x += width;
    if(p.x > width) p.x -= width;
    if(p.y < 0) p.y += height;
    if(p.y > height) p.y -= height;

    const ridge = Math.min(1, Math.abs(fg.v) * 1.8);
    const b = 18 + 140 * ridge + 40 * energy;
    const a = 40 + 140 * ridge * p.glow;
    const lx = p.vx * SETTINGS.lineScale * (0.6 + ridge);
    const ly = p.vy * SETTINGS.lineScale * (0.6 + ridge);

    stroke(p.hue + ridge * 18, 170, b, a);
    strokeWeight(p.w);
    line(px, py, px - lx, py - ly);

    if(ridge > 0.35){
      blendMode(ADD);
      stroke(p.hue + ridge * 20, 200, 180, 35 + 80 * ridge);
      strokeWeight(p.w * 1.8);
      line(px, py, px - lx * 0.9, py - ly * 0.9);
      blendMode(BLEND);
    }
  }
}
