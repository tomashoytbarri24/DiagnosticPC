# Versionado CorePulse

- CorePulse: **V261**
- Benchmark GPU/DirectX: **V25** (sin cambios de motor en V261)
- Plataforma objetivo: **Windows 10/11**
- Python: **3.12+**

## V261 — Scroll Audit & Storage Alignment

Corrige la alineación de la salud SMART/NVMe en las tarjetas de almacenamiento y normaliza el sistema de desplazamiento de las vistas largas. La rueda usa 96 px por paso y todas las páginas desplazables usan `StableScrollHost`; Benchmark conserva Canvas en resultados porque es la ruta validada para arrastrar la barra vertical.
