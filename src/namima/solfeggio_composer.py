"""Solfeggio ambient composer (candidate) — deep beat + drifting non-12-TET melody.

A second offline candidate alongside ``generator.py`` (the drone renderer). Where
the generator makes a single sustained tone, this composes a ~3-minute ambient
*piece*: a deep beat, a warm detuned pad/sub bed that drifts across harmonic
scenes, a floating ("たゆたう") melody, an optional formant-synth wordless voice,
and 888 Hz bell / 8888 Hz sparkle accents.

LOCKED AESTHETIC (by user direction):
  * deep beat + drifting melody; ambient; Alberto-Balsalm mood only.
  * NO portamento/glide lead — the melody is soft, STABLE-pitch swells that
    cross-fade (a rejected earlier version used a sirening glide lead).
  * pitches are the SOLFEGGIO FREQUENCIES AS ABSOLUTE Hz (from presets.yaml),
    NOT snapped to 12-TET — the 89-cent 396↔417 microtonal step is intentional.
  * 888 Hz allowed as an inharmonic bell; 8888 Hz only as sparse quiet "air".

DESIGN CONSTRAINTS (namima rules + audition target):
  * self-synthesised only — no samples; generated WAVs are gitignored.
  * numpy + scipy only (this candidate DOES import scipy.signal, unlike the
    generator — see requirements.txt); deterministic for a fixed ``seed``.
  * 48 kHz / 24-bit WAV via the shared ``generator.write_wav24``.
  * MONO-COMPATIBLE: the user auditions on an iPhone built-in (mono) speaker, so
    the mono-sum must not comb/cancel and "depth" is carried by audible mid-body
    (~120-500 Hz), not sub-bass (inaudible on that speaker).

Not wired into the namima runtime (sketch.js / audio.js). Candidate only.

    python -m namima.solfeggio_composer --out drift.wav          # full ~3 min
    python -m namima.solfeggio_composer --out s.wav --bars 16     # fast smoke
    python -m namima.solfeggio_composer --out s.wav --no-voice --seed 7
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.signal import butter, lfilter, fftconvolve

from .generator import write_wav24, load_presets, preset_frequency

__version__ = "0.1.0-candidate"
TAU = 2.0 * np.pi


# =============================================================================
# Config
# =============================================================================
@dataclass
class ComposeConfig:
    bars: int = 72
    bpm: float = 96.0
    seed: int = 528639
    sample_rate: int = 48000
    gain: float = 0.86               # peak-normalisation target (headroom)
    use_bells: bool = True           # 888 Hz bell accents
    use_voice: bool = True           # formant-synth wordless hum

    @property
    def beat(self) -> float:
        return 60.0 / self.bpm

    @property
    def bar(self) -> float:
        return 4.0 * self.beat

    @property
    def step(self) -> float:         # one 16th note
        return self.beat / 4.0

    def as_meta(self) -> dict:
        return {
            "version": __version__,
            "kind": "solfeggio_composer",
            "bpm": self.bpm,
            "bars": self.bars,
            "seed": self.seed,
            "sample_rate": self.sample_rate,
            "bit_depth": 24,
            "channels": 2,
            "gain": self.gain,
            "use_bells": self.use_bells,
            "use_voice": self.use_voice,
            "pitch_system": "absolute-solfeggio-Hz (non-12-TET; presets.yaml)",
        }


# wordless-vowel formants (Hz), bandwidths, gains — warm closed "ooh/mm"
VOWELS = {
    "ooh": ([320, 870, 2240], [70, 90, 130], [1.0, 0.4, 0.10]),
    "mmm": ([280, 1100, 2400], [60, 90, 130], [1.0, 0.35, 0.12]),
    "aah": ([680, 1150, 2600], [90, 110, 150], [1.0, 0.5, 0.16]),
}

# inharmonic bell partials (ratio, gain, decay_s) → metallic chime
BELL = ([1.0, 2.0, 2.41, 3.02, 4.21], [1.0, 0.5, 0.35, 0.2, 0.12],
        [1.6, 1.2, 0.9, 0.7, 0.5])
BELL_HZ, BELL_SUB_HZ, SPARKLE_HZ = 888.0, 444.0, 8888.0


def build_blocks(presets: dict | None = None) -> list[dict]:
    """Harmonic scenes with pitches sourced from presets.yaml (single source of
    truth for the absolute solfeggio Hz). Pad octave-doublings are derived (f*2),
    NOT re-typed. 444/888/8888 accents are documented literals (not solfeggio)."""
    p = presets or load_presets()

    def S(n):
        return preset_frequency(f"solfeggio_{n}", p)

    r174, r285 = S(174), S(285)
    return [
        # bass root, pad partials, melody pool, voice pool
        dict(bass=r174, pad=[r174, r174 * 2, S(528)],
             mel=[S(396), S(417), S(528), S(639)], voice=[S(396), S(528)]),
        dict(bass=r285, pad=[r285, r285 * 2, S(852)],
             mel=[S(528), S(639), S(741), S(417)], voice=[S(528), S(639)]),
        # blocks 2-3: drop 396/417 from the melody (leave them to the voice) so
        # the drifting line separates in register from the hum.
        dict(bass=r174, pad=[r174, r174 * 2, S(528), S(852)],
             mel=[S(528), S(639), S(741), S(852)], voice=[S(528), S(639)]),
        dict(bass=r285, pad=[r285, r285 * 2, S(639)],
             mel=[S(417), S(528), S(639), S(741)], voice=[S(396), S(528)]),
    ]


# =============================================================================
# Filters / envelopes (pure, no RNG)
# =============================================================================
def lp(x, fc, sr, order=2):
    b, a = butter(order, min(fc / (sr / 2), 0.999), btype="low")
    return lfilter(b, a, x)


def hp(x, fc, sr, order=1):
    b, a = butter(order, max(fc / (sr / 2), 1e-4), btype="high")
    return lfilter(b, a, x)


def env_ar(n, atk_s, rel_s, sr):
    """Raised-cosine attack/release window (soft; guards against short n)."""
    e = np.ones(n)
    atk = min(int(atk_s * sr), n // 2)
    rel = min(int(rel_s * sr), n // 2)
    if atk > 0:
        e[:atk] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, atk))
    if rel > 0:
        e[-rel:] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, rel))
    return e


def block_of(bar, cfg, blocks, lag=0):
    """Scene for a bar. ``lag`` bars delays the change (used to stagger the
    melody/voice scene boundaries behind the bed so scenes dissolve)."""
    q = max(cfg.bars // 4, 1)
    return blocks[int(np.clip((bar - lag) // q, 0, len(blocks) - 1))]


def block_ranges(cfg):
    q = max(cfg.bars // 4, 1)
    return [(0, q), (q, 2 * q), (2 * q, 3 * q), (3 * q, cfg.bars)]


# =============================================================================
# Bed: sustained sub + warm detuned pad (raw; brightness applied in compose)
# =============================================================================
def synth_bed(N, cfg, rng, blocks):
    sr = cfg.sample_rate
    pad = np.zeros(N)
    sub = np.zeros(N)
    for i, (b0, b1) in enumerate(block_ranges(cfg)):
        blk = blocks[min(i, len(blocks) - 1)]
        i0 = int(b0 * cfg.bar * sr)
        ln = min(int(((b1 - b0) * cfg.bar + 1.4) * sr), N - i0)  # overlap next scene
        if ln <= 0:
            continue
        t = np.arange(ln) / sr
        env = env_ar(ln, 1.4, 1.6, sr)
        breathe = 0.85 + 0.15 * np.sin(TAU * 0.045 * t + rng.uniform(0, TAU))
        seg = np.zeros(ln)
        for f in blk["pad"]:
            # per-scene detune offset (i*0.7c) so a partial shared between two
            # consecutive scenes beats slowly instead of statically cancelling.
            for det in (-5.0 + i * 0.7, 5.0 + i * 0.7):
                fk = f * 2.0 ** (det / 1200.0)
                ph = rng.uniform(0, TAU)
                v = np.sin(TAU * fk * t + ph)
                for h in (2, 3, 4):
                    v += (1.0 / h) * 0.4 * np.sin(TAU * h * fk * t + ph)
                seg += v
        pad[i0:i0 + ln] += seg * env * breathe / len(blk["pad"])
        f = blk["bass"]
        s = np.sin(TAU * f * t + rng.uniform(0, TAU)) + 0.6 * np.sin(TAU * (f / 2) * t)
        sub[i0:i0 + ln] += s * env
    return pad, lp(sub, 220, sr) * 0.6


# =============================================================================
# Drifting melody (soft swells; solfeggio pitches; NO glide)
# =============================================================================
def _pick_near(prev, pool, rng, force_far=False):
    d = np.array([abs(np.log2(f / prev)) for f in pool])
    if force_far:
        return float(pool[int(np.argmax(d))])
    w = np.exp(-d / 0.45)            # soft weight: near favoured, far never zero
    w = w / w.sum()
    return float(pool[rng.choice(len(pool), p=w)])


def melody_events(cfg, rng, blocks, start_bar=4):
    ev = []
    prev = 528.0
    t = start_bar * cfg.bar
    end = (cfg.bars - 2) * cfg.bar
    leap_in = int(rng.integers(4, 7))
    k = 0
    while t < end:
        blk = block_of(int(t // cfg.bar), cfg, blocks, lag=2)   # stagger behind bed
        force = k > 0 and k % leap_in == 0                       # periodic wide leap
        f = _pick_near(prev, blk["mel"], rng, force_far=force)
        prev = f
        if force:
            leap_in = int(rng.integers(4, 7))
        dur = rng.uniform(2.0, 4.2)
        ev.append((t, dur, f))
        t += dur * rng.uniform(0.55, 0.85)                       # overlap → cross-fade
        k += 1
    return ev


def synth_melody(ev, N, cfg, rng):
    sr = cfg.sample_rate
    out = np.zeros(N)
    for (t0, dur, f) in ev:
        i0 = int(t0 * sr)
        i1 = min(i0 + int(dur * sr), N)
        if i1 <= i0:
            continue
        t = np.arange(i1 - i0) / sr
        vib = 1.0 + 0.004 * np.sin(TAU * 4.4 * t + rng.uniform(0, TAU))   # ±~7c
        ph = TAU * f * np.cumsum(vib) / sr
        v = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
        trem = 0.82 + 0.18 * np.sin(TAU * 0.16 * t + rng.uniform(0, TAU))
        out[i0:i1] += v * env_ar(i1 - i0, 0.4, 0.6, sr) * trem
    return lp(out, 2600, sr) * 0.5


# =============================================================================
# Voice: formant-synth wordless hum (Norah-ish), solfeggio pitches
# =============================================================================
def voice_events(cfg, rng, blocks, start_bar=12):
    ev = []
    prev = 528.0
    t = start_bar * cfg.bar
    end = (cfg.bars - 3) * cfg.bar
    vw = ["ooh", "mmm", "ooh", "aah"]
    k = 0
    while t < end:
        blk = block_of(int(t // cfg.bar), cfg, blocks, lag=2)
        f = _pick_near(prev, blk["voice"], rng)
        prev = f
        ev.append((t, rng.uniform(3.0, 5.5), f, vw[k % len(vw)]))
        k += 1
        t += ev[-1][1] * rng.uniform(0.9, 1.5)
    return ev


def synth_voice(ev, N, cfg, rng):
    sr = cfg.sample_rate
    out = np.zeros(N)
    for (t0, dur, f, vowel) in ev:
        i0 = int(t0 * sr)
        i1 = min(i0 + int(dur * sr), N)
        if i1 <= i0:
            continue
        n = i1 - i0
        t = np.arange(n) / sr
        vib = 1.0 + 0.006 * np.sin(TAU * 5.1 * t + rng.uniform(0, TAU))
        ph = TAU * f * np.cumsum(vib) / sr
        kmax = min(int((sr / 2) / f), 22)
        src = np.zeros(n)
        for kk in range(1, kmax + 1):
            src += (1.0 / kk ** 1.6) * np.sin(kk * ph)   # warmer than 1/k (less buzz)
        src = 0.5 * src + hp(rng.standard_normal(n), 2200, sr, 2) * 0.04  # + breath
        F, BW, G = VOWELS[vowel]
        voc = np.zeros(n)
        for fc, bw, g in zip(F, BW, G):
            lo = max(fc - bw, 40) / (sr / 2)
            hi = min(fc + bw, sr / 2 - 100) / (sr / 2)
            b, a = butter(2, [lo, hi], btype="band")
            voc += g * lfilter(b, a, src)
        out[i0:i1] += voc * env_ar(n, 0.5, 0.9, sr)
    m = float(np.max(np.abs(out)))
    return out / m * 0.5 if m > 0 else out


# =============================================================================
# Deep beat — kick carries audible mid-body (not just sub), for the phone
# =============================================================================
def _kick(rng, sr):
    n = int(0.36 * sr)
    t = np.arange(n) / sr
    f = 46 + 120 * np.exp(-t / 0.05)                       # 166 → 46 Hz fundamental
    body = np.sin(TAU * np.cumsum(f) / sr) * np.exp(-t / 0.17)
    sub = np.sin(TAU * 47 * t) * np.exp(-t / 0.24) * 0.35  # desktop foundation
    thump = np.sin(TAU * 165 * t) * np.exp(-t / 0.05) * 0.5   # phone-audible punch
    knock = np.sin(TAU * 110 * t) * np.exp(-t / 0.07) * 0.4
    click = hp(rng.standard_normal(n), 1500, sr, 2) * np.exp(-t / 0.004) * 0.25
    k = body + sub + thump + knock + click
    k = hp(k, 70, sr, 1)                                   # HP before saturation
    return np.tanh(2.2 * k) * 0.85                         # more drive → survives on phone


def _rim(rng, sr):
    n = int(0.13 * sr)
    t = np.arange(n) / sr
    tone = np.sin(TAU * 330 * t) * np.exp(-t / 0.03) * 0.5
    noise = hp(rng.standard_normal(n), 2500, sr, 2) * np.exp(-t / 0.05) * 0.6
    return (tone + noise) * 0.5


def _hat(rng, sr, open_=False):
    n = int((0.16 if open_ else 0.04) * sr)
    t = np.arange(n) / sr
    return hp(rng.standard_normal(n), 7500, sr, 2) * np.exp(-t / (0.06 if open_ else 0.011)) * 0.4


def synth_drums(N, cfg, rng):
    sr = cfg.sample_rate
    out = np.zeros(N)
    rev = np.zeros(N)
    kick, rim, hatc, hato = _kick(rng, sr), _rim(rng, sr), _hat(rng, sr), _hat(rng, sr, True)

    def place(buf, dst, step, bar, vel, swing=True):
        sw = 0.14 * cfg.step if (swing and step % 2 == 1) else 0.0
        jit = rng.uniform(-0.002, 0.002)
        i0 = int((bar * cfg.bar + step * cfg.step + sw + jit) * sr)
        i1 = min(i0 + len(buf), N)
        if 0 <= i0 < i1:
            dst[i0:i1] += buf[: i1 - i0] * vel

    for bar in range(cfg.bars):
        place(kick, out, 0, bar, rng.uniform(0.95, 1.0))
        place(kick, out, 8, bar, rng.uniform(0.8, 0.95))
        if rng.random() < 0.4:
            place(kick, out, 11, bar, 0.55)
        for s in (4, 12):
            v = rng.uniform(0.5, 0.7)
            place(rim, out, s, bar, v)
            place(rim, rev, s, bar, v)
        for s in range(2, 16, 4):
            if s == 14 and rng.random() < 0.5:
                place(hato, out, s, bar, 0.35)
            else:
                place(hatc, out, s, bar, rng.uniform(0.18, 0.30))
    return lp(out, 11000, sr) * 0.95, rev


# =============================================================================
# 888 Hz bell (inharmonic, discrete — with release fade to kill HF clicks)
# =============================================================================
def bell_events(cfg, rng, start_bar=8):
    ev = []
    for bar in range(start_bar, cfg.bars - 1):
        if bar % 4 == 0:
            f = BELL_SUB_HZ if rng.random() < 0.3 else BELL_HZ
            ev.append((bar * cfg.bar, rng.uniform(0.7, 1.0), f))
        if bar % 8 == 4 and rng.random() < 0.6:
            ev.append((bar * cfg.bar + 8 * cfg.step, 0.5, BELL_HZ))
    # mark the breakdown drop/return with the phone-audible 888 (fixed pitch → no RNG)
    bd0, bd1 = int(cfg.bars * 0.60), int(cfg.bars * 0.75)
    for b in (bd0, bd1 - 1, bd1):
        if start_bar <= b < cfg.bars:
            ev.append((b * cfg.bar, 0.9, BELL_HZ))
    return ev


def synth_bell(ev, N, cfg, rng):
    sr = cfg.sample_rate
    ratios, gains, decays = BELL
    out = np.zeros(N)
    for (t0, vel, f0) in ev:
        i0 = int(t0 * sr)
        i1 = min(i0 + int(2.2 * sr), N)
        if i1 <= i0:
            continue
        t = np.arange(i1 - i0) / sr
        s = np.zeros(i1 - i0)
        for r, g, dc in zip(ratios, gains, decays):
            fk = f0 * r * (1 + rng.uniform(-0.002, 0.002))
            s += g * np.sin(TAU * fk * t) * np.exp(-t / dc)
        s *= env_ar(i1 - i0, 0.003, 0.015, sr)             # 15ms release → no click
        out[i0:i1] += s * vel
    return out * 0.5


def synth_sparkle(N, cfg, rng, start_bar=4):
    sr = cfg.sample_rate
    out = np.zeros(N)
    t = start_bar * cfg.bar
    end = (cfg.bars - 2) * cfg.bar
    while t < end:
        f = SPARKLE_HZ * (1 + rng.uniform(-0.004, 0.004))
        dur = rng.uniform(0.18, 0.5)
        i0 = int(t * sr)
        i1 = min(i0 + int(dur * sr), N)
        if i1 > i0:
            tt = np.arange(i1 - i0) / sr
            g = np.sin(TAU * f * tt) * np.exp(-tt / (dur * 0.4))
            g *= env_ar(i1 - i0, 0.004, 0.015, sr)         # release → no HF click
            out[i0:i1] += g * rng.uniform(0.5, 1.0)
        t += rng.uniform(0.8, 2.6)
    return out * 0.5


def reverb(x, rng, sr, decay=0.5, length=2.4):
    n = int(length * sr)
    t = np.arange(n) / sr
    ir = rng.standard_normal(n) * np.exp(-t / decay)
    ir[: int(0.028 * sr)] = 0                              # 28ms pre-delay (clarity)
    ir /= np.sqrt(np.sum(ir ** 2))
    return fftconvolve(x, ir)[: len(x)]


def _gate(N, cfg, on_bar, off_bar=0):
    t = np.arange(N) / cfg.sample_rate / cfg.bar
    a = 0.5 - 0.5 * np.cos(np.clip((t - on_bar) / 1.5, 0, 1) * np.pi)
    b = (0.5 + 0.5 * np.cos(np.clip((t - (off_bar - 1.5)) / 1.5, 0, 1) * np.pi)) if off_bar else 1.0
    return a * b


# =============================================================================
# compose
# =============================================================================
def compose(cfg: ComposeConfig | None = None):
    """Render the piece. Returns ``(stereo (n,2) in [-1,1], meta)``. Deterministic
    for ``cfg.seed`` — each layer gets its own seeded RNG so editing one layer does
    not perturb the others."""
    cfg = cfg or ComposeConfig()
    sr = cfg.sample_rate
    N = int((cfg.bars * cfg.bar + 4.0) * sr)               # + reverb/fade tail
    presets = load_presets()
    blocks = build_blocks(presets)

    rng_bed = np.random.default_rng(cfg.seed + 1)
    rng_mel = np.random.default_rng(cfg.seed + 2)
    rng_voc = np.random.default_rng(cfg.seed + 3)
    rng_drm = np.random.default_rng(cfg.seed + 4)
    rng_bel = np.random.default_rng(cfg.seed + 5)
    rng_spk = np.random.default_rng(cfg.seed + 6)
    rng_mst = np.random.default_rng(cfg.seed + 7)

    pad_raw, sub = synth_bed(N, cfg, rng_bed, blocks)
    mel = synth_melody(melody_events(cfg, rng_mel, blocks), N, cfg, rng_mel)
    voc = (synth_voice(voice_events(cfg, rng_voc, blocks), N, cfg, rng_voc)
           if cfg.use_voice else np.zeros(N))
    drums, rim_send = synth_drums(N, cfg, rng_drm)
    bell = synth_bell(bell_events(cfg, rng_bel), N, cfg, rng_bel) if cfg.use_bells else np.zeros(N)
    spark = synth_sparkle(N, cfg, rng_spk) if cfg.use_bells else np.zeros(N)

    # macro arc: deep beat drops for a breakdown (bars 60%..75%)
    bd0, bd1 = int(cfg.bars * 0.60), int(cfg.bars * 0.75)
    g_drums = np.clip(_gate(N, cfg, 8, bd0) + _gate(N, cfg, bd1, cfg.bars - 2), 0, 1)
    drums *= g_drums
    rim_send *= g_drums

    # pad brightness arc: crossfade dark↔bright lowpass so the bed opens up over
    # the piece (continuous internal motion), darkening through the breakdown.
    tb = np.arange(N) / sr / cfg.bar
    blend = np.clip(0.18 + 0.72 * (tb / cfg.bars), 0, 1) * (0.4 + 0.6 * g_drums)
    pad = lp(pad_raw, 1300, sr) * (1 - blend) + lp(pad_raw, 2300, sr) * blend
    pad *= 0.42

    # gentle sidechain: duck pad low-mids + sub under the kick (gated by g_drums,
    # so the breakdown — where the kick is gone — does not phantom-pump).
    duck = np.ones(N)
    for bar in range(cfg.bars):
        for step, dep in ((0, 0.5), (8, 0.42)):
            i = int((bar * cfg.bar + step * cfg.step) * sr)
            if i >= N:
                continue
            L = min(int(0.16 * sr), N - i)
            duck[i:i + L] *= 1 - dep * g_drums[i] * np.exp(-np.arange(L) / (0.075 * sr))
    pad *= 0.6 + 0.4 * duck
    sub = sub * duck

    # reverb send: high-passed so it stays clear (no low-mid wash)
    send = hp(0.45 * pad + 0.6 * mel + 0.95 * voc + 0.8 * rim_send
              + 0.6 * bell + 0.5 * spark, 300, sr, 2)
    wet = reverb(send, rng_mst, sr) * 0.34

    mix = pad + sub + drums + 0.7 * mel + 0.62 * voc + 0.26 * bell + 0.14 * spark + wet
    mix = hp(mix, 24, sr, 1)
    mix = np.tanh(1.1 * mix) / np.tanh(1.1)
    fi, fo = int(2.0 * sr), int(7.0 * sr)
    mix[:fi] *= np.linspace(0, 1, fi)
    mix[-fo:] *= np.linspace(1, 0, fo)
    mix *= cfg.gain / max(float(np.max(np.abs(mix))), 1e-9)

    # MONO-SAFE stereo: mid/side where the side is a high-passed, delayed copy, so
    # L+R == 2*mix EXACTLY (comb-free mono) and width lives only >1800 Hz (which is
    # inaudible on the phone anyway). Replaces a 9ms full-mix Haas that combed the
    # audible mid-body of the mono sum.
    d = int(0.009 * sr)
    side = np.concatenate([np.zeros(d), hp(mix, 1800, sr, 1)[:-d]])
    w = 0.15
    stereo = np.stack([mix + w * side, mix - w * side], axis=1)
    stereo *= cfg.gain / float(np.max(np.abs(stereo)))

    meta = cfg.as_meta()
    meta["frames"] = int(stereo.shape[0])
    return stereo, meta


# =============================================================================
# CLI
# =============================================================================
def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="namima.solfeggio_composer",
        description="Offline solfeggio ambient composer (candidate).",
    )
    p.add_argument("--out", default="drift.wav", help="output WAV path")
    p.add_argument("--bars", type=int, default=72, help="length in bars (~1.5s/bar at 96bpm)")
    p.add_argument("--smoke", action="store_true", help="short 16-bar smoke render")
    p.add_argument("--bpm", type=float, default=96.0)
    p.add_argument("--seed", type=int, default=528639)
    p.add_argument("--gain", type=float, default=0.86, help="peak target 0..1")
    p.add_argument("--no-bells", action="store_true", help="disable 888/8888 accents")
    p.add_argument("--no-voice", action="store_true", help="disable the formant hum")
    args = p.parse_args(argv)

    cfg = ComposeConfig(
        bars=16 if args.smoke else args.bars,
        bpm=args.bpm, seed=args.seed, gain=args.gain,
        use_bells=not args.no_bells, use_voice=not args.no_voice,
    )
    stereo, meta = compose(cfg)
    write_wav24(args.out, stereo, cfg.sample_rate)
    dur = stereo.shape[0] / cfg.sample_rate
    peak = float(np.max(np.abs(stereo)))
    print(f"wrote {args.out}  {dur:.1f}s  bars={cfg.bars}  seed={cfg.seed}  "
          f"peak={peak:.3f}  bells={cfg.use_bells}  voice={cfg.use_voice}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
