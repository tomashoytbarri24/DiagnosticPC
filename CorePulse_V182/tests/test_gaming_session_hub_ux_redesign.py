"""V100 — Gaming Session Hub UX Redesign."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    gaming = (ROOT / 'gui' / 'gaming_panel.py').read_text(encoding='utf-8')
    health = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    overlay = (ROOT / 'gui' / 'overlay_config_panel.py').read_text(encoding='utf-8')

    home = health.split('    def _render_gaming_comfort_home', 1)[1].split('    def ', 1)[0]
    stability = health.split('    def _render_gaming_stability_section', 1)[1].split('    def ', 1)[0]
    library = health.split('    def _render_registered_games', 1)[1].split('    def ', 1)[0]
    boost = health.split('    def _render_game_boost_config_section', 1)[1].split('    def ', 1)[0]

    check('version', VERSION.isdecimal())
    check('stage_preserved', bool(STAGE))
    check('four_primary_nav_destinations', all(x in gaming for x in (
        "('home', 'Inicio'", "('library', 'Biblioteca'",
        "('stability', 'Estabilidad'", "('overlay', 'Overlay'",
    )))
    check('home_is_session_first', "text='SESIÓN DE JUEGO'" in home and "uniform='gaming_session_metrics'" in home)
    check('home_uses_existing_real_sources', 'def _gaming_live_snapshot' in health and "agent.get_state()" in health and "latest_telemetry" in health)
    check('fps_is_not_synthesized', "fps = sample.get('fps')" in health and "if bool(state.get('game_detected'))" in health)
    check('primary_profiles_reduced', "uniform='gaming_profile_choices'" in home and "'BALANCED'" in home and "'HIGH_PERFORMANCE'" in home and "'MAXIMUM_PERFORMANCE'" in home)
    check('power_saver_is_secondary', "'Ahorro de energía'" in home and "secondary = ctk.CTkFrame" in home)
    check('home_has_no_tools_grid', "text='Tus herramientas'" not in home and "gaming_tools" not in home)
    check('game_boost_is_progressive', "text='Game Boost'" in home and "_select_performance_section('boost')" in home and "CTkSwitch" not in home)
    check('boost_options_are_dedicated', 'Acciones de la sesión' in boost and 'CTkSwitch' in boost and 'Rollback protegido' in boost)
    check('stability_is_useful_without_extra_page', 'Estabilidad de la sesión' in stability and 'Benchmark rápido' in stability and "'Ejecutar'" in stability)
    check('library_actions_are_hover_only', 'Intencionalmente NO se empaqueta aquí' in library and 'action_widget=menu_btn' in library)
    check('library_large_options_button_removed', "'Opciones'" not in library)
    check('library_grid_is_responsive', 'usable >= 1030' in health and 'usable >= 680' in health)
    check('overlay_is_progressive', "text='Personalizar overlay'" in overlay and 'def _toggle_advanced_settings' in overlay)
    check('overlay_advanced_hidden_by_default', 'self._advanced_open = False' in overlay and 'self.body.pack_forget()' in overlay)
    check('overlay_real_fps_policy_preserved', 'REAL_FPS_OR_NA_ONLY' in overlay)
    check('overlay_preview_preserved', "text='VISTA PREVIA'" in overlay and 'self.preview_text' in overlay)
    print('\nRESULTADO: PASS (19 checks)')


if __name__ == '__main__':
    main()
