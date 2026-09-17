"""Vista avanzada de red de CorePulse.

El panel mantiene las consultas de sistema y diagnósticos fuera del hilo Tk.
Los valores dinámicos provienen de contadores reales de psutil y la vista usa
REAL_OR_NA para cualquier dato que Windows no exponga.
"""
from __future__ import annotations
from core.theme_manager import color as theme_color

import ipaddress
import os
from pathlib import Path
from core.runtime_paths import resource_path
import threading
import time
import webbrowser

import customtkinter as ctk

from core.network_details import NetworkTrafficSampler, collect_network_identity, diagnose_network
from core.internet_speed_test import InternetSpeedTest
from gui.internal_navigation import show_dashboard
from gui.stable_scroll import StableScrollHost
from gui.widget_updates import configure_changed, set_changed
from gui.professional_visuals import build_title_block

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


def _corepulse_option_menu(master, *, values, width, height, command=None):
    """OptionMenu con paleta CorePulse también dentro del desplegable.

    CTkOptionMenu deja el popup con colores del tema por defecto si no se
    especifican; en Windows eso puede verse como un menú gris ajeno a la app.
    Centralizar el estilo mantiene modo claro/oscuro y evita variantes visuales.
    """
    return ctk.CTkOptionMenu(
        master, values=list(values), width=width, height=height,
        fg_color=theme_color('#0d2942'),
        button_color=theme_color('#164f7d'),
        button_hover_color=theme_color('#1b5c8f'),
        text_color=TEXT,
        dropdown_fg_color=CARD_2,
        dropdown_hover_color=theme_color('#164f7d'),
        dropdown_text_color=TEXT,
        font=(FONT, 8), dropdown_font=(FONT, 9),
        corner_radius=7, dynamic_resizing=False, anchor='w',
        command=command,
    )


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


