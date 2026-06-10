# BTC Short-Horizon Trading AutoResearch — Technical Report

*A self-contained briefing for agents (AI or human) who will use the benchmark, build strategies, or
continue the research. Written 2026-06-10. Backtesting research only; the sealed holdout has never
been opened.*

---

## 0. TL;DR / how to read this

- **What this is:** an automated research program for short-horizon (1-hour decision clock) BTC
  trading, plus a **frozen, adversarially-audited benchmark referee** that scores any strategy in a
  leakage-proof, cost-realistic way.
- **Three components:** (1) `btc_benchmark` — the immutable referee; (2) `btc_agentic_system` (this
  repo) — the upgradeable agent you fork and improve; (3) the private monorepo `btc_autoresearch` —
  the heavy research engine that produced the findings.
- **If you only do one thing:** implement the `Strategy` contract (§4.4), run the benchmark, and read
  the report's `gates` and `disqualified` fields *before* believing any return.
- **The central lesson:** in this problem, **correctness and the absence of leakage dominate
  modeling.** A look-ahead bug or an un-deflated best-of-N Sharpe will produce spectacular fake
  numbers (we measured a fake **+63,152%**). The whole system is built to make those impossible or
  visible.

**Priority order (non-negotiable, everything below serves it):**
`correctness > causality (no leakage) > robustness (survives deflation/costs) > honest failure > net return.`

---

## 1. The problem and the design philosophy

Short-horizon crypto signal research fails in three predictable ways, none of them about model choice:

1. **Look-ahead leakage** — a feature, label, or split silently uses information from the future.
   Produces enormous fake backtest returns.
2. **Multiple-testing / overfitting** — searching many configs on one out-of-sample window makes the
   *best* one look good by selection alone. The naive Sharpe is meaningless once N is large.
3. **Unrealistic accounting** — ignoring or understating transaction costs / funding, or using
   convenient execution assumptions, turns a losing strategy into a "winner."

Our response is to **separate evaluation from modeling** and make the evaluation *structurally*
trustworthy:

- The **referee is frozen and audited**: data, costs, walk-forward, causality gates, and a sealed
  holdout are owned by the benchmark and cannot be changed by a submission.
- Anti-leakage is **enforced by gates that run on every fold**, not by trusting the author.
- Overfitting is addressed with **explicit deflation statistics** (Deflated Sharpe, PBO, CPCV) over
  the *cumulative* number of trials ever run on the OOS window.
- A **6-month sealed holdout** is opened at most once, for one pre-registered candidate, with success
  criteria fixed in advance.

This is the Kaggle/Numerai "private leaderboard" idea, specialized for leakage-sensitive time series
and hardened by repeated adversarial audit.

---

## 2. System map

| Component | Repo | Role | Mutable by participants? |
|---|---|---|---|
| **Referee** | `btc_benchmark` | data, cost model, walk-forward, **causality gates**, sealed holdout, scoring | **No** (frozen) |
| **Agent** | `btc_agentic_system` (this repo) | the `Strategy` you fork & improve; reference strategies | **Yes** |
| **Research engine** | `btc_autoresearch` (private monorepo) | feature/label/model/policy search that produced the findings | n/a (internal) |

The referee depends **only** on its own audited internals (backtester, cost model, walk-forward,
random baseline) — never on participant code. A submission cannot change costs, splits, or the gates.
The benchmark repo is a **carved subset** of the monorepo (it ships `backtest`, `benchmark`, `data`,
`decisions/{baseline,random,sign}`, `features/technical_indicators`, `utils`) — it deliberately does
**not** contain the research engine (models, labels, regimes, scenario bank).

### 2.1 Code & git (where to get it)
All three are git repositories on GitHub under `github.com/YoonhoKim0527/<repo>`:

