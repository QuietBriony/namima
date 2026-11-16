"""Render the AI→human delivery catalogue (any PC).

    python scripts/catalog_deliveries.py                 # CATALOG.md + catalog.csv next to catalog.json, from catalog.json + files on disk
    python scripts/catalog_deliveries.py --set-verdict 2026-08-16_continuous-dissolve-v4-acid-meridian "採用。酸をもう少し前へ"
    python scripts/catalog_deliveries.py --handoff-dir <path>

`catalog.json` (curated: family / genre / engine / checkpoints / verdict) is the single
source of truth. It lives in `<handoff dir>/deliveries/00_カタログ・制作ノート/` (the Drive
folder was regrouped by hand on 2026-10-02) or, in the older flat layout, directly in
`<handoff dir>/deliveries/`. Packets may sit directly under `deliveries/` or one level
deeper inside a human-made group folder (`Mist Pulse/`, `namima IDM/`, ...); the `dir`
field in catalog.json stays the bare packet name. Inside a packet, files may also sit in
subfolders (`01_音源/` / `02_編集用/` / `03_検証・引継ぎ/`, split by hand on 2026-10-02);
they are counted down to PACKET_SUBDIR_DEPTH folder levels, in a fixed order. This script
merges the catalogue with what is actually on disk (files, sizes, wav durations, handoff
presence) so the table can never drift from the folder. Verdicts are written back into
catalog.json so the human judgement becomes part of the systematic record. CATALOG.md /
catalog.csv are generated next to catalog.json.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.deliver import resolve_handoff_dir  # noqa: E402

CATALOG_SUBDIR = "00_カタログ・制作ノート"
# folder levels scanned below a packet: 1 = `01_音源/x.m4a`; 2 also covers an unregistered
# group folder whose packets are split the same way (`<group>/<packet>/01_音源/x.m4a`)
PACKET_SUBDIR_DEPTH = 2


def wav_duration(p: Path) -> float | None:
    try:
        with wave.open(str(p), "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return None


def fmt(sec: float | None) -> str:
    if sec is None:
        return ""
    s = int(round(sec))
    return f"{s // 60}:{s % 60:02d}"


def find_catalog(deliveries: Path) -> Path | None:
    for cand in (deliveries / CATALOG_SUBDIR / "catalog.json", deliveries / "catalog.json"):
        if cand.exists():
            return cand
    return None


def locate_packet(deliveries: Path, name: str) -> Path | None:
    """`deliveries/<name>` or `deliveries/<group>/<name>` (one level, first match)."""
    direct = deliveries / name
    if direct.is_dir():
        return direct
    for group in sorted(x for x in deliveries.iterdir() if x.is_dir()):
        if (group / name).is_dir():
            return group / name
    return None


def packet_files(d: Path, max_depth: int = PACKET_SUBDIR_DEPTH) -> list[Path]:
    """Files directly in `d` plus those in its subfolders down to `max_depth` folder levels.

    Deterministic order: shallower first, then by relative path (direct files before
    `01_音源/…`, so a bare file name resolves to the shallowest copy).
    """
    out: list[Path] = []
    stack = [(d, 0)]
    while stack:
        cur, depth = stack.pop()
        for x in cur.iterdir():
            if x.is_file():
                out.append(x)
            elif x.is_dir() and depth < max_depth:
                stack.append((x, depth + 1))
    return sorted(out, key=lambda f: (len(f.relative_to(d).parts), f.relative_to(d).as_posix()))


def find_listen_first(d: Path, files: list[Path], name: str) -> Path | None:
    """`listen_first` as written (relative to the packet), else the first file with that name."""
    if not name:
        return None
    direct = d / name
    if direct.is_file():
        return direct
    base = Path(name).name
    return next((f for f in files if f.name == base), None)


def scan(deliveries: Path, cat: dict) -> list[dict]:
    known = {p["dir"] for p in cat["packets"]}
    rows = []
    groups: set[Path] = set()
    for p in cat["packets"]:
        d = locate_packet(deliveries, p["dir"])
        files = packet_files(d) if d else []
        # track length: masters anywhere, other wavs only at the packet top (as before) — stems
        # or loops inside 01_音源/ must not override the curated duration once masters left Drive
        wavs = [f for f in files if f.suffix.lower() == ".wav"
                and (f.parent == d or f.name.lower().endswith("-master.wav"))]
        durs = [wav_duration(f) for f in wavs]
        durs = [x for x in durs if x]
        lf = find_listen_first(d, files, p.get("listen_first", "")) if d else None
        row = dict(p)
        row["exists"] = d is not None
        row["location"] = d.relative_to(deliveries).as_posix() if d else p["dir"]
        row["n_files"] = len(files)
        row["size_mb"] = round(sum(f.stat().st_size for f in files) / 1e6, 1)
        row["has_handoff"] = any("handoff" in f.name.lower() for f in files)
        row["wav_duration"] = fmt(max(durs)) if durs else ""
        row["listen_first_exists"] = lf is not None
        row["listen_first_location"] = lf.relative_to(d).as_posix() if lf else ""
        rows.append(row)
        if d and d.parent != deliveries:
            groups.add(d.parent)
    # folders on disk that the curated catalogue does not know yet (group folders holding
    # known packets and the catalogue folder itself are not packets)
    for d in sorted(x for x in deliveries.iterdir() if x.is_dir()):
        if d.name in known or d in groups or d.name == CATALOG_SUBDIR:
            continue
        files = packet_files(d)
        rows.append({"dir": d.name, "family": "?", "title": d.name, "producer": "?", "engine": "?", "genre": "（catalog.json 未登録）",
                     "bpm": "", "key": "", "duration": "", "listen_first": "", "intended": "", "checkpoints": [],
                     "verdict": None, "verdict_date": None, "exists": True, "location": d.name,
                     "n_files": len(files), "size_mb": round(sum(f.stat().st_size for f in files) / 1e6, 1),
                     "has_handoff": any("handoff" in f.name.lower() for f in files), "wav_duration": "",
                     "listen_first_exists": False, "listen_first_location": ""})
    return rows


def render_md(cat: dict, rows: list[dict]) -> str:
    fam = {f["id"]: f for f in cat["families"]}
    out = [f"# AI→人間 納品カタログ（{cat.get('updated', '')} 更新 / 自動生成: scripts/catalog_deliveries.py）", "",
           "判定列が空 = **判定記録なし**（再生ログは存在しないので「聴いたかどうか」は人間の申告だけが記録になる）。",
           "判定は `python scripts/catalog_deliveries.py --set-verdict <packet> \"…\"` か、Claude/Codex に一言で書き戻す。",
           "packet 列は deliveries/ からの実際の場所（人間が系統ごとのフォルダへ移した分はそのフォルダ付き）。",
           "packet 内のサブフォルダ（`01_音源/` など）も数え、まず聴く 列は packet からの実際の場所を出す。",
           "尺は master（または packet 直下）の WAV があればその実測、無ければ catalog.json の値（master WAV は Drive に置かない運用）。", ""]
    registered = [r for r in rows if r["family"] != "?"]
    judged = sum(1 for r in registered if r.get("verdict"))
    missing = [r["dir"] for r in registered if not r["exists"]]
    out += [f"- packet 数: {len(registered)} / 判定あり: {judged} / 判定なし: {len(registered) - judged}"
            + (f" / 未登録フォルダ: {len(rows) - len(registered)}" if len(rows) > len(registered) else ""),
            f"- 合計サイズ: {sum(r['size_mb'] for r in rows):.0f} MB"]
    if missing:
        out.append("- ⚠ フォルダが見つからない packet: " + ", ".join(f"`{m}`" for m in missing))
    out.append("")
    for fid in list(fam) + (["?"] if any(r["family"] == "?" for r in rows) else []):
        frows = [r for r in rows if r["family"] == fid]
        if not frows:
            continue
        title = fam[fid]["title"] if fid in fam else "未分類（catalog.json 未登録のフォルダ）"
        out += [f"## {fid}. {title}", ""]
        if fid in fam and fam[fid].get("note"):
            out += [f"> {fam[fid]['note']}", ""]
        out += ["| packet | ジャンル / 方向 | エンジン | BPM / key | 尺 | まず聴く | 判定 |", "|---|---|---|---|---|---|---|"]
        for r in frows:
            dur = r.get("wav_duration") or r.get("duration", "")
            lf = r.get("listen_first", "")
            lf_shown = r.get("listen_first_location") or lf
            lf_cell = f"`{lf_shown}`" + ("" if r.get("listen_first_exists") else " ⚠missing") if lf else ""
            v = r.get("verdict") or "— 未判定"
            loc = f"`{r['location']}`" + ("" if r["exists"] else " ⚠missing")
            out.append(f"| {loc} | {r['genre']} | {r['engine']} | {r['bpm']} / {r['key']} | {dur} | {lf_cell} | {v} |")
        out.append("")
        for r in frows:
            if r.get("checkpoints"):
                out.append(f"**{r['title']}** — 聴きどころ: " + " ／ ".join(r["checkpoints"]))
        out.append("")
    out += ["## 聴く順（提案）", "",
            "1. D の v2→v3→v4（3 分 ×3・方向が最も明確: ポケット / テクノ床 / アシッド）",
            "2. C の通し 4:34（3 曲を一度に比較）", "3. B の v3（2:30）→ 必要なら v1/v2", "4. A（9:44・YouTube 候補）",
            "5. E（6:00・方向は判定済み、バランスの追い込み待ち）", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handoff-dir", default=None)
    ap.add_argument("--set-verdict", nargs=2, metavar=("PACKET_DIR", "TEXT"))
    a = ap.parse_args(argv)
    hd, src = resolve_handoff_dir(a.handoff_dir)
    deliveries = hd / "deliveries"
    cat_path = find_catalog(deliveries)
    if cat_path is None:
        print(f"catalog.json not found in {deliveries / CATALOG_SUBDIR} or {deliveries} (hand-off dir via {src})")
        return 1
    out_dir = cat_path.parent
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    if a.set_verdict:
        pdir, text = a.set_verdict
        hit = [p for p in cat["packets"] if p["dir"] == pdir]
        if not hit:
            print(f"unknown packet {pdir}")
            return 1
        hit[0]["verdict"] = text
        hit[0]["verdict_date"] = _dt.date.today().isoformat()
        cat["updated"] = _dt.date.today().isoformat()
        cat_path.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"verdict recorded for {pdir}")
    rows = scan(deliveries, cat)
    (out_dir / "CATALOG.md").write_text(render_md(cat, rows), encoding="utf-8")
    with open(out_dir / "catalog.csv", "w", newline="", encoding="utf-8-sig") as f:
        cols = ["dir", "location", "family", "title", "genre", "engine", "producer", "bpm", "key", "duration", "wav_duration",
                "listen_first", "listen_first_location", "intended", "n_files", "size_mb", "has_handoff", "verdict",
                "verdict_date"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    registered = [r for r in rows if r["family"] != "?"]
    judged = sum(1 for r in registered if r.get("verdict"))
    missing = [r["dir"] for r in registered if not r["exists"]]
    print(f"CATALOG.md + catalog.csv written to {out_dir}  ({len(registered)} packets, {judged} judged, "
          f"{len(rows) - len(registered)} unregistered folders, hand-off dir via {src})")
    if missing:
        print("WARNING packet folder not found: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
