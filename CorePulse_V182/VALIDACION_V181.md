# Validación V181

- Evidencia permanece oculta hasta que exista un hallazgo WARNING/CRITICAL con valores reales y el usuario la abra.
- Las tarjetas CPU/GPU/RAM y las siguientes filas rellenan la misma altura visual dentro de cada fila.
- Diagnóstico automático de audio: izquierda, derecha, ambos y apertura breve del stream de micrófono.
- Linux: benchmark GPU visible por X11/GLX/OpenGL; bajo Wayland usa XWayland cuando `DISPLAY` está disponible.
- Windows: benchmark visual multifase sin cambios de metodología.
- Módulo Benchmark de Linux permite seleccionar GPU, CPU, RAM y SSD.
- No se introducen dependencias Python nuevas para el benchmark Linux.
