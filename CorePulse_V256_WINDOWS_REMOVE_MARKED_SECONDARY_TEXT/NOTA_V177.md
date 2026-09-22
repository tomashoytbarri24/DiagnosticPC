# V177 — cierre y presentación del benchmark

Cambios sobre V176:
- `gui/health_center_panel.py`: actualiza widgets al finalizar, preserva mensaje al reconstruir la pantalla y rechaza callbacks tardíos/de otra ejecución. Presenta ruta JSON copiable y errores de guardado. FPS destacados por escena; duración nominal corregida a 49 s medidos más preparación.
- `core/version.py`, `LATEST_VERSION.txt`, `README.md`, `VERSIONING.md`, `CHANGELOG.md`: identificación y documentación.
- `tests/test_v177_benchmark_ui.py`: regresiones de progreso, reconstrucción, ruta y error de guardado.

Validación: `python -m unittest tests.test_v177_benchmark_ui -v`.
Las pruebas ejecutan métodos reales de interfaz con widgets de prueba, sin iniciar Tk ni fabricar resultados de hardware. No sustituyen una prueba visual en Windows.
El motor, renderer, escenas, telemetría y persistencia se conservan sin cambios respecto de V176. REAL_OR_NA permanece vigente. No se incluye un JSON de ejemplo como si fuera una medición.

Prueba manual: iniciar CorePulse, ejecutar GPU, comprobar 100 % y ruta copiable al terminar, cambiar de sección y regresar; el resultado debe mantenerse. Los cambios gráficos del escenario V13 no forman parte de esta versión.
