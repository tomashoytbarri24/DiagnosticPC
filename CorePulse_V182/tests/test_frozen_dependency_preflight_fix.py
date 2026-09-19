"""Regresión: dependencias empaquetadas y degradación de capacidades externas."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import VERSION, STAGE
from core.startup_readiness import ESSENTIAL_IMPORTS, BUNDLED_CAPABILITY_IMPORTS, format_blocking_message, ReadinessReport, ReadinessItem

def check(name,cond):
    if not cond: raise AssertionError(name)
    print('[PASS]',name)

def main():
    spec=(ROOT/'build/CorePulse.spec').read_text(encoding='utf-8')
    readiness=(ROOT/'core/startup_readiness.py').read_text(encoding='utf-8')
    check('version',VERSION.isdecimal())
    check('stage',bool(STAGE))
    check('send2trash_degradable_at_runtime',any(m=='send2trash' for m,_ in BUNDLED_CAPABILITY_IMPORTS) and all(m!='send2trash' for m,_ in ESSENTIAL_IMPORTS))
    check('groq_degradable_at_runtime',any(m=='groq' for m,_ in BUNDLED_CAPABILITY_IMPORTS))
    check('bundle_contains_dynamic_deps',all(x in spec for x in ('"send2trash"','"groq"','"win32api"','"pythoncom"','"pywintypes"','"clr"','"pythonnet"')))
    fake=ReadinessReport(generated_at='x',version=VERSION,platform='Windows',python='3.12',architecture='64-bit',ready=False,frozen=True,items=[ReadinessItem('x','Núcleo','ERROR',True,'faltante')])
    msg=format_blocking_message(fake)
    check('frozen_never_requests_pip','no instales paquetes Python manualmente' in msg and 'Ejecuta instalar_dependencias.bat' not in msg)
    check('hardwaremonitor_probe_present','_probe_hardwaremonitor' in readiness)
    print('RESULTADO: PASS')
if __name__=='__main__': main()
