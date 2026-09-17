# Actualizaciones de CorePulse V166

## Revisión y decisión

Base utilizada: esta carpeta CorePulse_V166. El flujo original ya contenía consulta de GitHub Releases, canales, descarga SHA-256, instalador Inno Setup, copia aislada para Git y aplicador portable con backup. Se reutilizan esas piezas.

**Publicar envía código; una Release distribuye una versión utilizable.** El botón Publicar sigue haciendo commit/push de la raíz seleccionada según el perfil Git. No crea tags, Releases ni adjuntos. No se modificaron `core/developer_publisher.py` ni `core/publication_profiles.py`, ni el flujo de edición/publicación de perfiles. Tampoco se reactivó su antiguo generador ZIP: no ofrecía las exclusiones necesarias para empaquetar una raíz arbitraria sin datos locales.

La solución simple para usuarios finales es conservar el instalador existente:

1. El desarrollador construye y comprueba el instalador.
2. Publica una Release con versión, notas, instalador y SHA-256.
3. El usuario abre Actualizaciones, descarga y verifica, y pulsa Instalar.
4. CorePulse abre el instalador y solicita su cierre normal. Inno Setup gestiona la instalación; su pantalla final ofrece abrir CorePulse.

No se introduce otro motor de instalación ni se vincula el repositorio de actualizaciones al perfil Git activo. Cambiar un perfil de desarrollo no debe cambiar de dónde descargan los usuarios su aplicación.

## Comportamiento por modo

| Ejecución actual | Paquete aceptado | Acción |
|---|---|---|
| CorePulse compilado | Instalador CorePulse Setup/Installer `.exe`, o `.msi` CorePulse | Abrir instalador verificado y cerrar CorePulse |
| Fuente portable fuera de Git | ZIP CorePulse con una única raíz reconocible | Preparar, crear backup, cerrar, aplicar y relanzar |
| Fuente dentro de Git | ZIP CorePulse | Preparar una copia aislada; conservar el checkout |

Esta V166 está dentro del repositorio padre `DiagnosticPC-Maxi`: corresponde al tercer modo. No se desactiva esa protección para aparentar una actualización en el proyecto de desarrollo.

## Cambios realizados

- Estable es el canal inicial si no existe preferencia; se conservan las preferencias de Desarrollo ya guardadas.
- Consulta paginada de Releases; los borradores y prereleases se filtran según el canal. Se distinguen falta de acceso, credencial inválida y limitación de consultas.
- Selección estricta de formato. Un archivo de notas, un ZIP en modo instalado o un instalador en modo fuente no se ofrecen como paquete compatible.
- SHA-256 del digest de GitHub o checksum adjunto asociado al nombre exacto. Un hash de otro paquete deja de aceptarse por ser la única línea del archivo.
- Unificación de la descarga antigua con la descarga verificada. Los parciales se verifican antes de convertirse en el archivo final.
- Cancelación y reintento desde el botón principal durante descarga; limitación de frecuencia de las notificaciones de progreso.
- Nueva comprobación del hash antes de preparar o abrir el paquete. El token sólo se adjunta a peticiones a `api.github.com`; se retira al redirigir fuera de ese host y no se aceptan conexiones HTTP.
- Nombres y carpetas de descarga/preparación controlados; el ZIP rechaza escapes de ruta, aliases ambiguos, duplicados y enlaces simbólicos. La extracción tiene límites de cantidad y tamaño total.
- El ZIP fuente debe identificar una sola raíz y declarar una versión que coincida con la Release, leída sin ejecutar código del paquete.
- El aplicador portable valida destino, ausencia de Git, backup y huellas de archivos preparados antes de reemplazar. Un fallo esperando el cierre deja la instalación intacta. El reinicio prefiere el launcher existente.
- Finalizar una consulta/descarga con la página oculta ya no pierde el resultado ni deja `busy` bloqueado. Una nueva consulta invalida paquetes de consultas anteriores. Se muestra el último estado del aplicador.
- `LATEST_VERSION.txt` se alinea con `core/version.py`: V166.

## Qué debe contener una Release

