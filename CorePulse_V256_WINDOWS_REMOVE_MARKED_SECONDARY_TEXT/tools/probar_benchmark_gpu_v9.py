"""Compatibilidad V173: el runner V9 termina redirigiendo al Benchmark GPU V11."""
from __future__ import annotations

from probar_benchmark_gpu_v10 import main

if __name__ == '__main__':
    print('[CorePulse] Benchmark V9 fue reemplazado por V11 en V173.', flush=True)
    raise SystemExit(main())
