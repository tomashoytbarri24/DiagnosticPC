# VALIDACIÓN V0.10.2.99w — Startup Integrity Deadlock Fix

## Problema corregido
El gate podía quedar detenido en `Monitoreo en tiempo real activo` con la barra cerca del 80% aunque la telemetría ya estuviera aplicada. Ese porcentaje corresponde a layout + gráficos + servicios listos mientras `integrity` seguía esperando.

## Corrección
- La primera telemetría real aplicada continúa siendo obligatoria.
- La auditoría profunda tiene un máximo de espera visual de 12 segundos.
- HardwareMonitor se sondea en proceso separado con timeout de 5 segundos en modo fuente.
- Un timeout de sensores opcionales se representa como N/A y no bloquea el panel.
- La auditoría puede terminar después y conserva su capacidad de reportar fallos reales.

## Runtime canónico
No se modifican `core/runtime_venv_path.py`, `bootstrap_corepulse.py`, `core/source_runtime_bootstrap.py` ni `requirements-runtime-lock.txt`.
