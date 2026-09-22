# CorePulse V205 — Safe Boat Route + Continued Visual Polish

V205 continúa la rama Windows desde V204. El benchmark GPU pasa a **V25** para corregir un problema real reportado: el **barco se metía en la isla**.

Cambios principales:
- **Ruta del barco corregida** para que permanezca en agua abierta.
- **Estela del barco** reforzada y sincronizada con la nueva ruta.
- Más pulido visual ligero en **agua / espuma / niebla**.
- Se mantiene **1 avión protagonista**, la política **REAL_OR_NA** y los **49 s medidos**.

Validación: `VALIDACION_V205_WINDOWS_SAFE_BOAT_ROUTE_VISUAL_POLISH.md`.

# CorePulse V204 — Visual Scene Polish

V204 continúa la rama Windows desde V203. El benchmark GPU pasa a **V24** para corregir el feedback visual del escenario:

- **Barco** más claro, más cercano y con ruta mejor definida.
- **Humo** con pluma propia más legible y movimiento en tiempo real.
- **Fogata** más visible.
- **Mar** con más profundidad, espuma y estela del barco.
- **Árboles** y **piedras** con materiales más trabajados.
- Se conserva **1 avión protagonista**, la política **REAL_OR_NA** y los **49 s medidos**.

Validación: `VALIDACION_V204_WINDOWS_VISUAL_SCENE_POLISH.md`.

# CorePulse V203 — Boat / Fire / Smoke Visibility

V203 continúa la rama Windows desde V202. El benchmark GPU pasa a **V23** porque se corrige materialmente la legibilidad visual de la escena:

- El **barco** se rediseña y recorre una ruta central más visible.
- La **fogata** ahora sí aparece como elemento propio en Extreme.
- El **humo** gana desplazamiento visible en tiempo real mediante varias instancias animadas.
- Se conserva 1 avión protagonista y el resto del benchmark permanece con la política **REAL_OR_NA**.
- Se mantienen los **49 s medidos** en las cuatro escenas estándar.

Validación: `VALIDACION_V203_WINDOWS_BOAT_FIRE_SMOKE_VISIBILITY.md`.

# CorePulse V202 — Visibility + HUD + Result Simplification

V202 continúa la rama Windows desde V201 y corrige lo observado en la grabación real:

- Corrige el HUD de **Extreme**: `Valle completo / Extreme` ya no se confunde con `VALLE · ESCENA 1/4`.
- Reubica y eleva el **barco** en el canal central para que sea realmente visible y no quede sumergido/fuera de cámara.
- Reubica la **fogata con humo** a la isla sur de la trayectoria de Extreme y conserva el volumen de los puffs para que el humo se lea en pantalla.
- Mantiene **un solo avión**.
- Simplifica **Resumen rápido**: conclusión + lectura rápida; elimina una segunda cuadrícula que repetía los mismos valores.
- El detalle completo sigue disponible en `GPU 3D`, `Sistema` y `Evidencia`.
- Se mantiene `REAL_OR_NA`, wall-clock, timestamps GPU y los 49 s medidos del perfil estándar.

Validación: `VALIDACION_V202_WINDOWS_VISIBILITY_HUD_RESULT_SIMPLIFICATION.md`.

# CorePulse V201 — Scene Rebalance + Result Usability

V201 continúa la rama Windows desde V200. El benchmark GPU pasa a **V21** porque cambia materialmente la escena visible y la lectura inicial del resultado:

- Se reduce la formación aérea a **1 avión protagonista**, mejor encuadrado y más fácil de leer.
- Se agrega **1 barco navegando** como elemento de movimiento secundario.
- En **Extreme** aparece una **fogata con humo** sobre una isla para enriquecer la escena máxima sin saturarla.
- La vista **Resumen rápido** reorganiza los resultados para entregar primero una lectura compacta y luego el detalle por componente.
- Se conserva la política **REAL_OR_NA**, el reloj de pared determinista, los timestamps GPU y los 49 s medidos.

Validación: `VALIDACION_V201_WINDOWS_SCENE_REBALANCE_RESULT_USABILITY.md`.

# CorePulse V200 — Result Clarity + Aircraft Framing

V200 continúa la rama Windows desde V199. El benchmark GPU pasa a **V20** porque cambia el encuadre espacial de los jets: la formación se acerca al corredor de cámara y aumenta ligeramente su tamaño aparente, manteniendo la misma geometría, cantidad de instancias y draw calls.

