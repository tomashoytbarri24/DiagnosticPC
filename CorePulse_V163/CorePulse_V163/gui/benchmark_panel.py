"""Página principal independiente del Benchmark visual de CorePulse."""
from __future__ import annotations

import customtkinter as ctk

from core.theme_manager import color as theme_color
from gui.health_center_panel import HealthCenterPanel
from gui.benchmark_history_panel import BenchmarkHistoryPanel
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
            subtitle='Configura y ejecuta cargas reales de GPU, CPU, RAM y SSD con telemetría y resultados medidos.',
            accent=PURPLE,
            badges=(),
            title_size=22,
        )
        hero['frame'].pack(anchor='w', fill='x')

        tabs = ctk.CTkFrame(header, fg_color='transparent')
        tabs.pack(side='right', pady=(8, 0))
        self._run_tab = ctk.CTkButton(
            tabs, text='Ejecutar', command=lambda: self._show_section('run'),
            width=92, height=31, corner_radius=8, fg_color=PURPLE,
            hover_color=theme_color('#7e22ce'), border_width=1,
            border_color=theme_color('#c084fc'), text_color='#ffffff', font=(FONT, 9, 'bold'),
        )
        self._run_tab.pack(side='left', padx=(0, 6))
        self._history_tab = ctk.CTkButton(
            tabs, text='Historial', command=lambda: self._show_section('history'),
            width=92, height=31, corner_radius=8, fg_color='transparent',
            hover_color=theme_color('#102840'), border_width=1, border_color=BORDER,
            text_color=TEXT2, font=(FONT, 9, 'bold'),
        )
        self._history_tab.pack(side='left')

        self._content = ctk.CTkFrame(self.frame, fg_color=BG, corner_radius=0)
        self._content.pack(fill='both', expand=True, padx=15, pady=(0, 10))
        self._run_host = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        self._history_host = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        self._run_host.pack(fill='both', expand=True)
        self._benchmark = HealthCenterPanel(
            app, self._run_host, performance_only=True, benchmark_only=True
        )
        self._history = BenchmarkHistoryPanel(app, self._history_host)
        self._section = 'run'


    def _show_section(self, section):
        section = 'history' if section == 'history' else 'run'
        if section == self._section:
            if section == 'history':
                try:
                    self._history.refresh()
                except Exception:
                    pass
            return
        try:
            if section == 'history':
                self._run_host.pack_forget()
                self._history_host.pack(fill='both', expand=True)
                self._run_tab.configure(fg_color='transparent', text_color=TEXT2)
                self._history_tab.configure(fg_color=PURPLE, text_color='#ffffff')
                self._benchmark.set_active(False)
                self._history.refresh()
            else:
                self._history_host.pack_forget()
                self._run_host.pack(fill='both', expand=True)
                self._history_tab.configure(fg_color='transparent', text_color=TEXT2)
                self._run_tab.configure(fg_color=PURPLE, text_color='#ffffff')
                self._benchmark.set_active(True)
        except Exception:
            pass
        self._section = section

    def widget(self):
        return self.frame

    def set_active(self, active):
        try:
            self._benchmark.set_active(bool(active) and self._section == 'run')
            if active and self._section == 'history':
                self._history.refresh()
        except Exception:
            pass

    def refresh(self):
        try:
            if self._section == 'history':
                self._history.refresh()
            else:
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
            self._history.destroy()
        except Exception:
            pass
        try:
            self.frame.destroy()
        except Exception:
            pass
