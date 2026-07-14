import can # type: ignore
import csv
from datetime import datetime

print("Iniciando motor de telemetría CAN en Linux a 500Kbps...")
print("Esperando tramas VIPV (0x100-0x103) y respuestas OBD\n")


# Estructura de datos para guardar la telemetría
telemetria_vipv = {
    "Temperatura_C": 0.0,
    "Accel_X": 0.0,
    "Accel_Y": 0.0,
    "Accel_Z": 0.0,
    "Voltaje": 0.0,
    "Corriente": 0.0,
    "Potencia": 0.0,
    "Potencia_Teorica": 0.0,
    "Irradiancia": 0.0,
    "Velocidad": 0.0,
    "RPM": 0.0,
    "Heartbeat_Entorno": 0,
    "Heartbeat_Dinamica": 0,
    "Heartbeat_Energia": 0,
    "Heartbeat_Irradiancia": 0
}


# --- FUNCIÓN AUXILIAR PARA RECONSTRUIR NÚMEROS DE 2 BYTES ---
def bytes_to_float_escalado(byte_alto, byte_bajo, escala=100.0):

    # Fusionar el LSB y el MSB (Byte alto desplazado 8 bits a la izquierda + Byte bajo)
    entero_16bits = (byte_alto << 8) | byte_bajo
    
    # Manejo de números negativos (Complemento a 2 para enteros de 16 bits)
    if entero_16bits > 32767:
        entero_16bits -= 65536
        
    # Deshacer el escalado realizado al empaquetar los datos, antes del envío
    return entero_16bits / escala
# -------------------------------------------------------------


# --- ARRAYS DEL PANEL Y CÁLCULO DE MÁXIMOS TEÓRICOS ---
v_vector = [0.0, 0.5485, 1.0970, 1.6455, 2.1941, 2.7426, 3.2911, 3.8396, 4.3881, 4.9366, 5.4852, 6.0337, 6.5822, 7.1307, 7.6792, 8.2277, 8.7762, 9.3248, 9.8733, 10.4218, 10.9703, 11.5188, 12.0673, 12.6158, 13.1644, 13.7129, 14.2614, 14.8099, 15.3584, 15.9069, 16.4555, 17.0040, 17.5525, 18.1010, 18.6495, 19.1980, 19.7465, 20.2951, 20.8436, 21.3921, 21.9406, 22.4891, 23.0376, 23.5862, 24.1347, 24.6832, 25.2317, 25.7802, 26.3287, 26.8772]
i_sol = [0.9576, 0.9472, 0.9368, 0.9265, 0.9161, 0.9057, 0.8953, 0.8849, 0.8745, 0.8651, 0.8596, 0.8540, 0.8482, 0.8422, 0.8360, 0.8298, 0.8244, 0.8190, 0.8134, 0.8075, 0.8015, 0.7952, 0.7890, 0.7835, 0.7779, 0.7721, 0.7661, 0.7598, 0.7533, 0.7468, 0.7412, 0.7354, 0.7293, 0.7229, 0.7163, 0.7092, 0.7018, 0.6938, 0.6852, 0.6758, 0.6654, 0.6533, 0.6392, 0.6212, 0.5962, 0.5550, 0.4832, 0.3640, 0.1721, -0.1322]
i_sombra = [0.7131, 0.6996, 0.6862, 0.6727, 0.6592, 0.6458, 0.6323, 0.6248, 0.6175, 0.6099, 0.6020, 0.5937, 0.5848, 0.5755, 0.5658, 0.5557, 0.5453, 0.5347, 0.5239, 0.5128, 0.5034, 0.4945, 0.4855, 0.4763, 0.4668, 0.4571, 0.4472, 0.4369, 0.4263, 0.4153, 0.4038, 0.3920, 0.3795, 0.3665, 0.3531, 0.3392, 0.3250, 0.3101, 0.2947, 0.2784, 0.2612, 0.2429, 0.2233, 0.2015, 0.1775, 0.1506, 0.1193, 0.0737, -0.0480, -0.3115]

# Precálculo de curvas base
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
# -------------------------------------------------------------


# --- INICIALIZACIÓN DEL ARCHIVO CSV ---
fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
nombre_archivo = f"telemetria_ruta_{fecha_hora}.csv"
archivo_csv = open(nombre_archivo, mode='w', newline='')
writer = csv.writer(archivo_csv)


# Cabecera
writer.writerow([
    'Timestamp', 'Temperatura [ºC]', 'Accel_X [g]', 'Accel_Y [g]', 'Accel_Z [g]', 
    'Voltaje_MPPT [V]', 'Potencia_Extraida [W]', 'Potencia_Teorica [W]', 'Irradiancia [W/m^2]', 'Velocidad [km/h]'
])

