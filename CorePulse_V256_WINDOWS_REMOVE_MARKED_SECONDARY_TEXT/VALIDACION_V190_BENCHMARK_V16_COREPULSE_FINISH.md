# Validación V190 — Benchmark GPU V16 · CorePulse Finish

## Alcance
Validación estática y funcional del cierre visual V190. Este entorno no ejecuta la ventana Direct3D 11 de Windows, por lo que la comprobación final del cursor/HUD debe realizarse con una ejecución real en Windows.

## Contrato V16 preservado
- `core/directx_scene.py`: idéntico a V189.
- `core/benchmark_engine.py`: idéntico a V189.
- HLSL embebido en `core/directx_benchmark.py`: hash idéntico a V189.
- Resultado persistente: `resultados/benchmark_gpu_v16_ultimo_resultado.json`.
- Perfil estándar: 10 + 12 + 12 + 15 = 49 s medidos, con warm-up/settle fuera de estadísticas.
- `REAL_OR_NA`, timestamps GPU y seguridad térmica preservados.

## Cambio DirectX permitido
`core/directx_benchmark.py` añade `WM_SETCURSOR` y `SetCursor(None)`. Ese trabajo se procesa en la ruta de ventana/pump y al mostrar la ventana, fuera de la región que cronometra render + Present. No modifica shaders, geometría ni carga gráfica.

## UX / diseño
- Escala tipográfica Benchmark: métrica 22, escena 15, título 16, sección 11, cuerpo 10, metadato 9, microtexto 8.
- No hay texto de 7 pt en las vistas principales del Benchmark.
- Cian/azul CorePulse como acento principal; valores primarios en blanco.
- Tarjetas con radios y bordes consistentes y pills de estado.
- `Prueba actual / Historial` distingue navegación de la acción `Repetir prueba`.
- El bloque de estado ya no usa el borde magenta legado.

## Alertas térmicas
Una muestra instantánea clasificada como crítica sigue participando en la autoridad de salud real, pero su presentación visual es ámbar/OBSERVANDO hasta confirmar persistencia. Una alerta sostenida crítica permanece roja/REACCIONANDO. La lógica de seguridad del benchmark no cambia.

## Pruebas
- `py_compile`/`compileall`: PASS.
- Suite funcional relevante V179–V190 seleccionada: **41 PASS**.
- Pruebas específicas V190: **7 PASS**.
- Autoridad unificada de salud con muestra instantánea real: PASS.

Los tests históricos que exigen literalmente números de versión antiguos o hashes de V13/V180 no se consideran regresiones vigentes.
