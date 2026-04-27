import streamlit as st # type: ignore
import pandas as pd # type: ignore
import can
from collections import deque

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

# --- INICIALIZACIÓN DE MEMORIA (Para que la gráfica avance sola) ---
MAX_PUNTOS = 50 # Los datos se guardan durante 50s, y a partir del seg 51, comienzan a reemplazarse

# st.session_state evita que las variables se borren si la página web se recarga.
if 'temp_data' not in st.session_state:
    st.session_state.temp_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_x = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_y = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_z = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.power_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.irr_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.speed_data = deque([0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.rpm_data = deque([0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)


# ==============================================================================
# --- MAQUETACIÓN DE LA WEB ---
# ==============================================================================
# SECCIÓN 1: ENTORNO (Temperatura e Irradiancia)
st.subheader("Entorno Solar y Térmico del Vehículo")
col_m1, col_m2 = st.columns(2) # divide la pantalla en columnas verticales, en este caso 2
metrica_temp = col_m1.empty()
metrica_irr = col_m2.empty()

col_g1, col_g2 = st.columns(2) # divide la pantalla en columnas verticales, en este caso 2
with col_g1:
    #st.subheader("🌡️ Evolución de Temperatura (ºC)")
    grafica_temp = st.empty()
with col_g2:
    #st.subheader(" Evolución de Irraciancia (W/m2)")
    grafica_irr = st.empty()

st.divider()


# SECCIÓN 2: COCHE Y ENERGÍA (Dinámica y Potencia)
st.subheader("Dinámica, Velocidad y Generación Solar del VIPV")
# 8 columnas para las métricas (3 para fuerzas G, 3 para energía, 2 para parámetros OBD)
col_dx, col_dy, col_dz, col_vel, col_rpm, col_ev, col_ei, col_ep = st.columns(8)
metrica_x = col_dx.empty()
metrica_y = col_dy.empty()
metrica_z = col_dz.empty()
metrica_v = col_ev.empty()
metrica_i = col_ei.empty()
metrica_p = col_ep.empty()
metrica_vel_obd = col_vel.empty()
metrica_rpm_obd = col_rpm.empty()

col_g3, col_g4, col_g5, col_g6 = st.columns(4)
with col_g3:
    #st.subheader(" Evolución de la Dinámica")
    grafica_accel = st.empty()
with col_g4:
     #st.subheader(" Evolución de la Velocidad")
    grafica_vel = st.empty()
with col_g5:
    #st.subheader(" Evolución de las RPMs")
    grafica_rpm = st.empty() 
with col_g6:
    #st.subheader(" Evolución de la Potencia")
    grafica_potencia = st.empty()

st.divider()



# ==============================================================================
# --- BUCLE PRINCIPAL CAN ---
# ==============================================================================
try:
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    
    # Este bucle infinito mantiene la web viva
    while True:
        msg = bus.recv(0.05) # Timeout corto (0.05s) para que la web no se congele mientras espera nuevos datos
        
        if msg is not None:
            # 1. ACTUALIZAR TEMPERATURA
            if msg.arbitration_id == 0x100:
                temp = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                st.session_state.temp_data.append(temp)
                
                # Refrescar UI
                metrica_temp.metric("Temperatura VIPV", f"{temp:.2f} °C")
                grafica_temp.line_chart(list(st.session_state.temp_data), color="#ff4b4b")


                
            # 2. ACTUALIZAR DINÁMICA
            elif msg.arbitration_id == 0x101:
                ax = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                ay = bytes_to_float_escalado(msg.data[2], msg.data[3], escala=100.0)
                az = bytes_to_float_escalado(msg.data[4], msg.data[5], escala=100.0)
                
                st.session_state.accel_x.append(ax)
                st.session_state.accel_y.append(ay)
                st.session_state.accel_z.append(az)
                
                # Refrescar UI
                metrica_x.metric("Eje X", f"{ax:.2f} g")
                metrica_y.metric("Eje Y", f"{ay:.2f} g")
                metrica_z.metric("Eje Z", f"{az:.2f} g")
                
                # Junto los 3 ejes en una tabla (DataFrame) para que Streamlit dibuje 3 líneas juntas
                df_accel = pd.DataFrame({
                    'Eje X': list(st.session_state.accel_x),
                    'Eje Y': list(st.session_state.accel_y),
                    'Eje Z': list(st.session_state.accel_z)
                })
                grafica_accel.line_chart(df_accel)



            # 3. ACTUALIZAR ENERGÍA
            elif msg.arbitration_id == 0x102:
                # Voltaje viene escalado por 100 (usamos la función por defecto)
                volts = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                
                # Corriente y Potencia vienen escaladas por 1000 (miliAmperios y miliVatios)
                amps = bytes_to_float_escalado(msg.data[2], msg.data[3], escala=1000.0)
                watts = bytes_to_float_escalado(msg.data[4], msg.data[5], escala=1000.0)
            
                # Guardar la potencia en la memoria para la gráfica
                st.session_state.power_data.append(watts)
                
                # Refrescar la UI
                metrica_v.metric("Voltaje del Panel", f"{volts:.2f} V")
                metrica_i.metric("Corriente Generada", f"{amps:.3f} A")
                metrica_p.metric("Potencia Total", f"{watts:.2f} W")
                
                grafica_potencia.line_chart(list(st.session_state.power_data), color="#00ff88")



            # 4. ACTUALIZAR IRRADIANCIA (0x103)
            elif msg.arbitration_id == 0x103:
                # Desescalar dividiendo por 10
                irr = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=10.0)
                
                # Guardar la irradiancia en la memoria para la gráfica
                st.session_state.irr_data.append(irr)
                
                # Refrescar UI 
                metrica_irr.metric("Irradiancia Solar", f"{irr:.1f} W/m²")
                grafica_irr.line_chart(list(st.session_state.irr_data), color="#ffa500")



            # 5. ESNIFAR VELOCIDAD DEL COCHE (0x7E8)
            elif msg.arbitration_id == 0x7E8:
                
                # Comprobación del byte 2 para confirmar que es el PID de velocidad (0x0D)
                if msg.data[2] == 0x0D: 
                    
                    # La velocidad real está alojada en el byte 3
                    velocidad = int(msg.data[3])
                    
                    # Guardar la velocidad en la memoria para la gráfica
                    st.session_state.speed_data.append(velocidad)
                    
                    # Refrescar UI
                    metrica_vel_obd.metric("Velocidad Coche", f"{velocidad} km/h")
                    grafica_vel.line_chart(list(st.session_state.speed_data), color="#00c0f9")


                # Comprobación del byte 2 para confirmar que es el PID de RPM (0x0C)
                if msg.data[2] == 0x0C: 
                    
                    # Cálculo de las RPMs reales a partir de los bytes 3 y 4
                    rpm = (msg.data[3] * 256 + msg.data[4]) / 4.0
                    
                    # Guardar las rpms en la memoria para la gráfica
                    st.session_state.rpm_data.append(rpm)
                    
                    # Refrescar UI
                    metrica_rpm_obd.metric("Revoluciones", f"{int(rpm)} RPM")
                    grafica_rpm.line_chart(list(st.session_state.rpm_data), color="#a200ff") 
                

except Exception as e:
    st.error(f"❌ Error de conexión CAN: {e}")
finally:
    if 'bus' in locals():
        bus.shutdown()