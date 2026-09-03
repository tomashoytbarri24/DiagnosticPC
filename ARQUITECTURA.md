# Arquitectura técnica de CorePulse

## Objetivo

CorePulse está diseñado como una aplicación universal de diagnóstico y optimización para hardware Windows. La universalidad se implementa por **detección de capacidades e identidad en tiempo de ejecución**. Ningún modelo concreto del equipo de desarrollo debe determinar reglas de telemetría, diagnóstico, vigencia o recomendaciones.

## Flujo principal

```text
Fuentes reales de Windows / sensores / PresentMon
                    ↓
            Inventario e identidad
                    ↓
             Telemetría REAL_OR_NA
                    ↓
           Muestreo temporal de sesión
                    ↓
        Diagnóstico determinístico CorePulse
             ↙                     ↘
   Salud/alertas                  PDF habilitado
                                   ↓
                         Plan base determinístico
                                   ↓
                         IA Groq (si disponible)
                                   ↓
                      Investigación web verificable
                                   ↓
                    PDF + vigencia + plan de acción
```

La IA nunca se ubica antes de la telemetría ni decide si un sensor existe.

## `core/` - identidad y política universal

- `device_identity.py`: obtiene identidad de sistema, placa madre, BIOS, CPU, RAM, GPU y almacenamiento desde fuentes reales de Windows.
- `hardware_policy.py`: reglas neutrales de selección de GPU, suficiencia de identidad, detección dinámica de posibles fuentes oficiales y objetivo de soporte físico.
- `product_contract.py`: contratos de integridad del producto.

En notebook, el objetivo de soporte físico es fabricante + modelo exacto cuando Windows lo expone. En desktop, se usa el modelo de sistema cuando es específico y, en su defecto, la placa madre. No se inventa un nombre comercial inexistente.

## `core/` - telemetría

- `telemetry.py`: fachada y matriz de cobertura de telemetría.
- `telemetry_full.py`: composición de fuentes y múltiples dispositivos.
- `telemetry_background.py`: adquisición en segundo plano.
- `telemetry_sampling.py`: muestreo temporal.
- `telemetry_consistency.py`: coherencia/frescura de lecturas.
- `telemetry_reliable.py`: fuentes base y fallbacks reales.
- `telemetry_lhm.py` y `lhm_provider.py`: sensores de HardwareMonitor/LibreHardwareMonitor.
- `telemetry_storage_cache.py`: continuidad de lecturas de almacenamiento sin fabricar muestras.
- `storage_health.py`: SMART/salud cuando el sistema o proveedor lo expone.

Las GPU se enumeran todas. La GPU representativa de tarjetas resumidas/overlay se selecciona por actividad real disponible, no por marca.

## `core/` - diagnóstico y salud

- `diagnostic_session.py`: ciclo de vida de la sesión y estadísticas temporales.
- `adaptive_diagnostic.py`: criterio adaptativo de finalización.
- `diagnostic_pipeline.py`: ensamblaje del resultado técnico.
- `diagnostic_explainer.py`: texto explicativo basado en hallazgos.
- `health_engine.py` y `live_health.py`: salud técnica.
- `alert_engine.py`: reglas de alertas con evidencia temporal.
- `recommendation_engine.py`: plan determinístico mínimo para condiciones reales confirmadas.

Los umbrales de sensores específicos se usan solo si provienen de la fuente/hardware. Las políticas propias de CorePulse, como presión de RAM o poco espacio libre, se identifican expresamente como políticas del producto y no como límites del fabricante.

## `core/` - IA, vigencia y evidencia

- `ai_report_engine.py`: sanitiza el inventario, limita la IA a problemas autorizados y combina plan determinístico + explicación.
- `ai_evidence_research.py`: investigación por componente, validación de fuentes, cálculo de confianza y vigencia estable.
- `env_config.py`: carga segura de configuración local.

La investigación de vigencia se realiza **por componente**. Las búsquedas se crean con el nombre, fabricante/vendor y hechos detectados del componente actual. Las fuentes oficiales se reconocen dinámicamente a partir de esa identidad; no existe una tabla de modelos permitidos.

