"""Smoke tests for the delivery lane (no ffmpeg needed)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.deliver import (  # noqa: E402
    resolve_handoff_dir, find_ffmpeg, handoff_md, write_packet, sha256,
)
from namima.idm_ambient import AmbientConfig, render  # noqa: E402


def test_resolve_handoff_env_and_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("NAMIMA_HANDOFF_DIR", str(tmp_path / "env"))
    p, src = resolve_handoff_dir(None)
    assert p == tmp_path / "env" and src.startswith("env:")
    p, src = resolve_handoff_dir(str(tmp_path / "flag"))
    assert p == tmp_path / "flag" and src == "flag"


def test_resolve_handoff_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("NAMIMA_HANDOFF_DIR", raising=False)
    monkeypatch.setattr("namima.deliver.handoff_candidates", lambda: [tmp_path / "nope"])
    p, src = resolve_handoff_dir(None, fallback=tmp_path / "deliveries")
    assert p == tmp_path / "deliveries" and src.startswith("fallback")


def test_find_ffmpeg_shape():
    ff, src = find_ffmpeg()
    assert src in ("env:NAMIMA_FFMPEG", "PATH", "imageio_ffmpeg", "none")
    assert (ff is None) == (src == "none")


def test_packet_without_ffmpeg(tmp_path):
    stereo, meta = render(AmbientConfig(bars=4, mode="soft"))
    hd = tmp_path / "drive"
    pk = write_packet(stereo, meta, "unit-test-s1-4bars", tmp_path / "out", hd, ff=None,
                      recipe_cmd="python scripts/deliver.py long --bars 4", deliver_master=True)
    assert pk["wav"].exists() and pk["handoff"].exists() and pk["m4a"] is None
    md = pk["handoff"].read_text(encoding="utf-8")
    assert sha256(pk["wav"]) in md and "unit-test-s1-4bars" in md and "Re-render" in md
    names = sorted(p.name for p in hd.iterdir())
    assert names == ["unit-test-s1-4bars-handoff.md", "unit-test-s1-4bars-master.wav"]


def test_handoff_md_structure_lines():
    meta = {"bpm": 96.0, "bars": 144, "seed": 1, "mode": "idm", "version": "x", "root_degree": 0,
            "pitch_system": "p", "sample_rate": 48000,
            "structure": {"lead": 8, "drums": 12, "breakdowns": [[24, 28], [56, 60]], "outro": 136}}
    md = handoff_md("b", meta, {}, "cmd")
    assert "1:00–1:10: breakdown" in md and "5:40–6:00: outro" in md and "0:20: lead motif" in md
