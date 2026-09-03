"""Regresión para V0.10.0.0w — consistencia de datos GPU."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core.gpu_display_logic import (
    active_display_on_other_gpu,
    human_gpu_hardware_type,
    windows_status_text,
    wmi_vram_presentation,
)


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    limited_text, limited_flag = wmi_vram_presentation(4 * 1024**3, 8192)
    normal_text, _ = wmi_vram_presentation(2 * 1024**3, 2048)
    selected = {'os_inventory': {'current_horizontal_resolution': None, 'current_vertical_resolution': None}}
    other = {'os_inventory': {'current_horizontal_resolution': 1920, 'current_vertical_resolution': 1080}}

    panel = (ROOT / 'gui' / 'gpu_detail_panel.py').read_text(encoding='utf-8')
    results = [
        check('version', VERSION == '0.10.0.0w'),
        check('stage', STAGE == 'HEALTH_INTELLIGENCE_RECOVERY'),
        check('wmi_4gb_marked_limited_against_real_8gb', limited_text == '4.00 GB · limitado por WMI'),
        check('wmi_matching_small_vram_not_marked_limited', normal_text == '2.00 GB'),
        check('windows_ok_humanized', windows_status_text('OK') == 'Funcionando correctamente'),
        check('lhm_type_humanized', human_gpu_hardware_type('GpuNvidia') == 'NVIDIA · LibreHardwareMonitor'),
        check('other_adapter_display_detected', active_display_on_other_gpu(selected, [selected, other]) is True),
        check('sensor_total_has_visual_priority', 'Total certificado por LibreHardwareMonitor' in panel),
        check('wmi_is_explicit_inventory', 'VRAM según Windows (WMI)' in panel),
        check('display_association_copy', 'No asociada directamente a este adaptador' in panel),
        check('raw_lhm_type_label_removed', 'Tipo de hardware LHM' not in panel),
        check('real_or_na_preserved', 'CorePulse muestra datos reales o N/A' in panel),
    ]
    ok = all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
