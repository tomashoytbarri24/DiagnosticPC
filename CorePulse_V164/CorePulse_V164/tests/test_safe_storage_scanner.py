"""V100 — escáner de almacenamiento simple, allowlist-only y revalidado."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION
import core.safe_storage_cleanup as storage


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"[PASS] {name}")


def _touch(path: Path, data: bytes, mtime: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (mtime, mtime))


def main():
    check('version', VERSION == '103')
    check('strict_policy', storage.POLICY == 'ALLOWLIST_RECREATABLE_ONLY')

    original_rules = storage.safe_cleanup_rules
    original_units = storage.list_local_storage_units
    now = time.time()
    try:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            user_temp = base / 'Temp'
            explorer = base / 'Explorer'
            personal = base / 'Documents'
            old_temp = user_temp / 'old.tmp'
            fresh_temp = user_temp / 'fresh.tmp'
            thumb = explorer / 'thumbcache_256.db'
            personal_file = personal / 'tesis.docx'
            hard_a = user_temp / 'hard_a.tmp'
            hard_b = user_temp / 'hard_b.tmp'
            link = user_temp / 'linked.tmp'

            _touch(old_temp, b'a' * 1024, now - storage.MIN_TEMP_AGE_SECONDS - 60)
            _touch(fresh_temp, b'b' * 2048, now - 60)
            _touch(thumb, b'c' * 4096, now - 60)
            _touch(personal_file, b'personal', now - 999999)
            _touch(hard_a, b'hard', now - storage.MIN_TEMP_AGE_SECONDS - 60)
            try:
                os.link(hard_a, hard_b)
            except OSError:
                hard_b = None
            try:
                link.symlink_to(personal_file)
            except OSError:
                link = None

            storage.safe_cleanup_rules = lambda: (
                storage.SafeCleanupRule('user_temp', 'Temporales del usuario', (user_temp,), min_age_seconds=storage.MIN_TEMP_AGE_SECONDS),
                storage.SafeCleanupRule('thumbnail_cache', 'Caché de miniaturas', (explorer,), patterns=('thumbcache_*.db',), recursive=False),
            )
            storage.list_local_storage_units = lambda: [{
                'mountpoint': str(base), 'fstype': 'TEST', 'total_bytes': 10_000_000,
                'used_bytes': 5_000_000, 'free_bytes': 5_000_000, 'used_percent': 50.0,
            }]

            scan = storage.scan_safe_storage_cleanup(now=now)
            paths = {Path(item['path']) for item in scan['candidates']}
            check('scans_local_units', scan['units_scanned'] == 1)
            check('old_temp_is_candidate', old_temp in paths)
            check('thumbnail_is_candidate', thumb in paths)
            check('fresh_temp_is_not_candidate', fresh_temp not in paths)
            check('personal_file_is_never_candidate', personal_file not in paths)
            if hard_b is not None:
                check('hardlinks_are_not_candidates', hard_a not in paths and hard_b not in paths)
            if link is not None:
                check('symlink_is_not_candidate', link not in paths)
            check('only_positive_categories_surface', all(row['bytes'] > 0 and row['files'] > 0 for row in scan['categories']))
            check('measured_total_matches_candidates', scan['total_bytes'] == sum(item['size'] for item in scan['candidates']))

            result = storage.delete_scanned_candidates(scan)
            check('scanned_candidates_deleted', not old_temp.exists() and not thumb.exists())
            check('fresh_temp_survives', fresh_temp.exists())
            check('personal_file_survives', personal_file.exists())
            check('deletion_count_is_exact', result['deleted_files'] == 2)

            # Un archivo modificado después del análisis debe quedar fuera aunque
            # mantenga el mismo nombre y continúe dentro de una raíz permitida.
            _touch(old_temp, b'x' * 1000, now - storage.MIN_TEMP_AGE_SECONDS - 60)
            scan2 = storage.scan_safe_storage_cleanup(now=now)
            _touch(old_temp, b'changed-after-scan', now)
            result2 = storage.delete_scanned_candidates(scan2)
            check('changed_file_is_revalidated_and_skipped', old_temp.exists() and result2['skipped'] >= 1)
    finally:
        storage.safe_cleanup_rules = original_rules
        storage.list_local_storage_units = original_units

    actions = (ROOT / 'gui' / 'cleaning_actions.py').read_text(encoding='utf-8')
    pro = (ROOT / 'gui' / 'cleaning_center.py').read_text(encoding='utf-8')
    check('storage_has_analyze_then_clean', 'analyze_command=self.analyze_storage' in actions and 'self.clean_storage' in actions)
    check('professional_card_keeps_original_layout', "'Liberar Almacenamiento'" in pro and 'analyze_command=self.analyze_storage' in pro)
    storage_block = pro[pro.index("self.storage_card ="):pro.index("self.tool_cards =")]
    check('user_does_not_see_internal_states', all(word not in storage_block.upper() for word in ('SEGURO', 'REVISAR', 'PROTEGIDO', 'DESCONOCIDO')))
    check('simple_storage_copy', 'Solo muestra archivos eliminables.' in storage_block)
    print('RESULTADO: PASS')


if __name__ == '__main__':
    main()
