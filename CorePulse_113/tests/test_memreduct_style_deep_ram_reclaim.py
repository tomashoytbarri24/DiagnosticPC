from pathlib import Path

import core.ram_optimizer as ram


def test_deep_policy_has_no_fake_99_percent_target():
    source = Path('core/ram_optimizer.py').read_text(encoding='utf-8')
    assert "target_percent': None" in source
    assert 'MEMORY_EMPTY_WORKING_SETS = 2' in source
    assert 'MEMORY_FLUSH_MODIFIED_LIST = 3' in source
    assert 'MEMORY_PURGE_STANDBY_LIST = 4' in source
    assert 'MEMORY_PURGE_LOW_PRIORITY_STANDBY_LIST = 5' in source
    assert 'SetSystemFileCacheSize' in source
    assert 'SeIncreaseQuotaPrivilege' in source


def test_deep_reclaim_reports_only_measured_result(monkeypatch):
    snapshots = iter([
        ram.MemorySnapshot(1.0, 16 * 1024**3, 4 * 1024**3, 12 * 1024**3, 75.0),
        ram.MemorySnapshot(2.0, 16 * 1024**3, 9 * 1024**3, 7 * 1024**3, 43.75),
    ])
    monkeypatch.setattr(ram, 'IS_WINDOWS', True)
    monkeypatch.setattr(ram, 'is_administrator', lambda: True)
    monkeypatch.setattr(ram, '_stable_snapshot', lambda samples=3, interval=0.12: next(snapshots))
    monkeypatch.setattr(ram.gc, 'collect', lambda: 7)
    monkeypatch.setattr(ram.time, 'sleep', lambda _seconds: None)
    monkeypatch.setattr(ram, '_trim_working_sets', lambda: (12, 2, 11))
    monkeypatch.setattr(ram, '_empty_system_working_sets', lambda: (True, {'ntstatus': 0}))
    monkeypatch.setattr(ram, '_flush_modified_page_list', lambda: (True, {'ntstatus': 0}))
    monkeypatch.setattr(ram, '_flush_system_file_cache', lambda: (True, {'winerror': 0}))
    monkeypatch.setattr(ram, '_purge_low_priority_standby_list', lambda: (True, {'ntstatus': 0}))
    monkeypatch.setattr(ram, '_purge_standby_list', lambda: (True, {'ntstatus': 0}))

    result = ram.optimize_ram_deep(settle_seconds=0, snapshot_samples=1, purge_standby=True)

    assert result['success'] is True
    assert result['target_percent'] is None
    assert result['regions_attempted'] == 6
    assert result['regions_completed'] == 6
    assert result['working_sets_trimmed'] == 12
    assert result['external_processes_modified'] == 11
    assert result['measured_recovered_bytes'] == 5 * 1024**3
    assert result['measured_recovered_gb'] == 5.0
    assert result['before']['used_percent'] == 75.0
    assert result['after']['used_percent'] == 43.75


def test_game_boost_still_purges_only_standby(monkeypatch):
    snapshots = iter([
        ram.MemorySnapshot(1.0, 8 * 1024**3, 2 * 1024**3, 6 * 1024**3, 75.0),
        ram.MemorySnapshot(2.0, 8 * 1024**3, 3 * 1024**3, 5 * 1024**3, 62.5),
    ])
    monkeypatch.setattr(ram, 'IS_WINDOWS', True)
    monkeypatch.setattr(ram, 'is_administrator', lambda: True)
    monkeypatch.setattr(ram, '_stable_snapshot', lambda samples=3, interval=0.12: next(snapshots))
    monkeypatch.setattr(ram.time, 'sleep', lambda _seconds: None)
    monkeypatch.setattr(ram, '_purge_standby_list', lambda: (True, {'ntstatus': 0}))

    result = ram.purge_standby_for_game(settle_seconds=0, snapshot_samples=1)

    assert result['success'] is True
    assert result['working_sets_trimmed'] == 0
    assert result['external_processes_modified'] == 0
    assert result['standby_purge_success'] is True
