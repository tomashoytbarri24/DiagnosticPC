from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


def test_linux_storage_inventory_detects_mounted_and_unmounted_physical_disks(monkeypatch):
    import core.telemetry as telemetry

    payload = {
        "blockdevices": [
            {
                "name": "nvme0n1", "path": "/dev/nvme0n1", "type": "disk",
                "size": 1000000000000, "model": "Linux NVMe", "serial": "LINUX1",
                "tran": "nvme", "rm": False, "rota": False,
                "children": [
                    {"name": "nvme0n1p2", "path": "/dev/nvme0n1p2", "type": "part",
                     "size": 900000000000, "mountpoints": ["/"]},
                ],
            },
            {
                "name": "nvme1n1", "path": "/dev/nvme1n1", "type": "disk",
                "size": 500000000000, "model": "Windows NVMe", "serial": "WIN1",
                "tran": "nvme", "rm": False, "rota": False,
                "children": [
                    {"name": "nvme1n1p3", "path": "/dev/nvme1n1p3", "type": "part",
                     "size": 450000000000, "mountpoints": [None]},
                ],
            },
        ]
    }

    monkeypatch.setattr(telemetry.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(
        telemetry.subprocess, 'run',
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload)),
    )
    monkeypatch.setattr(
        telemetry.psutil, 'disk_usage',
        lambda mount: SimpleNamespace(total=900000000000, used=360000000000, free=540000000000),
    )

    rows = telemetry._linux_storage_inventory()
    assert len(rows) == 2
    assert rows[0]['system_disk'] is True
    assert rows[0]['mount_points'] == '/'
    assert rows[0]['used_space_percent'] == 40.0
    assert rows[1]['system_disk'] is False
    assert rows[1]['mount_points'] is None
    assert rows[1]['used_space_percent'] is None
    assert rows[1]['device_id'] == '/dev/nvme1n1'


def test_linux_inventory_is_merged_as_real_storage_inventory(monkeypatch):
    import core.telemetry as telemetry

    monkeypatch.setattr(telemetry.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(telemetry, '_linux_storage_inventory', lambda: [{
        'name': 'Disk B', 'model': 'Disk B', 'serial_number': 'B',
        'device_id': '/dev/nvme1n1', 'disk_index': 1, 'size_bytes_os': 512 * 1024**3,
        'mount_points': None, 'system_disk': False, 'used_space_percent': None,
        'inventory_source': 'lsblk', 'usage_scope': 'unmounted_or_unreadable',
    }])
    telemetry._ENUM_CACHE['ts'] = 0
    telemetry._ENUM_CACHE['gpu'] = []
    telemetry._ENUM_CACHE['storage'] = []
    inv = telemetry._enum_cached()
    merged = telemetry._merge_storage_inventory([], inv['storage'])
    assert len(merged) == 1
    assert merged[0]['inventory_sources'] == ['lsblk']
    assert merged[0]['device_id'] == '/dev/nvme1n1'
    assert round(merged[0]['total_space_gb']) == 512


def test_reports_folder_is_cross_platform_and_diagnostic_cards_do_not_vertical_stretch():
    root = Path(__file__).resolve().parents[1]
    main_src = (root / 'main.py').read_text(encoding='utf-8')
    diag_src = (root / 'gui' / 'diagnostic_view.py').read_text(encoding='utf-8')
    assert "opener = 'open' if sys.platform == 'darwin' else 'xdg-open'" in main_src
    assert "self.component_report.grid(row=1, column=0, columnspan=2, sticky='ew'" in diag_src
    assert "row=row, column=col, sticky='new'" in diag_src


def test_linux_storage_detail_does_not_query_windows_physicaldrive():
    root = Path(__file__).resolve().parents[1]
    src = (root / 'gui' / 'storage_detail_panel.py').read_text(encoding='utf-8')
    assert "if platform.system() == 'Windows' and physical_index is not None:" in src
    assert "Linux obtiene SMART desde get_storage_health()" in src


def test_v179_stage_contract_is_preserved_in_history():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    history = (root / 'VERSIONING.md').read_text(encoding='utf-8')
    assert 'V179' in history or 'CROSS_PLATFORM_STORAGE_REPORTS_LAYOUT' in history
