# CorePulse V113 — Benchmark GPU: revisión de video + HUD FPS + Shaders

## Fallos confirmados desde la grabación
- La ejecución Extendida llegaba a CPU 96.0 °C y se detenía por la regla absoluta `cpu_temp >= 96.0`.
- Como consecuencia, Geometría, Fill y Texturas obtenían resultado, mientras Carga combinada quedaba N/A.
- La ventana podía mostrar el fondo de Windows/blanco brevemente mientras se preparaban recursos OpenGL.
- El warm-up usaba la carga combinada y podía mostrar el patrón de texturas antes de la Fase 1.

## Correcciones
- Eliminada la detención fija por CPU 96 °C y GPU 92 °C.
- CPU: stop sólo ante `Distance to TjMax <= 1.0 °C` durante dos muestras consecutivas, si el sensor real existe.
- GPU: stop sólo contra límites térmicos reales reportados por sensores, si existen, durante dos muestras consecutivas.
- Frame oscuro publicado inmediatamente antes de reservar texturas para evitar flash blanco.
- Warm-up neutro basado en geometría + shader disponible; no contamina métricas.
- SAFETY_STOP/CANCELLED/PARTIAL ahora muestran el motivo visible en la página Benchmark.

## Continuación del benchmark
- Nueva fase real `Shaders / ALU` mediante GLSL 1.20 cargado por `wglGetProcAddress`.
- Si GLSL no está disponible, la fase queda N/A; no se simula.
- Carga combinada incorpora shaders cuando están disponibles.
- HUD OpenGL con FPS reales en la esquina superior derecha y número de fase en la superior izquierda.
- El HUD deriva FPS de frametimes reales de la fase activa y reinicia su ventana al cambiar de fase.
- El texto del HUD usa display lists para minimizar la interferencia de medición.

## Fases actuales
1. Geometría
2. Fill / fragmentos
3. Texturas / VRAM
4. Shaders / ALU
5. Carga combinada

Compute y Ray Tracing permanecen fuera hasta implementar cargas reales.

## Validación estática ejecutada
- `test_benchmark_main_sidebar_v113.py`: PASS
- `test_benchmark_preconfiguration_v113.py`: PASS
- `test_visual_3d_benchmark_v113.py`: PASS
- `test_visual_benchmark_primary_v113.py`: PASS
- `test_gpu_benchmark_multiphase_v113.py`: PASS
- `test_gpu_benchmark_video_fix_hud_shaders_v113.py`: PASS
- `py_compile` módulos modificados: PASS

Nota: la ejecución Win32/OpenGL/GLSL final debe verificarse en Windows con GPU real; el entorno de construcción actual no puede abrir ese contexto gráfico.
