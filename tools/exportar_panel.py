"""Convierte el estado del torneo (state/) en los JSON que lee el panel de Claude.

Uso: python tools/exportar_panel.py <carpeta_state> <carpeta_salida>
Escribe equity.json, posiciones.json, pendientes.json, decisiones.json y operaciones.json,
cada uno una lista de filas (vacía si aún no hay datos). Solo lee: no toca state/.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

CAPITAL = 100_000.0
NOMBRES = {"A": "El Surfista", "B": "El Contrarian", "BENCH": "S&P 500"}
ACCION = {"BUY": "Compra", "SELL": "Venta"}


def _csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main(state: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)

    equity = [{"fecha": r["date"], "jugador": NOMBRES.get(r["agent"], r["agent"]),
               "valor_eur": round(float(r["equity_eur"]), 2),
               "rentabilidad": round(float(r["equity_eur"]) / CAPITAL - 1, 5),
               "liquidez_eur": round(float(r["cash_eur"]), 2)}
              for r in _csv(state / "equity.csv")]

    pos_path = state / "posiciones_hoy.json"
    posiciones = [{**{k: v for k, v in r.items() if k != "agente"},
                   "jugador": NOMBRES[r["agente"]]}
                  for r in (json.loads(pos_path.read_text()) if pos_path.exists() else [])]

    pendientes, decisiones = [], {}
    for k in ("A", "B"):
        cp = state / f"cartera_{k}.json"
        if cp.exists():
            for o in json.loads(cp.read_text()).get("pending", []):
                pendientes.append({
                    "id": o["id"], "jugador": NOMBRES[k], "decidido": o["created"],
                    "accion": ACCION.get(o["action"], o["action"]), "ticker": o["ticker"],
                    "peso": round(o.get("weight", 0), 4) if o["action"] == "BUY" else None,
                    "tipo": "Stop automático" if o.get("kind") == "stop" else "Decisión del agente",
                    "en_sencillo": o.get("plain") or "", "motivo": o.get("reason", "")})
    dec_path = state / "decisiones.jsonl"
    if dec_path.exists():
        for line in dec_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                decisiones[d["agent"]] = {"jugador": NOMBRES[d["agent"]], "fecha": d["date"],
                                          "lectura": d.get("lectura", ""),
                                          "descartes": d.get("descartes", ""),
                                          "candidatos": len(d.get("candidatos", []))}

    operaciones = [{"id": r["id"], "fecha": r["exec_date"], "jugador": NOMBRES[r["agent"]],
                    "accion": ACCION.get(r["action"], r["action"]), "ticker": r["ticker"],
                    "acciones": int(float(r["shares"] or 0)),
                    "precio": round(float(r["price_local"] or 0), 2),
                    "importe_eur": round(float(r["value_eur"] or 0), 2),
                    "resultado_eur": round(float(r["pnl_eur"] or 0), 2) if r["action"] == "SELL" else None,
                    "tipo": "Stop automático" if r.get("kind") == "stop" else "Decisión del agente",
                    "en_sencillo": r.get("en_sencillo", "")}
                   for r in _csv(state / "operaciones.csv") if r["status"] == "EJECUTADA"]
    operaciones.sort(key=lambda r: (r["fecha"], r["id"]), reverse=True)

    for name, rows in [("equity", equity), ("posiciones", posiciones),
                       ("pendientes", pendientes), ("decisiones", list(decisiones.values())),
                       ("operaciones", operaciones)]:
        (out / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
        print(f"{name}: {len(rows)} filas")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
