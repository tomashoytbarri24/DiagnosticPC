# Validación V187 — Benchmark GPU V16 UX Dashboard

## Revisión visual del video V186

La revisión completa confirmó que el workload V16 terminaba y entregaba resultados, pero la experiencia seguía presentando dos problemas de producto: respuesta percibida lenta en la primera entrada y una pantalla final excesivamente densa. También se observaron residuos de repintado/duplicación transitoria en la zona de resultados durante el scroll largo.

Hallazgos usados para V187:
- ausencia de feedback inmediato al primer clic mientras se construía la vista pesada;
- creación anticipada de Historial aunque no fuera usado;
- jerarquía visual insuficiente entre métricas principales y evidencia técnica;
- redundancia de GPU/Extreme y prominencia excesiva de la ruta JSON;
- alcance térmico global vs. fase GPU difícil de entender de un vistazo;
- ghosting transitorio aún visible en la vista larga de resultados.

## Invariantes del Benchmark GPU V16

- `core/directx_benchmark.py`: SHA-256 `a9106f3157a0a7e8cc54e4924d5afe2c0d99c78823a45c1acdb86b90c3d88437`
- `core/directx_scene.py`: SHA-256 `879f7a664d2616fa5485477e9475393bf11bd5b2d082cfaf2bf934ac5c05f5ee`
- `core/benchmark_engine.py`: SHA-256 `c77426c5b56632cda58c13af0a032470656ef3ae55e81ac209a8ea4d5fb40fe5`
- Los tres coinciden exactamente con V186.
- Resultado GPU: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.
- Perfil estándar GPU: 49 s medidos (10 + 12 + 12 + 15), sin cambios.

## Validación de código

- `py_compile`: PASS para `gui/benchmark_panel.py`, `gui/health_center_panel.py` y `core/version.py`.
- Suite funcional V179–V187 relevante, excluyendo guards históricos que exigen una versión/hash antiguo: 36 PASS.
- Primera entrada: shell visible + construcción diferida.
- Historial: construcción lazy y loading shell conservado hasta completar el árbol.
- Resultados: cuatro vistas, resumen por defecto, configuración colapsada al finalizar y retorno automático al inicio del resumen.
- Evidencia técnica: JSON, sensores, metodología y auditoría térmica separadas del vistazo principal.

## Pendiente de validación Windows

La mejora de percepción de apertura y la desaparición práctica del ghosting deben confirmarse con una ejecución real en Windows. V187 reduce la dependencia del scroll largo, pero no se declara validada visualmente hasta revisar el video del usuario.
