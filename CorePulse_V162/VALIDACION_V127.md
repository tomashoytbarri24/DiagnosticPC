# VALIDACIÓN V127

## Objetivo
Hacer que el Centro de salud > Reparación muestre la ejecución real de DISM/SFC en una consola de Windows PowerShell visible y elevada, y que CorePulse importe después la salida real dentro de la propia interfaz.

## Comportamiento implementado
- El diagnóstico y la reparación abren `powershell.exe` visible.
- La consola se solicita con `runas` mediante `ShellExecuteExW`, por lo que Windows muestra UAC si CorePulse está abierto como usuario estándar.
- No es necesario reiniciar CorePulse completo como administrador; esa opción sigue disponible como alternativa manual.
- PowerShell muestra cada comando y su salida real mientras DISM/SFC trabajan.
- La consola conserva por etapa el código de retorno, duración y salida real en UTF-8.
- Al terminar, CorePulse importa esos archivos, aplica la clasificación `REAL_OR_NA` existente y presenta la salida dentro de la pestaña Reparación.
- Si el usuario cancela UAC o cierra PowerShell antes de terminar, CorePulse no inventa éxito: las etapas sin resultado quedan como fallo/no concluyentes.
- Las APIs silenciosas anteriores se conservaron para compatibilidad; la UI de Reparación usa las nuevas APIs visibles.

## Validaciones
- PASS — V127 / `VISIBLE_ELEVATED_WINDOWS_REPAIR_CONSOLE`.
- PASS — secuencias DISM/SFC previas preservadas.
- PASS — elevación independiente con UAC (`runas`).
- PASS — consola visible (`SW_SHOWNORMAL`).
- PASS — captura e importación de stdout real por etapa.
- PASS — cuadro de salida real dentro de CorePulse.
- PASS — no se usa `shell=True`.
- PASS — runtime canónico y SMART/NVMe sin cambios.

## Política
Se mantiene `REAL_OR_NA`: CorePulse clasifica únicamente evidencia real devuelta por Windows y conserva `COMPLETED_UNCLASSIFIED`/error cuando la salida no permite afirmar un estado.
