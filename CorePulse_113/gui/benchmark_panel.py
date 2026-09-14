"""Página principal independiente del Benchmark visual de CorePulse."""
from __future__ import annotations

import customtkinter as ctk

from core.theme_manager import color as theme_color
from gui.health_center_panel import HealthCenterPanel
from gui.internal_navigation import show_dashboard
from gui.professional_visuals import build_title_block

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
BORDER = theme_color('#1b3048')
TEXT2 = theme_color('#b8c4d4')
PURPLE = '#a855f7'
FONT = 'Segoe UI'


class BenchmarkPanel:
    """Host dedicado: no contiene Gaming, diagnóstico ni otras herramientas."""

    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self.frame = ctk.CTkFrame(host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(12, 4))
        back = ctk.CTkButton(
            header, text='Volver al monitoreo', command=lambda: show_dashboard(self.app),
            width=172, height=31, corner_radius=8, fg_color='transparent',
            hover_color=theme_color('#102840'), border_width=1, border_color=BORDER,
            text_color=TEXT2, font=(FONT, 9, 'bold'),
        )
        back.pack(side='left', pady=(8, 0))

        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=(14, 12))
        hero = build_title_block(
            titles,
            eyebrow='Rendimiento de hardware',
            title='Benchmark',
            subtitle='Benchmark visual reproducible de GPU, CPU y RAM con métricas y telemetría reales.',
            accent=PURPLE,
            badges=(),
            title_size=22,
        )
        hero['frame'].pack(anchor='w', fill='x')

        content = ctk.CTkFrame(self.frame, fg_color=BG, corner_radius=0)
        content.pack(fill='both', expand=True, padx=15, pady=(0, 10))
        self._benchmark = HealthCenterPanel(
            app, content, performance_only=True, benchmark_only=True
        )

    def widget(self):
        return self.frame

    def set_active(self, active):
        try:
            self._benchmark.set_active(active)
        except Exception:
            pass

    def refresh(self):
        try:
            self._benchmark.refresh()
        except Exception:
            pass

    def destroy(self):
        self._alive = False
        try:
            self._benchmark.destroy()
        except Exception:
            pass
        try:
            self.frame.destroy()
        except Exception:
            pass