La interfaz de resultados corrige el recorte de contenido: `Resumen`, `GPU 3D`, `Sistema` y `Evidencia` conservan la navegación fija y cada vista usa un viewport desplazable independiente. Si una explicación o evidencia no cabe en 1280×800, sigue siendo accesible mediante scroll; no se trunca ni se pierde.

- Persistencia GPU vigente: `resultados/benchmark_gpu_v20_ultimo_resultado.json`.
- Tiempos medidos estándar: **10 + 12 + 12 + 15 = 49 s**.
- `REAL_OR_NA`, `REAL_FPS_OR_NA_ONLY`, wall-clock, GPU timestamps y `SAFETY_STOP` permanecen.
- La Conclusión CorePulse de V199 se conserva como capa principal de conocimiento.

Validación: `VALIDACION_V200_WINDOWS_RESULT_CLARITY_AIRCRAFT_FRAMING.md`.

---

# CorePulse V199 — Knowledge Clarity

V199 continúa la rama Windows desde V198. Mantiene Benchmark GPU V19 sin cambios y concentra la interpretación final en una Conclusión CorePulse breve, entendible y trazable.

# CorePulse V198 — Windows Mainline · Benchmark GPU V19 · Knowledge Layer

Versión actual: **V198 Windows — Benchmark GPU V19**.

V198 parte directamente de V197 y **no modifica el workload GPU V19**. Su objetivo es convertir mediciones reales en conocimiento comprensible sin inventar rankings:
- Cada GPU/CPU/RAM/SSD muestra una **Lectura CorePulse** visible: qué funcionó, qué merece atención y qué evidencia respalda la conclusión.
- CPU usa el estado real de la prueba, calidad de las muestras, integridad y temperatura observada; una medición `VARIABLE` o ≥95 °C se comunica como atención, no como “fallo” inventado.
- RAM sólo se presenta como correcta cuando la verificación byte a byte fue real y satisfactoria.
- SSD separa explícitamente rendimiento de E/S de salud/desgaste: SMART sigue siendo la fuente para salud física.
- GPU explica finalización de escenas, FPS/1% Low y temperatura; además muestra qué porcentaje representa el 1% Low respecto del promedio para enseñar consistencia sin imponer un ranking externo.
- Evidencia térmica explica por qué hubo o no `SAFETY_STOP`, incluyendo muestras sobre umbral, margen real a TjMax y racha observada, sin interpolar sensores.
- Resumen/Sistema mantienen una versión compacta de la explicación para seguir siendo utilizables en 1280×800; GPU/Evidencia ofrecen la explicación completa.
- `core/directx_scene.py`, `core/directx_benchmark.py` y `core/benchmark_engine.py` permanecen byte-identical a V197.
- Persistencia vigente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.
- `REAL_OR_NA`, wall-clock, **49 s medidos**, FPS/1% Low, timestamps GPU y seguridad térmica permanecen intactos.

Validación específica: `VALIDACION_V198_WINDOWS_BENCHMARK_V19_KNOWLEDGE_LAYER.md`.

---

# CorePulse V197 — Windows Mainline · Benchmark GPU V19 · UX Closure

Versión actual: **V197 Windows — Benchmark GPU V19**.

V197 parte directamente de V196 Windows y **no modifica el workload GPU V19**. Cambios:
- Historial reduce la primera pintura a 3 tarjetas y sólo precarga 5 sesiones; el resto se carga en segundo plano.
- Terminología técnica más legible: `Frame presentado`, `Variación`, `Frames lentos`, `Compresión zlib` y `Variación (CV)`.
- Resumen térmico ofrece acceso directo a `Evidencia` cuando hay temperatura alta o safety stop.
- Evidencia térmica muestra `Muestras sobre X °C` para evitar ambigüedad.
- `core/directx_scene.py`, `core/directx_benchmark.py` y `core/benchmark_engine.py` permanecen byte-identical a V196.
- Persistencia vigente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.
- `REAL_OR_NA`, wall-clock, **49 s medidos**, FPS/1% Low, timestamps GPU y seguridad térmica permanecen intactos.

Validación específica: `VALIDACION_V197_WINDOWS_BENCHMARK_V19_UX_CLOSURE.md`.

---

# CorePulse V196 — Windows Mainline · Benchmark GPU V19 · Visual/UX Finish

Versión actual: **V196 Windows — Benchmark GPU V19**.

