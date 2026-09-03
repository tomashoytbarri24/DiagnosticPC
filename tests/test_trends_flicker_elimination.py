"""Regresión V0.10.0.0w: Tendencias no debe crear/dibujar un canvas TkAgg visible."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import VERSION


def check(name, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {bool(condition)}")
    return bool(condition)


def main():
    panel = (ROOT / 'gui' / 'session_trends_panel.py').read_text(encoding='utf-8')
    checks = [
        check('version', VERSION == '0.10.0.0w'),
        check('tkagg_removed_from_trends', 'FigureCanvasTkAgg' not in panel),
        check('agg_offscreen_renderer', 'FigureCanvasAgg' in panel and 'agg.draw()' in panel),
        check('persistent_native_image_surface', 'self.chart_image = tk.Label' in panel and 'self._chart_photo' in panel),
        check('no_visible_canvas_draw', 'self.canvas.draw()' not in panel and 'get_tk_widget()' not in panel),
        check('data_signature_skips_repaint', '_last_render_signature' in panel and 'signature == self._last_render_signature' in panel),
        check('chart_is_published_after_raster', 'ImageTk.PhotoImage' in panel and 'chart_image.configure(image=photo' in panel),
        check('figure_is_released', 'fig.clear()' in panel),
    ]
    ok = all(checks)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
