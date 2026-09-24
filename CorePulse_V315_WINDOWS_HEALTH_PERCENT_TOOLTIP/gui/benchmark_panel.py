"""Página principal independiente del Benchmark visual de CorePulse.

V196 consolida respuesta percibida, jerarquía tipográfica, historial progresivo e identidad CorePulse: publica un shell ligero,
construye la vista pesada después de que Windows haya podido pintarlo y mantiene
el historial lazy hasta que el usuario realmente lo abre.
"""
from __future__ import annotations

import threading
import customtkinter as ctk

from core.theme_manager import color as theme_color
from gui.internal_navigation import show_dashboard
from gui.professional_visuals import build_title_block

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD2 = theme_color('#0a1726')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT2 = theme_color('#b8c4d4')
MUTED = theme_color('#8295ad')
ACCENT = '#2aa9e9'
ACCENT_HOVER = '#1788c4'
ACCENT_DARK = theme_color('#0e2a40')
ACCENT_BORDER = theme_color('#2f7ba5')
ACCENT_TEXT = theme_color('#7dd8ff')
FONT = 'Segoe UI'

# Escala visual del Benchmark. V190 evita mezclar tamaños arbitrarios y mantiene
# una jerarquía simple: título > sección > cuerpo > metadato.
BENCH_TITLE = 24
BENCH_SECTION = 11
BENCH_BODY = 10
BENCH_META = 9
BENCH_CONTROL_H = 36
BENCH_RADIUS = 12