V196 vuelve a la rama principal Windows tomando V195 como base estable. Cambios:
- Benchmark GPU pasa a **V19** porque cambia materialmente el workload visual.
- Jets con formación 3D determinista, ligera variación de pitch/roll/yaw y toberas visibles sin draw calls extra.
- Agua/costa menos repetitiva mediante swell amplio y ruptura procedural de espuma.
- Vegetación mantiene 328 triángulos por árbol, pero varía morfología y color por instancia sin datos aleatorios.
- Historial pinta primero 20 sesiones y precarga el resto en segundo plano; las tarjetas muestran GPU/CPU/RAM/SSD como bloques legibles en vez de una línea densa.
- Evidencia muestra nombre de archivo y acciones `Abrir carpeta` / `Copiar ruta` sin exponer la ruta completa como contenido principal.
- Persistencia vigente: `resultados/benchmark_gpu_v19_ultimo_resultado.json`.
- `REAL_OR_NA`, wall-clock, **49 s medidos**, FPS/1% Low, timestamps GPU y seguridad térmica permanecen vigentes.

Validación específica: `VALIDACION_V196_WINDOWS_BENCHMARK_V19_VISUAL_UX_FINISH.md`.

---

# CorePulse V195 — Benchmark GPU V18 · Professional Finish

Versión actual: **V195 — Benchmark GPU V18**.

V195 parte de V194 y cierra problemas detectados en la grabación real de Windows:
- Las vistas `Resumen / GPU 3D / Sistema / Evidencia` se construyen una vez y luego se alternan sin destruir widgets, evitando el ghosting grave visto al cambiar de pestaña.
- Historial lee las sesiones persistidas fuera del hilo Tk y mantiene un estado de carga visible; sólo construye 5 tarjetas iniciales.
- Identidad de benchmark centralizada: HUD, ventana DirectX, método, provider y JSON comparten siempre la misma versión.
- Benchmark GPU pasa a **V18** porque cambia la formación visual de jets y su tratamiento atmosférico.
- Jets usan formación en V determinista y mayor separación/contraste para conservar silueta a distancia.
- Resumen comunica `Benchmark completado · temperatura alta` en ámbar cuando hay temperatura elevada sin gatillo sostenido.
- Persistencia vigente: `resultados/benchmark_gpu_v18_ultimo_resultado.json`.
- `REAL_OR_NA`, wall-clock, 49 s medidos, FPS/1% Low, timestamps GPU y seguridad térmica permanecen vigentes.

Validación específica: `VALIDACION_V195_BENCHMARK_V18_PROFESSIONAL_FINISH.md`.

---

# CorePulse V193 — Benchmark GPU V16 · Clarity Finish

Versión actual: **V193 — Benchmark GPU V16**.

V193 parte de V192 y pule la experiencia sin modificar el workload medido:
- Resultados estáticos construidos antes del swap para eliminar el hueco visual entre 100 % y dashboard.
- GPU 3D muestra primero FPS + 1% Low; frametimes, CV y spikes quedan en `Ver detalles técnicos`.
- Sistema prioriza SHA-256, RAM Copia y SSD Lectura/Escritura; IOPS/CV/auxiliares quedan bajo demanda.
- Evidencia resume método/timestamps/REAL_OR_NA y deja la metodología extensa bajo `Ver metodología`.
- Bordes del módulo Benchmark reforzados de forma consistente con la identidad CorePulse.
- Historial conserva su tarjeta de carga hasta que el panel ya construido está publicado, evitando el frame vacío intermedio.
- DirectX V16, escenas, HLSL, 49 s, wall-clock, FPS/1% Low, timestamps GPU, `REAL_OR_NA` y seguridad térmica permanecen byte-identical a V192.

Validación específica: `VALIDACION_V193_BENCHMARK_V16_CLARITY_FINISH.md`.

---

# CorePulse V192 — Benchmark GPU V16 · Static Results

Versión actual: **V192 — Benchmark GPU V16**.

V192 parte de V191 y corrige dos problemas observados en Windows sin modificar el workload medido:
- Resultados finales fuera del viewport desplazable: Resumen/GPU 3D/Sistema/Evidencia se publican en una superficie estática.
- Resumen reducido a las cuatro métricas principales + estado térmico; las escenas GPU quedan sólo en `GPU 3D`.
- Historial se construye fuera de vista y se publica completo para evitar controles a medio montar.
- Filtros del Historial pasan a una segunda fila estable.
- Historial muestra 5 sesiones inicialmente y 5 más bajo demanda.
- DirectX V16, escenas, HLSL, 49 s, wall-clock, FPS/1% Low, timestamps GPU, `REAL_OR_NA` y seguridad térmica sin cambios.

Validación específica: `VALIDACION_V192_BENCHMARK_V16_STATIC_RESULTS.md`.

---

# CorePulse V191 — Benchmark GPU V16 · UX Refinement

Versión actual: **V191 — Benchmark GPU V16**.

