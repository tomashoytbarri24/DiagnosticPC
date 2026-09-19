# VALIDACIÓN V0.10.2.98w

## Base canónica

V0.10.2.98w fue construida sobre `V0.10.2.97w_UNIVERSAL_RUNTIME_FIX`.
Los siguientes archivos se conservaron **byte a byte** respecto de la base canónica:

- `core/runtime_venv_path.py`
- `bootstrap_corepulse.py`
- `core/source_runtime_bootstrap.py`
- `requirements-runtime-lock.txt`

En Windows el runtime fuente continúa resolviéndose bajo `%USERPROFILE%\.corepulse\runtime\py312_<hash>`.

## Correcciones

### Atajo exacto del Overlay

- La captura ya no consulta `event.state`.
- Sólo se conservan modificadores cuya pulsación fue capturada explícitamente.
- `Ctrl+9` se guarda como `Ctrl+9`; no se inserta `Alt` automáticamente.
- Atajos heredados de la captura antigua deben grabarse una vez para pasar a captura V2.

### Métricas visibles

- El panel izquierdo ya no se estira verticalmente hasta igualar la columna derecha.
- Se conserva el layout responsive de una/dos columnas.
- La última métrica ocupa el ancho disponible cuando queda sola en una fila.

### RTSS / RivaTuner Statistics Server

- Si el Overlay se inicia y Shared Memory aún no está disponible, CorePulse intenta abrir `RTSS.exe` automáticamente.
- Evita lanzar duplicados cuando RTSS ya está ejecutándose.
- Busca RTSS por registro, App Paths, desinstalador y rutas habituales de RTSS/MSI Afterburner.
- Reintenta el enlace mientras RTSS termina de iniciar.

## Pruebas automatizadas ejecutadas

- `test_canonical_runtime_guard_v098.py` — PASS
- `test_overlay_exact_hotkey_rtss_autostart_v098.py` — PASS
- `test_short_runtime_path_fix.py` — PASS
- `test_self_bootstrapping_runtime_restore.py` — PASS
- `test_bootstrap_pip_resilience_fix.py` — PASS
- `test_bootstrap_relaunch_loop_fix.py` — PASS
- `test_theme_toggle.py` — PASS
- `test_hardware_policy.py` — PASS
- `test_startup_gate_progressive_release.py` — PASS
- `test_startup.py` — PASS
- `test_integrity.py` — PASS
- `test_first_telemetry_ready_gate.py` — PASS

La ejecución física final debe comprobarse en ambos PCs Windows objetivo, ya que este entorno no puede ejecutar el hardware/RTSS de Tomás ni del segundo equipo.
