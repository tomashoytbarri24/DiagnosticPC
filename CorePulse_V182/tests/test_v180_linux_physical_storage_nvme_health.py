from __future__ import annotations

import json
from types import SimpleNamespace


def test_linux_storage_filters_zram_and_virtual_devices(monkeypatch):
    import core.telemetry as telemetry

    payload = {
        'blockdevices': [
            {'name':'zram0','path':'/dev/zram0','type':'disk','size':32*1024**3,'model':None,'serial':None,'tran':None,'rm':False,'rota':False},
            {'name':'loop0','path':'/dev/loop0','type':'disk','size':1000,'model':None,'serial':None,'tran':None,'rm':False,'rota':False},
            {'name':'nvme0n1','path':'/dev/nvme0n1','type':'disk','size':1000*1024**3,'model':'MSI M450 1TB','serial':'A','tran':'nvme','rm':False,'rota':False,'children':[]},
            {'name':'nvme1n1','path':'/dev/nvme1n1','type':'disk','size':512*1024**3,'model':'SAMSUNG NVME','serial':'B','tran':'nvme','rm':False,'rota':False,'children':[]},
        ]
    }
    monkeypatch.setattr(telemetry.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(telemetry.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload)))
    rows = telemetry._linux_storage_inventory()
    assert [row['device_id'] for row in rows] == ['/dev/nvme0n1', '/dev/nvme1n1']


def test_udisks_nvme_percentage_used_becomes_exact_remaining_health(monkeypatch):
    import core.storage_health_linux as linux_health

    monkeypatch.setattr(linux_health.shutil, 'which', lambda name: f'/usr/bin/{name}')

    def fake_run(args, timeout=8):
        joined = ' '.join(args)
        if args[:3] == ['udisksctl', 'info', '-b']:
            return SimpleNamespace(returncode=0, stdout="Drive: '/org/freedesktop/UDisks2/drives/MSI_M450'\n")
        if 'SmartUpdate' in joined:
            return SimpleNamespace(returncode=0, stdout='()')
        if 'SmartGetAttributes' in joined:
            return SimpleNamespace(returncode=0, stdout="({'avail_spare': <byte 0x64>, 'spare_thresh': <byte 0x0a>, 'percent_used': <byte 0x03>, 'power_cycles': <uint64 55>, 'media_errors': <uint64 0>},)")
        if 'SmartTemperature' in joined:
            return SimpleNamespace(returncode=0, stdout='(<uint16 307>,)')
        if 'SmartPowerOnHours' in joined:
            return SimpleNamespace(returncode=0, stdout='(<uint64 1200>,)')
        if 'SmartCriticalWarning' in joined:
            return SimpleNamespace(returncode=0, stdout="(<@as []>,)")
        raise AssertionError(args)

    monkeypatch.setattr(linux_health, '_run', fake_run)
    data = linux_health._udisks_nvme_health('/dev/nvme0n1')
    assert data['health'] == 97.0
    assert data['wear'] == 3.0
    assert round(data['temperature'], 1) == 33.9
    assert data['power_on_hours'] == 1200
    assert data['source'] == 'UDisks2 NVMe SMART'


def test_linux_health_uses_udisks_before_smartctl(monkeypatch):
    import core.storage_health_linux as linux_health

    monkeypatch.setattr(linux_health, '_physical_block_devices', lambda: [{
        'device_id':'/dev/nvme0n1', 'model':'MSI M450 1TB', 'serial':'SER', 'size':1000, 'transport':'nvme'
    }])
    monkeypatch.setattr(linux_health, '_udisks_nvme_health', lambda dev: {
        'health': 96.0, 'wear':4.0, 'temperature':40.0, 'health_source':'UDisks2 NVMe SMART · 100 - Percentage Used',
        'health_derived':True, 'health_status':'Healthy', 'operational_status':'OK', 'source':'UDisks2 NVMe SMART'
    })
    monkeypatch.setattr(linux_health, '_smartctl_health', lambda dev: (_ for _ in ()).throw(AssertionError('smartctl should not be needed')))
    rows = linux_health.get_linux_storage_health()
    assert rows[0]['health'] == 96.0
    assert rows[0]['wear'] == 4.0


def test_storage_dashboard_cards_are_physical_not_partition_titles():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    dash = (root/'gui'/'dashboard.py').read_text(encoding='utf-8')
    view = (root/'gui'/'hardware_storage_view.py').read_text(encoding='utf-8')
    assert "title += f'   ·   {float(total_raw):.2f} GB'" in dash
    assert "text=f'{model}   ·   {mounts}'" not in dash
    assert "line1 += f'   ·   {mounts}'" not in view
    assert 'No montado en este sistema' in dash


def test_version_is_not_older_than_180():
    from core.version import VERSION
    assert int(VERSION) >= 180
