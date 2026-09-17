"""V100 — el runtime fuente no depende de la longitud del proyecto."""
from pathlib import Path
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
from core.runtime_venv_path import source_runtime_venv


def check(name, value):
    if not value:
        raise AssertionError(name)
    print('[PASS]', name)


def main():
    check('version', VERSION == '103')
    with tempfile.TemporaryDirectory() as td:
        fake_root = Path(td) / ('ruta_muy_larga_' * 12)
        fake_root.mkdir(parents=True)
        (fake_root / 'requirements-runtime-lock.txt').write_text('psutil==7.2.2\n', encoding='utf-8')
        previous = os.environ.get('COREPULSE_VENV')
        os.environ['COREPULSE_VENV'] = str(Path(td) / 'cp_runtime_short')
        try:
            venv = source_runtime_venv(fake_root)
        finally:
            if previous is None:
                os.environ.pop('COREPULSE_VENV', None)
            else:
                os.environ['COREPULSE_VENV'] = previous
        check('override_supported', venv.name == 'cp_runtime_short')
        check('does_not_live_under_project', str(fake_root) not in str(venv))

    helper=(ROOT/'core'/'runtime_venv_path.py').read_text(encoding='utf-8')
    boot=(ROOT/'bootstrap_corepulse.py').read_text(encoding='utf-8')
    src=(ROOT/'core'/'source_runtime_bootstrap.py').read_text(encoding='utf-8')
    batch=(ROOT/'instalar_dependencias.bat').read_text(encoding='utf-8')
    check('windows_uses_userprofile_short_runtime', 'USERPROFILE' in helper and '.corepulse' in helper and 'runtime' in helper)
    check('lock_tokenized', '_lock_token(root)' in helper)
    check('bootstrap_shared_resolver', 'source_runtime_venv(ROOT)' in boot)
    check('source_runtime_shared_resolver', 'source_runtime_venv(root)' in src)
    check('build_uses_short_path', 'LOCALAPPDATA' in batch and 'CorePulse\\build\\py312' in batch)
    print('RESULTADO: PASS')

if __name__ == '__main__':
    main()
