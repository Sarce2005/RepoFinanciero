# Glosario del torneo

Los términos que verás en el [diario](diario.md), explicados sin jerga. El ejemplo de cada
término usa números inventados.

## Las dos filosofías

- **Seguimiento de tendencia (El Surfista).** Lo que sube con fuerza tiende a seguir subiendo
  un tiempo. No intenta adivinar el giro: se sube a la ola y se baja cuando se rompe. Gana poco
  en muchas operaciones fallidas y mucho en unas pocas que corren.
- **Reversión a la media (El Contrarian).** Un buen valor que cae de golpe en pocos días suele
  rebotar hacia su precio "normal". Compra miedo puntual y vende en cuanto se recupera. Acierta
  a menudo, pero con ganancias pequeñas, y sufre si la caída era el inicio de algo peor.

## Medias móviles

- **SMA (media móvil simple).** El precio medio de los últimos N días. Suaviza el ruido diario.
  - **SMA20**: el último mes de bolsa. El Contrarian la usa como objetivo de venta.
  - **SMA50**: unos dos meses y medio. La tendencia de medio plazo.
  - **SMA200**: casi un año. La línea que separa un valor "sano" de uno en declive.
- **Medias en orden.** Precio > SMA50 > SMA200: lo reciente está por encima de lo antiguo, así
  que la tendencia es alcista y ordenada. Es lo que busca el Surfista.

## Fuerza y dirección

- **ADX14.** Mide la *fuerza* de la tendencia, no su dirección. Por debajo de 20 no hay
  tendencia; por encima de 25 sí la hay; por encima de 40 es muy fuerte.
- **MACD.** Compara una media rápida con una lenta para medir el impulso. Si el *histograma*
  es positivo, el impulso es alcista. Un **cruce alcista** es el momento en que pasa de negativo
  a positivo.
- **Ruptura del máximo de 20 días (canal de Donchian).** El precio cierra por encima de lo más
  alto del último mes. Es la señal clásica de que una tendencia arranca o acelera.

## Sobrecompra y sobreventa

- **RSI (índice de fuerza relativa).** De 0 a 100, mide si las subidas recientes han ganado a
  las bajadas.
  - **RSI14** (14 días): por debajo de 30 está *sobrevendido* (ha caído mucho, quizá demasiado)
    y por encima de 70 está *sobrecomprado*.
  - **RSI2** (2 días): versión ultrarrápida. Por debajo de 10 indica una caída brusca de pocos
    días. Es la señal favorita del Contrarian.
- **Bandas de Bollinger y %B.** Una banda alrededor de la SMA20 que se ensancha con la
  volatilidad. **%B** dice dónde está el precio dentro de ella: 0 es la banda inferior, 1 la
  superior. Un %B negativo significa que el precio ha caído por debajo de la banda: un exceso.

## Riesgo

- **ATR (rango verdadero medio).** Cuánto se mueve el valor en un día normal. **ATR%** es ese
  movimiento como porcentaje del precio. Un ATR% alto indica un valor nervioso, así que el
  agente le da menos peso en la cartera.
- **Trailing stop 2×ATR (Surfista).** Un stop que sube con el precio. Si el valor cae desde su
  máximo más de dos veces su movimiento diario normal, el sistema vende solo.
- **Stop fijo −8 % (Contrarian).** Si el valor pierde un 8 % desde la compra, el sistema vende
  solo, para no esperar eternamente un rebote que no llega.
- **Peso.** El porcentaje de la cartera que ocupa un valor. Por reglamento, el máximo es el 20 %.

## Cómo funciona una jornada

1. El agente decide con los precios de **cierre** de hoy.
2. Sus órdenes se ejecutan a la **apertura** de la siguiente sesión, a un precio que todavía
   no conoce. Así no puede hacer trampa con información del futuro.
3. Cada operación paga una comisión del 0,1 %. Por eso a veces lo mejor es no hacer nada.
4. El **S&P 500** (comprado el primer día y sin tocar) es el rival a batir. Si un agente no lo supera, habría salido mejor no hacer nada.
