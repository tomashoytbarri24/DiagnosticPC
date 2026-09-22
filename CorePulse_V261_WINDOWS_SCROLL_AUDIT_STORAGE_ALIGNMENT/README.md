# CorePulse V261 — Scroll Audit & Storage Alignment

CorePulse V261 parte de **V260** y conserva la integración Windows de V258/V259. Esta revisión corrige dos detalles observados en prueba real: la posición de la salud de las unidades en Resumen y la inconsistencia de velocidad/comportamiento entre los distintos scrolls de la aplicación.

## Cambios de V261

- La insignia **Salud xx%** de cada unidad vuelve al extremo derecho real de su tarjeta. El botón contextual «Ver detalles» comparte ese mismo slot y sólo se superpone durante hover, sin reservar un hueco permanente.
- Scroll unificado mediante `StableScrollHost` en Temas, publicación Git, historial de benchmark y las páginas largas de Centro de salud, CPU, GPU, RAM, Red, Tweaks, Gaming, alertas y telemetría.
- Velocidad estándar de rueda elevada a **96 px por paso**; se eliminan los casos de 54/58 px que hacían algunas vistas sensiblemente más lentas.
- Las páginas densas usan el backend `place`, que desplaza un único contenedor y evita repintados GDI agresivos en cada paso.
- Los resultados de Benchmark conservan el backend Canvas probado en V259 para mantener el drag de la barra derecha, pero ahora usan la misma velocidad de 96 px.
- Se eliminan los `CTkScrollableFrame` restantes para que la barra derecha, la rueda y el comportamiento de drag sean consistentes en toda la aplicación.
- Benchmark V25, Driver Hub, salud NVMe, telemetría, temas, audio y publicación segura conservan su lógica funcional.

## Política de datos

CorePulse mantiene **REAL_OR_NA**: no inventa salud, sensores, drivers disponibles ni resultados de benchmark.
