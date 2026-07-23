"""Solfeggio IDM (candidate) — Aphex-Twin SAW-era mood ("Xtal" / "On").

Where ``solfeggio_composer`` drifts, this one *grooves*: composed riffs with 間
(rests), distinct instrument timbres, swing, and a syncopated bass locked to the
kick. Response to feedback that the drift piece was 単調 (monotonous) with 音色が
ない (no timbre).

Register → timbre assignment (all pitches are ABSOLUTE solfeggio Hz, non-12-TET;
octave shifts f*2 / f/2 preserve the pitch class):
  * 174 / 285 (low)      → bouncing octave BASS + warm breathy PAD body
  * 396 / 417 / 528 (mid)→ Karplus-Strong PLUCK answers + formant VOICE air
  * 639 / 741 / 852 (hi) → FM MALLET-BELL main riff (the "On" stab timbre)
  * 963 / 888 (top)      → accents only

LOCKED AESTHETIC (user direction):
  * NO portamento/glide lead (stable pitch per note; plucks/stabs are fine).
  * solfeggio frequencies as absolute Hz from presets.yaml — outside do-re-mi.
  * groove + riffs with 間; Aphex Twin "Xtal"/"On" as the mood reference.

DESIGN CONSTRAINTS: numpy + scipy only; deterministic per-layer seeded RNG;
48 kHz / 24-bit via generator.write_wav24; mono-compatible master (M/S with
high-passed side — L+R == 2*mix exactly); kick carries phone-audible mid-body.
Candidate only: no runtime wiring, generated audio gitignored.

    python -m namima.solfeggio_idm --out idm.wav            # full ~3 min
    python -m namima.solfeggio_idm --out s.wav --smoke      # 16-bar smoke
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.signal import butter, lfilter

from .generator import write_wav24, load_presets, preset_frequency
from .solfeggio_composer import lp, hp, env_ar, reverb, VOWELS

__version__ = "0.3.0-candidate"   # v0.3: soft round low end (no sub saturation,
                                  # split-band master), FM e-piano stabs, airier mix
TAU = 2.0 * np.pi


@dataclass
class IdmConfig:
    bars: int = 88
    bpm: float = 114.0
    seed: int = 852963
    sample_rate: int = 48000
    gain: float = 0.86

    @property
    def beat(self) -> float:
        return 60.0 / self.bpm

    @property
    def bar(self) -> float:
        return 4.0 * self.beat

    @property
    def step(self) -> float:
        return self.beat / 4.0

    def as_meta(self) -> dict:
        return {
            "version": __version__, "kind": "solfeggio_idm", "bpm": self.bpm,
            "bars": self.bars, "seed": self.seed, "sample_rate": self.sample_rate,
            "bit_depth": 24, "channels": 2, "gain": self.gain,
            "pitch_system": "absolute-solfeggio-Hz (non-12-TET; presets.yaml)",
        }


def build_scenes(presets: dict | None = None) -> list[dict]:
    """Two alternating harmonic scenes; pitches sourced from presets.yaml."""
    p = presets or load_presets()

    def S(n):
        return preset_frequency(f"solfeggio_{n}", p)

    return [
        dict(root=S(174), bell=[S(639), S(741), S(852), S(963)],
             pluck=[S(396), S(417), S(528)], pad=[S(174), S(174) * 2, S(417), S(528)],
             voice=[S(396), S(528)]),
        dict(root=S(285), bell=[S(639), S(741), S(852), S(963)],
             pluck=[S(417), S(528), S(639)], pad=[S(285), S(285) * 2, S(639)],
             voice=[S(417), S(639)]),
    ]


# =============================================================================
# Instrument timbres (each a distinct voice — the 音色 layer)
# =============================================================================
def fm_bell(f, dur, sr, rng):
    """2-op FM mallet/bell — the "On" stab. Inharmonic 3.53 ratio, index decays
    fast so the strike is metallic and the tail is warm. Stable pitch (no glide)."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    I = 2.4 * np.exp(-t / 0.11)                      # FM index envelope
    mod = np.sin(TAU * f * 3.53 * t)
    v = np.sin(TAU * f * t + I * mod)
    v += 0.35 * np.sin(TAU * f * 1.004 * t + 0.6 * I * mod)   # detuned body
    v += 0.25 * np.sin(TAU * f * 0.5 * t) * np.exp(-t / 0.5)  # sub-octave warmth
    v *= np.exp(-t / 0.34)
    v *= env_ar(n, 0.002, 0.02, sr)
    return lp(v, 6500, sr, 2)