class BenchmarkPanel:
    """Host dedicado y progresivo: publica primero, construye después."""

    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self._active = True
        self._section = 'run'
        self._benchmark = None
        self._history = None
        self._run_build_after = None
        self._history_build_after = None

        self.frame = ctk.CTkFrame(host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=24, pady=(14, 8))

        shell = ctk.CTkFrame(header, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        shell.pack(fill='x')
        accent = ctk.CTkFrame(shell, width=4, fg_color=ACCENT, corner_radius=14)
        accent.pack(side='left', fill='y', padx=(1, 0), pady=1)

        body = ctk.CTkFrame(shell, fg_color='transparent')
        body.pack(side='left', fill='both', expand=True, padx=14, pady=13)

        left = ctk.CTkFrame(body, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True)

        back_box = ctk.CTkFrame(left, fg_color='transparent', width=38, height=38)
        back_box.pack(anchor='w')
        back_box.pack_propagate(False)
        ctk.CTkButton(
            back_box, text='↶', command=lambda: show_dashboard(self.app),
            width=38, height=38, corner_radius=11, fg_color=CARD2,
            hover_color=theme_color('#102840'), border_width=1, border_color=BORDER,
            text_color=TEXT, font=(FONT, 17, 'bold'),
        ).pack(fill='both', expand=True)

        titles = ctk.CTkFrame(left, fg_color='transparent')
        titles.pack(fill='x', expand=True, pady=(10, 0))
        hero = build_title_block(
            titles,
            eyebrow='Rendimiento de hardware',
            title='Benchmark',
            subtitle='Mide GPU, CPU, RAM y SSD con resultados reales y una lectura clara al finalizar.',
            accent=ACCENT,
            badges=(('MEDICIÓN REAL', ACCENT), ('REAL_OR_NA', '#10b981')),
            title_size=BENCH_TITLE,
        )
        hero['frame'].pack(anchor='w', fill='x')

        state = ctk.CTkFrame(body, fg_color=CARD2, border_width=1, border_color=BORDER, corner_radius=12, width=118, height=118)
        state.pack(side='right', padx=(12, 0))
        state.pack_propagate(False)
        ctk.CTkLabel(state, text='ESTADO', font=(FONT, 8, 'bold'), text_color=ACCENT, anchor='w').pack(anchor='w', padx=11, pady=(11, 3))
        ctk.CTkLabel(state, text='Benchmark', font=(FONT, 14, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w', padx=11)
        ctk.CTkLabel(state, text='● Listo', font=(FONT, 8, 'bold'), text_color='#10b981', anchor='w').pack(anchor='w', padx=11, pady=(7, 0))
        ctk.CTkLabel(state, text='Prueba actual e historial con lectura real.', font=(FONT, 7), text_color=MUTED, anchor='w', justify='left', wraplength=92).pack(anchor='w', padx=11, pady=(4, 0))

        tabs_wrap = ctk.CTkFrame(self.frame, fg_color='transparent')
        tabs_wrap.pack(fill='x', padx=24, pady=(0, 10))
        tabs = ctk.CTkFrame(tabs_wrap, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=13)
        tabs.pack(side='left')
        self._run_tab = ctk.CTkButton(
            tabs, text='Prueba actual', command=lambda: self._show_section('run'),
            width=112, height=BENCH_CONTROL_H, corner_radius=BENCH_RADIUS, fg_color=ACCENT_DARK,
            hover_color=ACCENT_HOVER, border_width=1,
            border_color=ACCENT_BORDER, text_color='#ffffff', font=(FONT, BENCH_BODY, 'bold'),
        )
        self._run_tab.pack(side='left', padx=(4, 6), pady=4)
        self._history_tab = ctk.CTkButton(
            tabs, text='Historial', command=lambda: self._show_section('history'),
            width=98, height=BENCH_CONTROL_H, corner_radius=BENCH_RADIUS, fg_color='transparent',
            hover_color=theme_color('#102840'), border_width=1, border_color=BORDER,
            text_color=TEXT2, font=(FONT, BENCH_BODY, 'bold'),
        )
        self._history_tab.pack(side='left', padx=(0, 4), pady=4)

        self._content = ctk.CTkFrame(self.frame, fg_color=BG, corner_radius=0)
        self._content.pack(fill='both', expand=True, padx=20, pady=(0, 12))
        self._run_host = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        self._history_host = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        self._run_host.pack(fill='both', expand=True)

        # Shell visible en el primer frame: la navegación ya respondió aunque el
        # árbol CTk del benchmark todavía se esté construyendo.
        self._run_loading = self._build_loading_state(
            self._run_host,
            'Preparando benchmark',
            'Inicializando la vista local · todavía no se ejecuta ninguna carga.',
        )
        self._schedule_run_build()

    def prepare_for_commit(self):
        """Resuelve el shell ligero antes de que la navegación lo haga visible."""
        try:
            self.host.update_idletasks()
            self.frame.update_idletasks()
        except Exception:
            pass
        return True

    def _build_loading_state(self, parent, title, detail):
        shell = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14, height=152)
        shell.pack(fill='x', padx=8, pady=(8, 0))
        shell.pack_propagate(False)

        top = ctk.CTkFrame(shell, fg_color='transparent')
        top.pack(fill='x', padx=16, pady=(14, 8))
        icon = ctk.CTkFrame(top, width=42, height=42, fg_color=CARD2, border_width=1, border_color=ACCENT_BORDER, corner_radius=12)
        icon.pack(side='left')
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text='◔', font=(FONT, 18, 'bold'), text_color=ACCENT).pack(expand=True, fill='both')

        labels = ctk.CTkFrame(top, fg_color='transparent')
        labels.pack(side='left', fill='x', expand=True, padx=(12, 0))
        ctk.CTkLabel(labels, text=title, font=(FONT, 15, 'bold'), text_color=TEXT, anchor='w').pack(fill='x')
        ctk.CTkLabel(labels, text=detail, font=(FONT, BENCH_BODY), text_color=MUTED, anchor='w', justify='left', wraplength=900).pack(fill='x', pady=(3, 0))

        bar = ctk.CTkProgressBar(
            shell, height=8, corner_radius=999, progress_color=ACCENT,
            fg_color=CARD2, mode='indeterminate'
        )
        bar.pack(fill='x', padx=16, pady=(2, 10))
        try:
            bar.start()
        except Exception:
            bar.set(0.5)
        ctk.CTkLabel(shell, text='Preparación segura · la carga real comienza sólo cuando la vista ya está lista.', font=(FONT, BENCH_META), text_color=TEXT2, anchor='w').pack(fill='x', padx=16, pady=(0, 12))
        return shell

    def _schedule_run_build(self):
        if not self._alive or self._benchmark is not None or self._run_build_after is not None:
            return
        def build():
            self._run_build_after = None
            if not self._alive:
                return
            # Si el usuario salió antes del primer frame, no gastamos tiempo en
            # construir una página que ni siquiera está visible.
            if not self._active or self._section != 'run':
                return
            self._ensure_run_panel()
        try:
            self._run_build_after = self.app.after(80, build)
        except Exception:
            build()

    def _ensure_run_panel(self):
        if not self._alive or self._benchmark is not None:
            return self._benchmark
        from gui.health_center_panel import HealthCenterPanel

        # V279: el árbol pesado se construye en un host fuera del viewport. El
        # loading permanece intacto hasta que el nuevo árbol ya resolvió su layout.
        staging = ctk.CTkFrame(self._run_host, fg_color=BG, corner_radius=0)
        try:
            staging.place(x=-20000, y=0, relwidth=1.0, relheight=1.0)
        except Exception:
            pass
        try:
            panel = HealthCenterPanel(
                self.app, staging, performance_only=True, benchmark_only=True
            )
            staging.update_idletasks()
        except Exception:
            try:
                staging.destroy()
            except Exception:
                pass
            raise

        self._benchmark = panel
        try:
            staging.place_configure(x=0, y=0, relx=0, rely=0, relwidth=1.0, relheight=1.0)
            staging.lift()
            staging.update_idletasks()
        except Exception:
            pass
        try:
            if self._run_loading is not None and self._run_loading.winfo_exists():
                self._run_loading.destroy()
        except Exception:
            pass
        self._run_loading = None
        self._run_staging = staging
        return self._benchmark

    def _schedule_history_build(self):
        if not self._alive or self._history is not None or self._history_build_after is not None:
            return
        if not self._history_host.winfo_children():
            self._history_loading = self._build_loading_state(
                self._history_host,
                'Preparando historial',
                'Cargando primero las 3 sesiones más recientes · el resto queda en segundo plano.',
            )

        # V195: la lectura del historial puede tocar decenas de sesiones JSON. Se
        # realiza fuera del hilo Tk; la construcción visual vuelve al hilo UI con
        # sólo los datos ya cargados.
        token = object()
        self._history_build_after = token

        def read_worker():
            sessions = []
            total = 0
            try:
                store = getattr(self.app, 'health_history_store', None)
                if store is not None and hasattr(store, 'benchmark_session_count'):
                    total = int(store.benchmark_session_count())
                if store is not None and hasattr(store, 'latest_benchmark_sessions'):
                    # V196: primera pintura rápida. El resto se precarga después
                    # sin bloquear la publicación de las 5 tarjetas visibles.
                    sessions = list(store.latest_benchmark_sessions(limit=5))
                if not total:
                    total = len(sessions)
            except Exception:
                sessions, total = [], 0

            def publish():
                if self._history_build_after is not token:
                    return
                self._history_build_after = None
                if not self._alive:
                    return
                from gui.benchmark_history_panel import BenchmarkHistoryPanel
                staging = ctk.CTkFrame(self._history_host, fg_color=BG, corner_radius=0)
                panel = BenchmarkHistoryPanel(
                    self.app, staging,
                    preloaded_sessions=sessions, total_count=total,
                )
                try:
                    staging.update_idletasks()
                except Exception:
                    pass
                staging.pack(fill='both', expand=True)
                try:
                    if getattr(self, '_history_loading', None) is not None and self._history_loading.winfo_exists():
                        self._history_loading.destroy()
                except Exception:
                    pass
                self._history_loading = None
                self._history = panel

                if total > len(sessions) and store is not None and hasattr(store, 'latest_benchmark_sessions'):
                    def prefetch_all():
                        try:
                            full = list(store.latest_benchmark_sessions(limit=min(max(total, 20), 250)))
                        except Exception:
                            return
                        def install_cache():
                            if not self._alive or self._history is not panel:
                                return
                            try:
                                panel.set_sessions_cache(full, total_count=total)
                            except Exception:
                                pass
                        try:
                            self.app.after(0, install_cache)
                        except Exception:
                            pass
                    threading.Thread(target=prefetch_all, name='CorePulseBenchmarkHistoryPrefetch', daemon=True).start()

            try:
                self.app.after(0, publish)
            except Exception:
                pass

        threading.Thread(target=read_worker, name='CorePulseBenchmarkHistory', daemon=True).start()

    def _show_section(self, section):
        section = 'history' if section == 'history' else 'run'
        if section == self._section:
            if section == 'history':
                if self._history is not None:
                    try: self._history.refresh()
                    except Exception: pass
                else:
                    self._schedule_history_build()
            elif self._benchmark is None:
                self._schedule_run_build()
            return
        try:
            if section == 'history':
                self._run_host.pack_forget()
                self._history_host.pack(fill='both', expand=True)
                self._run_tab.configure(fg_color='transparent', border_color=BORDER, text_color=TEXT2)
                self._history_tab.configure(fg_color=ACCENT_DARK, border_color=ACCENT_BORDER, text_color=ACCENT_TEXT)
                if self._benchmark is not None:
                    self._benchmark.set_active(False)
                self._schedule_history_build()
            else:
                self._history_host.pack_forget()
                self._run_host.pack(fill='both', expand=True)
                self._history_tab.configure(fg_color='transparent', border_color=BORDER, text_color=TEXT2)
                self._run_tab.configure(fg_color=ACCENT_DARK, border_color=ACCENT_BORDER, text_color=ACCENT_TEXT)
                if self._benchmark is not None:
                    self._benchmark.set_active(True)
                else:
                    self._schedule_run_build()
        except Exception:
            pass
        self._section = section

    def widget(self):
        return self.frame

    def set_active(self, active):
        self._active = bool(active)
        try:
            if self._benchmark is not None:
                self._benchmark.set_active(self._active and self._section == 'run')
            elif self._active and self._section == 'run':
                self._schedule_run_build()
            if self._active and self._section == 'history':
                if self._history is not None:
                    self._history.refresh()
                else:
                    self._schedule_history_build()
        except Exception:
            pass

    def refresh(self):
        try:
            if self._section == 'history':
                if self._history is not None:
                    self._history.refresh()
                else:
                    self._schedule_history_build()
            else:
                if self._benchmark is not None:
                    self._benchmark.refresh()
                else:
                    self._schedule_run_build()
        except Exception:
            pass

    def destroy(self):
        self._alive = False
        for attr in ('_run_build_after', '_history_build_after'):
            after_id = getattr(self, attr, None)
            if after_id:
                try: self.app.after_cancel(after_id)
                except Exception: pass
                setattr(self, attr, None)
        try:
            if self._benchmark is not None:
                self._benchmark.destroy()
        except Exception:
            pass
        try:
            if self._history is not None:
                self._history.destroy()
        except Exception:
            pass
        try:
            self.frame.destroy()
        except Exception:
            pass
