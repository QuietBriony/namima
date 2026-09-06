"""Launcher: `python scripts/deliver.py <doctor|judge|long> ...` from the repo root
on any machine — no install, no PYTHONPATH."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from namima.deliver import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
