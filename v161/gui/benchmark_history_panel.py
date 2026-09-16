"""Historial profesional de benchmark de CorePulse V137.

La vista reutiliza exclusivamente sesiones persistidas por ``HealthHistoryStore``.
No crea rankings externos, no rellena métricas ausentes y sólo calcula variaciones
cuando existen dos mediciones reales equivalentes del mismo perfil/componentes y
hardware compatible.
"""
from __future__ import annotations

import csv
import datetime as dt
import math
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.theme_manager import role_color

FONT = "Segoe UI"
BG = role_color("bg")
SURFACE = role_color("surface")
SURFACE_2 = role_color("surface_2")
BORDER = role_color("border")
TEXT = role_color("text")
TEXT_2 = role_color("text_2")
MUTED = role_color("muted")
ACCENT = role_color("accent")
ACCENT_2 = role_color("accent_2")
GREEN = "#10b981"
AMBER = "#f59e0b"
RED = "#ef4444"
PURPLE = "#a855f7"

PROFILE_LABELS = {
    "QUICK": "Rápido",
    "FAST": "Rápido",
    "RAPIDO": "Rápido",
    "STANDARD": "Estándar",
    "ESTANDAR": "Estándar",
    "EXTENDED": "Extendido",
    "EXTENDIDO": "Extendido",
}
PROFILE_FILTERS = ("Todos", "Rápido", "Estándar", "Extendido")
COMPONENT_FILTERS = ("Todos", "GPU", "CPU", "RAM", "SSD")
STATUS_FILTERS = ("Todos", "Completado", "Parcial", "Error")


