# V182 — Benchmark GPU V14 · Visual Polish

V182 parte de V181. La lógica de medición y seguridad permanece, pero el workload visual cambia; por trazabilidad se incrementa el identificador de Benchmark GPU a V14. Los FPS V14 no deben compararse directamente con V13.

## Cambios
- Agua de 760 m, ondas no armónicas y dominio de ruido rotado/deformado para eliminar la cuadrícula visible.
- Mezcla atmosférica a distancia para esconder el borde del plano.
- Follaje con silueta lobulada + `fwidth` + dithering determinista en el borde y cuatro tarjetas por cluster.
- Avión con tomas de aire, pequeñas derivas adicionales y panelado metálico.

## Invariantes
- Perfil estándar conserva exactamente sus tiempos objetivo y reloj de pared.
- REAL_OR_NA y timestamps GPU auditados sin cambios de política.
- Seguridad térmica y propagación SAFETY_STOP de V181 conservadas.
- No se inventan FPS, temperaturas ni límites.

## Resultado
`resultados/benchmark_gpu_v14_ultimo_resultado.json`