def ks_pluck(f, dur, sr, rng):
    """Karplus-Strong pluck — organic string-ish answer voice."""
    n = int(dur * sr)
    p = max(int(sr / f), 2)
    buf = rng.standard_normal(p) * 0.7
    out = np.zeros(n + p)
    prev = buf
    pos = 0
    while pos < n:
        cur = 0.5 * (prev + np.concatenate([prev[-1:], prev[:-1]])) * 0.994
        m = min(p, n - pos)
        out[pos:pos + m] = cur[:m]
        prev = cur
        pos += m
    v = out[:n] * env_ar(n, 0.001, 0.05, sr)
    return lp(v, 4200, sr, 2)


def bass_note(f, dur, sr):
    """Rounded, driven bass — bouncy, locks to the kick."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    v = np.sin(TAU * f * t) + 0.35 * np.sin(TAU * 2 * f * t) + 0.12 * np.sin(TAU * 3 * f * t)
    v = np.tanh(1.8 * v)
    env = np.exp(-t / (dur * 0.45))
    atk = max(int(0.004 * sr), 1)
    env[:atk] *= np.linspace(0, 1, atk)
    return lp(v * env * env_ar(n, 0.002, 0.03, sr), 900, sr, 2)


def breathy_pad(freqs, dur, sr, rng):
    """Warm detuned pad + air noise — the Xtal breathiness."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    v = np.zeros(n)
    for f in freqs:
        for det in (-4.0, 4.0):
            fk = f * 2.0 ** (det / 1200.0)
            ph = rng.uniform(0, TAU)
            for h in (1, 2, 3, 4):
                v += (1.0 / h ** 1.3) * np.sin(TAU * h * fk * t + ph)
    v = lp(v, 1700, sr, 2) / max(len(freqs), 1)
    breath = lfilter(*butter(2, [800 / (sr / 2), 2600 / (sr / 2)], btype="band"),
                     rng.standard_normal(n)) * 0.05
    breath *= 0.6 + 0.4 * np.sin(TAU * 0.11 * t + rng.uniform(0, TAU))
    return (v + breath) * env_ar(n, 1.2, 1.4, sr)