V191 parte de V190 y se concentra en **usabilidad, densidad visual y respuesta del Historial**, manteniendo intacto el workload medido V16.

Cambios V191:
- Configuración compactada para reducir scroll y evitar el ghosting transitorio observado en RAM/SSD.
- Historial progresivo: 12 ejecuciones recientes al abrir + 12 más bajo demanda.
- Evidencia térmica separada en tarjetas CPU/GPU y protección térmica expresada de forma directa.
- Campo de ruta JSON integrado a la paleta azul/cian de CorePulse.
- DirectX V16, escenas, shaders, 49 s, FPS/1% Low, timestamps GPU, `REAL_OR_NA` y seguridad térmica sin cambios.
- El escenario 3D aún tiene margen visual; cualquier cambio material se reservará para Benchmark GPU V17.

Validación específica: `VALIDACION_V191_BENCHMARK_V16_UX_REFINEMENT.md`.

---

# CorePulse V190 — Benchmark GPU V16 · CorePulse Finish

Versión actual: **V190 — Benchmark GPU V16**.

V190 parte directamente de V189 y concentra el trabajo en **acabado profesional, jerarquía visual y personalidad CorePulse**, sin cambiar el workload medido del Benchmark GPU V16.

Cambios V190:
- Escala tipográfica ordenada para Benchmark: métrica / escena / título / sección / cuerpo / metadato / microtexto.
- HUD más legible y coherente con CorePulse, con cian como acento y valores reales en blanco.
- Cursor de la ventana DirectX controlado por la propia `WndProc` mediante `WM_SETCURSOR`; el manejo ocurre fuera de la región cronometrada.
- Dashboard con tarjetas más limpias, remates de color discretos, pills de estado, radios/bordes consistentes y navegación más clara.
- Pestaña superior `Prueba actual` evita confundir navegación con la acción de ejecutar.
- Evidencia, ruta JSON y controles secundarios adoptan el mismo estilo azul/cian.
- Una lectura térmica instantánea alta se muestra en ámbar mientras se confirma persistencia; el rojo queda para alertas sostenidas o un gatillo real.
- Benchmark V16 conserva escenas, HLSL, tiempos, wall-clock, FPS/1% Low, timestamps GPU, `REAL_OR_NA` y seguridad térmica.

Validación específica: `VALIDACION_V190_BENCHMARK_V16_COREPULSE_FINISH.md`.

---

# CorePulse V189 — Benchmark GPU V16 · Professional Integration

Versión actual: **V189 — Benchmark GPU V16**.

V189 parte directamente de V188 y **no modifica el workload GPU V16**. El objetivo es integrar visualmente Benchmark con CorePulse y cerrar problemas de presentación detectados en la grabación de V188.

Cambios V189:
- HUD externo rediseñado con identidad CorePulse azul/cian, jerarquía `CorePulse / Benchmark GPU V16`, nombre de escena y FPS real.
- Warm-up/settle continúan mostrando `N/A`; no se inventan FPS.
- Supresión reforzada del cursor sobre la ventana DirectX mediante el HWND/clase de `CorePulse Benchmark V16 — DirectX 11`, con restauración al finalizar.
- Benchmark usa la misma familia azul/cian del resto de CorePulse en cabecera, pestañas, CTA, progreso y navegación de resultados.
- La configuración cambia a `Resultado de esta ejecución` al finalizar y prioriza Resumen → GPU 3D → Sistema → Evidencia.
- Primera apertura: el panel dedicado evita sondeos de batería irrelevantes y publica una barra de preparación indeterminada antes de construir la vista pesada.
- `core/directx_benchmark.py`, `core/directx_scene.py` y `core/benchmark_engine.py` permanecen byte por byte idénticos a V188.

Validación específica: `VALIDACION_V189_BENCHMARK_V16_PRO_INTEGRATION.md`.

---

# CorePulse V188 — Benchmark GPU V16 UX/HUD Fix

# CorePulse V187 — Benchmark GPU V16 · UX Dashboard

Versión actual: **V187 — Benchmark GPU V16**.

V187 parte directamente de V186 y **no modifica el workload GPU V16**. El objetivo es que Benchmark responda desde el primer clic y que, al terminar, una persona pueda entender el resultado sin leer una pared de telemetría.

