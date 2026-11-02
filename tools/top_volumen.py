"""Genera la lista fija del torneo: los 250 valores del S&P 500 con más volumen negociado
(en dólares: precio de cierre x acciones) en una sesión concreta.

Uso: python tools/top_volumen.py 2026-11-02
Escribe torneo/lista_fija.csv. Se ejecuta una sola vez; la lista queda fija para el torneo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from torneo.universe import SP500_SNAPSHOT  # noqa: E402

N = 250


def main(day: str):
    tickers = list(SP500_SNAPSHOT)
    raw = yf.download(tickers, start=pd.Timestamp(day) - pd.Timedelta(days=7),
                      end=pd.Timestamp(day) + pd.Timedelta(days=1), group_by="ticker",
                      auto_adjust=False, threads=True, progress=False)
    rows, missing = [], []
    for t in tickers:
        try:
            df = raw[t].dropna(how="all")
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            bar = df.loc[pd.Timestamp(day)]
            rows.append({"ticker": t, "cierre_usd": round(float(bar["Close"]), 2),
                         "acciones": int(bar["Volume"]),
                         "volumen_usd": round(float(bar["Close"]) * float(bar["Volume"]))})
        except Exception:  # noqa: BLE001
            missing.append(t)
    df = pd.DataFrame(rows).sort_values("volumen_usd", ascending=False).reset_index(drop=True)
    df.insert(0, "puesto", df.index + 1)
    df["fecha"] = day
    top = df.head(N)
    top.to_csv(ROOT / "torneo" / "lista_fija.csv", index=False)
    print(f"Sesión {day}: {len(rows)} valores con dato, {len(missing)} sin dato: {missing}")
    print(f"Puesto {N}: {top.iloc[-1].ticker} con {top.iloc[-1].volumen_usd / 1e6:,.0f} M$")
    print(top.head(10).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
