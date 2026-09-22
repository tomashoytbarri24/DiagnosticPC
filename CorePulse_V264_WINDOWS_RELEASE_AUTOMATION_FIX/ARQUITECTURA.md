# Arquitectura actual de CorePulse V264

V264 conserva la arquitectura Windows de V263. El único cambio funcional está en la capa de publicación/desarrollo: plantillas GitHub Actions V2 y detección de workflows legacy.

## Separación de responsabilidades

- CorePulse publica únicamente la carpeta de versión hacia la rama elegida.
- `.github` nunca se modifica desde la aplicación.
- GitHub Actions empaqueta el código, calcula SHA-256 y crea la Release.
- `maxi/corepulse-dev` produce prereleases `V###-dev`.
- `main` produce releases estables `V###`.
