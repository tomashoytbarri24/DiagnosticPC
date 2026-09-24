# VALIDACIÓN V311 — SIDEBAR IDLE SETTLED COMMIT

## Base
- V310

## Problema observado
- Durante 1–2 frames al finalizar el slide aparecían textos/tarjetas duplicadas antes de estabilizarse.

## Cambio
- WM_SETREDRAW permanece desactivado un ciclo idle adicional.
- CustomTkinter resuelve sus redraws internos antes de publicar el frame final.
- Matplotlib sigue redibujándose después, con draw_idle.
