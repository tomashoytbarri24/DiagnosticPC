#!/usr/bin/env bash
# CorePulse Linux one-click launcher.
# Double-click CorePulse_Linux.desktop (or this file) instead of typing commands.
set -u

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
COREPULSE_HOME="$DATA_HOME/CorePulse"
CURRENT_LINK="$COREPULSE_HOME/current"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/CorePulse/logs"
mkdir -p "$COREPULSE_HOME" "$LOG_DIR" 2>/dev/null || true

notify_error() {
  local msg="$1"
  if command -v kdialog >/dev/null 2>&1; then
    kdialog --error "$msg" --title "CorePulse"
  elif command -v zenity >/dev/null 2>&1; then
    zenity --error --title="CorePulse" --text="$msg"
  else
    printf '%s\n' "$msg" >&2
  fi
}

set_current_link() {
  if [[ -L "$CURRENT_LINK" || ! -e "$CURRENT_LINK" ]]; then
    ln -sfn "$ROOT" "$CURRENT_LINK" 2>/dev/null || true
  fi
}

runtime_ready() {
  [[ -x "$ROOT/.venv-linux/bin/python" ]] || return 1
  "$ROOT/.venv-linux/bin/python" - <<'PY' >/dev/null 2>&1
import customtkinter, PIL, psutil, platformdirs
import tkinter
PY
}

launch_installer_terminal() {
  local quoted_root
  printf -v quoted_root '%q' "$ROOT"
  local command="cd $quoted_root; bash ./Instalar_CorePulse_Linux.sh; rc=\$?; if [ \$rc -eq 0 ]; then exec bash ./CorePulse_Linux_Launcher.sh --after-install; else echo; echo 'La preparación de CorePulse no pudo completarse (código '\$rc').'; echo 'Puedes cerrar esta ventana después de revisar el mensaje.'; fi"

  if command -v konsole >/dev/null 2>&1; then
    konsole --hold -e bash -lc "$command" >/dev/null 2>&1 &
    return 0
  elif command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal -- bash -lc "$command; echo; read -r -p 'Pulsa Enter para cerrar…' _" >/dev/null 2>&1 &
    return 0
  elif command -v xfce4-terminal >/dev/null 2>&1; then
    xfce4-terminal --hold -e "bash -lc '$command'" >/dev/null 2>&1 &
    return 0
  elif command -v xterm >/dev/null 2>&1; then
    xterm -hold -e bash -lc "$command" >/dev/null 2>&1 &
    return 0
  fi
  return 1
}

set_current_link

if ! runtime_ready; then
  if [[ "${1:-}" == "--after-install" ]]; then
    notify_error "La preparación terminó, pero el entorno de CorePulse todavía no está listo. Revisa el registro de instalación."
    exit 4
  fi
  if launch_installer_terminal; then
    exit 0
  fi
  notify_error "CorePulse necesita preparar su entorno la primera vez y no encontró un emulador de terminal compatible (Konsole, GNOME Terminal, XFCE Terminal o xterm)."
  exit 3
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  notify_error "No se detectó una sesión gráfica. Abre CorePulse desde tu escritorio Linux."
  exit 2
fi

exec "$ROOT/.venv-linux/bin/python" "$ROOT/corepulse_launcher.py" "$@"
