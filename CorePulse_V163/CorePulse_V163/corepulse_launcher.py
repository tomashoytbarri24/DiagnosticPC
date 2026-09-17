"""Launcher único de CorePulse para fuente y EXE.

V0.10.2.81w publica la GUI después de un gate mínimo y difiere la auditoría de
capacidades / self-test instalado. El self-test de BUILD sigue siendo obligatorio.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import sys
import threading
import traceback

from core.runtime_paths import executable_root, log_path, resource_root, state_path
from core.version import VERSION
from core.startup_profiler import startup_mark, persist_startup_metrics

startup_mark("launcher_imported")


def _arg_value(flag: str):
    try:
        idx = sys.argv.index(flag)
        return sys.argv[idx + 1]
    except Exception:
        return None


def _write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _handle_internal_mode() -> int | None:
    """Despacha modos internos ANTES del preflight/GUI."""
    if "--corepulse-helper-probe" in sys.argv:
        out = _arg_value("--output")
        if not out:
            return 64
        _write_json(out, {"ok": True, "version": VERSION, "pid": os.getpid()})
        return 0

    if "--corepulse-self-test" in sys.argv:
        out = _arg_value("--output") or str(state_path("exe_selftest.json"))
        from core.frozen_selftest import run_self_test
        code, _report = run_self_test(out)
        return int(code)

    mode = None
    if "--corepulse-tweak-apply" in sys.argv:
        mode = "apply"
    elif "--corepulse-tweak-rollback" in sys.argv:
        mode = "rollback"
    if mode:
        request = _arg_value("--request")
        if not request:
            return 64
        payload = {}
        try:
            request_path = Path(request)
            payload = json.loads(request_path.read_text(encoding="utf-8"))
            records = payload.get("records") or []
            result_path = Path(payload["result_path"])
            from core import windows_tweaks as wt
            results = wt.apply_snapshot_records(records) if mode == "apply" else wt.restore_snapshot_records(records, attempts=3)
            _write_json(result_path, {"results": results, "mode": mode, "version": VERSION})
            return 0
        except Exception as exc:
            try:
                result_path = Path(payload.get("result_path")) if isinstance(payload, dict) and payload.get("result_path") else None
                if result_path:
                    _write_json(result_path, {"results": [], "error": f"{type(exc).__name__}: {exc}", "mode": mode})
            except Exception:
                pass
            return 70
    return None


def _show_message(title: str, text: str, error: bool = False) -> None:
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.user32.MessageBoxW(None, str(text), str(title), 0x10 if error else 0x40)
            return
        except Exception:
            pass
    print(f"{title}\n{text}", file=sys.stderr if error else sys.stdout)


def _installed_selftest_required() -> tuple[bool, Path]:
    safe_version = VERSION.replace('.', '_').replace('-', '_')
    installed_test = state_path(f"installed_selftest_{safe_version}.json")
    if not installed_test.is_file():
        return True, installed_test
    try:
        prior = json.loads(installed_test.read_text(encoding="utf-8"))
        return not (bool(prior.get("ready")) and prior.get("version") == VERSION), installed_test
    except Exception:
        return True, installed_test


def _deferred_integrity_worker(app) -> None:
    """Audita capacidades e integridad sin bloquear Tk ni inventar readiness."""
    ok = True
    detail = ""
    try:
        app.after(0, lambda: app.update_startup_component(
            'integrity', 0.10, 'Verificando integridad del entorno…'
        ))
    except Exception:
        pass
    try:
        from core.startup_readiness import collect_readiness, persist_readiness, update_first_run_state, format_blocking_message
        report = collect_readiness(resource_root(), VERSION)
        report_path = persist_readiness(report)
        if report_path:
            os.environ["COREPULSE_READINESS_REPORT"] = str(report_path)
        first_for_version, _ = update_first_run_state(VERSION)
        os.environ["COREPULSE_FIRST_RUN_VERSION"] = "1" if first_for_version else "0"
        startup_mark("readiness_complete", ready=bool(report.ready))
        try:
            app.after(0, lambda: app.update_startup_component(
                'integrity', 0.58, 'Comprobando dependencias y recursos…'
            ))
        except Exception:
            pass
        if not report.ready:
            ok = False
            detail = format_blocking_message(report)

        if report.frozen:
            required, installed_test = _installed_selftest_required()
            if required:
                try:
                    app.after(0, lambda: app.update_startup_component(
                        'integrity', 0.74, 'Validando el ejecutable autocontenido…',
                        'Comprobando recursos y dependencias incluidas en CorePulse.'
                    ))
                except Exception:
                    pass
                from core.frozen_selftest import run_self_test
                code, _ = run_self_test(installed_test)
                if code != 0:
                    ok = False
                    detail = (
                        "La instalación no superó la comprobación interna de integridad.\n\n"
                        f"Reporte: {installed_test}\n\n"
                        "Reinstala CorePulse antes de utilizar diagnóstico, Tweaks o Gaming."
                    )
    except Exception as exc:
        # La auditoría diferida nunca falsifica capacidad: se registra como fallo.
        ok = False
        detail = f"La auditoría de integridad no pudo completarse: {type(exc).__name__}: {exc}"
    startup_mark("runtime_integrity_ready" if ok else "runtime_integrity_failed")
    persist_startup_metrics()
    try:
        app.after(0, lambda: app.handle_runtime_integrity_result(ok, detail))
    except Exception:
        pass


def _schedule_deferred_integrity(app) -> None:
    threading.Thread(
        target=_deferred_integrity_worker,
        args=(app,),
        daemon=True,
        name="CorePulse-RuntimeIntegrity",
    ).start()


def main() -> int:
    internal = _handle_internal_mode()
    if internal is not None:
        return internal

    os.chdir(executable_root())
    from core.startup_readiness import collect_launch_gate, format_blocking_message
    gate = collect_launch_gate(VERSION)
    startup_mark("launch_gate_complete", ready=bool(gate.ready))
    if not gate.ready:
        _show_message("CorePulse — requisitos incompletos", format_blocking_message(gate), error=True)
        return 2

    try:
        startup_mark("gui_import_begin")
        from main import App
        startup_mark("gui_import_complete")
        app = App()
        startup_mark("app_constructed")
        app.after_idle(lambda: _schedule_deferred_integrity(app))
        app.mainloop()
        return 0
    except SystemExit as exc:
        try:
            return int(exc.code or 0)
        except Exception:
            return 1
    except Exception:
        detail = traceback.format_exc()
        try:
            log_path("launcher_crash.log").write_text(detail, encoding="utf-8")
        except Exception:
            pass
        _show_message(
            "CorePulse — error de inicio",
            "CorePulse encontró un error durante el arranque.\n\n"
            "El detalle técnico se guardó en AppData\\CorePulse\\logs.",
            error=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
