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
v_vector = [0.548, 1.097, 1.645, 2.194, 2.742, 3.291, 3.839, 4.388, 4.936, 5.485, 6.033, 6.582, 7.13, 7.679, 8.228, 8.776, 9.324, 9.873, 10.422, 10.97, 11.519, 12.067, 12.615, 13.164, 13.712, 14.261, 14.809, 15.358, 15.907, 16.455, 17.004, 17.552, 18.101, 18.649, 19.198, 19.746, 20.295, 20.844, 21.392, 21.941, 22.489, 23.037, 23.587, 24.134, 24.683, 25.231, 25.78, 26.329, 26.877]
i_sol = [0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.9, 0.89, 0.88, 0.87, 0.86, 0.85, 0.84, 0.83, 0.83, 0.82, 0.81, 0.8, 0.8, 0.79, 0.78, 0.77, 0.76, 0.76, 0.75, 0.74, 0.73, 0.72, 0.72, 0.71, 0.7, 0.69, 0.68, 0.68, 0.67, 0.66, 0.65, 0.64, 0.63, 0.63, 0.61, 0.6, 0.58, 0.56, 0.54, 0.51, 0.45, 0.34, 0.15, -0.14]
i_sombra = [0.87, 0.85, 0.83, 0.82, 0.8, 0.79, 0.77, 0.75, 0.74, 0.73, 0.71, 0.69, 0.68, 0.67, 0.66, 0.64, 0.63, 0.62, 0.61, 0.6, 0.59, 0.58, 0.57, 0.56, 0.55, 0.54, 0.53, 0.52, 0.51, 0.5, 0.49, 0.47, 0.46, 0.45, 0.43, 0.42, 0.4, 0.39, 0.37, 0.36, 0.34, 0.32, 0.3, 0.28, 0.26, 0.23, 0.19, 0.13, 0.02, -0.24]

P_MAX_SOL = max([v * i for v, i in zip(v_vector, i_sol)])
P_MAX_SOMBRA = max([v * i for v, i in zip(v_vector, i_sombra)])
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
#writer.writerow([
#    'Timestamp', 'Temp_C', 'Accel_X', 'Accel_Y', 'Accel_Z', 
#    'Voltaje_V', 'Corriente_A', 'Potencia_W', 'Irradiancia_W_m2', 'Velocidad_kmh', 'RPM'
#])

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
                if telemetria_vipv["Irradiancia"] > 150.0:
                    p_max = P_MAX_SOL
                else:
                    p_max = P_MAX_SOMBRA

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
                if msg.data[2] == 0x0C:
                    rpm = (msg.data[3] * 256 + msg.data[4]) / 4.0
                    telemetria_vipv["RPM"] = rpm
                    
                    print(f"[OBD COCHE] RPM: {int(rpm)}")


        # --- GUARDADO EN CSV (Se ejecuta en cada recepción) ---
        # --- LÓGICA DE GUARDADO ASÍNCRONO (1 Hz) ---
        ahora = datetime.now()
        diferencia = (ahora - ultimo_guardado).total_seconds()
        
         # Si ha pasado 1 seg o más desde la última vez que se guardó en CSV:
        if diferencia >= 1.0:
            tiempo_actual_str = ahora.strftime("%H:%M:%S")
            #tiempo_actual = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # Limitar los números a 2 decimales y convertir a cadena para ordenar el Excel
            # NOTA: Excel usa comas ',' para los decimales, por ello usar replace('.', ',')
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


