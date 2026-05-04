// sketch.js
let particles = [];
let sources = [];
let orbitBodies = [];
let started = false;
let visualMode = "water";
let activeMood = "water_day";
let autoOn = false;
let autoIndex = 0;
let nextAutoAt = 0;
let moodProfiles = {};
let musicPacketPanelReady = false;

const AUTO_ROUTE = ["water_day", "garden_morning", "family_room", "transparent_evening"];
const MOOD_VISUAL = {
  water_day: { hueShift: 0, brightness: 1.0, response: 1.0, trailDelta: 0 },
  garden_morning: { hueShift: -24, brightness: 0.88, response: 0.82, trailDelta: 2 },
  family_room: { hueShift: 12, brightness: 0.72, response: 0.62, trailDelta: 5 },
  soft_sleep: { hueShift: -10, brightness: 0.46, response: 0.36, trailDelta: 9 },
  transparent_evening: { hueShift: 18, brightness: 0.82, response: 0.74, trailDelta: 3 },
};

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
  orbitTrailAlpha: 14,
  orbitCountMobile: 6,
  orbitCountDesktop: 8,
  orbitLineDistance: 310,
  orbitDamping: 0.982,
  orbitMaxSpeed: 1.15,
  autoMinMs: 180000,
  autoMaxMs: 480000,
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
  initOrbitBodies();

  const overlay = document.getElementById("startOverlay");
  overlay.addEventListener("pointerdown", async (e) => {
    e.preventDefault();
    // iOS対策：ここで確実にユーザー操作として音を開始
    await startAudio();
    overlay.style.display = "none";
    started = true;
    syncAudioMood();

    addSource(width*0.5, height*0.5, 0.55);
  }, {passive:false});

  const modeToggle = document.getElementById("modeToggle");
  if(modeToggle){
    modeToggle.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      cycleVisualMode();
    }, {passive:false});
    setVisualMode(visualMode);
  }

  const autoToggle = document.getElementById("autoToggle");
  if(autoToggle){
    autoToggle.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      setAuto(!autoOn);
    }, {passive:false});
  }

  const moodSelect = document.getElementById("moodSelect");
  if(moodSelect){
    moodSelect.addEventListener("change", (e) => {
      setMood(e.target.value, { manual: true });
    });
  }

  setupMusicPacketPanel();
  updateControlUi();
  loadMoodProfiles();
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
  initOrbitBodies();
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

function initOrbitBodies(){
  const n = isMobile() ? SETTINGS.orbitCountMobile : SETTINGS.orbitCountDesktop;
  const cx = width * 0.5;
  const cy = height * 0.5;
  const radiusBase = Math.max(70, Math.min(width, height) * 0.22);

  orbitBodies = [];
  for(let i=0;i<n;i++){
    const angle = (TWO_PI * i / n) + random(-0.24, 0.24);
    const radius = radiusBase * random(0.65, 1.28);
    orbitBodies.push({
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius,
      vx: random(-0.16, 0.16),
      vy: random(-0.16, 0.16),
      hue: random(188, 245),
      size: random(4.5, 8.5),
      phase: random(TWO_PI),
    });
  }
}

function setVisualMode(mode){
  visualMode = mode;
  const modeToggle = document.getElementById("modeToggle");
  if(modeToggle){
    modeToggle.textContent = visualMode === "orbit" ? "Visual: Orbit" : "Visual: Water";
    modeToggle.setAttribute("aria-label", `Switch visual mode, current mode ${modeToggle.textContent}`);
  }
}

function cycleVisualMode(){
  setVisualMode(visualMode === "water" ? "orbit" : "water");
}

function moodVisual(){
  return MOOD_VISUAL[activeMood] ?? MOOD_VISUAL.water_day;
}

function updateControlUi(){
  const autoToggle = document.getElementById("autoToggle");
  if(autoToggle) autoToggle.textContent = autoOn ? "Auto: On" : "Auto: Off";

  const moodSelect = document.getElementById("moodSelect");
  if(moodSelect) moodSelect.value = activeMood;
}

function setPacketStatus(message, type){
  const status = document.getElementById("packetStatus");
  if(!status) return;
  status.textContent = message;
  status.classList.toggle("is-ok", type === "ok");
  status.classList.toggle("is-error", type === "error");
}

function renderPacketTranslation(translation){
  const output = document.getElementById("packetOutput");
  if(!output) return;
  output.textContent = JSON.stringify({
    source_session_id: translation.source_session_id,
    mood_id: translation.mood_id,
    intent: translation.intent,
    visual_hint: translation.visual_hint,
    safety: translation.safety
  }, null, 2);
}

