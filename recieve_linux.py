import can # type: ignore

print("Iniciando motor de telemetría CAN en Linux a 500Kbps...")
print("Esperando tramas VIPV (ID 0x123). Pulsa Ctrl+C para salir.\n")


# Estructura de datos para guardar la telemetría
telemetria_vipv = {
    "Temperatura_C": 0.0,
    "Accel_X": 0.0,
    "Accel_Y": 0.0,
    "Accel_Z": 0.0,
    "Voltaje": 0.0,
    "Corriente": 0.0,
    "Potencia": 0.0,
    "Irradiancia": 0.0,
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


try:
    bus = can.interface.Bus(channel='can0', bustype='socketcan')
    
    while True:
        msg = bus.recv(1.0) 
        
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


            # --- PROCESAMIENTO TRAMA ENERGÍA (0x102) ---
            elif msg.arbitration_id == 0x102:
                # Voltaje viene escalado por 100 (usamos la función por defecto)
                volts = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=100.0)
                # Corriente y Potencia vienen escaladas por 1000 (miliAmperios y miliVatios)
                amps = bytes_to_float_escalado(msg.data[2], msg.data[3], escala=1000.0)
                watts = bytes_to_float_escalado(msg.data[4], msg.data[5], escala=1000.0)
                
                telemetria_vipv["Voltaje"] = volts
                telemetria_vipv["Corriente"] = amps
                telemetria_vipv["Potencia"] = watts
                telemetria_vipv["Heartbeat_Energia"] = msg.data[7]

                print(f"[ENERGÍA] V: {volts:.2f}V | I: {amps:.3f}A | P: {watts:.2f}W | Seq: {msg.data[7]}")
               


            # --- PROCESAMIENTO TRAMA IRRADIANCIA (0x103) ---
            elif msg.arbitration_id == 0x103:
                # Desescalar dividiendo por 10
                irr = bytes_to_float_escalado(msg.data[0], msg.data[1], escala=10.0)

                telemetria_vipv["Irradiancia"] = irr
                telemetria_vipv["Heartbeat_Irradiancia"] = msg.data[7]

                print(f"[ILUMINACIÓN] Irradiancia: {irr:.1f} W/m2 | Seq: {msg.data[7]}")
                pass


except KeyboardInterrupt:
    print("\nDetenido por el usuario. Cerrando conexión...")
except Exception as e:
    print(f"\n❌ Error de red CAN: {e}")
finally:
    if 'bus' in locals():
        bus.shutdown()
        print("Bus CAN liberado correctamente.")
