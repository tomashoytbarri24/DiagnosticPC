"""Prueba manual del Benchmark GPU V19 DirectX 11."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.directx_benchmark import run_directx_benchmark
from core.benchmark_engine import save_last_gpu_v19_result
from core.benchmark_version import GPU_BENCHMARK_LABEL


def progress(frac: float, stage: str, detail: str = "") -> None:
    pct = max(0, min(100, int(float(frac) * 100)))
    print(f"[{pct:3d}%] {stage}: {detail}", flush=True)


def main() -> int:
    print(f"CorePulse Benchmark {GPU_BENCHMARK_LABEL} · DirectX 11 · wall-clock deterministic", flush=True)
    profile = (sys.argv[1].strip().lower() if len(sys.argv) > 1 else "standard")
    if profile not in {"quick", "standard", "extended"}:
        profile = "standard"
    print(f"Perfil: {profile}. ESC cancela.\n", flush=True)
    result = run_directx_benchmark(profile, visible=True, progress_callback=progress)
    out = None
    if str(result.get("status") or "").upper() == "OK":
        out = save_last_gpu_v19_result(result)
    print("\nResumen:")
    print(f"Estado: {result.get('status')}")
    print(f"GPU: {result.get('renderer')}")
    print(f"FPS Extreme/primaria: {result.get('frames_per_s')}")
    print(f"1% Low: {result.get('one_percent_low_fps')} FPS")
    print(f"CPU/Present frametime: {result.get('frametime_avg_ms')} ms")
    print(f"GPU frametime: {result.get('gpu_frame_time_avg_ms')} ms")
    print(f"GPU timestamp coverage: {result.get('gpu_timestamp_coverage')}")
    for row in result.get('scenes') or []:
        print(f"{row.get('key')}: wall={row.get('measurement_wall_seconds')} s, render_accum={row.get('render_present_accumulated_seconds')} s")
    if out is not None:
        print(f"\nResultado GPU guardado en: {out}")
    else:
        print("\nEl benchmark no terminó correctamente; se conserva intacto el último resultado válido.")
    return 0 if str(result.get("status") or "").upper() == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
