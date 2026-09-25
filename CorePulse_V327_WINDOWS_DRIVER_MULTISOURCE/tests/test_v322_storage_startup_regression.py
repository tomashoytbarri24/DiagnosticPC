from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_startup_merge_preserves_health_bundle():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'def _merge_storage_health_records(self, incoming):' in main
    assert "not self._storage_health_record_has_percent(value)" in main
    assert "'health_label', 'health_source'" in main
    assert 'self._merge_storage_health_records(fast_health)' in main


def test_startup_can_wait_briefly_for_real_storage_health():
    main = (ROOT / 'main.py').read_text(encoding='utf-8')
    assert 'def _start_startup_storage_health_worker(self, telemetry):' in main
    assert "collect_storage_summary_health(snapshot, include_slow_fallbacks=True)" in main
    assert "'services', 0.98, 'Leyendo salud de almacenamiento…'" in main
    assert 'waited < 4.0' in main


def test_storage_health_cache_survives_normal_restart_window():
    storage = (ROOT / 'core' / 'storage_summary_health.py').read_text(encoding='utf-8')
    assert '_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60' in storage


def test_contract_states_it_is_an_acceptance_guard_not_magic_control():
    contract = (ROOT / 'COREPULSE_NON_REGRESSION_CONTRACT.md').read_text(encoding='utf-8')
    assert 'no controla por sí solo a otra IA' in contract
    assert 'No borrar ni modificar' in contract
