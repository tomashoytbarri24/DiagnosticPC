from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock, patch
import zipfile

import pytest

from core import update_manager as um


def _source_tree(root: Path, version: str, text: str = 'current') -> None:
    (root / 'core').mkdir(parents=True, exist_ok=True)
    (root / 'main.py').write_text(f'print({text!r})\n', encoding='utf-8')
    (root / 'core' / 'version.py').write_text(f'VERSION = {version!r}\n', encoding='utf-8')


def _release_zip(tmp_path: Path, version: str = '168') -> dict:
    archive = tmp_path / f'CorePulse_V{version}.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'CorePulse_V{version}/main.py', 'print("new")\n')
        zf.writestr(f'CorePulse_V{version}/core/version.py', f'VERSION = "{version}"\n')
        zf.writestr(f'CorePulse_V{version}/README.txt', 'release')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return {
        'verified': True,
        'path': str(archive),
        'expected_sha256': digest,
        'sha256': digest,
        'version': f'V{version}-dev',
    }


def test_source_update_is_installed_beside_current_version(tmp_path: Path):
    parent = tmp_path / 'DiagnosticPC-Maxi'
    current = parent / 'CorePulse_V167'
    _source_tree(current, '167')
    download = _release_zip(tmp_path)

    with patch.object(um, 'source_root', return_value=current), patch.object(um, 'updates_dir', return_value=tmp_path / 'updates'):
        plan = um.prepare_side_by_side_source_update(download)
        target = parent / 'CorePulse_V168'
        marker_path = um._side_by_side_marker_path(target)

    assert target.is_dir()
    assert (current / 'main.py').read_text(encoding='utf-8') == "print('current')\n"
    assert 'print("new")' in (target / 'main.py').read_text(encoding='utf-8')
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    assert marker['version'] == '168'
    assert marker['package_sha256'] == download['expected_sha256']
    assert plan['mode'] == 'side-by-side'
    assert Path(plan['target_root']) == target
    assert Path(plan['current_root']) == current


def test_existing_manual_target_is_never_overwritten(tmp_path: Path):
    parent = tmp_path / 'DiagnosticPC-Maxi'
    current = parent / 'CorePulse_V167'
    target = parent / 'CorePulse_V168'
    _source_tree(current, '167')
    _source_tree(target, '168', 'manual')
    download = _release_zip(tmp_path)

    with patch.object(um, 'source_root', return_value=current), patch.object(um, 'updates_dir', return_value=tmp_path / 'updates'):
        with pytest.raises(um.UpdateError, match='no la sobrescribirá'):
            um.prepare_side_by_side_source_update(download)

    assert (target / 'main.py').read_text(encoding='utf-8') == "print('manual')\n"


def test_helper_waits_for_current_process_then_launches_new_version(tmp_path: Path):
    parent = tmp_path / 'DiagnosticPC-Maxi'
    current = parent / 'CorePulse_V167'
    _source_tree(current, '167')
    download = _release_zip(tmp_path)

    with patch.object(um, 'source_root', return_value=current), patch.object(um, 'updates_dir', return_value=tmp_path / 'updates'):
        plan = um.prepare_side_by_side_source_update(download)

    ns = {'__name__': 'isolated_helper'}
    exec(compile(um._UPDATE_HELPER_SCRIPT, 'helper', 'exec'), ns)
    ns['wait_pid'] = Mock()
    ns['relaunch'] = Mock()

    with patch('sys.argv', ['helper', plan['plan']]):
        ns['main']()

    target = parent / 'CorePulse_V168'
    ns['wait_pid'].assert_called_once()
    ns['relaunch'].assert_called_once()
    assert ns['relaunch'].call_args.args[1] == target.resolve()
    status = json.loads(Path(plan['status']).read_text(encoding='utf-8'))
    assert status['ok'] is True
    assert status['action'] == 'side-by-side'
    assert Path(status['installed_root']) == target.resolve()


def test_update_ui_no_longer_exposes_manual_rollback():
    source = Path('gui/update_dialog.py').read_text(encoding='utf-8')
    assert 'text="Rollback"' not in source
    assert 'Preparar copia de prueba' not in source
    assert 'Actualizar y reiniciar' in source