| Repo | Role | Branch · HEAD | Status |
|---|---|---|---|
| `btc_benchmark` | referee (deliverable) | `main` · `166a99f` | pushed; 0 uncommitted |
| `btc_agentic_system` | agent scaffold (deliverable) | `main` · `ac02e46` | pushed (these report docs uncommitted until reviewed) |
| `btc_autoresearch` | research monorepo (internal) | `autonomous/m6-alpha-research` · `16be967` | the autonomous research is kept **off** the published `main` |

- The **two deliverable repos** are everything a participant/expert needs; the monorepo holds the
  heavy research engine and is **not** required to run the benchmark.
- The **data bundle is gitignored** (too large) and rebuilt from Binance archives with
  `scripts/bootstrap_data.py` — code is versioned, data is reproduced.

---

## 3. Data

- **Source:** **Binance USDⓈ-M (USDT-margined) perpetual futures**, symbol **BTCUSDT**, built from
  Binance's public market-data archives — klines (1m/5m/15m/1h), funding-rate, metrics
  (open-interest + long/short positioning), and mark-premium endpoints — via `src/data/download_*.py`.
  Spot is not used; funding / OI / premium are perp-specific. Paths under
  `data/raw/binance/futures_um/…`.
- **Canonical clock:** 1-hour bars, **59,148 rows, 2019-09 → 2026-06**. Each bar carries OHLCV plus
  `quote_volume`, `number_of_trades`, `taker_buy_*`, and provenance/quality flags (`is_imputed`,
  `data_quality_flag`, …). `timestamp_close = timestamp_open + 1h − 1ms`.
- **Sub-bars:** raw 1m / 5m / 15m klines (intra-hour context; only *completed* sub-bars are
  aggregated into a 1h row).
- **Higher timeframes:** 4h / 1d **resampled from the 1h** (imputed bars excluded, partials flagged),
  attached by **backward as-of join on `timestamp_close`** so only completed HTF bars are visible.
  1w skipped (sample too small).
- **Auxiliary event frames** (as-of attached, never silently forward-filled past staleness limits):
  - `funding` (4,291 rows, 8h funding rate)
  - `open_interest` (571,079 rows, 5-min OI + long/short positioning ratios)
  - `mark_premium` (56,184 rows, mark/index/premium)
- **Imputation** is explicit and flagged; non-finite prices hard-fail the backtester (never silently
  backtested). Build the bundle cold with `scripts/bootstrap_data.py` (download → impute → validate).

---

## 4. The benchmark referee — the contract you must satisfy

### 4.1 Walk-forward, purge, embargo, holdout
- Default split (`SPLIT`): **train 24mo, val 3mo, test 3mo, step 3mo**, purge overlapping labels,
  **sealed holdout 6mo** (≈ 2025-12-08 → 2026-06-08). 15 OOS folds tile the pre-holdout period.
- **Purge + embargo** remove training rows whose label horizon overlaps the test window. Multi-horizon
  decisions purge at `max(H)`.
- **Holdout firewall is structural:** holdout indices are *never* passed to a strategy for fit or
  scoring (`assert te1 <= holdout_start` in the runner). Dev runs cannot touch it.

### 4.2 Backtester accounting (correct first; returns are not optimized here)
- **Execution modes:** `close_to_close_reference` (Mode A, default — position decided at close *t*
  earns close*t*→close*t+1*, entry cost charged that period; the common research convention) and
  `next_open_conservative` (Mode B — decided at close *t*, executed at open *t+1*).
- **Cost model:** all-in **10 bps** per unit turnover; `cost[t] = |p[t]−p[t−1]| · bps/1e4`. Per-trade
  costs are split into entry/exit legs so that **Σ per-trade cost == portfolio cost exactly**
  (verified byte-identical in tests). No look-ahead: the last position earns nothing (no future bar).
- **Funding-aware P&L:** a position *d* over a funding event *f* contributes `−d·f` (long pays when
  funding > 0).
- Reported across **cost multiples 0–5×**, both execution modes, and with/without funding, so you can
  see exactly how cost-sensitive a result is.

### 4.3 Causality gates (run on EVERY fold; failure ⇒ `disqualified`)
Three gates validate the **exact scored positions array** (never a recomputed one):

