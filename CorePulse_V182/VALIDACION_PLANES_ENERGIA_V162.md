# V162 — planes de energía idempotentes

Cambio limitado a `performance/power_manager.py`, `performance/profile_manager.py`,
el nuevo `performance/managed_power_plans.py` y `tests/test_managed_power_plans.py`.

## Causa encontrada

La identificación anterior dependía del nombre. Si `/changename` fallaba después
de duplicar, se devolvía éxito y quedaba una copia que la siguiente búsqueda no
reconocía. Tampoco había un registro durable de GUID/base ni exclusión entre
creadores concurrentes. Esto permite duplicados; no demuestra cuál de esas rutas
produjo todas las copias históricas de este equipo.

## Comportamiento

- Registro atómico `managed_power_plans.json` en el directorio de datos de CorePulse
  (habitualmente `%LOCALAPPDATA%\CorePulse`, o `COREPULSE_DATA_DIR`). Guarda tipo,
  GUID, base, estado de creación, procedencia y ajustes consultables.
- Exclusión entre hilos y procesos. Antes de crear busca GUID registrado, planes
  oficiales y copias compatibles. La creación reserva un destino estable y sólo
  lo acepta como real cuando Windows lo confirma en `/list`.
- Un fallo de renombrado o una creación ambigua recupera la misma copia si existe.
  Si la creación falló y no aparece el GUID, se conserva el error y se bloquea la
  repetición automática, incluso tras reiniciar. No borrar el registro como medida
  de limpieza: ante ese error hay que revisar su causa y el estado real de Windows.
- Copias antiguas: nombre exacto y configuración compatible permiten reutilizar;
  eso NO concede permiso para borrarlas. Si no se puede comprobar compatibilidad,
  se informa del problema sin crear otra copia con el mismo nombre.
- Sólo se consolidan copias con procedencia registrada, mismo tipo/base, nombre
  esperado y todos los ajustes AC/DC interpretables iguales, incluidos los ajenos
  al procesador. Una lectura no disponible impide la limpieza.
- Antes de eliminar un duplicado activo se activa y verifica el conservado.
  El plan anterior de una transacción queda protegido para permitir restaurarlo.
  Planes estándar y copias sin procedencia demostrada no se eliminan.
- Los cambios de parámetros actualizan el GUID propio existente. Los perfiles
  manuales siguen siendo persistentes; AUTO legado restaura plan y ajustes previos
  conservando la copia registrada. Los backups antiguos mantienen su rollback.

La sintaxis de destino explícito se verificó en la
[documentación oficial de powercfg](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options#duplicatescheme).

## Validación ejecutada

- `python -m unittest tests.test_managed_power_plans -v`: 22 pruebas correctas.
- `python tests/test_power_manager.py`: 9 comprobaciones correctas.
- Incluye los diez escenarios solicitados, errores de renombrado/listado/borrado,
  registro corrupto, concurrencia, diferencias en ajustes de disco y AUTO repetido.
- Todos los comandos están simulados y el test nuevo bloquea procesos reales.
  No se han activado, creado ni eliminado planes reales para validar este cambio.
- Hashes comparados con el estado inicial de esta tarea: Benchmark, Overlay,
  diagnóstico, UI, archivos protegidos y demás archivos existentes intactos,
  excepto los dos módulos de energía indicados.

## Prueba manual pendiente

1. Reiniciar CorePulse desde esta carpeta.
2. Anotar el listado inicial con `powercfg /list` (sólo lectura).
3. Aplicar un mismo perfil varias veces: GUID y cantidad de planes deben mantenerse.
4. Cerrar, abrir y repetir; comprobar el plan activo con `powercfg /getactivescheme`.
5. Volver al perfil deseado y comprobar que Windows confirma el cambio.

No se promete eliminar copias antiguas que carezcan de evidencia de procedencia.
La interacción con Windows real y la interfaz no se ejecutó en esta validación.
