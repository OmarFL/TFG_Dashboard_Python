# TFG: Estación Base y Monitorización (Python)

Este repositorio contiene el *software* desarrollado en Python que actúa como estación base para la recepción y tratamiento de los datos del Trabajo de Fin de Grado.

El código alojado aquí cumple el rol de capa de presentación y almacenamiento, ejecutando las siguientes funciones:
1. **Recepción de red:** Escucha y decodificación en tiempo real de los mensajes de alta velocidad (500 kbps) provenientes del bus CAN del vehículo.
2. **Interfaz gráfica:** Despliegue de un panel de control interactivo que permite visualizar de forma instantánea el comportamiento eléctrico y cinemático del sistema fotovoltaico durante la conducción.
3. **Registro de datos (Datalogging):** Exportación automática y estructurada de las variables físicas a archivos CSV, garantizando la persistencia de los datos para su posterior cálculo analítico y validación de eficiencia.

---
Omar Ftouh Labrouzi - Trabajo de Fin de Grado (Ingeniería Electrónica Industrial y Automática, Universidad Politécnica de Madrid).
