from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_v248_version_contract():
    from core import version
    assert version.VERSION == '248'
    assert 'ORIGINAL_PALETTE_INTEGRATED_PERSONALIZATION' in version.STAGE

def test_v248_original_resource_palette_restored():
    dash = (ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    assert "'cpu_card'" not in dash
    assert 'STORAGE_CARD_ACCENTS' not in dash
    assert "(app.card_cpu, app.lbl_cpu_title, app.lbl_cpu, app.lbl_cpu_temp, app.bar_cpu, COLORS['primary'])" in dash
    assert "(app.card_ram, app.lbl_ram_title, app.lbl_ram, app.lbl_ram_gb, app.bar_ram, COLORS['green'])" in dash
    assert "(app.card_gpu, app.lbl_gpu_title, app.lbl_gpu, app.lbl_gpu_temp, app.bar_gpu, COLORS['purple'])" in dash
    assert "_ensure_soft_card_accent(app.frame_charts, COLORS['primary'], placement='left')" in dash
    assert "(app.card_cpu, app.lbl_cpu_title, app.lbl_cpu, app.lbl_cpu_temp, app.bar_cpu, CYAN)" in layout
    assert "(app.card_ram, app.lbl_ram_title, app.lbl_ram, app.lbl_ram_gb, app.bar_ram, GREEN)" in layout
    assert "(app.card_gpu, app.lbl_gpu_title, app.lbl_gpu, app.lbl_gpu_temp, app.bar_gpu, PURPLE)" in layout

def test_v248_personalization_has_no_enclosing_card():
    dash = (ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    layout = (ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    assert "personalization_block = ctk.CTkFrame(\n        app.sidebar,\n        fg_color='transparent',\n        border_width=0,\n        corner_radius=0" in dash
    assert "personalization_block.pack(side='top', fill='x', padx=0" in dash
    assert "_cfg(getattr(app, '_personalization_block', None), fg_color='transparent', border_width=0, corner_radius=0)" in layout
    assert "_cfg(personal, fg_color='transparent', border_width=0, corner_radius=0)" in layout

def test_v248_preserves_storage_alignment_and_square_trends():
    main = (ROOT/'main.py').read_text(encoding='utf-8')
    layout = (ROOT/'gui'/'dashboard_layout.py').read_text(encoding='utf-8')
    dash = (ROOT/'gui'/'dashboard.py').read_text(encoding='utf-8')
    assert "card.pack(fill='x', pady=3, padx=0)" in main
    assert "card.pack_configure(fill='x', expand=False, padx=0, pady=2)" in layout
    assert "app.frame_charts,\n        fg_color=COLORS['surface'],\n        border_color=COLORS['border'],\n        border_width=1,\n        corner_radius=0" in dash
    assert "_cfg(app.frame_charts, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=0)" in layout
