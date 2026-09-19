# CorePulse V159 — Cambios y validación

Base: CorePulse_V158.zip aportado por el usuario. V158 añadió un módulo de redibujado y su integración; no reemplazó los motores del diagnóstico de V157. Se compararon ambos ZIP antes de modificar.

## Correcciones

1. El aplazamiento de redibujos ahora pertenece a la ventana que está siendo redimensionada. Un diálogo u otra ventana continúa dibujando aunque la principal esté en resize. Dos ventanas pueden finalizar sus redibujos pendientes de forma independiente.
2. Se ejecuta el manejador original de dimensiones de CustomTkinter, preservando escala/DPI, actualización de tamaños, retorno y errores. Sólo se aplaza su llamada a dibujar durante resize; fuera de ese gesto el proveedor ejecuta su comportamiento normal. V158 copiaba esa lógica y no utilizaba el original guardado.
3. Al salir de CorePulse se retiran los widgets pendientes de esa ventana y se cancela el temporizador de resize.
4. La prueba gráfica de V158 que admitía cualquier número de pendientes (>=0) ahora exige dos eventos, cero dibujos durante el gesto y exactamente un dibujo al finalizar.
5. Se añadieron 15 pruebas de comportamiento con el manejador real de CTk y widgets instrumentados. La versión y la documentación se actualizaron a V159.

No se modifican motores SMART/NVMe, dependencias bloqueadas, bootstrap, telemetría, diagnóstico/cancelación, reparación, Gaming, PDF ni benchmark. La integración de cierre en main.py sólo libera el control de resize. No se ejecutaron reparaciones ni publicaciones remotas.

## Pruebas

- Regresión dirigida V157 + V158 + V159: **38 aprobadas y 4 omitidas**, de 42 pruebas.
- Las 15 pruebas nuevas comprueban: 1.000 eventos → 1 dibujo final, último tamaño correcto, tamaños sin cambios, conversiones a escala 1/1,25/1,5/2, independencia de ventanas, destrucción y errores de widgets, liberación al cerrar, instalación repetida, restauración del método original y referencias débiles.
- Suite general en V158: **107 aprobadas, 45 fallidas y 4 omitidas**.
- Misma suite en V159 más pruebas nuevas: **122 aprobadas, 45 fallidas y 4 omitidas**. La lista de los 45 fallos es idéntica; no hay fallos nuevos. Se conserva el inventario en PRUEBAS_V159.json.
- Los 28 scripts heredados adicionales produjeron los mismos códigos de salida en ambas versiones: **10 aprobados y 18 fallidos**. Entre los aprobados están sintaxis de arranque, estructura/integridad, parser NVMe, almacenamiento, seguridad de comandos, drivers, política de hardware y creación real de PDF.
- Todos los módulos Python entregados se validaron con ast.parse; se verificó el CRC y el contenido íntegro del ZIP.
- Se adaptaron dos contratos del test de V158 a la API por ventana y a versiones >=158; no se eliminaron los fallos heredados para obtener una suite verde.

## Lo que no se pudo verificar

Las cuatro pruebas que necesitan una ventana real se omitieron porque Tcl/Tk no logra leer init.tcl en este entorno. Las pruebas nuevas usan el manejador de dimensiones del CustomTkinter 6.0.0 instalado, con widgets instrumentados; no certifican arrastre con mouse, framerate, GPU ni una sesión gráfica completa en Windows. No se afirman mejoras de FPS medidas. Los resultados con Xvfb descritos en VALIDACION_V158.md pertenecen a la entrega anterior y no se presentan como pruebas ejecutadas aquí.

La suite antigua conserva fallos de contratos de versiones anteriores y de publicación/actualización, entre otros. El informe no afirma que todos sean simples comprobaciones del número de versión.

## Cómo abrir

En la carpeta **v159** del escritorio, abrir **Iniciar_CorePulse.bat** o **CorePulse.vbs**. El proyecto completo está directamente dentro de v159; también se incluye CorePulse_V159.zip como copia empaquetada.
Se mantiene el runtime fuente de CorePulse y sus dependencias existentes; no se generó un EXE nuevo.

Para reproducir las pruebas dirigidas con el runtime instalado:

`python -m unittest tests.test_v159_resize_ownership tests.test_v158_resize_render_guard tests.test_v157_diagnostic_lifecycle -v`

Comprobación manual pendiente: redimensionar el diagnóstico/centro de salud, abrir un diálogo durante resize, iniciar → cancelar → reiniciar, y cerrar desde la bandeja. No requiere aplicar reparaciones.

## Archivos protegidos

Los cinco archivos coinciden byte por byte entre V157, V158 y V159:

- `core/runtime_venv_path.py`: `263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92`
- `bootstrap_corepulse.py`: `925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b`
- `core/source_runtime_bootstrap.py`: `bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd`
- `requirements-runtime-lock.txt`: `36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706`
- `core/nvme_smart_windows.py`: `fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283`
