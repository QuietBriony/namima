"""texture_lane/make_packet.py --deliver: the master wav stays local unless --deliver-master (no ffmpeg needed)."""

from __future__ import annotations

import importlib.util
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("make_packet", ROOT / "scripts" / "texture_lane" / "make_packet.py")
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)


def _inputs(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "bedded-48k24.wav"
    with wave.open(str(src), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(48000)
        w.writeframes(b"\x00" * 6 * 4800)
    notes = tmp_path / "notes.md"
    notes.write_text("## Notes\n\n- unit test\n", encoding="utf-8")
    return src, notes


def _run(tmp_path, monkeypatch, packet: str, *extra: str) -> tuple[Path, Path]:
    monkeypatch.setattr(mp, "find_ffmpeg", lambda: (None, "none"))
    src, notes = _inputs(tmp_path)
    work, drive = tmp_path / "work", tmp_path / "drive"
    assert mp.main([str(src), packet, "unit-base", str(notes), "--out", str(work),
                    "--handoff-dir", str(drive), *extra]) == 0
    return work / packet, drive / "deliveries" / packet


def test_deliver_keeps_master_local_by_default(tmp_path, monkeypatch):
    local, dest = _run(tmp_path, monkeypatch, "2026-01-01_unit", "--deliver")
    master = local / "unit-base-master.wav"
    assert master.exists()
    assert sorted(p.name for p in dest.iterdir()) == ["unit-base-handoff.md"]
    md = (dest / "unit-base-handoff.md").read_text(encoding="utf-8")
    assert mp.sha256(master) in md and "Not copied to Drive" in md and "- unit test" in md


def test_deliver_master_is_opt_in(tmp_path, monkeypatch):
    _, dest = _run(tmp_path, monkeypatch, "2026-01-02_unit", "--deliver", "--deliver-master")
    assert sorted(p.name for p in dest.iterdir()) == ["unit-base-handoff.md", "unit-base-master.wav"]
    assert "Not copied to Drive" not in (dest / "unit-base-handoff.md").read_text(encoding="utf-8")


def test_no_deliver_touches_no_drive(tmp_path, monkeypatch):
    local, dest = _run(tmp_path, monkeypatch, "2026-01-03_unit")
    assert (local / "unit-base-master.wav").exists() and not dest.exists()


def test_deliver_master_needs_deliver(tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        _run(tmp_path, monkeypatch, "2026-01-04_unit", "--deliver-master")
