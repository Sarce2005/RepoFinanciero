"""Los dos analistas: prompt + llamada a la API de Claude (o un sustituto sin API para pruebas)."""
from __future__ import annotations

import json
import logging

import pandas as pd

from . import config
from .strategies import Strategy

log = logging.getLogger(__name__)

RULES = f"""
REGLAS DEL TORNEO (las verifica un validador automático; lo que las incumpla se rechaza):
- Solo acciones al contado y solo posiciones largas: BUY o SELL de lo que tengas. Nada de cortos,
  opciones, futuros ni apalancamiento.
- Máximo {config.MAX_OPS_PER_DAY} operaciones al día EN TOTAL. Los stops automáticos de hoy ya
  consumen huecos: te diré cuántos te quedan.
- Peso máximo por valor: {config.MAX_POSITION_WEIGHT:.0%} de la cartera. Máximo
  {config.MAX_POSITIONS} posiciones. Solo puedes comprar valores de tu lista de candidatos (o
  ampliar uno que ya tengas).
- Decides con el cierre de hoy y las órdenes se ejecutan a la apertura de la próxima sesión.
- Comisión del {config.COMMISSION:.1%} por operación: operar sin motivo cuesta dinero.
- Cada orden necesita una justificación concreta que cite los valores de los indicadores.
  Una persona va a leerla. Sé específico y breve (2-3 frases).

EXPLICA TU RAZONAMIENTO (quien te lee está aprendiendo cómo funciona el mercado):
- En cada orden, además de "reason" (técnica), rellena "en_sencillo": 1-2 frases sin jerga,
  como se lo explicarías a un amigo que empieza. Si usas un término (RSI, media móvil...),
  di en pocas palabras qué significa.
- En "revision_cartera" repasa TODAS tus posiciones abiertas, una por una: MANTENER, VENDER o
  AMPLIAR y por qué, con algún dato. Si vendes o amplías, la orden va también en "ordenes".
- En "descartes" explica en 1-3 frases por qué no compras los candidatos más tentadores que
  dejas fuera (o por qué hoy no compras nada).
- Compites contra otro analista con el método contrario y contra el {config.BENCHMARK_NAME}
  comprado y mantenido. Ganar es batir a ambos; no operar cuando no hay señal clara es una decisión válida.
"""

TOOL = {
    "name": "enviar_ordenes",
    "description": "Envía tu decisión del día: lectura del mercado y entre 0 y N órdenes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "lectura_mercado": {"type": "string",
                                "description": "2-3 frases sobre lo que ves hoy desde tu método."},
            "ordenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["BUY", "SELL"]},
                        "ticker": {"type": "string"},
                        "weight_pct": {"type": "number",
                                       "description": "BUY: % de la cartera a invertir (1-20)."},
                        "sell_fraction": {"type": "number",
                                          "description": "SELL: fracción de la posición (0.1-1)."},
                        "reason": {"type": "string",
                                   "description": "Justificación técnica citando indicadores."},
                        "en_sencillo": {"type": "string",
                                        "description": "La misma idea sin jerga, 1-2 frases."},
                    },
                    "required": ["action", "ticker", "reason", "en_sencillo"],
                },
            },
            "revision_cartera": {
                "type": "array",
                "description": "Una entrada por cada posición abierta (vacío si no tienes ninguna).",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "decision": {"type": "string", "enum": ["MANTENER", "VENDER", "AMPLIAR"]},
                        "motivo": {"type": "string"},
                    },
                    "required": ["ticker", "decision", "motivo"],
                },
            },
            "descartes": {"type": "string",
                          "description": "Por qué no compras los demás candidatos tentadores."},
        },
        "required": ["lectura_mercado", "ordenes", "revision_cartera", "descartes"],
    },
}

CAND_COLS = ["close", "chg_1d_pct", "chg_20d_pct", "sma20", "sma50", "sma200", "rsi2", "rsi14",
             "macd_hist", "macd_cross_up", "adx14", "atr_pct", "pct_b", "breakout_20d"]


def build_context(strategy: Strategy, date, equity: float, cash: float, positions_view: list[dict],
                  candidates: pd.DataFrame, stops: list[dict], slots: int) -> str:
    cand_csv = candidates[CAND_COLS].round(2).rename_axis("ticker").to_csv() if len(candidates) else "(ninguno hoy)"
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    d = pd.Timestamp(date)
    return f"""SESIÓN: {dias[d.weekday()]} {d:%d/%m/%Y} (datos al cierre)

TU CARTERA
- Valor total: {equity:,.0f} EUR | Liquidez: {cash:,.0f} EUR ({100 * cash / equity:.1f}%)
- Posiciones:
{json.dumps(positions_view, ensure_ascii=False, indent=1) if positions_view else "  (ninguna)"}

STOPS AUTOMÁTICOS QUE SE EJECUTARÁN MAÑANA (no los repitas):
{json.dumps(stops, ensure_ascii=False) if stops else "  (ninguno)"}

OPERACIONES DISPONIBLES HOY: {slots}

CANDIDATOS QUE CUMPLEN EL CRIBADO DE TU MÉTODO (precios en divisa local):
{cand_csv}
Decide y llama a la herramienta enviar_ordenes."""


def decide_llm(strategy: Strategy, context: str) -> tuple[dict, dict]:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=strategy.prompt + "\n" + RULES,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "enviar_ordenes"},
        messages=[{"role": "user", "content": context}],
    )
    block = next(b for b in msg.content if b.type == "tool_use")
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    return block.input, usage


def decide_rules(strategy: Strategy, positions_view: list[dict], candidates: pd.DataFrame,
                 slots: int) -> tuple[dict, dict]:
    """Sustituto determinista para probar el sistema sin gastar API."""
    orders, review = [], []
    for p in positions_view:
        if p["senales_salida"]:
            orders.append({"action": "SELL", "ticker": p["ticker"],
                           "reason": "[dry-run] " + "; ".join(p["senales_salida"]),
                           "en_sencillo": "[dry-run] la señal de salida de su método se ha activado"})
            review.append({"ticker": p["ticker"], "decision": "VENDER",
                           "motivo": "[dry-run] " + "; ".join(p["senales_salida"])})
        else:
            review.append({"ticker": p["ticker"], "decision": "MANTENER",
                           "motivo": f"[dry-run] sin señal de salida (rent. {p['rent_pct']:+.1f}%)"})
    held = {p["ticker"] for p in positions_view}
    for t, row in candidates.iterrows():
        if t not in held:
            orders.append({"action": "BUY", "ticker": t, "weight_pct": 10,
                           "reason": f"[dry-run] candidato con score {row['score']:.1f}",
                           "en_sencillo": "[dry-run] es de los que mejor encajan con su método hoy"})
    return {"lectura_mercado": "[dry-run] decisión por reglas, sin modelo",
            "ordenes": orders[:slots], "revision_cartera": review,
            "descartes": "[dry-run] se descartan los que no caben en los huecos del día"}, \
        {"input_tokens": 0, "output_tokens": 0}
