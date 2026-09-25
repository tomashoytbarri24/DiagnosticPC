from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_driver_hub_2_ui_contract():
    text = (ROOT / 'gui' / 'health_center_panel.py').read_text(encoding='utf-8')
    assert 'DRIVER HUB 3.0' in text
    assert 'Instalar seleccionados' in text
    assert 'Descargar todo' in text
    assert 'Inventario avanzado' in text
    assert 'ACTUALIZACIONES COMPATIBLES' in text
    assert 'Fabricante' in text


def test_driver_hub_2_backend_contract():
    text = (ROOT / 'core' / 'driver_updates.py').read_text(encoding='utf-8')
    assert 'Hardware ID + Microsoft Update Catalog' in text
    assert 'official_vendor' in text
    assert 'official_url' in text
    assert 'backup_installed_driver' in text
    assert 'SCAN_CACHE_FILE' in text
    assert 'ThreadPoolExecutor' in text


def test_firmware_excluded_from_bulk_install():
    text = (ROOT / 'core' / 'driver_updates.py').read_text(encoding='utf-8')
    assert 'bulk_install_allowed' in text
    assert 'FIRMWARE' in text
