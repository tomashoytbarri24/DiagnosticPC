# CorePulse en Linux — V182

## Inicio sin comandos

1. Extrae la carpeta `CorePulse_V182`.
2. Haz doble clic en **`CorePulse_Linux.desktop`**. También puedes ejecutar el archivo **`CorePulse`** con doble clic.
3. En el primer inicio, si falta el entorno Python, CorePulse abre automáticamente una terminal de preparación. No tienes que escribir comandos; sólo aceptar/ingresar la contraseña del sistema si Linux la solicita.
4. Tras la preparación, busca **CorePulse** en el menú de aplicaciones y ábrelo como cualquier programa.

El instalador crea un acceso por usuario en `~/.local/share/applications` y un puntero estable `~/.local/share/CorePulse/current`. Las actualizaciones side-by-side actualizan ese puntero para que el menú abra la versión nueva.

## Capacidades disponibles

- Dashboard y monitoreo CPU/RAM.
- CPU: nombre, uso, frecuencia y temperatura cuando hwmon la expone.
- GPU NVIDIA mediante `nvidia-smi`; inventario AMD/Intel/NVIDIA mediante DRM/sysfs.
- Discos, SMART (`smartctl`) y batería por `/sys/class/power_supply`.
- Test de audio ALSA sin modificar volumen maestro.
- Diagnóstico, historial, PDF, red, temas, Git/Publicar y actualizaciones.
- Benchmark CPU/RAM/SSD/GPU; la GPU usa una ventana OpenGL/GLX visible y real en Linux.
- `Ajustes Linux` usa `powerprofilesctl` cuando está disponible y muestra governor, swappiness, zram y GameMode.

Los módulos exclusivos de Windows no se muestran en Linux.

## Nota sobre discos Windows en dual boot

CorePulse enumera el disco físico aunque su partición NTFS no esté montada. Modelo, capacidad, temperatura y SMART pueden estar disponibles sin montar; **usado/libre del sistema de archivos requiere que el volumen esté montado**, porque Linux no expone esas cifras de un NTFS offline de forma segura. CorePulse no monta unidades automáticamente ni inventa esos valores.
