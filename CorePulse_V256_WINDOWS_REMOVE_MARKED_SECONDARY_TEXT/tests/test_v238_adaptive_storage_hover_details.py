from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_v238_version_contract():
    from core import version
    assert version.VERSION == '238'
    assert 'ADAPTIVE_STORAGE_HOVER_DETAILS' in version.STAGE


def test_storage_cards_use_hover_only_details():
    src = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    block = src.split('def _ensure_storage_card_decor', 1)[1].split('def _ensure_chart_accents', 1)[0]
    assert "_bind_card_hover(" in block
    assert "action_button=details" in block
    assert "details.place(" not in block
    assert "card._corepulse_storage_v238 = True" in block


def test_storage_height_contract_for_multi_disk():
    src = (ROOT / 'gui' / 'dashboard_layout.py').read_text(encoding='utf-8')
    block = src.split('def _storage_height_for', 1)[1].split('def _sync_storage_height', 1)[0]
    assert "if count == 1:" in block
    assert "return one" in block
    assert "return two" in block
    assert "card_h = 86" in block
    assert "if disk_count <= 2:" in src


def test_disk_update_reflows_height_and_keeps_per_disk_command():
    src = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert "command=lambda disk_index=idx: self.open_storage_details(disk_index)" in src
    assert "_sync_storage_height(self, getattr(self, '_layout_mode', 'compact'))" in src
