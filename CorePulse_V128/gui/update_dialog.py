"""Centro de actualizaciones manual para el canal interno de CorePulse V118."""
from __future__ import annotations

import threading
import webbrowser

import customtkinter as ctk

from core.runtime_paths import is_frozen
from core.theme_manager import color as theme_color
from core.update_manager import (
    CHANNEL_INTERNAL, CHANNEL_STABLE, UpdateError, check_for_update, choose_asset,
    download_asset, launch_installer, launch_staged_source, load_preferences,
    open_updates_folder, releases_web_url, save_preferences, stage_source_release,
)
from core.version import VERSION_LABEL
from gui.dialogs import error as cp_error, info as cp_info, warning as cp_warning

FONT = "Segoe UI"
BG = theme_color("#06111f")
CARD = theme_color("#0b1726")
CARD_2 = theme_color("#0e1d2f")
BORDER = theme_color("#17314d")
TEXT = theme_color("#f4f7fb")
TEXT_2 = theme_color("#c2ccda")
MUTED = theme_color("#8295ad")
BLUE = "#08aef0"
GREEN = "#16d98b"
AMBER = "#f3b54a"
RED = "#ff5d6c"

CHANNEL_LABELS = {
    "Pruebas internas": CHANNEL_INTERNAL,
    "Estable": CHANNEL_STABLE,
}
LABEL_BY_CHANNEL = {value: key for key, value in CHANNEL_LABELS.items()}


def _fmt_bytes(value: int) -> str:
    try:
        value = max(0, int(value))
    except Exception:
        return "N/A"
    if value >= 1024 ** 3:
        return f"{value / 1024 ** 3:.2f} GB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} B"


