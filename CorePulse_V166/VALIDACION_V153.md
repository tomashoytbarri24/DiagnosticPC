# Validación V153

## Objetivo
Resolver el caso real donde Git todavía registra una versión anterior de CorePulse (por ejemplo V136), mientras la carpeta destino de la nueva versión ya existe localmente y difiere de la copia que está ejecutando CorePulse.

## Comportamiento
- Una carpeta destino distinta pero no rastreada ni preparada en Git ya no bloquea la publicación.
- Antes de sustituirla, CorePulse la mueve a un respaldo persistente fuera del repositorio.
- La versión en ejecución se copia al destino, se retira la versión CorePulse antigua del commit y se hace commit/push únicamente del ámbito CorePulse.
- Si la carpeta destino ya contiene cambios Git preparados/rastreados, se mantiene el bloqueo de seguridad.
- FASE 1, FASE 2 y FASE 3 no se incluyen en el commit.

## Pruebas
- `tests/test_v153_untracked_target_sync_publish.py`: 4/4 PASS.
- Regresiones selectivas V151 de publicación/cancelación: 4/4 PASS.
- `python -m compileall -q core gui main.py`: PASS.
