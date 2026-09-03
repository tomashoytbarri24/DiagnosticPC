"""Regresión V0.10.0.0w: tema claro cómodo y tarjetas definidas."""
from pathlib import Path
import sys, tempfile
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.version import VERSION, STAGE
import core.theme_manager as tm

def check(name, value):
    print(f"[{'PASS' if value else 'FAIL'}] {name}: {bool(value)}")
    return bool(value)

def rgb(hexv):
    h=hexv.lstrip('#')
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def distance(a,b):
    aa,bb=rgb(a),rgb(b)
    return sum(abs(x-y) for x,y in zip(aa,bb))

def luminance(v):
    r,g,b=rgb(v)
    return (0.2126*r + 0.7152*g + 0.0722*b)/255.0

def main():
    old=tm._THEME_FILE
    try:
        with tempfile.TemporaryDirectory() as td:
            tm._THEME_FILE=Path(td)/'ui_theme.json'
            tm.set_theme(tm.LIGHT)
            app=tm.color('#06111f')
            sidebar=tm.color('#071522')
            card=tm.color('#0b1726')
            inner=tm.color('#0a1524')
            border=tm.color('#17314d')
            soft=tm.color('#102943')
            track=tm.color('#132741')
            grid=tm.color('#334155')
            text=tm.color('#f4f7fb')
    finally:
        tm._THEME_FILE=old
    results=[
        check('version', VERSION=='0.10.0.0w'),
        check('stage', STAGE=='HEALTH_INTELLIGENCE_RECOVERY'),
        check('no_pure_white_app', app.lower() not in {'#ffffff','#f7f9fc','#f8fafc'}),
        check('no_pure_white_card', card.lower()!='#ffffff'),
        check('light_is_comfortably_dimmed', luminance(app) < 0.92 and luminance(card) < 0.97),
        check('card_separates_from_app', distance(app,card) >= 25),
        check('border_is_visible', distance(card,border) >= 75),
        check('soft_border_is_visible', distance(card,soft) >= 45),
        check('sidebar_is_distinct', distance(app,sidebar) >= 15),
        check('inner_surface_distinct', distance(card,inner) >= 20),
        check('track_not_white', luminance(track) < 0.90),
        check('grid_not_white', luminance(grid) < 0.88),
        check('text_is_dark', luminance(text) < 0.25),
    ]
    ok=all(results)
    print(f"\nRESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