La categoría final de vigencia pasa por una rúbrica determinística. `ALTA` requiere evidencia fuerte, diversa y coherente. La caché se usa para estabilidad temporal, no para convertir un fallo de red en un hecho nuevo.

Si el extractor de IA falla después de que la investigación sí reunió evidencia suficiente, CorePulse realiza una reparación compacta. Como último recurso puede recuperar únicamente la última evaluación verificada del **mismo componente exacto, mismo año y mismos hechos estables**. Esa recuperación es trazable, no se registra como una nueva verificación y limita la confianza a `MEDIA`; un componente distinto jamás puede heredar esa evaluación.

## Tutoriales y reemplazabilidad

Para mantenimiento físico se usa la plataforma exacta detectada + componente + problema + acción requerida. Un tutorial solo se marca `VERIFIED_EXACT` cuando:

- su URL provino de una búsqueda web real;
- YouTube confirma que el recurso existe;
- el título público coincide con el modelo/plataforma exactos;
- el título coincide con la acción necesaria.

La reemplazabilidad de CPU, GPU, RAM o almacenamiento nunca se asume por ser laptop o desktop. Debe verificarse para la plataforma exacta. La investigación conserva `upgradeability_by_component`, de modo que en configuraciones multi-GPU o multi-almacenamiento cada dispositivo tenga su propia evidencia. Si no existe evidencia suficiente, se mantiene `UNVERIFIED` y se evita recomendar una compra/intervención incompatible.

## `core/` - PDF

- `report_generator.py`: punto público mínimo de exportación.
- `report_builder.py`: composición profesional del documento.
- `report_base.py`: inventario, estilos/base y utilidades de evidencia.
- `pdf_context.py`: asegura que el PDF use el diagnóstico actual.

El PDF incluye identidad, BIOS/placa, componentes, telemetría, diagnóstico, vigencia anual, acciones, insumos, tutoriales verificados y trazabilidad. La falta de IA no elimina el informe técnico.

## Overlay, FPS y agente

- `presentmon_fps.py`, `presentmon_same_pid.py`, `fps_certification.py`: FPS/frametime reales.
- `rtss_osd.py`, `rtss_overlay_service.py`: overlay.
- `realtime_agent.py`: supervisión continua.
- `tray_service.py`: bandeja del sistema.

## Limpieza

`gui/cleaning_center.py` y `gui/cleaning_actions.py` mantienen funciones separadas para caché, memoria, duplicados y almacenamiento. Una acción de limpieza no debe ocultar ni modificar telemetría para mejorar artificialmente el diagnóstico.

## Persistencia

`database/telemetry_repository.py` mantiene el historial local. `data/` y `logs/` contienen solo archivos generados en ejecución y no forman parte del código fuente distribuido.

## Compatibilidad y validación

El objetivo actual de distribución es Windows 10/11 x64. La palabra universal describe cobertura de hardware dentro de la plataforma compatible, no una afirmación de soporte de todos los sistemas operativos. La compatibilidad debe probarse en matrices reales de hardware; cuando un proveedor no expone un dato, CorePulse devuelve `N/A` en vez de simularlo.
## Observabilidad y trazabilidad (V0.9.19.0w)

- `core/runtime_logging.py`: logging rotativo, redacción de secretos y captura de excepciones no controladas. Un error de logging nunca bloquea el programa.
- `gui/telemetry_detail_panel.py`: vista interna de solo lectura que muestra metadata `_metrics` y `_sensor_summary` ya certificada por la capa de telemetría. No consulta sensores por su cuenta ni estima datos.
- Los ciclos de telemetría y refresco de UI registran fallos repetitivos con throttling, preservando continuidad de ejecución y la política `REAL_OR_NA`.
- La tarjeta de cobertura del Dashboard funciona como acceso a la trazabilidad para que un usuario pueda distinguir una lectura válida de una no disponible y conocer su procedencia.



## Consistencia UI y diagnóstico (V0.9.19.1w)

