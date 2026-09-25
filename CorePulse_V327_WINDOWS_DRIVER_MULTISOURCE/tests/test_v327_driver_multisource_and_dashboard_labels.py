from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_resource_titles_are_user_facing():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "text=f'Procesador\\n{cpu_name}'" in text
    assert "text='Memoria RAM\\nUso físico del sistema'" in text
    assert "text=f'Tarjeta Gráfica\\n{gpu_name}'" in text


def test_driver_hub_uses_multisource_vendor_and_catalog():
    text = (ROOT / 'core' / 'driver_updates.py').read_text(encoding='utf-8')
    assert 'INTEL_BLUETOOTH_PAGE' in text
    assert '_intel_wireless_bluetooth_update' in text
    assert '_vendor_update_for_device' in text
    assert '_best_catalog_update_only' in text
    assert 'compatible_ids' in text
    assert 'last-scan-v327.json' in text


def test_intel_bluetooth_official_source_parser(monkeypatch):
    import core.driver_updates as drv
    page = (
        '<html><body>'
        'Installs Intel Wireless Bluetooth version 24.70.0 '
        'Driver version 24.70.0.4 : For AX201 AX1650(i/s) 9560 '
        'Download BT-24.70.0-64UWD-Win10-Win11.exe '
        'SHA256: 001DF2E294E86D051645EA1367F4A19518CA8C2A52782CDD4C1CB81C3C0F038A '
        '<a href="https://downloadmirror.intel.com/123456/BT-24.70.0-64UWD-Win10-Win11.exe">download</a>'
        '</body></html>'
    )
    monkeypatch.setattr(drv, '_vendor_page_text', lambda *a, **k: page)
    monkeypatch.setattr(drv, '_cached_package_path', lambda *a, **k: None)
    device = {
        'device_name': 'Intel(R) Wireless Bluetooth(R)',
        'device_class': 'BLUETOOTH',
        'provider': 'Intel Corporation',
        'current_version': '23.170.0.3',
        'inf_name': 'oem42.inf',
        'hardware_ids': [r'USB\VID_8087&PID_0033'],
        'system_device_names': ['Killer(R) Wi-Fi 6 AX1650i 160MHz Wireless Network Adapter'],
    }
    item = drv._intel_wireless_bluetooth_update(device)
    assert item is not None
    assert item['available_version'] == '24.70.0.4'
    assert item['source_kind'] == 'vendor_installer'
    assert item['official_vendor'] == 'Intel'
    assert item['vendor_download_url'].startswith('https://downloadmirror.intel.com/')


def test_primary_scan_keeps_bluetooth_family():
    import core.driver_updates as drv
    inv = {'items': [
        {'DeviceName':'GPU','DeviceClass':'DISPLAY','DriverProviderName':'NVIDIA','DriverVersion':'1.0.0.0','DeviceID':r'PCI\VEN_10DE&DEV_1','HardwareID':r'PCI\VEN_10DE&DEV_1','hardware_priority':100,'status':'OK'},
        {'DeviceName':'Wi-Fi','DeviceClass':'NET','DriverProviderName':'Intel','DriverVersion':'1.0.0.0','DeviceID':r'PCI\VEN_8086&DEV_2','HardwareID':r'PCI\VEN_8086&DEV_2','hardware_priority':95,'status':'OK'},
        {'DeviceName':'Audio','DeviceClass':'MEDIA','DriverProviderName':'Realtek','DriverVersion':'1.0.0.0','DeviceID':r'HDAUDIO\FUNC_01&VEN_10EC','HardwareID':r'HDAUDIO\FUNC_01&VEN_10EC','hardware_priority':90,'status':'OK'},
        {'DeviceName':'Storage','DeviceClass':'SCSIADAPTER','DriverProviderName':'Intel','DriverVersion':'1.0.0.0','DeviceID':r'PCI\VEN_8086&DEV_3','HardwareID':r'PCI\VEN_8086&DEV_3','hardware_priority':88,'status':'OK'},
        {'DeviceName':'Intel(R) Wireless Bluetooth(R)','DeviceClass':'BLUETOOTH','DriverProviderName':'Intel Corporation','DriverVersion':'23.170.0.3','DeviceID':r'USB\VID_8087&PID_0033','HardwareID':r'USB\VID_8087&PID_0033','hardware_priority':84,'status':'OK'},
        {'DeviceName':'Unsigned helper','DeviceClass':'SYSTEM','DriverProviderName':'Third Party','DriverVersion':'1.0','DeviceID':r'ROOT\X','HardwareID':r'ROOT\X','hardware_priority':0,'status':'UNSIGNED'},
    ]}
    rows = drv._candidates_from_health_inventory(inv, limit=5)
    assert any(str(x.get('device_class')).upper() == 'BLUETOOTH' for x in rows)
