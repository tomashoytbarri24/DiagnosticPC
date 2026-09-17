# VALIDACIÓN V111

## Objetivo
Evitar reflows visuales destructivos al mover, maximizar/restaurar, redimensionar o cambiar de módulo.

## Contratos
- Mover sin cambiar tamaño no reconfigura el Dashboard.
- Dentro del mismo breakpoint sólo se sincroniza geometría dependiente del viewport.
- Un cambio de breakpoint realiza un único reflow al finalizar el resize.
- Páginas internas se mantienen cacheadas y se ocultan con `place_forget`, no se destruyen.
- Una página no cacheada se construye fuera del viewport mientras la anterior permanece visible.
- El runtime universal canónico permanece intacto.