function readMusicPacketFromPanel(){
  const input = document.getElementById("packetInput");
  const raw = input?.value.trim() || "";
  if(!raw){
    setPacketStatus("Music JSONを貼ってください。", "error");
    return null;
  }
  try {
    const packet = JSON.parse(raw);
    const translation = applyMusicSessionPacket(packet, { previewOnly: true });
    if(!translation) throw new Error("Music session adapter is not ready");
    renderPacketTranslation(translation);
    setPacketStatus(`OK: ${translation.source_session_id || "Music packet"} を ${translation.mood_id} へ翻訳しました。`, "ok");
    return { packet, translation };
  } catch (error) {
    const output = document.getElementById("packetOutput");
    if(output) output.textContent = "読めませんでした。JSON形式を確認してください。";
    setPacketStatus(`JSONを読めません: ${error.message}`, "error");
    return null;
  }
}

function applyMusicPacketFromPanel(){
  const read = readMusicPacketFromPanel();
  if(!read?.packet) return;
  const translation = applyMusicSessionPacket(read.packet, { previewOnly: false });
  if(!translation) return;
  renderPacketTranslation(translation);
  setPacketStatus(`moodへ反映しました: ${translation.mood_id}。STARTは人間が押すまで音を開始しません。`, "ok");
}

function clearMusicPacketPanel(){
  const input = document.getElementById("packetInput");
  const output = document.getElementById("packetOutput");
  if(input) input.value = "";
  if(output) output.textContent = "まだ読んでいません。";
  if(window.NamimaMusicSessionAdapter) window.NamimaMusicSessionAdapter.last = null;
  setPacketStatus("Music JSONを貼ると、safe mood翻訳がここに出ます。");
}

function setupMusicPacketPanel(){
  if(musicPacketPanelReady) return;
  const panel = document.getElementById("packetPanel");
  const toggle = document.getElementById("packetToggle");
  const close = document.getElementById("packetClose");
  const read = document.getElementById("packetRead");
  const apply = document.getElementById("packetApply");
  const clear = document.getElementById("packetClear");
  if(!panel || !toggle) return;
  musicPacketPanelReady = true;
  let lastPointerAt = 0;
  const guardedPointer = (callback) => (e) => {
    lastPointerAt = Date.now();
    e.preventDefault();
    e.stopPropagation();
    callback();
  };
  const guardedClick = (callback) => (e) => {
    if(Date.now() - lastPointerAt < 360) return;
    e.preventDefault();
    e.stopPropagation();
    callback();
  };
  if(toggle && panel){
    const togglePanel = () => panel.classList.toggle("is-open");
    toggle.addEventListener("pointerdown", guardedPointer(togglePanel), { passive:false });
    toggle.addEventListener("click", guardedClick(togglePanel));
  }
  if(close && panel){
    const closePanel = () => panel.classList.remove("is-open");
    close.addEventListener("pointerdown", guardedPointer(closePanel), { passive:false });
    close.addEventListener("click", guardedClick(closePanel));
  }
  if(read){
    read.addEventListener("pointerdown", guardedPointer(readMusicPacketFromPanel), { passive:false });
    read.addEventListener("click", guardedClick(readMusicPacketFromPanel));
  }
  if(apply){
    apply.addEventListener("pointerdown", guardedPointer(applyMusicPacketFromPanel), { passive:false });
    apply.addEventListener("click", guardedClick(applyMusicPacketFromPanel));
  }
  if(clear){
    clear.addEventListener("pointerdown", guardedPointer(clearMusicPacketPanel), { passive:false });
    clear.addEventListener("click", guardedClick(clearMusicPacketPanel));
  }
}

function syncAudioMood(){
  if(!window.AudioEngine) return;
  if(window.AudioEngine.setMood) window.AudioEngine.setMood(activeMood);
  if(window.AudioEngine.setMoodProfile) window.AudioEngine.setMoodProfile(moodProfiles[activeMood]);
  if(window.AudioEngine.setAuto) window.AudioEngine.setAuto(autoOn);
}

async function loadMoodProfiles(){
  try {
    const response = await fetch("./profiles/mood-profiles.json", { cache: "no-store" });
    if(!response.ok) return;
    const data = await response.json();
    const profiles = Array.isArray(data?.profiles) ? data.profiles : [];
    moodProfiles = {};
    for(const profile of profiles){
      if(profile?.id) moodProfiles[profile.id] = profile;
    }
    syncAudioMood();
  } catch (_error) {
    moodProfiles = {};
  }
}

function scheduleNextAuto(nowMs){
  nextAutoAt = nowMs + random(SETTINGS.autoMinMs, SETTINGS.autoMaxMs);
}

function setMood(mood, options={}){
  if(!MOOD_VISUAL[mood]) return;
  activeMood = mood;
  if(options.manual){
    const routeIndex = AUTO_ROUTE.indexOf(activeMood);
    if(routeIndex >= 0) autoIndex = routeIndex;
  }
  syncAudioMood();
  updateControlUi();
}

