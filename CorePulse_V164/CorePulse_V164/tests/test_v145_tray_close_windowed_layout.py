from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_version_145():
    version = read('core/version.py')
    assert 'VERSION = "145"' in version
    assert 'TRAY_CLOSE_AND_WINDOWED_LAYOUT_POLISH' in version

def test_native_x_minimizes_to_tray_but_real_close_remains():
    main = read('main.py')
    assert "self.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)" in main
    assert 'def minimize_to_tray(self):' in main
    assert 'def on_close(self):' in main
    assert 'self.withdraw()' in main
    assert 'self.iconify()' in main

def test_tray_has_explicit_exit():
    tray = read('core/tray_service.py')
    assert "pystray.MenuItem('Salir de CorePulse', quit_app)" in tray
    assert "self._dispatch('on_close')" in tray

def test_restore_preserves_window_state():
    main = read('main.py')
    assert '_tray_restore_state' in main
    assert '_tray_restore_geometry' in main
    assert "if restore_state == 'zoomed':" in main

def test_windowed_recommended_geometry():
    aw = read('gui/adaptive_window.py')
    assert 'PREFERRED_W = 1560' in aw
    assert 'PREFERRED_H = 860' in aw
    assert "'Recomendado': (1560, 860)" in aw

def test_compact_dashboard_density_only():
    layout = read('gui/dashboard_layout.py')
    assert "height = 82 if compact else 100 if standard else 106" in layout
    assert "meter_h = 100 if mode == 'compact' else 118 if mode == 'standard' else 126" in layout
    assert "ratio = 0.29 if mode == 'compact' else 0.37 if mode == 'standard' else 0.40" in layout
