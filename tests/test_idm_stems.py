"""Opt-in DAW export: mix invariance, safe output, aligned 24-bit packet."""

from dataclasses import asdict, replace
import hashlib
import io
import json
from pathlib import Path
import sys
import wave

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from namima.idm_ambient import AmbientConfig, MODES, render, render_stems
from namima import idm_stems as exporter


@pytest.mark.parametrize("mode", MODES)
def test_opt_in_preserves_master_and_has_real_parts(mode):
    # 16 bars includes both lead and drums (12 bars never enters the drum part).
    cfg = AmbientConfig(bars=16, bpm=240, mode=mode, seed=23)
    master, meta, parts = render_stems(cfg)
    old_interface, old_meta = render(cfg)
    assert np.array_equal(master, old_interface)
    assert meta == old_meta
    assert tuple(parts) == exporter.PARTS
    assert all(x.shape == (meta["frames"],) and np.isfinite(x).all() for x in parts.values())
    for name in exporter.PARTS:
        assert bool(np.any(parts[name])) == (name != "drums" or mode != "beatless")
    assert not np.any(parts["lead"][:int((8 * cfg.bar - .002) * cfg.sample_rate)])
    assert not np.any(parts["drums"][:int((12 * cfg.bar - .002) * cfg.sample_rate)])
    premaster, gain = exporter.prepare_parts(parts, meta["frames"])
    assert np.array_equal(premaster, sum(parts.values()))
    assert 0 < gain <= 1
    assert np.max(np.abs(premaster * gain)) <= exporter.HEADROOM_PEAK + 1e-12
    assert not np.allclose(premaster, master.mean(axis=1))


def test_one_attenuation_preserves_balance_and_bounds_individual_parts():
    parts = {name: np.array([.01, -.01]) for name in exporter.PARTS}
    parts["pad"] = np.array([5., -5.])
    parts["lead"] = np.array([-4., 4.])  # cancellation must not hide a clipping stem
    premaster, gain = exporter.prepare_parts(parts, 2)
    assert gain == pytest.approx(exporter.HEADROOM_PEAK / 5)
    assert np.allclose(sum(p * gain for p in parts.values()), premaster * gain)
    assert all(np.max(np.abs(p * gain)) <= exporter.HEADROOM_PEAK + 1e-12 for p in parts.values())
    quiet = {name: np.array([.001, -.001]) for name in exporter.PARTS}
    assert exporter.prepare_parts(quiet, 2)[1] == 1.0


@pytest.mark.parametrize("change", [
    {"bars": 0}, {"bars": 65}, {"bars": True}, {"bars": 1.5},
    {"seed": -1}, {"seed": 2**32}, {"seed": True},
    {"root_degree": -1}, {"root_degree": 9}, {"root_degree": .5},
    {"sample_rate": 16000}, {"sample_rate": 48000.0},
    {"bpm": 0}, {"bpm": float("nan")}, {"bpm": float("inf")}, {"bpm": True},
    {"gain": .70}, {"gain": 1.0}, {"gain": float("nan")}, {"gain": False},
    {"mode": "invalid"}, {"bars": 64, "bpm": 40}, {"bars": 1, "bpm": 240},
])
def test_config_rejected_before_any_write(tmp_path, monkeypatch, change):
    monkeypatch.setattr(exporter, "render_stems", lambda *a: pytest.fail("must not render"))
    target = tmp_path / "not-created"
    with pytest.raises(ValueError):
        exporter.export_packet(target, replace(AmbientConfig(), **change))
    assert not target.exists()


def test_refuses_existing_empty_and_occupied_folder_file_and_relative(tmp_path, monkeypatch):
    monkeypatch.setattr(exporter, "render_stems", lambda *a: pytest.fail("must not render"))
    empty = tmp_path / "empty"
    empty.mkdir()
    sentinel = tmp_path / "existing.txt"
    sentinel.write_text("keep this", encoding="utf-8")
    for target in (tmp_path, empty, sentinel):
        with pytest.raises(FileExistsError):
            exporter.export_packet(target)
    with pytest.raises(ValueError, match="absolute"):
        exporter.export_packet("relative-output")
    with pytest.raises(FileNotFoundError):
        exporter.export_packet(tmp_path / "missing-parent" / "child")
    assert sentinel.read_text(encoding="utf-8") == "keep this"
    assert list(empty.iterdir()) == []


