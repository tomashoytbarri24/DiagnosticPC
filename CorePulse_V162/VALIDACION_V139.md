# CorePulse V139 — Salud de almacenamiento multi-fuente

## Objetivo
Reducir los casos de `Salud N/A` sin inventar valores, manteniendo `REAL_OR_NA`.

## Fuentes y prioridad
1. NVMe SMART/Health Log nativo de Windows.
2. `smartctl`/smartmontools cuando ya está disponible en el sistema o en `tools/`.
3. Life/Health real expuesto por LibreHardwareMonitor.
4. Windows Storage Reliability `Wear`, incluyendo `Wear=0` únicamente cuando otro contador independiente (horas/ciclos/errores) demuestra que el proveedor está vivo y Windows reporta el disco sano.
5. `HealthStatus` de Windows como estado cualitativo cuando no existe una métrica cuantitativa verificable.

## Seguridad de datos
- Nunca convierte un `Wear=0` aislado en 100%.
- Una temperatura por sí sola no valida `Wear=0`, porque algunos miniports devuelven valores térmicos sentinel.
- No se modifica `core/nvme_smart_windows.py`.
- No hay porcentajes sintéticos por marca/modelo.
