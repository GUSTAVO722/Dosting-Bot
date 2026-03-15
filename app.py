from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import requests as peticiones_web
from binance.client import Client

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN DE TELEGRAM ---
TOKEN_TELEGRAM = "8608034319:AAECKEnZKGxZBK3NEzGvw2_jnzOhx9UJjrU"
CHAT_ID = "5735130657"  

def enviar_alerta_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    datos = {"chat_id": CHAT_ID, "text": mensaje}
    try:
        peticiones_web.post(url, data=datos)
        print(f"📲 Alerta enviada a Telegram: {mensaje}")
    except Exception as e:
        print(f"❌ Error al enviar Telegram: {e}")
# ---------------------------------

# --- CONFIGURACIÓN DE BINANCE (TESTNET) ---
API_KEY = "M8j8EAWLjLBSu8YjtlWdFXQw0voRDXp2zla9YK0TncdfFMFzOS8aFrcjYDH1Bvzr"
API_SECRET = "SZimBjG9a33KWtWo3jBSbabY0zdjvKvYR1KKHMsmJg46waEp1jlLOqSqqrQJA9xp"

# Encendemos el motor de Binance obligándolo a usar la red de pruebas (testnet=True)
try:
    cliente_broker = Client(API_KEY, API_SECRET, testnet=True)
except Exception as e:
    print(f"Error iniciando Binance: {e}")

def probar_conexion_broker():
    """Esta función revisa la billetera y avisa por Telegram al iniciar"""
    try:
        # Buscamos cuántos dólares falsos (USDT) nos dio Binance para probar
        balance = cliente_broker.get_asset_balance(asset='USDT')
        if balance:
            dolares_disponibles = round(float(balance['free']), 2)
            enviar_alerta_telegram(f"✅ ¡CONEXIÓN EXITOSA AL BROKER! El bot ha iniciado sesión en Binance Testnet. Fondos disponibles: ${dolares_disponibles} USDT.")
    except Exception as e:
        enviar_alerta_telegram(f"❌ Error conectando a la cuenta del Broker: {e}")
# ---------------------------------

# --- RADAR MAESTRO ---
activos_a_vigilar = ["BTC-USD", "ETH-USD", "EURUSD=X", "GC=F"]

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/agregar-simbolo', methods=['POST'])
def agregar_simbolo():
    global activos_a_vigilar
    datos_recibidos = request.json
    nuevo_simbolo = datos_recibidos.get('simbolo')
    
    if nuevo_simbolo:
        nuevo_simbolo = nuevo_simbolo.upper().strip()
        if nuevo_simbolo not in activos_a_vigilar:
            activos_a_vigilar.append(nuevo_simbolo)
            enviar_alerta_telegram(f"🎯 COMANDO RECIBIDO: Nuevo activo agregado al radar -> {nuevo_simbolo}")
            return jsonify({"mensaje": "Activo agregado al radar", "exito": True})
        else:
            return jsonify({"mensaje": "El activo ya está en el radar", "exito": False})
    
    return jsonify({"mensaje": "Error: No se envió ningún símbolo", "exito": False})

@app.route('/datos-bot')
def obtener_datos():
    global activos_a_vigilar
    resultados_radar = [] 

    for simbolo in activos_a_vigilar:
        try:
            activo = yf.Ticker(simbolo)
            datos = activo.history(period="2d", interval="5m")
            
            if datos.empty:
                continue
                
            precios_cierre = datos['Close']
            precio_actual = float(precios_cierre.iloc[-1])

            # RSI
            delta = precios_cierre.diff()
            ganancia = delta.where(delta > 0, 0)
            perdida = -delta.where(delta < 0, 0)
            media_ganancia = ganancia.ewm(alpha=1/14, adjust=False).mean()
            media_perdida = perdida.ewm(alpha=1/14, adjust=False).mean()
            rs = media_ganancia / media_perdida
            rsi_actual = float(100 - (100 / (1 + rs)).iloc[-1])

            # MACD
            ema_rapida = precios_cierre.ewm(span=12, adjust=False).mean()
            ema_lenta = precios_cierre.ewm(span=26, adjust=False).mean()
            macd = ema_rapida - ema_lenta
            linea_senal = macd.ewm(span=9, adjust=False).mean()
            macd_actual = float(macd.iloc[-1])
            senal_actual = float(linea_senal.iloc[-1])

            # EMA 200
            ema_200 = precios_cierre.ewm(span=200, adjust=False).mean()
            ema_200_actual = float(ema_200.iloc[-1])

            # Lógica
            decision = "ESPERAR 🟡"
            color_log = "text-yellow-400"
            tendencia_texto = "ALCISTA 🟢" if precio_actual > ema_200_actual else "BAJISTA 🔴"

            if precio_actual > ema_200_actual and rsi_actual < 45 and macd_actual > senal_actual:
                decision = "COMPRA 🟢"
                color_log = "text-green-400"
            elif precio_actual < ema_200_actual and rsi_actual > 55 and macd_actual < senal_actual:
                decision = "VENTA 🔴"
                color_log = "text-red-400"

            resultados_radar.append({
                "simbolo": simbolo,
                "precio": round(precio_actual, 4),
                "rsi": round(rsi_actual, 2),
                "tendencia": tendencia_texto,
                "decision": decision,
                "color": color_log
            })
            
        except Exception as e:
            print(f"Error procesando {simbolo}: {e}")

    return jsonify(resultados_radar)

if __name__ == '__main__':
    enviar_alerta_telegram("🤖 Sistema reiniciado.")
    # ¡Le decimos al bot que revise la billetera al encenderse!
    probar_conexion_broker() 
    app.run(host='0.0.0.0', port=5000)
