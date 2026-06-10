"""ML example: XGBoost next-1h return regression on trailing-return features + a cost-aware
position filter. Self-contained (no benchmark internals) and contract-honest:

  - features at t use ONLY rows <= t (trailing rolls/shifts)         -> future-perturbation gate OK
  - trained in fit() on rows [train_start, train_end) only           -> fold discipline
  - the position loop carries state from the PAST only               -> prefix gate OK

Upgrade ideas: richer features (aux funding/OI as-of joins), multi-horizon targets, better models,
regime gating, holding policies -- anything, as long as the gates stay green.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COST_DEC = 10.0 / 10000.0          # benchmark all-in cost (bps -> decimal); do NOT lower


def _features(candles: pd.DataFrame, upto: int) -> pd.DataFrame:
    c = pd.to_numeric(candles["close"].iloc[:upto], errors="coerce")
    v = pd.to_numeric(candles["volume"].iloc[:upto], errors="coerce")
    lr = np.log(c / c.shift(1))
    out = {f"lr_{w}": np.log(c / c.shift(w)) for w in (1, 3, 6, 12, 24, 48, 72)}
    out["vol_24"] = lr.rolling(24, min_periods=24).std()
    out["vol_72"] = lr.rolling(72, min_periods=72).std()
    ema24 = c.ewm(span=24, adjust=False, min_periods=24).mean()
    ema72 = c.ewm(span=72, adjust=False, min_periods=72).mean()
    out["ema_dist_24"] = c / ema24 - 1.0
    out["ema_dist_72"] = c / ema72 - 1.0
    out["rel_vol_24"] = v / v.rolling(24, min_periods=24).mean() - 1.0
    return pd.DataFrame(out)


class XgbMomentum:
    name = "xgb_momentum_costaware"
    horizon = 1

    def __init__(self, lam: float = 3.0, seed: int = 42):
        self.lam = lam
        self.seed = seed
        self.model = None

    def fit(self, data, train_start: int, train_end: int) -> None:
        import xgboost as xgb
        feat = _features(data.candles, train_end)
        close = pd.to_numeric(data.candles["close"].iloc[:train_end], errors="coerce").to_numpy()
        y = np.concatenate([np.log(close[1:] / close[:-1]), [np.nan]])     # next-1h log return
        X = feat.iloc[train_start:train_end].to_numpy("float64")
        yy = y[train_start:train_end]
        keep = np.isfinite(yy)
        self.model = xgb.XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05,
                                      subsample=0.8, colsample_bytree=0.8,
                                      random_state=self.seed, n_jobs=4)
        self.model.fit(X[keep], yy[keep])

    def positions(self, data, start: int, end: int) -> np.ndarray:
        feat = _features(data.candles, end)
        fc = self.model.predict(feat.iloc[start:end].to_numpy("float64"))
        out = np.zeros(end - start)
        cur = 0.0
        for t in range(end - start):                       # cost-aware long_cash filter (causal)
            f = float(fc[t])
            if not np.isfinite(f):
                out[t] = cur
                continue
            desired = 1.0 if f > 0 else 0.0
            if desired != cur and abs(f) > self.lam * abs(desired - cur) * COST_DEC:
                cur = desired
            out[t] = cur
        return out
