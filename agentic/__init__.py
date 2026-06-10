"""btc_agentic_system: participant-owned strategies for the BTC benchmark."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def attach_benchmark(repo: str | None = None):
    """Resolve the referee. Preferred: `pip install -e <btc_benchmark checkout>` (import just
    works); the checkout path is still needed for the DATA bundle -- pass it or set
    $BTC_BENCHMARK_REPO. Fallback: add the checkout to sys.path.

    Returns (benchmark_module, repo_path). repo_path may be None if only the package is
    installed and no data checkout was specified."""
    cand = repo or os.environ.get("BTC_BENCHMARK_REPO")
    if cand is None:
        here = Path(__file__).resolve().parents[1]
        for guess in (here.parent / "btc_benchmark",):
            if (guess / "btc_benchmark" / "benchmark").exists():
                cand = str(guess)
                break
    if cand is not None:
        p = str(Path(cand).resolve())
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import btc_benchmark  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("btc_benchmark not importable -- pip install it or set "
                           "$BTC_BENCHMARK_REPO to your btc_benchmark checkout") from e
    return btc_benchmark, (Path(cand).resolve() if cand else None)
