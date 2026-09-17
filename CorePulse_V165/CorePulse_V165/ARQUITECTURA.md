# Arranque fuente directo — V113

CorePulse ya no ejecuta un bootstrap automático antes de abrir. `main.py` y `corepulse_launcher.py` usan directamente el intérprete activo. `CorePulse.vbs` sólo localiza un Python ya preparado y lanza el proyecto; no instala, repara ni crea entornos. El EXE/instalador final seguirá siendo autocontenido.

# Arquitectura — V0.10.2.60w

`gui/dashboard.py` deja de construir tres mini tarjetas estadísticas encima de los gráficos. Se reemplazan por una cabecera única de tendencias y una geometría común para los tres ejes Matplotlib.

`main.py` conserva el mismo origen de datos y el mismo mecanismo de blitting. Sólo cambia la presentación inicial de la figura y su tamaño visual.

## Runtime fuente autocurable (V0.10.2.94w)
`core/source_runtime_bootstrap.py` se ejecuta antes de dependencias externas. En Windows fuente exige el `.venv` local de CorePulse; si falta o no puede importar el núcleo requerido, entrega el control a `bootstrap_corepulse.py`. Este bootstrap usa sólo stdlib/Tkinter, crea/repara `.venv`, instala el lock runtime y verifica imports reales. El modo PyInstaller/frozen no usa esta ruta porque el EXE conserva su self-test autocontenido.
## Bootstrap pip resiliente (V0.10.2.96w)

El bootstrap fuente no convierte una actualización de herramientas de empaquetado en dependencia funcional. Primero valida `pip` dentro del `.venv`; si no existe o está roto, usa `ensurepip --upgrade`, que forma parte de Python y no requiere PyPI. Después instala directamente el runtime bloqueado con reintento. Sólo un fallo real de instalación de dependencias puede detener el arranque.

