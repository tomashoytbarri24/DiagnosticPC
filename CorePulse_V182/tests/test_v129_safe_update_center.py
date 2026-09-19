"""V129 — centro de actualizaciones con descarga verificada, backup y rollback."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION, STAGE
from core import update_manager as um


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('[PASS]', name)


class _Response:
    def __init__(self, data: bytes, headers=None):
        self._io = io.BytesIO(data)
        self.headers = headers or {}
    def read(self, size=-1): return self._io.read(size)
    def __enter__(self): return self
    def __exit__(self, *args): return False


def sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main():
    check('version', VERSION.isdecimal())
    check('stage', bool(STAGE))
    check('channels', um.CHANNEL_DEVELOPMENT == um.CHANNEL_INTERNAL and um.CHANNEL_STABLE == 'stable')

    stable = um.ReleaseInfo('V129', 'V129', 'stable', False, None, None, ())
    preview = um.ReleaseInfo('V130', 'V130 beta', 'dev', True, None, None, ())
    check('development_sees_prerelease', um.choose_release([stable, preview], um.CHANNEL_DEVELOPMENT).tag == 'V130')
    check('stable_ignores_prerelease', um.choose_release([stable, preview], um.CHANNEL_STABLE).tag == 'V129')

    payload = b'corepulse-update-package'
    digest = hashlib.sha256(payload).hexdigest()
    asset = um.ReleaseAsset('CorePulse_V130.zip', len(payload), 'https://example/pkg', '', None, 'application/zip')
    sidecar = um.ReleaseAsset('CorePulse_V130.zip.sha256', 80, 'https://example/hash', '', None, 'text/plain')
    release = um.ReleaseInfo('V130', 'V130', 'notes', True, '2026-09-14T20:00:00Z', None, (asset, sidecar))
    def opener(req, **kwargs):
        url = getattr(req, 'full_url', str(req))
        if url.endswith('/hash'):
            return _Response(f'{digest}  CorePulse_V130.zip\n'.encode())
        return _Response(payload, {'Content-Length': str(len(payload))})
    expected, source = um.resolve_release_sha256(release, asset, opener=opener)
    check('sidecar_sha256', expected == digest and source.startswith('sidecar:'))

    old_data = os.environ.get('COREPULSE_DATA_DIR')
    with tempfile.TemporaryDirectory() as td:
        os.environ['COREPULSE_DATA_DIR'] = td
        downloaded = um.download_asset_verified(asset, release, opener=opener)
        check('verified_download', downloaded['verified'] is True and downloaded['sha256'] == digest)
        check('only_asset_downloaded', Path(downloaded['path']).name == 'CorePulse_V130.zip')
    if old_data is None:
        os.environ.pop('COREPULSE_DATA_DIR', None)
    else:
        os.environ['COREPULSE_DATA_DIR'] = old_data

    core = (ROOT / 'core' / 'update_manager.py').read_text(encoding='utf-8')
    ui = (ROOT / 'gui' / 'update_dialog.py').read_text(encoding='utf-8')
    check('git_checkout_guard', 'source-git' in core and 'no sobrescribe código versionado' in core)
    check('backup_and_rollback', all(token in core for token in ('create_source_backup', 'prepare_source_rollback', 'BACKUP_KEEP = 3')))
    check('detached_helper', 'launch_source_update_helper' in core and '_UPDATE_HELPER_SCRIPT' in core)
    check('ui_professional_fields', all(token in ui for token in ('Versión instalada', 'Versión disponible', 'SEGURIDAD Y RECUPERACIÓN', 'Descargar y verificar')))
    check('ui_channels', '"Desarrollo": CHANNEL_INTERNAL' in ui and '"Estable": CHANNEL_STABLE' in ui)
    check('ui_exact_theme_roles', 'from core.theme_manager import role_color' in ui and 'theme_color' not in ui)
    check('ui_does_not_clone', 'no clona el repositorio' in ui)

    expected_hashes = {
        'core/runtime_venv_path.py': '263d725dc8a50ef57d2e0dd8d8827968f58d2b67dcee6b0a276ca6dd8d562e92',
        'bootstrap_corepulse.py': '925d4ef090b28c27ceffbbbba9362a8137f665212ac445e96a096c0ce5e17a0b',
        'core/source_runtime_bootstrap.py': 'bde37780c35ebc280b0b22ac6a71926051ae9fde48b65935b6af64b819f7ccfd',
        'requirements-runtime-lock.txt': '36ee044c5dab3c5c8cfecbe0456923c9f406d83a93ef04d93f9fd27f1566c706',
        'core/nvme_smart_windows.py': 'fe9481d270d5b47299b97fc97d37ee56f65bd904333f634255e4a91e63958283',
    }
    for rel, digest_value in expected_hashes.items():
        check(f'protected_unchanged:{rel}', sha256(rel) == digest_value)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
