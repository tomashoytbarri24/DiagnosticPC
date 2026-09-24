from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_health_card_has_premium_visual_elements():
    dashboard = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert '_cp_health_progress' in dashboard
    assert '_cp_health_semaphore_normal' in dashboard
    assert '_cp_health_semaphore_warning' in dashboard
    assert '_cp_health_semaphore_critical' in dashboard
    assert 'font=(FONT, 27' in dashboard
    assert 'FACTORES DETECTADOS' in dashboard


def test_health_progress_animation_is_visual_only():
    binding = (ROOT / 'gui' / 'live_health_binding.py').read_text(encoding='utf-8')
    assert 'def _animate_health_progress' in binding
    assert '_cfg(getattr(app, \'_health_status\', None), text=score_text' in binding
    assert 'app.after(12, tick)' in binding


def test_human_facing_health_copy_avoids_tjmax_jargon():
    health = (ROOT / 'core' / 'health_engine.py').read_text(encoding='utf-8')
    binding = (ROOT / 'gui' / 'live_health_binding.py').read_text(encoding='utf-8')
    assert 'Temperatura CPU cerca del máximo' in health
    assert 'margen {tj:.1f} °C' in binding
