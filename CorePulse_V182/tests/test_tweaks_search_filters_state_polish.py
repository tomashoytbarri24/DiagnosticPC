"""V100 — búsqueda/filtros de Tweaks sin reconstruir filas."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f'[PASS] {name}')


def main():
    panel=(ROOT/'gui'/'windows_tweaks_panel.py').read_text(encoding='utf-8')
    check('version', VERSION.isdecimal())
    check('search_entry', "placeholder_text='Nombre, descripción, categoría o ID…'" in panel)
    check('state_filter', 'Aplicados por CorePulse' in panel and 'Ya estaban aplicados' in panel and 'No verificables' in panel)
    check('category_filter', "('Todas', *CATEGORY_ORDER)" in panel)
    check('risk_filter', "('Todos', 'Bajo', 'Medio', 'Alto', 'Crítico')" in panel)
    check('compatible_only', "text='Solo compatibles con este equipo'" in panel)
    check('dynamic_count', "self.lbl_filter_count.configure(text=f'{len(visible_ids)} de {len(self.items)}')" in panel)
    check('no_row_recreation', 'def _apply_filters' in panel and 'row.pack_forget()' in panel and "row.pack(fill='x', padx=9, pady=4)" in panel)
    check('filters_persist_restore_center', 'self.filter_bar.pack(' in panel and 'self.filter_bar' in panel.split('def _open_restore_center',1)[1].split('def _close_restore_center',1)[0])
    check('detected_state_cache', 'self._detected_states = dict(statuses)' in panel)
    check('compatibility_cache', 'self._compatible_ids_cache = set(compatible_ids)' in panel)
    check('filter_debounce', 'def _schedule_filter_apply' in panel and "trace_add('write'" in panel)
    print('\nRESULTADO: PASS (12 checks)')


if __name__ == '__main__':
    main()
