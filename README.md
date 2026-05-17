# Namima

Namima is the Music Stack public-friendly ambient surface. It turns Music /
Hazama FM / Band Room `SYNC` metadata into safe water, garden, transparent, or
soft sleep mood. It does not store audio, samples, lyrics, raw mic buffers, or
raw pointer streams.

Use it:

```powershell
python -m http.server
```

Then open `index.html`, press `Music SYNC` if you want to inspect a packet, and
tap the surface only when you want audio to start.

Checks:

```powershell
node scripts/check-mood-profiles.mjs
node scripts/check-music-session-adapter.mjs
node scripts/check-pwa-static.mjs
```

More detail: [docs/README.md](docs/README.md)
