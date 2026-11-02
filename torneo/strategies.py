"""Los dos métodos. El cribado y los stops son código; el criterio final es del agente."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config
from .indicators import atr


@dataclass
class Strategy:
    key: str
    name: str
    method: str
    prompt: str

    # --- cribado de entradas -------------------------------------------------
    def screen(self, snaps: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    # --- salidas -------------------------------------------------------------
    def mandatory_exit(self, pos: dict, hist: pd.DataFrame, snap: dict) -> str | None:
        """Stop obligatorio: devuelve el motivo o None. Lo ejecuta el código, no el agente."""
        raise NotImplementedError

    def exit_signals(self, pos: dict, snap: dict) -> list[str]:
        """Señales de salida opcionales: se le muestran al agente, decide él."""
        raise NotImplementedError


class TrendFollower(Strategy):
    def screen(self, s: pd.DataFrame) -> pd.DataFrame:
        trend = (s.close > s.sma50) & (s.sma50 > s.sma200) & (s.adx14 > 25)
        trigger = s.breakout_20d | s.macd_cross_up | (s.macd_hist > 0)
        out = s[trend & trigger].copy()
        out["score"] = out.adx14 + out.chg_20d_pct + 10 * out.breakout_20d.astype(int)
        return out.sort_values("score", ascending=False).head(config.MAX_CANDIDATES)

    def mandatory_exit(self, pos, hist, snap):
        since = hist.loc[pos["entry_date"]:, "Close"]
        if since.empty:
            return None
        peak = since.max()
        stop = peak - 2 * atr(hist).iloc[-1]
        if snap["close"] < stop:
            return (f"Trailing stop 2xATR: cierre {snap['close']:.2f} < {stop:.2f} "
                    f"(máximo desde la entrada {peak:.2f})")
        return None

    def exit_signals(self, pos, snap):
        sig = []
        if snap["close"] < snap["sma50"]:
            sig.append("cierre por debajo de la SMA50 (tendencia rota)")
        if snap["macd_hist"] < 0:
            sig.append("histograma MACD negativo")
        if snap["adx14"] < 20:
            sig.append("ADX < 20 (la tendencia se apaga)")
        return sig


class MeanReversion(Strategy):
    def screen(self, s: pd.DataFrame) -> pd.DataFrame:
        healthy = s.close > s.sma200
        oversold = (s.rsi2 < 10) | (s.rsi14 < 30) | (s.pct_b < 0)
        out = s[healthy & oversold].copy()
        out["score"] = -out.rsi2 - 20 * out.pct_b
        return out.sort_values("score", ascending=False).head(config.MAX_CANDIDATES)

    def mandatory_exit(self, pos, hist, snap):
        loss = snap["close"] / pos["entry_price"] - 1
        if loss <= -0.08:
            return f"Stop fijo -8%: {100 * loss:.1f}% desde la entrada a {pos['entry_price']:.2f}"
        return None

    def exit_signals(self, pos, snap):
        sig = []
        if snap["close"] > snap["sma20"]:
            sig.append("ha vuelto por encima de la SMA20 (objetivo de reversión cumplido)")
        if snap["rsi14"] > 70:
            sig.append("RSI14 > 70 (sobrecompra)")
        if snap["close"] < snap["sma200"]:
            sig.append("ha perdido la SMA200 (la tesis de 'sana pero castigada' ya no vale)")
        return sig


SURFISTA = TrendFollower(
    key="A",
    name="El Surfista",
    method="Seguimiento de tendencia (momentum)",
    prompt="""Eres "El Surfista", un analista técnico de seguimiento de tendencia.

TU HIPÓTESIS: los precios que llevan una tendencia sólida tienden a mantenerla (momentum de
series temporales, Moskowitz-Ooi-Pedersen 2012; práctica de los fondos CTA). No intentas
adivinar giros: te subes a la ola y te bajas cuando rompe.

TUS HERRAMIENTAS: SMA 50 y SMA 200 (estructura de tendencia), ADX 14 (fuerza de la tendencia,
>25 = hay tendencia), MACD 12/26/9 (impulso), ruptura del máximo de 20 días (canal de Donchian),
ATR 14 (volatilidad, para dimensionar y para el trailing stop).

CÓMO DECIDES:
- Compras valores en tendencia alcista confirmada, preferiblemente con ruptura reciente o cruce
  alcista del MACD. Cuanto mayor el ADX, más convicción.
- Dimensionas según volatilidad: con ATR% alto, peso menor.
- Vendes cuando la tendencia se rompe (cierre bajo la SMA50, MACD negativo, ADX apagándose).
  El trailing stop de 2xATR lo ejecuta el sistema automáticamente.
- Prefieres pocas posiciones con convicción a muchas tibias. No operar es válido.""",
)

CONTRARIAN = MeanReversion(
    key="B",
    name="El Contrarian",
    method="Reversión a la media",
    prompt="""Eres "El Contrarian", un analista técnico de reversión a la media.

TU HIPÓTESIS: a corto plazo los excesos se corrigen. Una empresa sana (por encima de su SMA 200)
que sufre una caída brusca de pocos días tiende a rebotar hacia su media (efecto de reversión a
corto plazo; estrategias tipo Connors RSI(2)). Compras miedo puntual, no hundimientos estructurales.

TUS HERRAMIENTAS: RSI 2 (<10 = sobreventa extrema), RSI 14 (<30 = sobreventa), Bandas de
Bollinger 20/2 (%B < 0 = por debajo de la banda inferior), SMA 200 (filtro de salud: solo compras
por encima), SMA 20 (objetivo de salida).

CÓMO DECIDES:
- Compras valores por encima de su SMA 200 con sobreventa marcada. Cuanto más extrema, más
  convicción, pero desconfía si la caída parece estructural (caída de 20 días muy grande).
- Vendes cuando el precio vuelve a la SMA 20 o el RSI14 pasa de 70: recoges el rebote y no te
  enamoras. El stop fijo de -8% lo ejecuta el sistema automáticamente.
- Diversificas un poco más que un seguidor de tendencia: tus operaciones son cortas y numerosas.
  No operar es válido.""",
)

STRATEGIES = {"A": SURFISTA, "B": CONTRARIAN}
