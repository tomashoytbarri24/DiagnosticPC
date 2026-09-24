# VALIDACIÓN V299 — CPU FREQUENCY UNIVERSAL FIX

## Objetivo
Evitar `Frecuencia de CPU: N/A` en PCs donde LibreHardwareMonitor no publica sensores Clock, sin inventar datos.

## Fuentes reales en orden
1. LibreHardwareMonitorLib (clocks por núcleo).
2. psutil.cpu_freq().current.
3. Win32_PerfFormattedData_Counters_ProcessorInformation.
4. Win32_Processor.CurrentClockSpeed.

## Política
REAL_OR_NA. Cada fallback conserva fuente, sensor, timestamp y si el valor fue derivado de contadores reales.
