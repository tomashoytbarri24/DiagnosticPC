# Versionado CorePulse

- CorePulse: **V262**
- Benchmark GPU/DirectX: **V25** (sin cambios de motor en V262)

## V262 — Git Destinations & Release Flow

V262 añade selección explícita del destino Git sin cambiar de checkout local. Desarrollo usa ramas `*/corepulse-dev`; `main` se trata como destino estable y requiere confirmación. Los workflows/Releases siguen viviendo en `.github` del repositorio y CorePulse nunca los modifica durante una publicación.

## V261 — Scroll Audit & Storage Alignment

Corrige la alineación de la salud SMART/NVMe en las tarjetas de almacenamiento y normaliza el sistema de desplazamiento de las vistas largas. La rueda usa 96 px por paso y todas las páginas desplazables usan `StableScrollHost`; Benchmark conserva Canvas en resultados porque es la ruta validada para arrastrar la barra vertical.
