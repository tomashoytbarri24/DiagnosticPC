# Validación CorePulse V175

## Alcance
- Diagnóstico completo específico de Linux.
- Battery Health Linux vía `/sys/class/power_supply`.
- Apertura de Releases con solicitud de foco al navegador.

## Resultado automatizado
- Quality Gate: PASS.
- Suite actual: 197 pruebas correctas, 15 omitidas por entorno GUI/hardware, 180 snapshots históricos fuera del gate, 11 subtests.
- Pruebas V175 específicas: 5/5.

## Pendiente de validación física
- Confirmar en el Acer Nitro que sysfs expone `charge_full_design`/`charge_full` o `energy_full_design`/`energy_full`.
- Confirmar foco del navegador bajo la sesión KDE/Wayland real; el compositor puede aplicar prevención de robo de foco.
