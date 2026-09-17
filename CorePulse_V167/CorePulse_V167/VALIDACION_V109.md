# VALIDACIÓN V109

- Benchmark GPU: firmas Win32 pointer-safe completas para `CreateWindowExW` en Python x64; corrige `argument 11: OverflowError`.
- Benchmark CPU: fallback real directo a LibreHardwareMonitor para temperatura cuando el alias de telemetría no está publicado.
- NVMe SMART: consulta tanto `StorageDeviceProtocolSpecificProperty` como `StorageAdapterProtocolSpecificProperty` para mejorar compatibilidad con VMD/RST/controladores portátiles.
- El porcentaje mostrado como **Salud SMART** se obtiene de `Percentage Used`/`Wear` real (`100 - desgaste`) y permanece marcado internamente como derivado; no se convierte `Healthy` en 100%.
- Runtime canónico preservado.
