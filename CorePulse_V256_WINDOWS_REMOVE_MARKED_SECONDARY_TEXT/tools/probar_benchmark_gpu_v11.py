"""Compatibilidad V178: Benchmark GPU V11 redirige al V13 determinista."""
from tools.probar_benchmark_gpu_v13 import main

if __name__ == "__main__":
    print("[CorePulse] V11 fue reemplazado por V13 en V178 (reloj de pared determinista).", flush=True)
    raise SystemExit(main())
