"""Run a strategy submission against the frozen benchmark.

    python -m scripts.run_benchmark --strategy agentic.strategies.ema_trend:EmaTrend
    python -m scripts.run_benchmark --strategy agentic.strategies.xgb_momentum:XgbMomentum --team me
"""
from __future__ import annotations

import argparse
import importlib
import json

from agentic import attach_benchmark


def load_strategy(spec: str):
    mod_name, _, cls_name = spec.partition(":")
    cls = getattr(importlib.import_module(mod_name), cls_name)
    return cls()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True, help="module.path:ClassName")
    ap.add_argument("--team", default="anonymous")
    ap.add_argument("--benchmark-repo", default=None)
    ap.add_argument("--no-sub-bars", action="store_true", help="skip loading 1m/5m/15m aux (faster)")
    args = ap.parse_args()

    bm, repo = attach_benchmark(args.benchmark_repo)
    if repo is None:
        raise SystemExit("need the btc_benchmark checkout for the data bundle -- "
                         "set $BTC_BENCHMARK_REPO or pass --benchmark-repo")
    data = bm.load_benchmark_data(repo, include_sub_bars=not args.no_sub_bars)
    run_benchmark = bm.run_benchmark
    strategy = load_strategy(args.strategy)
    report = run_benchmark(strategy, data, team=args.team,
                           leaderboard_path="results/leaderboard.jsonl")
    print(json.dumps(report, indent=2, default=str))
    if report["disqualified"]:
        print("\nDISQUALIFIED: causality gates failed -- fix the strategy (see report['gates']).")
    else:
        print(f"\nOK  sharpe={report['sharpe']}  net={report['net']:+.1%}  "
              f"maxDD={report['max_drawdown']:.1%}  vs buy&hold {report['buy_hold_net']:+.1%}")


if __name__ == "__main__":
    main()
