# Validación CorePulse V163

Base: V162 optimizada por Astra/Codex, continuada sin rehacer Benchmark ni Overlay.

## Cambios
- Red: identidad/tráfico permanecen activos en la vista Red; Ookla y lista de servidores se inicializan sólo al abrir Conectividad. Las sub-vistas ocultas dejan de repintarse.
- Gaming y Centro de salud: un refresh externo no ejecuta trabajo si la vista cacheada está oculta.
- Audio: actualizaciones de widgets sólo cuando cambia el valor, polling sin actividad al terminar y cancelación segura al destruir la vista.
- Energía: el resultado deja trazabilidad de `reused`/`duplicate_guard`; el contrato probado mantiene un único GUID/copia por modo a través de reinicios y bloquea una nueva duplicación si ya existe un nombre CorePulse no verificable.
- Limpieza: eliminadas envolturas `theme_color(theme_color(...))` equivalentes y cachés Python del entregable.

## Pruebas
- 91 pruebas dirigidas: OK, 1 omitida por entorno.
- Incluye Benchmark 2.0, audio, red, publicador Git y gestión de energía.
- Prueba adicional: 100 reinicios/aplicaciones simuladas de CorePulse Game producen una sola llamada `/duplicatescheme` y una sola copia.
- `compileall`: OK antes de limpiar cachés.

## Archivos protegidos
SHA-256 idéntico a la V162 recibida para:
- `core/runtime_venv_path.py`
- `bootstrap_corepulse.py`
- `core/source_runtime_bootstrap.py`
- `requirements-runtime-lock.txt`
- `core/nvme_smart_windows.py`

## Limitaciones
Este entorno no dispone de CustomTkinter/Tk operativo ni Windows real. No se afirma haber validado visualmente el resize, audio físico, Speedtest real ni `powercfg` real. Las pruebas de energía usan un backend simulado y nunca modifican los planes del equipo.

## Cómo probar V163
1. Ejecutar `Iniciar_CorePulse.bat` y comprobar V163.
2. Entrar/salir varias veces de Gaming, Audio, Red y Centro de salud; revisar que no queden pantallas congeladas.
3. En Red, abrir primero la vista Red y luego Conectividad; Ookla debe cargarse al abrir Conectividad.
4. En Test de Audio, ejecutar L/R/Ambos y micrófono; al terminar no debe quedar una operación ocupada.
5. Aplicar `CorePulse Game` o el perfil de rendimiento varias veces y reiniciar CorePulse; Windows no debe acumular copias idénticas del mismo plan.
6. Confirmar que Benchmark 3D, Diagnóstico y Overlay se comportan igual que en V162.
