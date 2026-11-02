"""Indicadores técnicos calculados con pandas. Aquí no se adivina nada."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def macd(close: pd.Series, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["Close"].shift()
    return pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(),
                      (df["Low"] - prev).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up = df["High"].diff()
    down = -df["Low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(df).ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / tr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / tr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = sma(close, n)
    sd = close.rolling(n).std()
    return mid - k * sd, mid, mid + k * sd


def snapshot(df: pd.DataFrame) -> dict:
    """Todos los indicadores del último día de un valor, redondeados para el prompt."""
    df = df.dropna(subset=["Close"])
    c = df["Close"]
    m_line, m_sig, m_hist = macd(c)
    bb_lo, bb_mid, bb_hi = bollinger(c)
    a = atr(df)
    last = len(c) - 1
    turnover = (c * df["Volume"]).rolling(20).mean()
    out = {
        "close": c.iloc[-1],
        "chg_1d_pct": 100 * (c.iloc[-1] / c.iloc[-2] - 1),
        "chg_20d_pct": 100 * (c.iloc[-1] / c.iloc[-21] - 1),
        "sma20": sma(c, 20).iloc[-1],
        "sma50": sma(c, 50).iloc[-1],
        "sma200": sma(c, 200).iloc[-1],
        "rsi2": rsi(c, 2).iloc[-1],
        "rsi14": rsi(c, 14).iloc[-1],
        "macd": m_line.iloc[-1],
        "macd_signal": m_sig.iloc[-1],
        "macd_cross_up": bool(m_hist.iloc[-1] > 0 >= m_hist.iloc[-2]),
        "macd_hist": m_hist.iloc[-1],
        "adx14": adx(df).iloc[-1],
        "atr14": a.iloc[-1],
        "atr_pct": 100 * a.iloc[-1] / c.iloc[-1],
        "bb_lower": bb_lo.iloc[-1],
        "bb_upper": bb_hi.iloc[-1],
        "pct_b": (c.iloc[-1] - bb_lo.iloc[-1]) / (bb_hi.iloc[-1] - bb_lo.iloc[-1]),
        "donchian_high20_prev": df["High"].iloc[last - 20:last].max(),
        "breakout_20d": bool(c.iloc[-1] > df["High"].iloc[last - 20:last].max()),
        "avg_turnover_20d": turnover.iloc[-1],
    }
    return {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v)
            for k, v in out.items()}
