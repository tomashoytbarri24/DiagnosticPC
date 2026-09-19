# Test de Audio — V162 actual

## Acceso y funcionamiento

Centro de salud → Test de Audio. Ventana independiente con scroll, salida,
canales, micrófono, indicador de amplitud y resumen. El diagnóstico también
ofrece el acceso desde su tarjeta Audio.

La implementación usa WASAPI compartido y el dispositivo predeterminado del rol
multimedia de Windows. Consulta nombres e identificadores reales; no presupone
marcas ni índices. La enumeración no inicializa streams. Sólo los botones de
prueba reproducen y sólo «Grabar 5 s» abre captura. «Detener» y cerrar cancelan.

Los tonos duran 0,65 s, tienen entrada/salida gradual y amplitud máxima 0,08 de
escala completa. No se cambia el volumen de Windows. El usuario debe ajustar
antes un volumen cómodo: la presión sonora depende de su equipo/amplificador.
Los canales L/R se envían por separado; un dispositivo mono o una distribución
multicanal desconocida muestra N/A para la prueba estéreo.

La grabación dura cinco segundos. El nivel muestra el pico real de amplitud
capturada (0–1), no una puntuación de calidad ni una detección de voz. La copia
para reproducción es mono; se limita su pico sin amplificarla. Los datos viven
sólo en memoria y se descartan al volver a grabar, cambiar dispositivo o cerrar.
No se crean WAV, ni se envía voz a internet o a IA.

La API puede terminar correctamente sin que el usuario escuche nada. Por eso
cada reproducción necesita Sí/No/No estoy seguro. AUDIO VERIFICADO exige las
confirmaciones de izquierdo, derecho, ambos y reproducción del micrófono.
Una respuesta No se presenta como PROBLEMA REPORTADO; no implica diagnóstico
automático del componente averiado. Mono conserva verificación parcial.

## Diagnóstico conservador

Se guarda únicamente evidencia técnica y confirmaciones en `audio_test_latest.json`
del directorio de datos de CorePulse (habitualmente `%LOCALAPPDATA%\CorePulse`).
El diagnóstico consulta esa evidencia si tiene como máximo 24 horas y siguen
siendo los mismos endpoints predeterminados. Para comprobar identidad sólo usa
IMMDeviceEnumerator: nunca crea un stream, reproduce o captura audio.
Si falta evidencia, caducó o cambió un endpoint: NO EVALUADO.
No se añade una fase automática de audio ni se modifican las cargas del diagnóstico.

## Archivos

Nuevos:
- `core/windows_audio.py`: proveedor nativo y conversión PCM/float.
- `core/audio_test.py`: sesión, privacidad, confirmaciones y evidencia reciente.
- `gui/audio_test_panel.py`: interfaz guiada.
- `tests/test_audio_test.py`: pruebas con proveedores/COM simulados.

Modificados sólo para conectar Audio:
- `gui/health_center_panel.py`: acceso desde Centro de salud.
- `gui/diagnostic_view.py`: tarjeta y botón de Audio.
- `core/complete_diagnostic.py`: consulta pasiva de evidencia previa.
- `core/diagnostic_summary.py`: resumen y evidencia de Audio.

Sin dependencias añadidas ni cambios en requisitos/runtime. Archivos protegidos,
planes de energía, overlay, motores de benchmark y resize conservan sus hashes.
En el archivo compartido de Centro de salud sólo se agregó el acceso a Audio.

## Validación

- `python -m unittest tests.test_audio_test -v`: 28 casos; 27 correctos, 1 omitido.
  Incluye ausencias, permisos simulados, cambio de endpoint, errores de reproducción,
  privacidad, canales, PCM, buffers WASAPI simulados, cancelación previa y consulta
  pasiva ejecutando el pipeline de diagnóstico con proveedores simulados.
- 17 pruebas existentes de `test_v161_benchmark_diagnostic`: correctas usando
  una intercepción adicional en memoria de `_visual_gpu_result`. El primer intento
  se detuvo: el mock antiguo de GPU ya no interceptaba la ruta de V162 y generaba
  fallos de instrumentación. No se editó el benchmark para adaptar las pruebas.
- Prueba GUI omitida porque el Python del entorno no encuentra un `init.tcl`
  utilizable. Sintaxis comprobada y alcance revisado mediante SHA-256.
- Las pruebas de Audio no emitieron tonos ni activaron el micrófono real.

## Límites y prueba manual

No se ha validado el transporte WASAPI contra el hardware físico ni la ventana
real. Se admiten formatos compartidos PCM 16/24/32 bits y float32. Otros formatos,
permisos denegados y endpoints no disponibles se informan como error/N/A.
Procesamiento de Windows, audio mono de accesibilidad, Bluetooth o efectos del
fabricante pueden afectar la ruta audible; la confirmación humana es necesaria.

1. Reiniciar CorePulse desde esta carpeta y abrir Centro de salud → Test de Audio.
2. Comprobar los nombres de salida/entrada y usar un volumen cómodo.
3. Probar izquierdo, derecho y ambos; responder tras cada reproducción.
4. Pulsar Grabar 5 s, hablar y observar el nivel mientras aparece GRABANDO.
5. Reproducir la grabación y confirmar; probar también No/No estoy seguro.
6. Cerrar y ejecutar Diagnóstico: debe mostrar evidencia previa sin emitir sonidos.
7. Cambiar el dispositivo predeterminado o desconectarlo, actualizar y repetir:
   las confirmaciones anteriores no deben certificar el nuevo dispositivo.
8. Probar Detener/cerrar durante una grabación: debe parar y descartar la voz.

Referencias de API: [IAudioClient](https://learn.microsoft.com/en-us/windows/win32/api/audioclient/nn-audioclient-iaudioclient),
[captura WASAPI](https://learn.microsoft.com/en-us/windows/win32/coreaudio/capturing-a-stream),
[propiedades de endpoints](https://learn.microsoft.com/en-us/windows/win32/coreaudio/device-properties).
