# Validación CorePulse V161

Base: CorePulse_V160.zip. Cambio limitado a Diagnóstico Completo + benchmark.

## Qué cambia

Flujo real: estado en escritorio → hardware/batería/almacenamiento (una fase existente) → Windows → benchmark CPU/RAM/SSD/GPU → análisis de telemetría recogida durante benchmark → correlación → resultado.

Se retiran las llamadas automáticas a estrés CPU/RAM/GPU y los 3 segundos de cooldown posterior. No se añaden esperas. Se eliminan aproximadamente 26 segundos nominales de estrés más 3 de cooldown respecto del flujo V160; no es una medición de duración total en hardware real. El orden interno CPU/RAM/SSD/GPU y las duraciones del benchmark estándar se conservan para mantener su metodología.

El motor de estrés sigue presente para uso interno. Los cuerpos de las funciones de carga de CPU, RAM, SSD, GPU OpenGL y del motor de estrés son idénticos a V160 (comparación AST). Windows Health, resize y los cinco archivos protegidos permanecen intactos.

## Evidencia y seguridad

- Cada resultado de benchmark conserva sus métricas y añade `telemetry`: muestras observadas, máximos/promedios, frecuencias, detector de throttling, errores de muestreo/ejecución e identidad disponible.
- La GPU se enlaza por renderer exacto normalizado; no se atribuyen los sensores o throttling de otro adaptador. Sin identidad verificable: N/A.
- La temperatura SSD se vincula al volumen probado mediante identidad inequívoca. El inventario inicial sólo aporta montaje/identidad: no rellena temperaturas actuales desde la caché. Healthy nunca se transforma en porcentaje.
- CPU 96 °C y GPU 92 °C conservan los límites existentes. Se interrumpe la carga, se omiten las posteriores y se conserva evidencia; no se registra como benchmark completado. Un componente omitido no se declara averiado.
- Throttling detectado requiere la evidencia explícita del detector existente; sospecha y margen térmico reducido quedan diferenciados. Ausencia de sensores no implica ausencia de throttling.
- No hay hilos nuevos de observación: el muestreo cooperativo usa el progreso y stop_check existentes. Se mantiene el token por sesión, cancelación, espera a la salida de workers anteriores y protección contra callbacks tardíos.
- El historial sólo recibe benchmarks completos, una vez. Una cancelación impide guardar diagnóstico final o generar su PDF. Una parada térmica puede producir un diagnóstico parcial con evidencia, nunca un benchmark exitoso.
- Pantalla y PDF consumen las mismas funciones de evidencia. Sus tablas no recortan filas de temperatura, frecuencia, throttling o errores. Cobertura: 6 fases reales; hardware agrupa batería y almacenamiento. No hay fases automáticas de estrés ni cooldown.

## Pruebas ejecutadas

Comando: `python -m unittest tests.test_v161_benchmark_diagnostic tests.test_v157_diagnostic_lifecycle -v`

**36 pruebas: 35 aprobadas, 1 omitida, 0 fallos.** Las 17 nuevas pruebas V161 cubren flujo sin estrés, benchmark, telemetría separada, cancelación en cada componente y reinicio, errores, N/A, seguridad CPU/GPU, identidad GPU/SSD, prioridad, guardado único, rechazo de PDF cancelado, evidencia común, fases UI y hashes. Se conservan 18 regresiones aprobadas de ciclo de vida V157; su escenario térmico se adapta al benchmark en vez del estrés eliminado.

Además:
- Cargas reales cortas de CPU SHA-256, copia RAM y lectura/escritura SSD: aprobadas, con rendimiento positivo, telemetría psutil de uso/frecuencia, limpieza del archivo temporal y sin workers CPU restantes. Perfil reducido sólo en el proceso de prueba; los perfiles entregados no cambian.
- PDF completo generado con datos instrumentados: 6 páginas renderizadas e inspeccionadas. Texto sin una prueba de estrés inexistente; todas las filas de evidencia del nuevo modelo presentes.
- Sintaxis de todos los archivos Python y contenido/CRC del ZIP comprobados.
- SHA-256 de los cinco protegidos idénticos al ZIP V160; ver PROTEGIDOS_V160_SHA256.json.

## Qué no se pudo validar

La prueba real Tk/CustomTkinter se omitió porque el intérprete disponible no encuentra un init.tcl utilizable. No se ejecutó la GUI completa ni el benchmark OpenGL real; GPU, temperaturas y protección térmica se verificaron con proveedores instrumentados, sin calentar intencionadamente el PC hasta sus límites. Tampoco se repitió un diagnóstico físico completo de Windows/batería/SMART ni una medición de duración total V160/V161.

El PDF usa datos de prueba, no es un diagnóstico de tu equipo. Una ejecución preliminar emitió un error de finalización de Python.NET al cerrar el proceso; la repetición final generó el PDF y terminó correctamente. No se modifica el runtime protegido para abordar ese comportamiento del entorno.

No se ejecutó ni se declara aprobada la suite histórica completa: contiene contratos de versiones anteriores (incluido el modelo de estrés V160) fuera de este cambio. El log adjunto corresponde únicamente a las pruebas indicadas.

## Cómo probar V161

1. Abre Iniciar_CorePulse.bat desde la carpeta completa v161 y comprueba la versión.
2. Inicia Diagnóstico Completo: debe ir de escritorio/hardware/Windows al benchmark, sin estrés ni cooldown de estrés.
3. Cancela durante benchmark y vuelve a iniciar inmediatamente; la ejecución anterior no debe habilitar PDF ni añadir historial válido.
4. Deja terminar la siguiente ejecución y comprueba una sola entrada de benchmark completo en el historial (si todos sus componentes se midieron).
5. Abre Ver evidencia de CPU/GPU/RAM/Almacenamiento: revisa escritorio, métricas de benchmark, telemetría e identidades; N/A es correcto si falta un sensor.
6. Genera el PDF final y compara sus valores con pantalla; revisa cobertura y prioridad. No fuerces sobretemperatura para probar la protección.
