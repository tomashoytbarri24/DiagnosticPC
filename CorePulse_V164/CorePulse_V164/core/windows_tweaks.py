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
import csv
import getpass
import json
import os
import platform
import subprocess
import threading
import time
import sys
import uuid
from pathlib import Path
from collections import deque
from core.runtime_paths import executable_root, is_frozen, source_root, state_dir

try:
    import winreg  # type: ignore
except Exception:  # pragma: no cover - no existe fuera de Windows
    winreg = None

PROJECT_ROOT = source_root()
LEGACY_STATE_PATH = PROJECT_ROOT / 'data' / 'windows_tweaks_state.json'
LEGACY_HISTORY_PATH = PROJECT_ROOT / 'data' / 'windows_tweaks_history.jsonl'


def _persistent_data_dir():
    """Ruta durable y compartida por modo fuente/EXE."""
    return state_dir()


PERSISTENT_DATA_DIR = _persistent_data_dir()
STATE_PATH = PERSISTENT_DATA_DIR / 'windows_tweaks_state.json'
STATE_BACKUP_PATH = PERSISTENT_DATA_DIR / 'windows_tweaks_state.backup.json'
HISTORY_PATH = PERSISTENT_DATA_DIR / 'windows_tweaks_history.jsonl'
_STATE_LOCK = threading.RLock()
_MIGRATION_DONE = False

# Contrato de rollback V0.10.2.23w:
# CorePulse no aplica acciones destructivas cuyo estado anterior no pueda
# reconstruirse de forma determinista. Los snapshots antiguos sí pueden
# intentar su reversión definida para no abandonar cambios de builds previas.
_NON_GUARANTEED_NEW_APPLY = {
    'remove_edge', 'remove_onedrive', 'remove_widgets_package',
}
_COMMAND_SNAPSHOT_SUPPORTED = {
    'disable_hibernation', 'disable_defender_stack',
}



