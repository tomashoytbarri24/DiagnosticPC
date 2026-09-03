"""Muestra alertas técnicas y evidencia de diagnóstico en una ventana secundaria."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
try:
    import customtkinter as ctk
except Exception:
    ctk = None
try:
    from gui.stable_scroll import StableScrollHost
except Exception:
    StableScrollHost = None
BG = theme_color('#0d1828')
BG_SOFT = theme_color('#101d2e')
BG_INNER = theme_color('#0a1422')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT_DIM = theme_color('#aebdd0')
TEXT_MUTED = theme_color('#72849b')
COLORS = {'CRITICAL': '#ef4444', 'WARNING': '#f59e0b', 'INFO': '#38bdf8', 'OBSERVING': '#60a5fa', 'NORMAL': '#10b981', 'UNKNOWN': theme_color('#94a3b8')}
ICONS = {'CRITICAL': '!', 'WARNING': '!', 'INFO': 'i', 'OBSERVING': '…', 'NORMAL': '✓', 'UNKNOWN': '?'}
class SmartAlertPanel:

    def __init__(self, parent):
        self.frame = None
        self.header_status = None
        self.hero = None
        self.hero_level = None
        self.hero_title = None
        self.hero_detail = None
        self.hero_evidence = None
        self.scroll = None
        if ctk is None:
            return
        self.frame = ctk.CTkFrame(parent, fg_color=BG, border_color=BORDER, border_width=1, corner_radius=14)
        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=16, pady=(14, 10))
        left = ctk.CTkFrame(header, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(left, text='Alertas y estado del agente', font=('Segoe UI', 20, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(left, text='Condiciones instantáneas y sostenidas explicadas con evidencia real del agente.', font=('Segoe UI', 9), text_color=TEXT_DIM, anchor='w').pack(anchor='w', pady=(2, 0))
        self.header_status = ctk.CTkLabel(header, text='NORMAL', font=('Segoe UI', 9, 'bold'), text_color=COLORS['NORMAL'], fg_color=theme_color(theme_color('#102235')), corner_radius=8, padx=10, pady=5)
        self.header_status.pack(side='right', padx=(12, 0))
        self.hero = ctk.CTkFrame(self.frame, fg_color=BG_SOFT, border_color=COLORS['NORMAL'], border_width=1, corner_radius=12)
        self.hero.pack(fill='x', padx=14, pady=(0, 12))
        self.hero_level = ctk.CTkLabel(self.hero, text='✓  SISTEMA SIN ALERTAS', font=('Segoe UI', 11, 'bold'), text_color=COLORS['NORMAL'])
        self.hero_level.pack(anchor='w', padx=14, pady=(12, 3))
        self.hero_title = ctk.CTkLabel(self.hero, text='No hay condiciones sostenidas de advertencia o críticas.', font=('Segoe UI', 15, 'bold'), text_color=TEXT, anchor='w', justify='left')
        self.hero_title.pack(fill='x', padx=14, pady=(0, 4))
        self.hero_detail = ctk.CTkLabel(self.hero, text='CorePulse seguirá observando el sistema en tiempo real.', font=('Segoe UI', 10), text_color=TEXT_DIM, anchor='w', justify='left', wraplength=820)
        self.hero_detail.pack(fill='x', padx=14, pady=(0, 5))
        self.hero_evidence = ctk.CTkLabel(self.hero, text='', font=('Segoe UI', 10, 'bold'), text_color=TEXT_DIM, anchor='w', justify='left', wraplength=820)
        self.hero_evidence.pack(fill='x', padx=14, pady=(0, 12))
        self.scroll_host = StableScrollHost(self.frame, fg_color=BG_INNER, height=360) if StableScrollHost is not None else None
        if self.scroll_host is not None:
            self.scroll_host.pack(fill='both', expand=True, padx=14, pady=(0, 14))
            self.scroll = self.scroll_host.content
        else:
            self.scroll = ctk.CTkFrame(self.frame, fg_color=BG_INNER, corner_radius=10)
            self.scroll.pack(fill='both', expand=True, padx=14, pady=(0, 14))

    def widget(self):
        return self.frame

    def _clear(self):
        if self.scroll is None:
            return
        for child in self.scroll.winfo_children():
            child.destroy()

    @staticmethod
    def _compact_evidence(item):
        evidence = item.get('evidence') or []
        useful = []
        for line in evidence:
            text = str(line)
            if text.startswith('Regla:'):
                continue
            useful.append(text)
        return '   •   '.join(useful[:3])

    def render(self, state, diagnostic):
        if self.frame is None:
            return
        host = getattr(self, 'scroll_host', None)
        if host is not None and host.is_scrolling():
            state_copy = dict(state or {})
            diagnostic_copy = dict(diagnostic or {})
            host.defer_until_idle(lambda: self.render(state_copy, diagnostic_copy))
            return
        self._clear()
        overall = state.get('overall', 'UNKNOWN')
        context = state.get('context', 'UNKNOWN')
        items = diagnostic.get('explanations') or []
        color = COLORS.get(overall, TEXT_DIM)
        self.header_status.configure(text=overall, text_color=color)
        if not items:
            instant = diagnostic.get('instant') or state.get('instant') or {}
            instant_level = str(instant.get('severity') or 'UNKNOWN').upper()
            instant_reasons = [str(x) for x in (instant.get('reasons') or []) if x]
            if instant_level in {'ELEVATED', 'WARNING', 'CRITICAL', 'ERROR'}:
                shown_level = 'CRITICAL' if instant_level in {'CRITICAL', 'ERROR'} else 'WARNING'
                instant_color = COLORS[shown_level]
                self.header_status.configure(text='OBSERVANDO', text_color=instant_color)
                self.hero.configure(border_color=instant_color)
                self.hero_level.configure(text=f'◷  {instant_level} INSTANTÁNEA', text_color=instant_color)
                self.hero_title.configure(text=instant.get('status') or 'Condición instantánea en observación')
                self.hero_detail.configure(text='CorePulse reaccionó a la lectura actual y está confirmando si persiste antes de crear una alerta sostenida.')
                self.hero_evidence.configure(text='   •   '.join(instant_reasons[:3]) or f'Contexto: {context}', text_color=instant_color)
                ctk.CTkLabel(self.scroll, text='Todavía no existe una alerta sostenida. El agente continúa acumulando evidencia en tiempo real.', font=('Segoe UI', 12), text_color=TEXT_DIM, wraplength=760, justify='left').pack(pady=26, padx=18)
            elif overall == 'OBSERVING':
                self.hero.configure(border_color=COLORS['OBSERVING'])
                self.hero_level.configure(text='…  OBSERVANDO SESIÓN', text_color=COLORS['OBSERVING'])
                self.hero_title.configure(text='CorePulse está acumulando evidencia.')
                self.hero_detail.configure(text='El agente todavía no tiene suficiente evidencia para declarar la sesión normal o anómala.')
                self.hero_evidence.configure(text=f'Contexto: {context}')
                ctk.CTkLabel(self.scroll, text='No hay diagnósticos activos que explicar.', font=('Segoe UI', 12), text_color=TEXT_DIM).pack(pady=26)
            else:
                self.hero.configure(border_color=COLORS['NORMAL'])
                self.hero_level.configure(text='✓  SIN ALERTAS ACTIVAS', text_color=COLORS['NORMAL'])
                self.hero_title.configure(text='No hay condiciones sostenidas de advertencia o críticas.')
                self.hero_detail.configure(text='CorePulse seguirá observando el sistema en tiempo real.')
                self.hero_evidence.configure(text=f'Contexto: {context}')
                ctk.CTkLabel(self.scroll, text='No hay diagnósticos activos que explicar.', font=('Segoe UI', 12), text_color=TEXT_DIM).pack(pady=26)
            return
        primary = items[0]
        p_level = primary.get('level', overall)
        p_color = COLORS.get(p_level, color)
        p_icon = ICONS.get(p_level, '!')
        self.hero.configure(border_color=p_color)
        self.hero_level.configure(text=f"{p_icon}  {p_level} • {primary.get('component', 'SYSTEM')}", text_color=p_color)
        self.hero_title.configure(text=primary.get('title') or 'Alerta activa')
        self.hero_detail.configure(text=primary.get('why') or primary.get('summary') or '')
        self.hero_evidence.configure(text=self._compact_evidence(primary), text_color=p_color)
        self._detail_section(primary, primary=True)
        for item in items[1:]:
            self._detail_section(item, primary=False)

    def _section_title(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=('Segoe UI', 10, 'bold'), text_color=TEXT).pack(anchor='w', padx=14, pady=(8, 2))

    def _detail_section(self, item, primary=False):
        level = item.get('level', 'INFO')
        color = COLORS.get(level, TEXT_DIM)
        card = ctk.CTkFrame(self.scroll, fg_color=BG, border_color=BORDER if primary else color, border_width=1, corner_radius=10)
        card.pack(fill='x', padx=4, pady=6)
        if primary:
            ctk.CTkLabel(card, text='DETALLE DE LA ALERTA PRINCIPAL', font=('Segoe UI', 10, 'bold'), text_color=TEXT_DIM).pack(anchor='w', padx=14, pady=(12, 2))
        else:
            ctk.CTkLabel(card, text=f"{level} • {item.get('component', 'SYSTEM')}", font=('Segoe UI', 11, 'bold'), text_color=color).pack(anchor='w', padx=14, pady=(12, 2))
            ctk.CTkLabel(card, text=item.get('title') or '', font=('Segoe UI', 13, 'bold'), text_color=TEXT, anchor='w', justify='left').pack(fill='x', padx=14, pady=(0, 4))
        evidence = item.get('evidence') or []
        if evidence:
            self._section_title(card, 'EVIDENCIA')
            ctk.CTkLabel(card, text='\n'.join((f'• {line}' for line in evidence[:7])), font=('Segoe UI', 10), text_color=TEXT_DIM, anchor='w', justify='left', wraplength=760).pack(fill='x', padx=14, pady=(0, 6))
        checks = item.get('checks') or []
        if checks:
            self._section_title(card, 'QUÉ REVISAR')
            ctk.CTkLabel(card, text='\n'.join((f'• {line}' for line in checks[:6])), font=('Segoe UI', 10), text_color=TEXT_DIM, anchor='w', justify='left', wraplength=760).pack(fill='x', padx=14, pady=(0, 6))
        notes = item.get('notes') or []
        if notes:
            ctk.CTkLabel(card, text=' '.join(notes[:4]), font=('Segoe UI', 9), text_color=TEXT_MUTED, anchor='w', justify='left', wraplength=760).pack(fill='x', padx=14, pady=(2, 12))
        else:
            ctk.CTkLabel(card, text='', height=4).pack()
