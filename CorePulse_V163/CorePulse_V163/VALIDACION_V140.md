# Validación V140 — Wear real de Windows + claridad de benchmark

## Objetivos
- Aceptar `Wear=0` de Windows Storage Reliability sólo cuando el mismo contador demuestra actividad real mediante latencias de E/S, horas, ciclos o errores, y Windows informa Healthy/OK.
- Mantener `REAL_OR_NA`: `HealthStatus=Healthy` por sí solo nunca genera un porcentaje.
- Evitar placeholders CPU/RAM dentro de la cuadrícula de fases GPU 3D.
- Mostrar la fase `Carga combinada` real y aclarar la transición GPU 3D → CPU/RAM/SSD.
- Mostrar el volumen donde realmente se ejecutó la prueba SSD.

## Evidencia que motivó V140
En el equipo de prueba, `Get-StorageReliabilityCounter` expone para ambos NVMe:
- `Wear = 0`
- temperatura real
- `ReadLatencyMax`, `WriteLatencyMax` y/o `FlushLatencyMax` no cero
- `HealthStatus = Healthy` y `OperationalStatus = OK`

Esto permite validar que el Reliability Counter está activo sin depender de PowerOnHours/ciclos, que ese controlador no expone.

## Pruebas
- `python -m compileall -q .` → PASS
- `python tests/test_v140_storage_wear_benchmark_clarity.py` → PASS
- `python tests/test_nvme_smart_windows.py` → PASS

## Archivos protegidos
No se modifican:
- `core/runtime_venv_path.py`
- `bootstrap_corepulse.py`
- `core/source_runtime_bootstrap.py`
- `requirements-runtime-lock.txt`
- `core/nvme_smart_windows.py`
