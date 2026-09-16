# Validación V154 — Arquitectura repositorio/rama de publicación

V154 corrige la semántica y la arquitectura del publicador Git.

- El **repositorio local** es el checkout Git que el usuario selecciona; puede llamarse y estar ubicado como quiera en cada PC.
- El **remoto** es `origin` del checkout.
- La **rama destino** es la rama Git activa; `main/master/trunk` continúan bloqueadas.
- `CorePulse_V154` es únicamente la **carpeta de CorePulse dentro del repositorio**, no el destino Git.
- Para GitHub se muestra la URL navegable de la rama cuando puede derivarse del remoto HTTPS/SSH.
- Publicar en rama ya no genera ZIP/SHA de Release: updater/releases quedan desacoplados del publicador de desarrollo.
- FASE 1, FASE 2 y FASE 3 siguen fuera del staging y se validan antes/después.
- Corregido el respaldo de carpeta local no rastreada para que se mueva una sola vez.
- No hay rutas de usuario hardcodeadas; funciona con clones en ubicaciones/nombres distintos.

## Resultado de validación
- 10/10 pruebas dirigidas PASS (arquitectura V154 + publicación con backup no rastreado).
- `compileall` PASS.
- Simulación Git con nombre de clon distinto: la raíz remota contiene FASE 1/2/3 + `CorePulse_V154`; no crea una carpeta con el nombre del checkout local.
- Conversión de remoto GitHub HTTPS y SSH a URL de rama validada.
- Archivos protegidos runtime/NVMe-SMART byte-idénticos a V153.
