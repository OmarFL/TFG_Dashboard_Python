import streamlit as st # type: ignore
import pandas as pd # type: ignore
import can
from collections import deque
import time
import plotly.graph_objects as go # librería Plotly, para hacer gráficas dinámicas
import altair as alt # liberría Altair (motor gráfico interno de Streamlit)

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
v_vector = [0.0, 0.548, 1.097, 1.645, 2.194, 2.742, 3.291, 3.839, 4.388, 4.936, 5.485, 6.033, 6.582, 7.13, 7.679, 8.228, 8.776, 9.324, 9.873, 10.422, 10.97, 11.519, 12.067, 12.615, 13.164, 13.712, 14.261, 14.809, 15.358, 15.907, 16.455, 17.004, 17.552, 18.101, 18.649, 19.198, 19.746, 20.295, 20.844, 21.392, 21.941, 22.489, 23.037, 23.587, 24.134, 24.683, 25.231, 25.78, 26.329, 26.877]
i_sol = [0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.9, 0.89, 0.88, 0.87, 0.86, 0.85, 0.84, 0.83, 0.83, 0.82, 0.81, 0.8, 0.8, 0.79, 0.78, 0.77, 0.76, 0.76, 0.75, 0.74, 0.73, 0.72, 0.72, 0.71, 0.7, 0.69, 0.68, 0.68, 0.67, 0.66, 0.65, 0.64, 0.63, 0.63, 0.61, 0.6, 0.58, 0.56, 0.54, 0.51, 0.45, 0.34, 0.15, -0.14]
i_sombra = [0.87, 0.85, 0.83, 0.82, 0.8, 0.79, 0.77, 0.75, 0.74, 0.73, 0.71, 0.69, 0.68, 0.67, 0.66, 0.64, 0.63, 0.62, 0.61, 0.6, 0.59, 0.58, 0.57, 0.56, 0.55, 0.54, 0.53, 0.52, 0.51, 0.5, 0.49, 0.47, 0.46, 0.45, 0.43, 0.42, 0.4, 0.39, 0.37, 0.36, 0.34, 0.32, 0.3, 0.28, 0.26, 0.23, 0.19, 0.13, 0.02, -0.24]

# Precálculo de las curvas de Potencia completas para dibujarlas de fondo
p_sol_curva = [v * i for v, i in zip(v_vector, i_sol)]
p_sombra_curva = [v * i for v, i in zip(v_vector, i_sombra)]

P_MAX_SOL = max(p_sol_curva)
P_MAX_SOMBRA = max(p_sombra_curva)
#P_MAX_SOL = max([v * i for v, i in zip(v_vector, i_sol)])
#P_MAX_SOMBRA = max([v * i for v, i in zip(v_vector, i_sombra)])


# --- INICIALIZACIÓN DE MEMORIA (Para que la gráfica avance sola) ---
MAX_PUNTOS = 50 # Los datos se guardan durante 50s, y a partir del seg 51, comienzan a reemplazarse

