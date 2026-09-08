"""Cheap fixture-based comparisons; no DAW, ffmpeg execution, or real playback."""
import json
from pathlib import Path
import sys
import wave

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from namima import idm_stems as exporter
from namima import stem_compare as compare
from namima.idm_ambient import AmbientConfig


def short_plan():
    return {**compare.default_plan(), "excerpt_start_s": 1.0, "excerpt_duration_s": 2.0}


@pytest.fixture
def packet(tmp_path, monkeypatch):
    cfg = AmbientConfig(bars=2, bpm=240)
    frames = exporter.validate_config(cfg)
    t = np.arange(frames) / compare.SR
    parts = {name: .1 * np.sin(2 * np.pi * (i + 1) * 110 * t)
             for i, name in enumerate(compare.PARTS)}
    master = np.repeat((sum(parts.values()) * .5)[:, None], 2, axis=1)
    monkeypatch.setattr(exporter, "render_stems", lambda *a: (master, {**cfg.as_meta(), "frames": frames}, parts))
    target = tmp_path / "source"
    exporter.export_packet(target, cfg)
    return target


def test_default_plan_deltas_preserve_beat_and_pitches():
    variants = compare.default_plan()["variants"]
    changed = [{key for key in compare.PARTS if a["gains_db"][key] != b["gains_db"][key]}
               for a, b in zip(variants, variants[1:])]
    assert changed == [{"pad"}, {"lead_echo", "reverb"}, {"texture"}]
    assert all(v["gains_db"]["drums"] == v["gains_db"]["sub"] == v["gains_db"]["lead"] == 0 for v in variants)


@pytest.mark.parametrize("case", ["nan", "negative", "too_long", "few", "many", "path", "duplicate", "boost", "bool", "missing_part", "label", "muted", "unknown_field", "unknown_variant", "bool_version"])
def test_bad_plan_refused_before_output(packet, tmp_path, case):
    plan = short_plan()
    if case == "nan": plan["gap_s"] = float("nan")
    if case == "negative": plan["excerpt_start_s"] = -1
    if case == "too_long": plan["excerpt_duration_s"] = 60
    if case == "few": plan["variants"] = plan["variants"][:1]
    if case == "many": plan["variants"] *= 2
    if case == "path": plan["variants"][0]["id"] = "../overwrite"
    if case == "duplicate": plan["variants"][1]["id"] = plan["variants"][0]["id"]
    if case == "boost": plan["variants"][0]["gains_db"]["pad"] = 1
    if case == "bool": plan["variants"][0]["gains_db"]["pad"] = False
    if case == "missing_part": plan["variants"][0]["gains_db"].pop("pad")
    if case == "label": plan["variants"][0]["label"] = "[bad](url)"
    if case == "muted": plan["variants"][0]["gains_db"] = dict.fromkeys(compare.PARTS)
    if case == "unknown_field": plan["filter"] = 300
    if case == "unknown_variant": plan["variants"][0]["swing"] = .8
    if case == "bool_version": plan["schema_version"] = True
    target = tmp_path / "not-created"
    with pytest.raises(ValueError):
        compare.export_comparison(packet, target, plan)
    assert not target.exists()