function setAuto(enabled){
  autoOn = Boolean(enabled);
  if(autoOn && nextAutoAt <= millis()) scheduleNextAuto(millis());
  syncAudioMood();
  updateControlUi();
}

function namimaSnapshot(){
  return {
    active_mood: activeMood,
    auto_enabled: autoOn,
    visual_mode: visualMode,
    started,
    mood_profiles_loaded: Object.keys(moodProfiles).length,
    last_music_session: window.NamimaMusicSessionAdapter?.last ?? null
  };
}

function applyMusicSessionPacket(packet, options={}){
  const adapter = window.NamimaMusicSessionAdapter;
  if(!adapter || typeof adapter.translateMusicSessionPacket !== "function") return null;
  const translation = adapter.translateMusicSessionPacket(packet);
  adapter.last = translation;
  if(translation.enabled && options.previewOnly !== true){
    setMood(translation.mood_id, { manual: true });
    if(translation.visual_hint?.mode) setVisualMode(translation.visual_hint.mode);
  }
  return translation;
}

window.namimaAdapter = {
  snapshot: namimaSnapshot,
  applyMusicSessionPacket,
  translateMusicSessionPacket: (packet) => window.NamimaMusicSessionAdapter?.translateMusicSessionPacket(packet) ?? null
};

if(document.readyState === "loading"){
  document.addEventListener("DOMContentLoaded", setupMusicPacketPanel, { once: true });
} else {
  setupMusicPacketPanel();
}

function advanceAutoMood(nowMs){
  if(!autoOn) return;
  if(nextAutoAt <= 0) scheduleNextAuto(nowMs);
  if(nowMs < nextAutoAt) return;

  autoIndex = (autoIndex + 1) % AUTO_ROUTE.length;
  setMood(AUTO_ROUTE[autoIndex]);
  scheduleNextAuto(nowMs);
}

function addSource(x,y, strength=0.7){
  sources.push({ x, y, t0: millis()/1000, strength });
  if(sources.length > SETTINGS.maxSources) sources.shift();
}

function handleTap(x, y){
  if(!started) return;
  const s = 0.55 + 0.45 * random();
  addSource(x, y, s);
  if(visualMode === "orbit") nudgeOrbit(x, y, s);

  // ★ここが鳴らす本体
  if(window.AudioEngine) window.AudioEngine.onTap(x / width, s);
}

function nudgeOrbit(x, y, strength){
  if(!orbitBodies.length) return;

  let nearest = orbitBodies[0];
  let best = Infinity;
  for(const body of orbitBodies){
    const dx = body.x - x;
    const dy = body.y - y;
    const d2 = dx*dx + dy*dy;
    if(d2 < best){
      best = d2;
      nearest = body;
    }
  }

  const d = Math.sqrt(best) + 1e-6;
  const influence = Math.max(0.18, 1 - Math.min(d, 260) / 260);
  nearest.vx += ((nearest.x - x) / d) * strength * influence * 1.2 + random(-0.12, 0.12);
  nearest.vy += ((nearest.y - y) / d) * strength * influence * 1.2 + random(-0.12, 0.12);
}

// PCクリック
function mousePressed(event){
  if(event?.target?.id === "modeToggle") return;
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
  const mood = moodVisual();
  const trailAlpha = (visualMode === "orbit" ? SETTINGS.orbitTrailAlpha : SETTINGS.trailAlpha) + mood.trailDelta;
  fill(5, 6, 10, trailAlpha);
  rect(0,0,width,height);

  const tNow = millis()/1000;
  advanceAutoMood(millis());

  // prune
  sources = sources.filter(s => (tNow - s.t0) < 7.2);

  // energy → audio
  let energy = 0;
  for(const s of sources){
    const dt = tNow - s.t0;
    if(dt < 0) continue;
    energy += s.strength * Math.exp(-dt / SETTINGS.timeDecay) * mood.response;
  }
  energy = Math.min(1, energy / 2.0);
  if(window.AudioEngine) window.AudioEngine.updateEnergy(energy);

  if(visualMode === "orbit"){
    drawOrbitMode(tNow, energy);
  } else {
    drawWaterMode(tNow, energy);
  }
}

function drawWaterMode(tNow, energy){
  const mood = moodVisual();
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
    const b = (18 + 140 * ridge + 40 * energy) * mood.brightness;
    const a = 40 + 140 * ridge * p.glow;
    const lx = p.vx * SETTINGS.lineScale * (0.6 + ridge);
    const ly = p.vy * SETTINGS.lineScale * (0.6 + ridge);

    stroke(p.hue + mood.hueShift + ridge * 18, 170, b, a);
    strokeWeight(p.w);
    line(px, py, px - lx, py - ly);

    if(ridge > 0.35){
      blendMode(ADD);
      stroke(p.hue + mood.hueShift + ridge * 20, 200, 180 * mood.brightness, 35 + 80 * ridge);
      strokeWeight(p.w * 1.8);
      line(px, py, px - lx * 0.9, py - ly * 0.9);
      blendMode(BLEND);
    }
  }
}

