"""Libro mayor, ejecución de órdenes y validador. El árbitro del torneo."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pandas as pd

from . import config
from .data import MarketData


def _d(date) -> str:
    return pd.Timestamp(date).strftime("%Y-%m-%d")


class Portfolio:
    def __init__(self, agent: str, state_dir: Path):
        self.agent = agent
        self.dir = state_dir
        self.path = state_dir / f"cartera_{agent}.json"
        if self.path.exists():
            self.s = json.loads(self.path.read_text())
        else:
            self.s = {"agent": agent, "cash": config.INITIAL_CAPITAL, "positions": {},
                      "pending": [], "last_equity": config.INITIAL_CAPITAL, "last_run": None,
                      "next_id": 1}

    # ---------------------------------------------------------------- persistencia
    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.s, indent=2, ensure_ascii=False))

    def _append_csv(self, name: str, row: dict):
        path = self.dir / name
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)

    def log_decision(self, record: dict):
        with (self.dir / "decisiones.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"agent": self.agent, **record}, ensure_ascii=False) + "\n")

    # ---------------------------------------------------------------- valoración
    @property
    def positions(self) -> dict:
        return self.s["positions"]

    def equity(self, md: MarketData, date) -> float:
        total = self.s["cash"]
        for t, p in self.positions.items():
            px = md.last_close(t, date) or p["entry_price"]
            total += md.to_eur(t, p["shares"] * px, date)
        return total

    def mark_to_market(self, md: MarketData, date) -> float:
        eq = self.equity(md, date)
        self.s["last_equity"] = eq
        self._append_csv("equity.csv", {
            "date": _d(date), "agent": self.agent, "equity_eur": round(eq, 2),
            "cash_eur": round(self.s["cash"], 2), "n_positions": len(self.positions)})
        return eq

    def weights(self, md: MarketData, date) -> dict[str, float]:
        eq = self.equity(md, date)
        return {t: md.to_eur(t, p["shares"] * (md.last_close(t, date) or p["entry_price"]),
                             date) / eq for t, p in self.positions.items()}

    # ---------------------------------------------------------------- ejecución
    def execute_pending(self, md: MarketData, date) -> list[dict]:
        """Ejecuta al precio de APERTURA de `date` las órdenes decididas en sesiones previas."""
        fills, still = [], []
        orders = sorted(self.s["pending"], key=lambda o: o["action"] != "SELL")  # ventas primero
        for o in orders:
            bar = md.bar(o["ticker"], date)
            if bar is None:   # mercado cerrado (festivo) o sin dato
                o["age"] = o.get("age", 0) + 1
                if o["age"] > config.PENDING_ORDER_MAX_AGE:
                    fills.append(self._record(o, date, status="CANCELADA",
                                              note="sin cotización durante demasiadas sesiones"))
                else:
                    still.append(o)
                continue
            fills.append(self._fill(o, float(bar["Open"]), md, date))
        self.s["pending"] = still
        return fills

    def _fill(self, o: dict, price: float, md: MarketData, date) -> dict:
        t = o["ticker"]
        fx = md.fx_on(date) if md.ccy(t) == "USD" else 1.0
        price_eur = price / fx
        if o["action"] == "SELL":
            pos = self.positions.get(t)
            if not pos:
                return self._record(o, date, status="CANCELADA", note="no hay posición")
            shares = pos["shares"] if o.get("fraction", 1) >= 0.999 else \
                max(1, math.floor(pos["shares"] * o["fraction"]))
            gross = shares * price_eur
            fee = gross * config.COMMISSION
            self.s["cash"] += gross - fee
            pnl = gross - fee - pos["cost_eur"] * shares / pos["shares"]
            pos["cost_eur"] -= pos["cost_eur"] * shares / pos["shares"]
            pos["shares"] -= shares
            if pos["shares"] == 0:
                del self.positions[t]
            return self._record(o, date, status="EJECUTADA", shares=shares, price=price,
                                value_eur=gross, fee_eur=fee, pnl_eur=pnl)

        # BUY: el peso objetivo se calcula sobre el valor de cartera del último cierre
        budget = o["weight"] * self.s["last_equity"]
        budget = min(budget, self.s["cash"] / (1 + config.COMMISSION))
        shares = math.floor(budget / price_eur)
        if shares * price_eur < config.MIN_TRADE_EUR:
            return self._record(o, date, status="CANCELADA",
                                note=f"liquidez insuficiente ({self.s['cash']:.0f} EUR)")
        gross = shares * price_eur
        fee = gross * config.COMMISSION
        self.s["cash"] -= gross + fee
        pos = self.positions.get(t)
        if pos:
            total = pos["shares"] + shares
            pos["entry_price"] = (pos["entry_price"] * pos["shares"] + price * shares) / total
            pos["shares"] = total
            pos["cost_eur"] += gross + fee
        else:
            self.positions[t] = {"shares": shares, "entry_price": price, "entry_date": _d(date),
                                 "cost_eur": gross + fee, "ccy": md.ccy(t)}
        return self._record(o, date, status="EJECUTADA", shares=shares, price=price,
                            value_eur=gross, fee_eur=fee, pnl_eur=0.0)

    def _record(self, o, date, status, shares=0, price=0.0, value_eur=0.0, fee_eur=0.0,
                pnl_eur=0.0, note="") -> dict:
        row = {"exec_date": _d(date), "decided": o["created"], "agent": self.agent,
               "id": o["id"], "action": o["action"], "ticker": o["ticker"], "status": status,
               "shares": shares, "price_local": round(price, 4), "value_eur": round(value_eur, 2),
               "fee_eur": round(fee_eur, 2), "pnl_eur": round(pnl_eur, 2), "kind": o["kind"],
               "reason": o["reason"], "note": note}
        self._append_csv("operaciones.csv", row)
        return row

    # ---------------------------------------------------------------- órdenes
    def queue(self, action, ticker, reason, date, kind="agente", weight=0.0, fraction=1.0):
        o = {"id": f"{self.agent}-{self.s['next_id']:04d}", "created": _d(date),
             "action": action, "ticker": ticker, "weight": weight, "fraction": fraction,
             "reason": reason, "kind": kind, "age": 0}
        self.s["next_id"] += 1
        self.s["pending"].append(o)
        return o

    def validate(self, proposals: list[dict], slots: int, candidates: set[str],
                 already_selling: set[str], md: MarketData, date) -> tuple[list, list]:
        """Aplica el reglamento. Devuelve (aceptadas, rechazadas con motivo)."""
        ok, bad = [], []
        weights = self.weights(md, date)
        cash_w = self.s["cash"] / max(self.equity(md, date), 1)
        n_pos = len(self.positions)
        seen = set(already_selling)

        def reject(p, why):
            bad.append({**p, "rechazo": why})

        # ventas primero: liberan liquidez y huecos
        for p in sorted(proposals, key=lambda p: p.get("action") != "SELL"):
            a, t = p.get("action"), p.get("ticker")
            if len(ok) >= slots:
                reject(p, f"supera el máximo de {config.MAX_OPS_PER_DAY} operaciones diarias")
            elif not p.get("reason", "").strip():
                reject(p, "sin justificación")
            elif t in seen:
                reject(p, "ticker repetido en el mismo día")
            elif a == "SELL":
                if t not in self.positions:
                    reject(p, "no hay posición que vender")
                else:
                    frac = float(p.get("sell_fraction") or 1.0)
                    frac = min(max(frac, 0.1), 1.0)
                    ok.append({**p, "fraction": frac})
                    cash_w += weights.get(t, 0) * frac
                    if frac >= 0.999:
                        n_pos -= 1
                    seen.add(t)
            elif a == "BUY":
                w = float(p.get("weight_pct") or 0) / 100
                current = weights.get(t, 0)
                if t not in candidates and t not in self.positions:
                    reject(p, "no está en la lista de candidatos de tu método")
                elif t not in self.positions and n_pos >= config.MAX_POSITIONS:
                    reject(p, f"ya hay {config.MAX_POSITIONS} posiciones")
                elif w <= 0:
                    reject(p, "peso no válido")
                else:
                    w = min(w, config.MAX_POSITION_WEIGHT - current, cash_w)
                    if w * self.s["last_equity"] < config.MIN_TRADE_EUR:
                        reject(p, "peso resultante demasiado pequeño (límite 20% o sin liquidez)")
                    else:
                        ok.append({**p, "weight": w})
                        cash_w -= w
                        n_pos += t not in self.positions
                        seen.add(t)
            else:
                reject(p, f"acción desconocida: {a}")
        return ok, bad
