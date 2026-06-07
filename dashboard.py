import streamlit as st # type: ignore
import pandas as pd # type: ignore
import can
from collections import deque
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="VIPV Telemetry", page_icon="🏎️", layout="wide")
st.title("🏎️ Panel de Telemetría VIPV en Tiempo Real")
st.markdown("Monitorización del Bus CAN | Nodo STM32 de Adquisición de Datos")

# --- FUNCIÓN DE CONVERSIÓN DE LOS DATOS RECIBIDOS ---
def bytes_to_float_escalado(byte_alto, byte_bajo, escala=100.0):
    entero_16bits = (byte_alto << 8) | byte_bajo
    if entero_16bits > 32767:
        entero_16bits -= 65536
    return entero_16bits / escala


# --- ARRAYS DEL PANEL Y CÁLCULO DE MÁXIMOS TEÓRICOS ---
v_vector = [0.548, 1.097, 1.645, 2.194, 2.742, 3.291, 3.839, 4.388, 4.936, 5.485, 6.033, 6.582, 7.13, 7.679, 8.228, 8.776, 9.324, 9.873, 10.422, 10.97, 11.519, 12.067, 12.615, 13.164, 13.712, 14.261, 14.809, 15.358, 15.907, 16.455, 17.004, 17.552, 18.101, 18.649, 19.198, 19.746, 20.295, 20.844, 21.392, 21.941, 22.489, 23.037, 23.587, 24.134, 24.683, 25.231, 25.78, 26.329, 26.877]
i_sol = [0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.9, 0.89, 0.88, 0.87, 0.86, 0.85, 0.84, 0.83, 0.83, 0.82, 0.81, 0.8, 0.8, 0.79, 0.78, 0.77, 0.76, 0.76, 0.75, 0.74, 0.73, 0.72, 0.72, 0.71, 0.7, 0.69, 0.68, 0.68, 0.67, 0.66, 0.65, 0.64, 0.63, 0.63, 0.61, 0.6, 0.58, 0.56, 0.54, 0.51, 0.45, 0.34, 0.15, -0.14]
i_sombra = [0.87, 0.85, 0.83, 0.82, 0.8, 0.79, 0.77, 0.75, 0.74, 0.73, 0.71, 0.69, 0.68, 0.67, 0.66, 0.64, 0.63, 0.62, 0.61, 0.6, 0.59, 0.58, 0.57, 0.56, 0.55, 0.54, 0.53, 0.52, 0.51, 0.5, 0.49, 0.47, 0.46, 0.45, 0.43, 0.42, 0.4, 0.39, 0.37, 0.36, 0.34, 0.32, 0.3, 0.28, 0.26, 0.23, 0.19, 0.13, 0.02, -0.24]

P_MAX_SOL = max([v * i for v, i in zip(v_vector, i_sol)])
P_MAX_SOMBRA = max([v * i for v, i in zip(v_vector, i_sombra)])


# --- INICIALIZACIÓN DE MEMORIA (Para que la gráfica avance sola) ---
MAX_PUNTOS = 50 # Los datos se guardan durante 50s, y a partir del seg 51, comienzan a reemplazarse