- **Gate 0 — determinism:** calling `positions()` again reproduces the scored array (purity given fit
  state). Catches "cheat on the scored call, behave on later calls."
- **Gate 1 — future-perturbation:** for cutoffs spread across the **whole** fold (always reaching the
  last decision), perturb *every numeric column* of all bars/aux strictly after the cutoff, in **two
  directions** (inflate + sign-flip), each over a **unique window** `[start, t0+2)`; the scored prefix
  `[:t0+1]` must be unchanged. A position that uses any future value is caught.
- **Gate 2 — prefix-invariance:** asking for a shorter window cannot change earlier decisions (catches
  dependence on the requested window *end* rather than on data).

**This gate was audited four times, each round finding a deeper bypass — a core project lesson that
independent adversarial verification is not optional:**

| Audit | Bypass found | Fix |
|---|---|---|
| 1 | gate ran on **one fold** → fold-selective cheater | gate **every** fold |
| 2 | gate re-invoked `positions()` (got honest output) instead of checking the **scored** array | gate the scored array; determinism compares scored vs recompute |
| 3 | **tail-gap**: cutoffs stopped at 0.75·n; a look-ahead confined to the last 25% scored **+63,152%** undetected | sweep the **whole** fold to the last decision |
| (hardening) | single-direction perturbation missed inflation-robust comparisons; only OHLCV perturbed (OI/trades/premium future was readable); a stateful **cache-replay** strategy memoised its scored output and replayed it | two directions; **all numeric columns**; **unique per-cutoff window** so replay can't satisfy the gate |

- **Cost note:** an airtight stride-1 sweep is O(n) full strategy evaluations per fold (minutes→hours
  on real folds), so the sweep is **budgeted** (`gate_max_cutoffs`, default 512; `None` = exhaustive
  stride-1) and the coverage actually run is **reported** (`future_perturbation_exhaustive`,
  `future_perturbation_cutoffs_min`). Internally the perturber mutates one working copy in place and
  restores it (≈7 ms/cutoff vs ≈1 s for naive frame rebuilds).
- **Disclosed inherent limit:** a strategy that *ignores its `data` argument* and returns a
  precomputed look-ahead array is invisible to any black-box perturbation gate (no input → no signal
  to detect). Documented, not hidden; the structural mitigation is **streaming (bar-by-bar) holdout
  evaluation**, recommended for the authoritative run. Also trusted-but-unenforced: a strategy's
  **declared horizon** (used for purge) — deliberate under-declaration is surfaced in the report.

### 4.4 The `Strategy` contract (what you implement)
```python
class Strategy(Protocol):
    name: str
    horizon: int                       # declared label horizon in bars (drives purge/embargo)
    def fit(self, data, train_start, train_end) -> None: ...        # may use ONLY rows [train_start, train_end)
    def positions(self, data, start, end) -> np.ndarray: ...        # p[t] in [-1, 1] for t in [start, end)
```
`p[t]` may use information only up to bar *t* (candles ≤ *t*; aux events with `event_time ≤ close[t]`).
Causal use **within** a window is not trusted — it is enforced by the gates. `data` is a
`BenchmarkData(candles: DataFrame, aux: dict[str, DataFrame])`.

### 4.5 Running it & reading the report
```python
from btc_benchmark.benchmark import load_benchmark_data, run_benchmark
data = load_benchmark_data(".")
report = run_benchmark(MyStrategy(), data, leaderboard_path="results/leaderboard.jsonl")
```
Key report fields: `disqualified` (gate failure ⇒ result invalid), `gates.{determinism,
future_perturbation, prefix_invariance, future_perturbation_exhaustive, failed_folds}`, `net`,
`sharpe`, `sortino`, `max_drawdown`, `profit_factor`, `n_trades`, `turnover`, holding stats,
`net_cost{0..5}x`, `net_next_open`, `net_funding_aware`, `random_pctile` (turnover-matched random
baseline percentile — beat it or the "edge" is just trading activity), `per_year`, `buy_hold_net`.
**Always read `disqualified` and `random_pctile` first.** For rapid iteration, `gates=False`; the
authoritative score runs the gates.

