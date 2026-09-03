"""Presenta el historial de alertas de la sesión actual."""
from __future__ import annotations
from core.theme_manager import color as theme_color
# Código refactorizado: nombres estables y documentación en español.
import hashlib
import json
from datetime import datetime
import customtkinter as ctk
from gui.stable_scroll import StableScrollHost
BG = theme_color('#0d1828')
INNER = theme_color('#0a1422')
CARD = theme_color('#101d2e')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
DIM = theme_color('#aebdd0')
MUTED = theme_color('#72849b')
LEVEL_COLORS = {'CRITICAL': '#ef5b67', 'WARNING': '#f0a23a', 'INFO': '#38bdf8', 'NORMAL': '#22c993'}

def _text(v, default='—'):
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default

def _time(v):
    if v in (None, ''):
        return '—'
    try:
        return datetime.fromtimestamp(float(v)).strftime('%d/%m · %H:%M:%S')
    except Exception:
        return _text(v)

class AlertHistoryPanel:
    MAX_ROWS = 10

    def __init__(self, parent):
        self._root = ctk.CTkFrame(parent, fg_color=BG, border_width=1, border_color=BORDER, corner_radius=14)
        header = ctk.CTkFrame(self._root, fg_color='transparent')
        header.pack(fill='x', padx=16, pady=(14, 8))
        left = ctk.CTkFrame(header, fg_color='transparent')
        left.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(left, text='Historial de alertas', font=('Segoe UI', 20, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(left, text='Máximo 10 alertas de esta ejecución. Al reiniciar CorePulse, el historial comienza vacío.', font=('Segoe UI', 9), text_color=DIM, anchor='w').pack(anchor='w', pady=(2, 0))
        self.lbl_summary = ctk.CTkLabel(header, text='Sin eventos', font=('Segoe UI', 9, 'bold'), text_color=DIM, fg_color=theme_color(theme_color('#102235')), corner_radius=8, padx=10, pady=5)
        self.lbl_summary.pack(side='right', padx=(12, 0))
        self.summary_band = ctk.CTkFrame(self._root, fg_color='transparent')
        self.summary_band.pack(fill='x', padx=14, pady=(0, 9))
        self._summary_widgets = {}
        for name, label, color in (('active', 'ACTIVAS', '#38bdf8'), ('warning', 'ADVERTENCIAS', LEVEL_COLORS['WARNING']), ('critical', 'CRÍTICAS', LEVEL_COLORS['CRITICAL']), ('resolved', 'RESUELTAS', LEVEL_COLORS['NORMAL'])):
            card = ctk.CTkFrame(self.summary_band, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=10)
            card.pack(side='left', fill='x', expand=True, padx=4)
            ctk.CTkLabel(card, text=label, font=('Segoe UI', 8, 'bold'), text_color=MUTED).pack(anchor='w', padx=10, pady=(7, 1))
            value = ctk.CTkLabel(card, text='0', font=('Segoe UI', 17, 'bold'), text_color=color)
            value.pack(anchor='w', padx=10, pady=(0, 7))
            self._summary_widgets[name] = value
        self.scroll_host = StableScrollHost(self._root, fg_color=INNER, border_width=1, border_color=theme_color('#16263a'), corner_radius=10, height=350)
        self.scroll_host.pack(fill='both', expand=True, padx=14, pady=(0, 14))
        self.scroll = self.scroll_host.content
        self._row_widgets = {}
        self._fingerprint = None

    def widget(self):
        return self._root

    def is_visible(self):
        try:
            return bool(self._root.winfo_exists() and self._root.winfo_viewable())
        except Exception:
            return False

    def _scroll_pos(self):
        try:
            view = self.scroll_host.yview()
            return float(view[0]) if view else 0.0
        except Exception:
            return 0.0

    def _restore(self, pos):
        try:
            self.scroll_host.yview_moveto(max(0.0, min(1.0, float(pos))))
        except Exception:
            pass

    def _key(self, row, i):
        if isinstance(row, dict):
            key = _text(row.get('key') or row.get('event_id') or row.get('id'), '')
            first = _text(row.get('first_seen'), '')
            if key:
                return f'{key}:{first}'
            return '|'.join([_text(row.get('component'), ''), _text(row.get('title'), ''), first]) or f'row:{i}'
        return f'row:{i}'

    def _norm(self, row):
        if not isinstance(row, dict):
            return {'component': 'SYSTEM', 'level': 'INFO', 'status': 'HISTÓRICO', 'title': _text(row), 'detail': '', 'time': '—'}
        level = _text(row.get('level') or row.get('severity'), 'INFO').upper()
        status = _text(row.get('status'), '')
        if not status:
            active = row.get('active')
            status = 'ACTIVA' if active is True else 'RESUELTA' if active is False else 'HISTÓRICO'
        detail = row.get('detail') or row.get('explanation') or ''
        evidence = row.get('evidence')
        if isinstance(evidence, list) and evidence:
            compact = ' • '.join((_text(x, '') for x in evidence[:3] if _text(x, '')))
            if compact:
                detail = f'{detail}  {compact}'.strip()
        occurrences = int(row.get('occurrences') or 1)
        meta = f"Primera: {_time(row.get('first_seen'))} • Última: {_time(row.get('last_seen') or row.get('resolved_at'))} • Repeticiones: {occurrences}"
        detail = f'{detail}  {meta}'.strip()
        timestamp = row.get('last_seen') or row.get('resolved_at') or row.get('first_seen') or row.get('persisted_at')
        return {'component': _text(row.get('component'), 'SYSTEM'), 'level': level, 'status': status.upper(), 'title': _text(row.get('title') or row.get('key'), 'Alerta'), 'detail': _text(detail, ''), 'time': _time(timestamp)}

    def _create(self, key, data):
        frame = ctk.CTkFrame(self.scroll, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=9)
        frame.pack(fill='x', pady=4, padx=2)
        accent = ctk.CTkFrame(frame, width=5, corner_radius=3, fg_color=MUTED)
        accent.pack(side='left', fill='y', padx=(0, 0), pady=7)
        accent.pack_propagate(False)
        content = ctk.CTkFrame(frame, fg_color='transparent')
        content.pack(side='left', fill='both', expand=True, padx=10, pady=7)
        top = ctk.CTkFrame(content, fg_color='transparent')
        top.pack(fill='x')
        component = ctk.CTkLabel(top, text='', font=('Segoe UI', 8, 'bold'), text_color=DIM)
        component.pack(side='left')
        level = ctk.CTkLabel(top, text='', font=('Segoe UI', 8, 'bold'))
        level.pack(side='left', padx=(8, 0))
        tm = ctk.CTkLabel(top, text='', font=('Segoe UI', 8), text_color=MUTED)
        tm.pack(side='right')
        title = ctk.CTkLabel(content, text='', font=('Segoe UI', 11, 'bold'), text_color=TEXT, anchor='w', justify='left')
        title.pack(fill='x', pady=(3, 1))
        detail = ctk.CTkLabel(content, text='', font=('Segoe UI', 9), text_color=DIM, anchor='w', justify='left', wraplength=800)
        detail.pack(fill='x', pady=(0, 2))
        widgets = {'frame': frame, 'accent': accent, 'component': component, 'level': level, 'time': tm, 'title': title, 'detail': detail, 'snapshot': None}
        self._row_widgets[key] = widgets
        self._update(widgets, data)

    def _update(self, widgets, data):
        snap = tuple((data.get(k) for k in ('component', 'level', 'status', 'title', 'detail', 'time')))
        if snap == widgets.get('snapshot'):
            return
        color = LEVEL_COLORS.get(data['level'], DIM)
        widgets['accent'].configure(fg_color=color)
        widgets['component'].configure(text=data['component'])
        widgets['level'].configure(text=f"{data['level']} · {data['status']}", text_color=color)
        widgets['time'].configure(text=data['time'])
        widgets['title'].configure(text=data['title'])
        widgets['detail'].configure(text=data['detail'] or 'Sin evidencia adicional.')
        widgets['snapshot'] = snap

    def render(self, rows, summary=None):
        if getattr(self, 'scroll_host', None) is not None and self.scroll_host.is_scrolling():
            rows_copy = list(rows) if isinstance(rows, list) else []
            summary_copy = dict(summary) if isinstance(summary, dict) else summary
            self.scroll_host.defer_until_idle(lambda: self.render(rows_copy, summary_copy))
            return False
        rows = (rows if isinstance(rows, list) else [])[:self.MAX_ROWS]
        fp = hashlib.sha1(json.dumps({'rows': rows, 'summary': summary}, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
        if fp == self._fingerprint:
            return False
        pos = self._scroll_pos()
        desired = []
        normalized = []
        for i, row in enumerate(rows):
            key = self._key(row, i)
            desired.append(key)
            normalized.append((key, self._norm(row)))
        for key in list(self._row_widgets):
            if key not in desired:
                try:
                    self._row_widgets[key]['frame'].destroy()
                except Exception:
                    pass
                self._row_widgets.pop(key, None)
        for key, data in normalized:
            if key in self._row_widgets:
                self._update(self._row_widgets[key], data)
            else:
                self._create(key, data)
        for key in desired:
            try:
                self._row_widgets[key]['frame'].pack_forget()
                self._row_widgets[key]['frame'].pack(fill='x', pady=4, padx=2)
            except Exception:
                pass
        if isinstance(summary, dict):
            active = int(summary.get('active', summary.get('active_count', 0)) or 0)
            warning = int(summary.get('warning', 0) or 0)
            critical = int(summary.get('critical', 0) or 0)
            resolved = int(summary.get('resolved', summary.get('history_count', 0)) or 0)
        else:
            active = warning = critical = 0
            resolved = max(0, len(rows))
        self.lbl_summary.configure(text=f'{len(rows)} eventos registrados')
        for key, value in (('active', active), ('warning', warning), ('critical', critical), ('resolved', resolved)):
            self._summary_widgets[key].configure(text=str(value))
        self._fingerprint = fp
        self._root.after_idle(lambda: self._restore(pos))
        return True
