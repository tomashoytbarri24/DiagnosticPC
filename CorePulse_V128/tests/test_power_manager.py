"""Valida comandos powercfg reversibles sin tocar el sistema real."""
from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.windows_commands import CommandResult
import performance.power_manager as pm

GUID='381b4222-f694-41f0-9685-ff5bb260df2e'

class FakeRunner:
    def __init__(self): self.calls=[]
    def __call__(self,args,**kwargs):
        args=tuple(str(x) for x in args); self.calls.append(args)
        if '/getactivescheme' in args:
            return CommandResult(True,args,0,f'Power Scheme GUID: {GUID}  (Balanced)\n','')
        if '/qh' in args or '/query' in args:
            out=(
                f'Power Setting GUID: {pm.MAX_PROCESSOR_STATE}\n'
                'Possible Setting Index: 0x00000000\nPossible Setting Index: 0x00000064\n'
                'Current AC Power Setting Index: 0x00000064\nCurrent DC Power Setting Index: 0x00000055\n'
                f'Power Setting GUID: {pm.BOOST_MODE}\n'
                'Possible Setting Index: 0x00000000\nPossible Setting Index: 0x00000001\n'
                'Current AC Power Setting Index: 0x00000001\nCurrent DC Power Setting Index: 0x00000000\n'
            )
            return CommandResult(True,args,0,out,'')
        return CommandResult(True,args,0,'','')

def check(name,cond): print(f"[{'PASS' if cond else 'FAIL'}] {name}: {bool(cond)}"); return bool(cond)

def main():
    old=pm.os.name; pm.os.name='nt'
    try:
        runner=FakeRunner(); mgr=pm.PowerManager(runner=runner)
        snap=mgr.snapshot(); original=snap.get('original') or {}
        results=[
            check('snapshot_success',snap.get('success')),
            check('active_guid_parsed',original.get('active_scheme_guid')==GUID),
            check('localized_independent_acdc',(original.get('settings') or {}).get('max_processor_state',{}).get('dc')==0x55),
            check('hidden_query_is_preferred', any('/qh' in call for call in runner.calls)),
        ]
        r=mgr.apply_gaming(GUID, original.get('settings'))
        calls=[' '.join(c) for c in runner.calls]
        results.append(check('gaming_success',r.get('success')))
        results.append(check('max_cpu_100',any('/setacvalueindex' in c and pm.MAX_PROCESSOR_STATE in c and c.endswith(' 100') for c in calls)))
        results.append(check('boost_enabled',any('/setacvalueindex' in c and pm.BOOST_MODE in c and c.endswith(' 1') for c in calls)))
        results.append(check('never_locks_minimum_to_100',not any('893dee8e-2bef-41e0-89c6-b55d0929964c' in c for c in calls)))
        restore=mgr.restore({'original':original})
        results.append(check('restore_success',restore.get('success')))
        ok=all(results); print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}"); return 0 if ok else 1
    finally: pm.os.name=old
if __name__=='__main__': raise SystemExit(main())