---

## 5. The AutoResearch engine & M7 methodology

The 1h close is the **decision clock**. At each close the system asks: *what regime are we in, what
are the likely scenarios over 1h–3d, is there a tradeable edge, where is the invalidation, and should
we enter / hold / exit / stay flat?* M7 searches that design space and reports honestly which pieces
help — **it is not a hunt for a higher headline** (the OOS is already heavily mined).

### 5.1 Features (`src/features/`)
- **`mtf_features.py`** — `intrahour` (5m/15m + compact 1m: path shape, max DD/run-up within the hour,
  momentum consistency, last 5m/15m return, volume burst/concentration, wick structure,
  reversal-in-hour, **breakout-failure**, range compression, sub-bar taker imbalance) and
  `htf_context` (4h/1d: EMA distance/slope, trailing vol percentile, Donchian state, momentum,
  drawdown-from-high, distance-to-high/low, bull/bear/range flags).
- Prior groups: `technical_indicators`, `alpha_features`, `cross_asset`, plus M6's `microstructure`,
  `taker_flow`, `funding`, `open_interest`, `positioning`, `premium`, `multitf`, `volatility_regime`.
- Every feature group is **versioned** and gets a future-perturbation causality test before use; the
  frozen M6 feature groups are left bit-identical.

### 5.2 Labels (`src/labels/multi_horizon.py`) — training targets ONLY, NaN tails
For each horizon **H ∈ {1, 4, 12, 24, 72} bars**: `return_H`, `direction_H`, `above-cost_H`,
vol-scaled-threshold, **MFE_H / MAE_H** (max favorable/adverse excursion via sliding windows),
**TP-first / SL-first_H** (vol-scaled triple-barrier, reuses `triple_barrier.py`),
trend-continuation_H, drawdown-risk_H. Path-aware labels make the system reason about *how* a move
happens, not just its endpoint.

### 5.3 Regimes (`src/regimes/regime_module.py`) — causal, rule-based; features AND decision filters
- **Trend:** 1d EMA + slope → bull / bear / range (dead-zone banded).
- **Volatility:** trailing rolling-rank percentile → low / normal / high / extreme.
- **Flow / crowding:** funding trailing percentile + OI z-score → long-crowded / short-crowded /
  neutral.
- Event & liquidity regimes skipped (no macro calendar / order-book source) and logged.

### 5.4 Scenario model bank (`src/research/scenario_m7.py`)
A walk-forward multi-horizon model bank emits a per-timestamp **scenario vector**: `E[ret_H]`,
`P(up_H)`, `P(above-cost_H)`, `P(TP-first_H)`, `E[MFE_H]`, `E[MAE_H]`. **Purge/embargo at max(H)=72**
whenever multiple horizons feed one decision (single-horizon trials purge at their own H). Forecasts
are cached by `(features, target, H, model, seed)` (see `results/m7_cache/`).

### 5.5 Trader-style policies (`src/decisions/policies_m7.py`) — causal state machines
Trend-holding (regime-gated entry; hold until regime break / multi-horizon flip / MAE-stop /
time-stop, with stop-cooldown and hysteresis), scenario-weighted score (a small **fixed** weight grid,
not free optimization), adaptive-exit overlays (veto-and-release), no-trade filters (below-cost
margin, timeframe conflict, extreme vol), trade-level meta-acceptance (audited `meta_labeling`), and
an optional short side. Compared against simple 1-bar **cost-aware** sizing and rule baselines.

### 5.6 Models
XGBoost 3.2.0, LightGBM 4.6.0, CatBoost 1.2.10, logistic, random forest, elastic net (NaN-native
where supported). Multi-horizon = separate models per horizon sharing one feature matrix (simple,
reproducible, leakage-auditable). **Sequence models (TCN/GRU/transformer) and representation learning
are DEFERRED** — torch is not installed; reproducibility and leakage-auditability take priority.