def _tw(
    tweak_id, title, description, category, *, risk='Bajo', presets=(), ops=(),
    requires_explorer=False, requires_restart=False, requires_admin=False,
    ps_apply=None, ps_undo=None, ps_detect=None, undo_mode='exact', note=None,
    edition_scope=None, min_build=None,
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
        'edition_scope': edition_scope,
        'min_build': min_build,
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

    _tw('disable_taskbar_window_sharing', 'Desactivar compartir ventana desde la barra de tareas',
        'Desactiva la integración de compartir ventanas desde la barra de tareas. Reduce una integración del shell que no todos usan.', 'Interfaz',
        presets=('performance',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'TaskbarSn', 0, 'dword'),)),
    _tw('disable_account_notifications_start', 'Ocultar avisos de cuenta en Inicio',
        'Evita avisos de cuenta, copia de seguridad y suscripciones en el menú Inicio. No desactiva notificaciones normales de aplicaciones.', 'Interfaz',
        presets=('privacy',),
        ops=(('HKCU', r'SOFTWARE\Policies\Microsoft\Windows\CurrentVersion\AccountNotifications', 'DisableAccountNotifications', 1, 'dword'),)),

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

    _tw('disable_clipboard_history', 'Desactivar historial del portapapeles',
        'Desactiva Win+V y evita que Windows mantenga un historial de elementos copiados.', 'Privacidad',
        risk='Medio', requires_admin=True, edition_scope='pro_plus',
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\System', 'AllowClipboardHistory', 0, 'dword'),),
        note='Disponible cuando la edición de Windows admite esta directiva. CorePulse lo marca N/A en ediciones no compatibles.'),
    _tw('disable_cross_device_clipboard', 'Desactivar sincronización del portapapeles',
        'Impide sincronizar el portapapeles entre dispositivos asociados a la misma cuenta.', 'Privacidad',
        risk='Medio', requires_admin=True, edition_scope='pro_plus',
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\System', 'AllowCrossDeviceClipboard', 0, 'dword'),),
        note='No elimina el portapapeles local; sólo desactiva su sincronización entre dispositivos.'),
    _tw('disable_recent_documents_tracking', 'Desactivar seguimiento de documentos recientes',
        'Evita que Windows mantenga listas de documentos recientes para Inicio y Jump Lists. Puede reducir comodidad en accesos recientes.', 'Privacidad',
        risk='Medio', presets=('privacy',), requires_explorer=True,
        ops=(('HKCU', r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced', 'Start_TrackDocs', 0, 'dword'),)),
    _tw('disable_search_location', 'Evitar que Windows Search use ubicación',
        'Impide que Windows Search use la ubicación para personalizar resultados.', 'Privacidad',
        risk='Medio', requires_admin=True, edition_scope='pro_plus',
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\Windows Search', 'AllowSearchToUseLocation', 0, 'dword'),)),

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
    _tw('disable_gamebar_controller_launch', 'Evitar que el mando abra Xbox Game Bar',
        'Desactiva el atajo que permite al botón Xbox/Nexus del controlador abrir Game Bar.', 'Gaming',
        presets=('gaming',),
        ops=(('HKCU', r'Software\Microsoft\GameBar', 'UseNexusForGameBarEnabled', 0, 'dword'),)),
    _tw('disable_game_dvr_policy', 'Bloquear Game DVR por política',
        'Desactiva grabación y difusión de juegos mediante la política oficial de Windows. Útil si no utilizas capturas de Xbox Game Bar.', 'Gaming',
        risk='Medio', requires_admin=True, edition_scope='pro_plus',
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\GameDVR', 'AllowGameDVR', 0, 'dword'),),
        note='Más estricto que el ajuste de usuario. No se incluye en presets porque la disponibilidad depende de la edición de Windows.'),
    _tw('enable_hags', 'Activar Hardware-Accelerated GPU Scheduling',
        'Solicita HAGS. Sólo tiene efecto si GPU, driver y build lo soportan; requiere reinicio.', 'Gaming',
        risk='Medio', requires_admin=True, requires_restart=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\GraphicsDrivers', 'HwSchMode', 2, 'dword'),)),
    _tw('disable_power_throttling', 'Desactivar Power Throttling global',
        'Reduce la limitación energética de procesos en segundo plano. Puede aumentar consumo y temperatura.', 'Gaming',
        risk='Medio', presets=('performance',), requires_admin=True,
        ops=(('HKLM', r'SYSTEM\CurrentControlSet\Control\Power\PowerThrottling', 'PowerThrottlingOff', 1, 'dword'),)),

    # ------------------------------------------------------------------
    # RENDIMIENTO / SEGUNDO PLANO
    # ------------------------------------------------------------------
    _tw('disable_edge_startup_boost', 'Desactivar Startup Boost de Microsoft Edge',
        'Evita que Edge mantenga procesos preparados desde el inicio de sesión. Edge puede tardar ligeramente más en su primer arranque.', 'Rendimiento',
        presets=('performance',), requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'StartupBoostEnabled', 0, 'dword'),)),
    _tw('disable_edge_background_mode', 'Cerrar procesos de Edge al cerrar el navegador',
        'Evita que Edge continúe ejecutando extensiones y aplicaciones en segundo plano después de cerrar la última ventana.', 'Rendimiento',
        risk='Medio', presets=('performance',), requires_admin=True,
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Edge', 'BackgroundModeEnabled', 0, 'dword'),),
        note='Puede detener notificaciones o tareas de extensiones/web apps cuando Edge esté cerrado.'),
    _tw('disable_windows_background_apps', 'Bloquear apps de Windows en segundo plano',
        'Fuerza a las apps de Windows compatibles a no ejecutar actividad en segundo plano. Puede reducir actividad ociosa, pero también notificaciones y sincronización.', 'Rendimiento',
        risk='Medio', requires_admin=True, requires_restart=True, edition_scope='pro_plus',
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\AppPrivacy', 'LetAppsRunInBackground', 2, 'dword'),),
        note='No se incluye en presets. Apps de correo, mensajería y otras pueden dejar de sincronizar o notificar en segundo plano.'),
    _tw('disable_search_highlights', 'Desactivar Search Highlights',
        'Desactiva contenido dinámico y destacados en Windows Search para reducir contenido conectado dentro de la búsqueda.', 'Rendimiento',
        requires_admin=True, requires_explorer=True, edition_scope='pro_plus',
        ops=(('HKLM', r'SOFTWARE\Policies\Microsoft\Windows\Windows Search', 'EnableDynamicContentInWSB', 0, 'dword'),),
        note='CorePulse sólo lo ofrece como disponible en ediciones donde Microsoft documenta esta directiva.'),

    # ------------------------------------------------------------------
    # ENERGÍA / SISTEMA / ACTUALIZACIONES
    # ------------------------------------------------------------------
    _tw('disable_hibernation', 'Desactivar hibernación',
        'Desactiva hibernación y libera hiberfil.sys. También puede deshabilitar Inicio rápido.', 'Energía',
        risk='Medio', requires_admin=True, requires_restart=True, undo_mode='exact',
        ops=(
            ('HKLM', r'SYSTEM\CurrentControlSet\Control\Session Manager\Power', 'HibernateEnabled', 0, 'dword'),
            ('HKLM', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FlyoutMenuSettings', 'ShowHibernateOption', 0, 'dword'),
        ),
        ps_apply="powercfg.exe /hibernate off; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
        ps_undo="powercfg.exe /hibernate on; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
        note='CorePulse captura el estado previo y restaura hibernación al estado exacto que tenía antes del tweak.'),
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
        risk='Crítico', requires_admin=True, undo_mode='exact',
        ps_detect=r"$p=Get-MpPreference -ErrorAction SilentlyContinue; if($p -and $p.DisableRealtimeMonitoring -and $p.DisableBehaviorMonitoring -and $p.DisableIOAVProtection -and $p.DisableScriptScanning){'1'}else{'0'}",
        ps_apply=r"Set-MpPreference -DisableRealtimeMonitoring $true -DisableBehaviorMonitoring $true -DisableBlockAtFirstSeen $true -DisableIOAVProtection $true -DisableScriptScanning $true -MAPSReporting 0 -SubmitSamplesConsent 2 -ErrorAction Stop",
        ps_undo=r"Set-MpPreference -DisableRealtimeMonitoring $false -DisableBehaviorMonitoring $false -DisableBlockAtFirstSeen $false -DisableIOAVProtection $false -DisableScriptScanning $false -MAPSReporting 2 -SubmitSamplesConsent 1 -ErrorAction Stop",
        note='No elimina binarios de Defender. CorePulse captura y restaura exactamente las preferencias que modifica antes de aplicar el tweak.'),
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
    'disable_llmnr', 'edge_debloat', 'disable_gamebar_controller_launch',
    'disable_edge_startup_boost', 'disable_edge_background_mode',
    'disable_taskbar_window_sharing', 'disable_recent_documents_tracking', 'disable_account_notifications_start',
}

CATEGORY_ORDER = (
    'Explorador', 'Barra de tareas', 'Interfaz', 'Privacidad', 'Gaming', 'Rendimiento', 'Energía',
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


def _current_user_sid():
    """SID del usuario del proceso, sin depender del idioma de Windows.

    Se usa para que un helper elevado pueda restaurar HKCU del usuario que
    creó el snapshot incluso si UAC solicita credenciales de otra cuenta.
    """
    if platform.system() != 'Windows':
        return None
    try:
        proc = subprocess.run(
            ['whoami.exe', '/user', '/fo', 'csv', '/nh'],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            row = next(csv.reader([proc.stdout.strip()]))
            if len(row) >= 2 and str(row[1]).strip().upper().startswith('S-1-'):
                return str(row[1]).strip()
    except Exception:
        pass
    return None


def _rollback_guarantee(tweak):
    """Devuelve (garantizado, motivo) para nuevas aplicaciones."""
    if not isinstance(tweak, dict):
        return False, 'Tweak desconocido.'
    tweak_id = str(tweak.get('id') or '')
    if tweak_id in _NON_GUARANTEED_NEW_APPLY:
        return False, (
            'Bloqueado por política de rollback: esta acción desinstala un componente y '
            'Windows/WinGet no permiten reconstruir exactamente la versión y estado previos.'
        )
    if tweak.get('ps_apply') and tweak_id not in _COMMAND_SNAPSHOT_SUPPORTED:
        # Acciones heredadas con PowerShell sólo se permiten si también tienen una
        # estrategia de snapshot exacto conocida. Evita crear nuevos cambios irreversibles.
        return False, 'Bloqueado porque CorePulse no puede capturar un rollback exacto para esta acción.'
    return True, ''


def _windows_edition_id():
    """EditionID real de Windows; None si no se puede consultar de forma fiable."""
    if platform.system() != 'Windows' or winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion', 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, 'EditionID')
        text = str(value or '').strip()
        return text or None
    except Exception:
        return None


def _is_pro_plus_edition(edition):
    text = str(edition or '').strip().lower()
    if not text:
        return None
    prefixes = ('professional', 'enterprise', 'education', 'iotenterprise')
    return text.startswith(prefixes)


def _availability(tweak):
    """Evalúa soporte sin asumir que todas las ediciones exponen cada política."""
    if not is_windows_11():
        return False, 'Disponible sólo en Windows 11'
    guaranteed, guarantee_reason = _rollback_guarantee(tweak)
    if not guaranteed:
        return False, guarantee_reason
    build = None
    try:
        build = int(platform.version().split('.')[2])
    except Exception:
        pass
    minimum = tweak.get('min_build')
    if minimum and build is None:
        return False, f'No se pudo confirmar la build de Windows; el tweak requiere build {minimum} o posterior'
    if minimum and build is not None and build < int(minimum):
        return False, f'Requiere Windows 11 build {minimum} o posterior'
    if tweak.get('edition_scope') == 'pro_plus':
        edition = _windows_edition_id()
        supported = _is_pro_plus_edition(edition)
        if supported is None:
            return False, 'No se pudo confirmar la edición de Windows; CorePulse no aplicará una política exclusiva de Pro/Enterprise/Education'
        if supported is False:
            return False, f'No disponible en Windows {edition}; requiere Pro/Enterprise/Education compatible'
    return True, ''


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
        'edition': _windows_edition_id(),
        'user': getpass.getuser(),
    }



def preflight_tweak(tweak_id):
    """Evalúa si un tweak es aplicable en ESTE equipo sin modificar Windows.

    El resultado distingue compatibilidad de privilegios actuales. Un tweak que
    requiere administrador puede seguir siendo ``applicable=True`` porque
    CorePulse puede elevar sólo esa operación cuando el usuario la ejecuta.
    """
    tweak = _tweak_by_id(tweak_id)
    if not tweak:
        return {
            'id': str(tweak_id), 'status': 'unknown', 'applicable': False,
            'available': False, 'requires_admin': False, 'reason': 'Tweak desconocido.',
        }
    available, reason = _availability(tweak)
    if not available:
        return {
            'id': tweak['id'], 'status': 'unavailable', 'applicable': False,
            'available': False, 'requires_admin': bool(tweak.get('requires_admin')),
            'reason': reason or 'No disponible en este equipo.',
            'requires_restart': bool(tweak.get('requires_restart')),
            'requires_explorer': bool(tweak.get('requires_explorer')),
        }
    return {
        'id': tweak['id'], 'status': 'applicable', 'applicable': True,
        'available': True, 'requires_admin': bool(tweak.get('requires_admin')),
        'reason': '', 'requires_restart': bool(tweak.get('requires_restart')),
        'requires_explorer': bool(tweak.get('requires_explorer')),
    }


def preflight_many(ids=None):
    ordered = _ordered_known_ids(ids) if ids is not None else [item['id'] for item in TWEAKS]
    return [preflight_tweak(tweak_id) for tweak_id in ordered]


def compatible_tweak_ids():
    """IDs que el preflight considera aplicables en el Windows actual."""
    return tuple(row['id'] for row in preflight_many() if row.get('applicable'))


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


def _write_raw_value(hive_name, path, name, value, reg_type):
    """Restaura valor y tipo exactos capturados antes del tweak."""
    root = _hive(hive_name)
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, int(reg_type or winreg.REG_SZ), value)


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
    """Detector booleano para acciones que no se representan sólo en Registro."""
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


def _expected_reg_type_id(kind):
    """ID estable del tipo REG_* esperado, incluso en tests fuera de Windows."""
    fallback = {'string': 1, 'dword': 4, 'qword': 11}
    if winreg is None:
        return fallback.get(str(kind), 1)
    table = {
        'string': winreg.REG_SZ,
        'dword': winreg.REG_DWORD,
        'qword': getattr(winreg, 'REG_QWORD', fallback['qword']),
    }
    return int(table.get(str(kind), winreg.REG_SZ))


def _registry_detection_probe(hive_name, path, name, desired, kind):
    """Lee un objetivo de Registro y conserva evidencia de valor + tipo.

    V0.10.2.33w deja de considerar como coincidencia exacta un DWORD guardado
    accidentalmente como texto (o viceversa). Si un backend de prueba no expone
    el tipo, se conserva compatibilidad y la coincidencia queda marcada como
    ``type_verified=False`` en vez de inventar un tipo.
    """
    location = f'{hive_name}\\{path}' + (f' · {name}' if name else ' · (Predeterminado)')
    try:
        exists, current, reg_type = _read_value(hive_name, path, name)
    except Exception as exc:
        return {
            'kind': 'registry', 'location': location, 'state': 'unknown',
            'match': None, 'value_match': None, 'type_match': None,
            'exists': None, 'current': None, 'desired': desired,
            'expected_kind': kind, 'reg_type': None,
            'detail': f'No se pudo leer: {type(exc).__name__}: {exc}',
        }

    if not exists:
        return {
            'kind': 'registry', 'location': location, 'state': 'missing',
            'match': False, 'value_match': False, 'type_match': None,
            'exists': False, 'current': None, 'desired': desired,
            'expected_kind': kind, 'reg_type': None,
            'detail': 'El valor objetivo no existe.',
        }

    value_match = bool(_equal(current, desired, kind))
    type_match = None
    if reg_type is not None:
        try:
            type_match = int(reg_type) == int(_expected_reg_type_id(kind))
        except Exception:
            type_match = None

    exact = bool(value_match and type_match is not False)
    if exact:
        state = 'match'
        detail = 'Valor objetivo confirmado.' if type_match is not None else 'Valor objetivo confirmado; tipo no expuesto por el backend.'
    elif value_match and type_match is False:
        state = 'type_mismatch'
        detail = 'El valor coincide, pero el tipo REG_* no coincide con el que CorePulse aplica.'
    else:
        state = 'mismatch'
        detail = 'El valor actual es distinto al objetivo del tweak.'

    return {
        'kind': 'registry', 'location': location, 'state': state,
        'match': exact, 'value_match': value_match, 'type_match': type_match,
        'type_verified': type_match is not None,
        'exists': True, 'current': current, 'desired': desired,
        'expected_kind': kind, 'reg_type': reg_type, 'detail': detail,
    }


def _powershell_detection_probe(script):
    value, detail = _detect_ps(script)
    if value is True:
        state = 'match'
    elif value is False:
        state = 'mismatch'
    else:
        state = 'unknown'
    return {
        'kind': 'powershell', 'location': 'Comprobación de estado de Windows',
        'state': state, 'match': value, 'detail': detail or ('Estado confirmado.' if value is not None else 'Estado no verificable.'),
    }


def _classify_detection(evidence, *, has_action=False):
    """Clasifica sin convertir evidencia incompleta en un falso positivo."""
    if not evidence:
        return 'action' if has_action else 'not_applied'

    states = [str(row.get('state') or 'unknown') for row in evidence]
    matches = sum(state == 'match' for state in states)
    unknown = sum(state == 'unknown' for state in states)
    mismatches = sum(state in ('missing', 'mismatch') for state in states)
    type_mismatches = sum(state == 'type_mismatch' for state in states)

    if matches == len(states):
        return 'applied'
    if matches or type_mismatches:
        return 'partial'
    if unknown:
        # Aunque exista una evidencia negativa, una parte del tweak no pudo
        # verificarse. No etiquetamos el conjunto como NO APLICADO a ciegas.
        return 'unknown'
    if mismatches == len(states):
        return 'not_applied'
    return 'partial'


def _detection_origin(tweak_id, status, rollback_ids):
    """Distingue cambio trazado por CorePulse de estado que ya existía."""
    has_rollback = str(tweak_id) in set(rollback_ids or ())
    if status == 'applied':
        return 'corepulse' if has_rollback else 'preexisting'
    if has_rollback:
        return 'corepulse_snapshot'
    return 'external_or_none'


def detect_tweak(tweak_id, *, _rollback_ids=None):
    """Detección determinística y explicable del estado de un tweak.

    Diferencia cuatro conceptos que antes se mezclaban:
    1. si el tweak es APLICABLE en esta build/edición;
    2. si TODOS sus objetivos están exactamente configurados;
    3. si existe una configuración PARCIAL o no verificable;
    4. si el estado aplicado está respaldado por un snapshot de CorePulse o ya
       estaba presente antes / fue configurado por otra herramienta.

    ``applied=True`` sólo se devuelve cuando TODA la evidencia declarada por el
    tweak coincide. Un valor correcto con tipo REG_* incorrecto queda PARCIAL.
    """
    tweak = _tweak_by_id(tweak_id)
    if not tweak:
        return {
            'id': tweak_id, 'status': 'unknown', 'applied': False,
            'origin': 'unknown', 'available': False, 'verified': False,
            'detail': 'Tweak desconocido', 'evidence': [],
        }

    available, availability_reason = _availability(tweak)

    # Fuera de Windows 11 no intentamos interpretar claves/PowerShell como si
    # fueran evidencia válida del sistema objetivo.
    if not is_windows_11():
        return {
            'id': tweak_id, 'status': 'unavailable', 'applied': False,
            'origin': 'external_or_none', 'available': False, 'verified': False,
            'availability_reason': availability_reason or 'Disponible sólo en Windows 11',
            'detail': availability_reason or 'Disponible sólo en Windows 11',
            'evidence': [], 'rollback_available': False,
        }

    evidence = []
    for hive_name, path, name, desired, kind in tweak.get('ops', ()):
        evidence.append(_registry_detection_probe(hive_name, path, name, desired, kind))

    if tweak.get('ps_detect'):
        evidence.append(_powershell_detection_probe(tweak['ps_detect']))

    status = _classify_detection(evidence, has_action=bool(tweak.get('ps_apply')))

    # Carga el estado persistente una vez por detect_all; detect_tweak individual
    # conserva la API pública y resuelve el conjunto por sí solo.
    rollback_ids = saved_rollback_ids() if _rollback_ids is None else set(_rollback_ids)
    origin = _detection_origin(tweak_id, status, rollback_ids)
    rollback_available = str(tweak_id) in rollback_ids

    unknown_count = sum(str(row.get('state')) == 'unknown' for row in evidence)
    type_unknown_count = sum(
        bool(row.get('kind') == 'registry' and row.get('exists') is True and row.get('type_match') is None)
        for row in evidence
    )
    verified = bool(status == 'applied' and not unknown_count and not type_unknown_count)
    if status == 'applied' and verified:
        confidence = 'high'
    elif status in ('applied', 'not_applied', 'partial') and not unknown_count:
        confidence = 'medium'
    else:
        confidence = 'low'

    if status == 'applied':
        if origin == 'corepulse':
            detail = 'Todos los objetivos coinciden exactamente y CorePulse conserva el rollback de este cambio.'
        else:
            detail = 'Todos los objetivos coinciden, pero CorePulse no tiene snapshot: el ajuste ya estaba aplicado o fue configurado fuera de CorePulse.'
    elif status == 'partial':
        detail = 'Sólo una parte de los objetivos coincide o existe una diferencia de tipo REG_*; no se considera aplicado por completo.'
    elif status == 'not_applied':
        detail = 'Los objetivos verificables no coinciden con la configuración del tweak.'
    elif status == 'unknown':
        detail = 'CorePulse no pudo verificar toda la evidencia necesaria; no se asume aplicado ni no aplicado.'
    elif status == 'action':
        detail = 'La acción existe, pero no declara un detector suficiente para afirmar su estado actual.'
    else:
        detail = str(status)

    if not available:
        suffix = availability_reason or 'No disponible para aplicación en este equipo.'
        detail += f' Aplicación bloqueada: {suffix}'

    return {
        'id': tweak_id,
        'status': status,
        'applied': status == 'applied',
        'origin': origin,
        'available': bool(available),
        'availability_reason': availability_reason or '',
        'verified': verified,
        'confidence': confidence,
        'rollback_available': rollback_available,
        'detail': detail,
        'evidence': evidence,
        'matched_targets': sum(str(row.get('state')) == 'match' for row in evidence),
        'total_targets': len(evidence),
    }


def detect_all():
    """Detecta el catálogo usando una sola lectura del almacén de rollback."""
    rollback_ids = saved_rollback_ids()
    return {item['id']: detect_tweak(item['id'], _rollback_ids=rollback_ids) for item in TWEAKS}


def _default_state():
    return {
        'schema': 5,
        'revision': 0,
        'updated_at': time.time(),
        'user': getpass.getuser(),
        'computer': platform.node(),
        'tweaks': {},
    }


def _legacy_state_candidates():
    """Rollbacks portables antiguos cercanos al ejecutable/proyecto actual."""
    candidates = [LEGACY_STATE_PATH]
    try:
        portable = executable_root() / 'data' / 'windows_tweaks_state.json'
        if portable != STATE_PATH and portable not in candidates and portable.is_file():
            candidates.append(portable)
    except Exception:
        pass
    try:
        parent = PROJECT_ROOT.parent
        for folder in parent.glob('CorePulse*'):
            candidate = folder / 'data' / 'windows_tweaks_state.json'
            if candidate != STATE_PATH and candidate not in candidates and candidate.is_file():
                candidates.append(candidate)
    except Exception:
        pass
    return candidates[:24]


def _read_legacy_candidate(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('tweaks'), dict):
            return None
        if data.get('user') != getpass.getuser():
            return None
        old_computer = str(data.get('computer') or '').strip()
        if old_computer and old_computer != platform.node():
            return None
        return data
    except Exception:
        return None


def _migrate_legacy_storage_once():
    """Migra rollbacks de builds portables antiguas al almacén durable del usuario."""
    global _MIGRATION_DONE
    if _MIGRATION_DONE:
        return
    with _STATE_LOCK:
        if _MIGRATION_DONE:
            return
        try:
            PERSISTENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
            backup_path = STATE_PATH.with_name('windows_tweaks_state.backup.json')
            if not STATE_PATH.exists() and not backup_path.exists():
                valid = []
                for candidate in _legacy_state_candidates():
                    data = _read_legacy_candidate(candidate)
                    if data is None:
                        continue
                    try:
                        stamp = candidate.stat().st_mtime
                    except Exception:
                        stamp = 0.0
                    valid.append((stamp, candidate, data))
                if valid:
                    # La copia más reciente con identidad local válida representa el
                    # último estado portable conocido. No mezclamos originales de
                    # snapshots distintos para evitar restauraciones ambiguas.
                    _, _candidate, data = max(valid, key=lambda row: row[0])
                    STATE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            if HISTORY_PATH != LEGACY_HISTORY_PATH and not HISTORY_PATH.exists() and LEGACY_HISTORY_PATH.exists():
                HISTORY_PATH.write_bytes(LEGACY_HISTORY_PATH.read_bytes())
        except Exception:
            # La migración jamás puede impedir abrir CorePulse; el motor seguirá
            # usando la ruta durable disponible y REAL_OR_NA para cualquier fallo.
            pass
        _MIGRATION_DONE = True


def _state_owner_matches(state):
    # En Windows STATE_PATH vive en LOCALAPPDATA (local al usuario/equipo). El
    # nombre del PC puede cambiar con el tiempo, por lo que no invalida un rollback.
    return isinstance(state, dict) and state.get('user') == getpass.getuser()


def _read_state_path(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if isinstance(data, dict) and isinstance(data.get('tweaks'), dict):
            data.setdefault('schema', 5)
            data.setdefault('revision', 0)
            data.setdefault('updated_at', 0.0)
            data.setdefault('user', getpass.getuser())
            data.setdefault('computer', platform.node())
            return data
    except Exception:
        return None
    return None


def _state_rank(data):
    if not isinstance(data, dict):
        return (-1, -1.0)
    try:
        revision = int(data.get('revision') or 0)
    except Exception:
        revision = 0
    try:
        updated = float(data.get('updated_at') or 0.0)
    except Exception:
        updated = 0.0
    return (revision, updated)


def _write_state_copy(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(payload, encoding='utf-8')
    temp.replace(path)


def _load_state():
    """Carga el snapshot más nuevo entre principal y espejo.

    Cada mutación se guarda en dos archivos con `revision`. Si Windows se cierra
    durante una escritura, se elige automáticamente la copia válida más reciente.
    """
    _migrate_legacy_storage_once()
    with _STATE_LOCK:
        backup_path = STATE_PATH.with_name('windows_tweaks_state.backup.json')
        primary = _read_state_path(STATE_PATH)
        backup = _read_state_path(backup_path)
        valid = [row for row in (primary, backup) if row is not None]
        if not valid:
            return _default_state()
        data = max(valid, key=_state_rank)
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        # Auto-repara la copia ausente/corrupta/obsoleta sin cambiar la revisión.
        try:
            if primary is None or _state_rank(primary) != _state_rank(data):
                _write_state_copy(STATE_PATH, payload)
        except Exception:
            pass
        try:
            if backup is None or _state_rank(backup) != _state_rank(data):
                _write_state_copy(backup_path, payload)
        except Exception:
            pass
        return data


def _save_state(data):
    """Guardado transaccional redundante del rollback.

    Se escribe primero el espejo y luego el principal. La `revision` permite
    recuperar la copia más nueva incluso si el proceso se interrumpe entre ambas.
    """
    _migrate_legacy_storage_once()
    with _STATE_LOCK:
        try:
            current_revision = int(data.get('revision') or 0)
        except Exception:
            current_revision = 0
        data['schema'] = 5
        data['revision'] = current_revision + 1
        data['updated_at'] = time.time()
        data.setdefault('user', getpass.getuser())
        data.setdefault('computer', platform.node())
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        backup_path = STATE_PATH.with_name('windows_tweaks_state.backup.json')
        backup_error = None
        try:
            _write_state_copy(backup_path, payload)
        except Exception as exc:
            backup_error = exc
        _write_state_copy(STATE_PATH, payload)
        # Si falló el espejo pero el principal quedó bien, lo reintentamos ahora.
        if backup_error is not None:
            try:
                _write_state_copy(backup_path, payload)
            except Exception:
                pass


def _audit(tweak_id, action, success, message=''):
    try:
        _migrate_legacy_storage_once()
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {
            'timestamp': time.time(), 'user': getpass.getuser(), 'computer': platform.node(),
            'tweak_id': tweak_id, 'action': action, 'success': bool(success), 'message': str(message or '')[:800],
        }
        with HISTORY_PATH.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    except Exception:
        pass


def saved_rollback_ids():
    """IDs con rollback persistente disponible, leídos en una sola operación."""
    state = _load_state()
    if not _state_owner_matches(state):
        return set()
    return set((state.get('tweaks') or {}).keys())


def has_saved_original(tweak_id):
    return str(tweak_id) in saved_rollback_ids()


def _capture_command_snapshot(tweak):
    """Captura estado exacto para acciones PowerShell/powercfg admitidas.

    Si no puede capturarse de forma fiable se lanza una excepción ANTES de
    modificar Windows, cumpliendo el contrato de rollback obligatorio.
    """
    if not tweak.get('ps_apply'):
        return None
    tweak_id = tweak.get('id')
    if tweak_id == 'disable_hibernation':
        exists, value, _ = _read_value('HKLM', r'SYSTEM\CurrentControlSet\Control\Session Manager\Power', 'HibernateEnabled')
        if not exists:
            raise RuntimeError('Windows no expuso HibernateEnabled; CorePulse no puede garantizar el rollback y no aplicará el tweak.')
        return {'strategy': 'hibernation_exact', 'enabled': bool(int(value or 0))}
    if tweak_id == 'disable_defender_stack':
        script = r"""
$p=Get-MpPreference -ErrorAction Stop
[pscustomobject]@{
 DisableRealtimeMonitoring=[bool]$p.DisableRealtimeMonitoring
 DisableBehaviorMonitoring=[bool]$p.DisableBehaviorMonitoring
 DisableBlockAtFirstSeen=[bool]$p.DisableBlockAtFirstSeen
 DisableIOAVProtection=[bool]$p.DisableIOAVProtection
 DisableScriptScanning=[bool]$p.DisableScriptScanning
 MAPSReporting=[int]$p.MAPSReporting
 SubmitSamplesConsent=[int]$p.SubmitSamplesConsent
} | ConvertTo-Json -Compress
"""
        result = _run_powershell(script, timeout=25)
        if not result.get('success'):
            raise RuntimeError('No se pudo capturar el estado previo de Microsoft Defender: ' + (result.get('stderr') or result.get('stdout') or 'sin detalle'))
        lines = [line.strip() for line in str(result.get('stdout') or '').splitlines() if line.strip()]
        if not lines:
            raise RuntimeError('Microsoft Defender no devolvió un estado previo verificable.')
        try:
            data = json.loads(lines[-1])
        except Exception as exc:
            raise RuntimeError(f'No se pudo interpretar el estado previo de Microsoft Defender: {exc}')
        required = {
            'DisableRealtimeMonitoring', 'DisableBehaviorMonitoring', 'DisableBlockAtFirstSeen',
            'DisableIOAVProtection', 'DisableScriptScanning', 'MAPSReporting', 'SubmitSamplesConsent',
        }
        if not isinstance(data, dict) or not required.issubset(data):
            raise RuntimeError('El snapshot de Microsoft Defender está incompleto; no se aplicará el tweak.')
        data['strategy'] = 'defender_preferences_exact'
        return data
    raise RuntimeError('CorePulse no tiene una estrategia de rollback exacto para esta acción; no se aplicará.')


def _assert_snapshot_persisted(tweak_id):
    reloaded = _load_state()
    record = (reloaded.get('tweaks') or {}).get(str(tweak_id))
    if not isinstance(record, dict):
        raise RuntimeError('No se pudo verificar el snapshot de rollback en disco; el tweak no se aplicará.')
    return record


def _save_original_if_needed(state, tweak):
    tweak_id = tweak['id']
    if tweak_id in state['tweaks']:
        _assert_snapshot_persisted(tweak_id)
        return
    originals = []
    for hive_name, path, name, desired, kind in tweak.get('ops', ()):
        exists, value, reg_type = _read_value(hive_name, path, name)
        originals.append({
            'hive': hive_name, 'path': path, 'name': name, 'existed': exists,
            'value': value, 'reg_type': reg_type,
        })
    command_snapshot = _capture_command_snapshot(tweak)
    state['tweaks'][tweak_id] = {
        'saved_at': time.time(),
        'owner_user': getpass.getuser(),
        'owner_sid': _current_user_sid(),
        'originals': originals,
        'command_snapshot': command_snapshot,
        'undo_mode': tweak.get('undo_mode', 'exact'),
        'has_command': bool(tweak.get('ps_apply')),
    }
    _save_state(state)
    # Nunca se toca Windows si el snapshot no puede releerse desde almacenamiento durable.
    _assert_snapshot_persisted(tweak_id)


def _registry_target_for_original(original, owner_sid=None):
    """Devuelve (root, path) respetando HKCU del dueño del snapshot.

    En una elevación con credenciales de otra cuenta, HKEY_CURRENT_USER apunta
    al administrador. Para rollback de usuario se usa HKEY_USERS\\<SID>.
    """
    hive_name = original.get('hive')
    path = str(original.get('path') or '')
    if (
        hive_name == 'HKCU' and owner_sid and winreg is not None
        and str(owner_sid) != str(_current_user_sid() or '')
    ):
        return winreg.HKEY_USERS, str(owner_sid) + ('\\' + path if path else '')
    return _hive(hive_name), path


def _read_original_target(original, owner_sid=None):
    hive_name = original.get('hive')
    if hive_name == 'HKCU' and owner_sid and str(owner_sid) != str(_current_user_sid() or '') and winreg is not None:
        root, target_path = _registry_target_for_original(original, owner_sid)
        try:
            with winreg.OpenKey(root, target_path, 0, winreg.KEY_READ) as key:
                value, reg_type = winreg.QueryValueEx(key, original.get('name', ''))
                return True, value, reg_type
        except (FileNotFoundError, OSError):
            return False, None, None
    return _read_value(hive_name, original.get('path', ''), original.get('name', ''))


def _write_original_target(original, owner_sid=None):
    hive_name = original.get('hive')
    if hive_name == 'HKCU' and owner_sid and str(owner_sid) != str(_current_user_sid() or '') and winreg is not None:
        root, target_path = _registry_target_for_original(original, owner_sid)
        if original.get('existed'):
            with winreg.CreateKeyEx(root, target_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(
                    key, original.get('name', ''), 0,
                    int(original.get('reg_type') or winreg.REG_SZ), original.get('value'),
                )
        else:
            try:
                with winreg.OpenKey(root, target_path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, original.get('name', ''))
            except (FileNotFoundError, OSError):
                pass
        return
    if original.get('existed'):
        _write_raw_value(hive_name, original.get('path', ''), original.get('name', ''), original.get('value'), original.get('reg_type'))
    else:
        _delete_value(hive_name, original.get('path', ''), original.get('name', ''))


def _restore_registry_originals(record):
    errors = []
    owner_sid = record.get('owner_sid')
    for original in record.get('originals', []):
        try:
            _write_original_target(original, owner_sid)
        except Exception as exc:
            errors.append(f"{original.get('path')}\\{original.get('name')}: {exc}")
    return errors


def _verify_registry_originals(record):
    mismatches = []
    owner_sid = record.get('owner_sid')
    for original in record.get('originals', []):
        try:
            exists, value, reg_type = _read_original_target(original, owner_sid)
            if bool(exists) != bool(original.get('existed')):
                mismatches.append(f"{original.get('path')}\\{original.get('name')}")
                continue
            if exists:
                wanted = original.get('value')
                wanted_type = original.get('reg_type')
                if value != wanted or (wanted_type is not None and reg_type != wanted_type):
                    mismatches.append(f"{original.get('path')}\\{original.get('name')}")
        except Exception:
            mismatches.append(f"{original.get('path')}\\{original.get('name')}")
    return mismatches


def _ps_bool(value):
    return '$true' if bool(value) else '$false'


def _command_restore_script(tweak, record):
    """Script de reversión construido desde el snapshot, no desde defaults."""
    tweak_id = str(tweak.get('id') or '')
    snap = record.get('command_snapshot') if isinstance(record, dict) else None
    if tweak_id == 'disable_hibernation':
        enabled = None
        if isinstance(snap, dict) and 'enabled' in snap:
            enabled = bool(snap.get('enabled'))
        if enabled is None:
            # Compatibilidad con snapshots V0.10.2.22w: el valor exacto ya estaba
            # guardado dentro de originals aunque command_snapshot no existiera.
            for original in record.get('originals', []):
                if original.get('hive') == 'HKLM' and original.get('name') == 'HibernateEnabled':
                    if original.get('existed'):
                        try:
                            enabled = int(original.get('value') or 0) != 0
                        except Exception:
                            enabled = None
                    break
        if enabled is None:
            return None, False, 'El snapshot no contiene el estado previo de hibernación.'
        mode = 'on' if enabled else 'off'
        return f'powercfg.exe /hibernate {mode}; if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}', False, ''

    if tweak_id == 'disable_defender_stack':
        required = (
            'DisableRealtimeMonitoring', 'DisableBehaviorMonitoring', 'DisableBlockAtFirstSeen',
            'DisableIOAVProtection', 'DisableScriptScanning', 'MAPSReporting', 'SubmitSamplesConsent',
        )
        if isinstance(snap, dict) and all(key in snap for key in required):
            script = (
                'Set-MpPreference '
                f"-DisableRealtimeMonitoring {_ps_bool(snap['DisableRealtimeMonitoring'])} "
                f"-DisableBehaviorMonitoring {_ps_bool(snap['DisableBehaviorMonitoring'])} "
                f"-DisableBlockAtFirstSeen {_ps_bool(snap['DisableBlockAtFirstSeen'])} "
                f"-DisableIOAVProtection {_ps_bool(snap['DisableIOAVProtection'])} "
                f"-DisableScriptScanning {_ps_bool(snap['DisableScriptScanning'])} "
                f"-MAPSReporting {int(snap['MAPSReporting'])} "
                f"-SubmitSamplesConsent {int(snap['SubmitSamplesConsent'])} -ErrorAction Stop"
            )
            return script, False, ''
        # Snapshot antiguo: no conocemos las preferencias exactas. Para no dejar
        # al usuario sin salida, se ejecuta la reversión segura heredada y se
        # conserva el mensaje de que no fue un snapshot exacto.
        if tweak.get('ps_undo'):
            return tweak['ps_undo'], True, 'Snapshot heredado: Defender se restaurará a valores seguros, no a preferencias exactas desconocidas.'
        return None, True, 'Snapshot heredado incompleto de Microsoft Defender.'

    # Acciones destructivas de builds antiguas pueden seguir deshaciéndose con su
    # inversa definida. Nuevas aplicaciones están bloqueadas por _availability.
    if tweak.get('ps_undo'):
        return tweak['ps_undo'], True, 'Reversión heredada definida; el snapshot antiguo no permite reconstrucción byte-a-byte.'
    return None, bool(tweak.get('ps_apply')), 'No existe una acción de reversión definida.'


def _verify_command_snapshot(tweak, record, *, legacy=False):
    if not tweak.get('ps_apply'):
        return []
    tweak_id = str(tweak.get('id') or '')
    snap = record.get('command_snapshot') if isinstance(record, dict) else None
    if tweak_id == 'disable_defender_stack' and isinstance(snap, dict) and not legacy:
        try:
            current = _capture_command_snapshot(tweak)
        except Exception as exc:
            return [f'No se pudo verificar Microsoft Defender: {exc}']
        keys = (
            'DisableRealtimeMonitoring', 'DisableBehaviorMonitoring', 'DisableBlockAtFirstSeen',
            'DisableIOAVProtection', 'DisableScriptScanning', 'MAPSReporting', 'SubmitSamplesConsent',
        )
        mismatch = [key for key in keys if current.get(key) != snap.get(key)]
        return ['Microsoft Defender no volvió a: ' + ', '.join(mismatch)] if mismatch else []
    if tweak_id == 'disable_hibernation':
        # El estado que powercfg modifica está respaldado por HibernateEnabled y
        # se valida en _verify_registry_originals después del comando.
        return []
    if tweak.get('ps_detect'):
        value, detail = _detect_ps(tweak['ps_detect'])
        if value is True:
            return ['Windows todavía detecta el tweak como aplicado.']
        if value is None:
            return [detail or 'No se pudo verificar la reversión del comando.']
    return []


def _restore_record_direct(tweak, record, attempts=3):
    """Restaura un snapshot sin leer/escribir STATE_PATH.

    Esta función es la que puede ejecutar el helper UAC. El padre conserva la
    autoridad sobre el archivo persistente y sólo elimina el snapshot cuando el
    helper devuelve `verified=True`.
    """
    max_attempts = max(1, min(int(attempts or 1), 5))
    last_problems = []
    legacy_note = ''
    for attempt in range(1, max_attempts + 1):
        problems = []
        legacy = False
        if tweak.get('ps_apply'):
            script, legacy, script_problem = _command_restore_script(tweak, record)
            if script_problem and not script:
                problems.append(script_problem)
            if script:
                result = _run_powershell(script)
                if not result.get('success'):
                    problems.append(result.get('stderr') or result.get('stdout') or f"PowerShell devolvió {result.get('returncode')}")
            if legacy and script_problem:
                legacy_note = script_problem

        problems.extend(_restore_registry_originals(record))
        registry_mismatches = _verify_registry_originals(record)
        if registry_mismatches:
            problems.append('Registro no restaurado: ' + ', '.join(registry_mismatches[:4]))
        problems.extend(_verify_command_snapshot(tweak, record, legacy=legacy))
        if not problems:
            message = 'Valor previo restaurado y verificado.'
            if legacy_note:
                message += ' ' + legacy_note
            if attempt > 1:
                message += f' Completado tras {attempt} intentos.'
            return {
                'success': True, 'id': tweak.get('id'), 'message': message, 'verified': True,
                'rollback_available': False, 'attempts': attempt, 'legacy_restore': bool(legacy_note),
                'requires_explorer': tweak.get('requires_explorer'), 'requires_restart': tweak.get('requires_restart'),
            }
        last_problems = problems
        if attempt < max_attempts:
            time.sleep(0.18 * attempt)
    message = 'No se pudo completar la reversión tras varios intentos: ' + ' | '.join(str(x) for x in last_problems[:4])
    return {
        'success': False, 'id': tweak.get('id'), 'message': message, 'verified': False,
        'rollback_available': True, 'attempts': max_attempts,
        'requires_explorer': tweak.get('requires_explorer'), 'requires_restart': tweak.get('requires_restart'),
    }


def restore_snapshot_records(rows, attempts=3):
    """API del helper elevado: restaura snapshots recibidos por payload."""
    results = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        tweak_id = str(row.get('id') or '')
        tweak = _tweak_by_id(tweak_id)
        record = row.get('record')
        if not tweak or not isinstance(record, dict):
            results.append({'success': False, 'id': tweak_id, 'rollback_available': True, 'message': 'Snapshot elevado inválido.'})
            continue
        results.append(_restore_record_direct(tweak, record, attempts=attempts))
    return results



def _apply_record_direct(tweak, record):
    """Aplica un tweak usando un snapshot YA persistido por el proceso dueño.

    El helper elevado usa esta ruta: nunca decide dónde guardar el rollback ni
    quién es su dueño. Sólo escribe, verifica y, si algo falla, restaura el
    snapshot exacto recibido.
    """
    tweak_id = str(tweak.get('id') or '')
    available, reason = _availability(tweak)
    if not available:
        return {
            'success': False, 'id': tweak_id, 'status': 'unavailable', 'skipped': True,
            'message': reason or 'No disponible en este equipo.', 'rollback_available': True,
            'requires_explorer': bool(tweak.get('requires_explorer')),
            'requires_restart': bool(tweak.get('requires_restart')),
        }
    try:
        for hive_name, path, name, desired, kind in tweak.get('ops', ()):
            _write_value(hive_name, path, name, desired, kind)
        if tweak.get('ps_apply'):
            result = _run_powershell(tweak['ps_apply'])
            if not result.get('success'):
                message = result.get('stderr') or result.get('stdout') or f"PowerShell devolvió {result.get('returncode')}"
                rollback = _restore_record_direct(tweak, record, attempts=2)
                return {
                    'success': False, 'id': tweak_id, 'status': 'error',
                    'message': message + (' Cambios parciales revertidos automáticamente.' if rollback.get('success') else ' Rollback automático incompleto.'),
                    'rolled_back': bool(rollback.get('success')), 'verified': False,
                    'rollback_available': not bool(rollback.get('success')),
                    'requires_explorer': bool(tweak.get('requires_explorer')),
                    'requires_restart': bool(tweak.get('requires_restart')),
                }
        final = detect_tweak(tweak_id)
        success = final.get('status') in ('applied', 'action')
        if not success:
            rollback = _restore_record_direct(tweak, record, attempts=2)
            return {
                'success': False, 'id': tweak_id, 'status': 'error',
                'message': 'Windows no confirmó todos los cambios.' + (' Cambios parciales revertidos automáticamente.' if rollback.get('success') else ' Rollback automático incompleto.'),
                'rolled_back': bool(rollback.get('success')), 'verified': False,
                'rollback_available': not bool(rollback.get('success')),
                'requires_explorer': bool(tweak.get('requires_explorer')),
                'requires_restart': bool(tweak.get('requires_restart')),
            }
        return {
            'success': True, 'id': tweak_id, 'status': 'applied', 'changed': True,
            'verified': True, 'rollback_available': True,
            'message': 'Aplicado y verificado correctamente.',
            'requires_explorer': bool(tweak.get('requires_explorer')),
            'requires_restart': bool(tweak.get('requires_restart')),
        }
    except Exception as exc:
        rollback = _restore_record_direct(tweak, record, attempts=2)
        return {
            'success': False, 'id': tweak_id, 'status': 'error',
            'message': f'{type(exc).__name__}: {exc}' + (' Cambios parciales revertidos automáticamente.' if rollback.get('success') else ' Rollback automático incompleto.'),
            'rolled_back': bool(rollback.get('success')), 'verified': False,
            'rollback_available': not bool(rollback.get('success')),
            'requires_explorer': bool(tweak.get('requires_explorer')),
            'requires_restart': bool(tweak.get('requires_restart')),
        }


def apply_snapshot_records(rows):
    """API del helper elevado: aplica únicamente snapshots recibidos."""
    results = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        tweak_id = str(row.get('id') or '')
        tweak = _tweak_by_id(tweak_id)
        record = row.get('record')
        if not tweak or not isinstance(record, dict):
            results.append({'success': False, 'id': tweak_id, 'status': 'error', 'message': 'Snapshot de aplicación elevado inválido.'})
            continue
        results.append(_apply_record_direct(tweak, record))
    return results


def _attempt_apply_rollback(tweak, record):
    result = _restore_record_direct(tweak, record, attempts=2)
    return {'success': bool(result.get('success')), 'errors': [] if result.get('success') else [result.get('message') or 'Rollback incompleto']}


def _verify_undo_complete(tweak, record):
    problems = []
    registry_mismatches = _verify_registry_originals(record)
    if registry_mismatches:
        problems.append('Registro no restaurado: ' + ', '.join(registry_mismatches[:4]))
    problems.extend(_verify_command_snapshot(tweak, record))
    return {'success': not problems, 'problems': problems}


def apply_tweak(tweak_id):
    tweak = _tweak_by_id(tweak_id)
    if not tweak:
        return {'success': False, 'id': tweak_id, 'message': 'Tweak desconocido.'}
    if not is_windows_11():
        return {
            'success': False, 'id': tweak_id, 'status': 'unavailable', 'skipped': True,
            'message': 'Esta función requiere Windows 11.',
        }
    available, reason = _availability(tweak)
    if not available:
        return {
            'success': False, 'id': tweak_id, 'status': 'unavailable', 'skipped': True,
            'message': reason or 'Este tweak no está disponible en esta edición/build de Windows.',
            'requires_explorer': bool(tweak.get('requires_explorer')),
            'requires_restart': bool(tweak.get('requires_restart')),
        }
    if tweak.get('requires_admin') and not is_admin():
        return {
            'success': False, 'id': tweak_id, 'status': 'requires_admin', 'needs_elevation': True,
            'message': 'Este tweak requiere privilegios de administrador.',
            'requires_explorer': bool(tweak.get('requires_explorer')),
            'requires_restart': bool(tweak.get('requires_restart')),
        }

    detected = detect_tweak(tweak_id)
    rollback_ids = saved_rollback_ids()
    if detected['applied'] and tweak_id not in rollback_ids:
        return {
            'success': True, 'id': tweak_id, 'changed': False,
            'message': 'Ya estaba aplicado antes de CorePulse.', 'rollback_available': False,
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }

    state = _load_state()
    if not _state_owner_matches(state):
        state = _default_state()
    record_preexisted = tweak_id in (state.get('tweaks') or {})

    try:
        _save_original_if_needed(state, tweak)
        record = (state.get('tweaks') or {}).get(tweak_id, {})
        for hive_name, path, name, desired, kind in tweak.get('ops', ()):
            _write_value(hive_name, path, name, desired, kind)

        if tweak.get('ps_apply'):
            result = _run_powershell(tweak['ps_apply'])
            if not result['success']:
                message = result.get('stderr') or result.get('stdout') or f"PowerShell devolvió {result.get('returncode')}"
                rollback = _attempt_apply_rollback(tweak, record)
                if rollback['success'] and not record_preexisted:
                    state = _load_state()
                    state.get('tweaks', {}).pop(tweak_id, None)
                    _save_state(state)
                suffix = ' Cambios parciales revertidos automáticamente.' if rollback['success'] else ' Rollback automático incompleto; la reversión queda guardada para reintentar.'
                full = message + suffix
                _audit(tweak_id, 'apply', False, full)
                return {
                    'success': False, 'id': tweak_id, 'message': full, 'rolled_back': rollback['success'],
                    'rollback_available': (not rollback['success']) or record_preexisted,
                    'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
                }

        final = detect_tweak(tweak_id)
        success = final.get('status') in ('applied', 'action')
        if not success:
            rollback = _attempt_apply_rollback(tweak, record)
            if rollback['success'] and not record_preexisted:
                state = _load_state()
                state.get('tweaks', {}).pop(tweak_id, None)
                _save_state(state)
            message = 'Windows no confirmó todos los cambios.'
            message += ' Cambios parciales revertidos automáticamente.' if rollback['success'] else ' Rollback automático incompleto; la reversión queda guardada para reintentar.'
            _audit(tweak_id, 'apply', False, message)
            return {
                'success': False, 'id': tweak_id, 'changed': True, 'message': message,
                'rolled_back': rollback['success'], 'rollback_available': (not rollback['success']) or record_preexisted,
                'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
            }

        message = 'Aplicado y verificado correctamente.'
        _audit(tweak_id, 'apply', True, message)
        return {
            'success': True, 'id': tweak_id, 'changed': True, 'message': message,
            'verified': True, 'rollback_available': True,
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }
    except Exception as exc:
        state = _load_state()
        record = (state.get('tweaks') or {}).get(tweak_id, {})
        rollback = _attempt_apply_rollback(tweak, record) if record else {'success': True, 'errors': []}
        if rollback['success'] and not record_preexisted and record:
            state.get('tweaks', {}).pop(tweak_id, None)
            _save_state(state)
        message = str(exc)
        message += ' Cambios parciales revertidos automáticamente.' if rollback['success'] else ' Rollback automático incompleto; la reversión queda guardada para reintentar.'
        _audit(tweak_id, 'apply', False, message)
        return {
            'success': False, 'id': tweak_id, 'message': message, 'rolled_back': rollback['success'],
            'rollback_available': (not rollback['success']) or record_preexisted,
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }


def undo_tweak(tweak_id, attempts=3):
    """Restaura un tweak desde su snapshot y conserva el snapshot si falla."""
    tweak = _tweak_by_id(tweak_id)
    if not tweak:
        return {'success': False, 'id': tweak_id, 'message': 'Tweak desconocido.'}
    if not is_windows_11():
        return {
            'success': False, 'id': tweak_id, 'status': 'unavailable', 'skipped': True,
            'message': 'Esta función requiere Windows 11.',
        }
    if tweak.get('requires_admin') and not is_admin():
        return {
            'success': False, 'id': tweak_id,
            'message': 'La reversión requiere elevación de administrador (UAC).',
            'rollback_available': True, 'needs_elevation': True,
            'requires_explorer': tweak['requires_explorer'], 'requires_restart': tweak['requires_restart'],
        }

    state = _load_state()
    if not _state_owner_matches(state):
        return {'success': False, 'id': tweak_id, 'message': 'El rollback guardado pertenece a otro usuario.'}
    record = (state.get('tweaks') or {}).get(tweak_id)
    if not isinstance(record, dict):
        return {'success': False, 'id': tweak_id, 'message': 'CorePulse no tiene una reversión guardada para este tweak.'}

    result = _restore_record_direct(tweak, record, attempts=attempts)
    if result.get('success') and result.get('verified'):
        latest = _load_state()
        # Sólo el proceso dueño del almacén elimina el snapshot, y únicamente si
        # sigue existiendo. Esto evita que un helper elevado manipule otro perfil.
        if isinstance((latest.get('tweaks') or {}).get(tweak_id), dict):
            latest.get('tweaks', {}).pop(tweak_id, None)
            _save_state(latest)
        _audit(tweak_id, 'undo', True, result.get('message') or 'Restaurado y verificado.')
        result['rollback_available'] = False
        return result

    message = (result.get('message') or 'No se pudo completar la reversión.')
    message += ' El rollback permanece guardado para reintentar.'
    result['message'] = message
    result['rollback_available'] = True
    _audit(tweak_id, 'undo', False, message)
    return result


def _ordered_known_ids(ids):
    wanted = {str(x) for x in (ids or ())}
    return [item['id'] for item in TWEAKS if item['id'] in wanted]


def _elevated_helper_target(mode, request_path):
    """Devuelve (ejecutable, ArgumentList) para UAC en fuente o EXE."""
    flag = '--corepulse-tweak-apply' if mode == 'apply' else '--corepulse-tweak-rollback'
    if is_frozen():
        exe = str(sys.executable)
        args = [flag, '--request', str(request_path)]
    else:
        exe = str(sys.executable)
        launcher = source_root() / 'corepulse_launcher.py'
        args = [str(launcher), flag, '--request', str(request_path)]
    return exe, subprocess.list2cmdline(args)


def _undo_many_elevated(ids):
    """Restaura sólo snapshots administrativos en un hijo UAC.

    El helper recibe COPIAS de los snapshots exactos; nunca resuelve LOCALAPPDATA
    ni HKCU por su propia identidad. El proceso padre es el único que elimina
    snapshots del estado persistente después de recibir `verified=True`.
    """
    ordered = _ordered_known_ids(ids)
    if not ordered:
        return []
    if platform.system() != 'Windows':
        return [undo_tweak(tweak_id) for tweak_id in ordered]

    state = _load_state()
    if not _state_owner_matches(state):
        return [{'success': False, 'id': x, 'rollback_available': True, 'message': 'El rollback pertenece a otro usuario.'} for x in ordered]
    owner_sid = _current_user_sid()
    rows = []
    missing = []
    for tweak_id in ordered:
        record = (state.get('tweaks') or {}).get(tweak_id)
        if not isinstance(record, dict):
            missing.append(tweak_id)
            continue
        record_copy = json.loads(json.dumps(record, ensure_ascii=False))
        record_copy.setdefault('owner_user', state.get('user') or getpass.getuser())
        record_copy.setdefault('owner_sid', owner_sid)
        rows.append({'id': tweak_id, 'record': record_copy})

    jobs = PERSISTENT_DATA_DIR / 'rollback_jobs'
    try:
        jobs.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return [{'success': False, 'id': tweak_id, 'rollback_available': True, 'message': f'No se pudo preparar la elevación: {exc}'} for tweak_id in ordered]

    token = uuid.uuid4().hex
    request_path = jobs / f'{token}.request.json'
    result_path = jobs / f'{token}.result.json'
    request_path.write_text(json.dumps({'records': rows, 'result_path': str(result_path)}, ensure_ascii=False), encoding='utf-8')

    def ps_quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    helper_exe, arg_string = _elevated_helper_target('rollback', request_path)
    script = f"$p=Start-Process -FilePath {ps_quote(helper_exe)} -ArgumentList {ps_quote(arg_string)} -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    elevated_results = []
    try:
        proc = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            capture_output=True, text=True, timeout=180, creationflags=flags,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or '').strip()
            message = 'La elevación UAC fue cancelada o no pudo iniciarse.' + ((' ' + detail[:300]) if detail else '')
            elevated_results = [{'success': False, 'id': tweak_id, 'rollback_available': True, 'message': message, 'needs_elevation': True} for tweak_id in ordered if tweak_id not in missing]
        else:
            try:
                payload = json.loads(result_path.read_text(encoding='utf-8'))
                got = payload.get('results') if isinstance(payload, dict) else None
                if isinstance(got, list):
                    elevated_results = got
                else:
                    raise ValueError('resultado sin lista')
            except Exception as exc:
                elevated_results = [{'success': False, 'id': tweak_id, 'rollback_available': True, 'message': f'No se pudo leer el resultado del rollback elevado: {exc}'} for tweak_id in ordered if tweak_id not in missing]

        by_id = {str(row.get('id')): row for row in elevated_results if isinstance(row, dict)}
        results = []
        success_ids = []
        for tweak_id in ordered:
            if tweak_id in missing:
                row = {'success': False, 'id': tweak_id, 'rollback_available': False, 'message': 'No existe snapshot persistente para este tweak.'}
            else:
                row = by_id.get(tweak_id, {'success': False, 'id': tweak_id, 'rollback_available': True, 'message': 'El proceso elevado no devolvió resultado para este tweak.'})
            results.append(row)
            if row.get('success') and row.get('verified'):
                success_ids.append(tweak_id)

        if success_ids:
            latest = _load_state()
            changed = False
            for tweak_id in success_ids:
                if tweak_id in (latest.get('tweaks') or {}):
                    latest['tweaks'].pop(tweak_id, None)
                    changed = True
                    _audit(tweak_id, 'undo', True, by_id.get(tweak_id, {}).get('message') or 'Restaurado por helper elevado.')
            if changed:
                _save_state(latest)
        for row in results:
            if not row.get('success') and row.get('rollback_available'):
                _audit(row.get('id'), 'undo', False, row.get('message') or 'Rollback elevado pendiente.')
        return results
    except Exception as exc:
        return [{'success': False, 'id': tweak_id, 'rollback_available': True, 'message': f'No se pudo solicitar elevación UAC: {exc}', 'needs_elevation': True} for tweak_id in ordered]
    finally:
        for path in (request_path, result_path):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


def _remove_new_apply_snapshots(ids):
    if not ids:
        return
    state = _load_state()
    changed = False
    for tweak_id in ids:
        if tweak_id in (state.get('tweaks') or {}):
            state['tweaks'].pop(tweak_id, None)
            changed = True
    if changed:
        _save_state(state)


def _apply_many_elevated(ids):
    """Aplica sólo tweaks administrativos bajo UAC, conservando snapshots del usuario padre."""
    ordered = _ordered_known_ids(ids)
    if not ordered:
        return []
    if platform.system() != 'Windows':
        return [apply_tweak(tweak_id) for tweak_id in ordered]

    state = _load_state()
    if not _state_owner_matches(state):
        state = _default_state()
    rows = []
    by_id = {}
    newly_snapshotted = []
    for tweak_id in ordered:
        tweak = _tweak_by_id(tweak_id)
        pf = preflight_tweak(tweak_id)
        if not pf.get('applicable'):
            by_id[tweak_id] = {
                'success': False, 'id': tweak_id, 'status': 'unavailable', 'skipped': True,
                'message': pf.get('reason') or 'No disponible en este equipo.',
                'requires_explorer': bool((tweak or {}).get('requires_explorer')),
                'requires_restart': bool((tweak or {}).get('requires_restart')),
            }
            continue
        detected = detect_tweak(tweak_id)
        rollback_ids = saved_rollback_ids()
        if detected.get('applied') and tweak_id not in rollback_ids:
            by_id[tweak_id] = {
                'success': True, 'id': tweak_id, 'status': 'preexisting', 'changed': False,
                'message': 'Ya estaba aplicado antes de CorePulse.', 'rollback_available': False,
                'requires_explorer': bool(tweak.get('requires_explorer')),
                'requires_restart': bool(tweak.get('requires_restart')),
            }
            continue
        record_preexisted = tweak_id in (state.get('tweaks') or {})
        try:
            _save_original_if_needed(state, tweak)
            latest = _load_state()
            record = (latest.get('tweaks') or {}).get(tweak_id)
            if not isinstance(record, dict):
                raise RuntimeError('No se pudo releer el snapshot persistente.')
            if not record_preexisted:
                newly_snapshotted.append(tweak_id)
            rows.append({'id': tweak_id, 'record': json.loads(json.dumps(record, ensure_ascii=False)), 'record_preexisted': record_preexisted})
            state = latest
        except Exception as exc:
            by_id[tweak_id] = {
                'success': False, 'id': tweak_id, 'status': 'error',
                'message': f'No se pudo preparar el rollback antes de elevar: {exc}',
                'rollback_available': record_preexisted,
                'requires_explorer': bool(tweak.get('requires_explorer')),
                'requires_restart': bool(tweak.get('requires_restart')),
            }

    if not rows:
        return [by_id.get(x, {'success': False, 'id': x, 'status': 'error', 'message': 'Sin resultado.'}) for x in ordered]

    jobs = PERSISTENT_DATA_DIR / 'apply_jobs'
    try:
        jobs.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        _remove_new_apply_snapshots(newly_snapshotted)
        for row in rows:
            by_id[row['id']] = {'success': False, 'id': row['id'], 'status': 'error', 'message': f'No se pudo preparar la elevación: {exc}'}
        return [by_id.get(x) for x in ordered]

    token = uuid.uuid4().hex
    request_path = jobs / f'{token}.request.json'
    result_path = jobs / f'{token}.result.json'
    request_path.write_text(json.dumps({'records': rows, 'result_path': str(result_path)}, ensure_ascii=False), encoding='utf-8')

    def ps_quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    helper_exe, arg_string = _elevated_helper_target('apply', request_path)
    script = f"$p=Start-Process -FilePath {ps_quote(helper_exe)} -ArgumentList {ps_quote(arg_string)} -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        proc = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            capture_output=True, text=True, timeout=240, creationflags=flags,
        )
        if proc.returncode != 0:
            _remove_new_apply_snapshots(newly_snapshotted)
            detail = (proc.stderr or proc.stdout or '').strip()
            message = 'La elevación UAC fue cancelada o no pudo iniciarse.' + ((' ' + detail[:300]) if detail else '')
            for row in rows:
                by_id[row['id']] = {
                    'success': False, 'id': row['id'], 'status': 'error', 'needs_elevation': True,
                    'message': message, 'rollback_available': bool(row.get('record_preexisted')),
                }
        else:
            try:
                payload = json.loads(result_path.read_text(encoding='utf-8'))
                got = payload.get('results') if isinstance(payload, dict) else None
                if not isinstance(got, list):
                    raise ValueError('resultado sin lista')
            except Exception as exc:
                got = [{'success': False, 'id': row['id'], 'status': 'error', 'message': f'No se pudo leer el resultado elevado: {exc}'} for row in rows]
            elevated = {str(row.get('id')): row for row in got if isinstance(row, dict)}
            cleanup = []
            for row in rows:
                tweak_id = row['id']
                result = elevated.get(tweak_id, {'success': False, 'id': tweak_id, 'status': 'error', 'message': 'El proceso elevado no devolvió resultado.'})
                by_id[tweak_id] = result
                if not result.get('success') and result.get('rolled_back') and not row.get('record_preexisted'):
                    cleanup.append(tweak_id)
                _audit(tweak_id, 'apply', bool(result.get('success')), result.get('message') or '')
            _remove_new_apply_snapshots(cleanup)
        return [by_id.get(x, {'success': False, 'id': x, 'status': 'error', 'message': 'Aplicación sin resultado.'}) for x in ordered]
    except Exception as exc:
        _remove_new_apply_snapshots(newly_snapshotted)
        for row in rows:
            by_id[row['id']] = {'success': False, 'id': row['id'], 'status': 'error', 'message': f'No se pudo solicitar elevación UAC: {exc}', 'needs_elevation': True}
        return [by_id.get(x) for x in ordered]
    finally:
        for path in (request_path, result_path):
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


def apply_many(ids, auto_elevate=True):
    """Aplica un lote universal: HKCU en el usuario y sólo HKLM/políticas bajo UAC."""
    ordered = _ordered_known_ids(ids)
    if not ordered:
        return []
    if not (auto_elevate and platform.system() == 'Windows' and not is_admin()):
        return [apply_tweak(tweak_id) for tweak_id in ordered]
    user_ids = [x for x in ordered if not (_tweak_by_id(x) or {}).get('requires_admin')]
    admin_ids = [x for x in ordered if (_tweak_by_id(x) or {}).get('requires_admin')]
    by_id = {}
    for row in [apply_tweak(x) for x in user_ids]:
        by_id[str(row.get('id'))] = row
    for row in (_apply_many_elevated(admin_ids) if admin_ids else []):
        by_id[str(row.get('id'))] = row
    return [by_id.get(x, {'success': False, 'id': x, 'status': 'error', 'message': 'Aplicación sin resultado.'}) for x in ordered]


def undo_many(ids, auto_elevate=True):
    """Deshace snapshots sin elevar jamás los tweaks HKCU innecesariamente."""
    ordered = _ordered_known_ids(ids)
    if not ordered:
        return []
    if not (auto_elevate and platform.system() == 'Windows' and not is_admin()):
        return [undo_tweak(tweak_id) for tweak_id in ordered]

    user_ids = [x for x in ordered if not (_tweak_by_id(x) or {}).get('requires_admin')]
    admin_ids = [x for x in ordered if (_tweak_by_id(x) or {}).get('requires_admin')]
    by_id = {}
    # Primero restaura HKCU bajo el usuario ORIGINAL. Sólo después se solicita UAC
    # para HKLM/políticas. Un tweak administrativo no arrastra al resto del lote.
    for row in [undo_tweak(x) for x in user_ids]:
        by_id[str(row.get('id'))] = row
    for row in (_undo_many_elevated(admin_ids) if admin_ids else []):
        by_id[str(row.get('id'))] = row
    return [by_id.get(x, {'success': False, 'id': x, 'rollback_available': True, 'message': 'Rollback sin resultado.'}) for x in ordered]


def undo_all_saved(auto_elevate=True):
    """Restaura todos los cambios que tienen snapshot persistente de CorePulse."""
    rollback_ids = saved_rollback_ids()
    ordered = [item['id'] for item in TWEAKS if item['id'] in rollback_ids]
    return undo_many(ordered, auto_elevate=auto_elevate)



def _compact_value(value, *, existed=True, limit=72):
    """Representación corta y estable para la UI del centro de restauración."""
    if not existed:
        return 'NO EXISTÍA'
    if value is None:
        text = 'None'
    elif isinstance(value, str):
        text = value if value else '(cadena vacía)'
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            text = repr(value)
    text = str(text).replace('\r', ' ').replace('\n', ' ').strip()
    if len(text) > int(limit):
        text = text[: max(1, int(limit) - 1)] + '…'
    return text


def _rollback_change_details_from_record(tweak, record):
    """Formatea un snapshot ya cargado, sin volver a tocar disco."""
    if not isinstance(record, dict) or not isinstance(tweak, dict):
        return []
    targets = {}
    for hive_name, path, name, desired, kind in tweak.get('ops', ()):
        targets[(str(hive_name), str(path), str(name))] = {
            'desired': desired,
            'kind': kind,
        }

    rows = []
    for original in record.get('originals', []):
        key = (
            str(original.get('hive') or ''),
            str(original.get('path') or ''),
            str(original.get('name') or ''),
        )
        target = targets.get(key, {})
        label_name = original.get('name')
        location = f"{key[0]}\\{key[1]}"
        if label_name:
            location += f" · {label_name}"
        rows.append({
            'type': 'registry',
            'location': location,
            'before': _compact_value(original.get('value'), existed=bool(original.get('existed'))),
            'applied': _compact_value(target.get('desired'), existed=True) if 'desired' in target else 'N/A',
            'before_existed': bool(original.get('existed')),
            'kind': target.get('kind'),
        })

    command_snapshot = record.get('command_snapshot')
    if isinstance(command_snapshot, dict):
        safe_snapshot = {k: v for k, v in command_snapshot.items() if k != 'strategy'}
        rows.append({
            'type': 'command',
            'location': 'Estado de sistema capturado antes de la acción',
            'before': _compact_value(safe_snapshot, existed=True, limit=180),
            'applied': 'Acción definida por CorePulse',
            'before_existed': True,
            'kind': str(command_snapshot.get('strategy') or 'command'),
        })
    return rows


def rollback_change_details(tweak_id):
    """Devuelve el snapshot previo y el objetivo aplicado sin modificar Windows.

    Esta API existe para que la UI pueda explicar exactamente qué sabe restaurar
    CorePulse. Nunca inventa un valor predeterminado: ``before`` proviene del
    snapshot persistente y ``applied`` del catálogo versionado del tweak.
    """
    tweak_id = str(tweak_id or '')
    state = _load_state()
    if not _state_owner_matches(state):
        return []
    record = (state.get('tweaks') or {}).get(tweak_id)
    tweak = _tweak_by_id(tweak_id)
    return _rollback_change_details_from_record(tweak, record)


def _rollback_original_matches(tweak, record):
    """True sólo cuando el estado actual coincide con el snapshot previo."""
    if not isinstance(tweak, dict) or not isinstance(record, dict):
        return False, ['Snapshot inválido.']
    problems = []
    registry_mismatches = _verify_registry_originals(record)
    if registry_mismatches:
        problems.append('Registro distinto al estado previo: ' + ', '.join(registry_mismatches[:4]))
    try:
        problems.extend(_verify_command_snapshot(tweak, record))
    except Exception as exc:
        problems.append(f'No se pudo verificar la acción del sistema: {exc}')
    return not problems, problems


def _rollback_last_events(limit=1000):
    """Último evento de auditoría por tweak, tolerante a líneas dañadas."""
    events = tweak_history(limit=limit)
    latest = {}
    for row in events:  # tweak_history ya devuelve más reciente primero
        tweak_id = str(row.get('tweak_id') or '')
        if tweak_id and tweak_id not in latest:
            latest[tweak_id] = row
    return latest


def rollback_inventory():
    """Inventario activo de rollbacks con detección de cambios externos.

    Estados:
    - ``applied``: el tweak sigue exactamente en el objetivo de CorePulse;
    - ``restored_externally``: el equipo ya coincide con el snapshot original,
      aunque CorePulse todavía conserva el registro para poder verificar/cerrar;
    - ``modified_externally``: el estado ya no coincide ni con el objetivo ni con
      el snapshot original. Restaurar requerirá confirmación explícita en la UI;
    - ``unavailable``: el snapshot existe, pero no puede evaluarse en el entorno.
    """
    state = _load_state()
    if not _state_owner_matches(state):
        return []
    records = state.get('tweaks') or {}
    last_events = _rollback_last_events()
    rows = []
    for tweak_id, record in records.items():
        tweak = _tweak_by_id(tweak_id)
        if not isinstance(record, dict):
            continue
        if not isinstance(tweak, dict):
            rows.append({
                'id': str(tweak_id), 'title': str(tweak_id), 'category': 'Desconocido',
                'risk': 'N/A', 'state': 'unavailable', 'state_label': 'NO DISPONIBLE',
                'saved_at': float(record.get('saved_at') or 0.0),
                'requires_admin': False, 'requires_restart': False, 'requires_explorer': False,
                'undo_mode': str(record.get('undo_mode') or 'exact'),
                'detail': 'El snapshot existe, pero este build ya no conoce el tweak.',
                'changes': [], 'last_event': last_events.get(str(tweak_id)),
            })
            continue

        try:
            detected = detect_tweak(tweak_id)
        except Exception as exc:
            detected = {'status': 'unavailable', 'applied': False, 'detail': str(exc)}
        try:
            original_matches, original_problems = _rollback_original_matches(tweak, record)
        except Exception as exc:
            original_matches, original_problems = False, [str(exc)]

        if detected.get('applied'):
            state_name = 'applied'
            state_label = 'APLICADO POR COREPULSE'
            detail = 'El estado actual coincide con el objetivo del tweak y el rollback exacto sigue disponible.'
        elif original_matches:
            state_name = 'restored_externally'
            state_label = 'RESTAURADO EXTERNAMENTE'
            detail = 'El estado actual ya coincide con el snapshot previo. CorePulse puede verificarlo y cerrar el rollback.'
        elif detected.get('status') == 'unavailable' and not is_windows_11():
            state_name = 'unavailable'
            state_label = 'NO DISPONIBLE'
            detail = detected.get('detail') or 'No se puede evaluar este rollback en el entorno actual.'
        else:
            state_name = 'modified_externally'
            state_label = 'MODIFICADO EXTERNAMENTE'
            detail = (
                'El estado actual no coincide ni con el objetivo aplicado por CorePulse ni con el snapshot previo. '
                'Restaurar sobrescribirá el cambio posterior.'
            )
            if original_problems:
                detail += ' ' + '; '.join(str(x) for x in original_problems[:2])

        rows.append({
            'id': tweak['id'],
            'title': tweak['title'],
            'description': tweak.get('description') or '',
            'category': tweak.get('category') or '',
            'risk': tweak.get('risk') or 'Bajo',
            'state': state_name,
            'state_label': state_label,
            'saved_at': float(record.get('saved_at') or 0.0),
            'owner_user': record.get('owner_user') or state.get('user'),
            'requires_admin': bool(tweak.get('requires_admin')),
            'requires_restart': bool(tweak.get('requires_restart')),
            'requires_explorer': bool(tweak.get('requires_explorer')),
            'undo_mode': str(record.get('undo_mode') or tweak.get('undo_mode') or 'exact'),
            'detail': detail,
            'changes': _rollback_change_details_from_record(tweak, record),
            'last_event': last_events.get(tweak['id']),
        })

    order = {'modified_externally': 0, 'applied': 1, 'restored_externally': 2, 'unavailable': 3}
    rows.sort(key=lambda row: (order.get(row.get('state'), 9), -float(row.get('saved_at') or 0.0), str(row.get('title') or '').lower()))
    return rows


def tweak_history(limit=200, tweak_id=None):
    """Lee el historial persistente más reciente sin cargar el archivo completo."""
    _migrate_legacy_storage_once()
    try:
        limit = max(1, min(int(limit), 2000))
    except Exception:
        limit = 200
    wanted = str(tweak_id) if tweak_id is not None else None
    if not HISTORY_PATH.exists():
        return []

    rows = deque(maxlen=limit)
    try:
        with HISTORY_PATH.open('r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                current_id = str(row.get('tweak_id') or '')
                if wanted is not None and current_id != wanted:
                    continue
                rows.append(row)
    except Exception:
        return []

    catalog_by_id = {item['id']: item for item in TWEAKS}
    output = []
    for row in reversed(rows):
        current_id = str(row.get('tweak_id') or '')
        item = catalog_by_id.get(current_id, {})
        action = str(row.get('action') or '').lower()
        success = bool(row.get('success'))
        if action == 'apply' and success:
            event_label = 'APLICADO'
        elif action == 'undo' and success:
            event_label = 'REVERTIDO'
        elif action == 'apply':
            event_label = 'ERROR AL APLICAR'
        elif action == 'undo':
            event_label = 'ROLLBACK PENDIENTE'
        else:
            event_label = action.upper() or 'EVENTO'
        output.append({
            **row,
            'tweak_id': current_id,
            'title': item.get('title') or current_id or 'Tweak',
            'category': item.get('category') or '',
            'risk': item.get('risk') or '',
            'event_label': event_label,
        })
    return output


def rollback_summary():
    """Resumen compacto para tarjetas del Restore Center."""
    inventory = rollback_inventory()
    history = tweak_history(limit=2000)
    counts = {
        'total': len(inventory),
        'applied': 0,
        'modified_externally': 0,
        'restored_externally': 0,
        'unavailable': 0,
        'history_events': len(history),
    }
    for row in inventory:
        key = str(row.get('state') or '')
        if key in counts:
            counts[key] += 1
    return counts

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
