"""Opt-in, CPU-only DAW packet export for the existing offline IDM candidate.

No playback, devices, DAW launch, network, automatic Drive discovery or overwrite.
The existing idm_ambient CLI and default render are deliberately unchanged.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import platform
from typing import Sequence

import numpy as np
import scipy

from .generator import load_presets, write_wav24
from .idm_ambient import AmbientConfig, MODES, render_stems

PARTS = ("pad", "lead", "lead_echo", "sub", "drums", "texture", "reverb")
COEFFICIENTS = dict(zip(PARTS, (0.30, 0.55, 0.35, 0.85, 0.90, 1.0, 1.0)))
HEADROOM_PEAK = 10.0 ** (-6.0 / 20.0)
MAX_SECONDS = 180.0  # full-length archival rerender is a separate, deliberate job
SOURCE_FILES = ("idm_ambient.py", "idm_stems.py", "generator.py", "tuning.py",
                "solfeggio_composer.py", "solfeggio_idm.py", "__init__.py")


def validate_config(cfg: AmbientConfig) -> int:
    """Bound allocations before rendering; return exact frame count."""
    for name, lo, hi in (("bars", 1, 64), ("seed", 0, 2**32 - 7),
                         ("root_degree", 0, 8)):
        value = getattr(cfg, name)
        if type(value) is not int or not lo <= value <= hi:
            raise ValueError(f"{name} must be an integer in [{lo}, {hi}]")
    if type(cfg.sample_rate) is not int or cfg.sample_rate != 48000:
        raise ValueError("stem packets require 48000 Hz")
    for name, lo, hi in (("bpm", 40.0, 240.0), ("gain", 0.71, 0.95)):
        value = getattr(cfg, name)
        if type(value) not in (float, int) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{name} must be finite and in [{lo}, {hi}]")
    if cfg.mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    seconds = cfg.bars * cfg.bar + 3.0
    if not 5.0 <= seconds <= MAX_SECONDS:
        raise ValueError(f"stem packet must be 5–{MAX_SECONDS:g} seconds including tail (master fade)")
    return int(seconds * cfg.sample_rate)


def prepare_parts(stems: dict[str, np.ndarray], frames: int):
    """One attenuation for all weighted parts AND their sum; never boost."""
    if tuple(stems) != PARTS:
        raise ValueError("unexpected stem names/order")
    for name, part in stems.items():
        if part.shape != (frames,) or not np.isfinite(part).all():
            raise ValueError(f"invalid stem: {name}")
    premaster = sum(stems.values())
    peak = max(float(np.max(np.abs(part))) for part in (*stems.values(), premaster))
    common_gain = min(1.0, HEADROOM_PEAK / max(peak, 1e-12))
    return premaster, common_gain


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_new(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _handoff(cfg: AmbientConfig, frames: int, common_gain: float) -> str:
    return f"""# IDM編集パケット — Sonarへ持ち込む

これは既存offline生成器から新しく作った編集候補です。過去の納品WAVの分離・復元ではありません。
音楽的な採用・実際のSonar読込・試聴は未判定。公開用の完成品でもありません。

- {cfg.mode} / {cfg.bpm:g} BPM / 4拍子 / {cfg.bars}小節 + 3秒tail / {frames / cfg.sample_rate:.3f}秒
- 全WAV: 48 kHz / 24-bit PCM / stereo / 同一開始・同一長
- seed: {cfg.seed} / root degree: {cfg.root_degree}
- stemとpremasterの共通gain: {common_gain:.12g}。個別正規化なし。
- leadは0始まりbar 8（DAWの9小節目）、drumsはbar 12（13小節目）から。
  beatlessのdrums、短い構成の未登場partは無音で正常です。

## 最初の10分

1. 新しい空のSonarプロジェクトを48 kHz・{cfg.bpm:g} BPM・4拍子にする。
2. `01-pad.wav`〜`07-reverb.wav`を別々のステレオ音声トラックへ読み込み、
   全て先頭（小節1・拍1）に揃える。自動ストレッチや個別正規化は使わない。
3. フェーダー0 dB、pan中央、FXなしで開始。再生は人が低い音量から行う。
4. `08-premaster-reference.wav`は比較用、`09-master-reference.wav`は完成処理後の参考。
   どちらもstemと同時に鳴らさず、最初はmute。二重再生すると音量・バランスが変わる。
5. まずpadを3 dB下げ、textureをmute。drumsとsubのノリを聴いてからleadを戻す。
   この操作は提案であり、自動適用・採用済みではない。
6. 別名のprojectとして保存し、感想を記録する。元のパケットは編集しない。

## 何が編集できるか

| ファイル | 役割 | 注意 |
|---|---|---|
| 01-pad | 背景の和音 | 音数を減らす入口 |
| 02-lead | 旋律の直接音 | MIDIではなく音声 |
| 03-lead_echo | 旋律のecho | leadをmuteしても残る |
| 04-sub | 低音 | キックとの釣り合い |
| 05-drums | ビートの合成bus | kick / rim / hat / breakの個別分離ではない |
| 06-texture | hiss / crackle | 密度の引き算 |
| 07-reverb | 共有残響return | 元の複数partを含む。各partに自動追従しない |
| 08-premaster-reference | 全stemの和 | 比較用。演奏レイヤーに追加しない |
| 09-master-reference | 元のmaster処理後 | 比較用。元renderの出音を保持 |

stemの和は**master前**です。元masterは22 Hz high-pass → 150 Hz以上のnonlinear glue →
fade → RMS調整 → limiter → 1800 Hz以上のM/S stereo処理 → peak調整を使います。
stemを足すだけでは09の音になりません。stemと08はdual monoで、このstereo処理を含みません。
07の残響・03のechoは印刷済みなので、leadの音を消す場合はreturn側も確認してください。
stemは最終fade前のため、編集時の端・切替にはfade / crossfadeが必要です。loop素材ではありません。

