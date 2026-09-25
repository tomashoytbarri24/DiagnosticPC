from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_startup_gate_has_visible_percent():
    text = (ROOT / 'gui' / 'startup_gate.py').read_text(encoding='utf-8')
    assert 'self.percent_label' in text
    assert "text='0%'" in text
    assert "value * 100.0" in text


def test_dashboard_uses_real_storage_health_key():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "smart = d.get('health')" in text
    assert "smart = d.get('health_percent')" in text  # compatibility only


def test_storage_health_preserves_native_nvme_and_cache(monkeypatch, tmp_path):
    import core.storage_summary_health as mod

    monkeypatch.setattr(mod, '_CACHE_FILE', tmp_path / 'storage_summary_health.json')
    monkeypatch.setattr(mod, 'get_storage_health', lambda: [{'device_id': 0, 'health_status': 'Healthy'}])
    monkeypatch.setattr(mod, 'match_reliability_record', lambda device, records: records[0] if records else {})
    monkeypatch.setattr(mod, 'resolve_physical_disk_index', lambda index, telemetry: 0)
    monkeypatch.setattr(mod, 'query_nvme_health_log', lambda physical_index: {'percentage_used': 6, 'temperature_c': 40, 'source': 'Windows NVMe Health Log'})
    monkeypatch.setattr(mod, 'query_smartctl_health', lambda physical_index: {})

    telemetry = {'_storage_devices': [{'model': 'NVMe Test', 'total_space_gb': 1000}]}
    result = mod.collect_storage_summary_health(telemetry, include_slow_fallbacks=False)
    assert result[0]['health'] == 94.0
    assert result[0]['wear_percent'] == 6.0
    assert mod.save_storage_summary_health_cache(result)
    restored = mod.load_storage_summary_health_cache()
    assert restored[0]['health'] == 94.0


def test_storage_two_phase_refresh_is_kept():
    text = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'include_slow_fallbacks=False' in text
    assert 'include_slow_fallbacks=True' in text
    assert 'keep_previous_health' in text
    assert 'load_storage_summary_health_cache' in text


def test_driver_scan_has_short_budget_and_no_per_device_pnp_property():
    text = (ROOT / 'core' / 'driver_updates.py').read_text(encoding='utf-8')
    assert 'CATALOG_HTTP_TIMEOUT = 4' in text
    assert 'def scan_driver_updates(*, max_devices: int = 5' in text
    assert 'workers = min(8' in text
    assert '$d.HardWareID' in text
    assert 'Get-PnpDeviceProperty -InstanceId $d.DeviceID' not in text
    assert 'CATALOG_CACHE_TTL = 12 * 60 * 60' in text


def test_all_theme_profiles_are_dark_and_twenty_or_more():
    from core.theme_manager import get_theme_profiles
    profiles = get_theme_profiles()
    assert len(profiles) >= 20
    assert all(str(profile.get('appearance')).lower() == 'dark' for profile in profiles.values())


def test_updates_module_stays_removed():
    assert not (ROOT / 'gui' / 'update_dialog.py').exists()
    assert not (ROOT / 'core' / 'update_manager.py').exists()


def test_driver_hub_2_protection_and_cache_contract():
    text = (ROOT / 'core' / 'driver_updates.py').read_text(encoding='utf-8')
    assert 'SCAN_CACHE_TTL = 15 * 60' in text
    assert 'INVENTORY_CACHE_TTL = 10 * 60' in text
    assert 'backup_installed_driver' in text
    assert '/export-driver' in text
    assert 'current_inf' in text