- `core/health_engine.py` clasifica la condición térmica instantánea en normal, atención, advertencia o crítica usando sensores reales y, cuando existe, distancia a TjMax.
- `gui/live_health_binding.py` evita confundir una condición instantánea con una alerta sostenida: el agente temporal sigue siendo la autoridad de persistencia.
- `gui/telemetry_detail_panel.py` presenta las métricas certificadas en español y permite inspeccionar cada lectura sin reconsultar hardware.
- `gui/dashboard.py` refleja la antigüedad real del snapshot y aplica feedback visual solamente a tarjetas con navegación válida.
- `gui/hardware_storage_view.py` colorea la lectura de temperatura según la condición actual sin transformar el dato.
- `gui/storage_detail_panel.py` agrega etiquetas de interpretación a salud, temperatura y espacio manteniendo siempre visible la fuente cuando existe.


## Detalles avanzados de CPU (V0.9.20.1w)

- `gui/cpu_detail_panel.py` presenta una página interna de CPU integrada al mismo host de navegación del Dashboard.
- `core/device_identity.py::collect_cpu_identity()` obtiene únicamente especificaciones reales expuestas por `Win32_Processor`; no infiere TDP, microarquitectura ni capacidades ausentes.
- `core/telemetry.py::_cert_cpu_details()` conserva el inventario individual de sensores CPU tras la certificación y adjunta tipo, valor, unidad, identificador, fuente y timestamp real; `core/telemetry_full.py` mantiene el normalizador base.
- La vista consume `app.latest_telemetry` y no sondea LibreHardwareMonitor desde el hilo de Tkinter.
- La consulta CIM de identidad se ejecuta en un hilo separado para mantener responsiva la interfaz.
- Política contractual: `REAL_OR_NA_NO_INFERENCE`.

### Correcciones de consistencia V0.9.20.1w

- La certificación CPU ya no elimina `sensor_count` ni `sensors`; la vista avanzada recibe el mismo origen real que produce los agregados de temperatura, frecuencia y potencia.
- `gui/cpu_detail_panel.py` dispone de un fallback de compatibilidad que crea filas únicamente desde métricas agregadas ya certificadas del snapshot, nunca desde estimaciones.
- `gui/telemetry_detail_panel.py` resuelve frescura en orden: `sensor_timestamp` → timestamp legado → `snapshot_timestamp`; esto mantiene la trazabilidad incluso en fuentes como psutil sin timestamp de sensor físico.
- El sidebar distingue **servicio activo** de **alerta sostenida**, evitando que `NORMAL` contradiga una condición instantánea del Dashboard.
- La navegación a CPU usa una capa de carga visible mientras CustomTkinter construye la página, evitando frames de solapamiento visual.
- `core/health_engine.py` usa `TEMPERATURA CRÍTICA` cuando la evidencia térmica real alcanza nivel crítico, incluyendo distancia a TjMax ≤ 5 °C.


### Estabilidad de scroll V0.9.20.3w

La vista avanzada de CPU mantiene el `CTkScrollableFrame` por compatibilidad con resoluciones compactas, pero separa la frecuencia de telemetría de la frecuencia de repintado del canvas. Un observador ligero del `yview` detecta rueda, touchpad, arrastre e inercia; mientras el viewport cambia, CorePulse no reconfigura ni reconstruye los widgets internos. Las tarjetas superiores permanecen en tiempo real y la tabla recupera su actualización apenas el scroll queda estable. Esto reduce artefactos de Tk/CustomTkinter sin sacrificar datos ni alterar `REAL_OR_NA`.


### GPU Advanced Details V0.9.21.1w

**Consistencia V0.9.21.1w:** el total de VRAM de sensor certificado tiene prioridad sobre `Win32_VideoController.AdapterRAM`; WMI se conserva como inventario y se marca como limitado cuando corresponde. La asociación de pantalla se informa por adaptador sin inferir topología física no expuesta.


