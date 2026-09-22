# Changelog

## V261 — Scroll Audit & Storage Alignment
- Salud de discos anclada de nuevo al extremo derecho de cada tarjeta del Resumen.
- «Ver detalles» se superpone al badge sólo durante hover y deja de reservar un hueco fijo.
- Scroll base unificado a 96 px por paso.
- Páginas largas migradas a `StableScrollHost` y backend `place` cuando corresponde.
- Temas, publicación Git e historial de benchmark dejan de usar `CTkScrollableFrame`.
- Resultados de Benchmark conservan Canvas, pero con velocidad normalizada a 96 px y drag de barra derecha.
- V260 Startup Gate y el resto de la lógica funcional se mantienen.

## V260 — Startup 97% Hotfix
- Corrige el bloqueo visual del arranque en 97 %.
- La telemetría ya no intenta acceder a `_header_last_update` cuando el header de agente fue eliminado en V259.
- No modifica benchmark, Driver Hub, almacenamiento, temas ni el resto de módulos funcionales.

## V259

- Eliminada la tarjeta redundante Estado del agente del header del Resumen.
- Benchmark: sin área vacía antes de ejecutar; progreso/resultados nacen sólo durante/después de una ejecución.
- Benchmark: scroll de resultados migrado al backend Canvas para recuperar el drag de la barra derecha.
- Driver Hub rediseñado y simplificado.
- Añadidos Descargar todo e Instalar todo; firmware se omite de la instalación masiva.
- Sustituida la sesión Windows Update Agent por consulta directa del Microsoft Update Catalog mediante ID de hardware + descarga directa + PnPUtil.
- Versión de aplicación actualizada a V259.

## V258

- Recuperación selectiva sobre V257 de salud NVMe, CPU, temas, audio, drivers y publicación segura.
