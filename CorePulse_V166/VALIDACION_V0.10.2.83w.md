# Validación — CorePulse V0.10.2.83w

## Instant Detail Card Navigation

Objetivo: eliminar la espera perceptible al abrir CPU, RAM, GPU o almacenamiento desde el Resumen sin alterar telemetría ni REAL_OR_NA.

Cambios validados:
- shell visible publicado antes de construir el árbol CTk de detalle;
- creación del panel real diferida un frame (~16 ms);
- CPU/RAM/GPU/almacenamiento añadidos a la caché de navegación;
- asociación del panel real sin segundo `commit` ni nuevo `polish_widget_tree()` global;
- CPU/RAM/GPU pausan el refresco periódico cuando quedan ocultos;
- hover contextual `Ver detalles` de 82w preservado;
- Safe Storage Scanner de 81w preservado.

## Resultado

- `compileall`: PASS
- 26 suites relevantes: PASS
- `corepulse_launcher.py --corepulse-helper-probe`: PASS
- versión reportada por helper: `0.10.2.83w`

La ejecución visual real de CustomTkinter/EXE en Windows debe validarse en un equipo Windows, ya que el entorno de empaquetado no reproduce el compositor/DPI de Windows.
