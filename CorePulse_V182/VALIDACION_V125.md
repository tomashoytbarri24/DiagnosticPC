# VALIDACIÓN V125

## Objetivo
Validar que el benchmark aplique cargas reales configurables, que Recuperación muestre los puntos de restauración existentes y que Temas sea visible sin alterar runtime/SMART.

## Comprobaciones
- PASS — versión `125` y stage `REAL_CONFIGURABLE_BENCHMARK_RESTORE_POINTS_THEME_VISIBILITY`.
- PASS — perfiles Rápido / Estándar / Extendido conservados.
- PASS — benchmark configura componentes antes de ejecutar: GPU, CPU, RAM y SSD.
- PASS — GPU usa `run_visual_benchmark(... components=['gpu'])` con carga 3D reforzada.
- PASS — CPU/RAM/SSD usan `run_benchmark_suite` y workloads reales.
- PASS — smoke real local: CPU SHA-256 > 0, RAM copy > 0 y SSD lectura/escritura > 0.
- PASS — renderer OpenGL real se muestra y un adaptador distinto genera aviso visible.
- PASS — `Get-ComputerRestorePoint` ya no se limita a cinco filas y normaliza fecha/hora.
- PASS — UI lista descripción, fecha, tipo y secuencia de todos los puntos devueltos.
- PASS — botón `Actualizar lista`.
- PASS — `Temas` usa una sección `PERSONALIZACIÓN` y el accent del tema activo.
- PASS — `compileall` completo.
- PASS — runtime canónico y SMART/NVMe idénticos a V124.

## Política
`REAL_OR_NA`, `REAL_FPS_OR_NA_ONLY` y `NO_REFERENCE_RANKING` se mantienen.
