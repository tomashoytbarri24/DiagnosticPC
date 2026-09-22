## V284 — Benchmark Summary Style + Agent Density

- Tarjetas del benchmark alineadas al lenguaje visual del Resumen.
- Eliminados switches circulares en la selección de componentes.
- Tarjeta del agente con más densidad visual.

## V283 — Dashboard Agent + Benchmark Cleanup

- Tarjeta del agente alineada al estilo del Resumen.
- Benchmark reordenado con botón de regreso tipo flecha.
- Limpieza visual de N/A en módulos de almacenamiento.

## V282 — Performance Optimized

- Redibujo de gráficos sólo con telemetría nueva y Dashboard visible.
- Historial de alertas no consulta almacenamiento si su vista está oculta.
- Estado del agente y tray evitan repintados repetidos sin cambios.
- CPU/GPU/RAM omiten repintados pesados del mismo snapshot.
- Sin cambios de diseño ni de política REAL_OR_NA.

## V281 — Dark Themes + Red

- Sólo temas oscuros.
- Nuevo tema Rojo.

# Versionado vigente


## V279 — Visual Consistency + Benchmark/Updates Cleanup
- Mantiene la base funcional y navegación V278/V277.
- Unifica superficies de temas claros para evitar tarjetas casi blancas aisladas entre módulos.
- Tarjeta del agente adopta la firma visual del Resumen con acento lateral.
- Actualizaciones elimina Rollback de la interfaz y conserva Versiones anteriores/Releases.
- Benchmark no reserva Estado de la prueba antes de iniciar; aparece sólo al comenzar o al mostrar resultados.
- Sin cambios en telemetría, SMART/NVMe, Driver Hub ni motor Benchmark V25.

- CorePulse: **V279**
- Benchmark GPU: **V25**
- Resultado GPU: `resultados/benchmark_gpu_v25_ultimo_resultado.json`
- Política: `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`


## V278 — Tomas Base Functional Recovery
- Base visual y navegación: V277 de Tomás.
- Recupera salud NVMe/Storage Reliability en dos fases con caché persistente.
- Recupera tolerancia de sensores CPU y frecuencia fallback real.
- Recupera 20 temas y contraste seguro sin rediseñar el selector.
- Recupera volumen de prueba de audio.
- Recupera Driver Direct/Driver Hub dentro del módulo existente.
- Recupera publicación Git multi-destino y workflows Development/Stable.
- Mantiene Benchmark V25 y sidebar V277 sin cambios funcionales.
- Windows-only.

## V273 — Sidebar Edge Border + Neutral Dividers
- Base funcional exacta: V272.
- El borde exterior mantiene cuatro trazos Tk nativos de 2 px, pero deja de estar insetado 8 px.
- Los cuatro trazos quedan pegados al perímetro real del sidebar (`x/y = 0` y extremos del CTkFrame), eliminando el efecto de rectángulo interno.
- Se mantienen los separadores internos neutros con el rol estructural `border`.
- Sin cambios en navegación, telemetría, SMART, benchmark ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V272 — Sidebar Strong Border + Neutral Dividers
- Base funcional exacta: V271.
- El borde exterior del sidebar pasa a cuatro trazos Tk independientes de 2 px para que los cuatro lados queden claramente marcados.
- Los separadores dejan el celeste de acento y usan el rol estructural `border`, coherente con tarjetas y gráficos.
- Sin cambios en navegación, telemetría, SMART, benchmark ni contratos REAL_OR_NA / REAL_FPS_OR_NA_ONLY.

## V271 — Sidebar Correct Border + Cyan Dividers
- Base funcional exacta: V269.
- Borde exterior del sidebar usa el borde estructural del dashboard.
- Separadores internos en celeste CorePulse.

## V269 — Sidebar Outer Rectangle Fix
- Borde exterior insetado, continuo y visible en los cuatro lados.

## V268 — Status Card Width Parity
- Base funcional: V267.
- `Supervisión actual` usa el mismo ancho efectivo que `Salud del sistema`.
- Sin cambios de telemetría, alertas, sidebar, gráficos ni REAL_OR_NA.

## V267 — Sidebar Border Visibility
- Base funcional: V266.
- Se refuerza únicamente el borde exterior del rectángulo del sidebar a 2 px.
- Sin cambios en separadores, navegación, telemetría ni lógica.

## V266 — Sidebar Border + Dividers Native Fix
- Borde continuo y separadores visibles con Tk nativo.
- Actualizaciones permanece visible dentro del panel.

## V265 — Sidebar Dividers + Border Fix
- Borde exterior continuo y separadores de secciones ajustados.
- Personalización mantiene Temas y Actualizaciones visibles.

## V264 — Sidebar Dividers + Updates Visibility
- Base funcional: V263.
- Separadores horizontales visibles entre cabecera, Monitoreo, Diagnóstico, Mantenimiento, Historial y Personalización.
- Personalización queda reservada como footer inferior del sidebar.
- Temas y Actualizaciones permanecen visibles en alturas de portátil.
- Sin cambios en telemetría, SMART, benchmark ni REAL_OR_NA.

## V263 — Sidebar Full Panel Parity
- Base funcional: V259.
- El propio sidebar es el panel rectangular: no hay marcos internos ni reparenting de widgets.
- Borde exterior cuadrado integrado con margen respecto a la ventana.
- Separadores sutiles entre Monitoreo, Diagnóstico, Mantenimiento, Historial y Personalización.
- Se preservan navegación, colapso/reapertura y comportamiento existente.

## V259 — Startup Bar Refinement White Branding
- Base funcional: V257.
- La tarjeta de inicio usa esquinas cuadradas (`corner_radius=0`).
- Se elimina el contador visual de porcentaje; sólo se muestra la barra de carga real.

## V257 — Project Cleanup
- Base funcional: V256.
- Sin cambios de telemetría, benchmark, SMART, diagnóstico o UI.
- Se eliminan cachés, archivos históricos de validación, runners de benchmark antiguos y módulos confirmados fuera de la ruta de ejecución actual.
- Se conserva un conjunto mínimo de pruebas de integridad del proyecto limpio.
