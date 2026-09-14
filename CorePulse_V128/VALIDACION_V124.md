# Validación CorePulse V124

## Objetivo
Integrar de forma acumulativa la rama V113 entregada por Tomás con las mejoras V114–V123 desarrolladas en paralelo, sin eliminar archivos ni funciones de la base de Tomás.

## Integración preservada
- Se conservaron todos los archivos presentes en la carpeta `CorePulse_113` de Tomás.
- Se mantuvieron su Benchmark visual 3D multiphase, página principal Benchmark, mejoras de dashboard, drivers, gaming/artwork, sidebar y pruebas V113 asociadas.
- Se añadieron las capas V114–V123: historial de benchmark/salud, diagnóstico de sensores, acceso a PDF, Antes vs Después automático, actualizador interno, recuperación de sesión, evaluación inteligente, Startup Analyzer y correcciones NVMe/SMART.
- Se conservaron los archivos del runtime universal: `core/runtime_venv_path.py`, `bootstrap_corepulse.py`, `core/source_runtime_bootstrap.py` y `requirements-runtime-lock.txt`.

## Temas V124
- La vista aplicada usa los hexadecimales exactos del rol de la paleta elegida.
- Los colores heredados se clasifican contra el rol original CorePulse más cercano en vez de usar umbrales de luminosidad que podían oscurecer superficies.
- La pantalla de carga usa directamente `bg`, `surface`, `surface_2`, `border`, `text`, `text_2`, `muted` y `accent` del tema activo.
- Cambiar de tema y reiniciar CorePulse también cambia la pantalla de carga.

## Validaciones realizadas
- `python -m compileall -q .`: PASS.
- Integridad de archivos de Tomás: 0 archivos faltantes en la carpeta V124 respecto de su V113.
- Paletas: los 10 roles principales aplicados coinciden con el hexadecimal exacto de cada perfil probado.
- No existen marcadores de conflicto Git en Python/Markdown.
- El historial de benchmark fue adaptado al resultado `HARDWARE_VISUAL_MULTI_PHASE` y no reemplaza el benchmark de Tomás.
