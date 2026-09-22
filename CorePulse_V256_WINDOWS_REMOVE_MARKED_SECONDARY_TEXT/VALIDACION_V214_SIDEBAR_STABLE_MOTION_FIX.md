# V214 — Windows Mainline · Sidebar Stable Motion Fix

## Problema observado en video
- Durante el colapso/expansión, todo el dashboard se comprimía cuadro a cuadro.
- Textos, tarjetas y gráficos aparecían cortados durante la transición.
- El botón activo del sidebar se veía como una barra azul demasiado grande.
- El control de colapso no estaba donde visualmente corresponde: sobre el divisor lateral.

## Corrección
- El contenido principal ahora salta inmediatamente a su geometría final.
- Ya no se anima el ancho real del sidebar, por lo que las tarjetas no se deforman.
- El efecto tipo motion blur queda reducido a una estela breve en el borde.
- El botón de colapso pasa a ser flotante sobre el divisor sidebar/contenido.
- El modo colapsado usa un rail de 64 px con botones compactos de icono.
- El estado activo usa un acento suave, no una barra cyan extensa.

## Política
- No cambia telemetría ni autoridad de datos.
- Se mantiene REAL_OR_NA.
