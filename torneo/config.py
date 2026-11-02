"""Reglamento del torneo. Todo lo que se pueda discutir en un bar, aquí."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
REPORTS_DIR = ROOT / "docs"   # "docs" para poder publicarlo con GitHub Pages
CACHE_DIR = ROOT / ".cache"

# --- Calendario --------------------------------------------------------------
START_DATE = "2026-11-03"   # primera sesión de decisión
END_DATE = "2026-12-03"     # ese día solo se ejecutan órdenes pendientes y se cierra el marcador

# --- Dinero ------------------------------------------------------------------
BASE_CCY = "EUR"
INITIAL_CAPITAL = 100_000.0     # por agente, en EUR
COMMISSION = 0.001              # 0,1% por operación (compra y venta)

# --- Reglas de juego (las hace cumplir el validador, no la buena fe) --------
MAX_OPS_PER_DAY = 5
MAX_POSITION_WEIGHT = 0.20      # 20% del valor de la cartera por posición
MAX_POSITIONS = 10
MIN_TRADE_EUR = 2_000           # nada de operaciones de calderilla
PENDING_ORDER_MAX_AGE = 3       # sesiones que una orden puede esperar (festivos) antes de cancelarse

# --- Universo ----------------------------------------------------------------
# "reducido": S&P 100 + NASDAQ-100 + EURO STOXX 50 + IBEX 35  (~230 valores únicos)
# "amplio":   S&P 500 + NASDAQ-100 + EURO STOXX 50 + IBEX 35  (~580 valores únicos)
UNIVERSE_MODE = "reducido"
MIN_AVG_TURNOVER_EUR = 20_000_000   # liquidez mínima: volumen medio diario de 20 días en EUR
HISTORY_PERIOD = "1y"               # suficiente para SMA 200

# --- Benchmark (compra y mantén, sin rebalanceo) -----------------------------
BENCHMARK = {"^GSPC": 0.75, "^STOXX50E": 0.25}   # 75% EE. UU. / 25% Europa
FX_TICKER = "EURUSD=X"                           # USD por 1 EUR

# --- Modelo ------------------------------------------------------------------
MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 6000
MAX_CANDIDATES = 15   # candidatos por agente que llegan al modelo (esto es lo que cuesta tokens)
