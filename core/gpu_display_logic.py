"""Reglas puras de presentación para datos GPU.

No consulta hardware ni depende de Tk. Mantiene separada la interpretación de
inventario Windows de la telemetría certificada para que la UI no convierta
limitaciones de WMI en datos de hardware autoritativos.
"""
from __future__ import annotations


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def gb_from_mb(value):
    number = _number(value)
    return None if number is None else number / 1024.0


def gb_from_bytes(value):
    number = _number(value)
    return None if number is None else number / (1024.0 ** 3)


def windows_status_text(value):
    raw = str(value or '').strip()
    if not raw:
        return 'N/A'
    labels = {
        'ok': 'Funcionando correctamente',
        'degraded': 'Rendimiento degradado',
        'error': 'Error reportado por Windows',
        'pred fail': 'Posible fallo reportado',
        'starting': 'Iniciando',
        'stopping': 'Deteniéndose',
        'stressed': 'Bajo carga',
        'nonrecover': 'Error no recuperable',
        'no contact': 'Sin comunicación',
        'lost comm': 'Comunicación perdida',
        'unknown': 'Estado desconocido',
    }
    return labels.get(raw.casefold(), raw)


def human_gpu_hardware_type(value):
    raw = str(value or '').strip()
    if not raw:
        return 'N/A'
    known = {
        'gpunvidia': 'NVIDIA · LibreHardwareMonitor',
        'gpuamd': 'AMD · LibreHardwareMonitor',
        'gpuintel': 'Intel · LibreHardwareMonitor',
    }
    key = raw.casefold()
    if key in known:
        return known[key]
    if key.startswith('gpu') and len(raw) > 3:
        return f'{raw[3:]} · LibreHardwareMonitor'
    return raw


def wmi_vram_presentation(os_bytes, sensor_total_mb=None):
    """Retorna ``(texto, limitado)`` sin promover AdapterRAM sobre un sensor real.

    ``Win32_VideoController.AdapterRAM`` es un entero de 32 bits y puede quedarse
    alrededor de 4 GiB en adaptadores con más memoria. La limitación sólo se
    declara cuando una lectura real del mismo adaptador demuestra una capacidad
    claramente superior.
    """
    wmi_gb = gb_from_bytes(os_bytes)
    sensor_gb = gb_from_mb(sensor_total_mb)
    if wmi_gb is None:
        return 'N/A', False
    limited = (
        sensor_gb is not None
        and sensor_gb > 4.25
        and wmi_gb <= 4.01
        and sensor_gb > wmi_gb + 0.5
    )
    if limited:
        return f'{wmi_gb:.2f} GB · limitado por WMI', True
    return f'{wmi_gb:.2f} GB', False


def active_display_on_other_gpu(selected_gpu, all_gpus):
    """True si Windows expone un modo de pantalla activo en otro adaptador."""
    for gpu in all_gpus or []:
        if gpu is selected_gpu:
            continue
        os_inv = gpu.get('os_inventory') if isinstance(gpu, dict) and isinstance(gpu.get('os_inventory'), dict) else {}
        width = _number(os_inv.get('current_horizontal_resolution'))
        height = _number(os_inv.get('current_vertical_resolution'))
        mode = str(os_inv.get('video_mode_description') or '').strip()
        if (width is not None and height is not None) or mode:
            return True
    return False


__all__ = [
    'active_display_on_other_gpu',
    'gb_from_bytes',
    'gb_from_mb',
    'human_gpu_hardware_type',
    'windows_status_text',
    'wmi_vram_presentation',
]