def voice_air(freqs, dur, sr, rng, vowel="aah"):
    """Breathy formant chord — wordless vocal air (Xtal-ish)."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    F, BW, G = VOWELS[vowel]
    for f in freqs:
        vib = 1.0 + 0.005 * np.sin(TAU * 4.8 * t + rng.uniform(0, TAU))
        ph = TAU * f * np.cumsum(vib) / sr
        kmax = min(int((sr / 2) / f), 18)
        src = np.zeros(n)
        for kk in range(1, kmax + 1):
            src += (1.0 / kk ** 1.4) * np.sin(kk * ph)
        src = 0.4 * src + hp(rng.standard_normal(n), 1800, sr, 2) * 0.12  # breathier
        voc = np.zeros(n)
        for fc, bw, g in zip(F, BW, G):
            b, a = butter(2, [max(fc - bw, 40) / (sr / 2),
                              min(fc + bw, sr / 2 - 100) / (sr / 2)], btype="band")
            voc += g * lfilter(b, a, src)
        out += voc
    m = float(np.max(np.abs(out)))
    return (out / m if m > 0 else out) * env_ar(n, 0.7, 0.9, sr)


# --- drums -------------------------------------------------------------------
def _kick(rng, sr):
    """Round, soft deep-house kick (Axel-Boman-ish thud) — weight without crush.
    Light drive only; the deep tail stays clean so full-range speakers get a
    soft round low end, while thump/knock keep it readable on small speakers."""
    n = int(0.38 * sr)
    t = np.arange(n) / sr
    f = 45 + 105 * np.exp(-t / 0.05)
    body = np.sin(TAU * np.cumsum(f) / sr) * np.exp(-t / 0.16)
    thump = np.sin(TAU * 168 * t) * np.exp(-t / 0.05) * 0.42   # phone-audible
    knock = np.sin(TAU * 110 * t) * np.exp(-t / 0.07) * 0.35
    sub = np.sin(TAU * 46 * t) * np.exp(-t / 0.30) * 0.55      # long soft tail
    click = hp(rng.standard_normal(n), 1600, sr, 2) * np.exp(-t / 0.003) * 0.13
    k = hp(body + thump + knock + sub + click, 32, sr, 1)
    return np.tanh(1.5 * k) / np.tanh(1.5) * 0.8


def _hat(rng, sr, open_=False):
    n = int((0.14 if open_ else 0.035) * sr)
    t = np.arange(n) / sr
    return hp(rng.standard_normal(n), 8000, sr, 2) * np.exp(-t / (0.05 if open_ else 0.010)) * 0.4


def _shaker(rng, sr):
    n = int(0.06 * sr)
    t = np.arange(n) / sr
    b, a = butter(2, [4000 / (sr / 2), 9000 / (sr / 2)], btype="band")
    return lfilter(b, a, rng.standard_normal(n)) * np.exp(-t / 0.02) * 0.3


def _snare(rng, sr):
    """Punchy break snare — tone + tuned rattle noise."""
    n = int(0.19 * sr)
    t = np.arange(n) / sr
    tone = (np.sin(TAU * 192 * t) + 0.5 * np.sin(TAU * 330 * t)) * np.exp(-t / 0.045) * 0.6
    b, a = butter(2, [1200 / (sr / 2), 6500 / (sr / 2)], btype="band")
    rattle = lfilter(b, a, rng.standard_normal(n)) * np.exp(-t / 0.07)
    return np.tanh(1.5 * (tone + rattle)) * 0.6


# =============================================================================
# Break engine — synthesize a 2-bar loop, then CHOP it (切り刻み)
# =============================================================================
def synth_break_loop(cfg, rng):
    """A straight-grid (no swing) 2-bar breakbeat loop; swing is added at
    reassembly so slice boundaries stay aligned to the hits."""
    sr = cfg.sample_rate
    step_n = int(cfg.step * sr)
    n = step_n * 32
    loop = np.zeros(n + int(0.4 * sr))
    kick = _kick(rng, sr) * 0.6                     # mid-weighted (the BODY kick is a
    kick = hp(kick, 90, sr, 1)                      # separate clean layer)
    snr, hatc, hato, shk = _snare(rng, sr), _hat(rng, sr), _hat(rng, sr, True), _shaker(rng, sr)

    def put(buf, slot, vel):
        i0 = slot * step_n
        i1 = min(i0 + len(buf), len(loop))
        loop[i0:i1] += buf[: i1 - i0] * vel

    for slot, vel in [(0, 1.0), (10, 0.9), (16, 1.0), (22, 0.85), (24, 0.6)]:
        put(kick, slot, vel)
    for slot, vel in [(4, 1.0), (12, 0.95), (20, 1.0), (28, 0.95), (30, 0.5)]:
        put(snr, slot, vel)
    for slot, vel in [(7, 0.3), (15, 0.25), (23, 0.3), (27, 0.25)]:   # ghosts
        put(snr, slot, vel)
    vel16 = [0.85, 0.30, 0.55, 0.30]
    for slot in range(32):
        if slot in (14, 26):
            put(hato, slot, 0.45)
        else:
            put(hatc, slot, vel16[slot % 4] * rng.uniform(0.85, 1.0))
        if slot % 2 == 0:
            put(shk, slot, 0.5)
    return loop[:n]


def chop_break(loop, cfg, rng, intensity, fill=False):
    """Reassemble the 2-bar loop from its 32 16th-slices with seeded edit ops:
    stutter / reverse / neighbor-swap / half-speed / mute (間). ``intensity``
    0..1 scales how mangled the phrase gets; ``fill`` forces a snare roll at the
    tail. Slices get 2 ms edge fades so cuts never click."""
    sr = cfg.sample_rate
    step_n = len(loop) // 32
    out = np.zeros(len(loop) + int(0.25 * sr))
    swing_n = int(0.14 * cfg.step * sr)

    def slice_at(j):
        j = int(np.clip(j, 0, 31))
        return loop[j * step_n:(j + 1) * step_n]

    for j in range(32):
        r = rng.random()
        s = slice_at(j)
        if fill and j >= 28:                                  # phrase-end snare roll
            src = slice_at(4)                                 # a snare slice
            sub_len = step_n // 2
            for k in range(2):
                seg = src[:sub_len] * (1.0 - 0.18 * k)
                seg = seg * env_ar(len(seg), 0.002, 0.002, sr)
                i0 = j * step_n + k * sub_len
                out[i0:i0 + len(seg)] += seg
            continue
        if r < 0.05 * intensity:
            continue                                          # mute = 間
        elif r < 0.15 * intensity:
            sub_n = max(step_n // int(rng.integers(2, 5)), 8)  # stutter/retrigger
            reps = step_n // sub_n
            seg0 = s[:sub_n] * env_ar(sub_n, 0.002, 0.002, sr)
            for k in range(reps):
                out_i = j * step_n + k * sub_n
                out[out_i:out_i + sub_n] += seg0 * (1.0 - 0.12 * k)
            continue
        elif r < 0.21 * intensity:
            s = s[::-1]                                       # reverse
        elif r < 0.28 * intensity:
            s = slice_at(j + int(rng.choice([-1, 1, 2])))     # neighbor swap
        elif r < 0.33 * intensity:
            half = s[: step_n // 2]                           # half-speed pitch-down
            s = np.interp(np.arange(step_n) / 2.0, np.arange(len(half)), half,
                          right=0.0)
        s = s * env_ar(len(s), 0.002, 0.002, sr)
        i0 = j * step_n + (swing_n if j % 2 == 1 else 0)      # swing at reassembly
        out[i0:i0 + len(s)] += s
    return out


# =============================================================================
# Fat bass bus — sub (<100 Hz, solfeggio octave-downs) + driven mid layer
# =============================================================================
def sub_note(f, dur, sr):
    """Pure deep sine sub — body weight (体にくる). Soft edges, no click.
    Stays CLEAN through the whole chain (saturating the sub is what crushes a
    low end); softness comes from the round attack and the un-driven sine."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    v = np.sin(TAU * f * t) + 0.30 * np.sin(TAU * 2 * f * t)
    env = np.exp(-t / (dur * 1.2))
    return lp(v * env, 170, sr, 2) * env_ar(n, 0.014, 0.10, sr)


