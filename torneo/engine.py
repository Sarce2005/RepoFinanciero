"""Un día de torneo: ejecutar lo pendiente, valorar, decidir, validar, registrar."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from . import config
from .agents import build_context, decide_llm, decide_rules
from .data import MarketData
from .indicators import snapshot
from .portfolio import Portfolio, _d
from .strategies import STRATEGIES

log = logging.getLogger(__name__)


class Benchmark:
    """Compra y mantén el índice de referencia desde el cierre del primer día del torneo."""

    def __init__(self, state_dir: Path):
        self.path = state_dir / "benchmark.json"
        self.s = json.loads(self.path.read_text()) if self.path.exists() else None

    def mark(self, md: MarketData, date) -> float:
        fx = md.fx_on(date)
        px = md.bench.loc[:date].iloc[-1]
        if self.s is None:
            units = {}
            for idx, w in config.BENCHMARK.items():
                eur = config.INITIAL_CAPITAL * w
                local = eur * fx if idx == "^GSPC" else eur
                units[idx] = local / float(px[idx])
            self.s = {"start": _d(date), "units": units}
            self.path.write_text(json.dumps(self.s, indent=2))
        value = 0.0
        for idx, u in self.s["units"].items():
            local = u * float(px[idx])
            value += local / fx if idx == "^GSPC" else local
        return value


def _snapshots(md: MarketData, date) -> pd.DataFrame:
    rows = {}
    for t, df in md.prices.items():
        if md.bar(t, date) is None:   # sin sesión hoy: no se ofrece como candidato
            continue
        snap = snapshot(df.loc[:date])
        snap["turnover_eur"] = md.to_eur(t, snap["avg_turnover_20d"], date)
        rows[t] = snap
    s = pd.DataFrame.from_dict(rows, orient="index")
    return s[s.turnover_eur >= config.MIN_AVG_TURNOVER_EUR]


def run_day(md: MarketData, state_dir: Path, dry_run: bool = False) -> dict | None:
    date = md.as_of
    if date < pd.Timestamp(config.START_DATE):
        log.info("%s es anterior al inicio del torneo (%s): nada que hacer", _d(date),
                 config.START_DATE)
        return None
    state_dir.mkdir(parents=True, exist_ok=True)
    ports = {k: Portfolio(k, state_dir) for k in STRATEGIES}
    if all(p.s["last_run"] == _d(date) for p in ports.values()):
        log.info("La sesión %s ya está procesada; no repito", _d(date))
        return None

    end = pd.Timestamp(config.END_DATE)
    if date > end and all((p.s["last_run"] or "") >= _d(end) for p in ports.values()):
        log.info("El torneo terminó el %s. Marcador final en el informe.", config.END_DATE)
        return None
    closing = date >= end
    snaps = None if closing else _snapshots(md, date)
    summary = {"date": _d(date), "agents": {}}

    for key, strat in STRATEGIES.items():
        p = ports[key]
        fills = p.execute_pending(md, date)
        eq = p.mark_to_market(md, date)
        day = {"fills": fills, "equity": eq, "stops": [], "accepted": [], "rejected": [],
               "lectura": "", "usage": {}}
        if not closing:
            day.update(_decide(p, strat, md, date, snaps, eq, dry_run))
        p.s["last_run"] = _d(date)
        p.save()
        summary["agents"][key] = day
        log.info("%s %s: %.0f EUR | ejecutadas %d | nuevas órdenes %d (+%d stops) | rechazadas %d",
                 _d(date), strat.name, eq, sum(f["status"] == "EJECUTADA" for f in fills),
                 len(day["accepted"]), len(day["stops"]), len(day["rejected"]))

    bench_eq = Benchmark(state_dir).mark(md, date)
    Portfolio("BENCH", state_dir)._append_csv("equity.csv", {
        "date": _d(date), "agent": "BENCH", "equity_eur": round(bench_eq, 2),
        "cash_eur": 0, "n_positions": len(config.BENCHMARK)})
    summary["bench"] = bench_eq
    return summary


def _decide(p: Portfolio, strat, md: MarketData, date, snaps: pd.DataFrame, eq: float,
            dry_run: bool) -> dict:
    # 1) stops obligatorios (los aplica el código y consumen huecos del día)
    pending_sells = {o["ticker"] for o in p.s["pending"] if o["action"] == "SELL"}
    stops, view = [], []
    weights = p.weights(md, date)
    for t, pos in list(p.positions.items()):
        hist = md.prices[t].loc[:date].dropna(subset=["Close"])
        snap = snapshot(hist)
        reason = strat.mandatory_exit(pos, hist, snap)
        if reason and t not in pending_sells and len(stops) < config.MAX_OPS_PER_DAY:
            o = p.queue("SELL", t, reason, date, kind="stop")
            stops.append({"ticker": t, "motivo": reason, "id": o["id"]})
            pending_sells.add(t)
            continue
        view.append({
            "ticker": t, "acciones": pos["shares"], "entrada": round(pos["entry_price"], 2),
            "fecha_entrada": pos["entry_date"], "cierre": round(snap["close"], 2),
            "rent_pct": round(100 * (snap["close"] / pos["entry_price"] - 1), 2),
            "peso_pct": round(100 * weights.get(t, 0), 1),
            "rsi14": round(snap["rsi14"], 1), "adx14": round(snap["adx14"], 1),
            "sma20": round(snap["sma20"], 2), "sma50": round(snap["sma50"], 2),
            "senales_salida": strat.exit_signals(pos, snap),
            "venta_pendiente": t in pending_sells,
        })

    slots = max(0, config.MAX_OPS_PER_DAY - len(stops))
    cands = strat.screen(snaps)
    out = {"stops": stops, "accepted": [], "rejected": [], "lectura": "", "usage": {},
           "n_candidates": len(cands), "revision": [], "descartes": "",
           "cartera": [{"ticker": v["ticker"], "rent_pct": v["rent_pct"], "peso_pct": v["peso_pct"],
                        "fecha_entrada": v["fecha_entrada"]} for v in view]}
    if slots == 0:
        out["lectura"] = "Sin huecos: los stops automáticos han consumido las 5 operaciones."
    else:
        if dry_run:
            decision, usage = decide_rules(strat, view, cands, slots)
        else:
            ctx = build_context(strat, date, eq, p.s["cash"], view, cands, stops, slots)
            decision, usage = decide_llm(strat, ctx)
        accepted, rejected = p.validate(decision.get("ordenes", []), slots, set(cands.index),
                                        pending_sells, md, date)
        for a in accepted:
            p.queue(a["action"], a["ticker"], a["reason"], date,
                    weight=a.get("weight", 0), fraction=a.get("fraction", 1.0),
                    plain=a.get("en_sencillo", ""))
        out.update(accepted=accepted, rejected=rejected, usage=usage,
                   lectura=decision.get("lectura_mercado", ""),
                   revision=decision.get("revision_cartera", []) or [],
                   descartes=decision.get("descartes", "") or "")

    p.log_decision({"date": _d(date), "lectura": out["lectura"], "stops": stops,
                    "aceptadas": out["accepted"], "rechazadas": out["rejected"],
                    "revision_cartera": out["revision"], "descartes": out["descartes"],
                    "cartera": out["cartera"],
                    "candidatos": list(cands.index), "usage": out["usage"]})
    return out
