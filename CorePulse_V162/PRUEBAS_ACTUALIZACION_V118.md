# Prueba interna del actualizador V118

## Idea
V118 es el cliente base. Para probar una actualización real publica una release posterior (por ejemplo V119) en GitHub.

1. Crea una Release o Pre-release con tag `V119`.
2. Sube un asset llamado `CorePulse_119.zip` para probar desde código fuente.
3. Cuando exista instalador, sube también `CorePulse_Setup_V119.exe`.
4. Abre CorePulse V118 > `Actualizaciones`.
5. Selecciona `Pruebas internas` y pulsa `Buscar actualizaciones`.
6. Descarga. CorePulse valida el SHA-256 publicado por GitHub.
7. En modo fuente, `Preparar copia de prueba` extrae V119 en AppData sin tocar tu repo.
8. En modo instalado, `Abrir instalador` inicia el instalador verificado.

No se necesita guardar tokens en el proyecto. Si el repositorio se vuelve privado, usa temporalmente la variable de entorno `COREPULSE_GITHUB_TOKEN`.
