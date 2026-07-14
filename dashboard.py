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
v_vector = [0.0, 0.5485, 1.0970, 1.6455, 2.1941, 2.7426, 3.2911, 3.8396, 4.3881, 4.9366, 5.4852, 6.0337, 6.5822, 7.1307, 7.6792, 8.2277, 8.7762, 9.3248, 9.8733, 10.4218, 10.9703, 11.5188, 12.0673, 12.6158, 13.1644, 13.7129, 14.2614, 14.8099, 15.3584, 15.9069, 16.4555, 17.0040, 17.5525, 18.1010, 18.6495, 19.1980, 19.7465, 20.2951, 20.8436, 21.3921, 21.9406, 22.4891, 23.0376, 23.5862, 24.1347, 24.6832, 25.2317, 25.7802, 26.3287, 26.8772]
i_sol = [0.9576, 0.9472, 0.9368, 0.9265, 0.9161, 0.9057, 0.8953, 0.8849, 0.8745, 0.8651, 0.8596, 0.8540, 0.8482, 0.8422, 0.8360, 0.8298, 0.8244, 0.8190, 0.8134, 0.8075, 0.8015, 0.7952, 0.7890, 0.7835, 0.7779, 0.7721, 0.7661, 0.7598, 0.7533, 0.7468, 0.7412, 0.7354, 0.7293, 0.7229, 0.7163, 0.7092, 0.7018, 0.6938, 0.6852, 0.6758, 0.6654, 0.6533, 0.6392, 0.6212, 0.5962, 0.5550, 0.4832, 0.3640, 0.1721, -0.1322]
i_sombra = [0.7131, 0.6996, 0.6862, 0.6727, 0.6592, 0.6458, 0.6323, 0.6248, 0.6175, 0.6099, 0.6020, 0.5937, 0.5848, 0.5755, 0.5658, 0.5557, 0.5453, 0.5347, 0.5239, 0.5128, 0.5034, 0.4945, 0.4855, 0.4763, 0.4668, 0.4571, 0.4472, 0.4369, 0.4263, 0.4153, 0.4038, 0.3920, 0.3795, 0.3665, 0.3531, 0.3392, 0.3250, 0.3101, 0.2947, 0.2784, 0.2612, 0.2429, 0.2233, 0.2015, 0.1775, 0.1506, 0.1193, 0.0737, -0.0480, -0.3115]

# Precálculo de las curvas de Potencia completas para dibujarlas de fondo
p_sol_curva = [v * i for v, i in zip(v_vector, i_sol)]
p_sombra_curva = [v * i for v, i in zip(v_vector, i_sombra)]
P_MAX_SOL = max(p_sol_curva)
P_MAX_SOMBRA = max(p_sombra_curva)


# --- CONSTANTES DE CALIBRACIÓN ---
P_STC_REF = 56.233
IRR_STC_REF = 1000.0

# Determinar irradiancias de calibración de las curvas base
irr_eq_sol = IRR_STC_REF * (P_MAX_SOL / P_STC_REF)
irr_eq_sombra = IRR_STC_REF * (P_MAX_SOMBRA / P_STC_REF)


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
    st.session_state.contador_quieto = 0
    st.session_state.estado_coche = "CALIBRANDO..."


