# V240 — Storage Multi-Unit Render Fix · SMART Preserved

## Objetivo
Corregir el bug visual al conectar/tener 2+ unidades SIN reemplazar la fuente física de salud/SMART de CorePulse.

## Principio de reparación
V240 parte de V238. Se descarta el enfoque V239 que convirtió volúmenes montados en la fuente principal de la UI, porque podía romper la asociación SMART/health del SSD.

## Cambios
- La telemetría de almacenamiento y salud conserva `_build_fast_disk_snapshot` y `storage_health_cache`.
- El arreglo multiunidad vive sólo en la capa de presentación.
- Se reafirma el orden de tarjetas por índice tras hot-plug.
- Las tarjetas profesionales mantienen alto fijo; otras capas no pueden reactivar `pack_propagate(True)`.
- Se recalculan viewport y scrollregion tras creación/eliminación de unidades.
- 1 unidad = compacta; 2 = ambas visibles; 3+ = dos visibles + scroll.
- El viewport vuelve al inicio tras un cambio de topología.

## REAL_OR_NA
No se inventa salud SMART, temperatura ni montaje. La salud sigue proviniendo de las fuentes físicas ya existentes en CorePulse.
