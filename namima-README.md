# Namima

Namima is the Music Stack public-friendly ambient surface: water, garden air,
transparent evening, and soft sleep. It is not the old dark-chaos prototype and
it is not a light copy of Music.

Current behavior:

- Music / Hazama FM / Band Room `SYNC` is metadata-only.
- Hazama FM review cues are translated into safe ambient mood bias.
- Band Room drum handoffs stay disabled for Namima unless Music explicitly
  routes to `namima`.
- Audio never starts until the human taps `Tap to start`.
- PWA standalone mode keeps the same human-gated behavior and exposes a small
  URL share button plus Music Stack return links.

Development:

```powershell
python -m http.server
node scripts/check-music-session-adapter.mjs
node scripts/check-pwa-static.mjs
```

Main docs: [docs/README.md](docs/README.md)
