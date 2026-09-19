# Validación V168

- Actualización fuente side-by-side: validada.
- Carpeta actual permanece intacta: validado.
- SHA-256 obligatorio antes de preparar la nueva versión: preservado.
- Destino manual preexistente no se sobrescribe: validado.
- Helper espera el cierre y lanza la nueva versión: validado con prueba aislada.
- Rollback manual eliminado de la interfaz: validado.
- Publicador/perfiles Git y automatización de releases: regresión preservada.
- Suite focal: 44 pruebas + 6 subpruebas correctas (con stub de CustomTkinter sólo para pruebas UI sin display).
