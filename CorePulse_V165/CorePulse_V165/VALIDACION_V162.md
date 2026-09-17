# Validación CorePulse V162 — Benchmark 2.0

Base: `v161` entregada por el usuario, equivalente en código fuente a `CorePulse_v161_GitPublisherFix.zip` (los archivos adicionales del RAR eran `__pycache__`). Cambio limitado al benchmark, su interpretación/persistencia y el uso del benchmark dentro de Diagnóstico.

## Qué cambia

- `COREPULSE_BENCHMARK_2` identifica la nueva metodología y evita comparar porcentajes contra sesiones antiguas no equivalentes.
- CPU conserva la carga SHA-256 sostenida real y registra método `COREPULSE_CPU_SHA256_V2`.
- RAM conserva la copia real de memoria, pero se describe como **tasa de copia sostenida**, no como ancho de banda DDR máximo.
- SSD en Windows intenta primero E/S directa con `FILE_FLAG_NO_BUFFERING | FILE_FLAG_WRITE_THROUGH`; si Windows/controlador no lo permite, conserva el benchmark real previo pero marca `BUFFERED_FALLBACK` y `cache_resistant=False`.
- GPU del Diagnóstico deja de usar la carga OpenGL simple como benchmark oficial. `run_benchmark_suite` reutiliza el benchmark visual multifase que ya usa el módulo Benchmark.
- El renderer GPU puede normalizar únicamente sufijos técnicos conocidos como `/PCIe/SSE2`. Si no hay una coincidencia única con el inventario real, los sensores permanecen N/A.
- Cancelar durante la fase GPU visual se propaga al Diagnóstico como CANCELLED; no habilita PDF ni resultado final.
- El benchmark deja las conclusiones térmicas al Diagnóstico; la pantalla de benchmark conserva medición y cambios observados.
- Historial: misma metodología/perfil/componentes/hardware/renderer; si se incluye SSD también deben coincidir volumen probado y modo de E/S.

## Qué NO cambia

- No se reintroduce stress automático en Diagnóstico.
- El motor de stress interno sigue presente para compatibilidad/uso avanzado futuro.
- No se modifica SMART/NVMe.
- No se modifica runtime/venv/bootstrap.
- No se modifica el publicador Git funcional de V161.
- No se trabaja en resize/optimización general, audio ni instalador.

## Pruebas ejecutadas

### V162 específicas

`python -m unittest tests.test_v162_benchmark_2_0 -v`

**10/10 aprobadas.** Cubren versión/métodos, renderer híbrido, GPU visual canónica, telemetría de la GPU correcta, SSD fallback explícito, semántica RAM, comparabilidad del historial, ausencia de stress automático, Diagnóstico completo y cancelación durante GPU.

### Regresiones de motor/evidencia V157/V161

`python -m unittest tests.test_v157_diagnostic_lifecycle.EngineTests tests.test_v157_diagnostic_lifecycle.EvidenceTests tests.test_v161_benchmark_diagnostic.TelemetryTests -v`

**17/17 aprobadas.**

### Publicador Git heredado de V161

`python -m unittest tests.test_publish_in_place -v`

**13/13 aprobadas.**

### Smoke real local

- CPU SHA-256: resultado positivo y estado OK.
- RAM copia sostenida: resultado positivo y estado OK.
- SSD: lectura/escritura reales y limpieza del temporal. En este entorno Linux se usa deliberadamente `BUFFERED_FALLBACK`, lo que confirma que el modo queda etiquetado y no se confunde con la ruta directa de Windows.
- `python -m compileall -q .`: aprobado.

## Archivos protegidos

SHA-256 sin cambios respecto de V160/V161:

- `core/runtime_venv_path.py` — `263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92`
- `bootstrap_corepulse.py` — `925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b`
- `core/source_runtime_bootstrap.py` — `bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd`
- `requirements-runtime-lock.txt` — `36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706`
- `core/nvme_smart_windows.py` — `fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283`

## Qué no se pudo validar aquí

Este entorno no es Windows y no incluye la GUI completa de CorePulse. Por tanto no se ejecutaron físicamente:

- la ventana OpenGL multifase real sobre una GPU Windows;
- `CreateFileW` con `NO_BUFFERING/WRITE_THROUGH` sobre tu NVMe;
- un Diagnóstico completo real en tu Nitro;
- tres benchmarks consecutivos para calcular dispersión real.

Esas son las pruebas manuales prioritarias en tu equipo. Si la ruta directa SSD falla por un controlador concreto, V162 no inventa que fue directa: ejecuta el fallback y lo marca explícitamente.

## Cómo probar V162

1. Ejecuta `Iniciar_CorePulse.bat` y confirma **V162**.
2. En **Benchmark**, usa perfil Estándar con CPU/RAM/SSD/GPU y deja terminar; GPU debe abrir sólo su ventana 3D multifase.
3. Repite el benchmark **3 veces** en condiciones similares y guarda capturas/resultados; después revisamos la dispersión CPU/RAM/SSD/GPU.
4. Comprueba SSD: el resultado/evidencia debe identificar el volumen probado y, cuando corresponda, modo de E/S directo/resistente a caché; si aparece fallback, envíame la evidencia.
5. En un portátil híbrido, confirma que el renderer NVIDIA no reciba temperatura/uso de la Intel. N/A es correcto si la identidad no puede verificarse.
6. Ejecuta **Diagnóstico Completo**: debe usar la misma ventana GPU multifase, sin ninguna fase de stress independiente.
7. Cancela una vez durante GPU y reinicia inmediatamente; el cancelado no debe habilitar PDF ni guardarse como benchmark completo.
8. Deja terminar otra ejecución y revisa Historial: V162 no debe calcular un porcentaje contra una sesión V161 como si fueran la misma metodología.