# st.session_state evita que las variables se borren si la página web se recarga.
if 'temp_data' not in st.session_state:
    st.session_state.temp_data = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_x = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_y = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.accel_z = deque([0.0]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.power_data = deque([None]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
    st.session_state.power_max_data = deque([None]*MAX_PUNTOS, maxlen=MAX_PUNTOS)
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


# SECCIÓN 3: Curva Dinámica 
st.subheader("Curva Dinámica I-V")
grafica_iv = st.empty() # El contenedor para Plotly


# SECCIÓN 4: Dinámica Auxiliar (Acelerómetro y revoluciones)
st.subheader("Acelerómetro e Inercia")
grafica_accel = st.empty()



# ==============================================================================
# --- BUCLE PRINCIPAL CAN ---
# ==============================================================================
try:
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    
    ultimo_refresco = time.time()
    ultimo_refresco_iv = time.time()
    
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
            
                # CÁLCULO DINÁMICO DE POTENCIA IDEAL

                # ultima_luz = st.session_state.irr_data[-1] if len(st.session_state.irr_data) > 0 else 0
                ultima_luz = st.session_state.irr_data[-1] if len(st.session_state.irr_data) > 0 else 10.0

                IRR_MAX_PY = 1000.0
                IRR_MIN_PY = 10.0
                
                # Acotar límites
                luz_acotada = max(IRR_MIN_PY, min(IRR_MAX_PY, ultima_luz))
                
                # Calcular la proporción de mezcla
                prop_luz = (luz_acotada - IRR_MIN_PY) / (IRR_MAX_PY - IRR_MIN_PY)
                
                # Reconstruir la curva entera de potencia para esta luz exacta
                curva_p_dinamica = [p_som + prop_luz * (p_sol - p_som) for p_som, p_sol in zip(p_sombra_curva, p_sol_curva)]
                
                # pico teórico máximo de la nueva curva
                p_max = max(curva_p_dinamica)


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


        # 2. DIBUJAR PANTALLA (Solo 2 veces por segundo (2 Hz) para evitar problemas de sincronización)
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

            # GRÁFICA DE TEMPERATURA
            grafica_temp.line_chart(list(st.session_state.temp_data), color="#ff4b4b")

            # GRÁFICA DE IRRADIANCIA
            grafica_irr.line_chart(list(st.session_state.irr_data), color="#ffa500")  

            # GRÁFICA DE POTENCIA
            #df_power = pd.DataFrame({'Potencia MPPT (Real)': list(st.session_state.power_data), 'Potencia Máx (Ideal)': list(st.session_state.power_max_data)})
            #grafica_potencia.line_chart(df_power, color=["#00ff88", "#aaaaaa"])


            # GRÁFICA DE POTENCIA CON ZOOM FORZADO (Altair)
            df_power = pd.DataFrame({
                'Potencia MPPT (Real)': list(st.session_state.power_data), 
                'Potencia Máx (Ideal)': list(st.session_state.power_max_data)
            }).reset_index()

            # Preparar los datos para que Altair los interprete
            df_melted = df_power.melt(id_vars='index', var_name='Señal', value_name='W')

            # Construir la gráfica forzando el zoom (zero=False)
            chart = alt.Chart(df_melted).mark_line(strokeWidth=3).encode(
                x=alt.X('index', axis=alt.Axis(labels=False, title=None)), # Ocultar el eje X por limpieza
                y=alt.Y('W', scale=alt.Scale(domain=[6.0, 15.0]), title="Potencia [W]"), #ZOOM
                color=alt.Color('Señal', scale=alt.Scale(
                    domain=['Potencia MPPT (Real)', 'Potencia Máx (Ideal)'],
                    range=["#00ff88", "#aaaaaa"] 
                ))
            ).properties(height=250)

            # Renderizado asíncrono
            grafica_potencia.altair_chart(chart, width='stretch')
            


            # GRÁFICA DE POTENCIA (Usando Plotly para zoom dinámico)
            #fig_pot = go.Figure()
            
            # Línea de Potencia Ideal (Gris)
            #fig_pot.add_trace(go.Scatter(
            #    y=list(st.session_state.power_max_data), mode='lines', name="P_Ideal", 
            #    line=dict(color="#aaaaaa", width=2)
            #))
            # Línea de Potencia Real MPPT (Verde brillante)
            #fig_pot.add_trace(go.Scatter(
            #    y=list(st.session_state.power_data), mode='lines', name="P_Real", 
            #    line=dict(color="#00ff88", width=3)
            #))

            # Extraemos el valor mínimo y máximo histórico del buffer para hacer el auto-zoom
            #min_p = min(list(st.session_state.power_data) + list(st.session_state.power_max_data))
            #max_p = max(list(st.session_state.power_data) + list(st.session_state.power_max_data))

            #fig_pot.update_layout(
            #    margin=dict(l=0, r=0, t=10, b=0),
            #    height=250,
                # Forzar eje Y para que abarque los datos dejando 1.5W de margen arriba y abajo
            #    yaxis=dict(range=[max(0, min_p - 1.5), max_p + 1.5]), 
            #    plot_bgcolor='rgba(0,0,0,0)',
            #    showlegend=True,
            #    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            #)
            
            #grafica_potencia.plotly_chart(fig_pot, width='stretch', key=f"pot_{ahora}")


            # GRÁFICA DEL ACELERÓMETRO
            df_accel = pd.DataFrame({'Eje X': list(st.session_state.accel_x), 'Eje Y': list(st.session_state.accel_y), 'Eje Z': list(st.session_state.accel_z)})
            grafica_accel.line_chart(df_accel)
            

            # GRÁFICA DE VELOCIDAD
            if len(st.session_state.speed_data) > 0:
                grafica_vel.line_chart(list(st.session_state.speed_data), color="#00c0f9")


            # Reiniciar temporizador
            ultimo_refresco = ahora



        # --- CONTROL INDEPENDIENTE DE 1 SEGUNDO PARA LA CURVA I-V ---
        if ahora - ultimo_refresco_iv >= 1.0:
            fig = go.Figure()
            
            # Cálculo de la curva dinámica (Sincronizado con la STM32)
            IRR_MAX_PY = 1000.0
            IRR_MIN_PY = 10.0
            ultima_luz = st.session_state.irr_data[-1] if len(st.session_state.irr_data) > 0 else 40.0
            luz_acotada = max(IRR_MIN_PY, min(IRR_MAX_PY, ultima_luz))
            
            prop_luz = (luz_acotada - IRR_MIN_PY) / (IRR_MAX_PY - IRR_MIN_PY)
            
            # Línea exacta sobre la que se mueve el MPP
            curva_i_dinamica = [i_som + prop_luz * (i_s - i_som) for i_som, i_s in zip(i_sombra, i_sol)]
            

            # Umbral para cambio de gráfica I-V
            UMBRAL_LUZ = 150.0  
            if ultima_luz > UMBRAL_LUZ:
                color_activa = "rgba(0, 255, 136, 1.0)"  # Verde brillante
                nombre_estado = "ESTADO: SOL"
            else:
                color_activa = "rgba(0, 200, 255, 1.0)"  # Azul brillante
                nombre_estado = "ESTADO: SOMBRA"
                

            # Dibujo de los límites de la gráfica (línea discontinua de color gris)
            fig.add_trace(go.Scatter(x=v_vector, y=i_sombra, mode='lines', name="Límite Sombra", line=dict(color="rgba(100, 100, 100, 0.3)", width=2, dash='dash')))
            fig.add_trace(go.Scatter(x=v_vector, y=i_sol, mode='lines', name="Límite Sol", line=dict(color="rgba(100, 100, 100, 0.3)", width=2, dash='dash')))
            

            # Representación de la curva I-V real y el punto MPP sobre ella
            fig.add_trace(go.Scatter(
                x=v_vector, y=curva_i_dinamica, mode='lines', name="Curva Teórica Actual", 
                line=dict(color=color_activa, width=4)
            ))
            
            amps_actuales = (watts / volts) if volts > 0.5 else 0.0
            fig.add_trace(go.Scatter(
                x=[volts], y=[amps_actuales], mode='markers', name="Rastreador MPPT",
                marker=dict(color='red', size=16, symbol='circle', line=dict(color='white', width=2))
            ))


            # Zoom y ajustes gráficos
            fig.update_layout(
                title=f"Búsqueda del Codo | Irradiancia: {ultima_luz:.1f} W/m² | {nombre_estado}",
                xaxis_title="Voltaje [V]",
                yaxis_title="Corriente [A]",
                margin=dict(l=10, r=10, t=40, b=10),
                height=450,
                #showlegend=False,
                showlegend=True, 
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[-0.25, 1.05]) 
            )
            
            grafica_iv.plotly_chart(fig, width='stretch', key=f"grafica_iv_mppt_{ahora}")
            ultimo_refresco_iv = ahora


            # CONSTRUCCIÓN DE LA GRÁFICA PLOTLY (I-V EN TIEMPO REAL)
            #fig = go.Figure()
            
            # Límites de calibración
            #IRR_MAX_PY = 1000.0
            #IRR_MIN_PY = 10.0
            
            # Recoger la última irradiancia registrada
            #ultima_luz = st.session_state.irr_data[-1] if len(st.session_state.irr_data) > 0 else 10.0
            #luz_acotada = max(IRR_MIN_PY, min(IRR_MAX_PY, ultima_luz))

            #prop_luz = (luz_acotada - IRR_MIN_PY) / (IRR_MAX_PY - IRR_MIN_PY)
            
            # CURVA I-V REAL TEÓRICA (Interpolación lineal)
            #curva_i_dinamica = [i_som + prop_luz * (i_s - i_som) for i_som, i_s in zip(i_sombra, i_sol)]


            # 1. Curvas límites estáticas de fondo (Líneas guía transparentes)
            #fig.add_trace(go.Scatter(
            #    x=v_vector, y=i_sombra, mode='lines', name="Límite Sombra (10 W/m²)", 
            #    line=dict(color="rgba(150, 150, 150, 0.2)", width=2, dash='dash')
            #))
            #fig.add_trace(go.Scatter(
            #    x=v_vector, y=i_sol, mode='lines', name="Límite Sol (1000 W/m²)", 
            #    line=dict(color="rgba(150, 150, 150, 0.2)", width=2, dash='dash')
            #))
            
            # 2. Curva Teórica Activa (La que muta en tiempo real)
            #fig.add_trace(go.Scatter(
            #    x=v_vector, y=curva_i_dinamica, mode='lines', name="Curva Teórica Actual", 
            #    line=dict(color="rgba(0, 200, 255, 0.9)", width=4)
            #))
            
            # 3. CORRIENTE ACTUAL EXTRAÍDA POR EL MPPT (I = P / V)
            # Evitar la división por cero si el voltaje es muy bajo al arrancar
            #amps_actuales = (watts / volts) if volts > 0.5 else 0.0

            # 4. PUNTO MPPT REAL (Búsqueda del codo)
            #fig.add_trace(go.Scatter(
            #    x=[volts], y=[amps_actuales], mode='markers', name="Rastreador MPPT",
            #    marker=dict(color='red', size=14, symbol='circle', line=dict(color='white', width=2))
            #))

            #fig.update_layout(
            #    title=f"Búsqueda del Codo en Tiempo Real (Irradiancia: {ultima_luz:.1f} W/m²)",
            #    xaxis_title="Voltaje [V]",
            #    yaxis_title="Corriente [A]",
            #    margin=dict(l=10, r=10, t=40, b=10),
            #    height=450,
            #    showlegend=True, # Activamos la leyenda para que los profesores vean las referencias
            #    plot_bgcolor='rgba(0,0,0,0)'
            #)
            
            #grafica_iv.plotly_chart(fig, width='stretch', key=f"grafica_iv_mppt_{ahora}")


except Exception as e:
    st.error(f"❌ Error de conexión CAN: {e}")
finally:
    if 'bus' in locals():
        bus.shutdown()