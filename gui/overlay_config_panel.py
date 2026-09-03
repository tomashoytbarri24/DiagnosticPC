"""Permite configurar las métricas y preferencias mostradas en el overlay."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import customtkinter as ctk
from core.overlay_preferences import DEFAULTS, load_overlay_preferences, reset_overlay_preferences, save_overlay_preferences
BG = theme_color('#0d1828')
INNER = theme_color('#0a1422')
CARD = theme_color('#101d2e')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
DIM = theme_color('#aebdd0')
MUTED = theme_color('#72849b')
CYAN = '#38bdf8'
GREEN = '#22c993'
WARN = '#f0a23a'

class OverlayConfigPanel:

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self._alive = True
        p = load_overlay_preferences()
        self.root = ctk.CTkFrame(parent, fg_color=BG, border_width=1, border_color=BORDER, corner_radius=14)
        self.layout_var = ctk.StringVar(value='Completo' if p['layout'] == 'FULL' else 'Compacto')
        self.pixel_var = ctk.StringVar(value=f"{p['pixel']}x")
        self.x_var = ctk.StringVar(value=str(p['x']))
        self.y_var = ctk.StringVar(value=str(p['y']))
        self.metric_vars = {k: ctk.BooleanVar(value=p[k]) for k in ('show_fps', 'show_frametime', 'show_1pct_low', 'show_cpu', 'show_ram', 'show_gpu', 'show_storage')}
        self._build()
        self.root.after(200, self._status_tick)

    def widget(self):
        return self.root

    def destroy(self):
        self._alive = False

    def _build(self):
        header = ctk.CTkFrame(self.root, fg_color='transparent')
        header.pack(fill='x', padx=16, pady=(14, 10))
        left = ctk.CTkFrame(header, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(left, text='Overlay In-Game', font=('Segoe UI', 20, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(left, text='Presentación configurable; FPS y telemetría mantienen sus fuentes reales certificadas.', font=('Segoe UI', 9), text_color=DIM, anchor='w').pack(anchor='w', pady=(2, 0))
        self.status_badge = ctk.CTkLabel(header, text='DETENIDO', font=('Segoe UI', 9, 'bold'), text_color=MUTED, fg_color=theme_color(theme_color('#102235')), corner_radius=8, padx=10, pady=5)
        self.status_badge.pack(side='right', padx=(12, 0))
        status = ctk.CTkFrame(self.root, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=11)
        status.pack(fill='x', padx=14, pady=(0, 10))
        self.lbl_rtss = ctk.CTkLabel(status, text='RTSS: overlay detenido', font=('Segoe UI', 10, 'bold'), text_color=DIM, anchor='w')
        self.lbl_rtss.pack(fill='x', padx=12, pady=(9, 1))
        self.lbl_app = ctk.CTkLabel(status, text='Aplicación 3D: N/A', font=('Segoe UI', 9), text_color=DIM, anchor='w')
        self.lbl_app.pack(fill='x', padx=12, pady=(0, 1))
        self.lbl_policy = ctk.CTkLabel(status, text='FPS: REAL_FPS_OR_NA_ONLY', font=('Segoe UI', 8, 'bold'), text_color=CYAN, anchor='w')
        self.lbl_policy.pack(fill='x', padx=12, pady=(0, 9))
        self.body = ctk.CTkFrame(self.root, fg_color='transparent')
        self.body.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        self.metrics = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=11)
        self.metrics.pack(side='left', fill='both', expand=True, padx=(0, 5))
        metrics = self.metrics
        ctk.CTkLabel(metrics, text='MÉTRICAS VISIBLES', font=('Segoe UI', 9, 'bold'), text_color=MUTED).pack(anchor='w', padx=12, pady=(11, 6))
        for key, label in (('show_fps', 'FPS'), ('show_frametime', 'Frametime'), ('show_1pct_low', '1% Low'), ('show_cpu', 'CPU · uso / temperatura / GHz'), ('show_ram', 'RAM · uso'), ('show_gpu', 'GPU · uso / temperatura / hotspot'), ('show_storage', 'Almacenamiento · temperatura / vida')):
            ctk.CTkSwitch(metrics, text=label, variable=self.metric_vars[key], command=self._save_live, font=('Segoe UI', 9), text_color=TEXT, progress_color=CYAN).pack(anchor='w', padx=12, pady=5)
        self.visual = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=11)
        self.visual.pack(side='left', fill='both', expand=True, padx=(5, 0))
        visual = self.visual
        ctk.CTkLabel(visual, text='PRESENTACIÓN', font=('Segoe UI', 9, 'bold'), text_color=MUTED).pack(anchor='w', padx=12, pady=(11, 6))
        ctk.CTkLabel(visual, text='Diseño', font=('Segoe UI', 9), text_color=DIM).pack(anchor='w', padx=12, pady=(4, 3))
        ctk.CTkSegmentedButton(visual, values=['Completo', 'Compacto'], variable=self.layout_var, command=lambda _=None: self._save_live()).pack(fill='x', padx=12)
        ctk.CTkLabel(visual, text='Escala RTSS', font=('Segoe UI', 9), text_color=DIM).pack(anchor='w', padx=12, pady=(12, 3))
        ctk.CTkSegmentedButton(visual, values=['1x', '2x', '3x', '4x'], variable=self.pixel_var, command=lambda _=None: self._save_live()).pack(fill='x', padx=12)
        ctk.CTkLabel(visual, text='Posición RTSS', font=('Segoe UI', 9), text_color=DIM).pack(anchor='w', padx=12, pady=(12, 3))
        pos = ctk.CTkFrame(visual, fg_color='transparent')
        pos.pack(fill='x', padx=12)
        for title, var in (('X', self.x_var), ('Y', self.y_var)):
            g = ctk.CTkFrame(pos, fg_color='transparent')
            g.pack(side='left', fill='x', expand=True, padx=4)
            ctk.CTkLabel(g, text=title, font=('Segoe UI', 8, 'bold'), text_color=MUTED).pack(anchor='w')
            e = ctk.CTkEntry(g, textvariable=var, height=30, fg_color=INNER, border_color=BORDER, text_color=TEXT)
            e.pack(fill='x', pady=(2, 0))
            e.bind('<Return>', lambda _e: self._save_live())
            e.bind('<FocusOut>', lambda _e: self._save_live())
        ctk.CTkLabel(visual, text='Los cambios se aplican en vivo al overlay activo.', font=('Segoe UI', 8), text_color=MUTED, wraplength=330, justify='left').pack(anchor='w', padx=12, pady=(12, 10))
        footer = ctk.CTkFrame(self.root, fg_color='transparent')
        footer.pack(fill='x', padx=14, pady=(0, 14))
        self.btn_toggle = ctk.CTkButton(footer, text='Iniciar Overlay', command=self._toggle_overlay, height=34, fg_color=theme_color('#123e5c'), hover_color=theme_color('#174e72'), text_color=TEXT, font=('Segoe UI', 10, 'bold'))
        self.btn_toggle.pack(side='left')
        ctk.CTkButton(footer, text='Guardar', command=self._save_live, height=34, width=100, fg_color='transparent', hover_color=theme_color('#14253b'), border_width=1, border_color=BORDER, text_color=TEXT).pack(side='right', padx=(6, 0))
        ctk.CTkButton(footer, text='Restaurar', command=self._reset, height=34, width=100, fg_color='transparent', hover_color=theme_color('#14253b'), border_width=1, border_color=BORDER, text_color=DIM).pack(side='right')
        self._layout_mode = None
        self.root.bind('<Configure>', self._on_resize, add='+')
        self.root.after(80, self._apply_responsive_layout)

    def _on_resize(self, event=None):
        if not self._alive or (event is not None and getattr(event, 'widget', None) is not self.root):
            return
        try:
            self.root.after_idle(self._apply_responsive_layout)
        except Exception:
            pass

    def _apply_responsive_layout(self):
        if not self._alive:
            return
        try:
            width = int(self.root.winfo_width())
        except Exception:
            width = 900
        # El área útil de CorePulse normalmente supera 800 px. Solo apilamos
        # si realmente queda estrecha, evitando recortes sin cambiar la ventana.
        mode = 'stacked' if width < 720 else 'columns'
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        try:
            self.metrics.pack_forget()
            self.visual.pack_forget()
            if mode == 'stacked':
                self.metrics.pack(fill='x', expand=False, pady=(0, 6))
                self.visual.pack(fill='x', expand=False)
            else:
                self.metrics.pack(side='left', fill='both', expand=True, padx=(0, 5))
                self.visual.pack(side='left', fill='both', expand=True, padx=(5, 0))
        except Exception:
            pass

    def _collect(self):
        try:
            pixel = int(str(self.pixel_var.get()).replace('x', ''))
        except Exception:
            pixel = DEFAULTS['pixel']
        try:
            x = int(self.x_var.get())
        except Exception:
            x = DEFAULTS['x']
        try:
            y = int(self.y_var.get())
        except Exception:
            y = DEFAULTS['y']
        d = {'layout': 'FULL' if self.layout_var.get() == 'Completo' else 'COMPACT', 'x': x, 'y': y, 'pixel': pixel}
        for k, v in self.metric_vars.items():
            d[k] = bool(v.get())
        return d

    def _save_live(self):
        p = save_overlay_preferences(self._collect())
        self.x_var.set(str(p['x']))
        self.y_var.set(str(p['y']))
        self.pixel_var.set(f"{p['pixel']}x")
        return p

    def _reset(self):
        p = reset_overlay_preferences()
        self.layout_var.set('Completo')
        self.pixel_var.set(f"{p['pixel']}x")
        self.x_var.set(str(p['x']))
        self.y_var.set(str(p['y']))
        for k, v in self.metric_vars.items():
            v.set(bool(p[k]))

    def _toggle_overlay(self):
        self._save_live()
        self.app.toggle_overlay()
        self._refresh_status()

    def _refresh_status(self):
        overlay = getattr(self.app, 'overlay_window', None)
        running = bool(overlay is not None and overlay.winfo_exists())
        if not running:
            self.status_badge.configure(text='DETENIDO', text_color=MUTED)
            self.lbl_rtss.configure(text='RTSS: overlay detenido', text_color=DIM)
            self.lbl_app.configure(text='Aplicación 3D: N/A')
            self.btn_toggle.configure(text='Iniciar Overlay')
            return
        try:
            status = overlay.get_status() or {}
        except Exception:
            status = {}
        available = bool(status.get('rtss_available'))
        active = status.get('active_app') or {}
        app_name = active.get('name') if isinstance(active, dict) else None
        error = status.get('last_error')
        self.status_badge.configure(text='ACTIVO' if available else 'ESPERANDO RTSS', text_color=GREEN if available else WARN)
        self.lbl_rtss.configure(text=f"RTSS: conectado · v{status.get('rtss_version')}" if available else f"RTSS: {error or 'no disponible'}", text_color=GREEN if available else WARN)
        self.lbl_app.configure(text=f"Aplicación 3D: {app_name or 'N/A'}")
        self.lbl_policy.configure(text=f"FPS: {status.get('fps_policy') or 'REAL_FPS_OR_NA_ONLY'}")
        self.btn_toggle.configure(text='Detener Overlay')

    def _status_tick(self):
        if not self._alive:
            return
        try:
            if not self.root.winfo_exists():
                return
            self._refresh_status()
            self.root.after(800, self._status_tick)
        except Exception:
            pass
