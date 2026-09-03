"""Vista avanzada de red de CorePulse.

El panel mantiene las consultas de sistema y diagnósticos fuera del hilo Tk.
Los valores dinámicos provienen de contadores reales de psutil y la vista usa
REAL_OR_NA para cualquier dato que Windows no exponga.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color

import threading
import time

import customtkinter as ctk

from core.network_details import NetworkTrafficSampler, collect_network_identity, diagnose_network
from core.internet_speed_test import InternetSpeedTest
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost

BG = theme_color('#06111f')
CARD = theme_color('#0d1828')
CARD_2 = theme_color('#0a1524')
BORDER = theme_color('#1b3048')
TEXT = theme_color('#f4f7fb')
TEXT_2 = theme_color('#b8c4d4')
MUTED = theme_color('#7f91a8')
CYAN = '#14b8ff'
GREEN = '#1fd18b'
AMBER = '#f59e0b'
RED = '#ff5d6c'
PURPLE = '#a78bfa'
FONT = 'Segoe UI'


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe(value):
    text = str(value or '').strip()
    return text if text else 'N/A'


def _join(values):
    if not isinstance(values, list):
        return 'N/A'
    clean = [str(x).strip() for x in values if str(x or '').strip()]
    return ', '.join(clean) if clean else 'N/A'


def _age(timestamp):
    try:
        seconds = max(0.0, time.time() - float(timestamp))
    except Exception:
        return 'N/A'
    if seconds < 1:
        return '< 1 s'
    if seconds < 60:
        return f'{seconds:.1f} s'
    return f'{seconds / 60.0:.1f} min'


def _format_bytes(value):
    n = _num(value)
    if n is None:
        return 'N/A'
    units = ('B', 'KB', 'MB', 'GB', 'TB')
    size = max(0.0, n)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            digits = 0 if unit == 'B' else 2
            return f'{size:.{digits}f} {unit}'
        size /= 1024.0
    return 'N/A'


def _format_rate(value):
    n = _num(value)
    if n is None:
        return 'N/A'
    if n < 1024:
        return f'{n:.0f} B/s'
    if n < 1024 ** 2:
        return f'{n / 1024:.1f} KB/s'
    if n < 1024 ** 3:
        return f'{n / 1024 ** 2:.2f} MB/s'
    return f'{n / 1024 ** 3:.2f} GB/s'


def _format_speed_mbps(value):
    n = _num(value)
    if n is None:
        return 'N/A'
    if n >= 1000:
        return f'{n / 1000.0:.2f} Gbps'
    return f'{n:.0f} Mbps'


def _diag_value(test):
    if not isinstance(test, dict):
        return 'N/A'
    if test.get('loss_percent') is not None:
        latency = test.get('latency_avg_ms')
        latency_text = f'{float(latency):.1f} ms' if _num(latency) is not None else 'N/A'
        return f"{latency_text} · pérdida {float(test['loss_percent']):.0f}%"
    if 'ok' in test:
        latency = test.get('latency_ms')
        return f"{float(latency):.1f} ms" if test.get('ok') and _num(latency) is not None else ('Correcto' if test.get('ok') else 'Falló')
    return 'N/A'


class NetworkDetailPanel:
    def __init__(self, app, host):
        self.app = app
        self.host = host
        self._alive = True
        self._after_id = None
        self._identity = None
        self._identity_loading = False
        self._identity_requested_at = 0.0
        self._identity_signature = None
        self._adapter_signature = None
        self._diag = None
        self._diag_running = False
        self._speed = None
        self._speed_progress = {'phase': 'idle', 'percent': 0, 'message': 'Prueba aún no ejecutada'}
        self._speed_running = False
        self._speed_runner = InternetSpeedTest()
        self._traffic = NetworkTrafficSampler()
        self._scroll_active_until = 0.0
        self._scroll_watch_after_id = None
        self._last_scroll_view = None
        self._connection_labels = {}
        self._traffic_labels = {}
        self._diag_labels = {}
        self._build()
        self._request_identity(force=True)
        self.refresh()

    def widget(self):
        return self.frame

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=18, pady=(15, 8))
        ctk.CTkButton(
            header, text='Volver al resumen', width=145, height=31,
            fg_color='transparent', hover_color=theme_color(theme_color('#102840')), border_width=1,
            border_color=theme_color(theme_color('#214765')), text_color=TEXT_2, font=(FONT, 9, 'bold'),
            corner_radius=8, command=lambda: show_dashboard(self.app),
        ).pack(side='left')
        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=14)
        ctk.CTkLabel(titles, text='Red y conectividad', font=(FONT, 19, 'bold'), text_color=TEXT, anchor='w').pack(anchor='w')
        ctk.CTkLabel(
            titles, text='Adaptadores, tráfico real, configuración IP y diagnóstico de conectividad',
            font=(FONT, 10), text_color=TEXT_2, anchor='w',
        ).pack(anchor='w', pady=(1, 0))
        self.lbl_freshness = ctk.CTkLabel(header, text='Actualización: N/A', font=(FONT, 9, 'bold'), text_color=MUTED)
        self.lbl_freshness.pack(side='right', padx=(8, 0))

        self.summary_row = ctk.CTkFrame(self.frame, fg_color='transparent')
        self.summary_row.pack(fill='x', padx=18, pady=(2, 9))
        self.status_card, self.status_value, self.status_detail = self._summary_card('CONEXIÓN', 'Cargando', 'Adaptador principal', GREEN)
        self.down_card, self.down_value, self.down_detail = self._summary_card('TRÁFICO ↓', 'N/A', 'Actividad actual', CYAN)
        self.up_card, self.up_value, self.up_detail = self._summary_card('TRÁFICO ↑', 'N/A', 'Actividad actual', PURPLE)
        self.link_card, self.link_value, self.link_detail = self._summary_card('ENLACE', 'N/A', 'Velocidad negociada', CYAN)
        for i, card in enumerate((self.status_card, self.down_card, self.up_card, self.link_card)):
            card.pack(side='left', fill='both', expand=True, padx=(0 if i == 0 else 5, 0 if i == 3 else 5))

        self.body_scroll = StableScrollHost(self.frame, fg_color=BG)
        self.body_scroll.pack(fill='both', expand=True, padx=13, pady=(0, 10))
        self.body = self.body_scroll.content

        # Medición activa de capacidad de Internet. Esto es distinto del tráfico
        # instantáneo mostrado en las tarjetas superiores.
        speed = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        speed.pack(fill='x', padx=5, pady=(0, 8))
        speed_header = ctk.CTkFrame(speed, fg_color='transparent')
        speed_header.pack(fill='x', padx=14, pady=(10, 5))
        speed_title_box = ctk.CTkFrame(speed_header, fg_color='transparent')
        speed_title_box.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(speed_title_box, text='PRUEBA DE VELOCIDAD DE INTERNET', font=(FONT, 10, 'bold'), text_color=TEXT_2).pack(anchor='w')
        ctk.CTkLabel(
            speed_title_box,
            text='Medición activa contra Cloudflare edge · 4 flujos paralelos · puede transferir hasta ~315 MB',
            font=(FONT, 8), text_color=MUTED,
        ).pack(anchor='w')
        self.btn_speed = ctk.CTkButton(
            speed_header, text='Iniciar prueba', width=145, height=28,
            fg_color=theme_color('#0d2942'), hover_color=theme_color('#164f7d'), border_width=1, border_color=theme_color('#1d5278'),
            text_color=theme_color('#75d2f7'), font=(FONT, 8, 'bold'), corner_radius=7, command=self._start_speed_test,
        )
        self.btn_speed.pack(side='right')

        speed_grid = ctk.CTkFrame(speed, fg_color='transparent')
        speed_grid.pack(fill='x', padx=14, pady=(2, 6))
        speed_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self._speed_labels = {}
        for col, (key, title, accent, unit) in enumerate((
            ('download', 'DESCARGA', CYAN, 'Mbps'),
            ('upload', 'SUBIDA', PURPLE, 'Mbps'),
            ('ping', 'PING', GREEN, 'ms'),
            ('jitter', 'JITTER', AMBER, 'ms'),
        )):
            card = ctk.CTkFrame(speed_grid, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=9)
            card.grid(row=0, column=col, sticky='nsew', padx=(0 if col == 0 else 4, 0 if col == 3 else 4))
            ctk.CTkLabel(card, text=title, font=(FONT, 8, 'bold'), text_color=MUTED).pack(anchor='w', padx=10, pady=(8, 0))
            value = ctk.CTkLabel(card, text='—', font=(FONT, 18, 'bold'), text_color=accent)
            value.pack(anchor='w', padx=10, pady=(1, 0))
            detail = ctk.CTkLabel(card, text=unit, font=(FONT, 8), text_color=MUTED)
            detail.pack(anchor='w', padx=10, pady=(0, 8))
            self._speed_labels[key] = (value, detail)

        self.speed_progress = ctk.CTkProgressBar(speed, height=5, progress_color=CYAN, fg_color=theme_color('#0f2135'))
        self.speed_progress.set(0)
        self.speed_progress.pack(fill='x', padx=14, pady=(0, 5))
        speed_status = ctk.CTkFrame(speed, fg_color='transparent')
        speed_status.pack(fill='x', padx=14, pady=(0, 9))
        self.lbl_speed_status = ctk.CTkLabel(speed_status, text='Prueba aún no ejecutada.', font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w')
        self.lbl_speed_status.pack(side='left', fill='x', expand=True)
        self.lbl_speed_server = ctk.CTkLabel(speed_status, text='Servidor: N/A', font=(FONT, 8), text_color=MUTED, anchor='e')
        self.lbl_speed_server.pack(side='right', padx=(8, 0))

        top = ctk.CTkFrame(self.body, fg_color='transparent')
        top.pack(fill='x', padx=5, pady=(0, 8))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=1)
        connection = self._section(top, 'CONEXIÓN ACTIVA', 'Configuración real del adaptador principal')
        connection.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        traffic = self._section(top, 'CONTADORES DE TRÁFICO', 'Acumulados del adaptador desde Windows')
        traffic.grid(row=0, column=1, sticky='nsew', padx=(5, 0))

        for key, label in (
            ('adapter', 'Adaptador'), ('description', 'Descripción'), ('ipv4', 'IPv4'), ('ipv6', 'IPv6'),
            ('mac', 'Dirección MAC'), ('gateway', 'Gateway'), ('dns', 'Servidores DNS'), ('ssid', 'Wi-Fi / SSID'),
            ('signal', 'Señal Wi-Fi'), ('source', 'Fuentes'),
        ):
            self._add_row(connection, self._connection_labels, key, label)
        for key, label in (
            ('download', 'Descarga actual'), ('upload', 'Subida actual'), ('received', 'Datos recibidos'),
            ('sent', 'Datos enviados'), ('packets_in', 'Paquetes recibidos'), ('packets_out', 'Paquetes enviados'),
            ('errors', 'Errores de interfaz'), ('drops', 'Paquetes descartados'), ('source', 'Fuente'),
        ):
            self._add_row(traffic, self._traffic_labels, key, label)

        diag = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        diag.pack(fill='x', padx=5, pady=(0, 8))
        diag_header = ctk.CTkFrame(diag, fg_color='transparent')
        diag_header.pack(fill='x', padx=14, pady=(10, 5))
        title_box = ctk.CTkFrame(diag_header, fg_color='transparent')
        title_box.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(title_box, text='DIAGNÓSTICO DE CONECTIVIDAD', font=(FONT, 10, 'bold'), text_color=TEXT_2).pack(anchor='w')
        ctk.CTkLabel(
            title_box, text='Prueba gateway local, salida a Internet y resolución DNS por separado',
            font=(FONT, 8), text_color=MUTED,
        ).pack(anchor='w')
        self.btn_diagnose = ctk.CTkButton(
            diag_header, text='Ejecutar diagnóstico', width=145, height=28,
            fg_color=theme_color('#0d2942'), hover_color=theme_color('#164f7d'), border_width=1, border_color=theme_color('#1d5278'),
            text_color=theme_color('#75d2f7'), font=(FONT, 8, 'bold'), corner_radius=7, command=self._start_diagnostic,
        )
        self.btn_diagnose.pack(side='right')
        diag_grid = ctk.CTkFrame(diag, fg_color='transparent')
        diag_grid.pack(fill='x', padx=14, pady=(2, 10))
        diag_grid.grid_columnconfigure((0, 1, 2), weight=1)
        for col, (key, title) in enumerate((('gateway', 'GATEWAY'), ('internet', 'INTERNET'), ('dns', 'DNS'))):
            card = ctk.CTkFrame(diag_grid, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=9)
            card.grid(row=0, column=col, sticky='nsew', padx=(0 if col == 0 else 4, 0 if col == 2 else 4))
            ctk.CTkLabel(card, text=title, font=(FONT, 8, 'bold'), text_color=MUTED).pack(anchor='w', padx=10, pady=(8, 0))
            value = ctk.CTkLabel(card, text='No ejecutado', font=(FONT, 11, 'bold'), text_color=TEXT_2)
            value.pack(anchor='w', padx=10, pady=(1, 0))
            detail = ctk.CTkLabel(card, text='N/A', font=(FONT, 8), text_color=MUTED, wraplength=320, justify='left')
            detail.pack(anchor='w', padx=10, pady=(0, 8))
            self._diag_labels[key] = (value, detail)
        self.lbl_diag_status = ctk.CTkLabel(diag, text='Diagnóstico aún no ejecutado.', font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w')
        self.lbl_diag_status.pack(fill='x', padx=14, pady=(0, 9))

        self.adapters_card = ctk.CTkFrame(self.body, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        self.adapters_card.pack(fill='x', padx=5, pady=(0, 8))
        ah = ctk.CTkFrame(self.adapters_card, fg_color='transparent')
        ah.pack(fill='x', padx=14, pady=(10, 5))
        ctk.CTkLabel(ah, text='ADAPTADORES DETECTADOS', font=(FONT, 10, 'bold'), text_color=TEXT_2).pack(side='left')
        self.lbl_adapter_count = ctk.CTkLabel(ah, text='Cargando inventario', font=(FONT, 8, 'bold'), text_color=MUTED)
        self.lbl_adapter_count.pack(side='right')
        self.adapter_rows = ctk.CTkFrame(self.adapters_card, fg_color='transparent')
        self.adapter_rows.pack(fill='x', padx=10, pady=(0, 10))

        note = ctk.CTkFrame(self.body, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=10)
        note.pack(fill='x', padx=5, pady=(0, 7))
        ctk.CTkLabel(note, text='LECTURA UNIVERSAL', font=(FONT, 9, 'bold'), text_color=GREEN).pack(anchor='w', padx=12, pady=(9, 2))
        ctk.CTkLabel(
            note,
            text=(
                'CorePulse no inventa SSID, señal, DNS, gateway, velocidad ni latencia. Una interfaz puede bloquear ICMP y aun así tener Internet; '
                'por eso gateway, Internet y DNS se informan como pruebas independientes.'
            ),
            font=(FONT, 8), text_color=MUTED, justify='left', anchor='w', wraplength=1150,
        ).pack(fill='x', padx=12, pady=(0, 9))

        footer = ctk.CTkFrame(self.body, fg_color='transparent')
        footer.pack(fill='x', padx=8, pady=(0, 6))
        ctk.CTkLabel(footer, text='CorePulse muestra datos reales o N/A: tráfico actual del adaptador y, sólo al ejecutarla, una prueba activa de velocidad contra Cloudflare edge.', font=(FONT, 8), text_color=MUTED).pack(side='left')
        self.lbl_source = ctk.CTkLabel(footer, text='Inventario de red: cargando…', font=(FONT, 8, 'bold'), text_color=MUTED)
        self.lbl_source.pack(side='right')

    def _summary_card(self, title, value, detail, accent):
        card = ctk.CTkFrame(self.summary_row, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12, height=92)
        card.pack_propagate(False)
        ctk.CTkLabel(card, text=title, font=(FONT, 9, 'bold'), text_color=TEXT_2).pack(anchor='w', padx=12, pady=(9, 0))
        value_label = ctk.CTkLabel(card, text=value, font=(FONT, 20, 'bold'), text_color=accent)
        value_label.pack(anchor='w', padx=12)
        detail_label = ctk.CTkLabel(card, text=detail, font=(FONT, 8), text_color=MUTED)
        detail_label.pack(anchor='w', padx=12, pady=(0, 7))
        return card, value_label, detail_label

    def _section(self, parent, title, subtitle):
        card = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        ctk.CTkLabel(card, text=title, font=(FONT, 10, 'bold'), text_color=TEXT_2).pack(anchor='w', padx=14, pady=(10, 0))
        ctk.CTkLabel(card, text=subtitle, font=(FONT, 8), text_color=MUTED).pack(anchor='w', padx=14, pady=(0, 5))
        return card

    def _add_row(self, parent, target, key, label):
        row = ctk.CTkFrame(parent, fg_color='transparent', height=33)
        row.pack(fill='x', padx=12, pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=label, width=155, font=(FONT, 8), text_color=MUTED, anchor='w').pack(side='left')
        value = ctk.CTkLabel(row, text='N/A', font=(FONT, 8, 'bold'), text_color=TEXT, anchor='w')
        value.pack(side='left', fill='x', expand=True, padx=(8, 0))
        target[key] = value

    def _scroll_canvas(self):
        return getattr(getattr(self, 'body_scroll', None), 'canvas', None)

    def _start_scroll_watch(self):
        # Compatibilidad con builds anteriores: StableScrollHost administra la
        # rueda, scrollbar e inercia sin un polling de 60 ms por página.
        return None

    def _is_scrolling(self):
        host = getattr(self, 'body_scroll', None)
        return bool(host is not None and host.is_scrolling())

    def _request_identity(self, force=False):
        if self._identity_loading:
            return
        now = time.monotonic()
        if not force and now - self._identity_requested_at < 10.0:
            return
        self._identity_requested_at = now
        self._identity_loading = True

        def worker():
            try:
                result = collect_network_identity()
            except Exception:
                result = {}
            self._identity = result if isinstance(result, dict) else {}
            self._identity_loading = False

        threading.Thread(target=worker, name='CorePulseNetworkIdentity', daemon=True).start()

    def _primary(self):
        identity = self._identity if isinstance(self._identity, dict) else {}
        adapters = identity.get('adapters') if isinstance(identity.get('adapters'), list) else []
        index = identity.get('primary_index')
        if isinstance(index, int) and 0 <= index < len(adapters):
            return adapters[index]
        return None

    def _apply_identity(self):
        identity = self._identity
        if not isinstance(identity, dict):
            return
        try:
            signature = repr((identity.get('primary_index'), identity.get('adapters')))
        except Exception:
            signature = str(id(identity))
        primary = self._primary() or {}
        self._connection_labels['adapter'].configure(text=_safe(primary.get('name')))
        self._connection_labels['description'].configure(text=_safe(primary.get('description')))
        self._connection_labels['ipv4'].configure(text=_join(primary.get('ipv4')))
        self._connection_labels['ipv6'].configure(text=_join(primary.get('ipv6')))
        self._connection_labels['mac'].configure(text=_safe(primary.get('mac')))
        self._connection_labels['gateway'].configure(text=_join(primary.get('gateways')))
        self._connection_labels['dns'].configure(text=_join(primary.get('dns_servers')))
        ssid = _safe(primary.get('ssid'))
        if ssid != 'N/A' and primary.get('wifi_radio_type'):
            ssid += f" · {primary.get('wifi_radio_type')}"
        self._connection_labels['ssid'].configure(text=ssid)
        signal = _num(primary.get('wifi_signal_percent'))
        self._connection_labels['signal'].configure(text=f'{signal:.0f}%' if signal is not None else 'N/A', text_color=GREEN if signal is not None and signal >= 65 else AMBER if signal is not None else TEXT)
        self._connection_labels['source'].configure(text=' · '.join(primary.get('sources') or []) if primary else 'N/A')
        self.lbl_source.configure(text=f"Inventario de red: {_safe(identity.get('source'))}", text_color=GREEN if primary else MUTED)
        if signature != self._adapter_signature:
            self._rebuild_adapters(identity.get('adapters') or [], identity.get('primary_index'))
            self._adapter_signature = signature
        self._identity_signature = signature

    def _rebuild_adapters(self, adapters, primary_index):
        for child in list(self.adapter_rows.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        valid = [x for x in adapters if isinstance(x, dict)]
        self.lbl_adapter_count.configure(text=f'{len(valid)} detectado' + ('' if len(valid) == 1 else 's'), text_color=GREEN if valid else MUTED)
        if not valid:
            ctk.CTkLabel(self.adapter_rows, text='No se detectaron adaptadores de red.', font=(FONT, 9), text_color=MUTED).pack(anchor='w', padx=8, pady=12)
            return
        for index, adapter in enumerate(valid):
            card = ctk.CTkFrame(self.adapter_rows, fg_color=CARD_2, border_width=1, border_color=(theme_color('#1d5278') if index == primary_index else BORDER), corner_radius=9)
            card.pack(fill='x', pady=4)
            head = ctk.CTkFrame(card, fg_color='transparent')
            head.pack(fill='x', padx=12, pady=(8, 3))
            name = _safe(adapter.get('name'))
            ctk.CTkLabel(head, text=name, font=(FONT, 10, 'bold'), text_color=TEXT).pack(side='left')
            state = 'PRINCIPAL' if index == primary_index else ('ACTIVO' if adapter.get('is_up') else 'INACTIVO')
            ctk.CTkLabel(head, text=state, font=(FONT, 8, 'bold'), text_color=GREEN if adapter.get('is_up') else MUTED).pack(side='right')
            info = ctk.CTkFrame(card, fg_color='transparent')
            info.pack(fill='x', padx=12, pady=(0, 8))
            desc = _safe(adapter.get('description'))
            link = _format_speed_mbps(adapter.get('link_speed_mbps'))
            ipv4 = _join(adapter.get('ipv4'))
            ssid = _safe(adapter.get('ssid'))
            line = f'{desc}   ·   Enlace {link}   ·   IPv4 {ipv4}'
            if ssid != 'N/A':
                line += f'   ·   Wi-Fi {ssid}'
            ctk.CTkLabel(info, text=line, font=(FONT, 8), text_color=MUTED, anchor='w', wraplength=1120, justify='left').pack(fill='x')

    def _speed_server_text(self, result):
        if not isinstance(result, dict):
            return 'Servidor: N/A'
        server = result.get('server') if isinstance(result.get('server'), dict) else {}
        parts = []
        colo = _safe(server.get('colo'))
        city = _safe(server.get('city'))
        country = _safe(server.get('country'))
        if colo != 'N/A':
            parts.append(colo)
        if city != 'N/A':
            parts.append(city)
        if country != 'N/A':
            parts.append(country)
        return 'Servidor: ' + (' · '.join(parts) if parts else 'Cloudflare edge')

    def _start_speed_test(self):
        if self._speed_running:
            return
        self._speed_running = True
        self._speed = None
        self._speed_progress = {'phase': 'preparing', 'percent': 1, 'message': 'Preparando prueba…'}
        self.btn_speed.configure(text='Midiendo…', state='disabled')
        self.lbl_speed_status.configure(text='Preparando medición activa…', text_color=AMBER)
        self.lbl_speed_server.configure(text='Servidor: seleccionando edge…')
        self.speed_progress.set(0.01)
        for value, _detail in self._speed_labels.values():
            value.configure(text='—')

        def progress(payload):
            # Sólo memoria compartida; nunca toca Tk desde el worker.
            if isinstance(payload, dict):
                self._speed_progress = dict(payload)

        primary = self._primary()
        self._speed_runner.link_speed_mbps = _num(primary.get('link_speed_mbps')) if isinstance(primary, dict) else None

        def worker():
            try:
                result = self._speed_runner.run(progress=progress)
            except Exception as exc:
                result = {
                    'ok': False, 'error': str(exc)[:180], 'timestamp': time.time(),
                    'download_mbps': None, 'upload_mbps': None, 'latency_ms': None, 'jitter_ms': None,
                }
            self._speed = result
            self._speed_running = False

        threading.Thread(target=worker, name='CorePulseInternetSpeedTest', daemon=True).start()

    def _apply_speed_test(self):
        progress = self._speed_progress if isinstance(self._speed_progress, dict) else {}
        percent = _num(progress.get('percent'))
        if percent is not None:
            self.speed_progress.set(max(0.0, min(1.0, percent / 100.0)))
        if self._speed_running:
            self.btn_speed.configure(text='Midiendo…', state='disabled')
            self.lbl_speed_status.configure(text=_safe(progress.get('message')), text_color=AMBER)
            current = _num(progress.get('current_mbps'))
            phase = progress.get('phase')
            if current is not None and phase in ('download', 'upload'):
                key = 'download' if phase == 'download' else 'upload'
                self._speed_labels[key][0].configure(text=f'{current:.1f}')
            return

        self.btn_speed.configure(text='Repetir prueba' if isinstance(self._speed, dict) else 'Iniciar prueba', state='normal')
        result = self._speed
        if not isinstance(result, dict):
            return
        values = (
            ('download', result.get('download_mbps'), 1),
            ('upload', result.get('upload_mbps'), 1),
            ('ping', result.get('latency_ms'), 1),
            ('jitter', result.get('jitter_ms'), 1),
        )
        for key, raw, decimals in values:
            value_label, _detail = self._speed_labels[key]
            number = _num(raw)
            value_label.configure(text=f'{number:.{decimals}f}' if number is not None else 'N/A')
        self.speed_progress.set(1 if result.get('ok') else 0)
        if result.get('ok'):
            used = _num(result.get('data_mb'))
            duration = _num(result.get('duration_s'))
            suffix = []
            if used is not None:
                suffix.append(f'{used:.0f} MB transferidos')
            if duration is not None:
                suffix.append(f'{duration:.1f} s')
            notes = [str(x) for x in (result.get('validation_notes') or []) if x]
            if notes:
                suffix.append(f'{len(notes)} medición descartada' + ('s' if len(notes) != 1 else ''))
            self.lbl_speed_status.configure(
                text='Prueba completada' + (f" · {' · '.join(suffix)}" if suffix else ''),
                text_color=AMBER if notes else GREEN,
            )
        else:
            notes = [str(x) for x in (result.get('validation_notes') or []) if x]
            message = 'Medición descartada por superar el enlace físico.' if notes else 'No se pudo completar la prueba de velocidad.'
            self.lbl_speed_status.configure(text=message, text_color=RED)
        self.lbl_speed_server.configure(text=self._speed_server_text(result))

    def _start_diagnostic(self):
        if self._diag_running:
            return
        self._diag_running = True
        self.btn_diagnose.configure(text='Diagnosticando…', state='disabled')
        self.lbl_diag_status.configure(text='Ejecutando pruebas reales fuera del hilo gráfico…', text_color=AMBER)
        identity_snapshot = self._identity if isinstance(self._identity, dict) else None

        def worker():
            try:
                result = diagnose_network(identity_snapshot, count=4)
            except Exception as exc:
                result = {'status': 'ERROR', 'error': str(exc), 'timestamp': time.time()}
            self._diag = result
            self._diag_running = False

        threading.Thread(target=worker, name='CorePulseNetworkDiagnostic', daemon=True).start()

    def _apply_diag(self):
        if self._diag_running:
            return
        self.btn_diagnose.configure(text='Ejecutar diagnóstico', state='normal')
        diag = self._diag
        if not isinstance(diag, dict):
            return
        status = diag.get('status')
        status_map = {
            'CONECTIVIDAD_OK': ('Conectividad correcta', GREEN),
            'SIN_INTERNET': ('Sin salida a Internet', RED),
            'DNS_CON_PROBLEMAS': ('Problema de resolución DNS', AMBER),
            'GATEWAY_NO_RESPONDE_ICMP': ('Gateway no responde ICMP', AMBER),
            'SIN_ADAPTADOR_ACTIVO': ('Sin adaptador activo', RED),
            'ERROR': ('Error de diagnóstico', RED),
        }
        status_text, status_color = status_map.get(status, (_safe(status), TEXT_2))
        self.lbl_diag_status.configure(text=status_text, text_color=status_color)
        gateway = diag.get('gateway') if isinstance(diag.get('gateway'), dict) else {}
        internet = diag.get('internet') if isinstance(diag.get('internet'), dict) else {}
        dns = diag.get('dns') if isinstance(diag.get('dns'), dict) else {}
        for key, test, ok in (
            ('gateway', gateway, bool(gateway.get('reachable'))),
            ('internet', internet, bool(internet.get('reachable'))),
            ('dns', dns, bool(dns.get('ok'))),
        ):
            value, detail = self._diag_labels[key]
            value.configure(text='Correcto' if ok else ('No disponible' if key == 'gateway' and not gateway.get('target') else 'Atención'), text_color=GREEN if ok else AMBER)
            detail_text = _diag_value(test)
            if key == 'gateway' and gateway.get('target'):
                detail_text += f" · {gateway.get('target')}"
            elif key == 'internet':
                detail_text += ' · 1.1.1.1'
            elif key == 'dns':
                detail_text += f" · {_safe(dns.get('host'))}"
            detail.configure(text=detail_text)

    def refresh(self):
        if not self._alive:
            return
        if self._after_id is not None:
            try:
                self.frame.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        try:
            self._request_identity()
            primary = self._primary()
            primary_name = primary.get('name') if isinstance(primary, dict) else None
            runtime = self._traffic.sample(primary_name)
            identity_stamp = (self._identity or {}).get('timestamp') if isinstance(self._identity, dict) else None
            self.lbl_freshness.configure(text=f'Actualización: {_age(runtime.get("timestamp"))}')

            connected = bool(primary and primary.get('is_up'))
            self.status_value.configure(text='Conectado' if connected else ('Sin conexión' if self._identity is not None else 'Cargando'), text_color=GREEN if connected else RED if self._identity is not None else MUTED)
            self.status_detail.configure(text=_safe(primary_name) if primary_name else 'Adaptador principal')
            self.down_value.configure(text=_format_rate(runtime.get('download_bps')), text_color=CYAN if _num(runtime.get('download_bps')) is not None else MUTED)
            self.up_value.configure(text=_format_rate(runtime.get('upload_bps')), text_color=PURPLE if _num(runtime.get('upload_bps')) is not None else MUTED)
            self.link_value.configure(text=_format_speed_mbps(primary.get('link_speed_mbps')) if primary else 'N/A', text_color=CYAN if primary and _num(primary.get('link_speed_mbps')) is not None else MUTED)
            self.link_detail.configure(text='Velocidad negociada del adaptador')

            if not self._is_scrolling():
                # La prueba de velocidad vive dentro del canvas desplazable. Sus
                # labels/progress no se repintan durante rueda/touchpad/scrollbar.
                self._apply_speed_test()
                self._apply_identity()
                self._traffic_labels['download'].configure(text=_format_rate(runtime.get('download_bps')))
                self._traffic_labels['upload'].configure(text=_format_rate(runtime.get('upload_bps')))
                self._traffic_labels['received'].configure(text=_format_bytes(runtime.get('bytes_recv_total')))
                self._traffic_labels['sent'].configure(text=_format_bytes(runtime.get('bytes_sent_total')))
                self._traffic_labels['packets_in'].configure(text=_safe(runtime.get('packets_recv_total')))
                self._traffic_labels['packets_out'].configure(text=_safe(runtime.get('packets_sent_total')))
                errors = None
                if _num(runtime.get('errors_in_total')) is not None or _num(runtime.get('errors_out_total')) is not None:
                    errors = f"Entrada {_safe(runtime.get('errors_in_total'))} · Salida {_safe(runtime.get('errors_out_total'))}"
                drops = None
                if _num(runtime.get('drops_in_total')) is not None or _num(runtime.get('drops_out_total')) is not None:
                    drops = f"Entrada {_safe(runtime.get('drops_in_total'))} · Salida {_safe(runtime.get('drops_out_total'))}"
                self._traffic_labels['errors'].configure(text=errors or 'N/A')
                self._traffic_labels['drops'].configure(text=drops or 'N/A')
                self._traffic_labels['source'].configure(text=_safe(runtime.get('source')))
                self._apply_diag()
                if identity_stamp is not None:
                    self.lbl_source.configure(text=f"Inventario de red: {_safe((self._identity or {}).get('source'))} · {_age(identity_stamp)}")
        except Exception:
            pass
        if self._alive:
            try:
                self._after_id = self.frame.after(950, self.refresh)
            except Exception:
                self._after_id = None
