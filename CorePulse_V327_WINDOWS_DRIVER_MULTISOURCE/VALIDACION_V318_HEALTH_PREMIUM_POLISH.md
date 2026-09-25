# Validación V318 — Health Premium Polish

## Base
- Proyecto base: V317

## Cambios
- Porcentaje principal de salud más grande y protagonista.
- Barra de salud con transición visual corta hacia el valor real.
- Mini indicador de tres niveles: normal / atención / crítico.
- Acento lateral, icono y estado visual reaccionan a la severidad real.
- Tooltip refinado con encabezados y bullets más limpios.
- Copy técnico humanizado: no se muestra `TjMax` al usuario; se expresa como margen hasta la temperatura máxima permitida.
- Textos internos relevantes se mantienen en blanco para mayor contraste.

## Integridad
- El porcentaje numérico mostrado se actualiza inmediatamente con el valor real.
- La animación afecta solo a la barra decorativa.
- REAL_OR_NA preservado.
- No se inventan sensores ni valores.
