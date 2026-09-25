# VALIDACIÓN V298 — AUTO MULTI-PYTHON BOOTSTRAP

## Objetivo
Evitar que un primer arranque directo con CPython 3.12+ x64 falle inmediatamente por módulos ausentes.

## Flujo
1. CorePulse comprueba imports esenciales antes de cargar CustomTkinter.
2. Si faltan, busca un runtime validado.
3. Si no existe, crea automáticamente un venv para el mismo minor de Python.
4. Instala lock o fallback flexible.
5. Valida el stack completo.
6. Sólo entonces reejecuta CorePulse en ese runtime.

## Política
No se simulan capacidades y no se declara un Python compatible si falla la validación de dependencias reales.

## Dependencias de bootstrap
El primer arranque instala únicamente dependencias de ejecución; PyInstaller queda fuera del runtime para no bloquear compatibilidad de la aplicación por una herramienta de empaquetado.