`gui/gpu_detail_panel.py` consume exclusivamente `app.latest_telemetry`; no abre LibreHardwareMonitor ni ejecuta CIM desde el hilo de Tkinter. El inventario `_gpu_inventory` une telemetría LHM con identidad real de `Win32_VideoController` cuando la correspondencia por nombre es demostrable. Cada adaptador conserva sus propias métricas y la interfaz permite cambiar entre ellos sin copiar datos de una GPU a otra. La selección inicial reutiliza la política universal de GPU representativa basada en actividad medida. Adaptadores sin sensores permanecen como `INVENTORY_ONLY` y muestran `N/A`. El panel aplica la misma separación entre telemetría viva y repintado del canvas usada en CPU para evitar ghosting durante scroll.

### RAM Advanced Details V0.9.22.0w

`gui/ram_detail_panel.py` separa inventario estático y telemetría dinámica. La identidad de módulos se obtiene mediante `core.device_identity.collect_ram_identity()` en un hilo de trabajo y nunca desde callbacks Tkinter. La telemetría de uso, memoria utilizada, disponible y total procede exclusivamente de `app.latest_telemetry`, cuyo origen es `psutil.virtual_memory` dentro del worker de telemetría.

`Win32_PhysicalMemory` es la autoridad para módulos físicos y `Win32_PhysicalMemoryArray.MemoryDevices` para el número de slots que Windows/SMBIOS expone. CorePulse sólo calcula slots disponibles como la resta transparente entre esos dos contadores reales. No se deduce canal Single/Dual, timings, XMP/EXPO ni información SPD que el sistema no publique. La vista aplica la protección de scroll usada por CPU/GPU y mantiene `REAL_OR_NA`.



### Windows 11 Tweaks V0.9.23.1w

- `core/windows_tweaks.py` es la única autoridad de lectura/escritura de tweaks.
- `gui/windows_tweaks_panel.py` sólo presenta el catálogo y despacha acciones.
- Cada aplicación guarda el valor anterior en `data/windows_tweaks_state.json`; deshacer restaura ese estado.
- El historial transaccional se registra en `data/windows_tweaks_history.jsonl`.
- No se ejecutan scripts remotos ni se aplican cambios de Defender o Windows Update.


### Biblioteca extendida de Tweaks V0.9.23.1w

`core/windows_tweaks.py` mantiene un catálogo declarativo con riesgo, privilegios, reinicio, operaciones de Registro y acciones PowerShell/WinGet opcionales. Los cambios de Registro guardan el valor exacto anterior en `data/windows_tweaks_state.json`; las acciones externas declaran una reversión definida. `gui/windows_tweaks_panel.py` nunca auto-selecciona ajustes Alto/Crítico y exige confirmación adicional para seguridad avanzada.


### Network Advanced Details V0.9.24.0w

`core/network_details.py` separa inventario, tráfico y diagnóstico. `collect_network_identity()` combina `psutil.net_if_stats`, `net_if_addrs` y `net_io_counters` con `Get-NetAdapter`/`Get-NetIPConfiguration` en Windows; `netsh wlan` sólo completa campos Wi-Fi publicados por el sistema. `NetworkTrafficSampler` calcula tasas desde deltas temporales de contadores reales y no usa pruebas de velocidad sintéticas.

`gui/network_detail_panel.py` ejecuta inventario y diagnóstico en hilos de trabajo, manteniendo Tkinter libre de PowerShell, `netsh`, ping y resolución DNS. El diagnóstico trata gateway, Internet y DNS como evidencias independientes: un gateway que bloquee ICMP no se interpreta automáticamente como pérdida de conectividad. La vista hereda la protección contra repintado durante scroll y conserva `REAL_OR_NA`.


### Network Sidebar Fix V0.9.24.2w
La ruta `network` se integra en las cuatro autoridades de navegación visual: `dashboard.py`, `dashboard_layout.py`, `ui_consistency.py` e `internal_navigation.py`, evitando que el botón desaparezca al reconstruir o redimensionar el sidebar.

### Real Internet Speed Test V0.9.24.2w

