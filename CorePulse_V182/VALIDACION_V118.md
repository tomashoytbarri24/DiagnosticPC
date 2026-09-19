# Validación CorePulse V118

## Objetivo
Dejar listo un actualizador manual para pruebas internas entre Maxi y Tomás mediante GitHub Releases.

## Criterios
- [x] V118 y stage `INTERNAL_RELEASE_UPDATER`.
- [x] Canal interno admite prereleases.
- [x] Canal estable excluye prereleases.
- [x] Selección ZIP en modo fuente e instalador en modo frozen.
- [x] Verificación SHA-256 obligatoria antes de preparar/abrir una actualización.
- [x] Descarga corrupta se elimina.
- [x] ZIP se extrae con protección contra path traversal.
- [x] Modo fuente no sobrescribe el repositorio actual.
- [x] Estado mutable de actualizaciones vive en AppData.
- [x] Acceso `Actualizaciones` integrado en sidebar.
- [x] Build scripts dejan de depender de versiones históricas hardcodeadas.
- [x] Runtime canónico y salud SMART sin cambios.

## Prueba automatizada
`python -m unittest tests.test_internal_updater_v118`

## Resultado ejecutado
- `python -m unittest -v tests.test_internal_updater_v118`: **7/7 OK**.
- Pruebas de regresión seleccionadas V115/V116/V117/V113: **PASS**.
- `compileall` de `core`, `gui`, `main.py` y launcher: **PASS**.
- Suite pytest completa no se usa como agregador porque existen validadores históricos que ejecutan `SystemExit` durante la colección; esto es comportamiento previo del repositorio, no una regresión de V118.
