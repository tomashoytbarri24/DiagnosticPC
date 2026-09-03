"""Motor reversible de Tweaks de Windows 11 para CorePulse.

V0.9.23.1w amplía el catálogo manteniendo una política conservadora:
- no descarga ni ejecuta scripts remotos;
- los tweaks de Registro guardan exactamente el valor previo por usuario/equipo;
- las acciones de PowerShell/WinGet declaran explícitamente si su reversión es definida;
- los cambios de seguridad o actualización nunca forman parte de presets automáticos;
- cada tweak expone riesgo, privilegios y necesidad de reinicio/Explorer.
"""
from __future__ import annotations

import ctypes
import getpass
import json
import os
import platform
import subprocess
import threading
import time
from pathlib import Path

try:
    import winreg  # type: ignore
except Exception:  # pragma: no cover - no existe fuera de Windows
    winreg = None

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = PROJECT_ROOT / 'data' / 'windows_tweaks_state.json'
HISTORY_PATH = PROJECT_ROOT / 'data' / 'windows_tweaks_history.jsonl'
_STATE_LOCK = threading.RLock()


def _tw(
    tweak_id, title, description, category, *, risk='Bajo', presets=(), ops=(),
    requires_explorer=False, requires_restart=False, requires_admin=False,
    ps_apply=None, ps_undo=None, ps_detect=None, undo_mode='exact', note=None,
):
    return {
        'id': tweak_id,
        'title': title,
        'description': description,
        'category': category,
        'risk': risk,
        'presets': tuple(presets),
        'ops': tuple(ops),
        'requires_explorer': bool(requires_explorer),
        'requires_restart': bool(requires_restart),
        'requires_admin': bool(requires_admin),
        'ps_apply': ps_apply,
        'ps_undo': ps_undo,
        'ps_detect': ps_detect,
        'undo_mode': undo_mode,
        'note': note,
    }