function drawOrbitMode(tNow, energy){
  if(!orbitBodies.length) initOrbitBodies();

  const mood = moodVisual();
  colorMode(HSB, 360, 255, 255, 255);
  blendMode(BLEND);

  const cx = width * 0.5;
  const cy = height * 0.5;
  const lineDistance = Math.min(SETTINGS.orbitLineDistance, Math.max(170, Math.min(width, height) * 0.56));

  for(const body of orbitBodies){
    let ax = (cx - body.x) * 0.00011;
    let ay = (cy - body.y) * 0.00011;

    ax += Math.cos(tNow * 0.28 + body.phase) * 0.0045;
    ay += Math.sin(tNow * 0.24 + body.phase) * 0.0045;

    for(const other of orbitBodies){
      if(other === body) continue;
      const dx = other.x - body.x;
      const dy = other.y - body.y;
      const d = Math.sqrt(dx*dx + dy*dy) + 1e-6;
      const preferred = lineDistance * 0.42;
      const pull = constrain((d - preferred) * 0.000014, -0.006, 0.006);
      ax += (dx / d) * pull;
      ay += (dy / d) * pull;

      if(d < 58){
        ax -= (dx / d) * 0.006;
        ay -= (dy / d) * 0.006;
      }
    }

    for(const src of sources){
      const dx = body.x - src.x;
      const dy = body.y - src.y;
      const d = Math.sqrt(dx*dx + dy*dy) + 1e-6;
      const dt = tNow - src.t0;
      const lift = src.strength * Math.exp(-dt / 1.8) * Math.max(0, 1 - Math.min(d, 280) / 280);
      ax += (dx / d) * lift * 0.012;
      ay += (dy / d) * lift * 0.012;
    }

    body.vx = (body.vx + ax) * SETTINGS.orbitDamping;
    body.vy = (body.vy + ay) * SETTINGS.orbitDamping;

    const maxSpeed = SETTINGS.orbitMaxSpeed + energy * 0.45 * mood.response;
    const speed = Math.sqrt(body.vx*body.vx + body.vy*body.vy);
    if(speed > maxSpeed){
      body.vx = body.vx / speed * maxSpeed;
      body.vy = body.vy / speed * maxSpeed;
    }

    body.x += body.vx;
    body.y += body.vy;

    const margin = 36;
    if(body.x < margin) body.vx += (margin - body.x) * 0.006;
    if(body.x > width - margin) body.vx -= (body.x - (width - margin)) * 0.006;
    if(body.y < margin) body.vy += (margin - body.y) * 0.006;
    if(body.y > height - margin) body.vy -= (body.y - (height - margin)) * 0.006;
  }

  blendMode(ADD);
  for(let i=0;i<orbitBodies.length;i++){
    for(let j=i+1;j<orbitBodies.length;j++){
      const a = orbitBodies[i];
      const b = orbitBodies[j];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const d = Math.sqrt(dx*dx + dy*dy);
      if(d > lineDistance) continue;

      const closeness = 1 - d / lineDistance;
      const pulse = 0.5 + 0.5 * Math.sin(tNow * 0.55 + a.phase + b.phase);
      stroke(202 + mood.hueShift + pulse * 24, 105, 210 * mood.brightness, (18 + 34 * energy) * closeness);
      strokeWeight(0.45 + closeness * 0.6);
      line(a.x, a.y, b.x, b.y);
    }
  }

  noFill();
  for(const src of sources){
    const dt = tNow - src.t0;
    const ring = 34 + dt * 74;
    const alpha = 42 * src.strength * Math.exp(-dt / 1.4);
    stroke(196 + mood.hueShift, 92, 220 * mood.brightness, alpha);
    strokeWeight(0.8);
    circle(src.x, src.y, ring);
  }

  for(const body of orbitBodies){
    const pulse = 0.5 + 0.5 * Math.sin(tNow * 0.72 + body.phase);
    const r = body.size * (1.15 + pulse * 0.22 + energy * 0.45);

    noFill();
    stroke(body.hue + mood.hueShift, 115, 230 * mood.brightness, 26 + 28 * energy);
    strokeWeight(0.75);
    circle(body.x, body.y, r * 6.2);

    stroke(body.hue + mood.hueShift + 8, 90, 210 * mood.brightness, 12 + 18 * energy);
    strokeWeight(0.55);
    circle(body.x, body.y, r * 11.5);

    noStroke();
    fill(body.hue + mood.hueShift, 90, 245 * mood.brightness, 62 + 45 * energy);
    circle(body.x, body.y, r * 1.75);
  }

  blendMode(BLEND);
}
