"""Contrato de subprocess: sin shell=True y ventanas Windows ocultas en rutas críticas."""
from __future__ import annotations
from pathlib import Path
import ast, sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}"); return bool(condition)


def main():
    shell_true=[]
    for p in list((ROOT/'core').glob('*.py'))+list((ROOT/'performance').glob('*.py')):
        tree=ast.parse(p.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call): continue
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='subprocess':
                for kw in node.keywords:
                    if kw.arg=='shell' and isinstance(kw.value,ast.Constant) and kw.value.value is True:
                        shell_true.append((p.name,node.lineno))
    wc=(ROOT/'core'/'windows_commands.py').read_text(encoding='utf-8')
    storage=(ROOT/'core'/'storage_health.py').read_text(encoding='utf-8')
    reliable=(ROOT/'core'/'telemetry_reliable.py').read_text(encoding='utf-8')
    results=[
        check('no_shell_true_in_runtime',not shell_true),
        check('central_runner_uses_create_no_window','CREATE_NO_WINDOW' in wc and 'STARTUPINFO' in wc and 'shell=False' in wc),
        check('storage_uses_hidden_runner','run_powershell' in storage),
        check('nvidia_command_is_argv',"['nvidia-smi'" in reliable and 'shell=True' not in reliable),
    ]
    ok=all(results); print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}"); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