class UpdateDialog:
    def __init__(self, app):
        self.app = app
        self.window = ctk.CTkToplevel(app)
        self.window.title("CorePulse · Actualizaciones")
        self.window.geometry("760x650")
        self.window.minsize(720, 610)
        self.window.configure(fg_color=BG)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.window.transient(app)
            self.window.lift()
            self.window.focus_force()
        except Exception:
            pass

        self.result = None
        self.asset = None
        self.download = None
        self.staged = None
        self.busy = False

        prefs = load_preferences()
        self.channel_var = ctk.StringVar(value=LABEL_BY_CHANNEL.get(prefs.get("channel"), "Pruebas internas"))
        self.status_var = ctk.StringVar(value="Listo para comprobar GitHub Releases.")
        self.version_var = ctk.StringVar(value=f"Versión instalada · {VERSION_LABEL}")
        self.asset_var = ctk.StringVar(value="Aún no se ha seleccionado una release.")
        self.progress_var = ctk.DoubleVar(value=0.0)
        self.progress_text_var = ctk.StringVar(value="")

        self._build()

    def _build(self):
        outer = ctk.CTkFrame(self.window, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=18, pady=18)

        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="Actualizaciones", font=(FONT, 22, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            head,
            text="Canal manual para probar nuevas versiones entre los desarrolladores sin actualizar nada en segundo plano.",
            font=(FONT, 10), text_color=TEXT_2, anchor="w", justify="left", wraplength=700,
        ).pack(anchor="w", pady=(3, 0))

        current = ctk.CTkFrame(outer, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        current.pack(fill="x", pady=(15, 10))
        row = ctk.CTkFrame(current, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=13)
        ctk.CTkLabel(row, textvariable=self.version_var, font=(FONT, 12, "bold"), text_color=TEXT).pack(side="left")
        self.mode_label = ctk.CTkLabel(
            row,
            text="Modo instalado" if is_frozen() else "Modo fuente · copia de prueba",
            font=(FONT, 9, "bold"), text_color=GREEN if is_frozen() else AMBER,
        )
        self.mode_label.pack(side="right")

        controls = ctk.CTkFrame(outer, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        controls.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(controls, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=14)
        ctk.CTkLabel(inner, text="Canal", font=(FONT, 9, "bold"), text_color=MUTED).grid(row=0, column=0, sticky="w")
        self.channel = ctk.CTkOptionMenu(
            inner, values=list(CHANNEL_LABELS), variable=self.channel_var, width=180, height=32,
            fg_color=CARD_2, button_color=theme_color("#16486d"), button_hover_color=theme_color("#1e628f"),
            text_color=TEXT, command=self._channel_changed,
        )
        self.channel.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.check_button = ctk.CTkButton(
            inner, text="Buscar actualizaciones", height=34, fg_color=BLUE, hover_color=theme_color("#168bc2"),
            text_color="#ffffff", font=(FONT, 10, "bold"), command=self.check,
        )
        self.check_button.grid(row=1, column=1, sticky="e", padx=(12, 0), pady=(4, 0))
        inner.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            controls,
            text="Pruebas internas incluye prereleases. Estable sólo considera releases finales.",
            font=(FONT, 8), text_color=MUTED, anchor="w",
        ).pack(fill="x", padx=15, pady=(0, 12))

        release = ctk.CTkFrame(outer, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
        release.pack(fill="both", expand=True, pady=(0, 10))
        ctk.CTkLabel(release, text="ESTADO DE LA RELEASE", font=(FONT, 8, "bold"), text_color=MUTED, anchor="w").pack(fill="x", padx=15, pady=(13, 3))
        self.status_label = ctk.CTkLabel(release, textvariable=self.status_var, font=(FONT, 12, "bold"), text_color=TEXT, anchor="w", justify="left", wraplength=680)
        self.status_label.pack(fill="x", padx=15)
        self.asset_label = ctk.CTkLabel(release, textvariable=self.asset_var, font=(FONT, 9), text_color=TEXT_2, anchor="w", justify="left", wraplength=680)
        self.asset_label.pack(fill="x", padx=15, pady=(4, 9))

        self.notes = ctk.CTkTextbox(release, height=130, fg_color=theme_color("#081421"), border_width=1, border_color=theme_color("#132b43"), text_color=TEXT_2, font=(FONT, 9), wrap="word")
        self.notes.pack(fill="both", expand=True, padx=15, pady=(0, 9))
        self.notes.insert("1.0", "Las notas de la release aparecerán aquí después de comprobar GitHub.")
        self.notes.configure(state="disabled")

        self.progress = ctk.CTkProgressBar(release, variable=self.progress_var, height=8, progress_color=BLUE, fg_color=theme_color("#132741"))
        self.progress.pack(fill="x", padx=15, pady=(0, 4))
        self.progress.set(0)
        ctk.CTkLabel(release, textvariable=self.progress_text_var, font=(FONT, 8), text_color=MUTED, anchor="w").pack(fill="x", padx=15, pady=(0, 12))

        actions = ctk.CTkFrame(outer, fg_color="transparent")
        actions.pack(fill="x")
        self.primary = ctk.CTkButton(actions, text="Descargar actualización", height=34, state="disabled", fg_color=BLUE, hover_color=theme_color("#168bc2"), font=(FONT, 10, "bold"), command=self.download_update)
        self.primary.pack(side="left")
        self.secondary = ctk.CTkButton(actions, text="Abrir carpeta", height=34, fg_color=CARD_2, hover_color=theme_color("#15314c"), border_width=1, border_color=BORDER, text_color=TEXT_2, command=self.open_folder)
        self.secondary.pack(side="left", padx=(8, 0))
        ctk.CTkButton(actions, text="Ver Releases", height=34, fg_color="transparent", hover_color=CARD_2, border_width=1, border_color=BORDER, text_color=TEXT_2, command=lambda: webbrowser.open(releases_web_url())).pack(side="left", padx=(8, 0))
        ctk.CTkButton(actions, text="Cerrar", height=34, fg_color="transparent", hover_color=CARD_2, text_color=TEXT_2, command=self.close).pack(side="right")

        if not is_frozen():
            ctk.CTkLabel(
                outer,
                text="Modo fuente: V118 nunca sobrescribe tu repositorio. Una release ZIP verificada se extrae en AppData y se abre como copia de prueba aislada.",
                font=(FONT, 8), text_color=AMBER, anchor="w", justify="left", wraplength=710,
            ).pack(fill="x", pady=(8, 0))

    def _channel_changed(self, _value=None):
        channel = CHANNEL_LABELS.get(self.channel_var.get(), CHANNEL_INTERNAL)
        save_preferences(channel=channel)
        self.result = self.asset = self.download = self.staged = None
        self.primary.configure(text="Descargar actualización", state="disabled", command=self.download_update)
        self.status_var.set("Canal cambiado. Pulsa Buscar actualizaciones.")
        self.asset_var.set("")
        self.progress_var.set(0.0)
        self.progress_text_var.set("")

    def _set_notes(self, text: str):
        try:
            self.notes.configure(state="normal")
            self.notes.delete("1.0", "end")
            self.notes.insert("1.0", text or "Sin notas publicadas para esta release.")
            self.notes.configure(state="disabled")
        except Exception:
            pass

    def _set_busy(self, busy: bool):
        self.busy = bool(busy)
        state = "disabled" if busy else "normal"
        try:
            self.check_button.configure(state=state)
            self.channel.configure(state=state)
        except Exception:
            pass

    def _call_ui(self, callback):
        try:
            self.window.after(0, callback)
        except Exception:
            pass

    def check(self):
        if self.busy:
            return
        self._set_busy(True)
        self.primary.configure(state="disabled")
        self.status_var.set("Consultando GitHub Releases…")
        self.asset_var.set("")
        self.progress_var.set(0.0)
        self.progress_text_var.set("")
        channel = CHANNEL_LABELS.get(self.channel_var.get(), CHANNEL_INTERNAL)
        save_preferences(channel=channel)

        def worker():
            try:
                result = check_for_update(channel)
                self._call_ui(lambda: self._finish_check(result))
            except Exception as exc:
                self._call_ui(lambda e=exc: self._fail("No se pudo comprobar la actualización", e))
        threading.Thread(target=worker, daemon=True, name="CorePulse-UpdateCheck").start()

    def _finish_check(self, result):
        self._set_busy(False)
        self.result = result
        release = result.get("latest")
        if release is None:
            self.status_var.set("No hay releases publicadas para este canal.")
            self.asset_var.set("Publica una release en GitHub para iniciar la prueba interna.")
            self._set_notes("")
            return
        asset = choose_asset(release)
        self.asset = asset
        channel_name = "prerelease/interna" if release.prerelease else "estable"
        self._set_notes(release.body)
        if result.get("available"):
            self.status_var.set(f"Nueva versión disponible · {release.tag} · {channel_name}")
            if asset is None:
                self.asset_var.set("La release existe, pero no contiene un asset compatible para este modo.")
                return
            verification = "SHA-256 publicado" if asset.sha256 else "sin digest SHA-256 publicado"
            self.asset_var.set(f"{asset.name} · {_fmt_bytes(asset.size)} · {verification}")
            self.primary.configure(text="Descargar actualización", state="normal", command=self.download_update)
        else:
            self.status_var.set(f"CorePulse está al día para este canal · última release {release.tag}")
            self.asset_var.set("No hay una versión superior a la instalada.")
            self.primary.configure(state="disabled")

    def _fail(self, title, exc):
        self._set_busy(False)
        message = str(exc) if isinstance(exc, UpdateError) else f"{type(exc).__name__}: {exc}"
        self.status_var.set(message)
        self.progress_text_var.set("")
        cp_error(self.window, "Actualizaciones", f"{title}.\n\n{message}")

    def download_update(self):
        if self.busy or self.asset is None or not self.result or not self.result.get("latest"):
            return
        self._set_busy(True)
        self.primary.configure(state="disabled")
        self.status_var.set("Descargando la actualización…")
        self.progress_var.set(0.0)
        self.progress_text_var.set("Preparando descarga")
        release = self.result["latest"]
        asset = self.asset

        def progress(done, total):
            def update():
                if total > 0:
                    self.progress_var.set(min(1.0, done / total))
                    self.progress_text_var.set(f"{_fmt_bytes(done)} / {_fmt_bytes(total)}")
                else:
                    self.progress_text_var.set(f"{_fmt_bytes(done)} descargados")
            self._call_ui(update)

        def worker():
            try:
                downloaded = download_asset(asset, release, progress=progress)
                self._call_ui(lambda: self._finish_download(downloaded))
            except Exception as exc:
                self._call_ui(lambda e=exc: self._fail("La descarga falló", e))
        threading.Thread(target=worker, daemon=True, name="CorePulse-UpdateDownload").start()

    def _finish_download(self, downloaded):
        self._set_busy(False)
        self.download = downloaded
        verified = bool(downloaded.get("verified"))
        self.progress_var.set(1.0)
        if not verified:
            self.status_var.set("Descarga completada, pero GitHub no publicó SHA-256 para este asset.")
            self.progress_text_var.set("CorePulse no instalará ni ejecutará automáticamente un asset sin verificación.")
            self.primary.configure(text="Descarga sin verificar", state="disabled")
            cp_warning(self.window, "Actualizaciones", "La release se descargó, pero el asset no incluye digest SHA-256. Para la prueba de actualización, vuelve a publicar el asset correctamente o usa una release cuyo asset exponga digest.")
            return

        self.progress_text_var.set(f"SHA-256 verificado · {str(downloaded.get('sha256') or '')[:16]}…")
        if is_frozen():
            self.status_var.set("Actualización descargada y verificada. El instalador está listo.")
            self.primary.configure(text="Abrir instalador", state="normal", command=self.install_update)
        else:
            self.status_var.set("Release descargada y verificada. Puedes preparar una copia aislada para probarla.")
            self.primary.configure(text="Preparar copia de prueba", state="normal", command=self.stage_source)

    def install_update(self):
        if not self.download:
            return
        try:
            launch_installer(self.download)
            cp_info(self.window, "Actualizaciones", "Se abrió el instalador verificado. CorePulse no fuerza el cierre: completa el asistente para probar la actualización.")
        except Exception as exc:
            self._fail("No se pudo abrir el instalador", exc)

    def stage_source(self):
        if self.busy or not self.download:
            return
        self._set_busy(True)
        self.status_var.set("Preparando una copia aislada en AppData…")

        def worker():
            try:
                staged = stage_source_release(self.download)
                self._call_ui(lambda: self._finish_stage(staged))
            except Exception as exc:
                self._call_ui(lambda e=exc: self._fail("No se pudo preparar la copia", e))
        threading.Thread(target=worker, daemon=True, name="CorePulse-UpdateStage").start()

    def _finish_stage(self, staged):
        self._set_busy(False)
        self.staged = staged
        self.status_var.set(f"Copia {staged.get('version') or ''} preparada sin modificar tu proyecto actual.")
        self.asset_var.set(f"Entrada: {staged.get('entry')}")
        self.primary.configure(text="Abrir copia de prueba", state="normal", command=self.launch_stage)

    def launch_stage(self):
        if not self.staged:
            return
        try:
            launch_staged_source(self.staged)
            cp_info(self.window, "Actualizaciones", "Se inició la copia descargada. La V118 actual permanece abierta para que puedas comparar ambas versiones.")
        except Exception as exc:
            self._fail("No se pudo abrir la copia de prueba", exc)

    def open_folder(self):
        try:
            open_updates_folder()
        except Exception as exc:
            self._fail("No se pudo abrir la carpeta", exc)

    def close(self):
        try:
            self.window.destroy()
        except Exception:
            pass
        try:
            if getattr(self.app, "_update_dialog", None) is self:
                self.app._update_dialog = None
        except Exception:
            pass


def show_update_dialog(app):
    existing = getattr(app, "_update_dialog", None)
    try:
        if existing is not None and existing.window.winfo_exists():
            existing.window.lift()
            existing.window.focus_force()
            return existing
    except Exception:
        pass
    dialog = UpdateDialog(app)
    app._update_dialog = dialog
    return dialog


__all__ = ["UpdateDialog", "show_update_dialog"]
