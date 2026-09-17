from core.windows_health import _driver_hardware_priority, _microsoft_inbox_driver


def test_gpu_network_audio_storage_are_prioritized():
    cases = [
        ({'DeviceClass': 'DISPLAY', 'DeviceName': 'NVIDIA GeForce RTX 4070', 'DriverProviderName': 'NVIDIA'}, 'GPU / VIDEO'),
        ({'DeviceClass': 'NET', 'DeviceName': 'Intel Wi-Fi 6 AX201', 'DriverProviderName': 'Intel'}, 'RED'),
        ({'DeviceClass': 'MEDIA', 'DeviceName': 'Realtek Audio', 'DriverProviderName': 'Realtek'}, 'AUDIO'),
        ({'DeviceClass': 'SCSIAdapter', 'DeviceName': 'Intel RST VMD Controller', 'DriverProviderName': 'Intel'}, 'ALMACENAMIENTO'),
        ({'DeviceClass': 'BLUETOOTH', 'DeviceName': 'Bluetooth Adapter', 'DriverProviderName': 'Intel'}, 'BLUETOOTH'),
    ]
    for row, category in cases:
        priority, detected = _driver_hardware_priority(row)
        assert priority > 0
        assert detected == category


def test_generic_microsoft_virtual_devices_do_not_dominate_old_driver_view():
    assert _microsoft_inbox_driver({
        'DeviceClass': 'NET',
        'DeviceName': 'WAN Miniport (IPv6)',
        'DriverProviderName': 'Microsoft',
    }) is True
    assert _microsoft_inbox_driver({
        'DeviceClass': 'DISPLAY',
        'DeviceName': 'NVIDIA GeForce RTX 4070',
        'DriverProviderName': 'NVIDIA',
    }) is False


def test_generic_microsoft_driver_has_no_hardware_priority():
    priority, category = _driver_hardware_priority({
        'DeviceClass': 'NET',
        'DeviceName': 'WAN Miniport (IPv6)',
        'DriverProviderName': 'Microsoft',
    })
    assert priority == 0
    assert category == 'WINDOWS / VIRTUAL'
