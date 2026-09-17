"""V100 — Gaming es un hub visual propio sin perder REAL_OR_NA."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, cond):
    ok = bool(cond)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok


def main():
    gaming = (ROOT/'gui'/'gaming_panel.py').read_text(encoding='utf-8')
    perf = (ROOT/'gui'/'health_center_panel.py').read_text(encoding='utf-8')
    overlay = (ROOT/'gui'/'overlay_config_panel.py').read_text(encoding='utf-8')
    theme = (ROOT/'core'/'theme_manager.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION == '103'),
        check('gaming_duplicate_summary_removed', 'self._build_summary(body)' not in gaming and 'Gaming listo' not in gaming),
        check('single_state_source_is_performance_panel', "status = manager.status()" in perf and "text='Estado de la sesión'" in perf),
        check('active_game_is_shown_once', "('JUEGO ACTIVO', active_game_text" in perf and "'JUEGOS ACTIVOS'" not in perf),
        check('gaming_header_is_compact', 'Juego actual, perfil y estado del equipo en una sola vista' in gaming and "('stability', 'Estabilidad'" in gaming and "('overlay', 'Overlay'" in gaming),
        check('performance_has_session_module', "text='Estado de la sesión'" in perf),
        check('performance_profiles_are_cards', "profile_specs = (" in perf and "gaming_profile_cards" in perf),
        check('four_power_modes_are_explained', 'Alto rendimiento' in perf and 'Máximo rendimiento' in perf and 'Ahorro de energía' in perf and "('AUTO', 'Automático'" not in perf),
        check('game_boost_is_separate_module', "text='Game Boost'" in perf and "switch_grid" in perf),
        check('technical_exe_entry_hidden', 'self.performance_exe_entry = None' in perf),
        check('exclude_uses_file_picker', "title='Selecciona el ejecutable que quieres excluir'" in perf),
        check('library_has_visual_state_badges', "state_text = 'Jugando ahora' if active else ('Excluido' if excluded else 'Disponible')" in perf and "kind_text = 'Manual' if manual else 'Detectado'" in perf),
        check('overlay_has_preview', "text='VISTA PREVIA'" in overlay and 'self.preview_text' in overlay),
        check('preview_does_not_invent_fps', "FPS        —" in overlay and "CPU        —%" in overlay and "GPU        —%" in overlay),
        check('overlay_has_explained_metrics', "Fotogramas por segundo" in overlay and "Caídas de rendimiento" in overlay),
        check('overlay_preserves_real_fps_policy', 'REAL_FPS_OR_NA_ONLY' in overlay),
        check('gaming_surface_has_light_theme_mapping', "'#091726': '#e8eef4'" in theme),
        check('cached_gaming_tabs_preserved', '_tab_hosts' in gaming and '_tab_panels' in gaming and 'place_forget()' in gaming),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
