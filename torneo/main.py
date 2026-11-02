"""Punto de entrada.

  python -m torneo.main run                 # sesión real de hoy (necesita ANTHROPIC_API_KEY)
  python -m torneo.main run --dry-run       # sesión real, pero decide con reglas (sin API)
  python -m torneo.main simulate --days 22  # ensayo con mercado sintético, sin red ni API
  python -m torneo.main report              # regenera el informe HTML
"""
from __future__ import annotations

import argparse
import logging
import shutil

import pandas as pd

from . import config, data, engine, report, universe


def main():
    ap = argparse.ArgumentParser(description="Torneo de bolsa entre dos agentes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("simulate")
    s.add_argument("--days", type=int, default=22)
    s.add_argument("--llm", action="store_true", help="usar la API también en la simulación")
    sub.add_parser("report")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.cmd == "run":
        md = data.download(universe.load_universe())
        summary = engine.run_day(md, config.STATE_DIR, dry_run=args.dry_run)
        if summary:
            report.append_diary(summary, config.REPORTS_DIR)
        report.build(config.STATE_DIR, config.REPORTS_DIR)

    elif args.cmd == "simulate":
        state, out = config.ROOT / "state_sim", config.ROOT / "reports_sim"
        shutil.rmtree(state, ignore_errors=True)
        shutil.rmtree(out, ignore_errors=True)
        full = data.synthetic()
        dates = list(full.fx.index[-args.days:])
        config.START_DATE = str(dates[0].date())
        config.END_DATE = str(dates[-1].date())
        for d in dates:
            summary = engine.run_day(full.truncate(d), state, dry_run=not args.llm)
            if summary:
                report.append_diary(summary, out)
        print("Informe:", report.build(state, out))

    elif args.cmd == "report":
        print(report.build(config.STATE_DIR, config.REPORTS_DIR))


if __name__ == "__main__":
    main()
