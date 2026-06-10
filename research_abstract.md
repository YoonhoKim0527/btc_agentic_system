# BTC Short-Horizon Trading AutoResearch — Research Abstract

**Status:** 2026-06-10 · Backtesting research only — no live/paper trading; the sealed holdout has never been opened.

---

## 1. Thesis

Finding *robust* short-horizon BTC trading signals is dominated not by modeling but by three failure
modes: **look-ahead leakage**, **multiple-testing / overfitting**, and **unrealistic backtest
accounting**. We address this with two deliberately decoupled artifacts:

1. **A frozen benchmark referee** (`btc_benchmark`) — immutable data, cost model, walk-forward,
   **causality gates**, and a sealed holdout. It scores any submitted strategy in a leakage-proof,
   cost-realistic, comparable way.
2. **An upgradeable agent system** (`btc_agentic_system`, this repo) — a small `Strategy` contract
   anyone can fork and improve. The *only* way to get a score is to run the frozen referee.

This mirrors the Kaggle/Numerai separation of *evaluation* from *modeling*, specialized for
leakage-sensitive financial time series, with anti-leakage enforcement made **structural and
adversarially audited** rather than trust-based.

---

## 2. What we have built (done)

### 2.1 Benchmark referee — complete, adversarially audited
- **Correct backtester:** exact per-trade cost accounting (per-trade costs sum byte-identically to
  the portfolio cost), close-to-close and next-open execution modes, funding-aware P&L.
- **Walk-forward** with purge + embargo; a **6-month sealed holdout, structurally firewalled**
  (holdout indices are never passed to any strategy).
- **Mandatory causality gates on every fold** (determinism / future-perturbation / prefix-invariance):
  a strategy that uses *any* future information is disqualified.
- **Survived four rounds of independent adversarial audit**, each finding a deeper bypass:
  (1) fold-selective gating; (2) gating a *recomputed* array instead of the *scored* one;
  (3) a **tail-gap** where the last 25% of each fold was never forward-checked — a tail-confined
  look-ahead scored a fake **+63,152%** undetected; (4) stateful **cache-replay**. The gate now
  sweeps the whole fold, perturbs **every numeric column in two directions**, and uses a **unique
  per-cutoff window** to defeat replay. The one *inherent* limitation (a strategy that ignores its
  inputs and returns a precomputed array is invisible to any black-box perturbation gate) is
  **disclosed, not hidden**, with the structural mitigation (streaming holdout evaluation).
- **Data:** ~59k hourly bars (2019-09 → 2026-06) + funding / open-interest / mark-premium +
  1m/5m/15m sub-bars.

### 2.2 Agent scaffold — complete
- Minimal `Strategy` contract (`fit` / `positions` / declared `horizon`), two reference strategies
  (EMA-trend, XGB-momentum), and a one-command benchmark runner. Fork → improve the agent → run the
  referee → get a leaderboard row.

### 2.3 AutoResearch engine + Milestone 7 study — infrastructure complete, analysis in progress
- **M1–M6 (prior):** automated walk-forward search over features/labels/models with cost-aware
  labels and an overfitting-statistics layer (PSR, Deflated Sharpe, PBO-CSCV, MinTRL,
  block-bootstrap, CPCV).
- **M7 (trader-style, multi-horizon, scenario):** multi-timeframe features (intra-hour 1m/5m/15m +
  higher-TF 4h/1d), **multi-horizon path-aware labels** (return / direction / above-cost / MFE / MAE
  / triple-barrier TP-SL, horizons H ∈ {1, 4, 12, 24, 72} bars), **causal regimes** (trend /
  volatility / flow), a **scenario model bank**, and **trader-style decision policies** (trend-holding
  with invalidation, scenario-weighted sizing with hysteresis, meta-labeling, no-trade filters).
  **182 search trials** across staged search S1–S4 (targets → representations → policies → model
  families); baselines computed.

