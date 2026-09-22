# Validación V171 — Benchmark V9 Realistic Valley

## Alcance
V171 cambia únicamente la metodología/presentación del benchmark GPU y las referencias activas de esa metodología. CPU/RAM/SSD continúan usando sus cargas V4 existentes.

## Perfil estándar GPU
- Warm-up global: 5,0 s, excluido.
- Valle: 10,0 s medidos.
- Bosque: 12,0 s medidos.
- Lago: 12,0 s medidos.
- Extreme: 15,0 s medidos.
- Total nominal: 54,0 s; ventana medida acumulada: 49,0 s.
- Antes de cada ventana: 4 frames de transición excluidos.

## Correcciones de medición
1. `frame_time_ms` se mide inmediatamente antes y después de `render_frame()`/`Present()`. Telemetría y callbacks UI quedan fuera de la muestra.
2. Las timestamp queries D3D11 se recopilan durante el render, pero el resultado de una escena se toma una sola vez desde el `drain` final. Esto elimina la duplicación que podía producir coberturas superiores a 100 %.
3. `_gpu_time_stats` incluye un guardrail: cobertura máxima 1.0 y `gpu_sample_overflow_discarded` para evidenciar cualquier inconsistencia futura.
4. Queries `DISJOINT`, incompletas o inválidas no generan un tiempo inventado.

## Carga visual
- Árbol: 998 triángulos por mesh; tronco + ramas + 6 lóbulos de copa 3D. Un solo draw call instanciado.
- Agua: 40.898 triángulos, desplazamiento de ondas + micro-normal procedural + Fresnel + especular + espuma de costa.
- Extreme: ~4.578.524 triángulos/frame aproximados, 5.675 instancias/objetos lógicos, 7 draw calls principales.
- Shader/texture workload escala de 8/4 a 56/20 iteraciones/muestras según fase.

## Bug visual de V170
V170 dibujaba la sky sphere antes que la escena con el estado de profundidad por defecto. V171 la dibuja al final; así sólo rellena píxeles de fondo y no puede ocluir terreno/agua/vegetación con una faceta de la esfera.

## Validación automatizada en entorno de construcción
- Geometría/índices válidos.
- Perfil 54 s / 49 s medidos.
- Progresión estricta de carga.
- Cobertura GPU limitada a 100 %.
- Orden de render: sky después de clouds/escena.
- Material markers de corteza/follaje.
- Compilación Python de módulos modificados.

## Límite de validación
Este entorno no ejecuta Direct3D 11 físico. La renderización, timestamps del driver, uso/temperatura y apariencia final deben verificarse en Windows ejecutando `Probar_Benchmark_GPU_V9.bat`. Si DirectX o una métrica no está disponible, la política sigue siendo REAL_OR_NA.

## Resultado de validación de esta entrega
- `tests/test_v171_benchmark_v9_realistic_audited.py`: **10/10 PASS**.
- Compilación Python: **401 archivos / 0 errores**.
- Perfil estándar: **54,0 s nominales / 49,0 s medidos**.
- Árbol V9: **602 vértices / 998 triángulos por mesh**.
- Agua V9: **20.736 vértices / 40.898 triángulos**.
- Extreme: **~4.578.524 triángulos/frame** y **7 draw calls principales/frame**.
