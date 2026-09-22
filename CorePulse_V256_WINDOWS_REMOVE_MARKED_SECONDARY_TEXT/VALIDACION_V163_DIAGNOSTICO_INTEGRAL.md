# CorePulse V163 — Diagnóstico Integral 5.0

## Objetivo
Un solo botón de diagnóstico ejecuta y conserva evidencia por etapas, sin promedios externos ni reparaciones automáticas.

## Flujo
1. Telemetría inicial / línea base.
2. Identificación de componentes, temperaturas, uso, batería y almacenamiento.
3. Estado de Windows: inicio, servicios, estabilidad y controladores.
4. Integridad: DISM CheckHealth + ScanHealth, SFC VerifyOnly y CHKDSK /scan.
5. Benchmark CPU/RAM/SSD/GPU.
6. Estrés separado CPU/RAM/GPU con límites térmicos de seguridad.
7. Respuesta de ventiladores sólo si RPM/control son expuestos por hardware/driver.
8. Audio: usa únicamente evidencia de prueba guiada reciente; nunca afirma audición sin confirmación humana.
9. Correlación final y habilitación del PDF.

## Reglas
- REAL_OR_NA.
- Benchmark y estrés son pruebas distintas.
- El estrés no publica score de rendimiento.
- DISM/SFC/CHKDSK del diagnóstico no ejecutan reparaciones.
- Sin sensor de ventilador: N/A, no fallo inventado.
- Sin prueba guiada de audio: NO EVALUADO.
- El historial no se usa para fabricar el diagnóstico actual.

## Validación ejecutada en entorno de desarrollo
- Compilación Python de módulos modificados: PASS.
- Smoke test de orquestación con fuentes simuladas controladas: PASS.
- Orden de fases: PASS (9/9).
- Política sin reparaciones automáticas: PASS.
- Benchmark separado de estrés: PASS.
- Ventilador con evidencia RPM: PASS.
- Audio sin inferencia automática: PASS.

La ejecución física de DISM/SFC/CHKDSK, sensores, benchmark, estrés y audio debe comprobarse en Windows real.
