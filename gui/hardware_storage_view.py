"""Organiza la presentación de hardware y almacenamiento usando únicamente datos ya medidos."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import types
DESIGN_ID = 'COREPULSE_PRO_HARDWARE_STORAGE'
FONT = 'Segoe UI'
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#b8c4d4')
MUTED = theme_color('#7f91a8')
SURFACE = theme_color('#0d1828')
BORDER = theme_color('#1b3048')
TRACK = theme_color('#15243a')
CYAN = '#14b8ff'
GREEN = '#1fd18b'
PURPLE = '#9a62ff'
AMBER = '#f3b54a'
RED = '#ff5d6c'

def _cfg(widget, **kwargs):
    if widget is None:
        return
    try:
        widget.configure(**kwargs)
    except Exception:
        pass

def _float(value):
    try:
        return float(value) if value is not None else None
    except Exception:
        return None

def _fmt(value, digits=1, suffix=''):
    v = _float(value)
    if v is None:
        return 'N/A'
    return f'{v:.{digits}f}{suffix}'

def _temperature_color(component, value, normal):
    v = _float(value)
    if v is None:
        return MUTED
    component = str(component or '').upper()
    if component == 'CPU':
        if v >= 95:
            return RED
        if v >= 80:
            return AMBER
    elif component == 'GPU':
        if v >= 95:
            return RED
        if v >= 80:
            return AMBER
    return normal

def _style_cards(app):
    specs = ((app.card_cpu, app.lbl_cpu, app.lbl_cpu_title, app.lbl_cpu_temp, app.bar_cpu, CYAN), (app.card_ram, app.lbl_ram, app.lbl_ram_title, app.lbl_ram_gb, app.bar_ram, GREEN), (app.card_gpu, app.lbl_gpu, app.lbl_gpu_title, app.lbl_gpu_temp, app.bar_gpu, PURPLE))
    for card, value, title, detail, bar, accent in specs:
        _cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=13, height=126)
        try:
            card.pack_propagate(False)
        except Exception:
            pass
        _cfg(title, font=(FONT, 9, 'bold'), text_color=TEXT_2, justify='left')
        _cfg(value, font=(FONT, 25, 'bold'), text_color=TEXT)
        _cfg(detail, font=(FONT, 9, 'bold'), text_color=accent, justify='left')
        _cfg(bar, height=6, progress_color=accent, fg_color=TRACK)

def _telemetry_text(app, telemetry):
    telemetry = telemetry or {}
    cpu_name = str(telemetry.get('cpu_name') or 'N/A')
    gpu_name = str(telemetry.get('gpu_name') or 'N/A')
    cpu_temp = _float(telemetry.get('cpu_temp'))
    cpu_ghz = _float(telemetry.get('cpu_ghz'))
    ram_used = _float(telemetry.get('ram_used_gb'))
    ram_total = _float(telemetry.get('ram_total_gb'))
    gpu_temp = _float(telemetry.get('gpu_temp'))
    gpu_vram_total = _float(telemetry.get('gpu_vram_gb'))
    _cfg(app.lbl_cpu_title, text=f'CPU\n{cpu_name}', font=(FONT, 9, 'bold'), text_color=TEXT_2)
    cpu_parts = []
    if cpu_temp is not None:
        cpu_parts.append(f'{cpu_temp:.1f} °C  Temperatura')
    if cpu_ghz is not None:
        cpu_parts.append(f'{cpu_ghz:.2f} GHz  Frecuencia')
    _cfg(app.lbl_cpu_temp, text='   ·   '.join(cpu_parts) if cpu_parts else 'Temperatura / Frecuencia: N/A', font=(FONT, 9, 'bold'), text_color=_temperature_color('CPU', cpu_temp, CYAN))
    _cfg(app.lbl_ram_title, text='MEMORIA RAM\nUso físico del sistema', font=(FONT, 9, 'bold'), text_color=TEXT_2)
    if ram_used is not None and ram_total is not None:
        ram_detail = f'{ram_used:.2f} GB usados   ·   {ram_total:.2f} GB total'
    else:
        ram_detail = 'Memoria utilizada / total: N/A'
    _cfg(app.lbl_ram_gb, text=ram_detail, font=(FONT, 9, 'bold'), text_color=GREEN)
    _cfg(app.lbl_gpu_title, text=f'GPU\n{gpu_name}', font=(FONT, 9, 'bold'), text_color=TEXT_2)
    gpu_parts = []
    if gpu_temp is not None:
        gpu_parts.append(f'{gpu_temp:.1f} °C  Temperatura')
    if gpu_vram_total is not None:
        gpu_parts.append(f'{gpu_vram_total:.1f} GB  VRAM total')
    _cfg(app.lbl_gpu_temp, text='   ·   '.join(gpu_parts) if gpu_parts else 'Temperatura / VRAM: N/A', font=(FONT, 9, 'bold'), text_color=_temperature_color('GPU', gpu_temp, PURPLE))

def _install_telemetry_presentation(app):
    if getattr(app, '_hardware_view_telemetry_wrapped', False):
        return
    original = app.apply_telemetry_to_ui

    def wrapped(self, telemetry, disks):
        original(telemetry, disks)
        _telemetry_text(self, telemetry)
    app.apply_telemetry_to_ui = types.MethodType(wrapped, app)
    app._hardware_view_telemetry_wrapped = True
    try:
        _telemetry_text(app, getattr(app, 'latest_telemetry', {}) or {})
    except Exception:
        pass

def _strip_disk_prefix(text):
    value = str(text or '').strip()
    prefixes = ('▰  ', '▰ ', '💾 ', '▱  ', '▱ ')
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if value.startswith(prefix):
                value = value[len(prefix):].strip()
                changed = True
    return value

def _style_storage(app, disks_data=None):
    by_index = {}
    for d in disks_data or []:
        try:
            by_index[d.get('index')] = d
        except Exception:
            pass
    _cfg(getattr(app, 'scroll_disks', None), fg_color='transparent')
    for idx, widgets in getattr(app, 'disk_widgets', {}).items():
        card = widgets.get('card')
        name = widgets.get('lbl_name')
        badge = widgets.get('lbl_badge')
        exact = widgets.get('lbl_exact')
        bar = widgets.get('bar')
        details = widgets.get('btn_details')
        d = by_index.get(idx, {})
        _cfg(card, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=12)
        try:
            card.pack_propagate(True)
            card.pack_configure(fill='x', expand=True, padx=2, pady=4)
        except Exception:
            pass
        model = d.get('model') or d.get('name')
        mounts = d.get('mount_points')
        total = _float(d.get('total_gb'))
        used = _float(d.get('used_gb'))
        pct = _float(d.get('used_percent'))
        temp = _float(d.get('temperature_c'))
        health = _float(d.get('health'))
        if not model and name is not None:
            model = _strip_disk_prefix(getattr(name, 'cget')('text'))
        line1 = str(model or f'Disco {idx}')
        if mounts:
            line1 += f'   ·   {mounts}'
        if total is not None:
            line1 += f'   ·   {total:.2f} GB'
        _cfg(name, text=line1, font=(FONT, 10, 'bold'), text_color=TEXT, anchor='w')
        free = None
        if total is not None and used is not None:
            free = max(0.0, total - used)
        parts = []
        if used is not None:
            parts.append(f'Usado  {used:.2f} GB')
        if free is not None:
            parts.append(f'Disponible  {free:.2f} GB')
        if pct is not None:
            parts.append(f'{pct:.1f}%')
        if temp is not None:
            parts.append(f'{temp:.0f} °C')
        _cfg(exact, text='   |   '.join(parts) if parts else 'Información de capacidad: N/A', font=(FONT, 9), text_color=CYAN, anchor='w')
        if health is not None:
            _cfg(badge, text=f'Salud SMART  {health:.0f}%', font=(FONT, 10, 'bold'))
        else:
            _cfg(badge, text='Salud SMART  N/A', font=(FONT, 10, 'bold'), text_color=MUTED)
        _cfg(bar, height=6, progress_color=CYAN, fg_color=TRACK)
        _cfg(details, text='Ver detalles', width=92, height=24, fg_color=theme_color('#0d2942'), hover_color=theme_color('#164f7d'), border_width=1, border_color=theme_color('#1d5278'), text_color=theme_color('#75d2f7'), font=('Segoe UI', 8, 'bold'), corner_radius=7)
        try:
            header = getattr(name, 'master', None)
            if header is not None:
                header.pack_configure(fill='x', padx=12, pady=(8, 3))
            exact.pack_configure(anchor='w', padx=12, pady=(0, 5))
            bar.pack_configure(fill='x', padx=12, pady=(0, 8))
        except Exception:
            pass

def _install_storage_presentation(app):
    if getattr(app, '_hardware_view_storage_wrapped', False):
        return
    original = app.update_disks_ui

    def wrapped(self, disks_data):
        original(disks_data)
        _style_storage(self, disks_data)
        sync = getattr(self, '_sync_storage_height_callback', None)
        if callable(sync):
            try:
                sync()
            except Exception:
                pass
    app.update_disks_ui = types.MethodType(wrapped, app)
    app._hardware_view_storage_wrapped = True
    try:
        _style_storage(app, getattr(app, 'latest_disks', []) or [])
    except Exception:
        pass

def apply_hardware_storage_information_architecture(app):
    if getattr(app, '_hardware_view_active', False):
        return
    _style_cards(app)
    _install_telemetry_presentation(app)
    _install_storage_presentation(app)
    app._hardware_view_active = True
    app._corepulse_design_id = DESIGN_ID
