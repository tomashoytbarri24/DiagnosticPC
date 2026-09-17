"""Centro de actualizaciones y publicación segura de CorePulse.

Actualizaciones y Publicar versión viven dentro del mismo shell. La publicación
usa perfiles Git locales, bloquea ramas principales y publica sólo cambios detectados.
"""
from __future__ import annotations

from datetime import datetime
import threading
import time
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
    source_update_supported, stage_source_release, read_last_update_status,
)
from core.version import VERSION_LABEL
from core.developer_publisher import (
    PublishError, inspect_profile_publish_context, publish_profile_root,
)
from core.publication_profiles import (
    PublicationProfileError, activate_profile_branch, configure_git_repository,
    delete_publication_profile, inspect_git_repository, load_publication_profiles,
    refresh_git_remote, save_publication_profile, set_active_publication_profile,
)
from gui.dialogs import error as cp_error, info as cp_info, ask_yes_no as cp_ask_yes_no

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
        self._visible = True
        self._download_cancel = threading.Event()
        self._auto_check_started = False
        self.publish_frame = None
        self.publish_context = None

        prefs = load_preferences()
        self.channel_var = ctk.StringVar(value=LABEL_BY_CHANNEL.get(prefs.get("channel"), "Estable"))
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
        # La página cacheada sigue viva: terminar un worker oculto debe liberar
        # busy y conservar su resultado para cuando el usuario vuelva.
        self._visible = bool(active)

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
        outer.grid_rowconfigure(3, weight=0)
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
            text="Desarrollo usa prereleases automáticas de */corepulse-dev. Estable sólo usa releases finales publicadas.",
            font=(FONT, 8), text_color=_c("muted"), anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 9))

        release = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        release.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        release.grid_columnconfigure(0, weight=1)
        release.grid_rowconfigure(2, weight=0)
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
        self._safety_card = safety
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
        actions.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self._update_actions = actions
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

        previous = read_last_update_status()
        if isinstance(previous, dict):
            if previous.get('ok'):
                self.backup_var.set('Última operación aplicada. Versión en ejecución: ' + VERSION_LABEL)
            else:
                self.backup_var.set('Última actualización no completada: ' + str(previous.get('error') or 'Revisa la copia de seguridad.'))
        self.on_viewport_settled()

    def on_viewport_settled(self):
        """Ajusta densidad sin reducir controles por debajo de tamaños legibles."""
        try:
            if self.publish_frame is not None and self.publish_frame.winfo_exists() and self.publish_frame.winfo_ismapped():
                self._apply_publish_density()
                return
        except Exception:
            pass
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
            self.notes.configure(height=72 if compact else 96)
            try:
                self._safety_card.grid_configure(pady=(0, 6 if compact else 8))
            except Exception:
                pass
        except Exception:
            pass

    def _auto_check(self):
        if self._auto_check_started or not self._alive:
            return
        self._auto_check_started = True
        self.check()

    def _channel_changed(self, _value=None):
        channel = CHANNEL_LABELS.get(self.channel_var.get(), CHANNEL_STABLE)
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
        self._download_cancel.clear()
        self.status_var.set("Consultando GitHub Releases…")
        self.progress_var.set(0.0)
        self.progress_text_var.set("")
        channel = CHANNEL_LABELS.get(self.channel_var.get(), CHANNEL_STABLE)
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
        self.asset = self.download = self.staged = None
        self.primary.configure(text='Descargar actualización', state='disabled', command=self.download_update)
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
        self.download = self.staged = None
        self.primary.configure(text='Reintentar descarga', command=self.download_update,
                               state='normal' if self.asset and self.result and self.result.get('available') else 'disabled')
        if self._visible and not self._download_cancel.is_set():
            cp_error(self.app, "Actualizaciones", f"{title}.\n\n{message}")

    def download_update(self):
        if self.busy or self.asset is None or not self.result or not self.result.get("latest"):
            return
        self._set_busy(True)
        self.primary.configure(state="disabled")
        self._download_cancel.clear()
        self.primary.configure(text='Cancelar descarga', state='normal', command=self.cancel_download)
        self.status_var.set("Descargando únicamente el paquete de actualización…")
        self.progress_var.set(0.0)
        self.progress_text_var.set("Buscando SHA-256 publicado")
        release = self.result["latest"]
        asset = self.asset

        last_progress = [0.0]
        def progress(done, total):
            now = time.monotonic()
            if now - last_progress[0] < .1 and (not total or done < total):
                return
            last_progress[0] = now
            def update():
                if total > 0:
                    self.progress_var.set(min(1.0, done / total))
                    self.progress_text_var.set(f"{_fmt_bytes(done)} / {_fmt_bytes(total)}")
                else:
                    self.progress_text_var.set(f"{_fmt_bytes(done)} descargados")
            self._call_ui(update)

        def worker():
            try:
                downloaded = download_asset_verified(asset, release, progress=progress, cancel=self._download_cancel)
                self._call_ui(lambda: self._finish_download(downloaded))
            except Exception as exc:
                self._call_ui(lambda e=exc: self._fail("La descarga falló", e))
        threading.Thread(target=worker, daemon=True, name="CorePulse-UpdateDownload").start()

    def cancel_download(self):
        self._download_cancel.set()
        self.primary.configure(state='disabled')
        self.status_var.set('Cancelando descarga…')

    def _finish_download(self, downloaded):
        if self._download_cancel.is_set():
            self._fail('Descarga', UpdateError('Descarga cancelada. Puedes volver a intentarlo.'))
            return
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
            self.status_var.set('Instalador verificado abierto. CorePulse se cerrará para permitir la actualización.')
            self.primary.configure(state='disabled')
            self.frame.after(350, self._close_app_for_update)
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
        self._apply_publish_density()
        self.refresh_publish_context()

    def _build_publish_view(self):
        self.publish_frame = ctk.CTkFrame(self.frame, fg_color=_c("bg"), corner_radius=0)
        outer = ctk.CTkScrollableFrame(self.publish_frame, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=18, pady=13)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(5, weight=1)
        self._publish_outer = outer

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        header.grid_columnconfigure(0, weight=1)
        self._publish_title_label = ctk.CTkLabel(
            header, text="Publicar con perfil", font=(FONT, 23, "bold"),
            text_color=_c("text"), anchor="w",
        )
        self._publish_title_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header, text="Volver a actualizaciones", width=150, height=34,
            fg_color="transparent", hover_color=_c("surface_2"),
            border_width=1, border_color=_c("border"), text_color=_c("text_2"),
            command=self.close_publish_view,
        ).grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            header,
            text=("Selecciona un perfil y publica la raíz completa del clon. Git detecta sólo lo que cambió y respeta .gitignore. "
                  "Los perfiles guardan configuración; las credenciales siguen en Git Credential Manager/SSH."),
            font=(FONT, 10), text_color=_c("text_2"), anchor="w", justify="left", wraplength=1050,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 0))

        profile_card = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1,
                                    border_color=_c("border"), corner_radius=12)
        profile_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        profile_card.grid_columnconfigure(1, weight=1)
        profile_card.grid_columnconfigure(2, weight=0)
        ctk.CTkLabel(profile_card, text="PERFIL DE PUBLICACIÓN", font=(FONT, 9, "bold"),
                     text_color=_c("muted"), anchor="w").grid(row=0, column=0, columnspan=3, sticky="ew", padx=14, pady=(10, 6))

        top = ctk.CTkFrame(profile_card, fg_color="transparent")
        top.grid(row=1, column=0, columnspan=3, sticky="ew", padx=14, pady=(0, 8))
        top.grid_columnconfigure(0, weight=1)
        self.publish_profile_var = ctk.StringVar(value="Sin perfiles guardados")
        self.publish_profile_combo = ctk.CTkComboBox(
            top, values=["Sin perfiles guardados"], variable=self.publish_profile_var,
            width=250, height=30, state="readonly", command=self._on_publish_profile_selected,
        )
        self.publish_profile_combo.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Crear perfil", width=96, height=30, command=self.new_publish_profile).grid(row=0, column=1, padx=(8, 0))
        self.edit_publish_profile_button = ctk.CTkButton(top, text="Editar perfil", width=96, height=30, command=self.edit_publish_profile)
        self.edit_publish_profile_button.grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(top, text="Eliminar", width=82, height=30, fg_color="transparent",
                      border_width=1, border_color=_c("border"), text_color=_c("text_2"),
                      command=self.delete_publish_profile).grid(row=0, column=3, padx=(8, 0))

        self.publish_profile_name_var = ctk.StringVar(value="")
        self.publish_repo_var = ctk.StringVar(value="")
        self.publish_remote_var = ctk.StringVar(value="")
        self.publish_branch_var = ctk.StringVar(value="")
        self.publish_git_name_var = ctk.StringVar(value="")
        self.publish_git_email_var = ctk.StringVar(value="")
        self._publish_profile_id = ""
        self._publish_profile_map = {}
        self._publish_editor_widgets = []
        self._publish_editor_visible = False

        def field(row, label_text, variable, *, browse=None):
            label = ctk.CTkLabel(profile_card, text=label_text, font=(FONT, 9), text_color=_c("text_2"), anchor="w")
            label.grid(row=row, column=0, sticky="w", padx=(14, 10), pady=4)
            entry = ctk.CTkEntry(profile_card, textvariable=variable, height=30,
                                 fg_color=_c("surface_2"), border_color=_c("border"),
                                 text_color=_c("text"), font=(FONT, 10))
            entry.grid(row=row, column=1, sticky="ew", pady=4)
            self._publish_editor_widgets.extend([label, entry])
            if browse:
                button = ctk.CTkButton(profile_card, text=browse[0], width=browse[1], height=30, command=browse[2])
                button.grid(row=row, column=2, sticky="e", padx=(8, 14), pady=4)
                self._publish_editor_widgets.append(button)
            else:
                spacer = ctk.CTkFrame(profile_card, fg_color="transparent", width=8, height=1)
                spacer.grid(row=row, column=2, padx=(0, 14))
                self._publish_editor_widgets.append(spacer)
            return entry

        self.publish_name_entry = field(2, "Nombre del perfil", self.publish_profile_name_var)
        self.publish_repo_entry = field(3, "Carpeta raíz / clon", self.publish_repo_var,
                                        browse=("Detectar Git", 112, self.select_publish_repo))
        self.publish_remote_entry = field(4, "Repositorio GitHub / origin", self.publish_remote_var)

        branch_label = ctk.CTkLabel(profile_card, text="Rama", font=(FONT, 9), text_color=_c("text_2"), anchor="w")
        branch_label.grid(row=5, column=0, sticky="w", padx=(14, 10), pady=4)
        branch_box = ctk.CTkFrame(profile_card, fg_color="transparent")
        branch_box.grid(row=5, column=1, columnspan=2, sticky="ew", pady=4, padx=(0, 14))
        self._publish_editor_widgets.extend([branch_label, branch_box])
        branch_box.grid_columnconfigure(0, weight=1)
        self.publish_branch_combo = ctk.CTkComboBox(
            branch_box, values=[""], variable=self.publish_branch_var, height=30,
            fg_color=_c("surface_2"), border_color=_c("border"), text_color=_c("text"), font=(FONT, 10),
        )
        self.publish_branch_combo.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(branch_box, text="Actualizar", width=84, height=30,
                      command=self.refresh_publish_branches).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(branch_box, text="Activar rama", width=100, height=30,
                      command=self.activate_publish_branch).grid(row=0, column=2, padx=(8, 0))

        self.publish_git_name_entry = field(6, "Usuario Git", self.publish_git_name_var)
        self.publish_git_email_entry = field(7, "Correo Git", self.publish_git_email_var)

        editor_actions = ctk.CTkFrame(profile_card, fg_color="transparent")
        editor_actions.grid(row=8, column=0, columnspan=3, sticky="e", padx=14, pady=(5, 11))
        ctk.CTkButton(editor_actions, text="Cancelar", width=86, height=30, fg_color="transparent",
                      border_width=1, border_color=_c("border"), text_color=_c("text_2"),
                      command=self.cancel_publish_profile_edit).pack(side="left", padx=(0, 8))
        ctk.CTkButton(editor_actions, text="Guardar perfil", width=112, height=30,
                      command=self.save_publish_profile).pack(side="left")
        self._publish_editor_widgets.append(editor_actions)

        summary = ctk.CTkFrame(outer, fg_color=_c("surface"), corner_radius=10)
        summary.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        summary.grid_columnconfigure(0, weight=1)
        self.publish_scope_var = ctk.StringVar(value="Carpeta de publicación: —")
        self.publish_destination_var = ctk.StringVar(value="Destino remoto: —")
        self.publish_identity_var = ctk.StringVar(value="Identidad Git: —")
        self._publish_field_labels = []
        for row, variable in enumerate((self.publish_scope_var, self.publish_destination_var, self.publish_identity_var)):
            label = ctk.CTkLabel(summary, textvariable=variable, font=(FONT, 10), text_color=_c("text"),
                                 anchor="w", justify="left", wraplength=980)
            label.grid(row=row, column=0, sticky="ew", padx=14, pady=(8 if row == 0 else 2, 8 if row == 2 else 2))
            self._publish_field_labels.append(label)

        commit_card = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        commit_card.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(commit_card, text="MENSAJE DEL COMMIT", font=(FONT, 8, "bold"), text_color=_c("muted"), anchor="w").pack(fill="x", padx=16, pady=(11, 4))
        self.commit_text = ctk.CTkTextbox(
            commit_card, height=68, fg_color=_c("surface_2"), border_width=1, border_color=_c("border"),
            text_color=_c("text"), font=(FONT, 10), wrap="word",
        )
        self.commit_text.pack(fill="x", padx=16, pady=(0, 11))
        self.commit_text.insert("1.0", f"CorePulse {VERSION_LABEL} - actualización del proyecto")

        status_card = ctk.CTkFrame(outer, fg_color=_c("surface"), border_width=1, border_color=_c("border"), corner_radius=14)
        status_card.grid(row=5, column=0, sticky="nsew", pady=(0, 8))
        status_card.grid_columnconfigure(0, weight=1)
        status_card.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(status_card, text="CONSOLA DE PUBLICACIÓN / VISTA PREVIA", font=(FONT, 8, "bold"), text_color=_c("muted"), anchor="w").grid(row=0, column=0, sticky="ew", padx=16, pady=(11, 3))
        self.publish_status_var = ctk.StringVar(value="Configura o selecciona un perfil de publicación.")
        self._publish_status_label = ctk.CTkLabel(
            status_card, textvariable=self.publish_status_var, font=(FONT, 10, "bold"),
            text_color=_c("text"), anchor="w", justify="left", wraplength=1000,
        )
        self._publish_status_label.grid(row=1, column=0, sticky="ew", padx=16)
        self.publish_log = ctk.CTkTextbox(
            status_card, height=112, fg_color=_c("surface_2"), border_width=1, border_color=_c("border"),
            text_color=_c("text_2"), font=(FONT, 9), wrap="word",
        )
        self.publish_log.grid(row=2, column=0, sticky="nsew", padx=16, pady=(8, 11))
        self.publish_log.configure(state="disabled")

        actions = ctk.CTkFrame(outer, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.review_publish_button = ctk.CTkButton(actions, text="Revisar", width=104, height=38,
                                                   command=lambda: self.refresh_publish_context(manual=True))
        self.review_publish_button.grid(row=0, column=0, sticky="w")
        self.do_publish_button = ctk.CTkButton(
            actions, text="Publicar", width=230, height=38, state="disabled",
            fg_color=_c("accent"), hover_color=_c("accent_2"), text_color=_c("text"),
            font=(FONT, 10, "bold"), command=self.publish_now,
        )
        self.do_publish_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ctk.CTkLabel(
            actions, text="Ámbito: toda la carpeta raíz seleccionada · main/master/trunk bloqueadas · sin force-push.",
            font=(FONT, 8), text_color=_c("muted"), anchor="w",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self._reload_publish_profiles()
        self._show_publish_profile_editor(False)
        try:
            self.publish_frame.after_idle(self._apply_publish_density)
        except Exception:
            pass

    def _apply_publish_density(self):
        """Mantiene el publicador usable en ventana y maximizado."""
        try:
            width = max(1, int(self.frame.winfo_width()))
            height = max(1, int(self.frame.winfo_height()))
            compact = height < 780 or width < 1050
            self._publish_outer.pack_configure(padx=12 if compact else 18, pady=9 if compact else 13)
            self._publish_title_label.configure(font=(FONT, 20 if compact else 23, 'bold'))
            wrap = max(180, width - 110)
            for label in self._publish_field_labels:
                label.configure(wraplength=wrap)
            self._publish_status_label.configure(wraplength=max(180, width - 110))
            self.publish_log.configure(height=125 if compact else 150)
            self.commit_text.configure(height=46 if compact else 58)
        except Exception:
            pass

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

    def _show_publish_profile_editor(self, show: bool):
        self._publish_editor_visible = bool(show)
        for widget in getattr(self, '_publish_editor_widgets', []):
            try:
                if show:
                    widget.grid()
                else:
                    widget.grid_remove()
            except Exception:
                pass
        try:
            self.edit_publish_profile_button.configure(state='normal' if getattr(self, '_publish_profile_id', '') else 'disabled')
        except Exception:
            pass
        try:
            self._apply_publish_density()
        except Exception:
            pass

    def edit_publish_profile(self):
        if self.busy or not getattr(self, '_publish_profile_id', ''):
            return
        self._show_publish_profile_editor(True)
        self.publish_status_var.set('Editando perfil. Los datos Git ya detectados pueden ajustarse y guardarse.')

    def cancel_publish_profile_edit(self):
        if self.busy:
            return
        profile = next((p for p in getattr(self, '_publish_profile_map', {}).values()
                        if str(p.get('id') or '') == str(getattr(self, '_publish_profile_id', '') or '')), None)
        if profile:
            self._populate_publish_profile(profile, collapse=False)
        self._show_publish_profile_editor(False)
        self.refresh_publish_context(manual=False)

    def _collect_publish_profile(self):
        return {
            'id': str(getattr(self, '_publish_profile_id', '') or ''),
            'name': self.publish_profile_name_var.get().strip(),
            'repo_root': self.publish_repo_var.get().strip(),
            'remote': 'origin',
            'remote_url': self.publish_remote_var.get().strip(),
            'branch': self.publish_branch_var.get().strip(),
            'git_user_name': self.publish_git_name_var.get().strip(),
            'git_user_email': self.publish_git_email_var.get().strip(),
        }

    @staticmethod
    def _profile_fields_equal(left, right):
        keys = ('id', 'name', 'repo_root', 'remote', 'remote_url', 'branch', 'git_user_name', 'git_user_email')
        return all(str((left or {}).get(key) or '').strip() == str((right or {}).get(key) or '').strip() for key in keys)

    def _reload_publish_profiles(self, select_id=None):
        store = load_publication_profiles()
        profiles = list(store.get('profiles') or [])
        self._publish_profile_map = {str(p.get('name') or ''): p for p in profiles if p.get('name')}
        names = list(self._publish_profile_map)
        self.publish_profile_combo.configure(values=names or ["Sin perfiles guardados"])
        wanted = str(select_id or store.get('active_profile_id') or '')
        profile = next((p for p in profiles if str(p.get('id') or '') == wanted), None)
        if profile is None and profiles:
            profile = profiles[0]
        if profile is not None:
            self._populate_publish_profile(profile)
            self._show_publish_profile_editor(False)
        else:
            self._publish_profile_id = ''
            self.publish_profile_var.set('Sin perfiles guardados')
            self.publish_profile_name_var.set('')
            self.publish_repo_var.set('')
            self.publish_remote_var.set('')
            self.publish_branch_var.set('')
            self.publish_git_name_var.set('')
            self.publish_git_email_var.set('')
            self.publish_status_var.set('No hay perfiles. Pulsa Crear perfil; CorePulse puede rellenar los datos leyendo Git de la carpeta que elijas.')
            self._set_publish_log('Crea un perfil para comenzar. Al elegir un clon Git, CorePulse detectará automáticamente origin, rama, usuario y correo cuando estén configurados.')
            self._show_publish_profile_editor(False)

    def _populate_publish_profile(self, profile, collapse=True):
        self._publish_profile_id = str(profile.get('id') or '')
        self.publish_profile_var.set(str(profile.get('name') or 'Perfil'))
        self.publish_profile_name_var.set(str(profile.get('name') or ''))
        self.publish_repo_var.set(str(profile.get('repo_root') or ''))
        self.publish_remote_var.set(str(profile.get('remote_url') or ''))
        self.publish_branch_var.set(str(profile.get('branch') or ''))
        self.publish_git_name_var.set(str(profile.get('git_user_name') or ''))
        self.publish_git_email_var.set(str(profile.get('git_user_email') or ''))
        try:
            set_active_publication_profile(self._publish_profile_id)
        except Exception:
            pass
        self.refresh_publish_branches(silent=True)
        if collapse:
            self._show_publish_profile_editor(False)

    def _on_publish_profile_selected(self, name):
        profile = self._publish_profile_map.get(str(name))
        if profile:
            self._populate_publish_profile(profile)
            self.refresh_publish_context(manual=True)

    def new_publish_profile(self, prefill=False):
        self._publish_profile_id = ''
        self.publish_profile_var.set('Nuevo perfil')
        self.publish_profile_name_var.set('')
        self.publish_repo_var.set('')
        self.publish_remote_var.set('')
        self.publish_branch_var.set('')
        self.publish_git_name_var.set('')
        self.publish_git_email_var.set('')
        self.publish_branch_combo.configure(values=[''])
        self.publish_context = None
        self.do_publish_button.configure(text='Publicar', state='disabled')
        self.publish_status_var.set('Configura el perfil y pulsa Guardar perfil.')
        self._set_publish_log('Selecciona Detectar Git para elegir la carpeta del clon. CorePulse rellenará origin, rama e identidad Git automáticamente.')
        self._show_publish_profile_editor(True)
        if (prefill or self.publish_repo_hint) and self.publish_repo_hint:
            try:
                self._apply_repository_info(inspect_git_repository(self.publish_repo_hint))
            except Exception:
                pass

    def _apply_repository_info(self, info):
        self.publish_repo_var.set(str(info.get('repo_root') or ''))
        self.publish_remote_var.set(str(info.get('remote_url') or ''))
        if not self.publish_branch_var.get().strip():
            self.publish_branch_var.set(str(info.get('branch') or ''))
        if not self.publish_git_name_var.get().strip():
            self.publish_git_name_var.set(str(info.get('git_user_name') or ''))
        if not self.publish_git_email_var.get().strip():
            self.publish_git_email_var.set(str(info.get('git_user_email') or ''))
        branches = list(info.get('branches') or [])
        current = self.publish_branch_var.get().strip()
        if current and current not in branches:
            branches.append(current)
        self.publish_branch_combo.configure(values=branches or [''])
        if not self.publish_profile_name_var.get().strip() and info.get('git_user_name'):
            self.publish_profile_name_var.set(str(info['git_user_name']).strip())
        self.publish_repo_hint = str(info.get('repo_root') or self.publish_repo_hint or '')
        if self.publish_repo_hint:
            save_preferences(publish_repo=self.publish_repo_hint)

    def select_publish_repo(self):
        if self.busy:
            return
        initial = self.publish_repo_var.get().strip() or self.publish_repo_hint or None
        try:
            chosen = filedialog.askdirectory(parent=self.app, title="Seleccionar carpeta raíz del clon Git", initialdir=initial)
        except Exception:
            chosen = filedialog.askdirectory(title="Seleccionar carpeta raíz del clon Git")
        if not chosen:
            return
        try:
            self._apply_repository_info(inspect_git_repository(chosen))
            self.publish_status_var.set('Repositorio detectado. Revisa los campos y guarda el perfil.')
            self._set_publish_log('Git detectado correctamente en:\n' + self.publish_repo_var.get())
        except Exception as exc:
            cp_error(self.app, 'Perfil de publicación', str(exc))

    def refresh_publish_branches(self, silent=False):
        repo = self.publish_repo_var.get().strip()
        if not repo:
            if not silent:
                cp_error(self.app, 'Perfil de publicación', 'Selecciona primero la carpeta raíz del repositorio.')
            return
        try:
            info = refresh_git_remote(repo, remote='origin') if not silent else inspect_git_repository(repo)
            current_value = self.publish_branch_var.get().strip()
            branches = list(info.get('branches') or [])
            if current_value and current_value not in branches:
                branches.append(current_value)
            self.publish_branch_combo.configure(values=branches or [''])
            if not current_value:
                self.publish_branch_var.set(str(info.get('branch') or ''))
            if not self.publish_remote_var.get().strip():
                self.publish_remote_var.set(str(info.get('remote_url') or ''))
        except Exception as exc:
            if not silent:
                cp_error(self.app, 'Ramas Git', str(exc))

    def activate_publish_branch(self):
        if self.busy:
            return
        repo = self.publish_repo_var.get().strip()
        branch = self.publish_branch_var.get().strip()
        if not repo or not branch:
            cp_error(self.app, 'Activar rama', 'Selecciona la carpeta y escribe/elige una rama.')
            return
        try:
            active = activate_profile_branch(repo, branch, remote='origin')
            self.publish_branch_var.set(active)
            self.refresh_publish_branches(silent=True)
            self.publish_status_var.set(f'Rama activa: {active}.')
            self.refresh_publish_context(manual=True)
        except Exception as exc:
            cp_error(self.app, 'Activar rama', str(exc))

    def save_publish_profile(self):
        if self.busy:
            return
        draft = self._collect_publish_profile()
        repo = draft.get('repo_root')
        try:
            info = inspect_git_repository(repo)
            current_remote = str(info.get('remote_url') or '')
            requested_remote = str(draft.get('remote_url') or '').strip()
            if current_remote and requested_remote and current_remote != requested_remote:
                ok = cp_ask_yes_no(
                    self.app, 'Cambiar repositorio remoto',
                    f"El origin actual es:\n{current_remote}\n\nEl perfil indica:\n{requested_remote}\n\n¿Actualizar origin con esta nueva URL?",
                )
                if not ok:
                    return
            configure_git_repository(
                repo, remote='origin', remote_url=requested_remote or current_remote,
                git_user_name=draft.get('git_user_name'), git_user_email=draft.get('git_user_email'),
            )
            saved = save_publication_profile(draft)
            self._reload_publish_profiles(select_id=saved['id'])
            self._show_publish_profile_editor(False)
            self.publish_status_var.set(f"Perfil {saved['name']} guardado.")
            self.refresh_publish_context(manual=True)
        except Exception as exc:
            cp_error(self.app, 'Guardar perfil', str(exc))

    def delete_publish_profile(self):
        profile_id = str(getattr(self, '_publish_profile_id', '') or '')
        if not profile_id:
            return
        name = self.publish_profile_name_var.get().strip() or 'este perfil'
        if not cp_ask_yes_no(self.app, 'Eliminar perfil', f'¿Eliminar el perfil de publicación {name}?\n\nNo se elimina el repositorio ni ninguna credencial Git.'):
            return
        try:
            delete_publication_profile(profile_id)
            self._reload_publish_profiles()
        except Exception as exc:
            cp_error(self.app, 'Eliminar perfil', str(exc))

    def refresh_publish_context(self, manual: bool = False):
        if self.publish_frame is None or self.busy:
            return
        self._publish_review_id = getattr(self, '_publish_review_id', 0) + 1
        ticket = self._publish_review_id
        self.publish_context = None
        self.do_publish_button.configure(state='disabled')
        self.review_publish_button.configure(text='Revisando…', state='disabled')
        self.publish_status_var.set('Comprobando perfil, rama y cambios Git…')
        draft = self._collect_publish_profile()

        def worker():
            try:
                context = inspect_profile_publish_context(draft)
                saved = next((p for p in load_publication_profiles().get('profiles', [])
                              if str(p.get('id') or '') == str(draft.get('id') or '')), None)
                if saved is None or not self._profile_fields_equal(saved, draft):
                    context = dict(context)
                    blockers = list(context.get('blockers') or [])
                    if 'Guarda los cambios del perfil antes de publicar.' not in blockers:
                        blockers.append('Guarda los cambios del perfil antes de publicar.')
                    context['blockers'] = blockers
                    context['can_publish'] = False
                    context['can_push'] = False
            except Exception as exc:
                context = {'can_publish': False, 'can_push': False, 'blockers': [str(exc)]}
            self._call_ui(lambda c=context: self._show_publish_context(c, ticket))
        threading.Thread(target=worker, daemon=True, name='CorePulse-PublishReview').start()

    def _show_publish_context(self, ctx, ticket):
        if ticket != getattr(self, '_publish_review_id', None) or self.busy:
            return
        self.publish_context = ctx
        root = ctx.get('repo_root') or self.publish_repo_var.get().strip() or '—'
        self.publish_scope_var.set(f'Carpeta de publicación: {root}')
        self.publish_destination_var.set(f"Destino remoto: {ctx.get('remote_branch_url') or self.publish_remote_var.get().strip() or '—'}")
        identity = ' · '.join(part for part in (ctx.get('git_user_name'), ctx.get('git_user_email')) if part)
        self.publish_identity_var.set(f'Identidad Git: {identity or "—"}')
        lines = []
        if ctx.get('can_publish'):
            count = int(ctx.get('planned_count') or 0)
            pending = len(ctx.get('pending_commits') or [])
            if ctx.get('can_push'):
                self.publish_status_var.set('LISTO PARA PUBLICAR')
                lines = [
                    f"Perfil: {ctx.get('profile_name') or '—'}",
                    f"Rama: {ctx.get('configured_branch') or ctx.get('branch') or '—'}",
                    f"Archivos pendientes: {count} · nuevos {ctx.get('new_count', 0)} · modificados {ctx.get('modified_count', 0)} · eliminados {ctx.get('deleted_count', 0)}.",
                    "El total cuenta rutas de archivo pendientes en Git; no significa esa cantidad de ediciones manuales.",
                ]
                if count >= 250:
                    lines.append('Cantidad alta: esto suele ocurrir al agregar/reemplazar una carpeta de versión completa o muchas rutas nuevas. Revisa la lista antes de publicar.')
                if pending:
                    lines.append(f'Commits locales pendientes de push: {pending}.')
                lines.extend(list(ctx.get('planned_files') or [])[:80])
                if count > 80:
                    lines.append('… Se muestran los primeros 80 archivos.')
                lines.append('Git publicará la raíz completa seleccionada; FASE 1/2/3 se tratan como cualquier otra carpeta y sólo cambian si Git detecta modificaciones.')
                label = f'Publicar {count} archivo' + ('' if count == 1 else 's') if count else 'Enviar commits pendientes'
                self.do_publish_button.configure(text=label, state='normal')
            else:
                self.publish_status_var.set('TODO ACTUALIZADO')
                lines = ['No hay archivos cambiados ni commits locales pendientes. No se creará un commit vacío ni se hará un push innecesario.']
                self.do_publish_button.configure(text='Sin cambios', state='disabled')
        else:
            self.publish_status_var.set('PUBLICACIÓN BLOQUEADA')
            lines = list(ctx.get('blockers') or ['Configura un perfil válido.'])
            self.do_publish_button.configure(text='Publicar', state='disabled')
        self._set_publish_log('\n'.join(lines))
        self.review_publish_button.configure(text='Revisar', state='normal')

    def publish_now(self):
        if self.busy or not self.publish_context or not self.publish_context.get('can_push'):
            return
        message = self.commit_text.get('1.0', 'end').strip()
        if not message:
            cp_error(self.app, 'Publicar proyecto', 'Escribe un mensaje de commit antes de publicar.')
            return
        profile = self._collect_publish_profile()
        reviewed_context = dict(self.publish_context)
        self._set_busy(True)
        self.do_publish_button.configure(state='disabled')
        self.publish_status_var.set('Publicando cambios…')
        self._set_publish_log('Iniciando publicación segura del perfil…')

        def note(text):
            self._call_ui(lambda value=text: self._set_publish_log(value, append=True))

        def worker():
            try:
                result = publish_profile_root(profile, message, progress=note, expected_context=reviewed_context)
                self._call_ui(lambda r=result: self._finish_publish(r))
            except Exception as exc:
                self._call_ui(lambda e=exc: self._fail_publish(e))
        threading.Thread(target=worker, daemon=True, name='CorePulse-GitProfilePublish').start()

    def _finish_publish(self, result):
        self._set_busy(False)
        if result.get('no_changes'):
            self.publish_status_var.set('Todo estaba actualizado.')
            self._set_publish_log('No había nada nuevo que enviar al remoto.', append=True)
        else:
            self.publish_status_var.set(f"Publicado correctamente · commit {result.get('commit')} · rama {result.get('branch')}")
            self._set_publish_log(
                f"Push completado.\nPerfil: {result.get('profile_name') or 'N/A'}\n"
                f"Carpeta raíz: {result.get('repo_root') or 'N/A'}\n"
                f"Destino remoto: {result.get('remote_branch_url') or ('origin/' + str(result.get('branch') or 'N/A'))}",
                append=True,
            )
            cp_info(
                self.app, 'Publicación completada',
                f"Los cambios detectados en la carpeta raíz se publicaron en origin/{result.get('branch')}.\n\nCommit: {result.get('commit')}"
            )
        self.publish_context = None
        self.do_publish_button.configure(state='disabled')
        self.refresh_publish_context(manual=False)

    def _fail_publish(self, exc):
        self._set_busy(False)
        message = str(exc) if isinstance(exc, (PublishError, PublicationProfileError, UpdateError)) else f"{type(exc).__name__}: {exc}"
        self.publish_status_var.set('No se pudo completar la publicación.')
        self._set_publish_log(message, append=True)
        self.publish_context = None
        self.do_publish_button.configure(text='Revisar antes de reintentar', state='disabled')
        self.review_publish_button.configure(state='normal', text='Revisar')
        cp_error(self.app, 'Publicar proyecto', message)

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