def _read24(path):
    with wave.open(str(path), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (2, 3, 48000)
        frames = wav.getnframes()
        raw = np.frombuffer(wav.readframes(frames), dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    values = raw[:, 0] | (raw[:, 1] << 8) | (raw[:, 2] << 16)
    values = (values ^ 0x800000) - 0x800000
    return values.reshape(frames, 2) / (2**23 - 1)


def test_packet_roundtrip_completion_provenance_and_reproducibility(tmp_path, monkeypatch):
    # Small synthetic parts keep I/O tests cheap. Real DSP is covered above.
    cfg = AmbientConfig(bars=2, bpm=240)
    frames = exporter.validate_config(cfg)
    t = np.arange(frames) / cfg.sample_rate
    parts = {name: .1 * np.sin(2 * np.pi * (n + 1) * 110 * t)
             for n, name in enumerate(exporter.PARTS)}
    master = np.repeat((.2 * np.sin(2 * np.pi * 440 * t))[:, None], 2, axis=1)
    meta = {**cfg.as_meta(), "frames": frames}
    monkeypatch.setattr(exporter, "render_stems", lambda *args: (master, meta, parts))
    target = tmp_path / "packet"
    manifest = exporter.export_packet(target, cfg)
    assert manifest == json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["complete"] is True
    assert len(manifest["assets"]) == 9
    assert len(list(target.iterdir())) == 12
    outputs = []
    for asset in manifest["assets"]:
        path = target / asset["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
        assert path.stat().st_size == asset["bytes"]
        data = _read24(path)
        assert data.shape == (frames, 2)
        outputs.append(data)
    assert all(np.array_equal(data[:, 0], data[:, 1]) for data in outputs[:8])
    assert np.max(np.abs(sum(outputs[:7]) - outputs[7])) < manifest["quantisation_sum_tolerance"]
    assert np.max(np.abs(outputs[8] - master)) <= .5 / (2**23 - 1) + 1e-12
    for output, part in zip(outputs[:7], parts.values()):
        assert np.max(np.abs(output[:, 0] - part * manifest["common_stem_gain"])) <= .5 / (2**23 - 1) + 1e-12
    recipe = json.loads((target / "recipe.json").read_text(encoding="utf-8"))
    assert recipe["config"] == asdict(cfg)
    assert "presets.yaml" in recipe["source_sha256"]
    assert recipe["presets"]["frequencies"]["solfeggio_528"] == 528
    assert set(recipe["environment"]) == {"python", "numpy", "scipy", "os"}
    for doc in manifest["documents"]:
        assert exporter.sha256(target / doc["file"]) == doc["sha256"]
    handoff = (target / "HANDOFF.md").read_text(encoding="utf-8")
    assert "--gain 0.86" in handoff and "二重再生" in handoff and "MIDI / .cwp" in handoff
    again = exporter.export_packet(tmp_path / "again", cfg)
    assert again == manifest  # no hidden timestamp, hostname or absolute path


def test_handoff_command_reproduces_config_exactly(tmp_path, monkeypatch):
    # :g-style rounding (6 significant digits) would silently change the render.
    cfg = AmbientConfig(bars=16, bpm=133.33333, gain=0.8612345, mode="beatless",
                        seed=7, root_degree=3)
    handoff = exporter._handoff(cfg, exporter.validate_config(cfg), .5)
    assert "133.33333 BPM" in handoff
    command = [line for line in handoff.splitlines() if line.startswith("python -m namima.idm_stems ")]
    assert len(command) == 1
    argv = command[0].split()[3:]
    options = dict(zip(argv[::2], argv[1::2]))
    assert float(options["--bpm"]) == cfg.bpm and float(options["--gain"]) == cfg.gain
    assert int(options["--bars"]) == cfg.bars and int(options["--seed"]) == cfg.seed
    # The CLI must rebuild exactly the same config from that command line.
    seen = []
    monkeypatch.setattr(exporter, "export_packet", lambda out, c: seen.append(c) or {"assets": []})
    argv[argv.index("--out-dir") + 1] = str(tmp_path / "again")
    assert exporter.main(argv) == 0
    assert seen == [cfg]


def test_cli_report_survives_narrow_console_after_export(tmp_path, monkeypatch):
    buffer = io.BytesIO()
    console = io.TextIOWrapper(buffer, encoding="cp932")  # strict, like redirected Japanese Windows
    monkeypatch.setattr(sys, "stdout", console)
    monkeypatch.setattr(exporter, "export_packet", lambda out, cfg: {"assets": [None] * 9})
    assert exporter.main(["--out-dir", str(tmp_path / "café")]) == 0
    console.flush()
    assert r"caf\xe9" in buffer.getvalue().decode("cp932")  # escaped, not a crash


def test_failure_keeps_recipe_but_never_marks_complete(tmp_path, monkeypatch):
    def fail(*args):
        raise ValueError("simulated DSP failure")
    monkeypatch.setattr(exporter, "render_stems", fail)
    target = tmp_path / "incomplete"
    with pytest.raises(ValueError, match="simulated"):
        exporter.export_packet(target)
    assert (target / "recipe.json").is_file()
    assert not (target / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        exporter.export_packet(target)


@pytest.mark.parametrize("problem", ("missing", "order", "shape", "nan"))
def test_rejects_bad_parts(problem):
    parts = {name: np.zeros(8) for name in exporter.PARTS}
    if problem == "missing":
        parts.pop("pad")
    elif problem == "order":
        parts = dict(reversed(list(parts.items())))
    elif problem == "shape":
        parts["pad"] = np.zeros((8, 2))
    else:
        parts["pad"][0] = np.nan
    with pytest.raises(ValueError):
        exporter.prepare_parts(parts, 8)
