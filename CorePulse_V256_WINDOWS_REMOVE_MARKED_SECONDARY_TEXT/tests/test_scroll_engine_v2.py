"""Regresión específica del motor de scroll V3 (Canvas nativo/directo)."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.version import VERSION

def main():
    text=(ROOT/'gui'/'stable_scroll.py').read_text(encoding='utf-8')
    checks={
        'version': VERSION == '103',
        'native_canvas': 'self.canvas = tk.Canvas(' in text and 'self.canvas.create_window' in text,
        'content_single_embedded_window': 'self._window_item = self.canvas.create_window' in text and 'window=self.content' in text,
        'no_manual_place_scroll': 'content.place_configure(y=' not in text and '_target_offset' not in text,
        'scrollbar_direct': 'self.canvas.yview_moveto' in text and 'def _scrollbar_command' in text,
        'wheel_direct_pixels': 'self.canvas.yview_scroll(amount' in text and 'yscrollincrement=1' in text,
        'touchpad_delta': '-delta / 120.0' in text,
        'no_time_interpolation': 'math.exp(' not in text and '_motion_tau' not in text,
        'windows_native_redraw': 'RedrawWindow' in text and 'ALLCHILDREN' in text,
        'defer_repaint': 'defer_until_idle' in text and 'is_scrolling()' in text,
        'compat_api': '_schedule_scrollregion' in text and '_refresh_scrollregion' in text,
    }
    ok=True
    for name,value in checks.items():
        print(f"[{'PASS' if value else 'FAIL'}] {name}: {bool(value)}")
        ok &= bool(value)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
