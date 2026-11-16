"""catalog_deliveries: packets split into subfolders (01_音源 / 02_編集用 / 03_検証・引継ぎ)."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("catalog_deliveries", ROOT / "scripts" / "catalog_deliveries.py")
cd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cd)


def _wav(path: Path, seconds: float, sr: int = 8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(seconds * sr))


def _file(path: Path, data: bytes = b"x" * 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _packet(dir_: str, listen_first: str, duration: str = "") -> dict:
    return {"dir": dir_, "family": "A", "title": dir_, "producer": "p", "engine": "e", "genre": "g",
            "bpm": "", "key": "", "duration": duration, "listen_first": listen_first, "intended": "",
            "checkpoints": [], "verdict": None, "verdict_date": None}


def _build(tmp_path: Path) -> tuple[Path, Path]:
    hd = tmp_path / "Music"
    dl = hd / "deliveries"
    cat = {"updated": "2026-01-01", "families": [{"id": "A", "title": "fam A"}],
           "packets": [_packet("2026-01-01_flat", "flat-iphone.m4a"),
                       _packet("2026-01-02_split", "split-iphone.m4a", duration="0:43"),
                       _packet("2026-01-03_sub-master", "sm-iphone.m4a"),
                       _packet("2026-01-04_gone", "gone-iphone.m4a")]}
    cat_path = dl / cd.CATALOG_SUBDIR / "catalog.json"
    cat_path.parent.mkdir(parents=True)
    cat_path.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # flat (pre-10/02 layout): everything directly in the packet
    flat = dl / "2026-01-01_flat"
    _file(flat / "flat-iphone.m4a")
    _file(flat / "flat-handoff.md")
    _wav(flat / "flat-master.wav", 3)
    # split (10/02 layout) inside a group folder; master already moved off Drive
    split = dl / "Group" / "2026-01-02_split"
    _file(split / "01_音源" / "split-iphone.m4a", b"m" * 100)
    _wav(split / "01_音源" / "loop-drums.wav", 7)          # a stem, not the track
    _file(split / "02_編集用" / "edit.zip", b"z" * 50)
    _file(split / "03_検証・引継ぎ" / "split-handoff.md")
    _file(split / "01_音源" / "a" / "b" / "too-deep.txt")   # 3 folder levels down: out of bounds
    # split with the master still inside 01_音源/
    sm = dl / "2026-01-03_sub-master"
    _file(sm / "01_音源" / "sm-iphone.m4a")
    _wav(sm / "01_音源" / "sm-master.wav", 5)
    _wav(sm / "01_音源" / "sm-stem.wav", 9)
    # unregistered folder with a version subfolder
    _file(dl / "Loose" / "top.mp3")
    _file(dl / "Loose" / "v2" / "next.mp3")
    return hd, cat_path


def _rows(tmp_path: Path) -> dict[str, dict]:
    hd, cat_path = _build(tmp_path)
    rows = cd.scan(hd / "deliveries", json.loads(cat_path.read_text(encoding="utf-8")))
    return {r["dir"]: r for r in rows}


def test_packet_files_bounded_and_ordered(tmp_path):
    hd, _ = _build(tmp_path)
    split = hd / "deliveries" / "Group" / "2026-01-02_split"
    rel = [f.relative_to(split).as_posix() for f in cd.packet_files(split)]
    assert rel == ["01_音源/loop-drums.wav", "01_音源/split-iphone.m4a", "02_編集用/edit.zip",
                   "03_検証・引継ぎ/split-handoff.md"]
    assert "01_音源/a/b/too-deep.txt" in [f.relative_to(split).as_posix()
                                          for f in cd.packet_files(split, max_depth=3)]
    flat = hd / "deliveries" / "2026-01-01_flat"
    assert [f.name for f in cd.packet_files(flat)] == ["flat-handoff.md", "flat-iphone.m4a", "flat-master.wav"]


def test_scan_finds_files_in_packet_subfolders(tmp_path):
    rows = _rows(tmp_path)
    s = rows["2026-01-02_split"]
    assert s["exists"] and s["location"] == "Group/2026-01-02_split"
    assert s["n_files"] == 4 and s["has_handoff"]
    assert s["listen_first_exists"] and s["listen_first_location"] == "01_音源/split-iphone.m4a"
    assert s["wav_duration"] == ""            # the 7 s stem must not replace the curated 0:43
    f = rows["2026-01-01_flat"]
    assert f["n_files"] == 3 and f["wav_duration"] == "0:03"
    assert f["listen_first_exists"] and f["listen_first_location"] == "flat-iphone.m4a"
    sm = rows["2026-01-03_sub-master"]
    assert sm["wav_duration"] == "0:05"       # master in 01_音源/ counts, the longer stem does not
    g = rows["2026-01-04_gone"]
    assert not g["exists"] and not g["listen_first_exists"] and g["n_files"] == 0
    loose = rows["Loose"]
    assert loose["family"] == "?" and loose["n_files"] == 2
    assert "Group" not in rows and cd.CATALOG_SUBDIR not in rows


def test_render_md_points_into_subfolder(tmp_path):
    hd, cat_path = _build(tmp_path)
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    md = cd.render_md(cat, cd.scan(hd / "deliveries", cat))
    assert "`01_音源/split-iphone.m4a` |" in md
    assert "split-iphone.m4a` ⚠missing" not in md
    assert "| 0:43 |" in md                    # falls back to catalog.json duration
    assert "`gone-iphone.m4a` ⚠missing" in md and "`2026-01-04_gone` ⚠missing" in md


def test_main_writes_views_and_leaves_catalog_json_alone(tmp_path):
    hd, cat_path = _build(tmp_path)
    before = hashlib.sha256(cat_path.read_bytes()).hexdigest()
    assert cd.main(["--handoff-dir", str(hd)]) == 0
    assert hashlib.sha256(cat_path.read_bytes()).hexdigest() == before
    out = cat_path.parent
    assert (out / "CATALOG.md").exists()
    with open(out / "catalog.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["dir"] for r in rows] == ["2026-01-01_flat", "2026-01-02_split", "2026-01-03_sub-master",
                                        "2026-01-04_gone", "Loose"]
    split = rows[1]
    assert split["listen_first_location"] == "01_音源/split-iphone.m4a" and split["n_files"] == "4"
