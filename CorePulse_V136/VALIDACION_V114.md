# VALIDACIÓN V114

## Alcance

V114 añade tres mejoras sobre V113 sin alterar el runtime canónico ni la lógica de salud de discos:

1. Historial de benchmark por sesión completa.
2. Diagnóstico de compatibilidad de sensores reutilizando el snapshot certificado actual.
3. Acceso desde Diagnóstico al último PDF generado y a su carpeta.

## Benchmark

- Se conserva el flujo V113: primero perfil + componentes, después ejecución.
- Cada ejecución nueva guarda perfil, componentes, suite completa, comparación antes/después e identidad básica de CPU/GPU.
- La vista Benchmark muestra hasta 5 ejecuciones recientes.
- Si existe una ejecución anterior equivalente (mismo perfil, mismos componentes y hardware compatible), muestra variación porcentual.
- No existen rankings externos ni valores inventados.

## Sensores

- Nuevo `core/sensor_diagnostics.py`.
- Consume `_hardware_capability_matrix` y `_metrics` del último snapshot ya disponible.
- No lanza sondeos nuevos de hardware.
- Mantiene REAL_OR_NA: sensor no expuesto => N/A.
- Resume CPU, RAM, GPU, almacenamiento y batería cuando corresponda.

## PDF

- Tras generar un informe, CorePulse recuerda el último PDF válido.
- Diagnóstico añade:
  - `Abrir último PDF`
  - `Mostrar carpeta`
- La ruta se conserva en el directorio de datos de CorePulse mediante `last_pdf_report.txt`.
- Si el archivo ya no existe, los accesos quedan deshabilitados/no disponibles.

## Pruebas

`tests/test_v114_history_sensors_report_access.py`

- PASS version
- PASS stage
- PASS sensor_cpu_present
- PASS sensor_gpu_partial
- PASS sensor_storage_real_or_na
- PASS sensor_no_extra_probe_policy
- PASS benchmark_session_saved
- PASS benchmark_profile_saved
- PASS benchmark_components_saved
- PASS benchmark_suite_saved
- PASS benchmark_history_ui
- PASS sensor_diagnostics_ui
- PASS report_open_button
- PASS report_folder_button
- PASS report_path_persisted

También pasan:

- `tests/test_pdf_button_flow.py`
- `tests/test_integrity.py`
- `compileall` del proyecto.

## Runtime canónico preservado

Los siguientes archivos permanecen byte-for-byte idénticos a V113:

- `core/runtime_venv_path.py`
- `bootstrap_corepulse.py`
- `core/source_runtime_bootstrap.py`
- `requirements-runtime-lock.txt`

## Salud de discos preservada

Los siguientes archivos permanecen byte-for-byte idénticos a V113:

- `core/storage_summary_health.py`
- `core/storage_health.py`
- `core/nvme_smart_windows.py`
- `gui/hardware_storage_view.py`

**Resultado: PASS**
