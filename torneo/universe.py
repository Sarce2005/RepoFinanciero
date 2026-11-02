"""Universo de valores invertibles (tickers en formato Yahoo Finance).

Los índices de EE. UU. se descargan de Wikipedia y se cachean en .cache/universe.csv.
Si Wikipedia falla, se usa una lista de respaldo. Las listas europeas están escritas a mano:
revísalas de vez en cuando, los índices cambian de composición. Un ticker que ya no exista
no rompe nada: data.py lo descarta y lo dice.
"""
from __future__ import annotations

import io
import logging

import pandas as pd

from . import config

log = logging.getLogger(__name__)

# EURO STOXX 50 (composición aproximada, 2026)
EUROSTOXX50 = [
    "ADS.DE", "ADYEN.AS", "AD.AS", "AI.PA", "AIR.PA", "ALV.DE", "ABI.BR", "ASML.AS", "CS.PA",
    "BAS.DE", "BAYN.DE", "SAN.MC", "BBVA.MC", "BMW.DE", "BNP.PA", "BN.PA", "DB1.DE", "DBK.DE",
    "DHL.DE", "DTE.DE", "ENEL.MI", "ENI.MI", "EL.PA", "RACE.MI", "IBE.MC", "ITX.MC", "IFX.DE",
    "INGA.AS", "ISP.MI", "OR.PA", "MC.PA", "MBG.DE", "MUV2.DE", "NDA-FI.HE", "PRX.AS",
    "RMS.PA", "RHM.DE", "SAF.PA", "SAN.PA", "SAP.DE", "SU.PA", "SIE.DE", "ENR.DE", "STLAM.MI",
    "TTE.PA", "UCG.MI", "DG.PA", "VOW3.DE", "WKL.AS", "NOKIA.HE",
]

# IBEX 35 (composición aproximada, 2026)
IBEX35 = [
    "ANA.MC", "ANE.MC", "ACX.MC", "ACS.MC", "AENA.MC", "AMS.MC", "MTS.MC", "SAB.MC", "SAN.MC",
    "BKT.MC", "BBVA.MC", "CABK.MC", "CLNX.MC", "ENG.MC", "ELE.MC", "FER.MC", "FDR.MC",
    "GRF.MC", "IAG.MC", "IBE.MC", "ITX.MC", "IDR.MC", "COL.MC", "LOG.MC", "MAP.MC", "MRL.MC",
    "NTGY.MC", "PUIG.MC", "RED.MC", "REP.MC", "ROVI.MC", "SCYR.MC", "SLR.MC", "TEF.MC", "UNI.MC",
]

# Respaldo de EE. UU. si Wikipedia no responde (aprox. S&P 100 + NASDAQ-100)
US_FALLBACK = """
AAPL ABBV ABT ACN ADBE AIG AMD AMGN AMT AMZN AVGO AXP BA BAC BK BKNG BLK BMY BRK-B C CAT CHTR
CL CMCSA COF COP COST CRM CSCO CVS CVX DE DHR DIS DUK EMR F FDX GD GE GILD GM GOOG GOOGL GS HD
HON IBM INTC INTU ISRG JNJ JPM KO LIN LLY LMT LOW MA MCD MDLZ MDT MET META MMM MO MRK MS MSFT
NEE NFLX NKE NOW NVDA ORCL PEP PFE PG PLTR PM PYPL QCOM RTX SBUX SCHW SO SPG T TGT TMO TMUS
TSLA TXN UBER UNH UNP UPS USB V VZ WFC WMT XOM
ABNB ADI ADP ADSK AEP AMAT APP ARM ASML AXON AZN BKR CCEP CDNS CEG CPRT CRWD CSGP CSX CTAS
CTSH DASH DDOG DXCM EA EXC FANG FAST FTNT GEHC GFS IDXX KDP KHC KLAC LRCX LULU MAR MCHP MDB
MELI MNST MRVL MSTR MU NXPI ODFL ON ORLY PANW PAYX PCAR PDD REGN ROP ROST SHOP SNPS TEAM TTD
TTWO VRSK VRTX WBD WDAY XEL ZS
""".split()

WIKI = {
    "sp100": ("https://en.wikipedia.org/wiki/S%26P_100", "Symbol"),
    "sp500": ("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", "Symbol"),
    "ndx": ("https://en.wikipedia.org/wiki/Nasdaq-100", "Ticker"),
}


def _wiki_tickers(key: str) -> list[str]:
    import requests

    url, col = WIKI[key]
    html = requests.get(url, headers={"User-Agent": "torneo-bolsa/1.0"}, timeout=20).text
    for table in pd.read_html(io.StringIO(html)):
        if col in table.columns:
            return [str(t).strip().replace(".", "-") for t in table[col].dropna()]
    raise ValueError(f"No encuentro la columna {col} en {url}")


def _market(ticker: str) -> str:
    if ticker.endswith(".MC"):
        return "IBEX"
    if "." in ticker and not ticker.endswith("-B"):
        return "EUROSTOXX"
    return "US"


def load_universe(refresh: bool = False) -> pd.DataFrame:
    """Devuelve un DataFrame con columnas ticker, market, ccy."""
    cache = config.CACHE_DIR / f"universe_{config.UNIVERSE_MODE}.csv"
    if cache.exists() and not refresh:
        return pd.read_csv(cache)

    us_keys = ["sp100", "ndx"] if config.UNIVERSE_MODE == "reducido" else ["sp500", "ndx"]
    us: list[str] = []
    try:
        for k in us_keys:
            us += _wiki_tickers(k)
        log.info("Universo EE. UU. descargado de Wikipedia: %d tickers", len(set(us)))
    except Exception as exc:  # noqa: BLE001
        log.warning("Wikipedia no disponible (%s); uso la lista de respaldo", exc)
        us = US_FALLBACK

    tickers = sorted(set(us) | set(EUROSTOXX50) | set(IBEX35))
    df = pd.DataFrame({"ticker": tickers})
    df["market"] = df["ticker"].map(_market)
    df["ccy"] = df["market"].map(lambda m: "USD" if m == "US" else "EUR")
    config.CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(cache, index=False)
    return df