def _first_ip(values, family):
    if not isinstance(values, list):
        return None
    want = 4 if str(family).lower() == 'ipv4' else 6
    fallback = None
    for raw in values:
        text = str(raw or '').strip()
        if not text:
            continue
        clean = text.split('%', 1)[0]
        try:
            ip = ipaddress.ip_address(clean)
        except Exception:
            continue
        if ip.version != want or ip.is_loopback or ip.is_unspecified:
            continue
        if fallback is None:
            fallback = text
        if not ip.is_link_local:
            return text
    return fallback


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
        self._visible = True
        self._runtime_started = False
        self._connectivity_runtime_started = False
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
        self._speed_runner = InternetSpeedTest(provider='ookla')
        self._speed_provider_choice = 'Speedtest.net (Ookla)'
        self._speed_ip_choice = 'Automática (recomendado)'
        self._speed_servers = []
        self._speed_server_map = {}
        self._speed_servers_loading = False
        self._speed_servers_signature = None
        self._ookla_status = None
        self._ookla_status_loading = False
        self._speed_result_url = None
        self._traffic = NetworkTrafficSampler()
        self._connection_labels = {}
        self._traffic_labels = {}
        self._diag_labels = {}
        self._network_view = 'network'
        self._network_view_frames = {}
        self._network_view_buttons = {}
        self._build()
        # Publica primero el shell de Red avanzada. Las consultas de identidad,
        # Ookla y contadores arrancan en el siguiente ciclo del event loop, para
        # que navegar a esta pestaña nunca espere a I/O o detección de red.
        try:
            self.frame.after_idle(self._start_runtime)
        except Exception:
            self._start_runtime()

    def widget(self):
        return self.frame

    def _start_runtime(self):
        if not self._alive or not self._visible:
            return
        if not self._runtime_started:
            self._runtime_started = True
            self._request_identity(force=True)
        self.refresh()

    def set_active(self, active):
        self._visible = bool(active)
        if not self._visible:
            self._traffic.reset()
            if self._after_id is not None:
                try:
                    self.frame.after_cancel(self._after_id)
                except Exception:
                    pass
                self._after_id = None
            return
        try:
            self.frame.after_idle(self._start_runtime)
        except Exception:
            self._start_runtime()

    def _build(self):
        self.frame = ctk.CTkFrame(self.host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill='both', expand=True)

        header = ctk.CTkFrame(self.frame, fg_color='transparent')
        header.pack(fill='x', padx=18, pady=(15, 8))
        ctk.CTkButton(
            header, text='Volver al monitoreo', width=145, height=31,
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1,
            border_color=theme_color('#214765'), text_color=TEXT_2, font=(FONT, 9, 'bold'),
            corner_radius=8, command=lambda: show_dashboard(self.app),
        ).pack(side='left')
        titles = ctk.CTkFrame(header, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True, padx=14)
        hero = build_title_block(
            titles,
            eyebrow='Conectividad avanzada',
            title='Red y conectividad',
            subtitle='Adaptadores, tráfico real, configuración IP y diagnóstico de conectividad',
            accent=CYAN,
            badges=(('Adaptadores', CYAN), ('Tráfico real', PURPLE), ('Diagnóstico', GREEN)),
            title_size=19,
        )
        hero['frame'].pack(anchor='w', fill='x')
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

        switch = ctk.CTkFrame(self.body, fg_color='transparent')
        switch.pack(fill='x', padx=5, pady=(0, 8))
        switch_left = ctk.CTkFrame(switch, fg_color='transparent')
        switch_left.pack(side='left')
        for key, label in (('network', 'Red'), ('connectivity', 'Conectividad')):
            btn = ctk.CTkButton(
                switch_left, text=label, width=160, height=31,
                fg_color='transparent', hover_color=theme_color('#102840'), border_width=1,
                border_color=BORDER, text_color=TEXT_2, font=(FONT, 9, 'bold'),
                corner_radius=8, command=lambda k=key: self._select_network_view(k),
            )
            btn.pack(side='left', padx=(0, 6))
            self._network_view_buttons[key] = btn
        ctk.CTkLabel(
            switch,
            text='Red concentra adaptadores, IP y tráfico real. Conectividad reúne speed test y diagnóstico activo.',
            font=(FONT, 8), text_color=MUTED, anchor='e',
        ).pack(side='right', padx=(8, 0))

        self.network_view_host = ctk.CTkFrame(self.body, fg_color='transparent')
        self.network_view_host.pack(fill='x', padx=0, pady=0)
        network_frame = ctk.CTkFrame(self.network_view_host, fg_color='transparent')
        connectivity_frame = ctk.CTkFrame(self.network_view_host, fg_color='transparent')
        self._network_view_frames['network'] = network_frame
        self._network_view_frames['connectivity'] = connectivity_frame

        # Vista RED: identidad del adaptador, configuración IP y tráfico real.
        top = ctk.CTkFrame(network_frame, fg_color='transparent')
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

        self.adapters_card = ctk.CTkFrame(network_frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        self.adapters_card.pack(fill='x', padx=5, pady=(0, 8))
        ah = ctk.CTkFrame(self.adapters_card, fg_color='transparent')
        ah.pack(fill='x', padx=14, pady=(10, 5))
        ctk.CTkLabel(ah, text='ADAPTADORES DETECTADOS', font=(FONT, 10, 'bold'), text_color=TEXT_2).pack(side='left')
        self.lbl_adapter_count = ctk.CTkLabel(ah, text='Cargando inventario', font=(FONT, 8, 'bold'), text_color=MUTED)
        self.lbl_adapter_count.pack(side='right')
        self.adapter_rows = ctk.CTkFrame(self.adapters_card, fg_color='transparent')
        self.adapter_rows.pack(fill='x', padx=10, pady=(0, 10))

        footer = ctk.CTkFrame(network_frame, fg_color='transparent')
        footer.pack(fill='x', padx=8, pady=(0, 6))
        ctk.CTkLabel(
            footer,
            text='CorePulse muestra datos reales o N/A: inventario de red, IP, tráfico del adaptador y velocidad negociada sin estimaciones.',
            font=(FONT, 8), text_color=MUTED,
        ).pack(side='left')
        self.lbl_source = ctk.CTkLabel(footer, text='Inventario de red: cargando…', font=(FONT, 8, 'bold'), text_color=MUTED)
        self.lbl_source.pack(side='right')

        # Vista CONECTIVIDAD: pruebas activas y comparables.
        speed = ctk.CTkFrame(connectivity_frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        speed.pack(fill='x', padx=5, pady=(0, 8))
        speed_header = ctk.CTkFrame(speed, fg_color='transparent')
        speed_header.pack(fill='x', padx=14, pady=(10, 5))
        speed_title_box = ctk.CTkFrame(speed_header, fg_color='transparent')
        speed_title_box.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(speed_title_box, text='SPEED TEST · PRUEBA DE VELOCIDAD DE INTERNET', font=(FONT, 11, 'bold'), text_color=TEXT_2).pack(anchor='w')
        ctk.CTkLabel(
            speed_title_box,
            text='Modo principal: Speedtest by Ookla · fija el mismo servidor para comparar dos pruebas de forma directa',
            font=(FONT, 8), text_color=MUTED,
        ).pack(anchor='w')
        self.btn_speed = ctk.CTkButton(
            speed_header, text='Iniciar prueba', width=145, height=28,
            fg_color=theme_color('#0d2942'), hover_color=theme_color('#164f7d'), border_width=1, border_color=theme_color('#1d5278'),
            text_color=theme_color('#75d2f7'), font=(FONT, 8, 'bold'), corner_radius=7, command=self._start_speed_test,
        )
        self.btn_speed.pack(side='right')

        speed_controls = ctk.CTkFrame(speed, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=9)
        speed_controls.pack(fill='x', padx=14, pady=(2, 7))
        engine_box = ctk.CTkFrame(speed_controls, fg_color='transparent')
        engine_box.pack(side='left', padx=(10, 6), pady=8)
        ctk.CTkLabel(engine_box, text='MOTOR', font=(FONT, 7, 'bold'), text_color=MUTED).pack(anchor='w')
        self.speed_provider_menu = _corepulse_option_menu(
            engine_box,
            values=['Speedtest.net (Ookla)', 'Cloudflare (alternativo)'],
            width=190, height=29, command=self._on_speed_provider_change,
        )
        self.speed_provider_menu.set('Speedtest.net (Ookla)')
        self.speed_provider_menu.pack(anchor='w', pady=(2, 0))

        server_box = ctk.CTkFrame(speed_controls, fg_color='transparent')
        server_box.pack(side='left', fill='x', expand=True, padx=6, pady=8)
        ctk.CTkLabel(server_box, text='SERVIDOR', font=(FONT, 7, 'bold'), text_color=MUTED).pack(anchor='w')
        self.speed_server_menu = _corepulse_option_menu(
            server_box, values=['Automático (Ookla elige)'], width=410, height=29,
            command=self._on_speed_server_change,
        )
        self.speed_server_menu.set('Automático (Ookla elige)')
        self.speed_server_menu.pack(anchor='w', fill='x', pady=(2, 0))

        self.btn_speed_servers = ctk.CTkButton(
            speed_controls, text='Actualizar servidores', width=145, height=27,
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1, border_color=BORDER,
            text_color=TEXT_2, font=(FONT, 8, 'bold'), command=self._request_speed_servers,
        )
        self.btn_speed_servers.pack(side='left', padx=6, pady=(20, 8))
        self.btn_speed_setup = ctk.CTkButton(
            speed_controls, text='Configurar Ookla', width=125, height=27,
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1, border_color=BORDER,
            text_color=TEXT_2, font=(FONT, 8, 'bold'), command=self._configure_ookla,
        )
        self.btn_speed_setup.pack(side='right', padx=(6, 10), pady=(20, 8))

        route_controls = ctk.CTkFrame(speed, fg_color='transparent')
        route_controls.pack(fill='x', padx=14, pady=(0, 5))
        ctk.CTkLabel(route_controls, text='RUTA IP', font=(FONT, 7, 'bold'), text_color=MUTED).pack(side='left', padx=(0, 8))
        self.speed_ip_menu = _corepulse_option_menu(
            route_controls,
            values=['Automática (recomendado)', 'IPv4 (comparar con navegador)', 'IPv6 (avanzado)'],
            width=230, height=27, command=self._on_speed_ip_change,
        )
        self.speed_ip_menu.set('Automática (recomendado)')
        self.speed_ip_menu.pack(side='left')
        self.lbl_speed_route_hint = ctk.CTkLabel(
            route_controls,
            text='Automática es el modo universal. Fija IPv4/IPv6 sólo para una comparación controlada con otra prueba.',
            font=(FONT, 8), text_color=MUTED, anchor='w',
        )
        self.lbl_speed_route_hint.pack(side='left', fill='x', expand=True, padx=(10, 0))

        self.lbl_speed_engine = ctk.CTkLabel(
            speed, text='Motor: verificando Speedtest by Ookla…', font=(FONT, 8, 'bold'), text_color=AMBER, anchor='w'
        )
        self.lbl_speed_engine.pack(fill='x', padx=14, pady=(0, 5))

        speed_grid = ctk.CTkFrame(speed, fg_color='transparent')
        speed_grid.pack(fill='x', padx=14, pady=(2, 6))
        speed_grid.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._speed_labels = {}
        for col, (key, title, accent, unit) in enumerate((
            ('download', 'DESCARGA', CYAN, 'Mbps'),
            ('upload', 'SUBIDA', PURPLE, 'Mbps'),
            ('ping', 'PING', GREEN, 'ms · en reposo'),
            ('jitter', 'JITTER', AMBER, 'ms'),
            ('loss', 'PÉRDIDA', RED, '%'),
        )):
            card = ctk.CTkFrame(speed_grid, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=9)
            card.grid(row=0, column=col, sticky='nsew', padx=(0 if col == 0 else 4, 0 if col == 4 else 4))
            ctk.CTkLabel(card, text=title, font=(FONT, 8, 'bold'), text_color=MUTED).pack(anchor='w', padx=10, pady=(8, 0))
            value = ctk.CTkLabel(card, text='—', font=(FONT, 18, 'bold'), text_color=accent)
            value.pack(anchor='w', padx=10, pady=(1, 0))
            detail = ctk.CTkLabel(card, text=unit, font=(FONT, 8), text_color=MUTED)
            detail.pack(anchor='w', padx=10, pady=(0, 8))
            self._speed_labels[key] = (value, detail)

        self.lbl_speed_loaded_latency = ctk.CTkLabel(
            speed,
            text='LATENCIA · Reposo N/A · Durante descarga N/A · Durante subida N/A',
            font=(FONT, 8, 'bold'), text_color=TEXT_2, anchor='w',
        )
        self.lbl_speed_loaded_latency.pack(fill='x', padx=14, pady=(0, 6))

        speed_meta = ctk.CTkFrame(speed, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=9)
        speed_meta.pack(fill='x', padx=14, pady=(1, 7))
        self.lbl_speed_server = ctk.CTkLabel(speed_meta, text='Servidor: N/A', font=(FONT, 8, 'bold'), text_color=TEXT_2, anchor='w')
        self.lbl_speed_server.pack(fill='x', padx=10, pady=(7, 1))
        self.lbl_speed_isp = ctk.CTkLabel(speed_meta, text='ISP: N/A', font=(FONT, 8), text_color=MUTED, anchor='w')
        self.lbl_speed_isp.pack(fill='x', padx=10, pady=1)
        compare_row = ctk.CTkFrame(speed_meta, fg_color='transparent')
        compare_row.pack(fill='x', padx=10, pady=(1, 7))
        self.lbl_speed_compare = ctk.CTkLabel(
            compare_row, text='Comparabilidad: pendiente', font=(FONT, 8), text_color=MUTED, anchor='w'
        )
        self.lbl_speed_compare.pack(side='left', fill='x', expand=True)
        self.btn_speed_result = ctk.CTkButton(
            compare_row, text='Ver resultado', width=105, height=24, state='disabled',
            fg_color='transparent', hover_color=theme_color('#102840'), border_width=1, border_color=BORDER,
            text_color=TEXT_2, font=(FONT, 8, 'bold'), command=self._open_speed_result,
        )
        self.btn_speed_result.pack(side='right', padx=(8, 0))

        self.speed_progress = ctk.CTkProgressBar(speed, height=5, progress_color=CYAN, fg_color=theme_color('#0f2135'))
        self.speed_progress.set(0)
        self.speed_progress.pack(fill='x', padx=14, pady=(0, 5))
        speed_status = ctk.CTkFrame(speed, fg_color='transparent')
        speed_status.pack(fill='x', padx=14, pady=(0, 9))
        self.lbl_speed_status = ctk.CTkLabel(speed_status, text='Prueba aún no ejecutada.', font=(FONT, 8, 'bold'), text_color=MUTED, anchor='w')
        self.lbl_speed_status.pack(side='left', fill='x', expand=True)
        self.lbl_speed_hint = ctk.CTkLabel(speed_status, text='Los resultados pueden variar entre ejecuciones por carga y ruta de red.', font=(FONT, 8), text_color=MUTED, anchor='e')
        self.lbl_speed_hint.pack(side='right', padx=(8, 0))

        diag = ctk.CTkFrame(connectivity_frame, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
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

        note = ctk.CTkFrame(connectivity_frame, fg_color=CARD_2, border_width=1, border_color=BORDER, corner_radius=10)
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

        self._select_network_view('network')
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

    def _refresh_network_view_buttons(self):
        for key, button in self._network_view_buttons.items():
            active = key == self._network_view
            button.configure(
                fg_color=(theme_color('#215c92') if active else 'transparent'),
                hover_color=(theme_color('#1b4e7c') if active else theme_color('#102840')),
                border_color=(theme_color('#2a7bc0') if active else BORDER),
                text_color=(TEXT if active else TEXT_2),
            )

    def _ensure_connectivity_runtime(self):
        if self._connectivity_runtime_started or not self._alive:
            return
        self._connectivity_runtime_started = True
        self._request_ookla_status()
        self._request_speed_servers()

    def _select_network_view(self, key):
        if key not in self._network_view_frames:
            key = 'network'
        self._network_view = key
        if key == 'connectivity':
            self._ensure_connectivity_runtime()
        for frame in self._network_view_frames.values():
            try:
                frame.pack_forget()
            except Exception:
                pass
        target = self._network_view_frames.get(key)
        if target is not None:
            target.pack(fill='x', padx=0, pady=0)
        self._refresh_network_view_buttons()

    def _add_row(self, parent, target, key, label):
        row = ctk.CTkFrame(parent, fg_color='transparent', height=33)
        row.pack(fill='x', padx=12, pady=1)
        row.pack_propagate(False)
        ctk.CTkLabel(row, text=label, width=155, font=(FONT, 8), text_color=MUTED, anchor='w').pack(side='left')
        value = ctk.CTkLabel(row, text='N/A', font=(FONT, 8, 'bold'), text_color=TEXT, anchor='w')
        value.pack(side='left', fill='x', expand=True, padx=(8, 0))
        target[key] = value

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
        provider_key = str(result.get('provider_key') or '').lower()
        if provider_key == 'ookla':
            name = _safe(server.get('name'))
            location = _safe(server.get('location'))
            country = _safe(server.get('country'))
            server_id = server.get('id')
            place = ', '.join(part for part in (location, country) if part != 'N/A')
            text = f'Servidor: {name}'
            if place:
                text += f' — {place}'
            if server_id is not None:
                text += f' · ID {server_id}'
            host = _safe(server.get('host'))
            if host != 'N/A':
                text += f' · {host}'
            return text

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
        return 'Servidor: Cloudflare edge ' + (' · '.join(parts) if parts else 'automático')

    def _speed_isp_text(self, result):
        if not isinstance(result, dict):
            return 'ISP: N/A'
        isp = _safe(result.get('isp'))
        external = _safe(result.get('external_ip'))
        text = f'ISP: {isp}'
        if external != 'N/A':
            text += f' · IP pública {external}'
        family = str(result.get('network_family') or '').upper()
        if family in ('IPV4', 'IPV6'):
            text += f' · Ruta {family}'
        loss = _num(result.get('packet_loss_percent'))
        if loss is not None:
            text += f' · Pérdida {loss:.1f}%'
        return text

    def _speed_compare_text(self, result):
        if not isinstance(result, dict):
            return 'Comparabilidad: pendiente'
        if result.get('provider_key') == 'ookla':
            server = result.get('server') if isinstance(result.get('server'), dict) else {}
            server_id = server.get('id')
            family = str(result.get('network_family') or result.get('requested_ip_family') or '').upper()
            if result.get('server_locked') and result.get('route_bound'):
                return f'Comparación controlada: Ookla + servidor ID {server_id if server_id is not None else "fijado"} + ruta {family or "IP"}. Verifica la misma IP/familia en la web.'
            if result.get('server_locked'):
                return f'Servidor ID {server_id if server_id is not None else "fijado"}, pero la ruta IP es automática; IPv4 e IPv6 pueden dar resultados muy distintos.'
            return 'Motor oficial de Ookla; fija servidor y familia IP para comparar de forma válida con Speedtest.net.'
        return 'Comparabilidad: Cloudflare es una prueba alternativa y no equivale 1:1 a Speedtest.net.'

    def _request_ookla_status(self):
        if self._ookla_status_loading:
            return
        self._ookla_status_loading = True

        def worker():
            try:
                status = self._speed_runner.cli_status()
            except Exception as exc:
                status = {'available': False, 'message': str(exc)[:160]}
            self._ookla_status = status if isinstance(status, dict) else {'available': False}
            self._ookla_status_loading = False

        threading.Thread(target=worker, name='CorePulseOoklaStatus', daemon=True).start()

    def _apply_ookla_status(self):
        status = self._ookla_status if isinstance(self._ookla_status, dict) else None
        if status is None:
            if self._ookla_status_loading:
                configure_changed(self.lbl_speed_engine, text='Motor: verificando Speedtest by Ookla…', text_color=AMBER)
            return
        if status.get('available'):
            version = _safe(status.get('version'))
            suffix = f' · {version}' if version != 'N/A' else ''
            configure_changed(self.lbl_speed_engine, text=f'Motor oficial detectado: Speedtest by Ookla{suffix}', text_color=GREEN)
            configure_changed(self.btn_speed_setup, text='CLI detectada')
        else:
            configure_changed(self.lbl_speed_engine, 
                text='Motor oficial no detectado · para resultados comparables con Speedtest.net instala/configura la CLI de Ookla.',
                text_color=AMBER,
            )
            configure_changed(self.btn_speed_setup, text='Configurar Ookla')

    def _request_speed_servers(self):
        if self._speed_running or self._speed_servers_loading:
            return
        if self._speed_runner.provider != 'ookla':
            return
        self._speed_servers_loading = True
        self.btn_speed_servers.configure(text='Buscando…', state='disabled')

        def worker():
            try:
                result = self._speed_runner.list_servers(limit=12)
            except Exception as exc:
                result = {'ok': False, 'servers': [], 'error_code': 'OOKLA_ERROR', 'message': str(exc)[:160]}
            self._speed_servers = result if isinstance(result, dict) else {'ok': False, 'servers': []}
            self._speed_servers_loading = False

        threading.Thread(target=worker, name='CorePulseOoklaServers', daemon=True).start()

    def _apply_speed_servers(self):
        configure_changed(self.btn_speed_servers, text='Buscando…' if self._speed_servers_loading else 'Actualizar servidores', state='disabled' if self._speed_servers_loading else 'normal')
        result = self._speed_servers if isinstance(self._speed_servers, dict) else None
        if result is None:
            return
        try:
            signature = repr((result.get('ok'), result.get('error_code'), result.get('servers')))
        except Exception:
            signature = str(id(result))
        if signature == self._speed_servers_signature:
            return
        self._speed_servers_signature = signature

        servers = result.get('servers') if isinstance(result.get('servers'), list) else []
        values = ['Automático (Ookla elige)']
        mapping = {'Automático (Ookla elige)': None}
        for server in servers:
            if not isinstance(server, dict) or server.get('id') is None:
                continue
            name = _safe(server.get('name'))
            location = _safe(server.get('location'))
            country = _safe(server.get('country'))
            place = ', '.join(part for part in (location, country) if part != 'N/A')
            label = f'{name} — {place} · ID {server.get("id")}' if place else f'{name} · ID {server.get("id")}'
            values.append(label)
            mapping[label] = server.get('id')
        self._speed_server_map = mapping
        configure_changed(self.speed_server_menu, values=values)

        selected = 'Automático (Ookla elige)'
        current_id = self._speed_runner.server_id
        for label, server_id in mapping.items():
            if current_id is not None and server_id == current_id:
                selected = label
                break
        self.speed_server_menu.set(selected)

        if not result.get('ok') and result.get('message'):
            configure_changed(self.lbl_speed_status, text=_safe(result.get('message')), text_color=AMBER)

    def _on_speed_provider_change(self, value):
        choice = str(value or '')
        self._speed_provider_choice = choice
        self._speed = None
        self._speed_result_url = None
        self.btn_speed_result.configure(state='disabled')
        for value_label, _detail in self._speed_labels.values():
            value_label.configure(text='—')
        self.speed_progress.set(0)

        if choice.startswith('Speedtest.net'):
            self._speed_runner.provider = 'ookla'
            self.speed_ip_menu.configure(state='normal')
            self.speed_server_menu.configure(state='normal', values=['Automático (Ookla elige)'])
            self.speed_server_menu.set('Automático (Ookla elige)')
            self._speed_runner.server_id = None
            self._speed_server_map = {'Automático (Ookla elige)': None}
            self.lbl_speed_status.configure(text='Modo Speedtest.net listo.', text_color=MUTED)
            self._request_ookla_status()
            self._request_speed_servers()
        else:
            self._speed_runner.provider = 'cloudflare'
            self._speed_runner.server_id = None
            self.speed_ip_menu.configure(state='disabled')
            self.speed_server_menu.configure(state='disabled', values=['Cloudflare edge automático'])
            self.speed_server_menu.set('Cloudflare edge automático')
            self.lbl_speed_engine.configure(text='Motor alternativo: Cloudflare · no comparable 1:1 con Speedtest.net.', text_color=AMBER)
            self.lbl_speed_status.configure(text='Modo alternativo Cloudflare listo.', text_color=MUTED)
        self.lbl_speed_server.configure(text='Servidor: N/A')
        self.lbl_speed_isp.configure(text='ISP: N/A')
        self.lbl_speed_compare.configure(text='Comparabilidad: pendiente')

    def _on_speed_server_change(self, value):
        if self._speed_runner.provider != 'ookla':
            return
        self._speed_runner.server_id = self._speed_server_map.get(str(value or ''))
        server_id = self._speed_runner.server_id
        if server_id is None:
            self.lbl_speed_compare.configure(text='Servidor automático: Ookla elegirá uno de los servidores disponibles.', text_color=MUTED)
        else:
            self.lbl_speed_compare.configure(text=f'Servidor fijado: ID {server_id} · úsalo también al comparar otra prueba.', text_color=GREEN)

    def _on_speed_ip_change(self, value):
        choice = str(value or '')
        self._speed_ip_choice = choice
        if choice.startswith('IPv4'):
            self._speed_runner.ip_family = 'ipv4'
        elif choice.startswith('IPv6'):
            self._speed_runner.ip_family = 'ipv6'
        else:
            self._speed_runner.ip_family = 'auto'
        self._speed_runner.bind_ip = None
        family = self._speed_runner.ip_family.upper() if self._speed_runner.ip_family != 'auto' else 'automática'
        self.lbl_speed_compare.configure(
            text=(f'Ruta {family} seleccionada. ' + ('El sistema elegirá la ruta disponible.' if self._speed_runner.ip_family == 'auto' else 'Para comparar con la web, usa también el mismo servidor y familia IP.')),
            text_color=GREEN if self._speed_runner.ip_family in ('ipv4', 'ipv6') else MUTED,
        )

    def _configure_ookla(self):
        script = resource_path('Instalar_Speedtest_Ookla.bat')
        if os.name != 'nt':
            self.lbl_speed_status.configure(text='La configuración automática de Ookla está disponible en Windows.', text_color=AMBER)
            return
        if not script.is_file():
            self.lbl_speed_status.configure(text='No se encontró Instalar_Speedtest_Ookla.bat.', text_color=RED)
            return
        try:
            os.startfile(str(script))
            self.lbl_speed_status.configure(text='Se abrió el instalador oficial vía winget. Al terminar, vuelve a “Actualizar servidores”.', text_color=AMBER)
        except Exception as exc:
            self.lbl_speed_status.configure(text=f'No se pudo abrir el instalador: {str(exc)[:120]}', text_color=RED)

    def _open_speed_result(self):
        url = str(self._speed_result_url or '').strip()
        if not url.startswith('https://www.speedtest.net/'):
            return
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _start_speed_test(self):
        if self._speed_running:
            return
        self._speed_running = True
        self._speed = None
        self._speed_result_url = None
        provider_name = 'Speedtest by Ookla' if self._speed_runner.provider == 'ookla' else 'Cloudflare'
        self._speed_progress = {'phase': 'preparing', 'percent': 1, 'message': f'Preparando {provider_name}…'}
        self.btn_speed.configure(text='Midiendo…', state='disabled')
        self.btn_speed_result.configure(state='disabled')
        self.lbl_speed_status.configure(text=f'Preparando medición con {provider_name}…', text_color=AMBER)
        self.lbl_speed_server.configure(text='Servidor: seleccionando…')
        self.lbl_speed_isp.configure(text='ISP: detectando…')
        self.speed_progress.set(0.01)
        for value, _detail in self._speed_labels.values():
            value.configure(text='—')
        self.lbl_speed_loaded_latency.configure(text='LATENCIA · Reposo N/A · Durante descarga N/A · Durante subida N/A')

        def progress(payload):
            # Sólo memoria compartida; nunca toca Tk desde el worker.
            if isinstance(payload, dict):
                self._speed_progress = dict(payload)

        primary = self._primary()
        self._speed_runner.link_speed_mbps = _num(primary.get('link_speed_mbps')) if isinstance(primary, dict) else None
        self._speed_runner.bind_ip = None
        if isinstance(primary, dict):
            if self._speed_runner.ip_family == 'ipv4':
                self._speed_runner.bind_ip = _first_ip(primary.get('ipv4'), 'ipv4')
            elif self._speed_runner.ip_family == 'ipv6':
                self._speed_runner.bind_ip = _first_ip(primary.get('ipv6'), 'ipv6')

        def worker():
            try:
                result = self._speed_runner.run(progress=progress)
            except Exception as exc:
                result = {
                    'ok': False, 'error': str(exc)[:180], 'timestamp': time.time(),
                    'download_mbps': None, 'upload_mbps': None, 'latency_ms': None, 'jitter_ms': None,
                    'provider_key': self._speed_runner.provider,
                }
            self._speed = result
            self._speed_running = False

        threading.Thread(target=worker, name='CorePulseInternetSpeedTest', daemon=True).start()

    def _apply_speed_test(self):
        # Tras una medición el motor usado es la autoridad del texto; no pintar
        # primero el estado de instalación y sobrescribirlo cada segundo.
        if self._speed_running or not isinstance(self._speed, dict):
            self._apply_ookla_status()
        self._apply_speed_servers()
        progress = self._speed_progress if isinstance(self._speed_progress, dict) else {}
        percent = _num(progress.get('percent'))
        if percent is not None:
            set_changed(self.speed_progress, max(0.0, min(1.0, percent / 100.0)))
        if self._speed_running:
            configure_changed(self.btn_speed, text='Midiendo…', state='disabled')
            configure_changed(self.lbl_speed_status, text=_safe(progress.get('message')), text_color=AMBER)
            current = _num(progress.get('current_mbps'))
            phase = progress.get('phase')
            if current is not None and phase in ('download', 'upload'):
                key = 'download' if phase == 'download' else 'upload'
                configure_changed(self._speed_labels[key][0], text=f'{current:.1f}')
            return

        configure_changed(self.btn_speed, text='Repetir prueba' if isinstance(self._speed, dict) else 'Iniciar prueba', state='normal')
        result = self._speed
        if not isinstance(result, dict):
            return
        values = (
            ('download', result.get('download_mbps'), 1),
            ('upload', result.get('upload_mbps'), 1),
            ('ping', result.get('latency_ms'), 1),
            ('jitter', result.get('jitter_ms'), 1),
            ('loss', result.get('packet_loss_percent'), 1),
        )
        for key, raw, decimals in values:
            value_label, _detail = self._speed_labels[key]
            number = _num(raw)
            configure_changed(value_label, text=f'{number:.{decimals}f}' if number is not None else 'N/A')

        idle = _num(result.get('latency_ms'))
        down_latency = result.get('download_latency') if isinstance(result.get('download_latency'), dict) else {}
        up_latency = result.get('upload_latency') if isinstance(result.get('upload_latency'), dict) else {}
        loaded_down = _num(down_latency.get('latency_ms'))
        loaded_up = _num(up_latency.get('latency_ms'))
        def _ms(v):
            return f'{v:.1f} ms' if v is not None else 'N/A'
        configure_changed(self.lbl_speed_loaded_latency, 
            text=f'LATENCIA · Reposo {_ms(idle)} · Durante descarga {_ms(loaded_down)} · Durante subida {_ms(loaded_up)}'
        )

        set_changed(self.speed_progress, 1 if result.get('ok') else 0)
        provider_key = str(result.get('provider_key') or '')
        if provider_key == 'ookla':
            version = _safe(result.get('cli_version'))
            configure_changed(self.lbl_speed_engine, 
                text='Motor usado: Speedtest by Ookla · CLI oficial' + (f' · {version}' if version != 'N/A' else ''),
                text_color=GREEN if result.get('official_engine') else AMBER,
            )
        else:
            configure_changed(self.lbl_speed_engine, text='Motor usado: Cloudflare · prueba alternativa, no Speedtest.net.', text_color=AMBER)

        configure_changed(self.lbl_speed_server, text=self._speed_server_text(result))
        configure_changed(self.lbl_speed_isp, text=self._speed_isp_text(result))
        configure_changed(self.lbl_speed_compare, 
            text=self._speed_compare_text(result),
            text_color=GREEN if provider_key == 'ookla' and result.get('ok') else AMBER if provider_key != 'ookla' else MUTED,
        )
        self._speed_result_url = result.get('result_url') if provider_key == 'ookla' else None
        configure_changed(self.btn_speed_result, state='normal' if self._speed_result_url else 'disabled')

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
                suffix.append(f'{len(notes)} aviso' + ('s' if len(notes) != 1 else ''))
            title = 'Speedtest by Ookla completado' if provider_key == 'ookla' else 'Prueba alternativa Cloudflare completada'
            configure_changed(self.lbl_speed_status, 
                text=title + (f" · {' · '.join(suffix)}" if suffix else ''),
                text_color=AMBER if notes else GREEN,
            )
        else:
            code = result.get('error_code')
            if code == 'OOKLA_CLI_NOT_FOUND':
                message = 'Speedtest by Ookla no está instalado. Pulsa “Configurar Ookla” para usar el motor oficial.'
            elif code == 'OOKLA_LICENSE_REQUIRED':
                message = 'La CLI oficial necesita configuración inicial: revisa y acepta sus términos una vez en la consola abierta por “Configurar Ookla”.'
            else:
                notes = [str(x) for x in (result.get('validation_notes') or []) if x]
                # Compatibilidad de diagnóstico: una medición descartada por superar el enlace físico sigue siendo explícita.
                message = _safe(result.get('error')) if result.get('error') else ('Medición descartada por superar el enlace físico.' if notes else 'No se pudo completar la prueba de velocidad.')
            configure_changed(self.lbl_speed_status, text=message, text_color=RED)

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
        configure_changed(self.btn_diagnose, text='Ejecutar diagnóstico', state='normal')
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
        configure_changed(self.lbl_diag_status, text=status_text, text_color=status_color)
        gateway = diag.get('gateway') if isinstance(diag.get('gateway'), dict) else {}
        internet = diag.get('internet') if isinstance(diag.get('internet'), dict) else {}
        dns = diag.get('dns') if isinstance(diag.get('dns'), dict) else {}
        for key, test, ok in (
            ('gateway', gateway, bool(gateway.get('reachable'))),
            ('internet', internet, bool(internet.get('reachable'))),
            ('dns', dns, bool(dns.get('ok'))),
        ):
            value, detail = self._diag_labels[key]
            configure_changed(value, text='Correcto' if ok else ('No disponible' if key == 'gateway' and not gateway.get('target') else 'Atención'), text_color=GREEN if ok else AMBER)
            detail_text = _diag_value(test)
            if key == 'gateway' and gateway.get('target'):
                detail_text += f" · {gateway.get('target')}"
            elif key == 'internet':
                detail_text += ' · 1.1.1.1'
            elif key == 'dns':
                detail_text += f" · {_safe(dns.get('host'))}"
            configure_changed(detail, text=detail_text)

    def refresh(self):
        if not self._alive or not self._visible:
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
            configure_changed(self.lbl_freshness, text=f'Actualización: {_age(runtime.get("timestamp"))}')

            connected = bool(primary and primary.get('is_up'))
            configure_changed(self.status_value, text='Conectado' if connected else ('Sin conexión' if self._identity is not None else 'Cargando'), text_color=GREEN if connected else RED if self._identity is not None else MUTED)
            configure_changed(self.status_detail, text=_safe(primary_name) if primary_name else 'Adaptador principal')
            configure_changed(self.down_value, text=_format_rate(runtime.get('download_bps')), text_color=CYAN if _num(runtime.get('download_bps')) is not None else MUTED)
            configure_changed(self.up_value, text=_format_rate(runtime.get('upload_bps')), text_color=PURPLE if _num(runtime.get('upload_bps')) is not None else MUTED)
            configure_changed(self.link_value, text=_format_speed_mbps(primary.get('link_speed_mbps')) if primary else 'N/A', text_color=CYAN if primary and _num(primary.get('link_speed_mbps')) is not None else MUTED)
            configure_changed(self.link_detail, text='Velocidad negociada del adaptador')

            if not self._is_scrolling():
                # No repintar la subvista oculta. Los workers pueden terminar en
                # segundo plano y el último estado se materializa al volver.
                if self._network_view == 'connectivity':
                    self._ensure_connectivity_runtime()
                    self._apply_speed_test()
                    self._apply_diag()
                else:
                    self._apply_identity()
                    configure_changed(self._traffic_labels['download'], text=_format_rate(runtime.get('download_bps')))
                    configure_changed(self._traffic_labels['upload'], text=_format_rate(runtime.get('upload_bps')))
                    configure_changed(self._traffic_labels['received'], text=_format_bytes(runtime.get('bytes_recv_total')))
                    configure_changed(self._traffic_labels['sent'], text=_format_bytes(runtime.get('bytes_sent_total')))
                    configure_changed(self._traffic_labels['packets_in'], text=_safe(runtime.get('packets_recv_total')))
                    configure_changed(self._traffic_labels['packets_out'], text=_safe(runtime.get('packets_sent_total')))
                    errors = None
                    if _num(runtime.get('errors_in_total')) is not None or _num(runtime.get('errors_out_total')) is not None:
                        errors = f"Entrada {_safe(runtime.get('errors_in_total'))} · Salida {_safe(runtime.get('errors_out_total'))}"
                    drops = None
                    if _num(runtime.get('drops_in_total')) is not None or _num(runtime.get('drops_out_total')) is not None:
                        drops = f"Entrada {_safe(runtime.get('drops_in_total'))} · Salida {_safe(runtime.get('drops_out_total'))}"
                    configure_changed(self._traffic_labels['errors'], text=errors or 'N/A')
                    configure_changed(self._traffic_labels['drops'], text=drops or 'N/A')
                    configure_changed(self._traffic_labels['source'], text=_safe(runtime.get('source')))
                    if identity_stamp is not None:
                        configure_changed(self.lbl_source, text=f"Inventario de red: {_safe((self._identity or {}).get('source'))} · {_age(identity_stamp)}")
        except Exception:
            pass
        if self._alive and self._visible:
            try:
                self._after_id = self.frame.after(950, self.refresh)
            except Exception:
                self._after_id = None
