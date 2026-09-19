# Validación CorePulse V171 — Linux compatibility foundation

## Objetivo

Hacer que el mismo árbol fuente de CorePulse pueda iniciar y trabajar en Windows y Linux, manteniendo la política REAL_OR_NA y sin simular equivalentes de funciones exclusivas de Windows.

## Implementado

- Launch gate Linux y rutas de usuario mediante `platformdirs`.
- Telemetría Linux nativa: CPU/RAM, hwmon/sysfs, DRM, `nvidia-smi`, batería power_supply.
- Identidad Linux: DMI sysfs, `/proc/cpuinfo`, DRM y `lsblk`.
- SMART Linux: `smartctl` cuando está disponible.
- Audio Linux: ALSA `aplay`/`arecord`; amplitud de tono 0.32; sin cambiar volumen maestro.
- Apertura de PDFs con `xdg-open`.
- Actualizador side-by-side compatible con espera de proceso Linux.
- Tweaks Windows y Gaming/Overlay Windows quedan deshabilitados/N/A en Linux, no emulados.

## Distribución

V171 Linux es una versión **portable/fuente**. El ejecutable/instalador nativo Linux queda fuera de esta primera fase.

## Hardware real pendiente

Validar en el Linux del usuario: temperatura CPU según hwmon, GPU según driver, audio ALSA, batería si existe, SMART con permisos y actualización V171→V172 cuando exista una release posterior.
