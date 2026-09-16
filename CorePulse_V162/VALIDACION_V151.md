# Validación V151

Hotfix previo a publicación de rama.

- Cancelar diagnóstico deja `Diagnosticar de nuevo` visible y reutilizable sin reiniciar CorePulse.
- Publicador Git acepta una versión anterior rastreada por HEAD pero ya eliminada físicamente; esa eliminación forma parte del reemplazo normal.
- Si la versión anterior contiene modificaciones locales reales, la publicación sigue bloqueada para proteger trabajo.
- Actualizaciones/Publicar reduce alturas elásticas y conserva las acciones visibles en ventana y maximizado.
- FASE 1/2/3 siguen fuera del staging.
- Archivos protegidos de runtime y NVMe/SMART no se modifican.
