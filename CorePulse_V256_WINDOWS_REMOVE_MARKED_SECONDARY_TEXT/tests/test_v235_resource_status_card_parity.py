from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_v235_version_contract():
    from core import version
    assert version.VERSION == '235'
    assert 'RESOURCE_STATUS_CARD_PARITY' in version.STAGE


def test_v235_resource_cards_are_rebuilt_like_status_cards():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'Reconstruye la tarjeta con la MISMA composición de las tarjetas superiores.' in text
    assert "accent_bar = ctk.CTkFrame(shell, fg_color=accent, width=4" in text
    assert "icon_box = ctk.CTkLabel(" in text
    assert "eyebrow = ctk.CTkLabel(text_box" in text
    assert "app.lbl_cpu_title, app.lbl_cpu, app.bar_cpu, app.lbl_cpu_temp = title, value, bar, detail" in text
    assert "app.lbl_ram_title, app.lbl_ram, app.bar_ram, app.lbl_ram_gb = title, value, bar, detail" in text
    assert "app.lbl_gpu_title, app.lbl_gpu, app.bar_gpu, app.lbl_gpu_temp = title, value, bar, detail" in text


def test_v235_storage_uses_same_composition():
    text = (ROOT / 'gui' / 'dashboard.py').read_text(encoding='utf-8')
    assert 'Da al almacenamiento la misma formación visual de las tarjetas superiores.' in text
    assert "eyebrow = ctk.CTkLabel(top, text='ALMACENAMIENTO'" in text
    assert "widgets.update({'lbl_name': name, 'lbl_badge': badge, 'lbl_exact': exact, 'bar': bar, 'btn_details': details})" in text


def test_v235_hardware_view_does_not_reintroduce_legacy_multiline_titles():
    text = (ROOT / 'gui' / 'hardware_storage_view.py').read_text(encoding='utf-8')
    assert "text=cpu_name" in text
    assert "text='Uso físico del sistema'" in text
    assert "text=gpu_name" in text
    assert "text=f'CPU\\n{cpu_name}'" not in text