Repositorio predeterminado: `tomashoytbarri24/DiagnosticPC`, conservado del código anterior. La excepción de entorno `COREPULSE_UPDATE_REPOSITORY=propietario/repositorio` continúa disponible. Los perfiles Git no cambian este destino.

Para una versión futura, por ejemplo V167:

- Tag `V167`, notas y clasificación estable o prerelease.
- `CorePulse_Setup_V167.exe`, generado con `build_exe.bat` y `build_installer.bat` después del self-test existente.
- Si se distribuye fuente portable: `CorePulse_V167.zip`, con `main.py`, `core/version.py` declarando 167, launcher, módulos, recursos y dependencias declaradas del proyecto. Una carpeta superior es válida; varias bases/versiones dentro del ZIP no lo son.
- Digest SHA-256 de GitHub o `CorePulse_Setup_V167.exe.sha256` / `CorePulse_V167.zip.sha256`. Formato recomendado: `<hash de 64 caracteres>  <nombre exacto del paquete>`.

El ZIP debe ser un artefacto de distribución limpio: excluir `.git`, entornos, `.env` y credenciales, datos locales, logs y otras versiones. No usar el ZIP automático de código fuente de GitHub como sustituto de un adjunto de distribución. No basta con modificar `LATEST_VERSION.txt` o pulsar Publicar.

El checksum comprueba integridad respecto de la Release; no sustituye la confianza en la cuenta publicadora ni una firma Authenticode del instalador. La firma de distribución puede añadirse posteriormente sin cambiar este flujo.

## Validación

- **26 pruebas unittest aprobadas**: 22 nuevas y 4 regresiones útiles del actualizador anterior.
- **6 comprobaciones adicionales aprobadas**: perfiles locales sin secretos, publicación real de cambios en remoto Git temporal local, no publicar sin cambios, bloqueo de main, disposición V166 y texto del contador de Publicar.
- Las pruebas de actualización y rollback ejecutan el código del helper en carpetas temporales, con espera de proceso y relanzamiento simulados. Ninguna instala CorePulse en la máquina ni ejecuta un paquete descargado.
- Las pruebas de red usan respuestas simuladas; cubren selección, paginación, checksum, cancelación, reintento, rutas, redirecciones, manipulación del paquete, versión interna, aplicación, fallo de copia y salida de la página.
- Se comprueban sintaxis y hashes de Publicar, perfiles Git y los cinco archivos protegidos históricos al cierre.

Comando reproducible principal:

```powershell
python -m unittest tests.test_v166_release_updates tests.test_internal_updater_v118.InternalUpdaterV118Tests.test_version_parser tests.test_internal_updater_v118.InternalUpdaterV118Tests.test_internal_includes_prerelease_stable_does_not tests.test_internal_updater_v118.InternalUpdaterV118Tests.test_verified_download_and_safe_source_stage tests.test_internal_updater_v118.InternalUpdaterV118Tests.test_bad_digest_is_rejected -q
```

Los tests históricos que exigen literalmente V118/V129/V164 no son la prueba de versión de esta V166. Las seis comprobaciones de funciones de Publicar se ejecutaron con un arnés temporal porque pytest no está instalado en este intérprete.

## Límites y prueba final pendiente

La consulta web pública del repositorio no pudo verificarse desde la herramienta disponible; no se concluye que el repositorio esté vacío o no exista. No se creó una Release real, no se subieron archivos ni se utilizaron credenciales Git para publicar.

No se validaron la GUI real, la instalación compilada, los diálogos nativos de Windows ni el arranque completo de una nueva distribución. El rollback portable existente restaura archivos del backup, pero no representa una transacción atómica de todo el sistema ni garantiza recuperar ante pérdida de energía o permisos que impidan también restaurar. El estado de éxito del helper indica copia aplicada, no certificación funcional del siguiente arranque.

Prueba final recomendada: publicar una prerelease con versión superior y paquetes probados; comprobar y cancelar/reintentar desde una instalación de prueba; probar el instalador; probar el ZIP desde una copia portable descartable; volver a abrir y verificar versión, datos y perfiles. En el checkout V166, probar sólo la preparación aislada.
