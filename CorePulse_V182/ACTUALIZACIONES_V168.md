# Actualizaciones V168

## Flujo

1. Buscar release en GitHub.
2. Descargar el ZIP compatible y verificar SHA-256.
3. Instalar la nueva versión como carpeta hermana de la versión en ejecución.
4. Cerrar CorePulse actual.
5. Abrir automáticamente la nueva versión.

Ejemplo:

`DiagnosticPC-Maxi/CorePulse_V167` → `DiagnosticPC-Maxi/CorePulse_V168`

La carpeta V167 no se modifica ni se borra. El actualizador no sobrescribe una carpeta `CorePulse_V168` preexistente que no haya creado él mismo.

El botón Rollback y la copia de prueba visible se retiran del Centro de actualizaciones.