def ep_stab(freqs, dur, sr, rng):
    """Warm FM e-piano chord stab (1:1 modulator = Rhodes-ish) with tremolo —
    the Axel-Boman "Hello" chord warmth. Rich but soft; rings and breathes."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    for f in freqs:
        ph = rng.uniform(0, TAU)
        I = 1.1 * np.exp(-t / 0.35)                     # FM index decays → mellow tail
        v = np.sin(TAU * f * t + I * np.sin(TAU * f * t + ph) + ph)
        v += 0.30 * np.sin(TAU * 2 * f * t + ph) * np.exp(-t / 0.22)   # strike tine
        out += v * np.exp(-t / 0.95)
    trem = 1 + 0.10 * np.sin(TAU * 4.6 * t + rng.uniform(0, TAU))
    out *= trem / max(len(freqs), 1)
    return lp(out, 3600, sr, 2) * env_ar(n, 0.006, 0.12, sr)


# =============================================================================
# Patterns (composed riffs with 間 — rests are part of the phrase)
# =============================================================================
# bell riff: 2 bars of (step, pool_idx, oct_mul, vel); bar 2 leaves space
BELL_RIFF = [
    (0, 0, 1.0, 1.00), (3, 1, 1.0, 0.80), (6, 2, 1.0, 0.90),
    (10, 1, 0.5, 0.70), (14, 3, 1.0, 0.85),
    (16 + 2, 2, 1.0, 0.80), (16 + 7, 0, 2.0, 0.55), (16 + 8, 1, 1.0, 0.90),
    (16 + 11, 3, 0.5, 0.75),
]
# bass groove: (step, oct_mul, dur_s, vel) — bouncing octaves, syncopated
BASS_PAT = [
    (0, 0.5, 0.30, 1.00), (3, 0.5, 0.12, 0.60), (6, 1.0, 0.15, 0.80),
    (8, 0.5, 0.25, 0.90), (11, 1.0, 0.12, 0.70), (14, 0.5, 0.10, 0.50),
]
PLUCK_STEPS = [5, 13]                     # answers in the riff's gaps


def bar_activity(cfg):
    """Arrangement: per-bar level (0..1) for each layer. The macro arc — intro →
    groove → riff → breakdown (間) → full return → outro."""
    B = cfg.bars
    act = {k: np.zeros(B) for k in
           ("pad", "air", "hats", "kick", "bass", "bell", "pluck", "clap", "ep")}

    def on(key, b0, b1, v=1.0):
        act[key][max(b0, 0):min(b1, B)] = v

    on("pad", 0, B, 0.9)
    on("air", 0, 8, 0.8)
    on("hats", 8, 40); on("hats", 48, 82)
    on("bass", 8, 40); on("bass", 48, 84)
    on("kick", 12, 40); on("kick", 48, 82)
    on("clap", 16, 40); on("clap", 48, 80)
    on("bell", 16, 40); on("bell", 40, 48, 0.55); on("bell", 48, 80)
    on("pluck", 24, 40); on("pluck", 56, 80)
    on("ep", 12, 40, 0.85); on("ep", 40, 48, 0.6); on("ep", 48, 82)
    on("air", 16, 18, 0.7); on("air", 24, 26, 0.7)
    on("air", 40, 48, 1.0)                          # breakdown = voice floats
    on("air", 56, 58, 0.8); on("air", 64, 66, 0.8); on("air", 72, 74, 0.8)
    on("pad", 80, B, 0.7); on("air", 82, B, 0.9)
    return act


def smooth_gate(act_row, N, cfg):
    """Upsample a per-bar activity row to sample rate with 1/4-bar cosine ramps."""
    sr = cfg.sample_rate
    bar_n = cfg.bar * sr
    g = np.zeros(N)
    edge = int(bar_n * 0.25)
    for b, v in enumerate(act_row):
        i0 = int(b * bar_n)
        i1 = min(int((b + 1) * bar_n), N)
        if i1 > i0:
            g[i0:i1] = v
    if edge > 1:                                     # soften every level change
        w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, edge))
        k = np.concatenate([w, w[::-1]])
        k /= k.sum()
        g = np.convolve(g, k, mode="same")
    return g


# =============================================================================
# compose
# =============================================================================
def compose(cfg: IdmConfig | None = None):
    """Render the piece. Returns ``(stereo (n,2), meta)``. Deterministic."""
    cfg = cfg or IdmConfig()
    sr = cfg.sample_rate
    N = int((cfg.bars * cfg.bar + 3.0) * sr)
    scenes = build_scenes()
    act = bar_activity(cfg)

    r_bell = np.random.default_rng(cfg.seed + 11)
    r_plk = np.random.default_rng(cfg.seed + 12)
    r_bass = np.random.default_rng(cfg.seed + 13)
    r_pad = np.random.default_rng(cfg.seed + 14)
    r_air = np.random.default_rng(cfg.seed + 15)
    r_drm = np.random.default_rng(cfg.seed + 16)
    r_mst = np.random.default_rng(cfg.seed + 17)

    def scene_of(bar):
        return scenes[(bar // 16) % 2]

    def put(dst, buf, t0, vel):
        i0 = int(t0 * sr)
        i1 = min(i0 + len(buf), N)
        if 0 <= i0 < i1:
            dst[i0:i1] += buf[: i1 - i0] * vel

    swing = 0.14 * cfg.step

    def stime(bar, step, human=0.0015, rng=r_drm):
        t = bar * cfg.bar + step * cfg.step
        if step % 2 == 1:
            t += swing
        return t + rng.uniform(-human, human)

    # --- bell riff (FM mallet) — repeats WITH variation, and rests (間) -------
    bell = np.zeros(N)
    for phrase in range(0, cfg.bars, 2):
        if act["bell"][min(phrase, cfg.bars - 1)] <= 0:
            continue
        pool = scene_of(phrase)["bell"]
        mute = int(r_bell.integers(0, len(BELL_RIFF)))          # drop one hit / phrase
        subst = int(r_bell.integers(0, len(BELL_RIFF)))         # re-pitch one hit
        for j, (st, idx, octm, vel) in enumerate(BELL_RIFF):
            if j == mute and r_bell.random() < 0.5:
                continue
            idx2 = int(r_bell.integers(0, len(pool))) if j == subst else idx
            bar = phrase + st // 16
            if bar >= cfg.bars:
                continue
            f = pool[idx2 % len(pool)] * octm
            v = fm_bell(f, 0.9, sr, r_bell)
            put(bell, v, stime(bar, st % 16, rng=r_bell),
                vel * float(act["bell"][bar]))

    # --- pluck answers (Karplus-Strong) in the gaps ---------------------------
    plk = np.zeros(N)
    for bar in range(cfg.bars):
        a = float(act["pluck"][bar])
        if a <= 0 or bar % 2 == 0:                              # answers on odd bars
            continue
        pool = scene_of(bar)["pluck"]
        for s in PLUCK_STEPS:
            if r_plk.random() < 0.75:
                f = pool[int(r_plk.integers(0, len(pool)))]
                v = ks_pluck(f, 0.7, sr, r_plk)
                put(plk, v, stime(bar, s, rng=r_plk), 0.8 * a)

    # --- fat bass bus: driven mid layer + deep sub (<100 Hz) ------------------
    # sub pitches are solfeggio octave-downs (174→87/43.5, 285→142.5/71.25 Hz):
    # same non-12-TET pitch classes, just dropped into the body register.
    bass = np.zeros(N)
    subb = np.zeros(N)
    for bar in range(cfg.bars):
        a = float(act["bass"][bar])
        if a <= 0:
            continue
        root = scene_of(bar)["root"]
        for (s, octm, dur, vel) in BASS_PAT:
            if s == 14 and r_bass.random() < 0.35:              # occasional 間
                continue
            v = bass_note(root * octm, dur, sr)
            put(bass, v, stime(bar, s, rng=r_bass), vel * a)
        fsub = root / 2.0                                       # 87 / 142.5 Hz
        for (s, dur_steps, vel) in ((0, 3.5, 1.0), (6, 1.5, 0.7), (8, 3.5, 0.95)):
            put(subb, sub_note(fsub, dur_steps * cfg.step, sr),
                stime(bar, s, human=0.0008, rng=r_bass), vel * a)
        if bar % 8 == 0:                                        # phrase drop: /4 deep
            put(subb, sub_note(root / 4.0, 2.0 * cfg.beat, sr),
                bar * cfg.bar, 0.85 * a)

    # --- e-piano offbeat stabs (the "Hello" warmth; deep-house bounce) --------
    r_ep = np.random.default_rng(cfg.seed + 19)
    ep = np.zeros(N)
    for bar in range(cfg.bars):
        a = float(act["ep"][bar])
        if a <= 0:
            continue
        sc = scene_of(bar)
        chord = sorted({f * 2 if f < 300 else f for f in sc["pad"]})[:4]
        for s, vel in ((2, 0.9), (10, 0.75)):           # offbeats of beats 1 & 3
            if r_ep.random() < 0.12:                    # occasional 間
                continue
            v = ep_stab(chord, 1.1, sr, r_ep)
            put(ep, v, stime(bar, s, rng=r_ep), vel * a * r_ep.uniform(0.85, 1.0))
        if bar % 4 == 3 and r_ep.random() < 0.5:        # pickup push
            v = ep_stab(chord, 0.7, sr, r_ep)
            put(ep, v, stime(bar, 14, rng=r_ep), 0.55 * a)

    # --- pad + vocal air ------------------------------------------------------
    pad = np.zeros(N)
    for b0 in range(0, cfg.bars, 4):
        a = float(np.max(act["pad"][b0:b0 + 4]))
        if a <= 0:
            continue
        sc = scene_of(b0)
        v = breathy_pad(sc["pad"], 4 * cfg.bar + 1.2, sr, r_pad)
        put(pad, v, b0 * cfg.bar, a)

    air = np.zeros(N)
    for bar in range(cfg.bars):
        a = float(act["air"][bar])
        if a <= 0 or act["air"][max(bar - 1, 0)] > 0 and bar > 0:
            continue                                             # start of a swell only
        span = 1
        while bar + span < cfg.bars and act["air"][bar + span] > 0:
            span += 1
        sc = scene_of(bar)
        vw = "aah" if (bar // 8) % 2 == 0 else "ooh"
        v = voice_air(sc["voice"], span * cfg.bar + 0.8, sr, r_air, vw)
        put(air, v, bar * cfg.bar, a)

    # --- drums: clean BODY kick layer + chopped break on top -----------------
    drums = np.zeros(N)
    brk = np.zeros(N)
    kick_b = _kick(r_drm, sr)
    kick_times = []
    for bar in range(cfg.bars):
        ak = float(act["kick"][bar])
        if ak <= 0:
            continue
        ksteps = [0, 8] + ([6] if bar % 2 == 0 else [11])
        if r_drm.random() < 0.25:
            ksteps.append(3)
        if r_drm.random() < 0.15:                                # 32nd double-hit
            put(drums, kick_b, stime(bar, 0) - cfg.step / 2, ak * 0.5)
        for s in ksteps:
            t0 = stime(bar, s)
            put(drums, kick_b, t0, ak * r_drm.uniform(0.92, 1.0))
            kick_times.append(t0)

    # chopped break (切り刻み): intensity grows across sections, fills at
    # phrase ends. act["hats"] gates the break layer.
    r_brk = np.random.default_rng(cfg.seed + 18)
    loop = synth_break_loop(cfg, r_brk)
    for phrase in range(0, cfg.bars, 2):
        a = float(np.max(act["hats"][phrase:phrase + 2]))
        if a <= 0:
            continue
        if phrase < 16:
            inten = 0.25
        elif phrase < 40:
            inten = 0.55
        elif phrase < 64:
            inten = 0.75
        else:
            inten = 1.0
        fill = (phrase % 8) == 6                                 # bars 6-7 of each 8
        chopped = chop_break(loop, cfg, r_brk, inten, fill=fill)
        put(brk, chopped, phrase * cfg.bar, 0.78 * a)           # leave air (抜け感)
    drums = lp(drums + brk, 12000, sr, 2)

    # --- sidechain duck: soft, slow — breathing, not pumping ------------------
    duck = np.ones(N)
    dl = int(0.18 * sr)
    dip = 1 - 0.32 * np.exp(-np.arange(dl) / (0.09 * sr))
    for t0 in kick_times:
        i0 = int(t0 * sr)
        i1 = min(i0 + dl, N)
        if i1 > i0:
            duck[i0:i1] *= dip[: i1 - i0]
    pad *= 0.6 + 0.4 * duck
    air *= 0.65 + 0.35 * duck
    ep *= 0.7 + 0.3 * duck
    bass *= 0.75 + 0.25 * duck
    subb *= 0.55 + 0.45 * duck                                  # gentle breathe

    # bass BUS: only the MID layer gets drive (harmonics for small speakers);
    # the sub joins CLEAN after — saturating the sub is what crushed the lows.
    bus = np.tanh(1.4 * 0.6 * bass) / np.tanh(1.4) + 0.66 * subb

    # --- mix / master ---------------------------------------------------------
    # open, airy reverb (抜け感): longer tail, more sends, EP in the room
    send = hp(0.5 * pad + 0.9 * air + 0.6 * bell + 0.5 * plk + 0.55 * ep
              + 0.28 * brk, 300, sr, 2)
    wet = reverb(send, r_mst, sr, decay=0.85, length=2.8) * 0.33

    mix = (0.26 * pad + 0.30 * air + 0.46 * bell + 0.34 * plk + 0.36 * ep
           + 0.92 * bus + 0.95 * drums + wet)
    mix = hp(mix, 21, sr, 1)
    # split-band master: lows stay LINEAR (no crush on full-range speakers),
    # only the upper band gets a light glue drive.
    low = lp(mix, 150, sr, 2)
    mix = low + np.tanh(1.12 * (mix - low)) / np.tanh(1.12)
    fi, fo = int(1.2 * sr), int(6.0 * sr)
    mix[:fi] *= np.linspace(0, 1, fi)
    mix[-fo:] *= np.linspace(1, 0, fo)
    # loudness WITHOUT crushing: normalise to an RMS target, then round ONLY the
    # rare overshoots with a soft knee (samples < 0.70 — i.e. the entire soft
    # low-end body — pass untouched; a whole-mix saturator is what crushed v0.2).
    rms = float(np.sqrt(np.mean(mix ** 2)))
    mix *= 0.235 / max(rms, 1e-9)
    knee, ceil = 0.70, cfg.gain
    over = np.abs(mix) > knee
    mix[over] = np.sign(mix[over]) * (
        knee + (ceil - knee) * np.tanh((np.abs(mix[over]) - knee) / (ceil - knee)))
    mix = np.clip(mix, -ceil, ceil)

    # mono-safe M/S (same construction as solfeggio_composer): L+R == 2*mix
    d = int(0.008 * sr)
    side = np.concatenate([np.zeros(d), hp(mix, 1800, sr, 1)[:-d]])
    stereo = np.stack([mix + 0.16 * side, mix - 0.16 * side], axis=1)
    stereo *= cfg.gain / float(np.max(np.abs(stereo)))

    meta = cfg.as_meta()
    meta["frames"] = int(stereo.shape[0])
    return stereo, meta


# =============================================================================
# CLI
# =============================================================================
def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="namima.solfeggio_idm",
        description="Offline solfeggio IDM composer (candidate; Xtal/On mood).",
    )
    p.add_argument("--out", default="idm.wav")
    p.add_argument("--bars", type=int, default=88)
    p.add_argument("--smoke", action="store_true", help="short 16-bar render")
    p.add_argument("--bpm", type=float, default=114.0)
    p.add_argument("--seed", type=int, default=852963)
    p.add_argument("--gain", type=float, default=0.86)
    args = p.parse_args(argv)

    cfg = IdmConfig(bars=16 if args.smoke else args.bars,
                    bpm=args.bpm, seed=args.seed, gain=args.gain)
    stereo, meta = compose(cfg)
    write_wav24(args.out, stereo, cfg.sample_rate)
    print(f"wrote {args.out}  {stereo.shape[0] / cfg.sample_rate:.1f}s  "
          f"bars={cfg.bars}  bpm={cfg.bpm}  seed={cfg.seed}  "
          f"peak={float(np.max(np.abs(stereo))):.3f}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
