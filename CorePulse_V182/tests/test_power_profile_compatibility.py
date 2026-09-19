"""V100: perfiles no deben quedar inutilizables si PERFBOOSTMODE está oculto/no expuesto."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION
from core.windows_commands import CommandResult
import performance.power_manager as pm

GUID='381b4222-f694-41f0-9685-ff5bb260df2e'
class HiddenBoostRunner:
    def __init__(self): self.calls=[]
    def __call__(self,args,**kwargs):
        args=tuple(str(x) for x in args); self.calls.append(args)
        if '/getactivescheme' in args:
            return CommandResult(True,args,0,f'GUID: {GUID}','')
        if '/qh' in args or '/query' in args:
            out=(f'Power Setting GUID: {pm.MAX_PROCESSOR_STATE}\n'
                 'Current AC: 0x00000064\nCurrent DC: 0x00000055\n')
            return CommandResult(True,args,0,out,'')
        return CommandResult(True,args,0,'','')

def check(name,cond): print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}"); return bool(cond)

def main():
    old=pm.os.name; pm.os.name='nt'
    try:
        r=HiddenBoostRunner(); mgr=pm.PowerManager(runner=r)
        snap=mgr.snapshot(); original=snap.get('original') or {}; settings=original.get('settings') or {}
        results=[
            check('version', VERSION.isdecimal()),
            check('snapshot_partial_but_successful', snap.get('success') and snap.get('partial')),
            check('max_backed_up', 'max_processor_state' in settings),
            check('boost_not_backed_up', 'boost_mode' not in settings),
        ]
        applied=mgr.apply_gaming(GUID,settings)
        calls=[' '.join(c) for c in r.calls]
        results += [
            check('gaming_still_applies', applied.get('success') and applied.get('partial')),
            check('max_cpu_changed', any('/setacvalueindex' in c and pm.MAX_PROCESSOR_STATE in c and c.endswith(' 100') for c in calls)),
            check('boost_not_modified_without_backup', not any('/setacvalueindex' in c and pm.BOOST_MODE in c for c in calls)),
        ]
        return 0 if all(results) else 1
    finally: pm.os.name=old
if __name__=='__main__': raise SystemExit(main())