### 5.7 Staged search (≤ ~300 trials, append-only ledger, failures kept)
**S1 Targets** (which (target, H) is worth forecasting) → **S2 Representations** (which feature set
helps) → **S3 Policies** (does the trader-style layer beat 1-bar cost-aware) → **S4 Model families**
→ **S5 Robustness** (cost/exec/funding stress, block-bootstrap CI, **family Deflated-Sharpe over the
cumulative trial count**, PBO-CSCV, seed stability, CPCV). Selection rules are deterministic and
logged. (182 trials run: S1=35, S2=15, S3=33, S4=99; **S5 robustness is the rerun in progress.**)

### 5.8 Overfitting statistics (`src/backtest/{overfitting,cpcv}.py`)
PSR (Probabilistic Sharpe), **Deflated Sharpe (DSR)** over the cumulative trial count, **PBO** via
CSCV (probability of backtest overfitting), **MinTRL** (minimum track-record length), block-bootstrap
CIs, and **CPCV** (combinatorial purged cross-validation). The headline number is never trusted; the
**deflated** number is.

---

## 6. Findings

### 6.0 Lineage — what has been tried before M7 (M1–M6, same OOS)
The program is iterative; M7 sits on five prior milestones, all mined on the same out-of-sample window:

- **M1–M5.5** built the autoresearch loop, the cost-aware labels/decisions, the overfitting-stat
  layer, and the M5 candidate **`t054`** (net +60%, Sharpe 0.52, 104 trades) — flagged
  `NEEDS_REFINEMENT`.
- **M6 (alpha discovery, ~500 cumulative trials).** *The discovery:* **microstructure** features
  (VWAP-deviation, close-in-range, intrabar) are the strongest, most stable predictor — rank-IC
  **0.069**, 99% fold-sign consistency; taker-flow and 5m→1h multi-TF add modest *independent* IC;
  OI / premium are weak. Best candidate **`alpha_full` cost-aware λ2, H=1**: net +250%, Sharpe 1.04,
  MaxDD −41% — beats `t054` on every axis, and from *better prediction*, not just lower turnover.
- **…but the honest deflation story is the real lesson:** every top candidate has **Deflated Sharpe
  ≈ 0** (best-of-N over ~500 trials). CPCV says the honest MaxDD is ~**−63%** (not −41%) and central
  Sharpe ~0.80; an **8-seed** refit gives Sharpe **0.70 ± 0.27** (the headline 1.04 is the lucky
  seed=42); the deployable **seed-ensemble portfolio** is Sharpe **0.78** / PSR 0.94. Meta-labeling's
  apparent drawdown cut did **not** survive resampling. The *relative* claim "alpha beats t054" **is**
  validated under CPCV; the *absolute* edge is unproven until the sealed holdout.
- **Things deliberately NOT tried / deferred** (all logged, never silently skipped): sequence models
  (TCN/GRU/transformer) and representation learning (torch not installed — reproducibility &
  leakage-auditability first); liquidation data (no historical source); event / liquidity regimes
  (no macro calendar / order-book feed); 1-week timeframe (sample too small).

### 6.1 M7 findings (verified from the 182-trial ledger; NOT yet deflation-final; holdout sealed)

- **Best signal:** `1h + funding/flow` features, **XGBoost**, target = return, **horizon H = 4 (4h)**,
  decision = cost-aware (λ=3.0) → **net +263%, Sharpe 1.12, MaxDD −35%, ~48% exposure, 146 trades**,
  2025 Sharpe 0.93.
- **Baselines** (same OOS): `rule_trend_hold` net +155% / Sharpe **0.95** / MaxDD −31% (best rule);
  buy-&-hold net +122% / Sharpe 0.67 / MaxDD −70%; ema-cross, donchian, rsi-meanrev all **negative**.
  → the H=4 cost-aware signal **edges the best rule baseline** on Sharpe and net.
