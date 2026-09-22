# CorePulse — Base canónica V262

## Identidad

- Aplicación: **V262**.
- Base inmediata: V261 Scroll Audit & Storage Alignment.
- Plataforma: Windows.
- Política de evidencia: **REAL_OR_NA**.

## Contratos que deben preservarse

- Salud NVMe/SSD: datos cuantitativos reales; nunca convertir Healthy/PASSED en 100 %.
- CPU: sensores reales y fallback de frecuencia, sin estimar temperatura.
- Benchmark: motor/cargas V25; no alterar metodología desde UI.
- Temas: 20 presets con contraste seguro.
- Git: publicación aditiva y segura, sin tocar FASE 1/2/3 ni `.github`.
- Drivers: búsqueda por ID de hardware, descarga desde Microsoft Update Catalog y validación/instalación con PnPUtil.
- Scroll: `StableScrollHost` es la autoridad para vistas desplazables; velocidad base 96 px. Resultados de Benchmark conservan backend Canvas para drag validado.
- Dashboard: la insignia de salud de almacenamiento permanece anclada al extremo derecho; «Ver detalles» no debe reservar espacio cuando está oculto.


## Destino Git V262

- Desarrollo, main estable y otras ramas remotas son destinos seleccionables.
- Main requiere confirmación explícita.
- Nunca force-push.
- Nunca incluir FASE 1/2/3 ni `.github` en un commit de versión.
- GitHub Actions/Releases son externos al árbol de la versión y se preservan.
