# Validación V179

Objetivo: corregir almacenamiento físico, carpeta de informes y layout del diagnóstico sin romper Windows/Linux.

- Inventario Linux detecta discos físicos montados y no montados mediante lsblk.
- El disco del sistema se marca por el mountpoint `/`; otros discos se mantienen visibles aunque no estén montados.
- Windows conserva Win32_DiskDrive/LHM.
- La carpeta de informes usa os.startfile en Windows, xdg-open en Linux y open en macOS.
- Las tarjetas del diagnóstico no se estiran verticalmente por el tamaño del viewport.
- El detalle SMART de Linux usa get_storage_health/smartctl nativo y no intenta `\\.\PhysicalDriveN`.