## 再現と保存

`recipe.json`にconfig・使用preset・実行時のPython/numpy/scipy版・source hashがあります。
同じcheckoutと依存環境で、namima repo rootから（PYTHONPATH=srcを設定して）:

```text
python -m namima.idm_stems --out-dir <未使用の絶対パス> --mode {cfg.mode} --bars {cfg.bars} --bpm {cfg.bpm:g} --seed {cfg.seed} --root-degree {cfg.root_degree} --gain {cfg.gain:g}
```

これは手動実行用。sourceとpreset hashが違う場合は同一再現と扱わないでください。
CLIはcheckoutのpresets.yamlを使い、recipeを自動ロードしません。preset snapshotは検証・手動復元用です。
異なる依存環境でのbit一致、過去の納品との一致は保証しません。
絶対Hzのnon-12-TET調律なので、普通のMIDI音符へ置換しても同じ音程にはなりません。
MIDI / .cwp / iPhone圧縮版は未出力。Drive・YouTube・機材・DAWへの自動送信はありません。
`manifest.json`が最後にできたパケットのみ完了扱い。失敗時は残ったfolderを再利用せず、状態を確認してください。
"""


def export_packet(out_dir: str | Path, cfg: AmbientConfig | None = None) -> dict:
    """Create a new local directory only. Refuse overwrite, even if empty.

    Manifest is the completion marker. Failed exports are left for inspection,
    never recursively cleaned up. Paths in the packet itself are relative.
    """
    cfg = cfg or AmbientConfig(bars=16, mode="idm")
    frames = validate_config(cfg)
    requested = Path(out_dir)
    if not requested.is_absolute():
        raise ValueError("out_dir must be an explicit absolute path")
    if requested.exists() or requested.is_symlink():
        raise FileExistsError(f"output must not exist: {requested}")
    parent = requested.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ValueError("output parent must already be a directory")
    out = parent / requested.name
    source_dir = Path(__file__).resolve().parent
    preset_path = source_dir.parents[1] / "presets.yaml"
    sources = {f"src/namima/{name}": sha256(source_dir / name) for name in SOURCE_FILES}
    sources["presets.yaml"] = sha256(preset_path)
    presets = load_presets(preset_path)
    recipe = {
        "schema_version": 1, "kind": "namima_idm_stem_recipe", "config": asdict(cfg),
        "presets": presets, "source_sha256": sources,
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "scipy": scipy.__version__, "os": platform.system()},
        "reproduction": "same source, presets and environment; not a recovered historical master",
    }
    out.mkdir(exist_ok=False)  # reserve before CPU work; no parents or existing-file writes
    _json_new(out / "recipe.json", recipe)
    master, meta, stems = render_stems(cfg, presets)
    if master.shape != (frames, 2) or not np.isfinite(master).all() or np.max(np.abs(master)) > 1:
        raise ValueError("invalid master")
    premaster, common_gain = prepare_parts(stems, frames)
    assets = []

    def save(name, data, role):
        path = out / name
        if path.exists() or path.is_symlink():
            raise FileExistsError(path)
        write_wav24(path, data, cfg.sample_rate)
        assets.append({"file": name, "role": role, "sha256": sha256(path),
                       "bytes": path.stat().st_size, "frames": frames,
                       "sample_rate": cfg.sample_rate, "channels": 2, "bit_depth": 24})

    for index, (name, part) in enumerate(stems.items(), 1):
        data = np.repeat((part * common_gain)[:, None], 2, axis=1)
        save(f"{index:02d}-{name}.wav", data, "weighted_premaster_part")
    save("08-premaster-reference.wav", np.repeat((premaster * common_gain)[:, None], 2, axis=1),
         "sum_reference_do_not_layer")
    save("09-master-reference.wav", master, "master_reference_do_not_layer")
    with (out / "HANDOFF.md").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(_handoff(cfg, frames, common_gain))
    manifest = {
        "schema_version": 1, "kind": "namima_idm_stem_packet", "complete": True,
        "render": meta, "common_stem_gain": common_gain,
        "maximum_stem_and_sum_peak": HEADROOM_PEAK,
        "mix_coefficients_already_applied": COEFFICIENTS,
        "reverb_note": "already contains 0.30 wet level; shared send is printed, not independent",
        "stem_sum_stage": "before master HPF/glue/fades/normalisation/limiter/stereo widening",
        "stem_channels": "dual mono; no master stereo widening",
        "quantisation_sum_tolerance": 8 / (2**23 - 1),
        "assets": assets,
        "documents": [{"file": name, "sha256": sha256(out / name)}
                      for name in ("recipe.json", "HANDOFF.md")],
        "human_checks": {"listening": "pending", "sonar_import": "pending", "adoption": "pending"},
    }
    _json_new(out / "manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, help="new absolute local folder; parent must exist")
    parser.add_argument("--mode", choices=MODES, default="idm")
    parser.add_argument("--bars", type=int, default=16)
    parser.add_argument("--bpm", type=float, default=96.0)
    parser.add_argument("--seed", type=int, default=174852)
    parser.add_argument("--root-degree", type=int, default=0)
    parser.add_argument("--gain", type=float, default=0.86)
    args = parser.parse_args(argv)
    cfg = AmbientConfig(bars=args.bars, bpm=args.bpm, seed=args.seed, mode=args.mode,
                        root_degree=args.root_degree, gain=args.gain)
    try:
        manifest = export_packet(args.out_dir, cfg)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"stem export refused/failed: {exc}\n")
    print(f"Created {len(manifest['assets'])} WAV files; see HANDOFF.md in {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
