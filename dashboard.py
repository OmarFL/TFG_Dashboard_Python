import streamlit as st # type: ignore
import pandas as pd # type: ignore
import can
from collections import deque

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="VIPV Telemetry", page_icon="🏎️", layout="wide")
st.title("🛰️ Panel de Telemetría del VIPV en Tiempo Real")
st.markdown("Monitorización del Bus CAN0 (ID: 0x100 Entorno | ID: 0x101 Dinámica)")

# --- FUNCIÓN DE CONVERSIÓN DE LOS DATOS RECIBIDOS ---
def bytes_to_float_escalado(byte_alto, byte_bajo, escala=100.0):
    entero_16bits = (byte_alto << 8) | byte_bajo
    if entero_16bits > 32767:
        entero_16bits -= 65536
    return entero_16bits / escala

# --- INICIALIZACIÓN DE MEMORIA (Para que la gráfica avance sola) ---
MAX_PUNTOS = 50 # Los datos se guardan durante 50s, y a partir del seg 51, comienzan a reemplazarse

# st.session_state evita que las variables se borren si la página web se recarga.
if 'temp_data' not in st.session_state:
    st.session_state.temp_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_x = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_y = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_z = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)

# --- MAQUETACIÓN DE LA WEB (Contenedores vacíos) ---
# Fila de métricas grandes
col1, col2, col3, col4 = st.columns(4) # divide la pantalla en columnas verticales, en este caso 4.
metrica_temp = col1.empty()
metrica_x = col2.empty()
metrica_y = col3.empty()
metrica_z = col4.empty()

st.divider()

# Fila de gráficas
col_graf_1, col_graf_2 = st.columns(2)  # divide la pantalla en columnas verticales, en este caso 2.

with col_graf_1:
    st.subheader("🌡️ Evolución de Temperatura (ºC)")
    grafica_temp = st.empty()

with col_graf_2:
    st.subheader("🚀 Fuerzas G (Acelerómetro)")
    grafica_accel = st.empty()

# --- BUCLE PRINCIPAL CAN ---
try:
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    
    # Este bucle infinito mantiene la web viva
    while True:
        msg = bus.recv(0.1) # Timeout corto (0.1s) para que la web no se congele mientras espera nuevos datos
        
        if msg is not None:
            # 1. ACTUALIZAR TEMPERATURA
            if msg.arbitration_id == 0x100:
                temp = bytes_to_float_escalado(msg.data[0], msg.data[1])
                st.session_state.temp_data.append(temp)
                
                # Refrescar UI
                metrica_temp.metric("Temperatura VIPV", f"{temp:.2f} °C")
                grafica_temp.line_chart(list(st.session_state.temp_data), color="#ff4b4b")
                
            # 2. ACTUALIZAR DINÁMICA
            elif msg.arbitration_id == 0x101:
                ax = bytes_to_float_escalado(msg.data[0], msg.data[1])
                ay = bytes_to_float_escalado(msg.data[2], msg.data[3])
                az = bytes_to_float_escalado(msg.data[4], msg.data[5])
                
                st.session_state.accel_x.append(ax)
                st.session_state.accel_y.append(ay)
                st.session_state.accel_z.append(az)
                
                # Refrescar UI
                metrica_x.metric("Eje X", f"{ax:.2f} g")
                metrica_y.metric("Eje Y", f"{ay:.2f} g")
                metrica_z.metric("Eje Z", f"{az:.2f} g")
                
                # Juntamos los 3 ejes en una tabla (DataFrame) para que Streamlit dibuje 3 líneas juntas
                df_accel = pd.DataFrame({
                    'Eje X': list(st.session_state.accel_x),
                    'Eje Y': list(st.session_state.accel_y),
                    'Eje Z': list(st.session_state.accel_z)
                })
                grafica_accel.line_chart(df_accel)

except Exception as e:
    st.error(f"❌ Error de conexión CAN: {e}")
finally:
    if 'bus' in locals():
        bus.shutdown()