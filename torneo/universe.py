"""Universo de valores invertibles (tickers en formato Yahoo Finance).

Los índices de EE. UU. se descargan de Wikipedia y se cachean en .cache/universe.csv.
Para el S&P 500 hay tres redes: Wikipedia -> CSV público en GitHub (datasets/s-and-p-500-companies)
-> copia fija de los 503 valores incluida aquí. Para el Nasdaq-100: Wikipedia -> lista de respaldo. Las listas europeas están escritas a mano:
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

# Copia fija del S&P 500 (503 valores, fuente: datasets/s-and-p-500-companies, última alta
# 06/10/2026). Solo se usa si fallan Wikipedia y GitHub.
SP500_SNAPSHOT = """
A AAPL ABBV ABNB ABT ACGL ACN ADBE ADI ADM ADP ADSK AEE AEP AES AFL AIG AIZ AJG AKAM ALB ALGN
ALL ALLE AMAT AMCR AMD AME AMGN AMP AMT AMZN ANET AON AOS APA APD APH APO APP APTV ARE ARES ATO
AVGO AVY AWK AXON AXP AZO BA BAC BALL BAX BBY BDX BE BEN BF-B BG BIIB BKNG BKR BLK BMY BNY BR
BRK-B BRO BSX BX BXP C CAH CARR CASY CAT CB CBOE CBRE CCI CCL CDNS CDW CEG CF CFG CHD CHRW CHTR
CI CIEN CINF CL CLX CMCSA CME CMG CMI CMS CNC CNP COF COHR COIN COO COP COR COST CPAY CPRT CPT
CRH CRL CRM CRWD CSCO CSGP CSX CTAS CTSH CVNA CVS CVX D DAL DASH DD DDOG DE DECK DELL DG DGX
DHI DHR DIS DLR DLTR DOC DOV DOW DPZ DRI DTE DUK DVA DVN DXCM EBAY ECHO ECL ED EFX EG EIX EL
ELV EME EMR EOG EQIX EQT ERIE ES ESS ETN ETR EVRG EW EXC EXE EXPD EXPE EXR F FANG FAST FCX FDS
FDX FDXF FE FERG FFIV FICO FIS FISV FITB FIX FLEX FOX FOXA FRT FSLR FTNT FTV GD GDDY GE GEHC
GEN GEV GILD GIS GL GLW GM GNRC GOOG GOOGL GPC GPN GRMN GS GWW HAL HAS HBAN HCA HD HIG HII HLT
HON HONA HOOD HPE HPQ HRL HSIC HST HSY HUBB HUM HWM IBKR IBM ICE IDXX IEX IFF ILMN INCY INTC
INTU INVH IP IQV IR IRM ISRG IT ITW IVZ J JBHT JBL JCI JKHY JNJ JPM KDP KEY KEYS KHC KIM KKR
KLAC KMB KMI KO KR KVUE L LDOS LEN LH LHX LII LIN LITE LLY LMT LNT LOW LRCX LULU LUV LVS LYB
LYV MA MAA MAR MAS MCD MCHP MCK MCO MDLZ MDT MET META MGM MKC MLM MMM MNST MO MOS MPC MPWR MRK
MRNA MRSH MRVL MS MSCI MSFT MSI MTB MTD MU NCLH NDAQ NDSN NEE NEM NFLX NI NKE NOC NOW NRG NSC
NTAP NTRS NUE NVDA NVR NWS NWSA NXPI O ODFL OKE OMC ON ORCL ORLY OTIS OXY P PANW PAYX PCAR PCG
PEG PEP PFE PFG PG PGR PH PHM PKG PLD PLTR PM PNC PNR PNW PODD PPG PPL PRU PSA PSX PTC PWR PYPL
Q QCOM RCL RDDT REG REGN RF RJF RL RMD ROK ROL ROP ROST RSG RTX RVTY SBAC SBUX SCHW SHW SJM
SKYD SLB SMCI SNA SNDK SNPS SO SOLV SPG SPGI SRE STE STLD STT STX STZ SW SWK SWKS SYF SYK SYY T
TDG TDY TECH TEL TER TFC TGT TJX TKO TMO TMUS TPL TPR TRGP TRMB TROW TRV TSCO TSLA TSN TT TTWO
TWLO TXN TXT TYL UAL UBER UDR UHS ULTA UNH UNP UPS URI USB V VEEV VICI VLO VLTO VMC VMRK VRSK
VRSN VRT VRTX VST VTR VTRS VYLR VZ WAB WAT WDAY WDC WEC WELL WFC WM WMB WMT WRB WSM WST WTW WY
WYNN XEL XOM XYL XYZ YUM ZBH ZBRA ZTS
""".split()

SP500_GITHUB_CSV = ("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
                    "main/data/constituents.csv")

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


def _github_sp500() -> list[str]:
    import requests

    text = requests.get(SP500_GITHUB_CSV, timeout=20).text
    df = pd.read_csv(io.StringIO(text))
    tickers = [str(t).strip().replace(".", "-") for t in df["Symbol"].dropna()]
    if len(tickers) < 450:
        raise ValueError(f"lista sospechosamente corta ({len(tickers)})")
    return tickers


def _index_tickers(key: str) -> list[str]:
    """Una lista de índice con sus redes de seguridad. Nunca falla."""
    try:
        t = _wiki_tickers(key)
        log.info("%s: %d tickers de Wikipedia", key, len(t))
        return t
    except Exception as exc:  # noqa: BLE001
        log.warning("%s: Wikipedia no disponible (%s)", key, exc)
    if key == "sp500":
        try:
            t = _github_sp500()
            log.info("sp500: %d tickers del CSV de GitHub", len(t))
            return t
        except Exception as exc:  # noqa: BLE001
            log.warning("sp500: GitHub no disponible (%s); uso la copia fija", exc)
        return list(SP500_SNAPSHOT)
    log.warning("%s: uso la lista de respaldo", key)
    return list(US_FALLBACK)


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
    europe = [] if config.UNIVERSE_MODE == "usa" else EUROSTOXX50 + IBEX35
    us: list[str] = []
    for k in us_keys:
        us += _index_tickers(k)
    log.info("Universo EE. UU.: %d tickers únicos", len(set(us)))

    tickers = sorted(set(us) | set(europe))
    df = pd.DataFrame({"ticker": tickers})
    df["market"] = df["ticker"].map(_market)
    df["ccy"] = df["market"].map(lambda m: "USD" if m == "US" else "EUR")
    config.CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(cache, index=False)
    return df
