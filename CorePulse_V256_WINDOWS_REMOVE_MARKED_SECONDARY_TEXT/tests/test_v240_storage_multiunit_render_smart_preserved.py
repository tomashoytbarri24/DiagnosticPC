from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v240_version_contract():
    from core import version
    assert version.VERSION == '240'
    assert 'STORAGE_MULTIUNIT_RENDER_SMART_PRESERVED' in version.STAGE


def test_v240_does_not_replace_physical_storage_source():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'def _build_fast_disk_snapshot(self, telemetry):' in main
    assert "enrichment = (getattr(self, 'storage_health_cache', {}) or {}).get(idx, {})" in main
    assert "life = enrichment.get('health')" in main
    assert 'def _build_live_volume_storage_snapshot' not in main
    assert 'psutil.disk_usage(mount)' not in main


def test_v240_multiunit_fix_is_presentation_only():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    hardware = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    assert 'def _finalize_storage_viewport(app, mode=None):' in layout
    assert "for idx in sorted(widgets_map):" in layout
    assert "card.pack_configure(fill='x', expand=False, padx=2, pady=2)" in layout
    assert 'app.after(70, lambda: schedule(0))' in layout
    assert "if getattr(card, '_corepulse_storage_v238', False):" in hardware
    assert "card.pack_propagate(False)" in hardware


def test_v240_height_contract_for_1_2_3_units_is_preserved():
    layout = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    assert 'return one if count == 1 else two' in layout
    assert '1 unidad: una tarjeta completa.' in layout
    assert '2 unidades: dos tarjetas completas.' in layout
    assert '3+ unidades: dos tarjetas visibles + scroll interno.' in layout
