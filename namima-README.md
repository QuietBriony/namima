# Namima

> A generative Web Audio engine that lives **between waves** –  
> warm like tape, deep like the sea, and chaotic like broken math.

`Namima` is a browser-based sound engine that aims to be the **music-side Hazama**:
a place where **analog warmth**, **dark space**, and **digital chaos** collide.

## Features (v0.5 – prototype)

- 🟤 **WARM layer** – tape-like drift, gentle tube saturation, subtle IR space
- 🔵 **SPACE layer** – dense pads, FDN-style reverb, slow-moving harmonies
- 🟣 **CHAOS layer** – granular-ish textures and broken step patterns
- ⚫ **BASS / RHYTHM core** – loose, human-ish groove instead of rigid grids
- 🎛 Simple UI: `Warm / Space / Chaos / Density` + transport

All audio runs **entirely in the browser** (Web Audio API),  
with no DAW or external plugins required.

## Roadmap

- [ ] v0.5 – first “all-in” prototype (warm + space + chaos)
- [ ] v0.6 – preset system & scene morphing
- [ ] v0.7 – exportable patterns (MIDI / JSON)
- [ ] v1.0 – performance-ready build for live sets

---

## Development

1. Clone this repo
2. Serve the repo root with `python -m http.server`
3. Open `index.html` in a modern browser (Chrome / Edge / Safari)
4. Tap **Tap to start** and touch the water surface

## PWA shell

- `index.html` is installable through `manifest.webmanifest`.
- `sw.js` caches only the local app shell, mood/profile metadata, docs, and icons under the `namima-pwa` cache prefix.
- p5.js and Tone.js stay as pinned CDN dependencies and are cached at runtime after an online load.
- Mobile lifecycle is guarded: screen lock, backgrounding, `pagehide`, and `freeze` release voices, quiet audio, and show the tap-to-restart overlay.
- Static PWA contract check: `node scripts/check-pwa-static.mjs`.

Namima is designed for **non-programmer track makers** first:
you play it like an instrument, not like a DAW.
