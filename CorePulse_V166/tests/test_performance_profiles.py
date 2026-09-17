"""V100 — perfiles manuales persistentes, multi-juego y rollback sólo ante fallo."""
from __future__ import annotations
from pathlib import Path
import tempfile, sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from performance.profile_manager import PerformanceProfileManager, VISIBLE_MODES

class FakeBoost:
    def __init__(self): self.active=False; self.sync_calls=0
    def set_notifier(self,cb): pass
    def status(self): return {'session_active':self.active,'settings':{}}
    def get_settings(self): return {}
    def set_option(self,k,v): return True
    def sync_games(self,games,**kwargs): self.active=True; self.sync_calls+=1; return {'success':True}
    def begin_session(self,games,**kwargs): self.active=True; self.sync_calls+=1; return {'success':True}
    def end_session(self): self.active=False; return {'success':True}

class FakePower:
    def __init__(self,fail_max=False):
        self.fail_max=fail_max; self.calls=[]; self.restore_calls=0
    def snapshot(self):
        return {'success':True,'original':{'active_scheme_guid':'11111111-1111-1111-1111-111111111111','settings':{
            'max_processor_state':{'setting_guid':'max','ac':75,'dc':65},
            'boost_mode':{'setting_guid':'boost','ac':1,'dc':1},
            'energy_performance_preference':{'setting_guid':'epp','ac':50,'dc':50},
        },'capabilities':{'max_processor_state':True,'boost_mode':True,'energy_performance_preference':True}}}
    def _ok(self,profile): self.calls.append(profile); return {'success':True,'profile':profile,'boost_managed':True,'epp_managed':True,'message':profile}
    def apply_balanced(self,s,settings=None): return self._ok('BALANCED')
    def apply_high_performance(self,s,settings=None): return self._ok('HIGH_PERFORMANCE')
    def apply_maximum_performance(self,s,settings=None):
        if self.fail_max: return {'success':False,'message':'Access denied'}
        return self._ok('MAXIMUM_PERFORMANCE')
    def apply_power_saver(self,s,settings=None): return self._ok('POWER_SAVER')
    def restore(self,backup): self.restore_calls+=1; return {'success':True,'message':'Restaurado'}
    def activate_balanced_default(self): return {'success':True,'profile':'BALANCED','message':'Balanced'}

class Detector:
    def __init__(self): self.games=[]
    def detect_active_games(self): return list(self.games)

def check(name,c):
    ok=bool(c); print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}"); return ok

def main():
    results=[check('four_visible_modes',VISIBLE_MODES==('BALANCED','HIGH_PERFORMANCE','MAXIMUM_PERFORMANCE','POWER_SAVER'))]
    with tempfile.TemporaryDirectory() as td:
        power=FakePower(); det=Detector(); boost=FakeBoost()
        mgr=PerformanceProfileManager(power,det,backup_path=Path(td)/'backup.json',start_thread=False,register_atexit=False,game_boost=boost)
        for mode in VISIBLE_MODES:
            r=mgr.set_mode(mode); results.append(check(f'{mode}_applies',r.get('success') and mgr.status()['requested_mode']==mode))
        results.append(check('manual_profile_transaction_committed',not (Path(td)/'backup.json').exists()))
        det.games=[{'pid':10,'name':'a.exe'},{'pid':20,'name':'b.exe'}]
        mgr.set_mode('HIGH_PERFORMANCE'); mgr.poll_games_once()
        results.append(check('high_performance_arms_gameboost',boost.active and mgr.status()['active_game_count']==2))
        det.games=[{'pid':20,'name':'b.exe'}]; mgr.poll_games_once()
        results.append(check('closing_one_keeps_gameboost',boost.active))
        det.games=[]; mgr.poll_games_once()
        results.append(check('closing_last_disarms_gameboost',not boost.active))
        mgr.set_mode('POWER_SAVER'); det.games=[{'pid':30,'name':'c.exe'}]; mgr.poll_games_once()
        results.append(check('saver_never_arms_gameboost',not boost.active))
        r=mgr.shutdown(restore=True)
        results.append(check('shutdown_preserves_manual_plan',r.get('success') and power.restore_calls==0))
    with tempfile.TemporaryDirectory() as td:
        power=FakePower(fail_max=True); mgr=PerformanceProfileManager(power,Detector(),backup_path=Path(td)/'b.json',start_thread=False,register_atexit=False,game_boost=FakeBoost())
        r=mgr.set_mode('MAXIMUM_PERFORMANCE')
        results.append(check('failed_max_rolls_back',not r.get('success') and power.restore_calls==1 and mgr.status()['requested_mode']=='BALANCED'))
    ok=all(results); print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}"); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
