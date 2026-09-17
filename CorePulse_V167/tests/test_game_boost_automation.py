"""V100 — Game Boost conserva rollback temporal sin revertir el plan persistente."""
from __future__ import annotations
from pathlib import Path
import tempfile, sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION
from performance.game_boost import GameBoostOptimizer
from performance.profile_manager import PerformanceProfileManager

class FakeBoost(GameBoostOptimizer):
    def __init__(self,config_path,notices):
        super().__init__(config_path=config_path,notifier=lambda t,m:notices.append((t,m)))
        for key in self.settings: self.settings[key]=True
        self.memory_calls=0; self.priority_calls=0; self.qos_calls=0; self.game_mode_calls=0
    def _enable_windows_game_mode(self):
        self.game_mode_calls+=1; self._game_mode_backup={'existed':True,'value':0,'type':4}
        return {'success':True,'action':'windows_game_mode','message':'Windows Game Mode: activado'}
    def _restore_windows_game_mode(self): self._game_mode_backup=None; return True
    def _set_high_priority(self,game):
        self.priority_calls+=1; pid=int(game['pid']); self._process_state.setdefault(pid,{'pid':pid,'name':game['name'],'create_time':None})
        return {'success':True,'action':'priority','message':'Prioridad del juego: Alta'}
    def _disable_power_throttling(self,game):
        self.qos_calls+=1; pid=int(game['pid']); self._process_state.setdefault(pid,{'pid':pid,'name':game['name'],'create_time':None})
        return {'success':True,'action':'power_throttling','message':'Power Throttling: desactivado (HighQoS)'}
    def _restore_process(self,pid): self._process_state.pop(int(pid),None)

class FakePower:
    def __init__(self): self.max_calls=0; self.high_calls=0; self.restore_calls=0
    def snapshot(self):
        return {'success':True,'original':{'active_scheme_guid':'11111111-1111-1111-1111-111111111111','settings':{
            'max_processor_state':{'setting_guid':'max','ac':90,'dc':80},
            'boost_mode':{'setting_guid':'boost','ac':1,'dc':1},
            'energy_performance_preference':{'setting_guid':'epp','ac':50,'dc':50},
        },'capabilities':{'max_processor_state':True,'boost_mode':True,'energy_performance_preference':True}}}
    def apply_balanced(self,s,settings=None): return {'success':True,'profile':'BALANCED','message':'Equilibrado'}
    def apply_high_performance(self,s,settings=None): self.high_calls+=1; return {'success':True,'profile':'HIGH_PERFORMANCE','boost_managed':True,'epp_managed':True,'message':'Alto rendimiento'}
    def apply_maximum_performance(self,s,settings=None): self.max_calls+=1; return {'success':True,'profile':'MAXIMUM_PERFORMANCE','boost_managed':True,'epp_managed':True,'message':'Máximo rendimiento'}
    def apply_power_saver(self,s,settings=None): return {'success':True,'profile':'POWER_SAVER','message':'Ahorro'}
    def restore(self,backup): self.restore_calls+=1; return {'success':True,'message':'Restaurado'}
    def activate_balanced_default(self): return {'success':True,'message':'Balanced'}

class Detector:
    def __init__(self): self.games=[]
    def detect_active_games(self): return list(self.games)

def check(name,cond):
    ok=bool(cond); print(f"[{'PASS' if ok else 'FAIL'}] {name}: {ok}"); return ok

def main():
    results=[]
    with tempfile.TemporaryDirectory() as td:
        notices=[]; boost=FakeBoost(Path(td)/'boost.json',notices); boost.settings['clean_standby_memory']=False
        power=FakePower(); det=Detector(); mgr=PerformanceProfileManager(power,det,backup_path=Path(td)/'power.json',start_thread=False,register_atexit=False,game_boost=boost)
        mgr.set_mode('MAXIMUM_PERFORMANCE')
        det.games=[{'pid':101,'name':'gameA.exe','source':'STEAM'}]; mgr.poll_games_once(); st=mgr.status()
        results += [
            check('version',VERSION == '103'),
            check('maximum_mode_active',st['effective_profile']=='MAXIMUM_PERFORMANCE'),
            check('process_priority_high',boost.priority_calls==1),
            check('process_high_qos',boost.qos_calls==1),
            check('game_mode_enabled',boost.game_mode_calls==1),
            check('notification_uses_new_mode_name',len(notices)==1 and 'Máximo rendimiento' in notices[0][1] and 'Modo Gaming' not in notices[0][1]),
        ]
        mgr.poll_games_once(); results.append(check('same_game_not_reoptimized',boost.priority_calls==1 and len(notices)==1))
        det.games=[{'pid':101,'name':'gameA.exe','source':'STEAM'},{'pid':202,'name':'gameB.exe','source':'EPIC'}]; mgr.poll_games_once()
        results.append(check('second_game_optimized_without_profile_reapply',power.max_calls==1 and boost.priority_calls==2 and boost.qos_calls==2))
        det.games=[]; mgr.poll_games_once(); results.append(check('closing_last_ends_gameboost',not boost.status()['session_active']))
        mgr.shutdown(restore=True); results.append(check('shutdown_keeps_power_profile',power.restore_calls==0))
    ram_source=(ROOT/'core'/'ram_optimizer.py').read_text(encoding='utf-8')
    game_source=(ROOT/'performance'/'game_boost.py').read_text(encoding='utf-8')
    power_source=(ROOT/'performance'/'power_manager.py').read_text(encoding='utf-8')
    results += [
        check('game_ram_uses_standby_only','purge_standby_for_game' in ram_source and "working_sets_trimmed': 0" in ram_source),
        check('never_realtime_priority','REALTIME_PRIORITY_CLASS' not in game_source and 'HIGH_PRIORITY_CLASS' in game_source),
        check('high_qos_uses_process_power_throttling','SetProcessInformation' in game_source and 'PROCESS_POWER_THROTTLING_EXECUTION_SPEED' in game_source),
        check('epp_performance_supported','PERF_EPP' in power_source and 'EPP CPU -> {int(epp_value)}' in power_source),
    ]
    ok=all(results); print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}"); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
