"""Define la presentación visual y semántica del overlay RTSS."""
# Código refactorizado: nombres estables y documentación en español.
from core.version import VERSION_LABEL
WHITE = 'F8FAFC'
LABEL = 'D7E1EE'
DIM = '7C8EA6'
DIM_LIGHT = 'A8B6C8'
FPS = '2DD4FF'
CPU = '38BDF8'
RAM = '34D399'
GPU = 'D946EF'
SSD = 'F59E0B'
PANEL_BG = 594205
PANEL_FG = 16317180
OSD_X = 20
OSD_Y = 20
OSD_PIXEL = 1
DIVIDER_COLOR = '355A7A'
DIVIDER = '============================================'

def _fmt(value, digits=0, suffix=''):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return 'N/A'
    return f'{value:.{digits}f}{suffix}'

def _tags():
    return f'<C0={FPS}><C1={CPU}><C2={RAM}><C3={GPU}><C4={SSD}><C5={WHITE}><C6={LABEL}><C7={DIM}><C8={DIM_LIGHT}><C10={DIVIDER_COLOR}>\r'

def _compact(data, prefs):
    lines = [_tags(), f"<C5>COREPULSE<C>  <C8>{data.get('exe') or 'Aplicacion 3D'}<C>"]
    frame = []
    if prefs.get('show_fps', True):
        frame.append(f"<C6>FPS<C> <C0>{_fmt(data.get('fps'), 0)}<C>")
    if prefs.get('show_frametime', True):
        frame.append(f"<C6>FT<C> <C0>{_fmt(data.get('frametime'), 2, ' ms')}<C>")
    if prefs.get('show_1pct_low', True):
        frame.append(f"<C6>1% LOW<C> <C0>{_fmt(data.get('low_1'), 0)}<C>")
    if frame:
        lines.append('   '.join(frame))
    comp = []
    if prefs.get('show_cpu', True):
        comp.append(f"<C6>CPU<C> <C1>{_fmt(data.get('cpu_usage'), 0, '%')} {_fmt(data.get('cpu_temp'), 0, 'C')}<C>")
    if prefs.get('show_ram', True):
        comp.append(f"<C6>RAM<C> <C2>{_fmt(data.get('ram_usage'), 0, '%')}<C>")
    if prefs.get('show_gpu', True):
        comp.append(f"<C6>GPU<C> <C3>{_fmt(data.get('gpu_usage'), 0, '%')} {_fmt(data.get('gpu_temp'), 0, 'C')}<C>")
    if prefs.get('show_storage', True):
        comp.append(f"<C6>SSD<C> <C4>{_fmt(data.get('ssd_temp'), 0, 'C')} {_fmt(data.get('ssd_life'), 0, '%')}<C>")
    if comp:
        lines.append('   '.join(comp))
    if len(lines) <= 2:
        lines.append('<C7>Sin métricas seleccionadas<C>')
    lines.append('<C7>REAL_OR_NA · RTSS<C>')
    return '\n'.join(lines)

def build_original_overlay(data, prefs=None):
    prefs = prefs if isinstance(prefs, dict) else {}
    if str(prefs.get('layout', 'FULL')).upper() == 'COMPACT':
        return _compact(data, prefs)
    lines = [_tags(), '<C5>COREPULSE<C>                              <C8>RTSS<C>', f"<C6>{data.get('exe') or 'Aplicacion 3D'}<C>"]
    if prefs.get('show_fps', True) or prefs.get('show_frametime', True) or prefs.get('show_1pct_low', True):
        lines += [f'<C10>{DIVIDER}<C>', '<C8>FRAME PRESENTATION<C>']
        row = []
        if prefs.get('show_fps', True):
            row.append(f"<C6>FPS<C> <C0>{_fmt(data.get('fps'), 0)}<C>")
        if prefs.get('show_frametime', True):
            row.append(f"<C6>FT<C> <C0>{_fmt(data.get('frametime'), 2, ' ms')}<C>")
        if row:
            lines.append('                 '.join(row))
        if prefs.get('show_1pct_low', True):
            lines.append(f"<C6>1% LOW<C> <C0>{_fmt(data.get('low_1'), 0)}<C>")
    comp = []
    secondary = []
    if prefs.get('show_cpu', True):
        comp.append(f"<C6>CPU<C> <C1>{_fmt(data.get('cpu_usage'), 0, '%')} {_fmt(data.get('cpu_temp'), 0, 'C')}<C>")
        secondary.append(f"<C6>CPU GHz<C> <C1>{_fmt(data.get('cpu_ghz'), 2)}<C>")
    if prefs.get('show_ram', True):
        comp.append(f"<C6>RAM<C> <C2>{_fmt(data.get('ram_usage'), 0, '%')}<C>")
    if prefs.get('show_gpu', True):
        comp.append(f"<C6>GPU<C> <C3>{_fmt(data.get('gpu_usage'), 0, '%')} {_fmt(data.get('gpu_temp'), 0, 'C')}<C>")
        secondary.append(f"<C6>GPU HOT<C> <C3>{_fmt(data.get('gpu_hotspot'), 0, 'C')}<C>")
    if prefs.get('show_storage', True):
        comp.append(f"<C6>SSD<C> <C4>{_fmt(data.get('ssd_temp'), 0, 'C')}<C>")
        secondary.append(f"<C6>SSD LIFE<C> <C4>{_fmt(data.get('ssd_life'), 0, '%')}<C>")
    if comp:
        lines += [f'<C10>{DIVIDER}<C>', '<C8>HARDWARE<C>', '    '.join(comp)]
        if secondary:
            lines.append('   <C8>•<C>   '.join(secondary))
    if len(lines) <= 3:
        lines.append('<C7>Sin métricas seleccionadas<C>')
    lines += [f'<C10>{DIVIDER}<C>', '<C6>Estado<C>  <C0>RTSS conectado<C>', f'<C7>CorePulse {VERSION_LABEL} · REAL_OR_NA<C>']
    return '\n'.join(lines)
