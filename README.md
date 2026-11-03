# Torneo de Bolsa: El Surfista vs. El Contrarian

Dos agentes de análisis técnico compiten del 03/11/2026 al 31/12/2026 con 100.000 € simulados
cada uno, comprando valores de una **lista fija de 258 valores** (`torneo/lista_fija.csv`): las 250
empresas del S&P 500 con más volumen negociado en dólares el 02/11/2026, más 8 añadidas a mano
el 03/11/2026 (ARM, BABA, CVAC, EH, NOK, QMCO, SPCX, ZM).
Sin dinero real, sin opciones, sin futuros, sin cortos y con un máximo de 5 operaciones al día.

| Agente | Método | Compra cuando… | Vende cuando… |
|---|---|---|---|
| **A · El Surfista** | Seguimiento de tendencia | Precio > SMA50 > SMA200, ADX > 25, ruptura de 20 días o MACD alcista | Trailing stop 2×ATR (automático) o la tendencia se rompe |
| **B · El Contrarian** | Reversión a la media | Por encima de SMA200 y en sobreventa (RSI2 < 10, RSI14 < 30 o bajo la Bollinger inferior) | Stop −8% (automático) o vuelta a la SMA20 / RSI14 > 70 |

El rival a batir es el S&P 500, medido en euros y comprado el primer día.

## Cómo funciona una sesión

1. Se descargan los precios de 1 año de los 258 valores de la lista fija (Yahoo Finance).
2. Se ejecutan, **a la apertura de hoy**, las órdenes decididas ayer.
3. Se valoran las carteras al cierre.
4. El código calcula los indicadores y aplica los stops automáticos.
5. Cada agente recibe su cartera y hasta 15 candidatos de su método, y decide.
6. El validador rechaza lo que incumpla el reglamento.
7. Las órdenes aceptadas quedan pendientes para la apertura siguiente y se actualiza el informe.

El modelo **no calcula** indicadores ni lleva la contabilidad: eso es código. Solo decide y justifica.

## Puesta en marcha (unos 15 minutos)

1. **Clave de API**: créala en <https://console.anthropic.com> y carga unos dólares de saldo.
   El mes completo cuesta del orden de 1-3 $.
2. **Repositorio en GitHub**: crea uno nuevo (puede ser privado) y sube esta carpeta tal cual.
3. **Secreto**: en el repositorio, *Settings → Secrets and variables → Actions → New repository
   secret*, con el nombre `ANTHROPIC_API_KEY` y tu clave como valor.
4. **Permisos**: en *Settings → Actions → General → Workflow permissions*, marca
   *Read and write permissions* para que el bot pueda guardar el estado.
5. **Prueba**: en la pestaña *Actions*, abre "Sesión diaria del torneo" y pulsa *Run workflow*.
   Antes del 03/11/2026 no hará nada (el torneo aún no ha empezado), pero comprobarás que
   descarga datos y que no falla.
6. **(Opcional) Web del marcador**: *Settings → Pages → Deploy from a branch → main / docs*.
   Tendrás el informe en `https://<tu-usuario>.github.io/<repo>/`. En repos privados, GitHub
   Pages requiere un plan de pago; si no, abre `docs/index.html` o lee `docs/diario.md`
   directamente en GitHub, que se ve bien desde el móvil.

A partir de ahí se ejecuta solo de lunes a viernes a las 22:30 (hora de Madrid) hasta el 31/12/2026.

## En local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m torneo.main simulate --days 22     # ensayo con mercado sintético: sin red ni API
python -m torneo.main run --dry-run          # datos reales, decisiones por reglas (sin API)
export ANTHROPIC_API_KEY=sk-ant-...
python -m torneo.main run                    # la de verdad
```

Si lo ejecutas en local en lugar de en GitHub Actions, prográmalo con cron
(`30 22 * * 1-5 cd /ruta && .venv/bin/python -m torneo.main run`). Ejecutarlo dos veces el mismo
día no duplica nada: la sesión ya procesada se salta.

## Dónde mirar

| Archivo | Qué contiene |
|---|---|
| `docs/index.html` | Marcador, curva de rentabilidad, últimas decisiones, carteras y operaciones |
| `docs/diario.md` | **Lo más cómodo para seguirlo.** Por agente y sesión: qué se ejecutó (y por qué se decidió), cómo ve el mercado, qué hace con cada posición, qué decide para mañana (explicación técnica y *en cristiano*) y qué descarta |
| `docs/glosario.md` | Qué significa cada indicador (RSI, ADX, MACD, Bollinger, ATR…) sin jerga |
| `state/operaciones.csv` | Todas las operaciones ejecutadas con su motivo y su resultado (ábrelo con Excel) |
| `state/decisiones.jsonl` | Cada decisión completa: lectura, órdenes, repaso de cartera, descartes, rechazos y tokens |
| `state/cartera_A.json`, `cartera_B.json` | Estado de cada cartera |

## Ajustes (`torneo/config.py`)

- `UNIVERSE_MODE`: `"fija"` por defecto (los 258 de `torneo/lista_fija.csv`: top 250 generado con
  `tools/top_volumen.py`). También existen `"usa"` (S&P 500 + Nasdaq-100, ~520 valores),
  `"reducido"` (S&P 100 + Nasdaq-100 + EURO STOXX 50 + IBEX 35, ~230) y `"amplio"` (S&P 500 +
  Nasdaq-100 + Europa, ~580).
- `BENCHMARK` / `BENCHMARK_NAME`: índice de referencia (100% S&P 500 por defecto).
- `MODEL`: `claude-sonnet-5-5` por defecto. Con `claude-haiku-5-5` sale más barato; con
  `claude-opus-5-5` razona mejor y cuesta más.
- `MAX_CANDIDATES`: cuántos candidatos ve cada agente. Es lo que más influye en los tokens.
- Comisión, límites por posición, capital, fechas, etc.

Los stops y los criterios de cribado están en `torneo/strategies.py`, y la personalidad de cada
agente, en el `prompt` de ese mismo archivo.

## Limitaciones conocidas

- Yahoo Finance es gratuito y no oficial. Si un día falla, la sesión no se procesa; al día
  siguiente se recupera sola, aunque las órdenes pendientes se ejecutarán un día más tarde.
- Las listas del S&P 500 y el Nasdaq-100 se leen de Wikipedia en cada sesión. Si Wikipedia
  falla, se usa una lista de respaldo más corta (S&P 100 + Nasdaq-100). Un ticker obsoleto
  simplemente se descarta.
- La ejecución a precio de apertura no simula deslizamiento (*slippage*). Con valores tan
  líquidos y una comisión del 0,1%, la diferencia es pequeña.
- Dos meses son unas 40 sesiones: estadísticamente sigue siendo poco. Diviértete, pero no saques
  conclusiones de inversión de aquí. **Nada de esto es asesoramiento financiero.**
