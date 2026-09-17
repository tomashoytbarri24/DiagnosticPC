# Validación V0.10.2.94w — Bootstrap Relaunch Loop Fix

## Corrección principal

La 93w lanzaba CorePulse preparado con `.venv\Scripts\pythonw.exe`, pero `core/source_runtime_bootstrap.py` sólo aceptaba `.venv\Scripts\python.exe` como runtime local. Eso provocaba un ciclo: bootstrap -> pythonw -> bootstrap -> pythonw.

La 94w reconoce ambos intérpretes como parte del mismo `.venv` autoritativo. Los imports reales siguen siendo obligatorios antes de considerar el runtime listo.

## Validación estructural

- `python.exe` local aceptado: PASS
- `pythonw.exe` local aceptado: PASS
- bootstrap sigue relanzando con `pythonw.exe`: PASS
- marcador no sustituye validación de imports: PASS
- `compileall`: PASS
- test específico de relaunch loop: PASS
- self-bootstrap: PASS
- startup gate / first frame: PASS
- launcher / EXE integrity: PASS
- batería: PASS
- Gaming / perfiles de energía: PASS
- análisis Windows: PASS
- storage / RAM profunda: PASS
- CPU/GPU: PASS
- rollback Tweaks: PASS

Se ejecutaron 26 suites relevantes; 25 de forma directa y la suite heredada de RAM con `PYTHONPATH=.` por su forma de importación. Todas finalizaron con código 0.

## Validación Windows pendiente

La ejecución nativa debe verificarse en Windows: al primer arranque puede aparecer una sola ventana `CorePulse está preparando este PC`; al terminar debe cerrarse y abrir CorePulse una única vez, sin reaparecer el preparador mientras el `.venv` permanezca sano.
