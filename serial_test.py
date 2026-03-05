import serial

# --- CONFIGURACIÓN ---
# ¡IMPORTANTE! Cambia 'COM3' por el número de puerto que usabas en tu PuTTY
PUERTO = 'COM3' 
BAUDIOS = 115200 # La misma velocidad que tenías en PuTTY y en tu STM32

print(f"Intentando conectar al puerto {PUERTO}...")

try:
    # Abrimos la conexión serie (igual que el botón 'Open' de PuTTY)
    conexion = serial.Serial(PUERTO, BAUDIOS, timeout=1)
    print(f"¡ÉXITO! Conectado a {PUERTO}. Escuchando a la placa...\n")

    while True:
        # Si hay datos esperando en el cable...
        if conexion.in_waiting > 0:
            # Leemos la línea entera, la decodificamos a texto normal y quitamos espacios extra
            linea = conexion.readline().decode('utf-8', errors='ignore').strip()
            
            # Si la línea no está vacía, la imprimimos
            if linea:
                print(f"-> {linea}")

except serial.SerialException as e:
    print(f"\n❌ ERROR de puerto: {e}")
    print("¿Estás 100% seguro de que has cerrado PuTTY?")
except KeyboardInterrupt:
    print("\nLectura detenida por el usuario.")
finally:
    # Si cerramos el programa, nos aseguramos de soltar el puerto
    if 'conexion' in locals() and conexion.is_open:
        conexion.close()
        print("Puerto liberado correctamente.")