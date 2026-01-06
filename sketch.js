// sketch.js

let particles = [];
let sources = [];
let started = false;

const SETTINGS = {
  particleCountMobile: 220,   // 260→220（さらに安全）
  particleCountDesktop: 900,
  maxSources: 5,
  waveFreq: 0.05,
  timeFreq: 2.2,
  distDecay: 0.0026,
  timeDecay: 1.1,
  forceScale: 18,
  friction: 0.93,
};

function isMobile() {
  return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
}

function setup() {
  createCanvas(windowWidth, windowHeight);
  pixelDensity(1);
  background(0);

  const n = isMobile() ? SETTINGS.particleCountMobile : SETTINGS.particleCountDesktop;
  particles = [];
  for (let i = 0; i < n; i++) particles.push(makeParticle(random(width), random(height)));

  const overlay = document.getElementById("startOverlay");
  overlay.addEventListener(
    "pointerdown",
    async () => {
      // 音開始（存在しなくても落ちない）
      if (window.AudioEngine?.start) await window.AudioEngine.start();

      overlay.style.display = "none";
      started = true;
      addSource(width * 0.5, height * 0.5, 0.55);
    },
    { passive: true }
  );
}

function windowResized() {
  resizeCanvas(windowWidth, windowHeight);
}

function makeParticle(x, y) {
  return {
    x, y,
    vx: random(-0.2, 0.2),
    vy: random(-0.2, 0.2),
    hue: random(170, 290),
    w: random(0.8, 2.0),
    glow: random(0.35, 0.85),
  };
}

function addSource(x, y, strength = 0.7) {
  sources.push({ x, y, t0: millis() / 1000, strength });
  if (sources.length > SETTINGS.maxSources) sources.shift();
}

function pointerToCanvas() {
  return {
    x: constrain(mouseX, 0, width),
    y: constrain(mouseY, 0, height),
  };
}

function mousePressed() {
  if (!started) return;

  const p = pointerToCanvas();
  const s = 0.55 + 0.45 * random();
  addSource(p.x, p.y, s);

  if (window.AudioEngine?.onTap) window.AudioEngine.onTap(p.x / width, s);
}

function touchStarted() {
  return false; // prevent scroll
}

function fieldAndGrad(x, y, tNow) {
  let v = 0, gx = 0, gy = 0;

  for (const src of sources) {
    const dt = tNow - src.t0;
    if (dt < 0) continue;

    const dx = x - src.x;
    const dy = y - src.y;
    const d = Math.sqrt(dx * dx + dy * dy) + 1e-6;

    const amp =
      src.strength *
      Math.exp(-d * SETTINGS.distDecay) *
      Math.exp(-dt / SETTINGS.timeDecay);

    const phase = d * SETTINGS.waveFreq - dt * SETTINGS.timeFreq;
    const s = Math.sin(phase);
    const c = Math.cos(phase);

    v += amp * s;

    const k = (amp * c * SETTINGS.waveFreq) / d;
    gx += k * dx;
    gy += k * dy;
  }

  return { v, gx, gy };
}

function draw() {
  // 1) trail は RGB のまま描く（HSBに引きずられないように）
  colorMode(RGB, 255, 255, 255, 255);
  noStroke();
  fill(5, 6, 10, 28);
  rect(0, 0, width, height);

  const tNow = millis() / 1000;

  // 2) audio energy
  let energy = 0;
  for (const s of sources) {
    const dt = tNow - s.t0;
    if (dt < 0) continue;
    energy += s.strength * Math.exp(-dt / SETTINGS.timeDecay);
  }
  energy = Math.min(1, energy / 2.2);
  if (window.AudioEngine?.updateEnergy) window.AudioEngine.updateEnergy(energy);

  // 3) particles
  colorMode(HSB, 360, 255, 255, 255);
  for (const p of particles) {
    const fg = fieldAndGrad(p.x, p.y, tNow);

    const fx = -fg.gy * SETTINGS.forceScale;
    const fy =  fg.gx * SETTINGS.forceScale;

    p.vx = (p.vx + fx * 0.016) * SETTINGS.friction;
    p.vy = (p.vy + fy * 0.016) * SETTINGS.friction;

    p.x += p.vx;
    p.y += p.vy;

    if (p.x < 0) p.x += width;
    if (p.x > width) p.x -= width;
    if (p.y < 0) p.y += height;
    if (p.y > height) p.y -= height;

    const b = 40 + 140 * Math.min(1, Math.abs(fg.v) * 1.6);
    fill(p.hue, 160, b, 170 * p.glow);
    circle(p.x, p.y, p.w + Math.abs(fg.v) * 2.0);
  }

  sources = sources.filter((s) => tNow - s.t0 < 6.5);
}