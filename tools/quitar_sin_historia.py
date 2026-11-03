"""Quita de torneo/lista_fija.csv los valores sin un año de historia (menos de 210 sesiones),
con el mismo criterio que aplica torneo/data.py. Uso: python tools/quitar_sin_historia.py"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

LISTA = Path(__file__).resolve().parents[1] / "torneo" / "lista_fija.csv"
MIN_SESIONES = 210


def main():
    df = pd.read_csv(LISTA)
    tickers = df["ticker"].tolist()
    raw = yf.download(tickers, period="1y", group_by="ticker", auto_adjust=True,
                      threads=True, progress=False)
    sesiones = {}
    for t in tickers:
        try:
            sesiones[t] = int(raw[t]["Close"].dropna().shape[0])
        except KeyError:
            sesiones[t] = 0
    fuera = sorted(t for t, n in sesiones.items() if n < MIN_SESIONES)
    for t in fuera:
        print(f"FUERA {t}: {sesiones[t]} sesiones")
    df[~df["ticker"].isin(fuera)].to_csv(LISTA, index=False)
    print(f"Quedan {len(df) - len(fuera)} de {len(df)} valores")


if __name__ == "__main__":
    main()
