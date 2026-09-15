# CorePulse V129 — Centro de Actualizaciones Seguro

V129 reemplaza la experiencia de pruebas del actualizador V118 por un centro de actualizaciones preparado para distribución.

## Cambios
- Canales **Desarrollo** y **Estable** sobre GitHub Releases.
- Muestra versión instalada/disponible, fecha, tamaño y changelog.
- Descarga únicamente el asset de actualización; no clona el repositorio.
- Verificación SHA-256 obligatoria mediante `asset.digest` de GitHub o archivo sidecar publicado (`.sha256` / SHA256SUMS).
- Un paquete que no puede verificarse no se instala ni ejecuta.
- En una copia fuente portable crea backup antes de aplicar y conserva hasta 3 backups.
- Aplicación diferida mediante helper: CorePulse se cierra, se actualiza y se relanza.
- Si falla la aplicación del paquete, el helper intenta restaurar automáticamente el backup.
- Rollback manual disponible para copias fuente portables.
- Si detecta un checkout Git, no lo sobrescribe: prepara una copia aislada para pruebas.
- En modo instalado abre únicamente un instalador verificado.
- La UI usa roles exactos del tema activo.

## Integridad
No se modifican runtime universal ni SMART/NVMe.