- **Horizon matters:** H=4 > H=1 and > H=72 on the cost-aware regression track.
- **Honest negatives (as important as the positives):**
  - **Intra-hour microstructure did not help** — `1h+flow` (Sharpe 1.12) **beat** `mtf_full`
    (1m/5m/15m + 4h/1d, Sharpe 0.90). Adding finer timeframes **hurt**.
  - **Trader-style policies mostly lost to transaction-cost churn.** The one survivor (a CatBoost
    scenario "trend + no-trade" policy) had low MaxDD (−13%) and strong 2025 Sharpe (2.0) but traded
    almost nothing (~1.6% exposure) — interesting, not yet usable.
- **The decisive caveat:** these trials sit on **~500 prior M5/M6 trials on the same OOS** (~680
  cumulative). Expected **Deflated Sharpe ≈ 0**; M7's real value is the **controlled comparisons**
  (does multi-TF / multi-horizon / adaptive-holding help vs fixed baselines on identical data), not a
  new headline. S5 quantifies this.

---

## 7. The sealed holdout — DO NOT OPEN (pre-registered, one shot)

`docs/HOLDOUT_PREREGISTRATION.md` fixes, **in advance**, the single candidate and success criteria so
the eventual test is genuinely out-of-sample. **Only the user runs it; agents must not.**

- **Pre-registered candidate** (chosen by rationale, not max-net): preset `alpha_full`, **H=1**,
  long_cash, decision cost-aware λ=2.0, XGBoost regressor (n_estimators 300, max_depth 4, lr 0.05,
  subsample 0.8, colsample 0.8). Rationale: microstructure rank-IC 0.069 with 99% fold-sign
  consistency is the strongest, most stable predictor; H=1 (not inflated by horizon-matched holding).
  Dev OOS: net +250%, Sharpe 1.04, MaxDD −41%, 204 trades, 10/15 folds positive, PSR 0.978.
- **Pre-committed success criteria (decide before looking):** holdout net > 0 at 1× cost; Sharpe > 0
  and ≥ ~0.3; beats turnover-matched random (≥ 0.90 pct); survives 2× cost; ≥ 10 trades. Otherwise the
  dev edge was selection bias (an honest, useful result). **Either way the holdout is then burned.**
- Status: **sealed holdout UNUSED.**

---

## 8. Non-negotiable guardrails (and why)

- **Backtesting research only** — no live, no paper trading.
- **The sealed holdout is never opened during research** — reusing it re-introduces overfitting.
- **No future leakage** — enforced by the gates, tested per module.
- **No changes to the backtester / cost model / evaluation accounting to improve a result**, and **no
  silent cost reduction** — the referee is frozen on purpose.
- **H>1 forecasts are never silently traded with 1-bar rebalancing** — holding mode is explicit per
  trial.
- **Value hierarchy:** correctness > causality > robustness > honest failure > net return. A correct
  negative result is a success; a leaky positive one is a failure.

---

## 9. File map (where to look)

**Benchmark (`btc_benchmark/`)**: `benchmark/contract.py` (Strategy + loader), `benchmark/runner.py`
(scoring + report), `benchmark/validity.py` (the gates), `backtest/{backtester,cost_model,
walk_forward,metrics,overfitting,cpcv}.py`, `decisions/{baseline_rules,random_baseline,sign_rule}.py`,
`data/*` (download/impute/resample/validate), `tests/test_benchmark_contract.py` (honest passes,
every cheater class disqualified), `scripts/repro_audit3_tailgap.py` (reproduce the +63,152% exploit →
now disqualified), `README.md`.