@pytest.mark.parametrize("case", ["incomplete", "outside", "size", "hash", "format", "frames", "document"])
def test_tampered_source_refused(packet, tmp_path, case):
    path = packet / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if case == "incomplete": manifest["complete"] = False
    if case == "outside": manifest["assets"][0]["file"] = "../secret.wav"
    if case == "size": manifest["assets"][0]["bytes"] += 1
    if case == "hash": manifest["assets"][0]["sha256"] = "0" * 64
    if case == "format": manifest["assets"][0]["sample_rate"] = 44100
    if case == "frames": manifest["render"]["frames"] = compare.MAX_FRAMES + 1
    if case == "document": manifest["documents"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        compare.export_comparison(packet, tmp_path / "not-created", short_plan())
    assert not (tmp_path / "not-created").exists()


def test_levels_determinism_nonmutation_and_roundtrip(packet, tmp_path):
    before = {p.name: compare.sha256(p) for p in packet.iterdir()}
    parts, _ = compare.load_packet(packet)
    snapshots = {name: x.copy() for name, x in parts.items()}
    audio, gains = compare.mixes(parts, short_plan())
    again, gains2 = compare.mixes(parts, short_plan())
    assert gains == gains2 and all(0 < g <= 1 for g in gains)
    assert all(np.array_equal(a, b) for a, b in zip(audio, again))
    assert all(np.array_equal(parts[n], snapshots[n]) for n in parts)
    levels = [np.sqrt(np.mean(a[compare.SR:3 * compare.SR] ** 2)) for a in audio]
    assert max(levels) - min(levels) < 1e-12
    assert all(np.isfinite(a).all() and np.max(np.abs(a)) <= 10**(-3/20) + 1e-12 for a in audio)
    assert all(not np.array_equal(a, b) for a, b in zip(audio, audio[1:]))
    out = tmp_path / "comparison"
    result = compare.export_comparison(packet, out, short_plan())
    assert result["complete"] and result["ffmpeg"] is None
    assert result["human_checks"]["adoption"] == "pending"
    assert result["source_manifest_sha256"] == before["manifest.json"]
    assert result["cues"][-1]["end_s"] == 10.25  # 4*2 + 3*.75, no trailing gap
    assert len(result["assets"]) == 5
    for asset in result["assets"]:
        assert compare.sha256(out / asset["file"]) == asset["sha256"]
        with wave.open(str(out / asset["file"]), "rb") as wav:
            assert (wav.getframerate(), wav.getsampwidth(), wav.getnchannels(), wav.getnframes()) == (48000, 3, 2, asset["frames"])
    assert {p.name: compare.sha256(p) for p in packet.iterdir()} == before
    for name, digest in result["documents"].items():
        assert compare.sha256(out / name) == digest
    assert "M4A" not in (out / "LISTENING-NOTES.md").read_text(encoding="utf-8").split("## Sonar")[0]
    assert compare.export_comparison(packet, tmp_path / "again", short_plan()) == result


def test_existing_path_and_missing_ffmpeg_leave_no_output(packet, tmp_path, monkeypatch):
    target = tmp_path / "occupied"
    target.mkdir()
    with pytest.raises(FileExistsError):
        compare.export_comparison(packet, target, short_plan())
    with pytest.raises(ValueError):
        compare.export_comparison(packet, Path("relative"), short_plan())
    with pytest.raises(ValueError):
        compare.export_comparison(packet, tmp_path / "new", short_plan(), tmp_path / "missing-ffmpeg")
    assert not (tmp_path / "new").exists()
    assert list(target.iterdir()) == []


def test_encoder_failure_never_marks_complete(packet, tmp_path, monkeypatch):
    fake = tmp_path / "test-encoder.exe"
    fake.write_bytes(b"test fixture; never executable")
    def run(args, **kwargs):
        if "-version" in args:
            return compare.subprocess.CompletedProcess(args, 0, stdout="ffmpeg fixture\n")
        assert "-n" in args and "-y" not in args and "-nostdin" in args
        raise compare.subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(compare.subprocess, "run", run)
    target = tmp_path / "failed"
    with pytest.raises(compare.subprocess.CalledProcessError):
        compare.export_comparison(packet, target, short_plan(), fake)
    assert (target / "plan.json").exists()
    assert not (target / "comparison.json").exists()


def test_bad_input_shape_and_nonfinite():
    frames = 5 * compare.SR
    parts = {name: np.ones(frames) for name in compare.PARTS}
    parts["pad"][0] = np.nan
    with pytest.raises(ValueError): compare.mixes(parts, short_plan())
    parts["pad"] = np.zeros((frames, 2))
    with pytest.raises(ValueError): compare.mixes(parts, short_plan())
