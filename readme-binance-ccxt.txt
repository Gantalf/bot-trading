Estrategia Utilizada
La estrategia utilizada en este bot se basa en el seguimiento de tendencias con dos medias móviles simples (SMA) diferentes:

Determinar la tendencia general:

Se utiliza la media móvil simple de 20 días (SMA20) para determinar la tendencia a largo plazo del mercado.
Si el precio de oferta (bid) está por debajo de la SMA20, se considera una tendencia bajista (BEARISH).
Si el precio de oferta está por encima de la SMA20, se considera una tendencia alcista (BULLISH).
Operar alrededor de la SMA de 15 minutos:

Se utiliza la SMA de 20 períodos en un gráfico de 15 minutos para identificar puntos de entrada y salida.
Se colocan órdenes de compra un 0.1% por debajo y un 0.3% por encima de la SMA de 15 minutos.
Se colocan órdenes de venta un 0.1% por encima y un 0.3% por debajo de la SMA de 15 minutos.
Acciones Paso por Paso
Configuración e importación de librerías:

Se importan las librerías necesarias (ccxt, dotenv, pandas, numpy, datetime, time, schedule).
Se carga el archivo .env para obtener las claves de API.
Conexión al intercambio:

Se crea una instancia del intercambio Binance utilizando ccxt.
Funciones auxiliares:

ask_bid(): Obtiene el mejor precio de oferta y demanda del libro de órdenes.
daily_sma(): Calcula la SMA de 20 días y determina la tendencia del mercado.
f15_sma(): Calcula la SMA de 15 minutos y establece precios para órdenes de compra y venta.
open_position(): Verifica si hay posiciones abiertas.
kill_switch(): Cierra todas las posiciones abiertas.
pnl_close(): Calcula el PnL y verifica si se ha alcanzado el objetivo de ganancias.
Ejecución del bot:

La función bot() se ejecuta cada 28 segundos para verificar las condiciones del mercado y tomar decisiones de trading.
Si no hay posiciones abiertas, el bot coloca órdenes de compra o venta basadas en la tendencia determinada por la SMA de 20 días.
Si hay una posición abierta, el bot no coloca nuevas órdenes.