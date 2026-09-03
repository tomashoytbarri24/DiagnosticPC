"""Regresión específica del motor de scroll V2."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.version import VERSION

def main():
    text=(ROOT/'gui'/'stable_scroll.py').read_text(encoding='utf-8')
    checks={
        'version': VERSION == '0.10.0.0w',
        'no_canvas': 'tk.Canvas(' not in text and '.create_window(' not in text,
        'native_viewport': 'self.viewport = tk.Frame' in text,
        'content_is_clipped_child': 'self.content = ctk.CTkFrame(self.viewport' in text,
        'place_scroll': 'self.content.place_configure(y=-int(round(self._offset)))' in text,
        '60fps_coalescing': 'self.after(16, self._flush_motion)' in text,
        'touchpad_delta': '-delta / 120.0' in text,
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