# Catálogo deliberadamente explícito. Los ajustes de riesgo Alto/Crítico NO están
# en presets. REG_DWORD se representa como "dword" y REG_SZ como "string".
TWEAKS = (
    # ------------------------------------------------------------------
    # EXPLORADOR
    # ------------------------------------------------------------------
    _tw('show_file_extensions', 'Mostrar extensiones de archivo',
        'Muestra .exe, .txt, .jpg y demás extensiones en el Explorador.', 'Explorador',
        presets=('minimal', 'recommended'), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'HideFileExt', 0, 'dword'),)),
    _tw('show_hidden_files', 'Mostrar archivos ocultos',
        'Permite visualizar archivos marcados como ocultos; no muestra archivos protegidos del sistema.', 'Explorador',
        presets=('recommended',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'Hidden', 1, 'dword'),)),
    _tw('open_this_pc', 'Abrir Explorador en Este equipo',
        'Hace que una nueva ventana del Explorador abra Este equipo en lugar de Inicio.', 'Explorador',
        presets=('recommended',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'LaunchTo', 1, 'dword'),)),
    _tw('hide_recent_quick_access', 'Ocultar archivos recientes en Inicio',
        'Evita que el Explorador liste archivos usados recientemente en la página Inicio.', 'Explorador',
        presets=('privacy',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer', 'ShowRecent', 0, 'dword'),)),
    _tw('hide_frequent_quick_access', 'Ocultar carpetas frecuentes en Inicio',
        'Evita que el Explorador muestre carpetas utilizadas con frecuencia.', 'Explorador',
        presets=('privacy',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer', 'ShowFrequent', 0, 'dword'),)),
    _tw('show_full_path_title', 'Mostrar ruta completa en el título',
        'Muestra la ruta completa de la carpeta en la barra de título del Explorador.', 'Explorador',
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\CabinetState', 'FullPath', 1, 'dword'),)),
    _tw('compact_explorer', 'Activar vista compacta del Explorador',
        'Reduce el espacio vertical entre archivos y carpetas.', 'Explorador',
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'UseCompactMode', 1, 'dword'),),
        requires_explorer=True),
    _tw('classic_context_menu', 'Menú contextual clásico',
        'Restaura el menú contextual clásico en Windows 11. Puede dejar de funcionar en builds futuras.', 'Explorador',
        risk='Medio', requires_explorer=True,
        ops=(('HKCU', r'Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32', '', '', 'string'),)),
    _tw('end_task_taskbar', 'Finalizar tarea desde la barra de tareas',
        'Activa “Finalizar tarea” al hacer clic derecho sobre una aplicación en la barra de tareas.', 'Explorador',
        presets=('recommended',),
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\TaskbarDeveloperSettings', 'TaskbarEndTask', 1, 'dword'),)),
    _tw('show_seconds_clock', 'Mostrar segundos en el reloj',
        'Muestra segundos en el reloj de la bandeja del sistema.', 'Explorador',
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'ShowSecondsInSystemClock', 1, 'dword'),),
        requires_explorer=True),

    # ------------------------------------------------------------------
    # BARRA DE TAREAS / INTERFAZ
    # ------------------------------------------------------------------
    _tw('disable_widgets', 'Ocultar Widgets de la barra de tareas',
        'Oculta el botón de Widgets sin desinstalar el paquete.', 'Barra de tareas',
        presets=('minimal', 'recommended', 'gaming'), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'TaskbarDa', 0, 'dword'),)),
    _tw('disable_chat', 'Ocultar Chat/Teams de la barra de tareas',
        'Oculta el acceso de Chat cuando existe en la build instalada.', 'Barra de tareas',
        presets=('recommended',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'TaskbarMn', 0, 'dword'),)),
    _tw('taskbar_left', 'Alinear barra de tareas a la izquierda',
        'Mueve Inicio y los iconos de la barra de tareas hacia la izquierda.', 'Barra de tareas',
        requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'TaskbarAl', 0, 'dword'),)),
    _tw('hide_taskbar_search', 'Ocultar búsqueda de la barra de tareas',
        'Oculta el cuadro/icono de búsqueda; Windows Search sigue disponible desde Inicio.', 'Barra de tareas',
        presets=('recommended',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Search', 'SearchboxTaskbarMode', 0, 'dword'),)),
    _tw('hide_task_view', 'Ocultar Vista de tareas',
        'Oculta el botón Vista de tareas sin desactivar escritorios virtuales.', 'Barra de tareas',
        requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'ShowTaskViewButton', 0, 'dword'),)),
    _tw('hide_copilot_button', 'Ocultar botón de Copilot',
        'Oculta el botón de Copilot cuando la build de Windows lo expone en la barra de tareas.', 'Barra de tareas',
        presets=('privacy',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'ShowCopilotButton', 0, 'dword'),)),
    _tw('disable_transparency', 'Desactivar transparencias',
        'Reduce efectos de transparencia en Inicio, barra de tareas y superficies compatibles.', 'Interfaz',
        presets=('performance',),
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize', 'EnableTransparency', 0, 'dword'),)),
    _tw('reduce_animations', 'Reducir animaciones de Windows',
        'Desactiva varias animaciones y sombras visuales para priorizar respuesta de interfaz.', 'Interfaz',
        risk='Medio', presets=('performance',), requires_explorer=True,
        ops=(
            ('HKCU', r'Control Panel\Desktop\WindowMetrics', 'MinAnimate', '0', 'string'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'TaskbarAnimations', 0, 'dword'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'ListviewAlphaSelect', 0, 'dword'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'ListviewShadow', 0, 'dword'),
        )),
    _tw('disable_aero_shake', 'Desactivar Aero Shake',
        'Evita minimizar las demás ventanas al agitar una ventana con el mouse.', 'Interfaz',
        presets=('recommended',),
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'DisallowShaking', 1, 'dword'),)),
    _tw('reduce_menu_delay', 'Reducir retardo de menús',
        'Reduce la demora de apertura de menús a 200 ms.', 'Interfaz',
        presets=('performance',),
        ops=(('HKCU', r'Control Panel\Desktop', 'MenuShowDelay', '200', 'string'),)),
    _tw('disable_startup_delay', 'Reducir retraso de apps al iniciar sesión',
        'Elimina el retardo artificial de inicio de algunas aplicaciones del usuario.', 'Interfaz',
        risk='Medio', presets=('performance',),
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize', 'StartupDelayInMSec', 0, 'dword'),)),
    _tw('dark_mode', 'Forzar modo oscuro de Windows',
        'Configura aplicaciones y sistema para usar el tema oscuro.', 'Interfaz',
        ops=(
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize', 'AppsUseLightTheme', 0, 'dword'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize', 'SystemUsesLightTheme', 0, 'dword'),
        )),
    _tw('disable_start_recommendations', 'Reducir recomendaciones de Inicio',
        'Desactiva recomendaciones dinámicas de contenido en el menú Inicio cuando la build respeta esta clave.', 'Interfaz',
        presets=('recommended', 'privacy'), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'Start_IrisRecommendations', 0, 'dword'),)),
    _tw('disable_lock_screen', 'Desactivar pantalla de bloqueo',
        'Omite la pantalla de bloqueo y pasa directamente a la pantalla de inicio de sesión.', 'Interfaz',
        risk='Medio', requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\Personalization', 'NoLockScreen', 1, 'dword'),)),

    # ------------------------------------------------------------------
    # PRIVACIDAD
    # ------------------------------------------------------------------
    _tw('disable_web_search', 'Desactivar resultados web en Inicio',
        'Evita sugerencias web/Bing en la búsqueda de Inicio sin desactivar Windows Search.', 'Privacidad',
        presets=('recommended', 'privacy'), requires_explorer=True,
        ops=(('HKCU', r'Software\Policies\Microsoft\Windows\Explorer', 'DisableSearchBoxSuggestions', 1, 'dword'),)),
    _tw('disable_advertising_id', 'Desactivar ID de publicidad',
        'Deshabilita el identificador de publicidad personalizado del usuario actual.', 'Privacidad',
        presets=('minimal', 'recommended', 'privacy'),
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo', 'Enabled', 0, 'dword'),)),
    _tw('disable_tailored_experiences', 'Desactivar experiencias personalizadas',
        'Evita recomendaciones personalizadas basadas en datos de diagnóstico.', 'Privacidad',
        presets=('recommended', 'privacy'),
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Privacy', 'TailoredExperiencesWithDiagnosticDataEnabled', 0, 'dword'),)),
    _tw('disable_sync_provider_ads', 'Desactivar anuncios del Explorador',
        'Oculta notificaciones promocionales del proveedor de sincronización.', 'Privacidad',
        presets=('recommended', 'privacy'), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'ShowSyncProviderNotifications', 0, 'dword'),)),
    _tw('disable_content_suggestions', 'Reducir sugerencias y contenido promocionado',
        'Desactiva varias suscripciones de sugerencias sin eliminar Microsoft Store.', 'Privacidad',
        presets=('recommended', 'privacy'), requires_explorer=True,
        ops=(
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager', 'SystemPaneSuggestionsEnabled', 0, 'dword'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager', 'SubscribedContent-338388Enabled', 0, 'dword'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager', 'SubscribedContent-338389Enabled', 0, 'dword'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager', 'SubscribedContent-353694Enabled', 0, 'dword'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager', 'SubscribedContent-353696Enabled', 0, 'dword'),
        )),
    _tw('disable_activity_history', 'Desactivar historial de actividad',
        'Impide publicar/subir el historial de actividad mediante políticas de Windows.', 'Privacidad',
        risk='Medio', presets=('privacy',), requires_admin=True,
        ops=(
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\System', 'EnableActivityFeed', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\System', 'PublishUserActivities', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\System', 'UploadUserActivities', 0, 'dword'),
        )),
    _tw('disable_telemetry', 'Reducir telemetría de Windows',
        'Solicita el nivel mínimo permitido por la edición instalada mediante política del sistema.', 'Privacidad',
        risk='Medio', presets=('privacy',), requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\DataCollection', 'AllowTelemetry', 0, 'dword'),)),
    _tw('disable_online_speech', 'Desactivar reconocimiento de voz en línea',
        'Deshabilita el consentimiento de reconocimiento de voz conectado para el usuario.', 'Privacidad',
        presets=('privacy',),
        ops=(('HKCU', r'Software\Microsoft\Speech_OneCore\Settings\OnlineSpeechPrivacy', 'HasAccepted', 0, 'dword'),)),
    _tw('disable_inking_typing', 'Reducir personalización de escritura y entrada',
        'Limita la recopilación implícita de texto/tinta usada para personalización.', 'Privacidad',
        presets=('privacy',),
        ops=(
            ('HKCU', r'Software\Microsoft\InputPersonalization', 'RestrictImplicitInkCollection', 1, 'dword'),
            ('HKCU', r'Software\Microsoft\InputPersonalization', 'RestrictImplicitTextCollection', 1, 'dword'),
            ('HKCU', r'Software\Microsoft\InputPersonalization\TrainedDataStore', 'HarvestContacts', 0, 'dword'),
        )),
    _tw('disable_feedback_prompts', 'Desactivar solicitudes de comentarios',
        'Reduce las solicitudes periódicas de feedback de Windows.', 'Privacidad',
        presets=('privacy',),
        ops=(('HKCU', r'Software\Microsoft\Siuf\Rules', 'NumberOfSIUFInPeriod', 0, 'dword'),)),
    _tw('disable_app_launch_tracking', 'Desactivar seguimiento de inicio de aplicaciones',
        'Evita que Windows rastree lanzamientos para personalizar Inicio y búsqueda.', 'Privacidad',
        presets=('privacy',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'Start_TrackProgs', 0, 'dword'),)),
    _tw('disable_location', 'Desactivar ubicación para el usuario',
        'Deniega el acceso a ubicación desde el almacén de consentimiento del usuario.', 'Privacidad',
        risk='Medio', presets=('privacy',),
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location', 'Value', 'Deny', 'string'),)),
    _tw('disable_error_reporting', 'Desactivar Windows Error Reporting',
        'Evita el envío automático de reportes de errores del usuario.', 'Privacidad',
        risk='Medio',
        ops=(('HKCU', r'Software\Microsoft\Windows\Windows Error Reporting', 'Disabled', 1, 'dword'),)),
    _tw('disable_copilot_policy', 'Desactivar Windows Copilot por política',
        'Solicita desactivar Windows Copilot mediante política del usuario cuando la build la respeta.', 'Privacidad',
        risk='Medio', presets=('privacy',), requires_explorer=True,
        ops=(('HKCU', r'Software\Policies\Microsoft\Windows\WindowsCopilot', 'TurnOffWindowsCopilot', 1, 'dword'),)),
    _tw('disable_recall', 'Desactivar Recall / AI Data Analysis',
        'Desactiva la política de análisis de datos de Windows AI/Recall cuando el componente existe.', 'Privacidad',
        risk='Medio', presets=('privacy',), requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\WindowsAI', 'DisableAIDataAnalysis', 1, 'dword'),)),
    _tw('disable_consumer_features', 'Desactivar Consumer Features',
        'Reduce instalaciones promocionadas y sugerencias de aplicaciones de Microsoft.', 'Privacidad',
        risk='Medio', presets=('recommended', 'privacy'), requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\CloudContent', 'DisableWindowsConsumerFeatures', 1, 'dword'),)),
    _tw('disable_delivery_optimization', 'Desactivar P2P de Delivery Optimization',
        'Evita usar ancho de banda para distribuir actualizaciones a otros equipos.', 'Privacidad',
        risk='Medio', presets=('recommended', 'privacy'), requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization', 'DODownloadMode', 0, 'dword'),)),

    # ------------------------------------------------------------------
    # GAMING / RENDIMIENTO
    # ------------------------------------------------------------------
    _tw('disable_mouse_acceleration', 'Desactivar aceleración del mouse',
        'Usa movimiento clásico sin Enhance Pointer Precision; útil para consistencia en juegos.', 'Gaming',
        presets=('gaming',),
        ops=(
            ('HKCU', r'Control Panel\Mouse', 'MouseSpeed', '0', 'string'),
            ('HKCU', r'Control Panel\Mouse', 'MouseThreshold1', '0', 'string'),
            ('HKCU', r'Control Panel\Mouse', 'MouseThreshold2', '0', 'string'),
        )),
    _tw('enable_game_mode', 'Mantener Modo Juego habilitado',
        'Solicita a Windows mantener Game Mode activo.', 'Gaming',
        presets=('gaming',),
        ops=(
            ('HKCU', r'Software\Microsoft\GameBar', 'AutoGameModeEnabled', 1, 'dword'),
            ('HKCU', r'Software\Microsoft\GameBar', 'AllowAutoGameMode', 1, 'dword'),
        )),
    _tw('disable_game_dvr', 'Desactivar Game DVR y capturas en segundo plano',
        'Desactiva captura/grabación de Game DVR. Puede afectar funciones de grabación de Xbox Game Bar.', 'Gaming',
        risk='Medio', presets=('gaming',),
        ops=(
            ('HKCU', r'System\GameConfigStore', 'GameDVR_Enabled', 0, 'dword'),
            ('HKCU', r'Software\Microsoft\Windows\CurrentVersion\GameDVR', 'AppCaptureEnabled', 0, 'dword'),
        )),
    _tw('disable_gamebar_startup', 'Reducir avisos de Xbox Game Bar',
        'Evita el panel de bienvenida/inicio automático de Game Bar sin desinstalarla.', 'Gaming',
        presets=('gaming',),
        ops=(('HKCU', r'Software\Microsoft\GameBar', 'ShowStartupPanel', 0, 'dword'),)),
    _tw('enable_hags', 'Activar Hardware-Accelerated GPU Scheduling',
        'Solicita HAGS. Sólo tiene efecto si GPU, driver y build lo soportan; requiere reinicio.', 'Gaming',
        risk='Medio', requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\GraphicsDrivers', 'HwSchMode', 2, 'dword'),)),
    _tw('disable_power_throttling', 'Desactivar Power Throttling global',
        'Reduce la limitación energética de procesos en segundo plano. Puede aumentar consumo y temperatura.', 'Gaming',
        risk='Medio', presets=('performance',), requires_admin=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\Power\PowerThrottling', 'PowerThrottlingOff', 1, 'dword'),)),

    # ------------------------------------------------------------------
    # ENERGÍA / SISTEMA / ACTUALIZACIONES
    # ------------------------------------------------------------------
    _tw('disable_hibernation', 'Desactivar hibernación',
        'Desactiva hibernación y libera hiberfil.sys. También puede deshabilitar Inicio rápido.', 'Energía',
        risk='Medio', requires_admin=True, requires_restart=True, undo_mode='defined',
        ops=(
            ('HKLM', r'SYSTEM\CurrentControlSet\Control\Session Manager\Power', 'HibernateEnabled', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FlyoutMenuSettings', 'ShowHibernateOption', 0, 'dword'),
        ),
        ps_apply="powercfg.exe /hibernate off; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
        ps_undo="powercfg.exe /hibernate on; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
        note='La reversión de la parte powercfg vuelve a habilitar hibernación; las claves de Registro sí recuperan su valor anterior.'),
    _tw('disable_fast_startup', 'Desactivar Inicio rápido',
        'Desactiva Fast Startup. Puede facilitar diagnósticos de drivers y dual boot.', 'Energía',
        risk='Medio', requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\Session Manager\Power', 'HiberbootEnabled', 0, 'dword'),)),
    _tw('disable_storage_sense', 'Desactivar Storage Sense',
        'Evita que Windows elimine automáticamente temporales según sus reglas de Storage Sense.', 'Sistema',
        risk='Medio',
        ops=(('HKCU', r'SOFTWARE\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy', '01', 0, 'dword'),)),
    _tw('enable_long_paths', 'Habilitar rutas Win32 largas',
        'Permite que aplicaciones compatibles utilicen rutas de más de 260 caracteres.', 'Sistema',
        presets=('recommended',), requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\FileSystem', 'LongPathsEnabled', 1, 'dword'),)),
    _tw('verbose_status', 'Mostrar mensajes detallados de inicio/apagado',
        'Muestra estados detallados durante inicio, cierre de sesión y apagado.', 'Sistema',
        requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System', 'VerboseStatus', 1, 'dword'),)),
    _tw('disable_remote_assistance', 'Desactivar Asistencia remota',
        'Impide invitaciones de Windows Remote Assistance. No desactiva Escritorio remoto (RDP).', 'Sistema',
        risk='Medio', requires_admin=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\Remote Assistance', 'fAllowToGetHelp', 0, 'dword'),)),
    _tw('exclude_driver_updates', 'Excluir drivers de Windows Update',
        'Evita que las actualizaciones de calidad incluyan controladores. Deberás gestionarlos por separado.', 'Actualizaciones',
        risk='Medio', requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate', 'ExcludeWUDriversInQualityUpdate', 1, 'dword'),)),
    _tw('no_auto_reboot_updates', 'Evitar reinicio automático con sesión iniciada',
        'Solicita a Windows Update no reiniciar automáticamente mientras haya un usuario conectado.', 'Actualizaciones',
        risk='Medio', requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU', 'NoAutoRebootWithLoggedOnUsers', 1, 'dword'),)),
    _tw('disable_auto_updates', 'Desactivar actualizaciones automáticas',
        'Desactiva la búsqueda/instalación automática mediante política. Aumenta el riesgo de quedar sin parches.', 'Actualizaciones',
        risk='Alto', requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU', 'NoAutoUpdate', 1, 'dword'),),
        note='No se incluye en ningún preset. CorePulse recomienda mantener actualizaciones de seguridad.'),

    # ------------------------------------------------------------------
    # RED
    # ------------------------------------------------------------------
    _tw('disable_llmnr', 'Desactivar LLMNR',
        'Deshabilita resolución de nombres multicast LLMNR. Puede mejorar privacidad/seguridad en redes administradas.', 'Red',
        risk='Medio', requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows NT\DNSClient', 'EnableMulticast', 0, 'dword'),)),

    # ------------------------------------------------------------------
    # APPS / DEBLOAT
    # ------------------------------------------------------------------
    _tw('edge_debloat', 'Microsoft Edge: reducir promociones y telemetría',
        'Aplica políticas para reducir recomendaciones, shopping, rewards, feedback y contenido promocional de Edge.', 'Apps y debloat',
        risk='Medio', requires_admin=True,
        ops=(
            ('HKLM', r'SOFTWARE\Policies\Microsoft\EdgeUpdate', 'CreateDesktopShortcutDefault', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'PersonalizationReportingEnabled', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'ShowRecommendationsEnabled', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'HideFirstRunExperience', 1, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'UserFeedbackAllowed', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'ConfigureDoNotTrack', 1, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'AlternateErrorPagesEnabled', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'EdgeCollectionsEnabled', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'EdgeShoppingAssistantEnabled', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'ShowMicrosoftRewards', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'WebWidgetAllowed', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'DiagnosticData', 0, 'dword'),
        )),
    _tw('remove_edge', 'Desinstalar Microsoft Edge',
        'Intenta desinstalar Edge a nivel de sistema conservando WebView2 Runtime y el perfil del usuario.', 'Apps y debloat',
        risk='Alto', requires_admin=True, undo_mode='defined',
        ps_detect=r"$a=Test-Path \"${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe\"; $b=Test-Path \"$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe\"; if($a -or $b){'0'}else{'1'}",
        ps_apply=r"$base=\"${env:ProgramFiles(x86)}\Microsoft\Edge\Application\"; $setup=Get-ChildItem -Path $base -Filter setup.exe -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1; if(-not $setup){exit 0}; $legacy=Join-Path $env:SystemRoot 'SystemApps\Microsoft.MicrosoftEdge_8wekyb3d8bbwe'; New-Item -ItemType Directory -Path $legacy -Force | Out-Null; New-Item -ItemType File -Path (Join-Path $legacy 'MicrosoftEdge.exe') -Force | Out-Null; $p=Start-Process -FilePath $setup.FullName -ArgumentList '--uninstall','--system-level','--force-uninstall' -Wait -PassThru; exit $p.ExitCode",
        ps_undo=r"winget install --id Microsoft.Edge --exact --accept-package-agreements --accept-source-agreements --silent; exit $LASTEXITCODE",
        note='WebView2 Runtime no se elimina. Windows Update puede volver a instalar Edge en algunas configuraciones.'),
    _tw('remove_onedrive', 'Desinstalar Microsoft OneDrive',
        'Ejecuta el desinstalador oficial de OneDrive sin borrar manualmente la carpeta de archivos sincronizados.', 'Apps y debloat',
        risk='Alto', requires_admin=True, undo_mode='defined',
        ps_detect=r"$p1=Test-Path \"$env:LOCALAPPDATA\Microsoft\OneDrive\OneDrive.exe\"; $p2=Test-Path \"$env:ProgramFiles\Microsoft OneDrive\OneDrive.exe\"; $p3=Test-Path \"${env:ProgramFiles(x86)}\Microsoft OneDrive\OneDrive.exe\"; if($p1 -or $p2 -or $p3){'0'}else{'1'}",
        ps_apply=r"Stop-Process -Name OneDrive -Force -ErrorAction SilentlyContinue; $s1=Join-Path $env:SystemRoot 'SysWOW64\OneDriveSetup.exe'; $s2=Join-Path $env:SystemRoot 'System32\OneDriveSetup.exe'; $setup=if(Test-Path $s1){$s1}elseif(Test-Path $s2){$s2}else{$null}; if(-not $setup){exit 2}; $p=Start-Process -FilePath $setup -ArgumentList '/uninstall' -Wait -PassThru; exit $p.ExitCode",
        ps_undo=r"winget install --id Microsoft.OneDrive --exact --accept-package-agreements --accept-source-agreements --silent; exit $LASTEXITCODE",
        note='CorePulse no elimina la carpeta OneDrive ni archivos personales; la reinstalación usa WinGet.'),
    _tw('remove_widgets_package', 'Desinstalar Windows Web Experience / Widgets',
        'Elimina el paquete que alimenta Widgets. Puede afectar funciones que dependan de Windows Web Experience Pack.', 'Apps y debloat',
        risk='Alto', requires_admin=True, requires_explorer=True, undo_mode='defined',
        ps_detect=r"$p=Get-AppxPackage MicrosoftWindows.Client.WebExperience -AllUsers -ErrorAction SilentlyContinue; if($null -eq $p){'1'}else{'0'}",
        ps_apply=r"Get-Process *Widget* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; Get-AppxPackage MicrosoftWindows.Client.WebExperience -AllUsers -ErrorAction SilentlyContinue | Remove-AppxPackage -AllUsers -ErrorAction Stop",
        ps_undo=r"winget install --id 9MSSGKG348SP --source msstore --accept-package-agreements --accept-source-agreements; exit $LASTEXITCODE",
        note='La reversión reinstala Windows Web Experience Pack desde Microsoft Store mediante WinGet.'),

    # ------------------------------------------------------------------
    # SEGURIDAD AVANZADA — nunca en presets
    # ------------------------------------------------------------------
    _tw('disable_defender_stack', 'Desactivar protecciones de Microsoft Defender',
        'Intenta desactivar protección en tiempo real, comportamiento, IOAV, scripts, nube y envío de muestras. Tamper Protection puede bloquearlo.', 'Seguridad avanzada',
        risk='Crítico', requires_admin=True, undo_mode='defined',
        ps_detect=r"$p=Get-MpPreference -ErrorAction SilentlyContinue; if($p -and $p.DisableRealtimeMonitoring -and $p.DisableBehaviorMonitoring -and $p.DisableIOAVProtection -and $p.DisableScriptScanning){'1'}else{'0'}",
        ps_apply=r"Set-MpPreference -DisableRealtimeMonitoring $true -DisableBehaviorMonitoring $true -DisableBlockAtFirstSeen $true -DisableIOAVProtection $true -DisableScriptScanning $true -MAPSReporting 0 -SubmitSamplesConsent 2 -ErrorAction Stop",
        ps_undo=r"Set-MpPreference -DisableRealtimeMonitoring $false -DisableBehaviorMonitoring $false -DisableBlockAtFirstSeen $false -DisableIOAVProtection $false -DisableScriptScanning $false -MAPSReporting 2 -SubmitSamplesConsent 1 -ErrorAction Stop",
        note='No elimina binarios de Defender. La reversión vuelve a valores de protección comunes, no puede restaurar una política corporativa desconocida.'),
    _tw('disable_smartscreen', 'Desactivar Microsoft Defender SmartScreen',
        'Desactiva SmartScreen por política. Reduce protección contra descargas/sitios potencialmente maliciosos.', 'Seguridad avanzada',
        risk='Crítico', requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\System', 'EnableSmartScreen', 0, 'dword'),)),
    _tw('disable_uac', 'Desactivar UAC',
        'Desactiva User Account Control. Reduce significativamente el aislamiento de privilegios y requiere reinicio.', 'Seguridad avanzada',
        risk='Crítico', requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System', 'EnableLUA', 0, 'dword'),)),
    _tw('disable_memory_integrity', 'Desactivar Integridad de memoria (HVCI)',
        'Desactiva Hypervisor-Enforced Code Integrity. Puede mejorar compatibilidad/rendimiento a costa de seguridad.', 'Seguridad avanzada',
        risk='Alto', requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity', 'Enabled', 0, 'dword'),)),
    _tw('disable_vbs', 'Desactivar Virtualization-Based Security (VBS)',
        'Solicita desactivar VBS. Puede afectar Credential Guard y otras protecciones; requiere reinicio.', 'Seguridad avanzada',
        risk='Alto', requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\DeviceGuard', 'EnableVirtualizationBasedSecurity', 0, 'dword'),)),
)

PRESETS = {
    'minimal': 'Minimal',
    'recommended': 'Recomendado',
    'privacy': 'Privacidad',
    'gaming': 'Gaming',
    'performance': 'Rendimiento',
    'advanced': 'Avanzado seguro',
}

# El preset avanzado sólo recoge tweaks de riesgo Bajo/Medio sin tocar seguridad,
# Update automático ni desinstalaciones de componentes.
_ADVANCED_SAFE_IDS = {
    'classic_context_menu', 'show_seconds_clock', 'disable_transparency', 'reduce_animations',
    'reduce_menu_delay', 'disable_startup_delay', 'disable_lock_screen', 'disable_error_reporting',
    'enable_hags', 'disable_power_throttling', 'disable_fast_startup', 'disable_storage_sense',
    'verbose_status', 'disable_remote_assistance', 'exclude_driver_updates', 'no_auto_reboot_updates',
    'disable_llmnr', 'edge_debloat',
}

CATEGORY_ORDER = (
    'Explorador', 'Barra de tareas', 'Interfaz', 'Privacidad', 'Gaming', 'Energía',
    'Sistema', 'Actualizaciones', 'Red', 'Apps y debloat', 'Seguridad avanzada',
)


def catalog():
    return tuple(dict(item) for item in TWEAKS)


def _tweak_by_id(tweak_id):
    for item in TWEAKS:
        if item['id'] == tweak_id:
            return item
    return None


def is_windows_11():
    if platform.system() != 'Windows':
        return False
    try:
        return int(platform.version().split('.')[2]) >= 22000
    except Exception:
        return platform.release() == '11'


def is_admin():
    if platform.system() != 'Windows':
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def environment_info():
    build = None
    try:
        build = int(platform.version().split('.')[2]) if platform.system() == 'Windows' else None
    except Exception:
        pass
    return {
        'supported': is_windows_11(),
        'windows': platform.system() == 'Windows',
        'build': build,
        'admin': is_admin(),
        'user': getpass.getuser(),
    }


def preset_ids(name):
    key = str(name or '').strip().lower()
    if key == 'advanced':
        return tuple(item['id'] for item in TWEAKS if item['id'] in _ADVANCED_SAFE_IDS)
    return tuple(item['id'] for item in TWEAKS if key in item.get('presets', ()))


def selected_metadata(ids):
    rows = [item for item in TWEAKS if item['id'] in set(ids or ())]
    risk_rank = {'Bajo': 0, 'Medio': 1, 'Alto': 2, 'Crítico': 3}
    highest = max((risk_rank.get(row.get('risk'), 0) for row in rows), default=0)
    return {
        'requires_admin': any(row.get('requires_admin') for row in rows),
        'requires_restart': any(row.get('requires_restart') for row in rows),
        'requires_explorer': any(row.get('requires_explorer') for row in rows),
        'high_risk': [row for row in rows if risk_rank.get(row.get('risk'), 0) >= 2],
        'critical': [row for row in rows if risk_rank.get(row.get('risk'), 0) >= 3],
        'highest_risk': highest,
    }


def _hive(name):
    if winreg is None:
        raise RuntimeError('Registro de Windows no disponible en este sistema.')
    table = {'HKCU': winreg.HKEY_CURRENT_USER, 'HKLM': winreg.HKEY_LOCAL_MACHINE}
    if name not in table:
        raise ValueError(f'Hive no soportado: {name}')
    return table[name]


def _reg_type(kind):
    if winreg is None:
        raise RuntimeError('Registro de Windows no disponible.')
    table = {
        'dword': winreg.REG_DWORD,
        'qword': getattr(winreg, 'REG_QWORD', winreg.REG_DWORD),
        'string': winreg.REG_SZ,
    }
    return table.get(kind, winreg.REG_SZ)


def _read_value(hive_name, path, name):
    root = _hive(hive_name)
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            value, reg_type = winreg.QueryValueEx(key, name)
            return True, value, reg_type
    except (FileNotFoundError, OSError):
        return False, None, None


def _write_value(hive_name, path, name, value, kind):
    root = _hive(hive_name)
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, _reg_type(kind), value)


def _delete_value(hive_name, path, name):
    root = _hive(hive_name)
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except (FileNotFoundError, OSError):
        pass


def _equal(current, desired, kind):
    if kind in ('dword', 'qword'):
        try:
            return int(current) == int(desired)
        except Exception:
            return False
    return str(current) == str(desired)


def _run_powershell(script, timeout=45):
    if platform.system() != 'Windows':
        return {'success': False, 'returncode': -1, 'stdout': '', 'stderr': 'PowerShell sólo está disponible en Windows.'}
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        proc = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', str(script)],
            capture_output=True, text=True, timeout=timeout, creationflags=flags,
        )
        return {
            'success': proc.returncode == 0,
            'returncode': proc.returncode,
            'stdout': (proc.stdout or '').strip(),
            'stderr': (proc.stderr or '').strip(),
        }
    except Exception as exc:
        return {'success': False, 'returncode': -1, 'stdout': '', 'stderr': str(exc)}


def _detect_ps(script):
    result = _run_powershell(script, timeout=20)
    if not result['success']:
        return None, result.get('stderr') or result.get('stdout') or 'No se pudo consultar el estado.'
    lines = [line.strip() for line in result.get('stdout', '').splitlines() if line.strip()]
    if not lines:
        return None, 'La detección no devolvió un valor.'
    value = lines[-1].lower()
    if value in ('1', 'true', 'applied', 'yes'):
        return True, ''
    if value in ('0', 'false', 'not_applied', 'no'):
        return False, ''
    return None, f'Respuesta de detección no reconocida: {lines[-1]}'


def detect_tweak(tweak_id):
    tweak = _tweak_by_id(tweak_id)
    if not tweak:
        return {'id': tweak_id, 'status': 'unknown', 'applied': False, 'detail': 'Tweak desconocido'}
    if not is_windows_11():
        return {'id': tweak_id, 'status': 'unavailable', 'applied': False, 'detail': 'Disponible sólo en Windows 11'}

    checks = []
    for hive_name, path, name, desired, kind in tweak.get('ops', ()):
        exists, value, _ = _read_value(hive_name, path, name)
        checks.append(bool(exists and _equal(value, desired, kind)))

    ps_detect = tweak.get('ps_detect')
    ps_value = None
    ps_detail = ''
    if ps_detect:
        ps_value, ps_detail = _detect_ps(ps_detect)
        if ps_value is not None:
            checks.append(bool(ps_value))

    if checks and all(checks):
        status = 'applied'
    elif any(checks):
        status = 'partial'
    elif checks:
        status = 'not_applied'
    elif tweak.get('ps_apply'):
        status = 'action'
    else:
        status = 'not_applied'
    return {'id': tweak_id, 'status': status, 'applied': status == 'applied', 'detail': ps_detail or status}


def detect_all():
    return {item['id']: detect_tweak(item['id']) for item in TWEAKS}


def _default_state():
    return {
        'schema': 2,
        'user': getpass.getuser(),
        'computer': platform.node(),
        'tweaks': {},
    }


def _load_state():
    with _STATE_LOCK:
        try:
            data = json.loads(STATE_PATH.read_text(encoding='utf-8'))
            if isinstance(data, dict) and isinstance(data.get('tweaks'), dict):
                return data
        except Exception:
            pass
        return _default_state()


def _save_state(data):
    with _STATE_LOCK:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp = STATE_PATH.with_suffix('.tmp')
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        temp.replace(STATE_PATH)


def _audit(tweak_id, action, success, message=''):
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {
            'timestamp': time.time(), 'user': getpass.getuser(), 'computer': platform.node(),
            'tweak_id': tweak_id, 'action': action, 'success': bool(success), 'message': str(message or '')[:800],
        }
        with HISTORY_PATH.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    except Exception:
        pass


def has_saved_original(tweak_id):
    state = _load_state()
    return (
        tweak_id in (state.get('tweaks') or {})
        and state.get('user') == getpass.getuser()
        and state.get('computer') == platform.node()
    )


def _save_original_if_needed(state, tweak):
    tweak_id = tweak['id']
    if tweak_id in state['tweaks']:
        return
    originals = []
    for hive_name, path, name, desired, kind in tweak.get('ops', ()):
        exists, value, reg_type = _read_value(hive_name, path, name)
        originals.append({
            'hive': hive_name, 'path': path, 'name': name, 'existed': exists,
            'value': value, 'reg_type': reg_type,
        })
    state['tweaks'][tweak_id] = {
        'saved_at': time.time(),
        'originals': originals,
        'undo_mode': tweak.get('undo_mode', 'exact'),
        'has_command': bool(tweak.get('ps_apply')),
    }
    _save_state(state)


def apply_tweak(tweak_id):
    tweak = _tweak_by_id(tweak_id)
    if not tweak:
        return {'success': False, 'id': tweak_id, 'message': 'Tweak desconocido.'}
    if not is_windows_11():
        return {'success': False, 'id': tweak_id, 'message': 'Esta función requiere Windows 11.'}
    if tweak.get('requires_admin') and not is_admin():
        return {'success': False, 'id': tweak_id, 'message': 'Este tweak requiere ejecutar CorePulse como administrador.'}

    detected = detect_tweak(tweak_id)
    if detected['applied'] and not has_saved_original(tweak_id):
        return {
            'success': True, 'id': tweak_id, 'changed': False,
            'message': 'Ya estaba aplicado antes de CorePulse.',
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }

    state = _load_state()
    if state.get('user') != getpass.getuser() or state.get('computer') != platform.node():
        state = _default_state()

    try:
        _save_original_if_needed(state, tweak)
        for hive_name, path, name, desired, kind in tweak.get('ops', ()):
            _write_value(hive_name, path, name, desired, kind)

        if tweak.get('ps_apply'):
            result = _run_powershell(tweak['ps_apply'])
            if not result['success']:
                message = result.get('stderr') or result.get('stdout') or f"PowerShell devolvió {result.get('returncode')}"
                _audit(tweak_id, 'apply', False, message)
                return {
                    'success': False, 'id': tweak_id, 'message': message,
                    'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
                }

        final = detect_tweak(tweak_id)
        # Acciones sin detector se consideran correctas si el comando terminó bien.
        success = final.get('status') in ('applied', 'action')
        message = 'Aplicado correctamente.' if success else 'Windows no confirmó todos los cambios.'
        _audit(tweak_id, 'apply', success, message)
        return {
            'success': success, 'id': tweak_id, 'changed': True, 'message': message,
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }
    except Exception as exc:
        _audit(tweak_id, 'apply', False, str(exc))
        return {
            'success': False, 'id': tweak_id, 'message': str(exc),
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }


def undo_tweak(tweak_id):
    tweak = _tweak_by_id(tweak_id)
    if not tweak:
        return {'success': False, 'id': tweak_id, 'message': 'Tweak desconocido.'}
    if not is_windows_11():
        return {'success': False, 'id': tweak_id, 'message': 'Esta función requiere Windows 11.'}
    if tweak.get('requires_admin') and not is_admin():
        return {'success': False, 'id': tweak_id, 'message': 'Este tweak requiere ejecutar CorePulse como administrador.'}

    state = _load_state()
    if state.get('user') != getpass.getuser() or state.get('computer') != platform.node():
        return {'success': False, 'id': tweak_id, 'message': 'El estado guardado pertenece a otro usuario o equipo.'}
    record = (state.get('tweaks') or {}).get(tweak_id)
    if not isinstance(record, dict):
        return {'success': False, 'id': tweak_id, 'message': 'CorePulse no tiene una reversión guardada para este tweak.'}

    try:
        command_error = None
        if tweak.get('ps_undo'):
            result = _run_powershell(tweak['ps_undo'])
            if not result['success']:
                command_error = result.get('stderr') or result.get('stdout') or f"PowerShell devolvió {result.get('returncode')}"

        for original in record.get('originals', []):
            hive_name = original['hive']; path = original['path']; name = original['name']
            if original.get('existed'):
                root = _hive(hive_name)
                with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, name, 0, int(original.get('reg_type') or winreg.REG_SZ), original.get('value'))
            else:
                _delete_value(hive_name, path, name)

        if command_error:
            _audit(tweak_id, 'undo', False, command_error)
            return {
                'success': False, 'id': tweak_id, 'message': command_error,
                'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
            }

        del state['tweaks'][tweak_id]
        _save_state(state)
        label = 'Valor previo restaurado.' if tweak.get('undo_mode') == 'exact' else 'Reversión definida ejecutada.'
        _audit(tweak_id, 'undo', True, label)
        return {
            'success': True, 'id': tweak_id, 'message': label,
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }
    except Exception as exc:
        _audit(tweak_id, 'undo', False, str(exc))
        return {
            'success': False, 'id': tweak_id, 'message': str(exc),
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }


def apply_many(ids):
    return [apply_tweak(tweak_id) for tweak_id in ids]


def undo_many(ids):
    return [undo_tweak(tweak_id) for tweak_id in ids]


def create_restore_point(description='CorePulse - antes de Tweaks'):
    """Crea un punto de restauración si Windows/privilegios/configuración lo permiten."""
    if not is_windows_11():
        return {'success': False, 'message': 'Requiere Windows 11.'}
    if not is_admin():
        return {'success': False, 'message': 'Requiere ejecutar CorePulse como administrador.'}
    command = [
        'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        f"Checkpoint-Computer -Description '{description.replace(chr(39), '')}' -RestorePointType 'MODIFY_SETTINGS'",
    ]
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, timeout=45,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if proc.returncode == 0:
            return {'success': True, 'message': 'Punto de restauración creado.'}
        detail = (proc.stderr or proc.stdout or '').strip()
        return {'success': False, 'message': detail or f'PowerShell devolvió código {proc.returncode}.'}
    except Exception as exc:
        return {'success': False, 'message': str(exc)}


def restart_explorer():
    """Reinicia Explorer sólo cuando el usuario lo solicita explícitamente."""
    if platform.system() != 'Windows':
        return {'success': False, 'message': 'Disponible sólo en Windows.'}
    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.run(['taskkill', '/F', '/IM', 'explorer.exe'], capture_output=True, timeout=10, creationflags=flags)
        subprocess.Popen(['explorer.exe'], creationflags=flags)
        return {'success': True, 'message': 'Explorador reiniciado.'}
    except Exception as exc:
        return {'success': False, 'message': str(exc)}
