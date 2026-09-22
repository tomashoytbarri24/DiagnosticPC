# Validación V262 — Git Destinations & Release Flow

## Objetivo

Permitir que la misma copia de CorePulse publique su carpeta de versión en una rama remota elegida por el usuario, incluyendo `main`, sin cambiar de checkout local y sin mezclar otros archivos del repositorio.

## Pruebas realizadas

- Compilación de todos los archivos Python del proyecto.
- Suite de integridad V262: 9 pruebas.
- Repositorio Git temporal con `main` y `maxi/corepulse-dev`.
- Publicación de V262 a `origin/main` mientras el checkout local permanecía en `maxi/corepulse-dev`.
- Cambio staged dentro de `FASE 1` antes de publicar: permaneció staged localmente y no entró al commit remoto.
- Verificación de que `.github`, FASE 1/2/3 y una versión anterior permanecieron sin cambios en `main`.
- Verificación de que la rama remota de desarrollo no recibió V262 cuando el destino fue `main`.
- Verificación de plantillas de Actions para desarrollo y estable.

## Contrato

- Sin `force-push`.
- Sin checkout/pull/merge automático.
- Sin modificaciones a `.github` desde CorePulse.
- Sólo la carpeta de la versión actual puede formar parte del commit preparado.
- `main` exige confirmación explícita en la interfaz.