Cambios V187:
- Primera entrada progresiva: muestra inmediatamente un shell `Preparando Benchmark` y construye el panel pesado en el siguiente frame.
- `Historial` pasa a ser **lazy**: no se importa ni construye hasta que el usuario lo abre.
- Resultado con divulgación progresiva en cuatro vistas: **Resumen / GPU / CPU · RAM · SSD / Evidencia**.
- `Resumen` es la vista por defecto y prioriza sólo métricas de vistazo, estado térmico y componentes realmente ejecutados.
- Al completar una prueba se colapsa la configuración y el viewport vuelve al resumen; `Cambiar componentes` la restaura.
- JSON, compatibilidad de sensores, metodología y auditoría térmica detallada dejan de competir con el resumen y pasan a `Evidencia`.
- Se reduce drásticamente la necesidad de scroll largo, que en el video V186 todavía exponía artefactos de repintado.
- Los archivos `core/directx_benchmark.py`, `core/directx_scene.py` y `core/benchmark_engine.py` siguen byte por byte idénticos a V186.

Validación específica: `VALIDACION_V187_BENCHMARK_V16_UX_DASHBOARD.md`.

---

## Historial V186

# CorePulse V186 — Benchmark GPU V16 · Scroll Backend Fix

Versión actual: **V186 — Benchmark GPU V16**.

V186 parte directamente de V185 y **no modifica el workload GPU V16**. Conserva escenas, shaders, agua, vegetación, aviones, 49 s medidos, wall-clock, FPS/1% Low, timestamps GPU, `REAL_OR_NA`, persistencia JSON y seguridad térmica.

Cambios V186:
- La página independiente de Benchmark usa un backend de scroll por **viewport + `place`**, sin `Canvas.create_window` para el árbol CTk denso.
- El contenido completo se mueve como un solo frame recortado por el viewport, evitando el desfase de pintura que producía copias fantasma al hacer scroll en Windows.
- El resto de pantallas conserva el backend Canvas existente para limitar el alcance del cambio.
- La restauración de posición usa primero la API de `StableScrollHost`; el `canvas.yview_moveto` queda sólo como fallback legado.
- Los archivos `core/directx_benchmark.py`, `core/directx_scene.py` y `core/benchmark_engine.py` son byte a byte idénticos a V185.

Validación específica: `VALIDACION_V186_BENCHMARK_V16_SCROLL_BACKEND_FIX.md`.

---

## Historial V185

# CorePulse V185 — Benchmark GPU V16 · UI Ghost Fix

Versión actual: **V185 — Benchmark GPU V16**.

V185 parte directamente de V184 y **no modifica el workload GPU V16**. Conserva escenas, shaders, agua, vegetación, aviones, 49 s medidos, wall-clock, FPS/1% Low, timestamps GPU, `REAL_OR_NA` y seguridad térmica. El único cambio funcional es el repaint del scroll en Windows para eliminar restos/duplicados transitorios del frame anterior.

Cambios V185:
- La rueda del mouse en Windows solicita repaint fuerte (invalidate + erase + children) con throttle por frame.
- Si ya existe un repaint pendiente, conserva la petición fuerte en vez de degradarla a repaint suave.
- No hay `update()` reentrante ni reconstrucción extra de la vista.
- Benchmark GPU sigue siendo **V16** y conserva `resultados/benchmark_gpu_v16_ultimo_resultado.json`.

Validación específica: `VALIDACION_V185_BENCHMARK_V16_UI_GHOST_FIX.md`.

---

## Historial V184

# CorePulse V184 — Benchmark GPU V16 · Visual Cleanup

Versión actual: **V184 — Benchmark GPU V16**.

V184 parte directamente de V183. Conserva `REAL_OR_NA`, wall-clock, FPS/1% Low, timestamps GPU y seguridad térmica. Como cambia el recorte/orientación del follaje, el workload GPU pasa correctamente de V15 a **V16** y usa un archivo independiente: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.

Cambios V184:
- metadata runtime GPU unificada a V16 (`method`, `mode`, `policy`, provider, perfil y presentación);
- agua de V183 preservada exactamente;
- follaje con **las mismas 3 tarjetas por cluster y 328 triángulos por árbol**, pero tarjetas más estrechas/asimétricas y recorte interior determinista con una sola muestra de textura para reducir el efecto de “pared verde”;
- evidencia térmica rotulada explícitamente como **fase GPU DirectX**, diferenciándola de la temperatura máxima global del suite;
- publicación de resultados con settle corto + idle de `StableScroll`, sin `update()` reentrante ni repaints tardíos que puedan competir con el primer scroll.

El perfil estándar mantiene exactamente 5 s de warm-up global y **49 s medidos**: Valle 10 s, Bosque 12 s, Lago 12 s y Extreme 15 s.

Validación específica: `VALIDACION_V184_BENCHMARK_V16_VISUAL_CLEANUP.md`.
