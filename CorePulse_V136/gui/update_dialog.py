"""Centro de actualizaciones y publicación segura de CorePulse V136.

Actualizaciones y Publicar versión viven dentro del mismo shell. La publicación
usa Git ya configurado, bloquea ramas principales y protege FASE 1/2/3.
"""
from __future__ import annotations

from datetime import datetime
import threading
import webbrowser
from tkinter import filedialog

import customtkinter as ctk

from core.runtime_paths import is_frozen
from core.theme_manager import role_color
from core.update_manager import (
    CHANNEL_INTERNAL, CHANNEL_STABLE, UpdateError, check_for_update, choose_asset,
    download_asset_verified, installation_mode, launch_installer,
    launch_source_update_helper, launch_staged_source, list_source_backups,
    load_preferences, open_updates_folder, prepare_source_rollback,
    prepare_source_update, releases_web_url, save_preferences,
    source_update_supported, stage_source_release,
)
from core.version import VERSION_LABEL
from core.developer_publisher import (
    PublishError, inspect_publish_context, publish_current_version, TARGET_FOLDER,
)
from gui.dialogs import error as cp_error, info as cp_info

FONT = "Segoe UI"

CHANNEL_LABELS = {"Desarrollo": CHANNEL_INTERNAL, "Estable": CHANNEL_STABLE}
LABEL_BY_CHANNEL = {value: key for key, value in CHANNEL_LABELS.items()}


def _c(role: str) -> str:
    return role_color(role)


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


def _fmt_date(value: str | None) -> str:
    if not value:
        return "N/A"
    try:
        raw = value.replace("Z", "+00:00")
        return datetime.fromisoformat(raw).astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)


