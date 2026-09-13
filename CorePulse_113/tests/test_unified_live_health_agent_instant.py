"""Agent instant sample must participate in unified live-health authority."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.live_health import evaluate_unified_live_health

def main():
    telemetry={'cpu_temp': 70.0, 'gpu_temp': 50.0, '_cpu': {}}
    agent={'overall':'NORMAL','instant':{'severity':'CRITICAL','status':'TEMPERATURA CRÍTICA','reasons':['CPU a 4.0 °C de TjMax'],'synthetic':False,'estimated':False}}
    result=evaluate_unified_live_health(telemetry, [], preliminary_score=95.0, agent_state=agent)
    assert result['severity']=='CRITICAL', result
    assert result['authority']=='REALTIME_AGENT_CURRENT_SAMPLE', result
    assert result['score'] is None or result['score'] <= 49.0, result
    assert 'CPU a 4.0 °C de TjMax' in result['reasons'], result
    assert result['sensor_values_unchanged'] is True
    print('[PASS] unified live health consumes real agent instant condition without mutating sensors')

if __name__=='__main__': main()