`core/internet_speed_test.py` implementa una prueba activa separada del muestreador de tráfico. Usa los endpoints públicos `speed.cloudflare.com/__down` y `/__up`, mide latencia sobre una conexión HTTPS persistente y ejecuta etapas de ancho de banda con cuatro flujos paralelos. La prueba sólo se inicia por acción explícita del usuario y corre en un thread de trabajo; Tk sólo consulta el estado compartido. Los contadores de `psutil` siguen representando exclusivamente tráfico instantáneo y nunca se presentan como velocidad contratada/capacidad.


### Global UI & Scroll Stability V0.9.24.3w

Las páginas internas extensas usan `gui.stable_scroll.StableScrollHost` en lugar de acceder al canvas privado de `CTkScrollableFrame`. El host usa un canvas Tk opaco con un frame CTk interno, agrupa eventos `Configure`, difiere cambios de scrollregion durante inercia y ofrece `defer_until_idle()` para evitar reconstrucciones mientras se desplaza.

`internal_navigation` publica las páginas mediante una capa opaca de transición: el usuario ve un estado estable mientras se construye el árbol de widgets y el commit lo revela de forma atómica. El Dashboard fuerza el repintado de su `FigureCanvasTkAgg` al ser descubierto para impedir superficies blancas residuales.

### Global Scroll Engine V2 V0.9.24.6w

`StableScrollHost` V2 elimina `Canvas.create_window` de las páginas internas grandes. Un viewport Tk nativo recorta un único frame CTk desplazado con `place`, los eventos de rueda/touchpad se agrupan a ~60 FPS y los repintados costosos continúan diferidos hasta que termina la inercia.

### Header & Sidebar Layout Refresh V0.9.24.10w

- El símbolo de CorePulse se renderiza en la cabecera principal y deja de ocupar altura dentro del sidebar.
- El sidebar queda reservado para navegación, estado del agente, selector de tema y versión.
- La identidad del equipo se alinea a la izquierda junto al símbolo y mantiene la autoridad de `collect_device_identity`.
- La autoridad responsive (`dashboard_layout.py`) tiene prohibido volver a montar `frame_logo` al redimensionar.
- La tarjeta del agente mantiene el detalle visible incluso en modo compacto gracias al espacio recuperado.
- El mismo contrato se aplica a tema claro y oscuro; sólo cambia el recurso gráfico/paleta mediante `theme_manager`.


### Sidebar Alignment & Agent Polish V0.9.24.10w

El sidebar reserva la zona superior para navegación desde el primer bloque `MONITOREO` y mantiene el agente, selector de tema y versión anclados en la zona inferior. La identidad CorePulse vive en el header principal y su separación izquierda se adapta al modo responsive.

### Reacción instantánea del agente V0.9.24.12w

El estado visual del Agente CorePulse separa dos capas: **reacción instantánea** y **alerta sostenida**. `core/agent_reaction.py` evalúa la muestra real más reciente con la misma política térmica del Dashboard y la expone como observación, mientras `IntelligentAlertEngine` conserva la autoridad exclusiva para activar alertas rolling. La interfaz puede cambiar inmediatamente a OBSERVANDO/REACCIONANDO sin escribir un pico aislado en el historial de alertas.



### Compatibilidad Python 3.12+ (V0.9.24.15w)

El proceso principal no fija un máximo de CPython. `core/python_compat.py` impone únicamente Python >= 3.12 y detecta capacidades opcionales por disponibilidad real de módulos. El stack LibreHardwareMonitor se instala separado del runtime base para evitar que la falta temporal de wheels de `pythonnet` para una versión futura impida iniciar CorePulse. Esta degradación mantiene la política REAL_OR_NA.


### Centro de Salud V0.10.0.0w

El Centro de Salud separa adquisición de datos, análisis y UI. `core/health_history.py` persiste muestras espaciadas; `core/battery_health.py` combina únicamente fuentes reales; `core/thermal_throttling.py` distingue evidencia explícita de sospecha; `core/benchmark_engine.py` ejecuta pruebas locales cortas; `core/windows_health.py` encapsula analizadores WMI/Event Log/Restore; `core/before_after.py` conserva snapshots observados. `gui/health_center_panel.py` consume estas capas fuera del hilo Tk mediante workers.
