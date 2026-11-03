# CLAUDE.md: Torneo "Surfista contra Contrarian" (versión GitHub Actions)

Contexto para Claude al abrir este repositorio. Léelo antes de tocar nada.

## Qué es

Torneo **simulado** de bolsa (sin dinero real) entre dos analistas técnicos. Cada uno es una
llamada a la API de Claude con su propia personalidad:

- **A, "El Surfista"**: sigue la tendencia (momentum). Usa la SMA50 y la SMA200, el ADX14, el
  MACD, las rupturas del máximo de 20 días y el ATR. El sistema aplica automáticamente un
  trailing stop de 2xATR.
- **B, "El Contrarian"**: busca la reversión a la media. Compra sobreventa (RSI2, RSI14, %B de
  Bollinger) solo en valores por encima de su SMA200 y busca salir en la SMA20. El sistema aplica
  automáticamente un stop fijo de -8 %.

Los dos compiten contra el **S&P 500** comprado y mantenido desde el primer día.
Todo se mide en EUR (los valores cotizan en USD y se convierten con el EURUSD del día) y cada
uno arranca con 100.000 €. El universo es el modo `"fija"`: **255 valores** guardados en
`torneo/lista_fija.csv`: los 250 del S&P 500 con más volumen negociado en dólares el 02/11/2026
y 6 añadidos a mano por el usuario el 03/11/2026 (ARM, BABA, EH, NOK, QMCO, ZM;
columna `origen`). El 03/11 se quitaron CVAC, HONA y SPCX por no tener un año de historia. Solo el usuario decide cambios en la lista: no la regeneres por tu cuenta.
Fechas: del **03/11/2026 al 31/12/2026** (ver `config.py`). El último día solo se ejecutan las
órdenes pendientes y se cierra el marcador.

El objetivo del usuario es **aprender cómo funciona el mercado** viendo razonar a los dos
agentes. Por eso cada decisión se explica dos veces, en lenguaje técnico y en lenguaje sencillo.

No es asesoramiento financiero. No conviertas nada de esto en recomendaciones de inversión.

## Estructura

```
.github/workflows/sesion_diaria.yml  cron L-V 21:30 UTC; acciones fijadas por SHA (política del repo)
torneo/
  config.py      reglamento: fechas, capital, comisión 0,1 %, límites, modelo
  universe.py    lista de valores (modo "fija" -> lista_fija.csv)
  lista_fija.csv los 255 valores del torneo (249 del top 250, sin HONA, + 6 a mano)
  data.py        descarga con yfinance (y mercado sintético para `simulate`)
  indicators.py  SMA, RSI, MACD, ADX, ATR, Bollinger, Donchian
  strategies.py  cribado, stops obligatorios y personalidad (prompt) de cada analista
  agents.py      contexto, reglas y esquema de la herramienta `enviar_ordenes`
  engine.py      sesión diaria: ejecución a la apertura → valoración → stops → decisión
  portfolio.py   carteras, órdenes pendientes, validador, libro mayor
  report.py      genera docs/index.html y docs/diario.md
  main.py        CLI: run | run --dry-run | simulate | report
state/           estado vivo (carteras, operaciones.csv, decisiones.jsonl, equity.csv)
docs/            informe publicado: index.html, diario.md, glosario.md
```

## Qué explica cada agente (esquema de `enviar_ordenes`)

- `lectura_mercado`: cómo ve el día desde su método.
- `ordenes[]`: `action`, `ticker`, `weight_pct` o `sell_fraction`, `reason` (técnica, citando
  indicadores) y `en_sencillo` (sin jerga).
- `revision_cartera[]`: una entrada por posición abierta, con MANTENER, VENDER o AMPLIAR y su motivo.
- `descartes`: por qué deja fuera a los candidatos tentadores.

Todo queda en `state/decisiones.jsonl`. El motivo de cada orden viaja con ella hasta que se
ejecuta (`state/operaciones.csv`, columnas `reason` y `en_sencillo`).

## Reglas (las aplica el validador del código, no la buena fe)

- Solo posiciones largas al contado, con un máximo de 5 operaciones al día (los stops cuentan).
- Cada posición pesa como mucho el 20 % de la cartera, hay un máximo de 10 posiciones y cada
  orden tiene un importe mínimo.
- Se decide con el cierre del día y la orden se ejecuta a la apertura de la sesión siguiente.
  Una orden pendiente caduca a las 3 sesiones sin cotización (festivos).
- Solo se compran valores de la lista de candidatos del día (o se amplía una posición que ya se
  tenga).
- Los analistas deciden **solo** con los indicadores que les da el motor.

## Flujo

GitHub Actions ejecuta `python -m torneo.main run` con el secreto `ANTHROPIC_API_KEY` y hace
commit de `state/` y `docs/` como `torneo-bot`. Ejecutarlo dos veces el mismo día no duplica
nada.

En local:
```bash
pip install -r requirements.txt
python -m torneo.main simulate --days 22   # mercado sintético, sin red ni API
python -m torneo.main run --dry-run        # datos reales, decisiones por reglas
python -m torneo.main run                  # la de verdad (necesita ANTHROPIC_API_KEY)
```

## Normas para Claude en este repo

- Una vez empezado el torneo (03/11/2026), no cambies `config.py`, `strategies.py` ni el
  esquema de `agents.py`. Si encuentras un error, explícalo y propón el cambio, pero no lo
  apliques en silencio.
- No edites a mano `state/` ni `docs/diario.md`: solo los modifica el motor.
- No inventes decisiones de los analistas ni retoques sus textos.
- Las acciones del workflow deben ir fijadas por SHA completo (política del repositorio).

## Relación con el otro torneo

Existe un torneo paralelo (S&P 500, USD, contra el SPY, del 27/10 al 30/11/2026) que juega una
tarea programada de claude.ai y cuya fuente de verdad es un artifact de claude.ai. **No es este
motor**: usa otros comandos (`preparar`/`jugar`), otra carpeta de estado (`estado/`) y subagentes
en lugar de la API. No mezcles sus ficheros con los de este repo.
