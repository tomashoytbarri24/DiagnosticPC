# Reconciliación de energía — V162 actual, sin cambio de versión

## Hallazgos

Sólo existe una ruta de duplicación de planes en esta V162: ManagedPowerPlans.
La corrección anterior ya guardaba el GUID antes de duplicar y evitaba que un
fallo de renombrado generara otra copia. No hay logs suficientes para atribuir
todos los duplicados históricos del equipo a una causa exacta.

Quedaban dos carencias verificadas: no se reconocían los nombres CorePulse Game
y CorePulse Turbo Performance, y la reconciliación sólo conocía GUID registrados,
sin descubrir identidad persistida en Windows. Además, el monitor de juegos
consultaba el plan activo cada dos segundos.

## Cambios limitados a energía

- performance/power_manager.py: identidades/aliases y API explícita de perfiles
  propios y reconciliación.
- performance/managed_power_plans.py: descubrimiento de identidad, preferencia de
  GUID, reutilización, comparación conservadora y reconciliación.
- performance/profile_manager.py: Alto rendimiento asegura CorePulse Game;
  Máximo rendimiento asegura CorePulse Turbo Performance. AUTO/GAMING legado
  mantiene su correspondencia anterior con Máximo rendimiento. No cambia la UI.
  Sondeo de cambios externos limitado a una vez cada 30 s; la reconciliación no
  se ejecuta durante ese sondeo ni durante navegación/telemetría.
- tests/test_managed_power_plans.py: expectativa del nombre canónico e inyección
  de metadatos ficticios para no consultar Windows real.
- tests/test_power_reconciliation.py: nuevos escenarios Game/Turbo.

Game y Turbo tienen identidades y GUID estables distintos. Un GUID previamente
registrado se prefiere; los nombres de versiones anteriores se reutilizan sin
renombrarlos. Una copia existente compatible y no registrada puede reutilizarse,
pero no se declara propiedad de CorePulse sólo por su nombre.

Las nuevas copias guardan en la descripción de Windows un marcador exacto de
CorePulse con tipo/base. Se consulta mediante la API pública
[PowerReadDescription](https://learn.microsoft.com/en-us/windows/win32/api/powrprof/nf-powrprof-powerreaddescription).
No se hardcodean GUID del equipo del usuario. La descripción no es una firma
criptográfica: una copia que conserve ese marcador y todos sus ajustes se trata
como duplicado administrado sólo si también conserva un nombre exacto admitido.

## Duplicados históricos y seguridad

Se consolidan copias de la misma identidad respaldadas por el registro existente
o por el marcador exacto, y con configuración AC/DC equivalente consultada con
/qh. El GUID canónico guardado tiene prioridad. Game nunca se mezcla con Turbo.
Un fallo de lectura, ajustes diferentes o nombre/identidad ambiguos evita borrar.
Los nombres parciales, OEM y GUID estándar no se consideran propios.

El duplicado activo sólo se elimina después de activar y verificar el canónico.
El plan anterior respaldado por una transacción se conserva para restauración;
por ello puede quedar una copia pendiente de consolidación en esa activación.
Los planes propios permanecen instalados al terminar sesiones temporales.

Las copias antiguas sin registro ni marcador NO pueden eliminarse de manera
inequívoca automáticamente. Pueden quedar dos copias con igual nombre: esto es
intencional cuando la alternativa sería borrar configuraciones del usuario sin
prueba suficiente. No se promete reducir esas copias a una por el nombre solo.

## Pruebas

35 pruebas correctas: 22 de gestión existentes y 13 de reconciliación nueva.
Incluyen diez activaciones, reutilización tras reiniciar, tres duplicados con
identidad verificable, conservación OEM/usuario, activo y verificación antes de
borrar, perfiles ambiguos, parámetros distintos, GUID preferido, Game/Turbo
coexistentes y ausencia de consultas repetidas en diez sondeos de juegos.
Todos los comandos y descripciones de Windows están simulados.
No se han modificado planes reales ni se ha validado visualmente Opciones de energía.
Audio y los archivos excluidos se verifican mediante hashes, sin ejecutarlos.

## Cómo probar

1. Reiniciar CorePulse desde la carpeta V162 actual y anotar `powercfg /list`.
2. Aplicar Alto rendimiento y Máximo rendimiento: las nuevas copias serán
   CorePulse Game y CorePulse Turbo Performance, respectivamente. Un alias antiguo
   reutilizable puede conservar su nombre anterior.
3. Alternar perfiles y activar/desactivar sesiones Gaming varias veces.
4. Reabrir Opciones de energía: no deben generarse nuevas copias por activación.
5. Reiniciar CorePulse y repetir. Los dos perfiles distintos deben conservarse.

Si persisten duplicados históricos no identificables, no borrarlos en bloque:
requieren revisión manual de procedencia/configuración.
