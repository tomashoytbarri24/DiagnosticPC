from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _main_source():
    return (ROOT / "main.py").read_text(encoding="utf-8")

def test_v302_visual_mask_path_is_superseded():
    src = _main_source()
    method = src[src.index("    def set_sidebar_collapsed"):src.index("    def toggle_sidebar_collapse")]
    assert "_show_sidebar_transition_cover" not in method
    assert "_run_sidebar_motion_effect" not in method
    assert "_capture_sidebar_transition_snapshot" not in method

def test_native_redraw_is_kept_only_for_final_commit():
    src = _main_source()
    assert "ImageGrab.grab" not in src
    assert "WM_SETREDRAW = 0x000B" in src
    assert "def _commit_sidebar_drawer_state" in src