class UpdatePanel:
    """Página interna de Actualizaciones, sin crear una segunda ventana."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.frame = ctk.CTkFrame(parent, fg_color=_c("bg"), corner_radius=0)
        self.frame.pack(fill="both", expand=True)

        self.result = None
        self.asset = None
        self.download = None
        self.staged = None
        self.busy = False
        self.mode = installation_mode()
        self._alive = True
        self._auto_check_started = False
        self.publish_frame = None
        self.publish_context = None

        prefs = load_preferences()
        self.channel_var = ctk.StringVar(value=LABEL_BY_CHANNEL.get(prefs.get("channel"), "Desarrollo"))
        self.status_var = ctk.StringVar(value="Preparando comprobación de actualizaciones…")
        self.version_var = ctk.StringVar(value=f"Versión instalada  {VERSION_LABEL}")
        self.release_var = ctk.StringVar(value="Versión disponible  —")
        self.meta_var = ctk.StringVar(value="Tamaño —  ·  Publicación —")
        self.progress_var = ctk.DoubleVar(value=0.0)
        self.progress_text_var = ctk.StringVar(value="")
        self.backup_var = ctk.StringVar(value="Sin copia de rollback creada en esta sesión.")
        self.publish_repo_hint = str(prefs.get("publish_repo") or "").strip()

        self._build()
        try:
            self.frame.after_idle(self.on_viewport_settled)
        except Exception:
            pass
        # Entrar a Actualizaciones ya expresa intención de consultar. La búsqueda
        # automática evita una pantalla aparentemente inerte y mantiene el botón
        # manual para reintentar/refrescar cuando el usuario quiera.
        try:
            self.frame.after(260, self._auto_check)
        except Exception:
            pass

    def widget(self):
        return self.frame

    def set_active(self, active: bool):
        self._alive = bool(active)

    def refresh(self):
        """Refresca roles visuales y conserva resultados de la sesión."""
        try:
            self.frame.configure(fg_color=_c("bg"))
        except Exception:
            pass

    def _build(self):
        # V131: layout por grid con un único tramo elástico (estado/changelog).
        # Así el pie de acciones nunca desaparece al restaurar una ventana más
        # baja y los controles mantienen tamaños mínimos legibles.
        outer = ctk.CTkFrame(self.frame, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=18, pady=13)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(3, weight=1)
        self._outer = outer

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        self._title_label = ctk.CTkLabel(
            header, text="Centro de actualizaciones", font=(FONT, 23, "bold"),
            text_color=_c("text"), anchor="w",
        )
        self._title_label.pack(fill="x")
        self._subtitle_label = ctk.CTkLabel(
            header,
            text="CorePulse comprueba, descarga y verifica la versión publicada sin clonar el repositorio. Todo ocurre dentro de esta misma ventana.",
            font=(FONT, 10), text_color=_c("text_2"), anchor="w", justify="left", wraplength=900,
        )
        self._subtitle_label.pack(fill="x", pady=(3, 0))

        summary = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        summary.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        grid = ctk.CTkFrame(summary, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=11)
        grid.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(grid, textvariable=self.version_var, font=(FONT, 12, "bold"), text_color=_c("text"), anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(grid, textvariable=self.release_var, font=(FONT, 12, "bold"), text_color=_c("accent"), anchor="w").grid(row=0, column=1, sticky="w", padx=(18, 0))
        mode_text = {
            "installed": "Instalación · paquete/instalador verificado",
            "source-git": "Desarrollo Git · tu rama nunca se sobrescribe",
            "source-portable": "Fuente portable · backup + actualización + rollback",
        }.get(self.mode, self.mode)
        ctk.CTkLabel(grid, text=mode_text, font=(FONT, 9), text_color=_c("muted"), anchor="w").grid(row=1, column=0, sticky="w", pady=(5, 0))
        ctk.CTkLabel(grid, textvariable=self.meta_var, font=(FONT, 9), text_color=_c("text_2"), anchor="w").grid(row=1, column=1, sticky="w", padx=(18, 0), pady=(5, 0))

        controls = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        row = ctk.CTkFrame(controls, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(11, 6))
        row.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(row, text="Canal", font=(FONT, 9, "bold"), text_color=_c("muted")).grid(row=0, column=0, sticky="w")
        self.channel = ctk.CTkOptionMenu(
            row, values=list(CHANNEL_LABELS), variable=self.channel_var, width=170, height=34,
            fg_color=_c("surface_2"), button_color=_c("accent_2"), button_hover_color=_c("accent"),
            dropdown_fg_color=_c("surface"), dropdown_hover_color=_c("surface_2"),
            text_color=_c("text"), command=self._channel_changed,
        )
        self.channel.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.check_button = ctk.CTkButton(
            row, text="Buscar actualizaciones", width=190, height=36,
            fg_color=_c("accent"), hover_color=_c("accent_2"), text_color=_c("text"),
            font=(FONT, 10, "bold"), command=self.check,
        )
        self.check_button.grid(row=0, column=3, sticky="e", padx=(12, 0))
        self._flow_label = ctk.CTkLabel(
            controls,
            text="1 · Buscar  →  2 · Descargar y verificar SHA-256  →  3 · Instalar / probar  →  4 · Rollback si corresponde",
            font=(FONT, 9, "bold"), text_color=_c("text_2"), anchor="w", justify="left", wraplength=980,
        )
        self._flow_label.pack(fill="x", padx=16, pady=(0, 3))
        ctk.CTkLabel(
            controls,
            text="Desarrollo incluye prereleases. Estable sólo usa releases finales publicadas.",
            font=(FONT, 8), text_color=_c("muted"), anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 9))

        release = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        release.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        release.grid_columnconfigure(0, weight=1)
        release.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(release, text="ESTADO", font=(FONT, 8, "bold"), text_color=_c("muted"), anchor="w").grid(row=0, column=0, sticky="ew", padx=16, pady=(11, 3))
        self._status_label = ctk.CTkLabel(
            release, textvariable=self.status_var, font=(FONT, 12, "bold"), text_color=_c("text"),
            anchor="w", justify="left", wraplength=900,
        )
        self._status_label.grid(row=1, column=0, sticky="ew", padx=16)
        self.notes = ctk.CTkTextbox(
            release, height=110, fg_color=_c("surface_2"), border_width=1, border_color=_c("border"),
            text_color=_c("text_2"), font=(FONT, 9), wrap="word",
        )
        self.notes.grid(row=2, column=0, sticky="nsew", padx=16, pady=(8, 8))
        self.notes.insert("1.0", "CorePulse comprobará automáticamente este canal. También puedes usar ‘Buscar actualizaciones’ para actualizar el estado manualmente.")
        self.notes.configure(state="disabled")

        self.progress = ctk.CTkProgressBar(release, variable=self.progress_var, height=9, progress_color=_c("accent"), fg_color=_c("border"))
        self.progress.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 3))
        self.progress.set(0)
        ctk.CTkLabel(release, textvariable=self.progress_text_var, font=(FONT, 8), text_color=_c("muted"), anchor="w").grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 9))

        safety = ctk.CTkFrame(outer, fg_color=_c("surface_2"), border_width=1, border_color=_c("border"), corner_radius=12)
        safety.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(safety, text="SEGURIDAD Y RECUPERACIÓN", font=(FONT, 8, "bold"), text_color=_c("muted"), anchor="w").pack(fill="x", padx=14, pady=(8, 2))
        self._backup_label = ctk.CTkLabel(
            safety, textvariable=self.backup_var, font=(FONT, 9), text_color=_c("text_2"),
            anchor="w", justify="left", wraplength=900,
        )
        self._backup_label.pack(fill="x", padx=14, pady=(0, 7))
        if self.mode == "source-portable":
            backups = list_source_backups()
            if backups:
                self.backup_var.set(f"Rollback disponible · {backups[0]['name']} · {_fmt_bytes(backups[0]['size'])}")
        elif self.mode == "source-git":
            self.backup_var.set("Checkout Git detectado: CorePulse no reemplazará archivos de tu rama. Una versión nueva se abrirá en una copia aislada para probarla.")
        else:
            self.backup_var.set("Modo instalado: CorePulse verificará el instalador antes de abrirlo. El rollback de instalación depende del paquete publicado.")

        actions = ctk.CTkFrame(outer, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew")
        actions.grid_columnconfigure(5, weight=1)
        self.primary = ctk.CTkButton(
            actions, text="Descargar actualización", width=165, height=36, state="disabled",
            fg_color=_c("accent"), hover_color=_c("accent_2"), text_color=_c("text"),
            font=(FONT, 10, "bold"), command=self.download_update,
        )
        self.primary.grid(row=0, column=0, sticky="w")
        self.rollback = ctk.CTkButton(
            actions, text="Rollback", width=110, height=36,
            fg_color=_c("surface_2"), hover_color=_c("surface"), border_width=1, border_color=_c("border"),
            text_color=_c("text_2"), command=self.rollback_latest,
        )
        self.rollback.grid(row=0, column=1, sticky="w", padx=(8, 0))
        if self.mode != "source-portable" or not list_source_backups():
            self.rollback.configure(state="disabled")
        ctk.CTkButton(actions, text="Carpeta", width=100, height=36, fg_color="transparent", hover_color=_c("surface_2"), border_width=1, border_color=_c("border"), text_color=_c("text_2"), command=self.open_folder).grid(row=0, column=2, sticky="w", padx=(8, 0))
        ctk.CTkButton(actions, text="Releases", width=100, height=36, fg_color="transparent", hover_color=_c("surface_2"), border_width=1, border_color=_c("border"), text_color=_c("text_2"), command=lambda: webbrowser.open(releases_web_url())).grid(row=0, column=3, sticky="w", padx=(8, 0))
        self.publish_button = ctk.CTkButton(
            actions, text="Publicar", width=105, height=36, fg_color="transparent",
            hover_color=_c("surface_2"), border_width=1, border_color=_c("border"),
            text_color=_c("text_2"), command=self.open_publish_view,
        )
        self.publish_button.grid(row=0, column=4, sticky="w", padx=(8, 0))
        ctk.CTkButton(actions, text="Volver al resumen", width=130, height=36, fg_color="transparent", hover_color=_c("surface_2"), text_color=_c("text_2"), command=self.close).grid(row=0, column=6, sticky="e")

        self.on_viewport_settled()

    def on_viewport_settled(self):
        """Ajusta densidad sin reducir controles por debajo de tamaños legibles."""
        try:
            width = max(1, int(self.frame.winfo_width()))
            height = max(1, int(self.frame.winfo_height()))
        except Exception:
            return
        compact = height < 760 or width < 940
        try:
            self._outer.pack_configure(padx=12 if compact else 18, pady=9 if compact else 13)
            self._title_label.configure(font=(FONT, 20 if compact else 23, "bold"))
            wrap = max(560, width - (90 if compact else 120))
            self._subtitle_label.configure(wraplength=wrap)
            self._flow_label.configure(wraplength=wrap)
            self._status_label.configure(wraplength=wrap)
            self._backup_label.configure(wraplength=wrap)
            self.notes.configure(height=82 if compact else 110)
        except Exception:
            pass

    def _auto_check(self):
        if self._auto_check_started or not self._alive:
            return
        self._auto_check_started = True
        self.check()

    def _channel_changed(self, _value=None):
        channel = CHANNEL_LABELS.get(self.channel_var.get(), CHANNEL_INTERNAL)
        save_preferences(channel=channel)
        self.result = self.asset = self.download = self.staged = None
        self.primary.configure(text="Descargar actualización", state="disabled", command=self.download_update)
        self.status_var.set("Canal cambiado. Comprobando versiones publicadas…")
        self.release_var.set("Versión disponible  —")
        self.meta_var.set("Tamaño —  ·  Publicación —")
        self._set_notes("Comprobando el canal seleccionado…")
        self.progress_var.set(0.0)
        self.progress_text_var.set("")
        # El cambio de canal también refresca automáticamente; el botón manual
        # sigue disponible para repetir la consulta.
        try:
            self.frame.after(80, self.check)
        except Exception:
            pass

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
            if self._alive:
                self.frame.after(0, callback)
        except Exception:
            pass

    def check(self):
        if self.busy or not self._alive:
            return
        self._set_busy(True)
        self.primary.configure(state="disabled")
        self.status_var.set("Consultando GitHub Releases…")
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
            channel_name = self.channel_var.get()
            self.status_var.set(f"No hay versiones publicadas en el canal {channel_name}.")
            self.release_var.set("Versión disponible  —")
            self.meta_var.set("Sin release publicada · no hay nada que descargar")
            self._set_notes("Esto no es un fallo de CorePulse. Este canal todavía no tiene una GitHub Release compatible publicada. Puedes volver a comprobar cuando exista una nueva versión.")
            self.primary.configure(text="Descargar actualización", state="disabled", command=self.download_update)
            return
        self.asset = choose_asset(release)
        self.release_var.set(f"Versión disponible  {release.tag}")
        size = _fmt_bytes(self.asset.size) if self.asset else "sin paquete compatible"
        self.meta_var.set(f"Tamaño {size}  ·  Publicación {_fmt_date(release.published_at)}")
        self._set_notes(release.body)
        channel_name = "desarrollo" if release.prerelease else "estable"
        if result.get("available"):
            self.status_var.set(f"Nueva versión disponible · {release.tag} · canal {channel_name}")
            if self.asset is None:
                self.status_var.set("La release existe, pero no contiene un ZIP/instalador compatible.")
                self.primary.configure(state="disabled")
                return
            self.primary.configure(text="Descargar y verificar", state="normal", command=self.download_update)
        else:
            self.status_var.set(f"CorePulse está al día · última versión del canal {release.tag}")
            self.primary.configure(state="disabled")

    def _fail(self, title, exc):
        self._set_busy(False)
        message = str(exc) if isinstance(exc, UpdateError) else f"{type(exc).__name__}: {exc}"
        self.status_var.set(message)
        self.progress_text_var.set("")
        cp_error(self.app, "Actualizaciones", f"{title}.\n\n{message}")

    def download_update(self):
        if self.busy or self.asset is None or not self.result or not self.result.get("latest"):
            return
        self._set_busy(True)
        self.primary.configure(state="disabled")
        self.status_var.set("Descargando únicamente el paquete de actualización…")
        self.progress_var.set(0.0)
        self.progress_text_var.set("Buscando SHA-256 publicado")
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
                downloaded = download_asset_verified(asset, release, progress=progress)
                self._call_ui(lambda: self._finish_download(downloaded))
            except Exception as exc:
                self._call_ui(lambda e=exc: self._fail("La descarga falló", e))
        threading.Thread(target=worker, daemon=True, name="CorePulse-UpdateDownload").start()

    def _finish_download(self, downloaded):
        self._set_busy(False)
        self.download = downloaded
        self.progress_var.set(1.0)
        source = downloaded.get("checksum_source") or "SHA-256"
        self.progress_text_var.set(f"Integridad verificada · {source} · {str(downloaded.get('sha256') or '')[:16]}…")
        if is_frozen():
            self.status_var.set("Paquete descargado y verificado. Listo para abrir el instalador.")
            self.primary.configure(text="Instalar actualización", state="normal", command=self.install_update)
        elif self.mode == "source-git":
            self.status_var.set("Paquete verificado. Tu checkout Git no será modificado.")
            self.primary.configure(text="Preparar copia de prueba", state="normal", command=self.stage_source)
        elif source_update_supported():
            self.status_var.set("Paquete verificado. Se creará backup antes de reemplazar esta copia.")
            self.primary.configure(text="Actualizar y reiniciar", state="normal", command=self.apply_source_update)
        else:
            self.primary.configure(state="disabled")

    def install_update(self):
        if not self.download:
            return
        try:
            launch_installer(self.download)
            cp_info(self.app, "Actualizaciones", "El instalador verificado fue abierto. CorePulse no ejecutó ningún paquete sin comprobar su SHA-256.")
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
        self.status_var.set(f"Copia {staged.get('version') or ''} preparada sin modificar tu rama.")
        self.primary.configure(text="Abrir copia de prueba", state="normal", command=self.launch_stage)

    def launch_stage(self):
        if not self.staged:
            return
        try:
            launch_staged_source(self.staged)
            cp_info(self.app, "Actualizaciones", "Se inició la copia descargada en paralelo. Tu proyecto Git permanece intacto.")
        except Exception as exc:
            self._fail("No se pudo abrir la copia", exc)

    def apply_source_update(self):
        if self.busy or not self.download:
            return
        self._set_busy(True)
        self.primary.configure(state="disabled")
        self.status_var.set("Creando backup y preparando actualización…")

        def worker():
            try:
                plan = prepare_source_update(self.download)
                self._call_ui(lambda: self._finish_apply_plan(plan))
            except Exception as exc:
                self._call_ui(lambda e=exc: self._fail("No se pudo preparar la actualización", e))
        threading.Thread(target=worker, daemon=True, name="CorePulse-UpdatePrepare").start()

    def _finish_apply_plan(self, plan):
        self._set_busy(False)
        backup = plan.get("backup_zip") or ""
        self.backup_var.set(f"Backup creado · {backup}")
        self.status_var.set("Backup listo. CorePulse se cerrará, aplicará la actualización y volverá a abrirse.")
        try:
            launch_source_update_helper(plan)
            self.frame.after(350, self._close_app_for_update)
        except Exception as exc:
            self._fail("No se pudo iniciar el aplicador", exc)

    def _close_app_for_update(self):
        try:
            close_fn = getattr(self.app, "on_close", None)
            if callable(close_fn):
                close_fn()
            else:
                self.app.destroy()
        except Exception:
            try:
                self.app.destroy()
            except Exception:
                pass

    def rollback_latest(self):
        if self.busy or self.mode != "source-portable":
            return
        try:
            plan = prepare_source_rollback()
            launch_source_update_helper(plan)
            self.status_var.set("Rollback preparado. CorePulse se cerrará y restaurará la copia anterior.")
            self.frame.after(350, self._close_app_for_update)
        except Exception as exc:
            self._fail("No se pudo preparar el rollback", exc)

    def open_publish_view(self):
        """Abre el flujo de publicación dentro de la misma ventana."""
        try:
            self._outer.pack_forget()
        except Exception:
            pass
        if self.publish_frame is None or not self.publish_frame.winfo_exists():
            self._build_publish_view()
        self.publish_frame.pack(fill="both", expand=True)
        self.refresh_publish_context()

    def _build_publish_view(self):
        self.publish_frame = ctk.CTkFrame(self.frame, fg_color=_c("bg"), corner_radius=0)
        outer = ctk.CTkFrame(self.publish_frame, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=18, pady=13)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header, text="Publicar versión", font=(FONT, 23, "bold"),
            text_color=_c("text"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header, text="Volver a actualizaciones", width=150, height=34,
            fg_color="transparent", hover_color=_c("surface_2"),
            border_width=1, border_color=_c("border"), text_color=_c("text_2"),
            command=self.close_publish_view,
        ).grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            header,
            text="Sube CorePulse a tu rama usando Git ya configurado. FASE 1, FASE 2 y FASE 3 quedan fuera del commit.",
            font=(FONT, 10), text_color=_c("text_2"), anchor="w", justify="left", wraplength=980,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))

        repo_card = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        repo_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        repo_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(repo_card, text="REPOSITORIO", font=(FONT, 8, "bold"), text_color=_c("muted")).grid(row=0, column=0, sticky="w", padx=16, pady=(11, 2))
        self.publish_repo_var = ctk.StringVar(value=self.publish_repo_hint or "No detectado")
        self.publish_branch_var = ctk.StringVar(value="Rama —")
        self.publish_target_var = ctk.StringVar(value=f"Destino {TARGET_FOLDER}")
        self.publish_protected_var = ctk.StringVar(value="FASE 1 — · FASE 2 — · FASE 3 —")
        ctk.CTkLabel(repo_card, textvariable=self.publish_repo_var, font=(FONT, 10, "bold"), text_color=_c("text"), anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew", padx=16)
        ctk.CTkLabel(repo_card, textvariable=self.publish_branch_var, font=(FONT, 9), text_color=_c("text_2"), anchor="w").grid(row=2, column=0, sticky="w", padx=16, pady=(5, 0))
        ctk.CTkLabel(repo_card, textvariable=self.publish_target_var, font=(FONT, 9), text_color=_c("text_2"), anchor="w").grid(row=2, column=1, sticky="w", padx=(10, 16), pady=(5, 0))
        ctk.CTkLabel(repo_card, textvariable=self.publish_protected_var, font=(FONT, 9, "bold"), text_color=_c("ok"), anchor="w").grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(5, 9))
        buttons = ctk.CTkFrame(repo_card, fg_color="transparent")
        buttons.grid(row=0, column=2, rowspan=4, sticky="e", padx=16)
        ctk.CTkButton(
            buttons, text="Seleccionar repo", width=125, height=32,
            fg_color=_c("surface_2"), hover_color=_c("accent_2"), text_color=_c("text"),
            command=self.select_publish_repo,
        ).pack(pady=(0, 5))
        self.review_publish_button = ctk.CTkButton(
            buttons, text="Revisar", width=125, height=30,
            fg_color="transparent", hover_color=_c("surface_2"), border_width=1,
            border_color=_c("border"), text_color=_c("text_2"),
            command=lambda: self.refresh_publish_context(manual=True),
        )
        self.review_publish_button.pack()

        commit_card = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        commit_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(commit_card, text="MENSAJE DEL COMMIT", font=(FONT, 8, "bold"), text_color=_c("muted"), anchor="w").pack(fill="x", padx=16, pady=(11, 4))
        self.commit_text = ctk.CTkTextbox(
            commit_card, height=78, fg_color=_c("surface_2"), border_width=1, border_color=_c("border"),
            text_color=_c("text"), font=(FONT, 10), wrap="word",
        )
        self.commit_text.pack(fill="x", padx=16, pady=(0, 11))
        self.commit_text.insert("1.0", f"CorePulse {VERSION_LABEL} - publicación desde CorePulse")

        status_card = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        status_card.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        status_card.grid_columnconfigure(0, weight=1)
        status_card.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(status_card, text="VISTA PREVIA / REGISTRO", font=(FONT, 8, "bold"), text_color=_c("muted"), anchor="w").grid(row=0, column=0, sticky="ew", padx=16, pady=(11, 3))
        self.publish_status_var = ctk.StringVar(value="Selecciona o revisa el repositorio antes de publicar.")
        ctk.CTkLabel(status_card, textvariable=self.publish_status_var, font=(FONT, 11, "bold"), text_color=_c("text"), anchor="w", justify="left", wraplength=980).grid(row=1, column=0, sticky="ew", padx=16)
        self.publish_log = ctk.CTkTextbox(
            status_card, height=150, fg_color=_c("surface_2"), border_width=1, border_color=_c("border"),
            text_color=_c("text_2"), font=(FONT, 9), wrap="word",
        )
        self.publish_log.grid(row=2, column=0, sticky="nsew", padx=16, pady=(8, 11))
        self.publish_log.configure(state="disabled")

        actions = ctk.CTkFrame(outer, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew")
        actions.grid_columnconfigure(1, weight=1)
        self.do_publish_button = ctk.CTkButton(
            actions, text="Publicar en mi rama", width=180, height=38, state="disabled",
            fg_color=_c("accent"), hover_color=_c("accent_2"), text_color=_c("text"),
            font=(FONT, 10, "bold"), command=self.publish_now,
        )
        self.do_publish_button.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            actions, text="Nunca publica directamente sobre main. Usa tus credenciales Git existentes.",
            font=(FONT, 8), text_color=_c("muted"), anchor="e",
        ).grid(row=0, column=2, sticky="e")

    def close_publish_view(self):
        try:
            if self.publish_frame is not None:
                self.publish_frame.pack_forget()
            self._outer.pack(fill="both", expand=True, padx=18, pady=13)
            self.on_viewport_settled()
        except Exception:
            pass

    def _set_publish_log(self, text: str, *, append: bool = False):
        try:
            self.publish_log.configure(state="normal")
            if not append:
                self.publish_log.delete("1.0", "end")
            self.publish_log.insert("end", ("\n" if append and self.publish_log.get("1.0", "end").strip() else "") + str(text))
            self.publish_log.see("end")
            self.publish_log.configure(state="disabled")
        except Exception:
            pass

    def select_publish_repo(self):
        initial = self.publish_repo_hint or None
        try:
            chosen = filedialog.askdirectory(parent=self.app, title="Seleccionar repositorio DiagnosticPC", initialdir=initial)
        except Exception:
            chosen = filedialog.askdirectory(title="Seleccionar repositorio DiagnosticPC")
        if not chosen:
            return
        self.publish_repo_hint = chosen
        save_preferences(publish_repo=chosen)
        self.refresh_publish_context(manual=True)

    def refresh_publish_context(self, manual: bool = False):
        if self.publish_frame is None:
            return
        checked_at = datetime.now().strftime("%H:%M:%S")
        if manual:
            try:
                self.review_publish_button.configure(text="Revisando…", state="disabled")
            except Exception:
                pass
            self.publish_status_var.set(f"Revisando repositorio · {checked_at}")
            try:
                self.frame.update_idletasks()
            except Exception:
                pass

        hint = self.publish_repo_hint or None
        try:
            ctx = inspect_publish_context(hint)
        except Exception as exc:
            ctx = {"available": False, "can_publish": False, "blockers": [str(exc)]}

        # Si V136 encontró de forma inequívoca un clon Git cercano, adoptamos la
        # raíz canónica y la recordamos. Así no se vuelve a mostrar la carpeta ZIP
        # que el usuario había seleccionado por error.
        resolved_root = str(ctx.get("repo_root") or "").strip()
        if resolved_root and resolved_root != self.publish_repo_hint:
            self.publish_repo_hint = resolved_root
            save_preferences(publish_repo=resolved_root)

        self.publish_context = ctx
        root = str(ctx.get("repo_root") or self.publish_repo_hint or "No detectado")
        self.publish_repo_var.set(root)
        self.publish_branch_var.set(f"Rama  {ctx.get('branch') or '—'}")
        self.publish_target_var.set(f"Destino  {ctx.get('target_folder') or TARGET_FOLDER}")
        protected = ctx.get("protected") or {}
        parts = []
        for name in ("FASE 1", "FASE 2", "FASE 3"):
            parts.append(f"{'✓' if protected.get(name) else '✕'} {name}")
        self.publish_protected_var.set("   ·   ".join(parts))

        blockers = list(ctx.get("blockers") or [])
        note = str(ctx.get("resolution_note") or "").strip()
        candidates = list(ctx.get("nearby_candidates") or [])
        prefix = f"Revisión {checked_at}" if manual else "Comprobación"
        if ctx.get("can_publish"):
            old = ", ".join(ctx.get("tracked_corepulse") or []) or "ninguna"
            auto = " · clon Git detectado automáticamente" if ctx.get("auto_detected") else ""
            self.publish_status_var.set(
                f"{prefix}{auto} · listo para publicar {VERSION_LABEL} en {ctx.get('branch')}. "
                f"CorePulse anterior: {old}."
            )
            lines = []
            if note:
                lines.append(note)
            lines.extend([
                f"Repositorio Git: {root}",
                f"Rama: {ctx.get('branch') or 'N/A'}",
                f"Remoto: {ctx.get('remote') or 'N/A'}",
                f"Se reemplazará únicamente la carpeta CorePulse versionada por {TARGET_FOLDER}.",
                "FASE 1, FASE 2 y FASE 3 no se prepararán ni se incluirán en el commit.",
            ])
            self._set_publish_log("\n".join(lines))
            self.do_publish_button.configure(state="normal")
        else:
            self.publish_status_var.set(f"{prefix} · publicación bloqueada hasta resolver las comprobaciones de seguridad.")
            lines = []
            if note:
                lines.append(f"• {note}")
            lines.extend(f"• {item}" for item in blockers)
            if candidates:
                lines.append("\nRepositorios Git cercanos detectados:")
                lines.extend(f"  - {item}" for item in candidates[:6])
            if not lines:
                lines.append("No se detectó un repositorio Git compatible.")
            self._set_publish_log("\n".join(lines))
            self.do_publish_button.configure(state="disabled")

        if manual:
            try:
                self.review_publish_button.configure(text="Revisar", state="normal")
            except Exception:
                pass

    def publish_now(self):
        if self.busy or not self.publish_context or not self.publish_context.get("can_publish"):
            return
        message = self.commit_text.get("1.0", "end").strip()
        if not message:
            cp_error(self.app, "Publicar versión", "Escribe un mensaje de commit antes de publicar.")
            return
        repo = self.publish_context.get("repo_root") or self.publish_repo_hint
        if not repo:
            return
        self._set_busy(True)
        self.do_publish_button.configure(state="disabled")
        self.publish_status_var.set("Publicando versión…")
        self._set_publish_log("Iniciando publicación segura…")

        def note(text):
            self._call_ui(lambda t=text: self._set_publish_log(t, append=True))

        def worker():
            try:
                result = publish_current_version(repo, message, progress=note)
                self._call_ui(lambda r=result: self._finish_publish(r))
            except Exception as exc:
                self._call_ui(lambda e=exc: self._fail_publish(e))
        threading.Thread(target=worker, daemon=True, name="CorePulse-GitPublish").start()

    def _finish_publish(self, result):
        self._set_busy(False)
        self.publish_status_var.set(f"Publicado correctamente · commit {result.get('commit')} · rama {result.get('branch')}")
        assets = result.get("release_assets") or {}
        self._set_publish_log(
            f"Push completado.\nZIP para Release: {assets.get('zip') or 'N/A'}\n"
            f"SHA-256: {assets.get('sha256') or 'N/A'}",
            append=True,
        )
        if result.get("source_old_left_local"):
            self._set_publish_log(
                "La versión anterior quedó sólo como carpeta local porque CorePulse se estaba ejecutando desde ella. "
                "En GitHub ya fue retirada del commit; puedes borrar esa carpeta local después de cerrar CorePulse.",
                append=True,
            )
        cp_info(
            self.app, "Publicación completada",
            f"{result.get('target_folder')} se subió a {result.get('branch')} sin incluir FASE 1, FASE 2 ni FASE 3.\n\nCommit: {result.get('commit')}"
        )
        self.refresh_publish_context()

    def _fail_publish(self, exc):
        self._set_busy(False)
        message = str(exc) if isinstance(exc, (PublishError, UpdateError)) else f"{type(exc).__name__}: {exc}"
        self.publish_status_var.set("No se pudo completar la publicación.")
        self._set_publish_log(message, append=True)
        try:
            self.do_publish_button.configure(state="normal" if self.publish_context and self.publish_context.get("can_publish") else "disabled")
        except Exception:
            pass
        cp_error(self.app, "Publicar versión", message)

    def open_folder(self):
        try:
            open_updates_folder()
        except Exception as exc:
            self._fail("No se pudo abrir la carpeta", exc)

    def close(self):
        try:
            from gui.internal_navigation import show_dashboard
            show_dashboard(self.app)
        except Exception:
            pass


# Alias de compatibilidad: ya no representa una ventana independiente.
UpdateDialog = UpdatePanel


def show_update_dialog(app):
    """Compatibilidad con V118/V129: redirige a la página interna."""
    opener = getattr(app, "open_update_center", None)
    if callable(opener):
        return opener()
    return None


__all__ = ["UpdatePanel", "UpdateDialog", "show_update_dialog"]
