# btc_agentic_system

The **agent (research) system** for the BTC 1h trading benchmark. Fork this repo, upgrade your
strategies / features / models / search loops, and score them against the frozen
[`btc_benchmark`](https://github.com/YoonhoKim0527/btc_benchmark) referee.

```
[btc_agentic_system]  ← you upgrade this (strategies, features, models, search loops)
        │  Strategy contract (fit / positions)
        ▼
[btc_benchmark]       ← frozen referee (data, backtester, costs, walk-forward,
                          causality gates, sealed holdout, leaderboard)
```

*(한글) BTC 1시간봉 벤치마크의 **에이전트(연구) 시스템**. 이 레포를 포크해 전략/피처/모델/서치를
업그레이드하고, 동결된 `btc_benchmark` 심판으로 점수를 받습니다.*

## Rules (enforced by the benchmark)
1. The benchmark drives the walk-forward and calls your `fit(train)` / `positions(test)` per fold —
   you cannot pick your own splits or look beyond the requested fold.
2. **Causality gates** (determinism / future-perturbation / prefix-invariance) run on **every** fold
   before scoring. Any failure ⇒ `disqualified` (still recorded).
3. Costs / accounting / splits are referee constants — your submission cannot lower them.
4. **The sealed holdout is never touched** (a host-owned one-shot protocol).

## Setup

```bash
git clone https://github.com/YoonhoKim0527/btc_benchmark.git
cd btc_benchmark && pip install -e ".[dev]" && pytest      # install + verify the referee
python -m scripts.bootstrap_data                            # rebuild the data bundle (~10 min)
cd ..
git clone https://github.com/YoonhoKim0527/btc_agentic_system.git
cd btc_agentic_system && pip install -e .
export BTC_BENCHMARK_REPO=../btc_benchmark                  # the checkout whose data bundle is built
```

## The strategy contract (v1)

```python
class MyStrategy:
    name = "my_strategy"
    horizon = 1                      # declared label horizon (drives purge/embargo; shown in report)

    def fit(self, data, train_start, train_end):
        # train using ONLY data.candles.iloc[train_start:train_end]
        ...

    def positions(self, data, start, end):
        # return p[t] in [-1, 1] for t in [start, end).
        # p[t] may use only info up to bar t (candles rows <= t; aux event_time <= close[t]).
        # The gates verify this -- peeking at the future ⇒ disqualified.
        ...
```

`data.aux` carries raw funding / open_interest / mark_premium / 5m·15m·1m sub-kline frames (when
present). Causal use (as-of joins, completed bars only) is your responsibility and is gate-checked —
including straddling sub-bars (a 5m bar that opens before but closes after your decision bar is
treated as future by the gate).

## Run

```bash
python -m scripts.run_benchmark --strategy agentic.strategies.ema_trend:EmaTrend
python -m scripts.run_benchmark --strategy agentic.strategies.xgb_momentum:XgbMomentum --team myteam
```

Results print and append to `results/leaderboard.jsonl` (with the benchmark version + gate results).

## Where to upgrade
- `agentic/strategies/` — add new strategies (any features / models / multi-horizon / regimes /
  policies; just keep the gates green). The two bundled examples are intentionally weak demos.
- Run your own search loop, but submit only **final** candidates: every submission is recorded, and
  more submissions inflate selection bias (see the benchmark's Deflated Sharpe).

## Honesty note
correctness > causality > robustness > honest failure > net return. High returns from leakage,
overfitting, a lucky seed, or a hidden cost reduction are meaningless — hence the gates and the
robustness battery (cost multiples, next-open, funding-aware, random-matched, per-year).
