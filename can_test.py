import can

print("Iniciando conexión GS_USB con WinUSB...")

try:
    # Ahora sí, el USB está libre y gs_usb puede tomar el control
    bus = can.Bus(interface='gs_usb', channel=0, bitrate=500000)
    
    print("¡ÉXITO! Luces encendidas y escuchando a 500K.")
    print("Esperando mensajes de tu STM32... (Pulsa Ctrl+C para salir)\n")

    while True:
        msg = bus.recv(2.0) 
        
        if msg is not None:
            datos_hex = [hex(byte) for byte in msg.data]
            print(f"-> RECIBIDO | ID: {hex(msg.arbitration_id)} | Datos: {datos_hex}")

except Exception as e:
    print(f"\n❌ ERROR: {e}")