**Monorepo research engine (`btc_autoresearch/`)**: `src/features/` (mtf_features, alpha_features,
feature_registry, …), `src/labels/{multi_horizon,triple_barrier,fixed_horizon}.py`,
`src/regimes/regime_module.py`, `src/research/{scenario_m7,autoresearch_m7,meta_labeling,
candidate_audit,report_generator}.py`, `src/decisions/{policies_m7,cost_aware_threshold,
horizon_matched,risk_filters,baseline_rules}.py`, `src/models/`, `scripts/run_m7*.py`,
`docs/{M7_PLAN,M7_REPORT,HOLDOUT_PREREGISTRATION,BENCHMARK_SPLIT_DESIGN,RESEARCH_PLAN}.md`,
`results/reports/m7_scenario_autoresearch/{trial_ledger.csv, baselines.csv, …}`.

**Agent (`btc_agentic_system/`, this repo)**: `agentic/strategies/{ema_trend,xgb_momentum}.py`,
`scripts/run_benchmark.py`, `results/leaderboard.jsonl`, `research_abstract.md` (short version of this
report).

---

## 10. How another agent should continue

1. **Stand up the benchmark.** Install `btc_benchmark` (pip), build the data bundle
   (`scripts/bootstrap_data.py`), confirm `tests/test_benchmark_contract.py` is green and the
   `repro_audit3_tailgap.py` exploit is disqualified.
2. **Reproduce a known-good baseline.** Run the reference `EmaTrend` / `XgbMomentum`; confirm it
   passes the gates (`disqualified=False`) and check `random_pctile`.
3. **Improve the agent, not the referee.** Implement a new `Strategy` in `btc_agentic_system`. The
   most promising direction is the **H=4 cost-aware return regression on 1h+flow features** (§6).
   Declare your horizon honestly (it drives purge).
4. **Trust the gate, then the deflation.** A result is only real if (a) `disqualified=False`,
   (b) it beats `random_pctile ≥ 0.9`, (c) it survives 2× cost, and (d) its **Deflated** Sharpe over
   the cumulative trial count is meaningful — not its raw Sharpe.
5. **Never touch the holdout.** It is one-shot, user-only, pre-registered (§7).

---

## 11. Open problems & next steps

- **Finish S5 robustness** (running): family DSR / PBO / CPCV / seed stability / cost-exec-funding
  stress → fill `docs/M7_REPORT.md`, answer the 10 milestone questions, freeze candidate configs,
  independent correctness audit, and emit a recommendation ∈ {READY_FOR_PRE_HOLDOUT_AUDIT,
  CONTINUE_SIGNAL_RESEARCH, NEEDS_RISK_REDUCTION, REJECT_ALL}.
- **Decide: holdout now or keep searching?** The dev edge (Sharpe ~1.1) is selected from ~680 trials;
  is it worth the one-shot pre-holdout audit, or do we demand a higher deflated bar first?
- **Risk profile:** ~48%-exposure / −35%-MaxDD signal vs the ~2%-exposure low-DD policy vs a blend.
- **Benchmark rigor vs cost:** add **streaming holdout evaluation** to close the input-ignoring-replay
  limitation structurally?
- **Research directions:** sequence models (currently deferred for reproducibility), regime-conditional
  sizing, better no-trade / risk gating, execution realism, cross-validated meta-labeling.

---

## 12. Glossary

- **OOS** — out-of-sample (the walk-forward test folds, excluding the sealed holdout).
- **Purge / embargo** — dropping train rows whose label horizon overlaps (purge) or sits just before
  (embargo) the test window, to prevent label leakage.
- **MFE / MAE** — maximum favorable / adverse excursion over a horizon (path-aware labels).
- **Triple barrier** — label = which of {take-profit, stop-loss, time} is hit first.
- **DSR / PSR / PBO / CPCV / MinTRL** — deflation & overfitting statistics (§5.8); the deflated Sharpe
  over cumulative trials is the number that matters.
- **`random_pctile`** — percentile of the strategy's net return vs many turnover-matched random
  position sequences; ≥ 0.9 means the edge is more than just trading activity.
- **Mode A / Mode B** — close-to-close (reference) vs next-open (conservative) execution.
- **cost-aware decision** — only take a position when expected edge exceeds a cost-scaled threshold
  (λ controls how much expected return must beat cost before trading).
