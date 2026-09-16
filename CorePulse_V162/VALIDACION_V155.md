# Validación V155

Objetivo: corregir definitivamente el flujo de publicación de la carpeta CorePulse hacia la rama Git seleccionada sin confundir el repositorio con la carpeta versionada.

## Contrato
- Repositorio local: cualquier clon Git válido seleccionado por el usuario.
- Remoto: `origin` configurado en ese clon.
- Rama destino: rama activa, nunca `main`, `master` o `trunk`.
- Carpeta publicada: `CorePulse_V155` dentro de la raíz del repositorio.
- FASE 1, FASE 2 y FASE 3 no se preparan ni se incluyen en el commit.

## Seguridad V155
- Una versión CorePulse anterior con cambios locales ya no bloquea: se retira sólo del índice y sus archivos permanecen físicamente en el equipo.
- Una V155 local distinta se respalda fuera del repositorio antes de sincronizar.
- Cambios staged fuera de carpetas CorePulse siguen bloqueando la publicación.
- Si la publicación falla antes del commit, se restaura el índice y el destino respaldado.

## Pruebas dirigidas
`tests/test_v155_robust_branch_publish.py`: 5/5 PASS.

Casos cubiertos:
1. URL exacta de rama GitHub derivada de origin + rama.
2. V136 modificada localmente se preserva mientras sale del remoto.
3. V155 preexistente y distinta se respalda y reemplaza por la versión ejecutada.
4. V136 ya borrada físicamente se retira del remoto sin bloquear.
5. Archivos staged fuera de CorePulse siguen bloqueando.

`compileall` de `core`, `gui` y `main.py`: PASS.
