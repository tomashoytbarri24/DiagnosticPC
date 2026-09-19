from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from core.diagnostic_lifecycle import DiagnosticRun, DiagnosticState


def test_diagnostic_lifecycle_accepts_audio_between_hardware_and_benchmark():
    run = DiagnosticRun(182)
    assert run.transition(DiagnosticState.RUNNING_HARDWARE)
    assert run.transition(DiagnosticState.RUNNING_AUDIO)
    assert run.transition(DiagnosticState.RUNNING_BENCHMARK)
    assert run.state == DiagnosticState.RUNNING_BENCHMARK


def test_linux_gpu_client_message_only_closes_on_wm_delete():
    import core.benchmark_engine as engine

    source = inspect.getsource(engine._benchmark_gpu_opengl_linux)
    assert "event_type == 33 and wm_delete" in source
    assert "event.xclient.data.l[0]" in source
    assert "event_type in (17, 33)" not in source


def test_standalone_benchmark_finishes_with_gpu_visual_phase():
    source = Path("gui/health_center_panel.py").read_text(encoding="utf-8")
    method = source[source.index("    def _run_visual_benchmark(self):"):source.index("    def _render_sensor_compatibility", source.index("    def _run_visual_benchmark(self):"))]
    work = method[method.index("def work():"):method.index("def done(payload, error):")]
    assert work.index("if classic_selected:") < work.index("if gpu_selected:")
    assert "Continúa: GPU 3D visible" in work


def test_linux_storage_marks_unmounted_filesystem_without_inventing_usage(monkeypatch):
    import core.telemetry as telemetry

    payload = {
        "blockdevices": [
            {
                "name": "nvme0n1", "kname": "nvme0n1", "path": "/dev/nvme0n1",
                "type": "disk", "size": 1000000000000, "model": "LINUX SSD", "serial": "A",
                "tran": "nvme", "rm": 0, "rota": 0,
                "children": [
                    {"name": "nvme0n1p1", "path": "/dev/nvme0n1p1", "type": "part",
                     "fstype": "btrfs", "mountpoints": ["/"]}
                ],
            },
            {
                "name": "nvme1n1", "kname": "nvme1n1", "path": "/dev/nvme1n1",
                "type": "disk", "size": 500000000000, "model": "WINDOWS SSD", "serial": "B",
                "tran": "nvme", "rm": 0, "rota": 0,
                "children": [
                    {"name": "nvme1n1p3", "path": "/dev/nvme1n1p3", "type": "part",
                     "fstype": "ntfs", "mountpoints": [None]}
                ],
            },
            {"name": "zram0", "type": "disk", "size": 32000000000, "model": "zram", "rm": 0, "rota": 0},
        ]
    }

    monkeypatch.setattr(telemetry.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        telemetry.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload)),
    )
    monkeypatch.setattr(
        telemetry.psutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=900, used=300, free=600),
    )

    rows = telemetry._linux_storage_inventory()
    assert [row["model"] for row in rows] == ["LINUX SSD", "WINDOWS SSD"]
    windows = rows[1]
    assert windows["used_space_percent"] is None
    assert windows["mounted_used_bytes"] is None
    assert windows["unmounted_filesystems"] == ["ntfs"]
    assert "sin montar" in windows["usage_reason"].lower()
