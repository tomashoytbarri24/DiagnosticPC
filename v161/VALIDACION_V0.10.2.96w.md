# Validación V0.10.2.96w — Short Runtime Path Fix

## Problema reproducido

En rutas profundas de Windows, el bootstrap V0.10.2.96w creaba `.venv` dentro de la propia carpeta del proyecto. En el caso aportado, el proyecto estaba además duplicado dentro de otra carpeta con el mismo nombre largo, por lo que `pip` terminó intentando escribir rutas de `site-packages` superiores al límite Win32.

El registro real incluido en el proyecto muestra `WinError 206` durante la instalación de `pywin32`, y después el segundo intento queda sobre un entorno parcialmente instalado. Los avisos de Pylance sobre `matplotlib` y `pythoncom` son una consecuencia directa de que el runtime no terminó de instalarse.

## Corrección

- El runtime fuente ya no se instala dentro de la ruta larga del proyecto.
- En Windows se usa `%LOCALAPPDATA%\CorePulse\runtime\py312_<hash-lock>`.
- El nombre del entorno depende del hash de `requirements-runtime-lock.txt`, por lo que distintas revisiones incompatibles no pisan silenciosamente el mismo runtime.
- `source_runtime_bootstrap.py` y `bootstrap_corepulse.py` usan la misma resolución de ruta.
- `instalar_dependencias.bat` también usa un entorno de build corto bajo `%LOCALAPPDATA%\CorePulse\build\py312`.
- Se añadió configuración de VS Code para apuntar Pylance al runtime correcto de esta revisión.
- La distribución corregida no incluye el `.venv` roto/portable de la copia original.

## Resultado esperado en Windows

Al ejecutar `main.py` o `corepulse_launcher.py` desde una carpeta profunda:

1. CorePulse crea el runtime corto en AppData Local.
2. Pip instala los wheels sin depender de que Windows Long Paths esté habilitado.
3. Finalizada la instalación, CorePulse se relanza con el Python del runtime corto.
4. VS Code puede resolver `matplotlib`, `pythoncom` y el resto de dependencias al usar el intérprete configurado.

## Nota

No se desactiva ninguna dependencia ni se ocultan errores de sensores. El cambio sólo elimina la causa de longitud de ruta observada en el log real.