archivo_csv.flush()  
print(f"-> Grabando datos de la prueba en: {nombre_archivo}\n")


try:
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    
    # --- TEMPORIZADOR PARA EL CSV ---
    ultimo_guardado = datetime.now()

    while True:
        msg = bus.recv(0.1) #Timeout de 0.1s para comprobación continua de los datos
        
        if msg is not None:
            
            # --- PROCESAMIENTO TRAMA ENTORNO (0x100) ---
            if msg.arbitration_id == 0x100:
                # Extraemos temperatura (Bytes 0 y 1)
                temp = bytes_to_float_escalado(msg.data[0], msg.data[1])
                telemetria_vipv["Temperatura_C"] = temp
                telemetria_vipv["Heartbeat_Entorno"] = msg.data[7]
                
                print(f"[ENTORNO] Temp: {temp:.2f} ºC | Seq: {msg.data[7]}")

                
            # --- PROCESAMIENTO TRAMA DINÁMICA (0x101) ---
            elif msg.arbitration_id == 0x101:
                # Eje X (Bytes 0 y 1)
                ax = bytes_to_float_escalado(msg.data[0], msg.data[1])
                # Eje Y (Bytes 2 y 3)
                ay = bytes_to_float_escalado(msg.data[2], msg.data[3])
                # Eje Z (Bytes 4 y 5)
                az = bytes_to_float_escalado(msg.data[4], msg.data[5])
                
                telemetria_vipv["Accel_X"] = ax
                telemetria_vipv["Accel_Y"] = ay
                telemetria_vipv["Accel_Z"] = az
                telemetria_vipv["Heartbeat_Dinamica"] = msg.data[7]
                
                print(f"[DINÁMICA] X:{ax:.2f}g | Y:{ay:.2f}g | Z:{az:.2f}g | Seq: {msg.data[7]}")



            # --- PROCESAMIENTO TRAMA ENERGÍA MPPT (0x102) ---
            elif msg.arbitration_id == 0x102:
                # Voltaje Óptimo MPPT
                volts = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                # Potencia Extraída Simulada (Bytes 4 y 5)
                watts = bytes_to_float_escalado(msg.data[4], msg.data[5], escala=1000.0)
                
                # Cálculo de la Potencia Máxima Teórica basada en la última medida de irradiancia
                #if telemetria_vipv["Irradiancia"] > 10.0:
                #    p_max = P_MAX_SOL
                #else:
                #    p_max = P_MAX_SOMBRA


                # Cálculo de la Potencia Ideal Continua
                ultima_luz = telemetria_vipv["Irradiancia"]

                # Acotar límites de seguridad matemática
                luz_acotada = max(0.0, min(1000.0, ultima_luz))
                
                # Calcular la proporción (Factor de mezcla de 0.0 a 1.0)
                #prop_luz = (luz_acotada - 10.0) / (1000.0 - 10.0)
                
                # Fórmula matemática de la Potencia Ideal (Interpolación lineal)
                #p_max = P_MAX_SOMBRA + prop_luz * (P_MAX_SOL - P_MAX_SOMBRA)

                if luz_acotada > 150.0:
                    ratio = luz_acotada / irr_eq_sol
                    p_max = P_MAX_SOL * ratio
                else:
                    ratio = luz_acotada / irr_eq_sombra
                    p_max = P_MAX_SOMBRA * ratio


                telemetria_vipv["Voltaje"] = volts
                telemetria_vipv["Potencia"] = watts
                telemetria_vipv["Potencia_Teorica"] = p_max
                telemetria_vipv["Heartbeat_Energia"] = msg.data[7]

                print(f"[MPPT] V_opt: {volts:.2f}V | P_ext: {watts:.2f}W | P_ideal: {p_max:.2f}W | Seq: {msg.data[7]}")



            # --- PROCESAMIENTO TRAMA ENERGÍA (0x102) ---
            # elif msg.arbitration_id == 0x102:
            #     # Voltaje viene escalado por 100 (usamos la función por defecto)
            #     volts = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
            #     # Corriente y Potencia vienen escaladas por 1000 (miliAmperios y miliVatios)
            #     amps = bytes_to_float_escalado(msg.data[2], msg.data[3], escala=1000.0)
            #     watts = bytes_to_float_escalado(msg.data[4], msg.data[5], escala=1000.0)
            #     
            #     telemetria_vipv["Voltaje"] = volts
            #     telemetria_vipv["Corriente"] = amps
            #     telemetria_vipv["Potencia"] = watts
            #     telemetria_vipv["Heartbeat_Energia"] = msg.data[7]
            # 
            #     print(f"[ENERGÍA] V: {volts:.2f}V | I: {amps:.3f}A | P: {watts:.2f}W | Seq: {msg.data[7]}")
            


            # --- PROCESAMIENTO TRAMA IRRADIANCIA (0x103) ---
            elif msg.arbitration_id == 0x103:
                # Desescalar dividiendo por 10
                irr = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=10.0)

                telemetria_vipv["Irradiancia"] = irr
                telemetria_vipv["Heartbeat_Irradiancia"] = msg.data[7]

                print(f"[ILUMINACIÓN] Irradiancia: {irr:.1f} W/m2 | Seq: {msg.data[7]}")

            # --- PROCESAMIENTO TRAMA OBD VELOCIDAD (0x7E8) ---
            elif msg.arbitration_id == 0x7E8:
                # PID 0x0D: Velocidad
                if msg.data[2] == 0x0D:
                    vel = int(msg.data[3]) # Extraemos la velocidad directa
                    telemetria_vipv["Velocidad"] = vel
                    
                    print(f"[OBD COCHE] Velocidad Actual: {vel} km/h")

                # PID 0x0C: RPMs
                #if msg.data[2] == 0x0C:
                #    rpm = (msg.data[3] * 256 + msg.data[4]) / 4.0
                #    telemetria_vipv["RPM"] = rpm
                #    
                #    print(f"[OBD COCHE] RPM: {int(rpm)}")


        # --- GUARDADO EN CSV (Se ejecuta en cada recepción) ---
        # --- LÓGICA DE GUARDADO ASÍNCRONO (1 Hz) ---
        ahora = datetime.now()
        diferencia = (ahora - ultimo_guardado).total_seconds()
        
         # Si ha pasado 1 seg o más desde la última vez que se guardó en CSV:
        if diferencia >= 1.0:
            tiempo_actual_str = ahora.strftime("%H:%M:%S")
            #tiempo_actual = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # Limitar los números a 2 decimales y convertir a cadena para ordenar el Excel
            # NOTA: Excel usa comas ',' para los decimales, por ello es útil usar replace('.', ',') para 
            # el posterior tratamiento de los datos guardados en el CSV
            p_extraida_formateada = f"{telemetria_vipv['Potencia']:.2f}".replace('.', ',')
            p_teorica_formateada = f"{telemetria_vipv['Potencia_Teorica']:.2f}".replace('.', ',')
            v_mppt_formateado = f"{telemetria_vipv['Voltaje']:.2f}".replace('.', ',')
            irr_formateada = f"{telemetria_vipv['Irradiancia']:.1f}".replace('.', ',')
            temp_formateada = f"{telemetria_vipv['Temperatura_C']:.2f}".replace('.', ',')
            ax_formateada = f"{telemetria_vipv['Accel_X']:.2f}".replace('.', ',')
            ay_formateada = f"{telemetria_vipv['Accel_Y']:.2f}".replace('.', ',')
            az_formateada = f"{telemetria_vipv['Accel_Z']:.2f}".replace('.', ',')

            #writer.writerow([
            #    tiempo_actual_str,
            #    telemetria_vipv["Temperatura_C"],
            #    telemetria_vipv["Accel_X"],
            #    telemetria_vipv["Accel_Y"],
            #    telemetria_vipv["Accel_Z"],
            #    telemetria_vipv["Voltaje"],
            #    telemetria_vipv["Corriente"],
            #    telemetria_vipv["Potencia"],
            #    telemetria_vipv["Potencia_Teorica"],
            #    telemetria_vipv["Irradiancia"],
            #    telemetria_vipv["Velocidad"],
            #    telemetria_vipv["RPM"]
            #])

            writer.writerow([
                tiempo_actual_str,
                temp_formateada,
                ax_formateada,
                ay_formateada,
                az_formateada,
                v_mppt_formateado,
                p_extraida_formateada,      
                p_teorica_formateada,       
                irr_formateada,
                telemetria_vipv["Velocidad"]
                # RPM 
            ])
            archivo_csv.flush() # Para guardado inmediato

            # Reiniciar para el próximo segundo
            ultimo_guardado = ahora



except KeyboardInterrupt:
    print("\nDetenido por el usuario. Cerrando conexión...")
except Exception as e:
    print(f"\n❌ Error de red CAN: {e}")
finally:
    if 'bus' in locals():
        bus.shutdown()
        print("Bus CAN liberado correctamente.")
    archivo_csv.close()
