# Validación V166 — Benchmark V4 por áreas

## Objetivo
Medir únicamente trabajo realmente ejecutado por este PC. Cada área no aislable se declara `N/A`; no se sustituye por estimaciones, tablas por modelo ni valores aleatorios.

## Cobertura activa

### CPU
- SHA-256 single thread: medido.
- SHA-256 multi thread: medido.
- Throughput SHA-256: medido.
- Compresión zlib: medido + integridad.
- Descompresión zlib: medido + integridad.
- Procesamiento de imagen Pillow: medido + SHA-256 de salida estable.
- Integer ALU puro: N/A (backend nativo pendiente).
- Floating Point puro: N/A.
- SIMD puro: N/A.
- Cache latency: N/A.

### RAM
- Native write/fill (`memset`): medido, mediana 3.
- Native copy (`memmove`): medido, mediana 3.
- Warm-up excluido del intervalo medido.
- Sentinelas de contenido post-test.
- Pure read: N/A.
- Latency: N/A.

### SSD
- Sequential write/read: 3 muestras.
- Windows Direct I/O cuando el controlador/volumen lo acepta.
- Random 4K QD1 read/write: 3 muestras en Windows.
- Latencia QD1: `1000 / IOPS`, sólo cuando IOPS fue medido.

### GPU
- Geometry / Vertex.
- Pixel Fill / Blending.
- Texture Sampling.
- Fragment Shader / ALU.
- Compute Shader / GPGPU.
- Mixed Graphics.
- GPU Buffer Copy / physical VRAM bandwidth: N/A en V166.
- Ray Tracing: N/A.
- Mesh Shaders: N/A.
- AI/Matrix: N/A.

## Validación ejecutada en entorno de desarrollo
- `py_compile` de módulos modificados: PASS.
- `test_v166_benchmark_v4_areas.py`: PASS.
- compatibilidad wrappers V3: PASS.
- smoke CPU V4: integridad PASS.
- smoke RAM V4: integridad PASS.
- suite CPU+RAM V4: finaliza correctamente.

## Validación pendiente en PC Windows físico
- GPU OpenGL acelerada por hardware.
- VSync / Timer Query del driver.
- SSD `NO_BUFFERING + WRITE_THROUGH`.
- Random 4K QD1.
- Repetibilidad térmica/energética del equipo real.

## Regla
`REAL_OR_NA`: si una capacidad no puede aislarse o verificarse, CorePulse publica `N/A`, no una aproximación.
