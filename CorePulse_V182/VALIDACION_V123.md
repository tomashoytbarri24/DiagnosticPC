# Validación CorePulse V123

Objetivo: corregir el transporte de `IOCTL_STORAGE_QUERY_PROPERTY` para SMART NVMe y garantizar fallback `REAL_OR_NA`.

Validaciones:
- versión/stage V123;
- buffer completo utilizado tanto como entrada como salida en `DeviceIoControl`;
- excepción del miniport NVMe no elimina el `HealthStatus` real de Windows;
- no se inventa porcentaje cuando SMART directo no está disponible;
- temperatura Windows válida permanece disponible como fallback;
- `compileall` del proyecto;
- archivos críticos del runtime idénticos a V122.
