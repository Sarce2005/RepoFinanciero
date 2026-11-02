"""Descarga de precios (yfinance) y un generador sintético para probar sin red."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)
FIELDS = ["Open", "High", "Low", "Close", "Volume"]


class MarketData:
    """Contenedor: precios por ticker + tipo de cambio + benchmark."""

    def __init__(self, prices: dict[str, pd.DataFrame], fx: pd.Series, bench: pd.DataFrame,
                 meta: pd.DataFrame):
        self.prices = prices          # ticker -> DataFrame[Open, High, Low, Close, Volume]
        self.fx = fx                  # USD por EUR, indexado por fecha
        self.bench = bench            # cierres de los índices del benchmark
        self.meta = meta.set_index("ticker")
        self.as_of = max(df.index[-1] for df in prices.values())

    def ccy(self, ticker: str) -> str:
        return self.meta.loc[ticker, "ccy"] if ticker in self.meta.index else "EUR"

    def fx_on(self, date) -> float:
        s = self.fx.loc[:date].dropna()
        return float(s.iloc[-1])

    def to_eur(self, ticker: str, amount: float, date) -> float:
        return amount / self.fx_on(date) if self.ccy(ticker) == "USD" else amount

    def bar(self, ticker: str, date) -> pd.Series | None:
        """Vela de ese día o None si ese mercado no abrió (festivo) o no hay dato."""
        df = self.prices.get(ticker)
        if df is None or date not in df.index:
            return None
        row = df.loc[date]
        return None if pd.isna(row["Open"]) or pd.isna(row["Close"]) else row

    def last_close(self, ticker: str, date) -> float | None:
        df = self.prices.get(ticker)
        if df is None:
            return None
        s = df["Close"].loc[:date].dropna()
        return float(s.iloc[-1]) if len(s) else None

    def truncate(self, date) -> "MarketData":
        """Vista de los datos hasta `date` incluida (para simular sin mirar el futuro)."""
        prices = {t: df.loc[:date] for t, df in self.prices.items() if len(df.loc[:date])}
        md = MarketData(prices, self.fx.loc[:date], self.bench.loc[:date], self.meta.reset_index())
        return md


def download(universe: pd.DataFrame) -> MarketData:
    import yfinance as yf

    tickers = universe["ticker"].tolist()
    log.info("Descargando %d tickers de Yahoo Finance...", len(tickers))
    raw = yf.download(tickers, period=config.HISTORY_PERIOD, group_by="ticker",
                      auto_adjust=True, threads=True, progress=False)
    prices: dict[str, pd.DataFrame] = {}
    missing = []
    for t in tickers:
        try:
            df = raw[t][FIELDS].dropna(how="all")
        except KeyError:
            df = pd.DataFrame()
        if len(df) < 210:   # sin historia suficiente para la SMA 200
            missing.append(t)
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        prices[t] = df
    if missing:
        log.warning("Descartados %d tickers sin datos suficientes: %s", len(missing),
                    ", ".join(missing[:20]) + ("..." if len(missing) > 20 else ""))

    extra = yf.download([config.FX_TICKER, *config.BENCHMARK], period=config.HISTORY_PERIOD,
                        auto_adjust=True, progress=False)["Close"]
    extra.index = pd.to_datetime(extra.index).tz_localize(None).normalize()
    fx = extra[config.FX_TICKER].ffill()
    bench = extra[list(config.BENCHMARK)].ffill()
    meta = universe[universe["ticker"].isin(prices)]
    return MarketData(prices, fx, bench, meta)


def synthetic(n_us: int = 60, n_eu: int = 40, days: int = 300, seed: int = 7) -> MarketData:
    """Mercado de mentira con regímenes de tendencia y de rango, para tests."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp(config.END_DATE), periods=days)
    prices, rows = {}, []
    for i in range(n_us + n_eu):
        t = f"US{i:03d}" if i < n_us else f"EU{i:03d}.PA"
        drift = rng.normal(0.0004, 0.0012)
        vol = rng.uniform(0.012, 0.03)
        # régimen: tramos con deriva distinta para que haya tendencias y rangos
        regime = np.repeat(rng.normal(0, 0.0015, days // 40 + 1), 40)[:days]
        rets = rng.normal(drift + regime, vol)
        close = 50 * np.exp(np.cumsum(rets))
        open_ = close * np.exp(rng.normal(0, vol / 3, days))
        high = np.maximum(open_, close) * (1 + rng.uniform(0, vol, days))
        low = np.minimum(open_, close) * (1 - rng.uniform(0, vol, days))
        volume = rng.uniform(1e6, 5e6, days)
        df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                           "Volume": volume}, index=idx)
        if i >= n_us:   # un festivo europeo de pega para probar órdenes pendientes
            df.loc[idx[-10]] = np.nan
        prices[t] = df
        rows.append({"ticker": t, "market": "US" if i < n_us else "EUROSTOXX",
                     "ccy": "USD" if i < n_us else "EUR"})
    fx = pd.Series(1.08 + np.cumsum(rng.normal(0, 0.003, days)), index=idx)
    bench = pd.DataFrame({k: 4000 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, days)))
                          for k in config.BENCHMARK}, index=idx)
    return MarketData(prices, fx, bench, pd.DataFrame(rows))
