# Auditoría V262 — Git Destinations & Release Flow

- Cambio funcional limitado al flujo de publicación Git y metadatos/documentación de versión.
- `main` se habilita como destino estable con confirmación explícita; las ramas `*/corepulse-dev` se presentan como desarrollo.
- La publicación se construye sobre el HEAD remoto de la rama elegida mediante índice temporal.
- No se ejecutan checkout, pull, merge ni force-push.
- HEAD, rama local y staging permanecen intactos.
- Sólo la carpeta de versión puede entrar al commit; FASE 1/2/3, `.github` y versiones anteriores quedan fuera.
- GitHub Actions/Releases siguen bajo control del repositorio raíz; CorePulse no escribe `.github`.
- Benchmark V25, Driver Hub, telemetría, salud de almacenamiento, dashboard, audio y scroll no se modifican.

# Auditoría V0.10.2.92w — Battery Wear State Visual Refinement

Cambio limitado a la presentación del desgaste dentro de Salud de batería. El porcentaje de desgaste sigue viniendo de la misma evidencia de batería; sólo cambia su jerarquía visual. La tarjeta dedicada ocupa dos filas y elimina el remate tipo barra para no sugerir una escala/progreso adicional. El color es contextual y no altera ni reinterpreta el valor. No cambia `core/battery_health.py`, fuentes, sensores, `REAL_OR_NA`, Gaming, Windows, limpieza, perfiles de energía ni rollback.

# Auditoría V0.10.2.87w — Power Profile Shutdown Persistence Fix

- Evidencia de usuario: el video muestra `CorePulse - Máximo rendimiento` activo antes de salir y `Alto rendimiento` activo durante el teardown posterior.
- Se corrige el ciclo de cierre, no sólo el estado visual.
- El GUID manual confirmado se conserva en memoria de sesión y se verifica después de Game Boost.
- Existe una segunda verificación al final de `safe_shutdown` y una tercera/definitiva inmediatamente antes de destruir la app, después del shutdown de telemetría y sensores.
- No se fuerza un perfil al arrancar: Windows sigue siendo autoridad para cambios hechos mientras CorePulse estuvo cerrado.
- La interfaz no usa `BALANCED` como fallback sin evidencia.
- `REAL_OR_NA`, `REAL_FPS_OR_NA_ONLY`, sensores, limpieza y Tweaks no se modifican.

# Auditoría V0.10.2.87w — Persistent Windows Power Profiles

- Cambio limitado al ciclo de vida de perfiles de energía y textos asociados de Gaming.
- Los perfiles manuales confirmados son persistentes; `shutdown()` no los revierte.
- El snapshot del perfil se usa como transacción de seguridad y se descarta después de un cambio verificado.
- Una aplicación fallida conserva rollback inmediato.
- Un backup pendiente al iniciar representa una transacción incompleta y se recupera antes de continuar.
- Game Boost conserva su rollback temporal independiente.
- El plan real de Windows es la autoridad: reinicios de CorePulse y cambios externos se detectan sin imponer un plan.
- `REAL_OR_NA`, `REAL_FPS_OR_NA_ONLY`, telemetría, sensores y Tweaks no se modifican.

# Auditoría V0.10.2.85w — Gaming Sidebar Consolidation

- Cambio limitado a arquitectura visual/navegación lateral.
- Gaming y Overlay siguen siendo páginas internas cacheables y funcionales.
- La autoridad visual del acceso Gaming queda en `Centro de salud > Rendimiento`.
- El estado activo del sidebar para Gaming/Overlay apunta a `Centro de salud`.
- No se modifican sensores, telemetría, optimizaciones ni rollback.
- `REAL_OR_NA` y `REAL_FPS_OR_NA_ONLY` preservados.

# Auditoría V0.10.2.84w — Gaming Session Hub UX Redesign

- Rediseño limitado a UX/jerarquía Gaming; no se amplían fuentes de telemetría ni permisos de optimización.
- `REAL_OR_NA` y `REAL_FPS_OR_NA_ONLY` preservados.
- Game Boost conserva snapshot/rollback previo.
- 36 suites seleccionadas y `compileall` en PASS.
- Render y DPI requieren validación final en Windows.

# Auditoría de estabilidad — V0.10.2.82w Hover Details Action Refinement

Superficie modificada:
- `gui/dashboard.py`: visibilidad contextual de `Ver detalles` en CPU/RAM/GPU.
- `gui/hardware_storage_view.py`: visibilidad contextual del botón de almacenamiento.
- metadatos de versión, build y pruebas de regresión.

No se modifica telemetría, sensores, muestreo, diagnóstico, limpieza de almacenamiento, rollback ni políticas `REAL_OR_NA` / `REAL_FPS_OR_NA_ONLY`.

## Startup 61w

La validación de startup se divide en gate mínimo, primer frame, gráficos diferidos, servicios background e integridad runtime diferida. No se declaran mejoras en segundos sin medición real en Windows; el archivo `startup_metrics.json` conserva las etapas observadas por equipo.

## V0.10.2.83w — Instant Detail Card Navigation

- Las fichas CPU/RAM/GPU/almacenamiento publican un shell antes de construir widgets pesados.
- Las cuatro vistas quedan cacheadas para evitar reconstrucción en reaperturas.
- CPU/RAM/GPU suspenden sus callbacks periódicos mientras están ocultas.
- No se modifica adquisición de telemetría, sensores, diagnóstico, limpieza ni política REAL_OR_NA.

## V0.10.2.94w — Runtime portable entre PCs
Se elimina la dependencia implícita de un `.venv` copiado desde el equipo de desarrollo. El proyecto fuente se autorrepara en Windows antes de cargar GUI/sensores. La validez del entorno se determina mediante imports reales; el marcador local sólo acelera el arranque y nunca sustituye la verificación de capacidad.
## V0.10.2.96w — Bootstrap Pip Resilience

Se eliminó el fallo duro observado cuando `pip install --upgrade pip setuptools wheel` devuelve código distinto de cero. El bootstrap usa el pip ya incluido en Python 3.12, puede repararlo con `ensurepip` y sólo detiene el arranque si la instalación del runtime real falla.

