# CorePulse V0.10.2.81w — Validación

## Objetivo
Añadir un escáner de almacenamiento simple para el usuario y restrictivo internamente, preservando el diseño de limpieza de la base 78w.

## Contratos
- `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY` intactos.
- Allowlist determinista: una ruta no reconocida nunca se convierte en candidato.
- Sólo unidades locales fijas.
- No symlinks/junctions/reparse points ni hardlinks.
- Temporales con antigüedad mínima de 24 horas.
- Revalidación exacta antes de eliminar: regla, ruta, patrón, tamaño y mtime.
- Ningún archivo personal o carpeta de sistema no permitida se borra automáticamente.

## Validación ejecutada
- `python -m compileall -q .`: PASS.
- `tests/test_safe_storage_scanner.py`: PASS (20 checks).
- Regresiones críticas de sidebar, visuales, almacenamiento, Centro de Salud, Windows, startup, Gaming, CPU/GPU, rollback, EXE e instalador: 20/20 suites PASS.

## Limitación de entorno
El render final de CustomTkinter y el EXE congelado deben validarse en Windows real; el contenedor de validación no reproduce el shell/ACL/locking de Windows.
