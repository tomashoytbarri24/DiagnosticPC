from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def test_version_156():
    assert 'VERSION = "156"' in text('core/version.py')


def test_old_driver_is_not_claimed_as_update_available():
    s = text('gui/health_center_panel.py')
    assert "'OLD':'Antiguo · revisar actualización'" in s
    assert 'No significa que CorePulse haya confirmado una actualización disponible en Internet.' in s


def test_driver_table_exposes_age():
    s = text('gui/health_center_panel.py')
    assert "'title': 'Edad aprox.'" in s
    assert 'age_years' in s


def test_core_note_keeps_age_semantics_honest():
    s = text('core/windows_health.py')
    assert 'ni confirma que exista una actualización disponible' in s


def test_alerts_are_not_named_as_diagnostic_anymore():
    for rel in (
        'gui/dashboard.py', 'gui/dashboard_layout.py', 'gui/sidebar.py',
        'gui/internal_navigation.py', 'core/tray_service.py'
    ):
        s = text(rel)
        assert 'Alertas y diagnóstico' not in s
        assert 'Alertas técnicas' in s


def test_publisher_not_modified_by_v156_contract():
    s = text('VALIDACION_V156.md')
    assert 'No se modifica Publicar/Actualizaciones.' in s
