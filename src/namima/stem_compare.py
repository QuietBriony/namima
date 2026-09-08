"""Compare subtractive mixes of an existing IDM stem packet, without resynthesis.

Explicit local input/output only. No playback, DAW, device or cloud operations.
Optional M4A encoding uses an explicitly provided, already installed ffmpeg.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import wave

import numpy as np
import scipy

from .generator import write_wav24
from .idm_stems import PARTS, sha256, _json_new
from .solfeggio_composer import hp

SR = 48000
MAX_FRAMES = SR * 180
FILES = tuple(f"{i:02d}-{part}.wav" for i, part in enumerate(PARTS, 1)) + (
    "08-premaster-reference.wav", "09-master-reference.wav")


def default_plan() -> dict:
    a = dict.fromkeys(PARTS, 0.0)
    b = {**a, "pad": -6.0}
    c = {**b, "lead_echo": -6.0, "reverb": -6.0}
    d = {**c, "texture": None}
    return {"schema_version": 1, "excerpt_start_s": 30.0, "excerpt_duration_s": 10.0,
            "gap_s": 0.75, "variants": [
                {"id": "A-reference", "label": "基準", "gains_db": a},
                {"id": "B-less-pad", "label": "背景の直接音を減らす", "gains_db": b},
                {"id": "C-less-returns", "label": "さらにechoと共有残響を減らす", "gains_db": c},
                {"id": "D-no-texture", "label": "さらにhiss / crackleを外す", "gains_db": d},
            ]}


def read_json(path: Path) -> dict:
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("JSON exceeds 1 MiB")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def load_packet(packet: Path):
    """Verify fixed local filenames, bounds, hashes and PCM before any write."""
    if not packet.is_absolute():
        raise ValueError("packet must be an absolute path")
    packet = packet.resolve(strict=True)
    manifest = read_json(packet / "manifest.json")
    if (manifest.get("schema_version") != 1 or manifest.get("kind") != "namima_idm_stem_packet"
            or manifest.get("complete") is not True):
        raise ValueError("not a completed IDM stem packet")
    frames = manifest.get("render", {}).get("frames")
    if type(frames) is not int or not 5 * SR <= frames <= MAX_FRAMES:
        raise ValueError("invalid/beyond-limit frame count")
    if any(manifest["render"].get(k) != v for k, v in (("sample_rate", SR), ("channels", 2), ("bit_depth", 24))):
        raise ValueError("invalid packet format metadata")
    assets = manifest.get("assets", [])
    if len(assets) != len(FILES) or [a.get("file") for a in assets] != list(FILES):
        raise ValueError("unexpected packet filenames or order")
    stems = {}
    for index, asset in enumerate(assets):
        path = packet / FILES[index]  # never follow a supplied relative path
        if any(asset.get(k) != v for k, v in (("sample_rate", SR), ("channels", 2), ("bit_depth", 24), ("frames", frames))):
            raise ValueError("inconsistent asset format metadata")
        if path.is_symlink() or path.resolve().parent != packet:
            raise ValueError("linked/outside packet asset")
        if path.stat().st_size != frames * 6 + 44 or asset.get("bytes") != path.stat().st_size:
            raise ValueError(f"size/hash mismatch: {path.name}")
        with path.open("rb") as handle:
            payload = handle.read(frames * 6 + 45)
        if len(payload) != frames * 6 + 44 or hashlib.sha256(payload).hexdigest() != asset.get("sha256"):
            raise ValueError(f"size/hash mismatch: {path.name}")
        # Decode the exact bounded bytes just hashed, not a second file read.
        with wave.open(io.BytesIO(payload), "rb") as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes(),
                    wav.getcomptype()) != (SR, 2, 3, frames, "NONE"):
                raise ValueError(f"unsupported PCM: {path.name}")
            if index < len(PARTS):
                raw = np.frombuffer(wav.readframes(frames), dtype=np.uint8).reshape(-1, 3).astype(np.int32)
                ints = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
                ints = ((ints ^ 0x800000) - 0x800000).reshape(-1, 2)
                if not np.array_equal(ints[:, 0], ints[:, 1]):
                    raise ValueError("expected dual-mono premaster parts")
                stems[PARTS[index]] = ints[:, 0] / (2**23 - 1)
    documents = manifest.get("documents", [])
    if [d.get("file") for d in documents] != ["recipe.json", "HANDOFF.md"]:
        raise ValueError("unexpected packet documents")
    for doc in documents:
        path = packet / doc["file"]
        if path.is_symlink() or path.resolve().parent != packet or path.stat().st_size > 1024 * 1024:
            raise ValueError("invalid packet document")
        if sha256(path) != doc.get("sha256"):
            raise ValueError("packet document hash mismatch")
    return stems, manifest


def validate_plan(plan: dict, frames: int) -> tuple[int, int]:
    if (set(plan) != {"schema_version", "excerpt_start_s", "excerpt_duration_s", "gap_s", "variants"}
            or type(plan.get("schema_version")) is not int or plan["schema_version"] != 1):
        raise ValueError("unsupported plan")
    for key, lo, hi in (("excerpt_start_s", 0, 180), ("excerpt_duration_s", 2, 60), ("gap_s", .25, 3)):
        value = plan.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"invalid {key}")
    start = round(plan["excerpt_start_s"] * SR)
    end = start + round(plan["excerpt_duration_s"] * SR)
    if end > frames:
        raise ValueError("excerpt extends beyond source")
    variants = plan.get("variants")
    if not isinstance(variants, list) or not 2 <= len(variants) <= 6:
        raise ValueError("plan requires 2–6 variants")
    seen = set()
    for v in variants:
        if not isinstance(v, dict) or set(v) != {"id", "label", "gains_db"}:
            raise ValueError("unexpected variant fields")
        name, label, gains = v.get("id"), v.get("label"), v.get("gains_db")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,39}", name) or name in seen:
            raise ValueError("invalid/duplicate variant id")
        seen.add(name)
        if not isinstance(label, str) or not 1 <= len(label) <= 100 or any(c in label for c in "\n\r|[]<>"):
            raise ValueError("invalid label")
        if not isinstance(gains, dict) or set(gains) != set(PARTS):
            raise ValueError("plan must specify every part")
        for value in gains.values():
            if value is not None and (type(value) not in (float, int) or not math.isfinite(value) or not -60 <= value <= 0):
                raise ValueError("part gain must be -60..0 dB, or null for mute")
    return start, end


def mixes(stems: dict, plan: dict):
    frames = len(stems["pad"])
    if not 5 * SR <= frames <= MAX_FRAMES:
        raise ValueError("invalid mix duration")
    if set(stems) != set(PARTS) or any(p.shape != (frames,) or not np.isfinite(p).all() for p in stems.values()):
        raise ValueError("invalid parts")
    start, end = validate_plan(plan, frames)
    outputs, levels = [], []
    fade = np.ones(frames)
    fade[:int(1.5 * SR)] *= np.linspace(0, 1, int(1.5 * SR))
    fade[-5 * SR:] *= np.linspace(1, 0, 5 * SR)
    for variant in plan["variants"]:
        gains = variant["gains_db"]
        mix = sum(stems[name] * (0 if gains[name] is None else 10**(gains[name] / 20)) for name in PARTS)
        mix = hp(mix, 22, SR, 1) * fade
        level = float(np.sqrt(np.mean(mix[start:end] ** 2)))
        if level < 1e-8:
            raise ValueError("silent comparison window")
        outputs.append(mix)
        levels.append(level)
    # Match DOWN to the quietest excerpt. Then one common attenuation for all
    # full mixes. No limiter, per-track normalisation, or nonlinear master.
    match_gains = [min(levels) / level for level in levels]
    peak = max(float(np.max(np.abs(x))) * g for x, g in zip(outputs, match_gains))
    common = min(1.0, 10**(-3 / 20) / max(peak, 1e-12))
    return [x * g * common for x, g in zip(outputs, match_gains)], [g * common for g in match_gains]


def export_comparison(packet: Path, out: Path, plan: dict, ffmpeg: Path | None = None) -> dict:
    if not out.is_absolute() or not out.parent.is_dir():
        raise ValueError("out must be absolute with an existing parent")
    if out.exists() or out.is_symlink():
        raise FileExistsError(out)
    stems, source = load_packet(packet)
    start, end = validate_plan(plan, len(stems["pad"]))
    audio, gains = mixes(stems, plan)
    ff_info = None
    if ffmpeg is not None:
        if not ffmpeg.is_absolute() or not ffmpeg.is_file():
            raise ValueError("ffmpeg must be an explicit installed executable path")
        version = subprocess.run([str(ffmpeg), "-version"], capture_output=True, text=True,
                                 timeout=15, check=True).stdout.splitlines()[0]
        ff_info = {"version": version, "sha256": sha256(ffmpeg)}
    source_hash = sha256(packet / "manifest.json")
    out.mkdir(exist_ok=False)
    _json_new(out / "plan.json", plan)
    assets, cues, segments = [], [], []
    gap = np.zeros(round(plan["gap_s"] * SR))

    def save(name, mono):
        path = out / name
        if path.exists():
            raise FileExistsError(path)
        write_wav24(path, np.repeat(mono[:, None], 2, axis=1), SR)
        assets.append({"file": name, "sha256": sha256(path), "frames": len(mono),
                       "peak": float(np.max(np.abs(mono)))})

    cursor = 0
    for i, (variant, mix, gain) in enumerate(zip(plan["variants"], audio, gains)):
        save(variant["id"] + ".wav", mix)
        clip = mix[start:end].copy()
        nfade = int(.08 * SR)
        clip[:nfade] *= np.linspace(0, 1, nfade)
        clip[-nfade:] *= np.linspace(1, 0, nfade)
        cues.append({"id": variant["id"], "start_s": cursor / SR,
                     "end_s": (cursor + len(clip)) / SR, "level_match_gain": gain,
                     "window_rms_before_edge_fades": float(np.sqrt(np.mean(mix[start:end] ** 2)))})
        segments.append(clip)
        cursor += len(clip)
        if i < len(audio) - 1:
            segments.append(gap)
            cursor += len(gap)
    save("comparison-reel.wav", np.concatenate(segments))
    if ffmpeg is not None:
        m4a = out / "comparison-reel.m4a"
        subprocess.run([str(ffmpeg), "-nostdin", "-n", "-hide_banner", "-loglevel", "error",
                        "-i", str(out / "comparison-reel.wav"), "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(m4a)], check=True, timeout=120)
        assets.append({"file": m4a.name, "sha256": sha256(m4a), "codec": "AAC 192k"})
    lines = ["# 引き算で磨く — 比較ノート", "", "## まず聴く", "",
             "[比較リール（WAV）](comparison-reel.wav)" + (" ／ [M4A](comparison-reel.m4a)" if ffmpeg else ""),
             f"元の同じ {plan['excerpt_start_s']:g}〜{plan['excerpt_start_s'] + plan['excerpt_duration_s']:g}秒を比較。",
             "基準Aもstemから作った素直なmixで、元の完成masterとは別です。採用・聴感・実Sonarは未判定。", "",
             "| 開始〜終了（秒） | 版 | フル版 |", "|---|---|---|"]
    for variant, cue in zip(plan["variants"], cues):
        lines.append(f"| {cue['start_s']:.2f}〜{cue['end_s']:.2f} | {variant['label']} | [{variant['id']}]({variant['id']}.wav) |")
    lines += ["", "## Sonarで同じ引き算をする", "", "元の7stemを先頭から別トラックへ。同じ出力busへ送り、faderを次のdB値へ。",
              "muteは消音。echoと共有reverbは印刷済みで、直接音のfaderに自動追従しません。", "",
              "| part | " + " | ".join(v["id"] for v in plan["variants"]) + " |",
              "|---|" + "---|" * len(plan["variants"])]
    for part in PARTS:
        lines.append("| " + part + " | " + " | ".join("mute" if v["gains_db"][part] is None else f"{v['gains_db'][part]:g}"
                                                      for v in plan["variants"]) + " |")
    lines += ["", "共通処理: 22 Hz HPF（1次）→1.5秒fade-in / 5秒fade-out→比較用gain。",
              "元masterのglue・limiter・stereo拡張は使いません。全版dual monoです。",
              "同じ区間の平均レベル（RMS）を最も静かな版へ減衰で揃え、全体に共通のpeak余裕を確保。",
              "これはLUFS / true-peak測定や聴感音量の完全一致ではありません。リール端に80ms fadeを加えています。",
              "細かなgainはcomparison.jsonのcues参照。全版を重ねて再生せず、一つずつ比較します。", "",
              "## 判断を一言で残す", "", "例: Bの余白は好き／Cは乾きすぎ／Dはノリが残る。どれも嫌、でも構いません。",
              "今回ビートのpatternや音程は不変。ノレなさが全版共通なら次はfaderでなくpatternを変えます。", "",
              "## 再現", "", "同じ元packetとplan.jsonを指定して、未使用の絶対出力先へ再実行します。",
              "`python -m namima.stem_compare --packet <元packetの絶対パス> --plan <このplan.jsonの絶対パス> --out-dir <未使用の絶対パス>`",
              "元packetのhash・input recipe・比較toolのhashと実行版はcomparison.jsonに記録。元file・判定・公開状態は変更しません。",
              "任意の --ffmpeg <既存実行ファイルの絶対パス> でM4Aも作成。自動install・再生・uploadはしません。", ""]
    with (out / "LISTENING-NOTES.md").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))
    here = Path(__file__).parent
    manifest = {"schema_version": 1, "kind": "namima_stem_comparison", "complete": True,
                "source_packet": str(packet.resolve()), "source_manifest_sha256": source_hash,
                "source_assets": source["assets"], "source_documents": source["documents"],
                "tool_sha256": {name: sha256(here / name) for name in
                                ("stem_compare.py", "idm_stems.py", "generator.py", "solfeggio_composer.py")},
                "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
                "ffmpeg": ff_info, "cues": cues, "assets": assets,
                "documents": {name: sha256(out / name) for name in ("plan.json", "LISTENING-NOTES.md")},
                "processing": "22Hz HPF; 1.5/5s fades; downward excerpt RMS matching; common -3dBFS sample-peak ceiling",
                "human_checks": {"listening": "pending", "sonar_import": "pending", "adoption": "pending"}}
    _json_new(out / "comparison.json", manifest)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--ffmpeg", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = read_json(args.plan) if args.plan else default_plan()
        result = export_comparison(args.packet, args.out_dir, plan, args.ffmpeg)
    except (ValueError, OSError, KeyError, TypeError, AttributeError, wave.Error, subprocess.SubprocessError) as exc:
        parser.exit(2, f"comparison refused/failed: {exc}\n")
    print(f"Created {len(result['assets'])} audio files in {args.out_dir}; no playback or upload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
