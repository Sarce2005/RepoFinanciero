"""Marcador: reports/index.html (para mirar) y reports/diario.md (para leer en el móvil)."""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from . import config
from .strategies import STRATEGIES

NAMES = {k: s.name for k, s in STRATEGIES.items()} | {"BENCH": "Índice 75/25"}
COLORS = {"A": "#2a78d6", "B": "#e0662f", "BENCH": "#8a8f98"}


def _read(state_dir: Path):
    eq = pd.read_csv(state_dir / "equity.csv", parse_dates=["date"])
    ops_path = state_dir / "operaciones.csv"
    ops = pd.read_csv(ops_path) if ops_path.exists() else pd.DataFrame()
    dec_path = state_dir / "decisiones.jsonl"
    decs = [json.loads(l) for l in dec_path.read_text(encoding="utf-8").splitlines()] \
        if dec_path.exists() else []
    carteras = {k: json.loads((state_dir / f"cartera_{k}.json").read_text())
                for k in STRATEGIES if (state_dir / f"cartera_{k}.json").exists()}
    return eq, ops, decs, carteras


def _svg_chart(eq: pd.DataFrame) -> str:
    w, h, pad = 760, 280, 44
    piv = eq.pivot_table(index="date", columns="agent", values="equity_eur").ffill()
    piv = 100 * (piv / config.INITIAL_CAPITAL - 1)
    if len(piv) < 2:
        return "<p class='muted'>La gráfica aparece a partir de la segunda sesión.</p>"
    lo, hi = min(piv.min().min(), -0.5), max(piv.max().max(), 0.5)
    xs = lambda i: pad + i * (w - 2 * pad) / (len(piv) - 1)  # noqa: E731
    ys = lambda v: h - pad - (v - lo) * (h - 2 * pad) / (hi - lo)  # noqa: E731
    parts = [f'<line x1="{pad}" x2="{w - pad}" y1="{ys(0):.1f}" y2="{ys(0):.1f}" class="zero"/>']
    for v in (lo, 0, hi):
        parts.append(f'<text x="{pad - 6}" y="{ys(v) + 4:.1f}" text-anchor="end" '
                     f'class="tick">{v:+.1f}%</text>')
    for i in (0, len(piv) - 1):
        parts.append(f'<text x="{xs(i):.1f}" y="{h - pad + 18}" text-anchor="middle" '
                     f'class="tick">{piv.index[i]:%d/%m}</text>')
    for agent in ["BENCH", "B", "A"]:
        if agent not in piv:
            continue
        pts = " ".join(f"{xs(i):.1f},{ys(v):.1f}" for i, v in enumerate(piv[agent]))
        dash = ' stroke-dasharray="5 4"' if agent == "BENCH" else ""
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{COLORS[agent]}" '
                     f'stroke-width="2.2"{dash}/>')
        last = piv[agent].iloc[-1]
        parts.append(f'<text x="{w - pad + 4}" y="{ys(last) + 4:.1f}" class="lbl" '
                     f'fill="{COLORS[agent]}">{NAMES[agent].split()[-1]}</text>')
    return (f'<svg viewBox="0 0 {w + 40} {h}" role="img" aria-label="Rentabilidad acumulada">'
            + "".join(parts) + "</svg>")


