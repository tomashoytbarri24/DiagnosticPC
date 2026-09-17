# Validación V145

## Objetivo
Corregir el cierre desde X y mejorar la composición del Dashboard en modo ventana sin alterar el modo maximizado.

## Contrato
- `WM_DELETE_WINDOW` llama a `minimize_to_tray`.
- `on_close` conserva el apagado real para `Salir de CorePulse`, actualizaciones y reinicios explícitos.
- Si pystray está listo, X hace `withdraw()` y el agente continúa.
- Si la bandeja aún no está lista, X usa `iconify()` y nunca destruye el proceso.
- Restaurar desde bandeja conserva `zoomed`/geometría normal.
- Recomendado 1080p: 1560×860; el modo compacto reduce altura de header, estado, métricas, storage y tendencias.
- Runtime y NVMe/SMART protegidos permanecen byte-identical a V144.
