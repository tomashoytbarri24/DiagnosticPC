"""Presenta comparaciones y tendencias de las sesiones de diagnóstico."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import datetime as dt
import json
import tkinter as tk
try:
    import customtkinter as ctk
except Exception:
    ctk = None
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PIL import Image, ImageTk
from matplotlib.figure import Figure
from gui.stable_scroll import StableScrollHost
BG = theme_color('#0d1828')
INNER = theme_color('#0a1422')
CARD = theme_color('#101d2e')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
DIM = theme_color('#aebdd0')
MUTED = theme_color('#72849b')
GREEN = '#10b981'
CYAN = '#38bdf8'
PURPLE = '#a855f7'
ORANGE = '#f59e0b'
RED = '#ef4444'
BLUE = '#60a5fa'
class SessionTrendsPanel:

    def __init__(self, parent):
        self.frame = None
        self.summary_frame = None
        self.chart_frame = None
        self.table = None
        self.canvas = None
        self._chart_photo = None
        self._last_render_signature = None
        if ctk is None:
            return
        self.frame = ctk.CTkFrame(parent, fg_color=BG, border_color=BORDER, border_width=1, corner_radius=14)
        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=16, pady=(14, 8))
        left = ctk.CTkFrame(header, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(left, text='Tendencias entre sesiones', font=('Segoe UI', 20, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(left, text='Últimos 10 diagnósticos de esta ejecución. GAME y DESKTOP se comparan siempre por separado.', font=('Segoe UI', 9), text_color=DIM, anchor='w').pack(anchor='w', pady=(2, 0))
        self.header_status = ctk.CTkLabel(header, text='Sin sesiones', font=('Segoe UI', 9, 'bold'), text_color=DIM, fg_color=theme_color(theme_color('#102235')), corner_radius=8, padx=10, pady=5)
        self.header_status.pack(side='right', padx=(12, 0))
        self.summary_frame = ctk.CTkFrame(self.frame, fg_color='transparent')
        self.summary_frame.pack(fill='x', padx=14, pady=(0, 10))
        self.chart_frame = ctk.CTkFrame(self.frame, fg_color=INNER, border_color=BORDER, border_width=1, corner_radius=10)
        self.chart_frame.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        # Tendencias no usa TkAgg: el gráfico se rasteriza fuera de pantalla y
        # sólo se publica cuando el frame ya está completo. Evita el flash del
        # canvas nativo de Matplotlib al mapear/desmapear páginas internas.
        self.chart_image = tk.Label(
            self.chart_frame,
            bg=INNER,
            fg=TEXT,
            bd=0,
            highlightthickness=0,
            relief='flat',
            anchor='center',
        )
        self.chart_image.pack(fill='both', expand=True, padx=8, pady=8)
        self.table_host = StableScrollHost(self.frame, fg_color=INNER, corner_radius=10, height=205)
        self.table_host.pack(fill='x', padx=14, pady=(0, 14))
        self.table = self.table_host.content

    def widget(self):
        return self.frame

    @staticmethod
    def _clear(widget):
        for child in widget.winfo_children():
            child.destroy()

    def _card(self, title, value, subtitle, color):
        card = ctk.CTkFrame(self.summary_frame, fg_color=CARD, border_color=BORDER, border_width=1, corner_radius=10)
        card.pack(side='left', fill='x', expand=True, padx=4)
        ctk.CTkLabel(card, text=title, font=('Segoe UI', 9, 'bold'), text_color=DIM).pack(anchor='w', padx=10, pady=(8, 2))
        ctk.CTkLabel(card, text=value, font=('Segoe UI', 16, 'bold'), text_color=color).pack(anchor='w', padx=10, pady=(0, 1))
        ctk.CTkLabel(card, text=subtitle, font=('Segoe UI', 8), text_color=DIM).pack(anchor='w', padx=10, pady=(0, 8))

    @staticmethod
    def _comparison_text(info, profile):
        status = info.get('status', 'INSUFFICIENT')
        delta = info.get('delta')
        profile_label = {'GAME': 'juego', 'DESKTOP': 'escritorio'}.get(profile, 'sesión')
        if status == 'NOT_COMPARABLE':
            return f'Sin sesión {profile_label} comparable'
        if delta is None:
            return 'Sin comparación'
        sign = '+' if delta > 0 else ''
        if status == 'IMPROVING':
            return f'{sign}{delta:.1f} °C vs {profile_label} anterior ↓'
        if status == 'WORSENING':
            return f'{sign}{delta:.1f} °C vs {profile_label} anterior ↑'
        return f'{sign}{delta:.1f} °C vs {profile_label} anterior'

    def render(self, sessions, summary):
        if self.frame is None:
            return
        # Evita destruir/recrear tarjetas, filas y gráfico cuando el colector
        # entrega exactamente el mismo estado. Esto elimina repintados visibles
        # al reabrir la pestaña o recibir refrescos redundantes.
        try:
            signature = json.dumps(
                {'sessions': sessions, 'summary': summary},
                sort_keys=True,
                ensure_ascii=False,
                default=str,
                separators=(',', ':'),
            )
        except Exception:
            signature = repr((sessions, summary))
        if signature == self._last_render_signature:
            return
        if getattr(self, 'table_host', None) is not None and self.table_host.is_scrolling():
            sessions_copy = list(sessions) if isinstance(sessions, list) else []
            summary_copy = dict(summary) if isinstance(summary, dict) else {}
            self.table_host.defer_until_idle(lambda: self.render(sessions_copy, summary_copy))
            return
        self.header_status.configure(text=f"{summary.get('session_count', 0)} sesiones • {summary.get('validated_sessions', 0)} válidas • {summary.get('legacy_sessions', 0)} legacy")
        self._clear(self.summary_frame)
        profile = summary.get('summary_profile') or summary.get('comparison_profile')
        cpu_value = summary.get('summary_cpu_value')
        gpu_value = summary.get('summary_gpu_value')
        if profile == 'GAME':
            cpu_title = 'CPU MÁX. JUGANDO'
            gpu_title = 'GPU MÁX. JUGANDO'
        elif profile == 'DESKTOP':
            cpu_title = 'CPU MÁX. ESCRITORIO'
            gpu_title = 'GPU MÁX. ESCRITORIO'
        else:
            cpu_title = 'CPU MÁX. CONTEXTO'
            gpu_title = 'GPU MÁX. CONTEXTO'
        self._card(cpu_title, f'{cpu_value:.1f} °C' if isinstance(cpu_value, (int, float)) else 'N/A', self._comparison_text(summary.get('cpu_comparison') or {}, profile), CYAN)
        self._card(gpu_title, f'{gpu_value:.1f} °C' if isinstance(gpu_value, (int, float)) else 'N/A', self._comparison_text(summary.get('gpu_comparison') or {}, profile), PURPLE)
        self._card('SESIONES CON JUEGO', str(summary.get('game_sessions', 0)), 'sesiones GAME validadas', GREEN)
        self._card('SESIONES CON ALERTAS', f"Advertencia {summary.get('warning_sessions', 0)} • Crítica {summary.get('critical_sessions', 0)}", f"Eventos: {summary.get('warning_events', 0)} advertencias • {summary.get('critical_events', 0)} críticas", ORANGE if summary.get('warning_sessions', 0) else RED if summary.get('critical_sessions', 0) else GREEN)
        self._render_chart(sessions[:10], summary)
        self._render_rows(sessions[:20])
        self._last_render_signature = signature

    def _render_chart(self, sessions, summary):
        if not sessions:
            self._chart_photo = None
            self.chart_image.configure(image='', text='Aún no hay sesiones guardadas.', font=('Segoe UI', 12))
            return
        self.chart_image.configure(text='')
        ordered = list(reversed(sessions))
        x = list(range(1, len(ordered) + 1))
        # Se calcula un tamaño cercano al viewport final. El host puede estar
        # fuera de pantalla durante la construcción, pero Tk ya conoce el ancho
        # de la ventana principal después de update_idletasks().
        try:
            self.frame.update_idletasks()
            width_px = int(self.chart_frame.winfo_width()) - 18
        except Exception:
            width_px = 0
        if width_px < 680:
            try:
                width_px = max(760, int(self.frame.winfo_toplevel().winfo_width()) - 390)
            except Exception:
                width_px = 900
        width_px = max(680, min(width_px, 1500))
        height_px = 278
        dpi = 100
        fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi, facecolor=INNER)
        ax = fig.add_subplot(111, facecolor=INNER)
        for profile, label_suffix in (('DESKTOP', 'DESKTOP'), ('GAME', 'GAME')):
            px = []
            cpu_y = []
            gpu_y = []
            for idx, session in enumerate(ordered, start=1):
                if session.get('profile') != profile:
                    continue
                maxima = session.get('game_maxima') or {} if profile == 'GAME' else session.get('maxima') or {}
                cpu = maxima.get('cpu_temp')
                gpu = maxima.get('gpu_temp')
                if isinstance(cpu, (int, float)):
                    px.append(idx)
                    cpu_y.append(float(cpu))
            if cpu_y:
                ax.plot(px, cpu_y, marker='o', linewidth=2, label=f'CPU {label_suffix}', color=CYAN if profile == 'DESKTOP' else BLUE)
            gx = []
            gy = []
            for idx, session in enumerate(ordered, start=1):
                if session.get('profile') != profile:
                    continue
                source = session.get('game_maxima') or {} if profile == 'GAME' else session.get('maxima') or {}
                gpu = source.get('gpu_temp')
                if isinstance(gpu, (int, float)):
                    gx.append(idx)
                    gy.append(float(gpu))
            if gy:
                ax.plot(gx, gy, marker='o', linewidth=2, label=f'GPU {label_suffix}', color=PURPLE if profile == 'DESKTOP' else GREEN)
        legacy_x = []
        legacy_cpu = []
        legacy_gpu = []
        for idx, session in enumerate(ordered, start=1):
            if session.get('profile') != 'LEGACY':
                continue
            maxima = session.get('maxima') or {}
            cpu = maxima.get('cpu_temp')
            gpu = maxima.get('gpu_temp')
            if isinstance(cpu, (int, float)):
                legacy_x.append(idx)
                legacy_cpu.append(float(cpu))
            if isinstance(gpu, (int, float)):
                legacy_gpu.append((idx, float(gpu)))
        if legacy_cpu:
            ax.scatter(legacy_x, legacy_cpu, marker='x', s=45, color=MUTED, label='CPU LEGACY')
        if legacy_gpu:
            ax.scatter([item[0] for item in legacy_gpu], [item[1] for item in legacy_gpu], marker='x', s=45, color=theme_color('#475569'), label='GPU LEGACY')
        ax.set_title('Tendencias confiables — JUEGO usa solo GAME_ACTIVE', color=TEXT, fontsize=10, fontweight='bold')
        ax.set_xticks(x)
        labels = []
        for number, session in zip(x, ordered):
            profile = session.get('profile', 'LEGACY')
            if profile == 'GAME':
                suffix = 'GAME'
            elif profile == 'DESKTOP':
                suffix = 'DESKTOP'
            else:
                suffix = 'LEGACY'
            labels.append(f'S{number}\n{suffix}')
        ax.set_xticklabels(labels, color=DIM, fontsize=7)
        ax.tick_params(axis='y', colors=DIM, labelsize=8)
        ax.grid(True, color=theme_color('#334155'), linestyle='--', linewidth=0.5, alpha=0.65)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        if len(x) == 1:
            ax.set_xlim(0.5, 1.5)
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            legend = ax.legend(fontsize=7, facecolor=CARD, edgecolor=BORDER, loc='best')
            for text in legend.get_texts():
                text.set_color(TEXT)
        fig.tight_layout()
        # Render off-screen (Agg). No Tk canvas, no draw visible y no ventana
        # hija de Matplotlib que pueda parpadear durante una transición.
        agg = FigureCanvasAgg(fig)
        agg.draw()
        size = agg.get_width_height()
        image = Image.frombuffer('RGBA', size, agg.buffer_rgba(), 'raw', 'RGBA', 0, 1).copy()
        photo = ImageTk.PhotoImage(image=image, master=self.chart_image)
        self._chart_photo = photo
        self.chart_image.configure(image=photo, text='')
        self.canvas = None
        fig.clear()

    @staticmethod
    def _duration(seconds):
        if not isinstance(seconds, (int, float)):
            return '--'
        seconds = int(seconds)
        if seconds < 60:
            return f'{seconds}s'
        minutes, seconds = divmod(seconds, 60)
        if minutes < 60:
            return f'{minutes}m {seconds}s'
        hours, minutes = divmod(minutes, 60)
        return f'{hours}h {minutes}m'

    @staticmethod
    def _basename(path):
        if not path:
            return None
        return str(path).replace('\\', '/').split('/')[-1]

    def _render_rows(self, sessions):
        self._clear(self.table)
        for index, session in enumerate(sessions, start=1):
            profile = session.get('profile', 'LEGACY')
            is_legacy = profile == 'LEGACY'
            profile_color = GREEN if profile == 'GAME' else BLUE if profile == 'DESKTOP' else MUTED
            profile_label = 'JUEGO' if profile == 'GAME' else 'ESCRITORIO' if profile == 'DESKTOP' else 'LEGACY'
            row = ctk.CTkFrame(self.table, fg_color=BG, border_color=MUTED if is_legacy else BORDER, border_width=1, corner_radius=9)
            row.pack(fill='x', padx=4, pady=4)
            maxima = session.get('maxima') or {}
            averages = session.get('averages') or {}
            game_max = session.get('game_maxima') or {}
            alerts = session.get('alerts') or {}
            timestamp = session.get('ended_at')
            try:
                when = dt.datetime.fromtimestamp(timestamp).strftime('%d/%m %H:%M') if isinstance(timestamp, (int, float)) else '--'
            except Exception:
                when = '--'
            game = self._basename(session.get('principal_game')) or self._basename(session.get('game')) or 'No detectado'
            ctk.CTkLabel(row, text=f"#{index}  {when} • {session.get('overall', 'UNKNOWN')} • {profile_label}", font=('Segoe UI', 10, 'bold'), text_color=profile_color).pack(anchor='w', padx=11, pady=(8, 2))
            if is_legacy:
                ctk.CTkLabel(row, text='Sesión histórica anterior a Session Accuracy. No participa en comparaciones ni conteo de alertas.', font=('Segoe UI', 9, 'bold'), text_color=MUTED).pack(anchor='w', padx=11, pady=(0, 4))
            ctk.CTkLabel(row, text=f"Duración {self._duration(session.get('duration_seconds'))} • Juego {game} • Tiempo en juego {self._duration(session.get('total_game_seconds', 0))}", font=('Segoe UI', 9), text_color=DIM).pack(anchor='w', padx=11, pady=(0, 2))
            if session.get('alerts_trusted', False):
                alerts_text = f"Eventos: {alerts.get('warning', 0)} advertencias • {alerts.get('critical', 0)} críticas"
            else:
                alerts_text = 'Alertas históricas no usadas'
            ctk.CTkLabel(row, text=f"CPU máx {maxima.get('cpu_temp', 'N/A')} °C (media {averages.get('cpu_temp', 'N/A')}) • GPU máx {maxima.get('gpu_temp', 'N/A')} °C (media {averages.get('gpu_temp', 'N/A')}) • {alerts_text}", font=('Segoe UI', 9), text_color=DIM).pack(anchor='w', padx=11, pady=(0, 2))
            if not is_legacy and any((isinstance(game_max.get(key), (int, float)) for key in ('cpu_temp', 'gpu_temp'))):
                ctk.CTkLabel(row, text=f"Solo durante juego activo → CPU máx {game_max.get('cpu_temp', 'N/A')} °C • GPU máx {game_max.get('gpu_temp', 'N/A')} °C", font=('Segoe UI', 9, 'bold'), text_color=GREEN).pack(anchor='w', padx=11, pady=(0, 8))