# ==============================================================================
# --- MAQUETACIÓN DE LA WEB ---
# ==============================================================================
st.subheader("Datos en Tiempo Real")
col_m1, col_m2, col_m3, col_m4, col_m5, col_m6, col_m7, col_m8, col_m9, col_m10 = st.columns(10)
metrica_temp = col_m1.empty()
metrica_irr = col_m2.empty()
metrica_v = col_m3.empty()
metrica_pot_i = col_m4.empty() # Potencia Ideal
metrica_pot_mppt = col_m5.empty() # Potencia MPPT
metrica_vel_obd = col_m6.empty()
metrica_x = col_m7.empty()
metrica_y = col_m8.empty()
metrica_z = col_m9.empty()
metrica_estado_coche = col_m10.empty() 

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

                # --- LÓGICA DE DETECCIÓN DE MOVIMIENTO ---
                if len(st.session_state.accel_x) >= 2:
                    # Cálculo de los deltas entre la lectura actual y la anterior
                    dx = abs(st.session_state.accel_x[-1] - st.session_state.accel_x[-2])
                    dy = abs(st.session_state.accel_y[-1] - st.session_state.accel_y[-2])
                    dz = abs(st.session_state.accel_z[-1] - st.session_state.accel_z[-2])
                    
                    # Extraer la última velocidad leída del bus CAN (OBD)
                    vel_actual = st.session_state.speed_data[-1] if len(st.session_state.speed_data) > 0 else 0
                    
                    # Condición de reposo absoluto: Cero vibraciones inerciales y velocidad cero
                    if dx < 0.05 and dy < 0.05 and dz < 0.05 and vel_actual == 0:
                        st.session_state.contador_quieto += 1
                    else:
                        st.session_state.contador_quieto = 0
                        
                    # 5 tramas consecutivas para confirmación de estado
                    if st.session_state.contador_quieto >= 5:
                        st.session_state.estado_coche = "PARADO"
                    else:
                        st.session_state.estado_coche = "EN MOVIMIENTO"


            elif msg.arbitration_id == 0x102:
                volts = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                watts = bytes_to_float_escalado(msg.data[4], msg.data[5], escala=1000.0)
            
                # CÁLCULO DINÁMICO DE POTENCIA IDEAL

                # ultima_luz = st.session_state.irr_data[-1] if len(st.session_state.irr_data) > 0 else 0
                ultima_luz = st.session_state.irr_data[-1] if len(st.session_state.irr_data) > 0 else 10.0

                luz_acotada = max(0.0, min(1000.0, ultima_luz))

                if luz_acotada > 150.0:
                    ratio = luz_acotada / irr_eq_sol
                    p_max = P_MAX_SOL * ratio
                else:
                    ratio = luz_acotada / irr_eq_sombra
                    p_max = P_MAX_SOMBRA * ratio

                #IRR_MAX_PY = 1000.0
                #IRR_MIN_PY = 10.0
                
                # Acotar límites
                #luz_acotada = max(IRR_MIN_PY, min(IRR_MAX_PY, ultima_luz))
                
                # Calcular la proporción de mezcla
                #prop_luz = (luz_acotada - IRR_MIN_PY) / (IRR_MAX_PY - IRR_MIN_PY)

                # Fórmula matemática directa
                #p_max = P_MAX_SOMBRA + prop_luz * (P_MAX_SOL - P_MAX_SOMBRA)
                
                # Reconstruir la curva entera de potencia para esta luz exacta
                #curva_p_dinamica = [p_som + prop_luz * (p_sol - p_som) for p_som, p_sol in zip(p_sombra_curva, p_sol_curva)]
                
                # pico teórico máximo de la nueva curva
                #p_max = max(curva_p_dinamica)


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


        # 2. DIBUJAR PANTALLA (2 veces por segundo (2 Hz) para evitar problemas de sincronización)
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
            metrica_estado_coche.metric("Estado del Vehículo", st.session_state.estado_coche)

            # GRÁFICA DE TEMPERATURA
            grafica_temp.line_chart(list(st.session_state.temp_data), color="#ff4b4b")

            # GRÁFICA DE IRRADIANCIA
            grafica_irr.line_chart(list(st.session_state.irr_data), color="#ffa500")  

            # GRÁFICA DE POTENCIA
            #df_power = pd.DataFrame({'Potencia MPPT (Real)': list(st.session_state.power_data), 'Potencia Máx (Ideal)': list(st.session_state.power_max_data)})
            #grafica_potencia.line_chart(df_power, color=["#00ff88", "#aaaaaa"])


            # GRÁFICA DE POTENCIA CON ZOOM FORZADO (Altair)
            df_power = pd.DataFrame({
                'Potencia Real (MPPT)': list(st.session_state.power_data), 
                'Potencia Ideal (MPPT)': list(st.session_state.power_max_data)
            }).reset_index()

            # Preparar los datos para que Altair los interprete
            df_melted = df_power.melt(id_vars='index', var_name='Señal', value_name='W')

            # Construir la gráfica forzando el zoom (zero=False)
            chart = alt.Chart(df_melted).mark_line(strokeWidth=3).encode(
                x=alt.X('index', axis=alt.Axis(labels=False, title=None)), # Ocultar el eje X por limpieza
                #y=alt.Y('W', scale=alt.Scale(domain=[6.0, 15.0]), title="Potencia [W]"), #ZOOM
                y=alt.Y('W', scale=alt.Scale(domain=[0.0, 60.0]), title="Potencia [W]"), #ZOOM

                color=alt.Color('Señal', scale=alt.Scale(
                    domain=['Potencia Real (MPPT)', 'Potencia Ideal (MPPT)'],
                    range=["#00ff88", "#aaaaaa"] 
                ))
            ).properties(height=250)

            # Renderizado asíncrono
            grafica_potencia.altair_chart(chart, width='stretch')
            #grafica_accel.line_chart(pd.DataFrame({'Eje X': list(st.session_state.accel_x), 'Eje Y': list(st.session_state.accel_y), 'Eje Z': list(st.session_state.accel_z)}))


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
            ultima_luz = st.session_state.irr_data[-1] if len(st.session_state.irr_data) > 0 else 40.0
            luz_acotada = max(0.0, min(1000.0, ultima_luz))
            
            # --- CURVA DINÁMICA I-V ---
            if luz_acotada > 150.0:
                ratio = luz_acotada / irr_eq_sol
                curva_i_dinamica = [i * ratio for i in i_sol]
                color_activa = "rgba(0, 255, 136, 1.0)"  # Verde para la curva I-V de Sol
                nombre_estado = "ESTADO: SOL"
            else:
                ratio = luz_acotada / irr_eq_sombra
                curva_i_dinamica = [i * ratio for i in i_sombra]
                color_activa = "rgba(0, 200, 255, 1.0)"  # Azul pra la curva I-V de sombra
                nombre_estado = "ESTADO: SOMBRA"


            #prop_luz = (luz_acotada - IRR_MIN_PY) / (IRR_MAX_PY - IRR_MIN_PY)
            
            # Línea exacta sobre la que se mueve el MPP
            #curva_i_dinamica = [i_som + prop_luz * (i_s - i_som) for i_som, i_s in zip(i_sombra, i_sol)]
            

            # Umbral para cambio de gráfica I-V
            #UMBRAL_LUZ = 150.0  
            #if ultima_luz > UMBRAL_LUZ:
            #    color_activa = "rgba(0, 255, 136, 1.0)"  # Verde brillante
            #    nombre_estado = "ESTADO: SOL"
            #else:
            #    color_activa = "rgba(0, 200, 255, 1.0)"  # Azul brillante
            #    nombre_estado = "ESTADO: SOMBRA"
                

            # Dibujo de los límites de la gráfica (línea discontinua de color gris)
            #fig.add_trace(go.Scatter(x=v_vector, y=i_sombra, mode='lines', name="Límite Sombra", line=dict(color="rgba(100, 100, 100, 0.3)", width=2, dash='dash')))
            #fig.add_trace(go.Scatter(x=v_vector, y=i_sol, mode='lines', name="Límite Sol", line=dict(color="rgba(100, 100, 100, 0.3)", width=2, dash='dash')))
            

            # Representación de la curva I-V real y el punto MPP sobre ella
            #fig.add_trace(go.Scatter(
            #    x=v_vector, y=curva_i_dinamica, mode='lines', name="Curva Teórica Actual", 
            #    line=dict(color=color_activa, width=4)
            #))
            
            #amps_actuales = (watts / volts) if volts > 0.5 else 0.0
            #fig.add_trace(go.Scatter(
            #    x=[volts], y=[amps_actuales], mode='markers', name="Rastreador MPPT",
            #    marker=dict(color='red', size=16, symbol='circle', line=dict(color='white', width=2))
            #))


            # Curvas límites estáticas de calibración base
            fig.add_trace(go.Scatter(x=v_vector, y=i_sombra, mode='lines', name="Calibración Sombra", line=dict(color="rgba(100, 100, 100, 0.3)", width=2, dash='dash')))
            fig.add_trace(go.Scatter(x=v_vector, y=i_sol, mode='lines', name="Calibración Sol", line=dict(color="rgba(100, 100, 100, 0.3)", width=2, dash='dash')))
            
            fig.add_trace(go.Scatter(x=v_vector, y=curva_i_dinamica, mode='lines', name="Curva Escalada Actual", line=dict(color=color_activa, width=4)))
            
            amps_actuales = (watts / volts) if volts > 0.5 else 0.0
            fig.add_trace(go.Scatter(x=[volts], y=[amps_actuales], mode='markers', name="Rastreador MPPT", marker=dict(color='red', size=16, symbol='circle', line=dict(color='white', width=2))))


            # Zoom y ajustes gráficos
            fig.update_layout(
                title=f"Búsqueda del MPP (Pto. máxima potencia)| Irradiancia: {ultima_luz:.1f} W/m² | {nombre_estado}",
                xaxis_title="Voltaje [V]",
                yaxis_title="Corriente [A]",
                margin=dict(l=10, r=10, t=40, b=10),
                height=450,
                #showlegend=False,
                showlegend=True, 
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[-0.25, 2.55]) 
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