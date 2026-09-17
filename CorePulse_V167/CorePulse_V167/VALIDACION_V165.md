# Validación CorePulse V165

## Objetivo
Mejorar la experiencia del publicador por perfiles sin alterar el flujo Git seguro introducido en V164.

## Cambios principales
- El editor completo de perfil ya no aparece desplegado al entrar a **Publicar**.
- La vista principal muestra únicamente el selector de perfil y las acciones **Crear perfil / Editar perfil / Eliminar**.
- **Crear perfil** abre el editor bajo demanda.
- **Detectar Git** permite seleccionar la raíz de un clon y autocompleta `origin`, rama activa, usuario y correo desde la configuración Git local cuando están disponibles.
- Al guardar o seleccionar un perfil, el editor vuelve a quedar contraído.
- La consola de publicación se mantiene como registro visible de revisión y progreso del push.
- Diseño compacto mejorado para modo ventana: menos altura del editor, commit más compacto y consola con mayor altura útil.
- Se conserva publicación de la raíz completa, `.gitignore`, bloqueo de main/master/trunk y ausencia de force-push.

## Flujo esperado
1. Entrar a Actualizaciones > Publicar.
2. Elegir un perfil existente, o pulsar **Crear perfil**.
3. En un perfil nuevo, pulsar **Detectar Git** y elegir la carpeta raíz del clon.
4. Revisar los datos autocompletados, guardar y seleccionar la rama deseada.
5. Pulsar **Revisar** para ver cambios en la consola.
6. Pulsar **Publicar** y seguir el progreso en la misma consola.
