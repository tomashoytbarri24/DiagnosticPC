# Validación V164 - Diagnóstico Total 6.0

Fecha de integración: 2026-09-17

## Objetivo

La pestaña **Iniciar diagnóstico** debe ejecutar una sesión nueva y completa, conservar sólo evidencia real o N/A y terminar mostrando el resultado técnico + interpretación IA. El PDF es opcional y reutiliza el mismo resultado congelado.

## Flujo V164

1. Telemetría inicial / baseline.
2. Componentes, sensores, batería y almacenamiento.
3. Estado de Windows (inicio, servicios, estabilidad y drivers).
4. Integridad: DISM CheckHealth/ScanHealth + SFC VerifyOnly + CHKDSK /scan, sin reparación automática.
5. Benchmark CPU/RAM/SSD/GPU.
6. Estrés CPU/RAM/GPU separado del benchmark y sin score de rendimiento.
7. Respuesta de ventiladores basada en sensores reales; N/A si no existen.
8. Audio: reproducción técnica real o reutilización de prueba guiada reciente. No se inventa confirmación acústica.
9. Limpieza segura automática de temporales/cachés recreables mediante allowlist y revalidación.
10. Correlación determinística de evidencia de esta máquina.
11. IA: explicación + vigencia del hardware para el año de ejecución, sólo con evidencia disponible.

## Política de evidencia

- `REAL_OR_NA`: no se fabrican sensores, temperaturas, FPS, SMART, scores ni estados.
- Sin ranking/promedio externo dentro del benchmark.
- Benchmark y estrés son pruebas distintas.
- Los chequeos de Windows son diagnósticos; no ejecutan reparación automática.
- La limpieza no toca documentos, Descargas, juegos, registro ni rutas fuera de la allowlist recreable.
- La salida física de parlantes requiere confirmación humana para declararse acústicamente verificada.
- Si la IA/proveedor no está disponible, el diagnóstico técnico sigue siendo válido y la IA queda `UNAVAILABLE`/`N/A`.

## Pruebas realizadas en entorno de integración

- `python -m compileall -q core gui main.py`: **PASS**.
- `tests/test_v164_diagnostico_total_6_0.py`: **4 PASS**.
- Flujo simulado completo: **11/11 fases, COMPLETE**.
- Progreso del flujo: corregido para no retroceder entre fases.
- `core/visual_benchmark.py`, `core/benchmark_engine.py`, `core/telemetry.py` y `core/telemetry_full.py`: **sin cambios respecto de V162**.
- Generación PDF con resultado V164 + pipeline vigente: **PASS**, 6 páginas.
- Render del PDF de prueba: **PASS**, icono CorePulse y sección `Diagnóstico Total 6.0` visibles.

## Pendiente de validación física

La validación que sólo puede hacerse en un equipo Windows real debe comprobarse al ejecutar esta versión: sensores LHM/NVML, batería real, SMART disponible, DISM/SFC/CHKDSK, benchmark GPU, estrés, RPM de ventiladores cuando estén expuestas, dispositivo WASAPI de audio, limpieza de temporales y proveedor IA configurado. Cualquier fuente no disponible debe permanecer N/A, no ser sustituida por datos sintéticos.
