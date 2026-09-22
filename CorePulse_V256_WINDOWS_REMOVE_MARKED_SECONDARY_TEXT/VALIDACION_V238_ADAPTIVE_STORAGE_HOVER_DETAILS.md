# V238 — Adaptive Storage + Hover Details

## Objetivo
Corregir el bloque de almacenamiento del Resumen para múltiples unidades reales y reducir el ruido visual del botón de detalles.

## Comportamiento
- 1 unidad: tarjeta compacta.
- 2 unidades: ambas tarjetas se muestran completas.
- 3 o más unidades: se mantiene un viewport equivalente a dos tarjetas y se habilita scroll interno.
- USB/HDD/SSD/NVMe adicionales que lleguen por `update_disks_ui` crean su propia tarjeta.
- `Ver detalles` permanece oculto y aparece únicamente al pasar el mouse por la tarjeta de esa unidad.
- Cada tarjeta conserva su SMART, capacidad, temperatura, porcentaje y barra reales / N/A.

## Política
Se mantiene REAL_OR_NA. No se inventan unidades ni métricas.
