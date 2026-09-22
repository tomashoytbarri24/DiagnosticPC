# CorePulse V191 — Benchmark GPU V16 · UX Refinement

V191 parte de V190 y corrige problemas de usabilidad observados en la grabación real de Windows sin modificar el workload medido del Benchmark GPU V16.

## Cambios

- Configuración inicial más compacta para 1280x800: reduce altura y elimina una tarjeta de ayuda redundante para evitar scroll innecesario y el ghosting transitorio observado en RAM/SSD.
- Historial con divulgación progresiva: muestra primero 12 ejecuciones recientes y permite cargar 12 más bajo demanda, evitando construir decenas de tarjetas en el primer acceso.
- La carga del historial comunica que se preparan primero las ejecuciones recientes.
- Campo de ruta JSON alineado con la paleta CorePulse, sin fondo gris/marrón heredado.
- Evidencia térmica reorganizada en dos tarjetas legibles CPU/GPU y un estado explícito de protección térmica.
- Mantiene intactos DirectX V16, escenas, HLSL, geometría, wall-clock, FPS, 1% Low, timestamps GPU, REAL_OR_NA y persistencia JSON.

## Pendiente visual deliberado

El escenario 3D V16 sigue siendo funcional, pero la grabación V190 muestra margen de mejora estética en aviones, agua/costa y repetición de vegetación. Esos cambios modificarían materialmente el workload y deben hacerse como Benchmark GPU V17, no dentro de V191.