# st.session_state evita que las variables se borren si la página web se recarga.
if 'temp_data' not in st.session_state:
    st.session_state.temp_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_x = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_y = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_z = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.power_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.power_max_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.irr_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.speed_data = deque([0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.rpm_data = deque([0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)


# ==============================================================================
# --- MAQUETACIÓN DE LA WEB ---
# ==============================================================================
st.subheader("Datos en Tiempo Real")
col_m1, col_m2, col_m3, col_m4, col_m5, col_m6, col_m7, col_m8, col_m9 = st.columns(9)
metrica_temp = col_m1.empty()
metrica_irr = col_m2.empty()
metrica_v = col_m3.empty()
metrica_pot_i = col_m4.empty() # Potencia Ideal
metrica_pot_mppt = col_m5.empty() # Potencia MPPT
metrica_vel_obd = col_m6.empty()
metrica_x = col_m7.empty()
metrica_y = col_m8.empty()
metrica_z = col_m9.empty() 

st.divider()



# SECCIÓN 1: ENTORNO (Temperatura y Velocidad)
st.subheader("Entorno Térmico del Vehículo y Cinemática")
col_g1, col_g2 = st.columns(2) # divide la pantalla en columnas verticales, en este caso 2
with col_g1:
    #st.subheader("Evolución de Temperatura (ºC)")
    grafica_temp = st.empty()
with col_g2:
    #st.subheader("Evolución de Velocidad (km/h)")
    grafica_vel = st.empty()

st.divider()



# SECCIÓN 2: SEGUIMIENTO SOLAR (Irradiancia y Algoritmo MPPT)
st.subheader("Rendimiento VIPV: Seguimiento MPPT vs Irradiancia")

col_g3, col_g4 = st.columns([3, 2]) # MPPT ocupa un poco más de espacio que la irradiancia

with col_g3:
    #st.subheader(" Evolución de la Potencia deseada / teórica")
    grafica_potencia = st.empty()
with col_g4:
     #st.subheader(" Evolución de la Irradiancia")
    grafica_irr = st.empty()

st.divider()



# SECCIÓN 3: Dinámica Auxiliar (Acelerómetro y revoluciones)
st.subheader("Acelerómetro e Inercia")
grafica_accel = st.empty()



# ==============================================================================
# --- BUCLE PRINCIPAL CAN ---
# ==============================================================================
try:
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    
    ultimo_refresco = time.time()
    
    # Variables de estado temporal
    temp=0.0; ax=0.0; ay=0.0; az=0.0; volts=0.0; watts=0.0; p_max=0.0; irr=0.0; velocidad=0; rpm=0

    while True:
        # 1. BUCLE INTERNO: VACÍA EL BUFFER CAN A LA MÁXIMA VELOCIDAD
        while True:
            msg = bus.recv(0.0) # 0.0 NO bloquea. Si no hay mensajes, sale del bucle interno
            
            if msg is None:
                break # Fin de los mensajes atrasados
            
            # --- PROCESAMIENTO SILENCIOSO DE TRAMAS ---
            if msg.arbitration_id == 0x100:
                temp = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                st.session_state.temp_data.append(temp)
                
            elif msg.arbitration_id == 0x101:
                ax = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                ay = bytes_to_float_escalado(msg.data[2], msg.data[3], escala=100.0)
                az = bytes_to_float_escalado(msg.data[4], msg.data[5], escala=100.0)
                st.session_state.accel_x.append(ax)
                st.session_state.accel_y.append(ay)
                st.session_state.accel_z.append(az)

            elif msg.arbitration_id == 0x102:
                volts = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                watts = bytes_to_float_escalado(msg.data[4], msg.data[5], escala=1000.0)
            
                # UMBRAL FIJADO EN 150.0 W/m2
                ultima_luz = st.session_state.irr_data[-1] if len(st.session_state.irr_data) > 0 else 0
                if ultima_luz > 150.0:
                    p_max = P_MAX_SOL
                else:
                    p_max = P_MAX_SOMBRA

                st.session_state.power_data.append(watts)
                st.session_state.power_max_data.append(p_max)

            elif msg.arbitration_id == 0x103:
                irr = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=10.0)
                st.session_state.irr_data.append(irr)

            elif msg.arbitration_id == 0x7E8:
                if msg.data[2] == 0x0D: 
                    velocidad = int(msg.data[3])
                    st.session_state.speed_data.append(velocidad)
                if msg.data[2] == 0x0C: 
                    rpm = (msg.data[3] * 256 + msg.data[4]) / 4.0
                    st.session_state.rpm_data.append(rpm)


        # 2. DIBUJAR PANTALLA (Solo 2 veces por segundo para evitar el cuelgue)
        ahora = time.time()
        if ahora - ultimo_refresco >= 0.5:
            
            # Actualizar números
            metrica_temp.metric("Temperatura", f"{temp:.2f} °C")
            metrica_irr.metric("Irradiancia", f"{irr:.1f} W/m²")
            metrica_v.metric("V_MPPT", f"{volts:.2f} V")
            metrica_pot_i.metric("P_Ideal", f"{p_max:.2f} W") 
            metrica_pot_mppt.metric("P_Real", f"{watts:.2f} W")
            metrica_vel_obd.metric("Velocidad", f"{velocidad} km/h")
            metrica_x.metric("Eje X", f"{ax:.2f} g")
            metrica_y.metric("Eje Y", f"{ay:.2f} g")
            metrica_z.metric("Eje Z", f"{az:.2f} g")

            # Actualizar Gráficas
            grafica_temp.line_chart(list(st.session_state.temp_data), color="#ff4b4b")
            grafica_irr.line_chart(list(st.session_state.irr_data), color="#ffa500")
            
            df_power = pd.DataFrame({'Potencia MPPT (Real)': list(st.session_state.power_data), 'Potencia Máx (Ideal)': list(st.session_state.power_max_data)})
            grafica_potencia.line_chart(df_power, color=["#00ff88", "#aaaaaa"])
            
            df_accel = pd.DataFrame({'Eje X': list(st.session_state.accel_x), 'Eje Y': list(st.session_state.accel_y), 'Eje Z': list(st.session_state.accel_z)})
            grafica_accel.line_chart(df_accel)
            
            if len(st.session_state.speed_data) > 0:
                grafica_vel.line_chart(list(st.session_state.speed_data), color="#00c0f9")
            #if len(st.session_state.rpm_data) > 0:
            #    grafica_rpm.line_chart(list(st.session_state.rpm_data), color="#a200ff")
            
            # Reiniciar temporizador
            ultimo_refresco = ahora

except Exception as e:
    st.error(f"❌ Error de conexión CAN: {e}")
finally:
    if 'bus' in locals():
        bus.shutdown()