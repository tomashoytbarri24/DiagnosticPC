# VALIDACIÓN V257 — Project Cleanup

Base: V256.

Se retiró únicamente material confirmado como no necesario para la ruta de ejecución vigente: cachés, documentación histórica acumulada, runners versionados de benchmark, bootstrap fuente obsoleto, helpers de tweaks sin dependencia física actual y el benchmark visual legado no importado.

Se conservaron todos los módulos alcanzables desde `main.py`/`corepulse_launcher.py`, recursos visuales, PresentMon, build, installer y dependencias de runtime.

La validación incluye compilación de todo Python, resolución estática de imports locales y pruebas V257.
