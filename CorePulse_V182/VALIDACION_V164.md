# Validación CorePulse V164

Base: V163. Esta versión cambia únicamente la arquitectura de publicación Git visible y agrega perfiles persistentes; no modifica Benchmark, Overlay, Diagnóstico, audio ni planes de energía.

## Cambios principales
- Perfiles de publicación persistentes en AppData/configuración de usuario.
- Cada perfil guarda nombre, raíz del clon, origin, rama, `user.name` y `user.email`.
- No se guardan tokens, contraseñas ni credenciales.
- La carpeta seleccionada es la raíz real del repositorio a publicar.
- El nuevo flujo usa `git add -A` sobre la raíz, por lo que altas/modificaciones/eliminaciones se detectan por Git y `.gitignore` sigue vigente.
- FASE 1/2/3 participan sólo cuando cambian; no tienen reglas especiales en el flujo V164.
- Se bloquean `main`, `master`, `trunk`, detached HEAD, conflictos y operaciones Git incompletas.
- Antes del commit/push se consulta la rama remota y se bloquea cualquier situación que requiera force-push.
- El índice se prepara de forma transaccional mediante un índice temporal, preservando el patrón seguro ya usado en V163.

## Pruebas automatizadas realizadas
- `tests/test_v164_publication_profiles.py`: 5/5 OK.
  - persistencia de perfiles sin credenciales;
  - publicación de cambios en CorePulse y FASE 1/2/3;
  - respeto de `.gitignore`;
  - no publicar cuando no hay cambios;
  - bloqueo de `main`.
- `tests/test_publish_in_place.py`: 13/13 OK + 2 subtests, confirmando que el publicador histórico V163 permanece compatible.
- `py_compile` de los módulos nuevos/modificados: OK.

## Archivos protegidos
Los SHA-256 de los archivos críticos no modificados se registran en `PROTEGIDOS_V164_SHA256.json`.

## Cómo probar V164 en Windows
1. Ejecutar `Iniciar_CorePulse.bat` y confirmar V164.
2. Ir a Personalización > Actualizaciones > Publicar.
3. Crear perfil `Maxi`.
4. Seleccionar `C:\Users\Maxi\Desktop\DiagnosticPC-Maxi` como carpeta raíz.
5. Confirmar que origin apunte a `tomashoytbarri24/DiagnosticPC` y que la rama sea `maxi/corepulse-dev`.
6. Confirmar usuario/correo Git y pulsar `Guardar perfil`.
7. Si la rama configurada no está activa, pulsar `Activar rama`.
8. Pulsar `Revisar`: debe mostrar sólo los archivos realmente cambiados en toda la raíz.
9. Si no hay cambios, el botón debe quedar en `Sin cambios`.
10. Realizar un cambio pequeño controlado, volver a `Revisar` y publicar. Verificar en GitHub que sólo aparece ese cambio y que la estructura raíz del repositorio se conserva.

## Limitaciones de esta validación
El entorno de construcción no es Windows y no dispone de la sesión GitHub real del usuario. Se validó el flujo con repositorios Git y remotos bare locales reales; la autenticación de GitHub/Git Credential Manager debe comprobarse en el PC de Maxi/Tomás.