def _num(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _fmt_duration(value):
    seconds = _num(value)
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    return f"{minutes} min {rest:.0f} s"


def _profile_label(value):
    key = str(value or "").strip().upper()
    return PROFILE_LABELS.get(key, key.title() if key else "N/A")


def _components(session):
    values = []
    for item in (session.get("components") or []):
        key = str(item or "").strip().upper()
        if key and key not in values:
            values.append(key)
    if values:
        return values
    suite = session.get("suite") if isinstance(session.get("suite"), dict) else {}
    for item in (suite.get("selected_components") or []):
        key = str(item or "").strip().upper()
        if key and key not in values:
            values.append(key)
    return values


def _suite(session):
    return session.get("suite") if isinstance(session.get("suite"), dict) else {}


def _visual(session):
    suite = _suite(session)
    return suite.get("visual_gpu") if isinstance(suite.get("visual_gpu"), dict) else {}


def _system_suite(session):
    suite = _suite(session)
    return suite.get("system_suite") if isinstance(suite.get("system_suite"), dict) else {}


def _renderer(session):
    visual = _visual(session)
    hardware = session.get("hardware") if isinstance(session.get("hardware"), dict) else {}
    value = visual.get("renderer") or hardware.get("renderer")
    return str(value).strip() if value else "N/A"


def _status(session):
    suite = _suite(session)
    return str(suite.get("status") or "N/A").strip().upper()


def _metric(session, key):
    visual = _visual(session)
    system = _system_suite(session)
    if key == "gpu_fps":
        return _num(visual.get("frames_per_s"))
    if key == "gpu_low":
        return _num(visual.get("one_percent_low_fps"))
    if key == "cpu":
        row = system.get("cpu") if isinstance(system.get("cpu"), dict) else {}
        value = _num(row.get("throughput_mbps"))
        if value is None:
            legacy = visual.get("cpu_benchmark") if isinstance(visual.get("cpu_benchmark"), dict) else {}
            value = _num(legacy.get("throughput_mbps"))
        return value
    if key == "ram":
        row = system.get("ram") if isinstance(system.get("ram"), dict) else {}
        value = _num(row.get("value"))
        if value is not None:
            return value / 1024.0 if value >= 1024 else value / 1024.0
        legacy = visual.get("ram_benchmark") if isinstance(visual.get("ram_benchmark"), dict) else {}
        return _num(legacy.get("copy_gb_s"))
    if key == "ssd_read":
        row = system.get("ssd") if isinstance(system.get("ssd"), dict) else {}
        return _num(row.get("read_mbps"))
    if key == "ssd_write":
        row = system.get("ssd") if isinstance(system.get("ssd"), dict) else {}
        return _num(row.get("write_mbps"))
    return None


def _metric_text(session):
    parts = []
    for key, label, unit, digits in (
        ("gpu_fps", "GPU", " FPS", 1),
        ("gpu_low", "1% Low", " FPS", 1),
        ("cpu", "CPU", " MB/s", 0),
        ("ram", "RAM", " GB/s", 2),
        ("ssd_read", "SSD L", " MB/s", 0),
        ("ssd_write", "SSD E", " MB/s", 0),
    ):
        value = _metric(session, key)
        if value is not None:
            parts.append(f"{label}: {value:.{digits}f}{unit}")
    return "  ·  ".join(parts) if parts else "Sin métricas numéricas válidas guardadas"


def _signature(session):
    profile = str(session.get("profile") or _suite(session).get("profile") or "").strip().upper()
    comps = tuple(sorted(_components(session)))
    hardware = session.get("hardware") if isinstance(session.get("hardware"), dict) else {}
    cpu = str(hardware.get("cpu_name") or "").strip().lower()
    gpu = str(hardware.get("gpu_name") or "").strip().lower()
    renderer = _renderer(session).strip().lower()
    return profile, comps, cpu, gpu, renderer if renderer != "n/a" else ""


def _equivalent(a, b):
    pa, ca, cpua, gpua, ra = _signature(a)
    pb, cb, cpub, gpub, rb = _signature(b)
    if pa != pb or ca != cb:
        return False
    if cpua and cpub and cpua != cpub:
        return False
    if gpua and gpub and gpua != gpub:
        return False
    # Renderer sólo restringe cuando ambos fueron registrados. Esto conserva
    # compatibilidad con sesiones V114-V136 donde el renderer no estaba en hardware_json.
    if ra and rb and ra != rb:
        return False
    return True


class BenchmarkHistoryPanel:
    def __init__(self, app, host):
        self.app = app
        self.host = host
        self.frame = ctk.CTkFrame(host, fg_color=BG, corner_radius=0)
        self.frame.pack(fill="both", expand=True)
        self.profile_filter = ctk.StringVar(value="Todos")
        self.component_filter = ctk.StringVar(value="Todos")
        self.status_filter = ctk.StringVar(value="Todos")
        self._selected_id = None
        self._sessions = []
        self._total_count = 0

        toolbar = ctk.CTkFrame(self.frame, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=10)
        toolbar.pack(fill="x", padx=4, pady=(4, 10))
        left = ctk.CTkFrame(toolbar, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=14, pady=11)
        ctk.CTkLabel(left, text="Historial de benchmark", font=(FONT, 16, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="Sesiones reales guardadas en este PC. Las variaciones sólo comparan ejecuciones equivalentes; no existen rankings externos.",
            font=(FONT, 9), text_color=TEXT_2, anchor="w", justify="left",
        ).pack(anchor="w", pady=(2, 0))

        filters = ctk.CTkFrame(toolbar, fg_color="transparent")
        filters.pack(side="right", padx=12, pady=9)
        ctk.CTkLabel(filters, text="Perfil", font=(FONT, 9, "bold"), text_color=MUTED).grid(row=0, column=0, padx=(0, 5), sticky="e")
        self.profile_menu = ctk.CTkOptionMenu(
            filters, values=list(PROFILE_FILTERS), variable=self.profile_filter,
            command=lambda _v: self.refresh(), width=118, height=31,
            fg_color=SURFACE_2, button_color=ACCENT_2, button_hover_color=ACCENT,
            text_color=TEXT, dropdown_fg_color=SURFACE, dropdown_text_color=TEXT,
        )
        self.profile_menu.grid(row=0, column=1, padx=(0, 10))
        ctk.CTkLabel(filters, text="Componente", font=(FONT, 9, "bold"), text_color=MUTED).grid(row=0, column=2, padx=(0, 5), sticky="e")
        self.component_menu = ctk.CTkOptionMenu(
            filters, values=list(COMPONENT_FILTERS), variable=self.component_filter,
            command=lambda _v: self.refresh(), width=105, height=31,
            fg_color=SURFACE_2, button_color=ACCENT_2, button_hover_color=ACCENT,
            text_color=TEXT, dropdown_fg_color=SURFACE, dropdown_text_color=TEXT,
        )
        self.component_menu.grid(row=0, column=3, padx=(0, 8))
        ctk.CTkLabel(filters, text="Estado", font=(FONT, 9, "bold"), text_color=MUTED).grid(row=0, column=4, padx=(0, 5), sticky="e")
        self.status_menu = ctk.CTkOptionMenu(
            filters, values=list(STATUS_FILTERS), variable=self.status_filter,
            command=lambda _v: self.refresh(), width=108, height=31,
            fg_color=SURFACE_2, button_color=ACCENT_2, button_hover_color=ACCENT,
            text_color=TEXT, dropdown_fg_color=SURFACE, dropdown_text_color=TEXT,
        )
        self.status_menu.grid(row=0, column=5, padx=(0, 8))
        ctk.CTkButton(
            filters, text="Limpiar", command=self._clear_filters, width=74, height=31,
            fg_color="transparent", hover_color=SURFACE_2, border_width=1,
            border_color=BORDER, text_color=TEXT_2, font=(FONT, 9, "bold"),
        ).grid(row=0, column=6, padx=(0, 6))
        ctk.CTkButton(
            filters, text="Exportar CSV", command=self._export_csv, width=98, height=31,
            fg_color="transparent", hover_color=SURFACE_2, border_width=1,
            border_color=BORDER, text_color=TEXT_2, font=(FONT, 9, "bold"),
        ).grid(row=0, column=7)

        self.scroll = ctk.CTkScrollableFrame(self.frame, fg_color=BG, corner_radius=0)
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)
        self.refresh()

    def widget(self):
        return self.frame

    def _read_sessions(self):
        store = getattr(self.app, "health_history_store", None)
        self._total_count = 0
        if store is None or not hasattr(store, "latest_benchmark_sessions"):
            return []
        try:
            if hasattr(store, "benchmark_session_count"):
                self._total_count = int(store.benchmark_session_count())
            sessions = list(store.latest_benchmark_sessions(limit=100))
            if not self._total_count:
                self._total_count = len(sessions)
            return sessions
        except Exception:
            return []

    def _filtered(self, sessions):
        profile = self.profile_filter.get()
        component = self.component_filter.get()
        status_filter = self.status_filter.get()
        out = []
        for session in sessions:
            if not isinstance(session, dict):
                continue
            if profile != "Todos" and _profile_label(session.get("profile") or _suite(session).get("profile")) != profile:
                continue
            if component != "Todos" and component not in _components(session):
                continue
            status = _status(session)
            if status_filter == "Completado" and status != "OK":
                continue
            if status_filter == "Parcial" and status not in {"PARTIAL", "CANCELLED", "UNAVAILABLE"}:
                continue
            if status_filter == "Error" and status not in {"ERROR", "SAFETY_STOP"}:
                continue
            out.append(session)
        return out

    def _clear_filters(self):
        self.profile_filter.set("Todos")
        self.component_filter.set("Todos")
        self.status_filter.set("Todos")
        self.refresh()

    def _export_csv(self):
        sessions = self._filtered(self._read_sessions())
        if not sessions:
            messagebox.showinfo("CorePulse · Benchmark", "No hay sesiones visibles para exportar.")
            return
        path = filedialog.asksaveasfilename(
            title="Exportar historial de benchmark",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"CorePulse_Benchmark_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        )
        if not path:
            return
        headers = [
            "fecha", "perfil", "estado", "duracion_s", "componentes",
            "cpu", "gpu_supervisada", "renderer_opengl",
            "gpu_fps", "gpu_1pct_low_fps", "cpu_mbps_sha256",
            "ram_gb_s", "ssd_lectura_mbps", "ssd_escritura_mbps",
        ]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=headers)
                writer.writeheader()
                for session in sessions:
                    hardware = session.get("hardware") if isinstance(session.get("hardware"), dict) else {}
                    try:
                        stamp = dt.datetime.fromtimestamp(float(session.get("ts") or 0)).isoformat(sep=" ", timespec="seconds")
                    except Exception:
                        stamp = ""
                    writer.writerow({
                        "fecha": stamp,
                        "perfil": _profile_label(session.get("profile") or _suite(session).get("profile")),
                        "estado": _status(session),
                        "duracion_s": _num(_suite(session).get("duration_s")),
                        "componentes": ",".join(_components(session)),
                        "cpu": hardware.get("cpu_name") or "",
                        "gpu_supervisada": hardware.get("gpu_name") or "",
                        "renderer_opengl": _renderer(session) if _renderer(session) != "N/A" else "",
                        "gpu_fps": _metric(session, "gpu_fps"),
                        "gpu_1pct_low_fps": _metric(session, "gpu_low"),
                        "cpu_mbps_sha256": _metric(session, "cpu"),
                        "ram_gb_s": _metric(session, "ram"),
                        "ssd_lectura_mbps": _metric(session, "ssd_read"),
                        "ssd_escritura_mbps": _metric(session, "ssd_write"),
                    })
            messagebox.showinfo("CorePulse · Benchmark", f"Historial exportado correctamente:\n{path}")
        except Exception as exc:
            messagebox.showerror("CorePulse · Benchmark", f"No se pudo exportar el CSV:\n{exc}")

    def _clear(self):
        for child in self.scroll.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

    def refresh(self):
        if not self.frame.winfo_exists():
            return
        self._sessions = self._read_sessions()
        sessions = self._filtered(self._sessions)
        self._clear()
        self._render_summary(sessions)
        self._render_comparison(sessions)
        self._render_sessions(sessions)

    def _summary_card(self, parent, col, title, value, detail=""):
        card = ctk.CTkFrame(parent, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=9)
        card.grid(row=0, column=col, sticky="nsew", padx=4, pady=4)
        ctk.CTkLabel(card, text=title, font=(FONT, 9, "bold"), text_color=MUTED, anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(card, text=value, font=(FONT, 12, "bold"), text_color=TEXT, anchor="w").pack(fill="x", padx=10)
        if detail:
            ctk.CTkLabel(card, text=detail, font=(FONT, 9), text_color=TEXT_2, anchor="w", wraplength=240).pack(fill="x", padx=10, pady=(2, 8))
        else:
            ctk.CTkLabel(card, text="", height=12, font=(FONT, 9), text_color=MUTED).pack(fill="x", padx=10, pady=(0, 5))

    def _render_summary(self, sessions):
        grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
        grid.pack(fill="x", padx=3, pady=(0, 6))
        for col in range(4):
            grid.grid_columnconfigure(col, weight=1, uniform="bench_history_summary")
        latest = sessions[0] if sessions else None
        total_all = max(len(self._sessions), int(self._total_count or 0))
        filtered = len(sessions)
        count_text = str(filtered) if filtered == total_all else f"{filtered} / {total_all}"
        self._summary_card(grid, 0, "SESIONES", count_text, "filtradas / guardadas" if filtered != total_all else "guardadas en este PC")
        if latest:
            try:
                date_text = dt.datetime.fromtimestamp(float(latest.get("ts") or 0)).strftime("%d-%m-%Y %H:%M")
            except Exception:
                date_text = "N/A"
            self._summary_card(grid, 1, "ÚLTIMA EJECUCIÓN", date_text, _profile_label(latest.get("profile")))
            self._summary_card(grid, 2, "DURACIÓN", _fmt_duration(_suite(latest).get("duration_s")), ", ".join(_components(latest)) or "Componentes N/A")
            renderer = _renderer(latest)
            self._summary_card(grid, 3, "RENDERER GPU", renderer, "registrado por OpenGL" if renderer != "N/A" else "N/A en esta sesión")
        else:
            self._summary_card(grid, 1, "ÚLTIMA EJECUCIÓN", "N/A")
            self._summary_card(grid, 2, "DURACIÓN", "N/A")
            self._summary_card(grid, 3, "RENDERER GPU", "N/A")

    def _render_comparison(self, sessions):
        if len(sessions) < 2:
            return
        current = sessions[0]
        previous = next((item for item in sessions[1:] if _equivalent(current, item)), None)
        box = ctk.CTkFrame(self.scroll, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=10)
        box.pack(fill="x", padx=7, pady=(2, 9))
        ctk.CTkLabel(box, text="Comparación automática", font=(FONT, 10, "bold"), text_color=ACCENT, anchor="w").pack(fill="x", padx=12, pady=(9, 2))
        if previous is None:
            ctk.CTkLabel(
                box, text="No existe todavía otra ejecución equivalente con el mismo perfil, componentes y hardware compatible.",
                font=(FONT, 9), text_color=TEXT_2, anchor="w", justify="left",
            ).pack(fill="x", padx=12, pady=(0, 9))
            return
        try:
            prev_date = dt.datetime.fromtimestamp(float(previous.get("ts") or 0)).strftime("%d-%m-%Y %H:%M")
        except Exception:
            prev_date = "sesión anterior"
        changes = []
        for key, label in (("gpu_fps", "GPU FPS"), ("gpu_low", "1% Low"), ("cpu", "CPU"), ("ram", "RAM"), ("ssd_read", "SSD lectura"), ("ssd_write", "SSD escritura")):
            new = _metric(current, key)
            old = _metric(previous, key)
            if new is None or old in (None, 0):
                continue
            delta = ((new - old) / abs(old)) * 100.0
            changes.append(f"{label} {'+' if delta >= 0 else ''}{delta:.1f}%")
        text = "  ·  ".join(changes) if changes else "No hay dos métricas numéricas equivalentes suficientes para calcular variaciones."
        ctk.CTkLabel(box, text=f"Contra {prev_date}", font=(FONT, 9, "bold"), text_color=MUTED, anchor="w").pack(fill="x", padx=12, pady=(0, 2))
        ctk.CTkLabel(box, text=text, font=(FONT, 9, "bold"), text_color=ACCENT if changes else TEXT_2, anchor="w", justify="left", wraplength=1100).pack(fill="x", padx=12, pady=(0, 9))

    def _render_sessions(self, sessions):
        head = ctk.CTkFrame(self.scroll, fg_color="transparent")
        head.pack(fill="x", padx=9, pady=(2, 4))
        ctk.CTkLabel(head, text="Ejecuciones", font=(FONT, 11, "bold"), text_color=TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(head, text=f"{len(sessions)} mostrada(s)", font=(FONT, 9, "bold"), text_color=MUTED).pack(side="right")
        if not sessions:
            empty = ctk.CTkFrame(self.scroll, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=10)
            empty.pack(fill="x", padx=7, pady=5)
            ctk.CTkLabel(empty, text="Todavía no hay benchmarks que coincidan con estos filtros.", font=(FONT, 10, "bold"), text_color=TEXT, anchor="w").pack(fill="x", padx=14, pady=(12, 3))
            ctk.CTkLabel(empty, text="Ejecuta un benchmark; CorePulse guardará automáticamente sólo las mediciones reales obtenidas.", font=(FONT, 9), text_color=TEXT_2, anchor="w").pack(fill="x", padx=14, pady=(0, 12))
            return
        for session in sessions[:50]:
            self._render_session_card(session)

    def _render_session_card(self, session):
        sid = session.get("id")
        selected = sid == self._selected_id
        card = ctk.CTkFrame(self.scroll, fg_color=SURFACE, border_width=1, border_color=ACCENT_2 if selected else BORDER, corner_radius=10)
        card.pack(fill="x", padx=7, pady=4)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(9, 4))
        try:
            stamp = dt.datetime.fromtimestamp(float(session.get("ts") or 0)).strftime("%d-%m-%Y · %H:%M:%S")
        except Exception:
            stamp = "Fecha N/A"
        profile = _profile_label(session.get("profile") or _suite(session).get("profile"))
        status = _status(session)
        status_color = GREEN if status == "OK" else AMBER if status in {"PARTIAL", "CANCELLED", "UNAVAILABLE"} else RED if status in {"ERROR", "SAFETY_STOP"} else MUTED
        ctk.CTkLabel(top, text=stamp, font=(FONT, 9, "bold"), text_color=TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(top, text=f"{profile}  ·  {status}", font=(FONT, 9, "bold"), text_color=status_color).pack(side="right")
        meta = ctk.CTkFrame(card, fg_color="transparent")
        meta.pack(fill="x", padx=12, pady=(0, 3))
        ctk.CTkLabel(meta, text="Componentes: " + (", ".join(_components(session)) or "N/A"), font=(FONT, 9, "bold"), text_color=MUTED, anchor="w").pack(side="left")
        ctk.CTkLabel(meta, text="Duración: " + _fmt_duration(_suite(session).get("duration_s")), font=(FONT, 9), text_color=MUTED).pack(side="right")
        ctk.CTkLabel(card, text=_metric_text(session), font=(FONT, 9, "bold"), text_color=TEXT_2, anchor="w", justify="left", wraplength=1040).pack(fill="x", padx=12, pady=(2, 3))
        renderer = _renderer(session)
        ctk.CTkLabel(card, text=f"Renderer: {renderer}", font=(FONT, 9), text_color=MUTED, anchor="w", justify="left", wraplength=1000).pack(fill="x", padx=12, pady=(0, 5))
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(0, 9))
        ctk.CTkButton(
            actions, text="Ocultar detalle" if selected else "Ver detalle",
            command=lambda value=sid: self._toggle_detail(value), width=106, height=28,
            fg_color=ACCENT_2 if selected else "transparent", hover_color=ACCENT_2,
            border_width=1, border_color=BORDER, text_color=TEXT, font=(FONT, 9, "bold"),
        ).pack(side="left")
        if selected:
            self._render_detail(card, session)

    def _toggle_detail(self, sid):
        self._selected_id = None if self._selected_id == sid else sid
        self.refresh()

    def _render_detail(self, card, session):
        detail = ctk.CTkFrame(card, fg_color=SURFACE_2, border_width=1, border_color=BORDER, corner_radius=8)
        detail.pack(fill="x", padx=12, pady=(0, 11))
        hardware = session.get("hardware") if isinstance(session.get("hardware"), dict) else {}
        suite = _suite(session)
        rows = [
            ("CPU", hardware.get("cpu_name") or "N/A"),
            ("GPU supervisada", hardware.get("gpu_name") or "N/A"),
            ("Renderer OpenGL", _renderer(session)),
            ("Perfil", _profile_label(session.get("profile") or suite.get("profile"))),
            ("Componentes", ", ".join(_components(session)) or "N/A"),
            ("Estado", _status(session)),
            ("Duración", _fmt_duration(suite.get("duration_s"))),
            ("Resultados", _metric_text(session)),
        ]
        reason = str(suite.get("reason") or "").strip()
        if reason:
            rows.append(("Detalle", reason))
        for label, value in rows:
            row = ctk.CTkFrame(detail, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=label, width=130, font=(FONT, 9, "bold"), text_color=MUTED, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=str(value), font=(FONT, 9), text_color=TEXT_2, anchor="w", justify="left", wraplength=880).pack(side="left", fill="x", expand=True)

    def destroy(self):
        try:
            self.frame.destroy()
        except Exception:
            pass
