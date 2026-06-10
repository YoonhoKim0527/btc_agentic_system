"""btc_agentic_system: participant-owned strategies for the BTC benchmark."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def attach_benchmark(repo: str | None = None) -> Path:
    """Make the benchmark repo importable (Phase-A wiring; Phase B: pip-installed package).

    Order: explicit arg > $BTC_BENCHMARK_REPO > ../btc_autoresearch next to this repo.
    """
    cand = repo or os.environ.get("BTC_BENCHMARK_REPO")
    if cand is None:
        here = Path(__file__).resolve().parents[1]
        for guess in (here.parent / "btc_autoresearch",
                      here.parent / "Autoresearch_Trading" / "btc_autoresearch"):
            if (guess / "src" / "benchmark").exists():
                cand = str(guess)
                break
    if cand is None or not (Path(cand) / "src" / "benchmark").exists():
        raise RuntimeError("benchmark repo not found -- set $BTC_BENCHMARK_REPO to your "
                           "btc_autoresearch checkout")
    p = str(Path(cand).resolve())
    if p not in sys.path:
        sys.path.insert(0, p)
    return Path(p)
