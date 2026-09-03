"""Regresión de políticas universales de identidad y selección de hardware."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.hardware_policy import (
    component_identity_specific,
    device_support_target,
    host_looks_official,
    select_active_gpu,
    select_representative_gpu_stats,
    resolve_component_id,
)


def check(name, condition):
    ok = bool(condition)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}")
    return ok

# El nombre/fabricante es deliberadamente ficticio: la política no debe conocerlo previamente.
gpus = [
    {'name': 'Aurora Integrated Graphics', 'usage_percent': 8.0, 'temperature_c': 48.0},
    {'name': 'Nebula Accelerator X900', 'usage_percent': 74.0, 'temperature_c': 66.0},
]
selected = select_active_gpu(gpus)

specific_unknown_vendor = component_identity_specific('GPU', 'Nebula Accelerator X900', {'manufacturer': 'Nova Silicon'})
generic_gpu = component_identity_specific('GPU', 'Integrated Graphics', {'manufacturer': 'Nova Silicon'})
ram_ok = component_identity_specific('RAM', '24 GB RAM', {'total_gb': 24})
official_dynamic = host_looks_official('support.novasilicon.com', {
    'component_type': 'GPU',
    'detected_hardware': 'Nebula Accelerator X900',
    'facts': {'manufacturer': 'Nova Silicon'},
})
model_name_alone_is_not_official = host_looks_official('nebula-reviews.example', {
    'component_type': 'GPU',
    'detected_hardware': 'Nebula Accelerator X900',
    'facts': {},
})
laptop_target = device_support_target({'form_factor': 'LAPTOP', 'manufacturer': 'Example Systems', 'model': 'Notebook Z14'})
desktop_target = device_support_target({'form_factor': 'DESKTOP', 'manufacturer': '', 'model': 'N/A', 'motherboard': 'BoardWorks AX-77'})
desktop_structured_target = device_support_target({'form_factor': 'DESKTOP', 'manufacturer': '', 'model': 'N/A', 'motherboard': {'manufacturer': 'BoardWorks', 'model': 'AX-77'}})

lookup = {
    'GPU:0': {'type': 'GPU', 'name': 'Aurora Integrated Graphics 200'},
    'GPU:1': {'type': 'GPU', 'name': 'Nebula Accelerator X900'},
    'STORAGE:0': {'type': 'STORAGE', 'name': 'ExampleDrive Q700 · 1024 GB'},
    'STORAGE:1': {'type': 'STORAGE', 'name': 'ArchiveDisk Z20 · 2048 GB'},
}
resolved_gpu = resolve_component_id('GPU:Nebula Accelerator X900', lookup)
ambiguous_gpu = resolve_component_id('GPU:adapter', lookup)
resolved_storage = resolve_component_id('STORAGE:ExampleDrive Q700', lookup)
trend_name, _trend_stats = select_representative_gpu_stats({
    'Aurora Integrated Graphics 200': {'usage_percent': {'avg': 5.0}, 'temperature_c': {'avg': 45.0}},
    'Nebula Accelerator X900': {'usage_percent': {'avg': 81.0}, 'temperature_c': {'avg': 68.0}},
})

results = [
    check('active_gpu_selected_by_real_usage_not_brand', selected.get('name') == 'Nebula Accelerator X900'),
    check('unknown_vendor_model_is_researchable', specific_unknown_vendor[0]),
    check('generic_gpu_remains_not_specific', not generic_gpu[0]),
    check('ram_identity_uses_real_capacity', ram_ok[0]),
    check('official_host_detected_from_runtime_manufacturer', official_dynamic),
    check('model_name_alone_does_not_create_official_source', not model_name_alone_is_not_official),
    check('laptop_support_uses_exact_runtime_model', laptop_target == 'Example Systems Notebook Z14'),
    check('desktop_support_falls_back_to_motherboard', desktop_target == 'BoardWorks AX-77'),
    check('desktop_support_accepts_structured_motherboard', desktop_structured_target == 'BoardWorks AX-77'),
    check('multi_gpu_exact_mapping_is_not_first_device', resolved_gpu == 'GPU:1'),
    check('ambiguous_multi_gpu_mapping_returns_none', ambiguous_gpu is None),
    check('multi_storage_exact_mapping_is_correct', resolved_storage == 'STORAGE:0'),
    check('trend_gpu_selected_by_measured_activity', trend_name == 'Nebula Accelerator X900'),
]
print('\nRESULTADO:', 'PASS' if all(results) else 'FAIL')
raise SystemExit(0 if all(results) else 1)
