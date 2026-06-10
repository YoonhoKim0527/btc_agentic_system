"""Minimal honest example: long when close > trailing EMA(span) — no model, no aux.

Demonstrates the contract: positions(start, end) uses only trailing information (ewm is causal),
so the benchmark's gates pass. Upgrade ideas: regime filters, multi-TF confirmation, vol scaling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class EmaTrend:
    name = "ema_trend_48"
    horizon = 1

    def __init__(self, span: int = 48):
        self.span = span
        self.name = f"ema_trend_{span}"

    def fit(self, data, train_start: int, train_end: int) -> None:
        pass                                              # rule-based: nothing to fit

    def positions(self, data, start: int, end: int) -> np.ndarray:
        close = pd.to_numeric(data.candles["close"].iloc[:end], errors="coerce")
        ema = close.ewm(span=self.span, adjust=False, min_periods=self.span).mean()
        pos = (close > ema).astype(float).where(ema.notna(), 0.0).to_numpy()
        return pos[start:end]
