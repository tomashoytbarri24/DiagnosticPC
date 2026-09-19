# Validación V180

- Sólo discos físicos en Linux: zram/loop/ram/dm excluidos.
- Salud NVMe Linux: UDisks2 NVMe SMART + fallback smartctl.
- Tarjetas de almacenamiento sin particiones/subvolúmenes en el título.
- Discos no montados conservan modelo/capacidad y no inventan uso.
- Windows conserva reglas anteriores de salud y desgaste.
- Quality Gate debe finalizar en PASS.
