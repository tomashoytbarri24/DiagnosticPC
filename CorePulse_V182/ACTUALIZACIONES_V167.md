# Actualizaciones automáticas de Desarrollo · V167

V167 conserva el actualizador seguro de V166 y automatiza la creación de la prerelease de Desarrollo.

## Flujo

1. CorePulse publica normalmente la raíz del clon en una rama `*/corepulse-dev`.
2. El publicador incluye en la raíz del repositorio `.github/workflows/corepulse-development-release.yml`.
3. Cada push a una rama `*/corepulse-dev` ejecuta GitHub Actions.
4. La Action detecta la carpeta `CorePulse_VN` más nueva y valida que `core/version.py` declare la misma versión.
5. Genera un ZIP fuente limpio `CorePulse_VN.zip` y `CorePulse_VN.zip.sha256`.
6. Crea o actualiza una única prerelease por versión con tag `VN-dev`.
7. El canal Desarrollo de CorePulse detecta esa prerelease. El canal Estable continúa ignorándola.

No se crea una Release diferente por cada commit: todos los pushes de una misma versión actualizan los assets de la misma prerelease.

## Seguridad

- No se guardan tokens ni contraseñas en CorePulse.
- GitHub Actions usa `github.token` con permiso `contents: write` sólo dentro del repositorio que ejecuta el workflow.
- El ZIP excluye `.git`, `.github`, `.venv`, `venv`, `.env`, `data`, `logs`, caches, `dist` y logs locales.
- Se publica un SHA-256 exacto para el ZIP.
- El workflow es administrado por CorePulse y no sobrescribe un archivo existente en esa ruta si no tiene la marca de gestión de CorePulse.
- `main`, `master` y `trunk` siguen bloqueadas en Publicar.

## Primera prueba real

Después de publicar V167 en `maxi/corepulse-dev`:

1. Abrir GitHub → Actions y esperar `CorePulse Development Release` en verde.
2. GitHub → Releases debe mostrar `V167-dev` como prerelease con `CorePulse_V167.zip` y su `.sha256`.
3. Abrir V166 → Actualizaciones → canal Desarrollo → Buscar actualizaciones.
4. Debe aparecer V167 como disponible y permitir descargar/verificar el ZIP.
5. Como V166 está dentro de un checkout Git, CorePulse preparará una copia aislada para probarla y no sobrescribirá la rama.
