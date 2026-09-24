CorePulse V118 - Build y pruebas de actualización

1. Ejecuta instalar_dependencias.bat si corresponde.
2. Ejecuta build_exe.bat.
3. Ejecuta build_installer.bat.

Los scripts leen core/version.py y generan CorePulse_Setup_V<version>.exe.
Para probar el actualizador interno publica una GitHub Release/Prerelease con tag V<version> y sube el instalador o ZIP. GitHub publica el digest SHA-256 del asset; CorePulse lo exige antes de abrir/preparar la actualización.