---

## 3. Preliminary findings
*(Selected from the 182 M7 trials; not yet multiple-testing-deflated; holdout sealed. OOS ≈ 2019–2025.)*

- **Best signal so far:** a **4-hour-horizon, cost-aware return regression** (XGBoost) on **1h price +
  funding/flow** features — net **+263%**, Sharpe **1.12**, MaxDD **−35%**, ~48% exposure, 146 trades.
  It beats the 1-bar-horizon variant and edges the strongest rule baseline
  (`rule_trend_hold`: net +155%, Sharpe 0.95, MaxDD −31%) and buy-&-hold (net +122%, Sharpe 0.67).
- **Horizon matters:** H=4 (4h) > H=1 and > H=72; predicting a few hours ahead with cost-aware sizing
  is the sweet spot.
- **Honest negatives (equally important):**
  - *Intra-hour micro-structure did not help* — `1h+flow` (Sharpe 1.12) **>** `mtf_full` with
    1m/5m/15m + 4h/1d (Sharpe 0.90). Adding finer timeframes **hurt**.
  - *Trader-style discretionary-mimicking policies mostly lost to transaction-cost churn.* The one
    survivor (a CatBoost regime/scenario "trend + no-trade" policy) had low MaxDD (−13%) and strong
    2025 Sharpe (2.0) but traded almost nothing (~1.6% exposure) — interesting, not yet usable.
- **The real test is deflation:** these trials sit on ~500 prior M5/M6 trials on the same OOS window
  (~680 cumulative). The **deflated** (DSR/PBO/CPCV) edge — not the raw Sharpe — decides whether
  anything is real. That robustness pass is **in progress** (stage 5).

---

## 4. What's next

### 4.1 Finish M7 (immediate)
- Complete the **stage-5 robustness rerank**: cost/execution/funding stress, block-bootstrap CIs,
  **family Deflated-Sharpe over the cumulative trial count**, PBO-CSCV, seed stability, CPCV.
- Fill the M7 report, answer the 10 milestone questions, freeze candidate configs, run an independent
  correctness audit.
- Emit a recommendation ∈ {READY_FOR_PRE_HOLDOUT_AUDIT, CONTINUE_SIGNAL_RESEARCH, NEEDS_RISK_REDUCTION,
  REJECT_ALL}. **The sealed holdout opens only if a candidate first passes a pre-holdout audit** — once.

### 4.2 Move ongoing research into the agent system (this repo)
- Re-express the promising signals (starting with the H=4 cost-aware regression) as **agent strategies
  here**, scored by the frozen referee — so every future improvement is automatically leakage-proof
  and comparable on the public leaderboard.
- Directions: sequence models (deferred so far), regime-conditional sizing, better no-trade / risk
  gating, execution realism, cross-validated meta-labeling.

---

## 5. Non-negotiable constraints
Backtesting research only (no live, no paper). Sealed holdout never opened during research. No future
leakage. No changes to the backtester / cost model / evaluation accounting to improve results.
Priority order: **correctness > causality > robustness > honest failure > net return.**

---

## 6. Open questions (where feedback would help most)
1. **Take it to holdout, or keep searching?** Is the H=4 cost-aware edge (Sharpe ~1.1, but selected
   from ~680 cumulative trials) worth the one-shot pre-holdout audit now, or should we demand a higher
   *deflated* bar first?
2. **Risk profile.** The best signal runs ~48% exposure with −35% MaxDD. Prefer that, the low-exposure
   (~2%) low-drawdown policy, or a blend? What MaxDD / exposure target is acceptable?
3. **Benchmark rigor vs. cost.** Is the disclosed "input-ignoring replay" limitation acceptable for a
   public referee, or should we add streaming (bar-by-bar) holdout evaluation to close it structurally?
4. **Scope.** Should all future research live in this agent repo (clean, comparable), keeping the
   monorepo only for heavy offline search?
