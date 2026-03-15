from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import requests as peticiones_web
from binance.client import Client
import sqlite3
from datetime import datetime

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
        pass
# ---------------------------------

# --- CONFIGURACIÓN DE BINANCE (TESTNET) ---
API_KEY = "M8j8EAWLjLBSu8YjtlWdFXQw0voRDXp2zla9YK0TncdfFMFzOS8aFrcjYDH1Bvzr"
API_SECRET = "SZimBjG9a33KWtWo3jBSbabY0zdjvKvYR1KKHMsmJg46waEp1jlLOqSqqrQJA9xp"

cliente_broker = None 

def conectar_y_probar_broker():
    global cliente_broker
    try:
        cliente_broker = Client(API_KEY, API_SECRET, testnet=True)
        balance = cliente_broker.get_asset_balance(asset='USDT')
        if balance:
            dolares_disponibles = round(float(balance['free']), 2)
            enviar_alerta_telegram(f"✅ ¡ARMAMENTO LISTO! Binance Testnet Online. Fondos: ${dolares_disponibles} USDT.")
    except Exception as e:
        print(f"Error Binance: {e}")

conectar_y_probar_broker()
# ---------------------------------

# --- NUEVO: LA BÓVEDA INMORTAL (BASE DE DATOS SQLITE) ---
def iniciar_base_datos():
    conexion = sqlite3.connect('memoria_bot.db')
    cursor = conexion.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            simbolo TEXT,
            tipo TEXT,
            monto REAL,
            precio REAL
        )
    ''')
    conexion.commit()
    conexion.close()

def registrar_operacion(simbolo, tipo, monto, precio):
    conexion = sqlite3.connect('memoria_bot.db')
    cursor = conexion.cursor()
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO operaciones (fecha, simbolo, tipo, monto, precio) VALUES (?, ?, ?, ?, ?)",
                   (fecha_actual, simbolo, tipo, monto, precio))
    conexion.commit()
    conexion.close()
    print(f"💾 Guardado en Bóveda: {tipo} {simbolo} por ${monto}")

iniciar_base_datos()
# ---------------------------------------------------------

# --- RADAR MAESTRO Y MEMORIA DE TRADING ---
activos_a_vigilar = ["BTC-USD", "ETH-USD", "EURUSD=X", "GC=F"]
memoria_trading = {} 

@app.route('/')
def inicio():
    return render_template('index.html')

# --- NUEVO: RUTA DEL CAJERO AUTOMÁTICO ---
@app.route('/saldo')
def obtener_saldo():
    global cliente_broker
    if cliente_broker:
        try:
            balance = cliente_broker.get_asset_balance(asset='USDT')
            if balance:
                return jsonify({"exito": True, "saldo": round(float(balance['free']), 2)})
        except Exception as e:
            return jsonify({"exito": False, "saldo": 0})
    return jsonify({"exito": False, "saldo": 0})
# -----------------------------------------

@app.route('/agregar-simbolo', methods=['POST'])
def agregar_simbolo():
    global activos_a_vigilar
    datos_recibidos = request.json
    nuevo_simbolo = datos_recibidos.get('simbolo')
    
    if nuevo_simbolo:
        nuevo_simbolo = nuevo_simbolo.upper().strip()
        if nuevo_simbolo not in activos_a_vigilar:
            activos_a_vigilar.append(nuevo_simbolo)
            enviar_alerta_telegram(f"🎯 Nuevo activo agregado al radar -> {nuevo_simbolo}")
            return jsonify({"mensaje": "Activo agregado al radar", "exito": True})
        else:
            return jsonify({"mensaje": "El activo ya está en el radar", "exito": False})
    return jsonify({"mensaje": "Error: No se envió ningún símbolo", "exito": False})

@app.route('/datos-bot')
def obtener_datos():
    global activos_a_vigilar, memoria_trading
    resultados_radar = [] 

    for simbolo in activos_a_vigilar:
        try:
            activo = yf.Ticker(simbolo)
            datos = activo.history(period="2d", interval="5m")
            
            if datos.empty: continue
                
            precios_cierre = datos['Close']
            precio_actual = float(precios_cierre.iloc[-1])

            # Indicadores
            delta = precios_cierre.diff()
            ganancia = delta.where(delta > 0, 0)
            perdida = -delta.where(delta < 0, 0)
            media_ganancia = ganancia.ewm(alpha=1/14, adjust=False).mean()
            media_perdida = perdida.ewm(alpha=1/14, adjust=False).mean()
            rs = media_ganancia / media_perdida
            rsi_actual = float(100 - (100 / (1 + rs)).iloc[-1])

            ema_rapida = precios_cierre.ewm(span=12, adjust=False).mean()
            ema_lenta = precios_cierre.ewm(span=26, adjust=False).mean()
            macd = ema_rapida - ema_lenta
            linea_senal = macd.ewm(span=9, adjust=False).mean()
            macd_actual = float(macd.iloc[-1])
            senal_actual = float(linea_senal.iloc[-1])

            ema_200 = precios_cierre.ewm(span=200, adjust=False).mean()
            ema_200_actual = float(ema_200.iloc[-1])

            # Lógica Matemática
            decision = "ESPERAR 🟡"
            color_log = "text-yellow-400"
            tendencia_texto = "ALCISTA 🟢" if precio_actual > ema_200_actual else "BAJISTA 🔴"

            if precio_actual > ema_200_actual and rsi_actual < 45 and macd_actual > senal_actual:
                decision = "COMPRA 🟢"
                color_log = "text-green-400"
            elif precio_actual < ema_200_actual and rsi_actual > 55 and macd_actual < senal_actual:
                decision = "VENTA 🔴"
                color_log = "text-red-400"

            # 🔥 GATILLO + BÓVEDA 🔥
            if simbolo not in memoria_trading:
                memoria_trading[simbolo] = "ESPERAR 🟡"

            if "-USD" in simbolo and cliente_broker:
                simbolo_binance = simbolo.replace("-USD", "USDT")
                if decision == "COMPRA 🟢" and memoria_trading[simbolo] != "COMPRA 🟢":
                    try:
                        orden = cliente_broker.create_order(
                            symbol=simbolo_binance,
                            side='BUY',
                            type='MARKET',
                            quoteOrderQty=15.0 
                        )
                        # Anotamos la compra en la Base de Datos para siempre
                        registrar_operacion(simbolo_binance, "COMPRA", 15.0, precio_actual)
                        enviar_alerta_telegram(f"💸 ¡GATILLO ACTIVADO! $15 USDT invertidos en {simbolo_binance}.")
                    except Exception as e:
                        print(f"Error de compra {simbolo}: {e}")

            memoria_trading[simbolo] = decision

            resultados_radar.append({
                "simbolo": simbolo,
                "precio": round(precio_actual, 4),
                "rsi": round(rsi_actual, 2),
                "tendencia": tendencia_texto,
                "decision": decision,
                "color": color_log
            })
            
        except Exception as e:
            pass 

    return jsonify(resultados_radar)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)