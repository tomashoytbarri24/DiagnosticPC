# CorePulse V171 — Quality Gate

La validación oficial del árbol fuente es:

```text
Validar_CorePulse.bat
```

o, desde Python:

```text
python quality_gate.py
```

El gate valida la autoridad única de versión (`core/version.py`), sincronización de metadatos, compilación de los módulos de runtime y la suite pytest actual. Las regresiones históricas `test_vNNN_*` anteriores a V162 se conservan como documentación ejecutable, pero están marcadas `legacy_snapshot` y no bloquean una release actual porque verifican estados de UI ya reemplazados.

## Pruebas que necesitan Windows real

La suite automatizada normal no debe cambiar planes de energía, ejecutar DISM/SFC, lanzar juegos ni depender de sensores físicos. Antes de una release estable hay que validar manualmente en Windows: arranque GUI/CustomTkinter, temperaturas y sensores LHM, Test de Audio con dispositivos físicos, Overlay/RTSS dentro de un juego, planes de energía con `powercfg`, Ookla/Red avanzada, actualización con cierre/reinicio entre versiones y build EXE/instalador con su self-test.

El modificador `--windows-real` queda reservado para pruebas futuras marcadas explícitamente `windows_real`; nunca se activa por defecto.


## Linux

En Linux se puede ejecutar `./Validar_CorePulse_Linux.sh`. La suite automática valida el proveedor Linux, el backend ALSA, el dispatcher de sensores, la ausencia de dependencias Win32 en `requirements-linux.txt` y el filtrado de funciones exclusivas de Windows en la interfaz Linux.

La validación de hardware real (temperaturas hwmon, GPU/driver, audio ALSA, SMART y batería) debe realizarse en un equipo Linux físico porque depende de los dispositivos y permisos expuestos por el kernel.
