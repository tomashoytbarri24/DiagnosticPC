CorePulse V0.10.2.96w - Windows Analysis Section Navigation

1. Ejecuta instalar_dependencias.bat
2. Ejecuta build_exe.bat
3. build_exe.bat NO da OK si CorePulse.exe falla el self-test interno.
4. Instala Inno Setup 6.
5. Ejecuta build_installer.bat

El PC destino NO necesita Python.
El instalador copia el bundle ONEDIR validado a LocalAppData\Programs\CorePulse.
Los datos del usuario, historiales, logs y snapshots quedan en AppData, fuera del bundle.

Externos por diseño: RTSS, PawnIO, Ookla CLI y GROQ_API_KEY. Su ausencia debe
degradar sólo la función afectada a N/A/NO DISPONIBLE.