def _table(df: pd.DataFrame, cols: dict) -> str:
    if df.empty:
        return "<p class='muted'>Nada todavía.</p>"
    head = "".join(f"<th>{v}</th>" for v in cols.values())
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(r[c]))}</td>" for c in cols) + "</tr>"
                   for _, r in df.iterrows())
    return f"<div class='scroll'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def build(state_dir: Path, out_dir: Path) -> Path:
    eq, ops, decs, carteras = _read(state_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    last = eq[eq.date == eq.date.max()].set_index("agent")
    as_of = eq.date.max()

    # --- marcador
    cards = []
    ranking = sorted(last.index, key=lambda a: -last.loc[a, "equity_eur"])
    for pos, a in enumerate(ranking, 1):
        v = last.loc[a, "equity_eur"]
        ret = 100 * (v / config.INITIAL_CAPITAL - 1)
        a_ops = ops[(ops.agent == a) & (ops.status == "EJECUTADA")] if len(ops) else ops
        sells = a_ops[a_ops.action == "SELL"] if len(a_ops) else a_ops
        win = f"{100 * (sells.pnl_eur > 0).mean():.0f}%" if len(sells) else "–"
        sub = (f"{len(a_ops)} operaciones · aciertos {win}" if a != "BENCH"
               else "compra y mantén")
        method = STRATEGIES[a].method if a in STRATEGIES else "S&P 500 75% · EURO STOXX 50 25%"
        cards.append(f"""<div class="card" style="--c:{COLORS[a]}">
          <div class="pos">#{pos}</div><div class="name">{NAMES[a]}</div>
          <div class="method">{method}</div>
          <div class="val">{v:,.0f} €</div>
          <div class="ret {'up' if ret >= 0 else 'down'}">{ret:+.2f}%</div>
          <div class="muted">{sub}</div></div>""")

    # --- últimas decisiones
    latest = {}
    for d in decs:
        latest[d["agent"]] = d
    dec_html = []
    for a, d in latest.items():
        items = "".join(
            f"<li><b>{o['action']} {o['ticker']}</b>"
            f"{' · ' + str(round(100 * o.get('weight', 0), 1)) + '%' if o['action'] == 'BUY' else ''}"
            f" — {html.escape(o['reason'])}</li>" for o in d["aceptadas"])
        items += "".join(f"<li><b>STOP {s['ticker']}</b> — {html.escape(s['motivo'])}</li>"
                         for s in d["stops"])
        items += "".join(f"<li class='rej'><b>RECHAZADA {o.get('action')} {o.get('ticker')}</b>"
                         f" — {html.escape(o['rechazo'])}</li>" for o in d["rechazadas"])
        dec_html.append(f"""<div class="dec" style="--c:{COLORS[a]}">
          <h3>{NAMES[a]} <span class="muted">· decidido el {d['date']}, se ejecuta en la próxima apertura</span></h3>
          <p class="lectura">{html.escape(d['lectura'])}</p>
          <ul>{items or '<li class="muted">Sin órdenes: hoy no ve señal clara.</li>'}</ul></div>""")

    # --- carteras
    port_html = []
    for a, c in carteras.items():
        rows = pd.DataFrame([{"ticker": t, **p} for t, p in c["positions"].items()])
        if len(rows):
            rows["entry_price"] = rows["entry_price"].round(2)
        port_html.append(f"<h3 style='color:{COLORS[a]}'>{NAMES[a]} · liquidez "
                         f"{c['cash']:,.0f} €</h3>" + _table(rows, {
                             "ticker": "Valor", "shares": "Acciones", "entry_price": "Entrada",
                             "entry_date": "Fecha", "ccy": "Divisa"}))

    ops_recent = ops.sort_values(["exec_date", "id"], ascending=False).head(60) if len(ops) else ops
    if len(ops_recent):
        ops_recent = ops_recent.assign(agente=ops_recent.agent.map(NAMES))
    page = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Torneo de Bolsa</title>
<style>
:root{{--bg:#f7f7f5;--fg:#1d1f23;--muted:#6b7079;--card:#fff;--line:#e3e3df}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e8e8e6;--muted:#9097a0;--card:#1f2228;--line:#30343b}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:980px;margin:auto;padding:24px 16px 60px}}
h1{{margin:0;font-size:26px}} h2{{margin:36px 0 12px;font-size:18px}} h3{{margin:0 0 6px;font-size:15px}}
.muted{{color:var(--muted);font-size:13px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:18px}}
.card,.dec{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:10px;padding:14px 16px}}
.pos{{float:right;color:var(--muted);font-weight:700}} .name{{font-weight:700}}
.method{{color:var(--muted);font-size:13px}} .val{{font-size:24px;font-weight:700;margin-top:6px;font-variant-numeric:tabular-nums}}
.ret{{font-weight:700}} .up{{color:#1f9d55}} .down{{color:#d64545}}
svg{{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}}
.zero{{stroke:var(--line)}} .tick{{fill:var(--muted);font-size:11px}} .lbl{{font-size:12px;font-weight:700}}
.dec{{margin-bottom:12px}} .dec ul{{margin:6px 0 0;padding-left:18px}} .dec li{{margin:4px 0}}
.lectura{{margin:4px 0;font-style:italic}} .rej{{color:var(--muted)}}
.scroll{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}}
td:last-child{{white-space:normal;min-width:260px}}
</style></head><body><main>
<h1>Torneo de Bolsa</h1>
<div class="muted">Simulación sin dinero real · datos al cierre del {as_of:%d/%m/%Y} · capital inicial {config.INITIAL_CAPITAL:,.0f} € por jugador</div>
<div class="cards">{''.join(cards)}</div>
<h2>Rentabilidad acumulada</h2>{_svg_chart(eq)}
<h2>Últimas decisiones</h2>{''.join(dec_html) or "<p class='muted'>Aún no hay decisiones.</p>"}
<h2>Carteras</h2>{''.join(port_html)}
<h2>Operaciones ejecutadas</h2>{_table(ops_recent, {"exec_date": "Fecha", "agente": "Agente",
    "action": "Op.", "ticker": "Valor", "status": "Estado", "shares": "Acc.",
    "price_local": "Precio", "pnl_eur": "P&L €", "reason": "Justificación"})}
</main></body></html>"""
    out = out_dir / "index.html"
    out.write_text(page, encoding="utf-8")
    return out


def append_diary(summary: dict, out_dir: Path):
    """Resumen diario en Markdown, cómodo de leer desde el móvil en GitHub."""
    lines = [f"\n## {summary['date']}\n"]
    for a, d in summary["agents"].items():
        ret = 100 * (d["equity"] / config.INITIAL_CAPITAL - 1)
        lines.append(f"**{NAMES[a]}**: {d['equity']:,.0f} € ({ret:+.2f}%)  ")
        if d.get("lectura"):
            lines.append(f"_{d['lectura']}_  ")
        for f in d["fills"]:
            lines.append(f"- Ejecutada {f['action']} {f['ticker']} ({f['status']}) "
                         f"{f['shares']} acc. a {f['price_local']}")
        for s in d["stops"]:
            lines.append(f"- STOP mañana {s['ticker']}: {s['motivo']}")
        for o in d["accepted"]:
            lines.append(f"- Orden para mañana: {o['action']} {o['ticker']} — {o['reason']}")
        for o in d["rejected"]:
            lines.append(f"- Rechazada {o.get('action')} {o.get('ticker')}: {o['rechazo']}")
        lines.append("")
    ret_b = 100 * (summary["bench"] / config.INITIAL_CAPITAL - 1)
    lines.append(f"**Índice 75/25**: {summary['bench']:,.0f} € ({ret_b:+.2f}%)\n")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "diario.md"
    if not path.exists():
        path.write_text("# Diario del torneo\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
