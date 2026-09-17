# V162 — Equilibrado, Audio integrado y respuesta de la interfaz

## Equilibrado

El listado real de Windows no contiene el GUID estándar de Equilibrado. El log
del 16/09/2026 a las 20:25:07 muestra que `/duplicatescheme` devolvió código 1:
«El plan, subgrupo o configuración de energía especificado no existe».
El registro guardó ese fallo y los intentos siguientes repetían el error guardado.

Ahora, si falta Equilibrado y no hay copia reutilizable, se recupera únicamente ese
esquema mediante PowerRestoreIndividualDefaultPowerScheme, después de consultar
PowerCanRestoreIndividualDefaultPowerScheme. Se comprueba su presencia antes y
después. No se usa restoredefaultschemes, no se borran otros planes, no se toma un
plan personalizado como supuesto Equilibrado. Si ya existe, no se restablece.
La recuperación sucede al solicitar Equilibrado en la aplicación, no durante tests.

La consulta de disponibilidad en este entorno restringido devolvió código 5
(Acceso denegado). No se ejecutó recuperación real. Si la aplicación muestra ese
error, usar su opción existente de abrir como administrador y repetir. Si Windows
no tiene la plantilla recuperable, se mostrará el error real: no se inventa un plan.
API: https://learn.microsoft.com/en-us/windows/win32/api/powrprof/nf-powrprof-powerrestoreindividualdefaultpowerscheme

## Audio

Centro de salud → Test de Audio abre un módulo CTkFrame en la misma página.
Usa el scroll del Centro de salud, sin Toplevel ni scroll anidado. El acceso desde
Diagnóstico apunta al mismo módulo. Salir del área cancela la operación y descarta
la grabación. Los resultados técnicos y confirmaciones mantienen su lógica anterior.
Un trabajo de otra sección no reconstruye Audio ni interrumpe su prueba.

## Cambios de respuesta

- `PerformanceProfileManager.status()` no espera el candado ocupado por powercfg:
  devuelve una copia del último estado confirmado hasta que termine el worker.
- `snapshot_scheme()` obtiene los tres ajustes CPU/Boost/EPP con una sola consulta
  de subgrupo; sólo añade /query si faltan valores. Antes ejecutaba /qh tres veces.
- Trabajos asíncronos de una sección abandonada no reconstruyen la vista nueva.

Estas son reducciones verificables de bloqueo, consultas y reconstrucción. No se
ha medido una mejora porcentual global ni se garantiza eliminar todo el parpadeo.

## Archivos y pruebas

Modificados: performance/power_manager.py, performance/managed_power_plans.py,
performance/profile_manager.py, gui/audio_test_panel.py, gui/health_center_panel.py
y tests/test_audio_test.py. Nuevo test: tests/test_v162_balanced_audio_responsiveness.py.

72 pruebas ejecutadas: 71 correctas, 1 GUI omitida por init.tcl no disponible.
Comando: `python -m unittest tests.test_v162_balanced_audio_responsiveness tests.test_managed_power_plans tests.test_power_reconciliation tests.test_audio_test -q`.
Incluye recuperación individual simulada, error de permisos, GUID ausente tras API
exitosa, ausencia de borrados/duplicaciones, diez reutilizaciones, consulta única
para tres ajustes y lectura de estado sin esperar un worker que mantiene el candado.

No se reprodujo audio, no se grabó el micrófono ni se modificaron planes reales.
Archivos protegidos y motores de benchmark/diagnóstico/overlay conservados por hash.

## Prueba manual

1. Cerrar y abrir la V162 desde esta carpeta para cargar los cambios.
2. Solicitar Equilibrado; si Windows pide permisos, abrir CorePulse como administrador.
3. Comprobar en Opciones de energía que los demás planes siguen presentes.
4. Abrir Centro de salud → Test de Audio: debe permanecer dentro de la ventana principal.
5. Probar grabar/detener y salir del módulo; la captura debe detenerse.
6. Alternar módulos mientras se aplica un perfil y comprobar la respuesta visual.
