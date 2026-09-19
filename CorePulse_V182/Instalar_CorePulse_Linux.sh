#!/usr/bin/env bash
set -u

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

say() { printf '%s\n' "$*"; }
run_pkg_install() {
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

say "CorePulse · preparación para Linux"
say "Ruta: $ROOT"

# Dependencias del sistema. Son best-effort: CorePulse puede abrir aunque una
# capacidad opcional (SMART/audio) no esté instalada, y la marcará N/A.
if command -v apt-get >/dev/null 2>&1; then
  say "Detectado apt. Instalando Tk/venv, ALSA, SMART y utilidades…"
  run_pkg_install apt-get update || true
  run_pkg_install apt-get install -y python3 python3-venv python3-pip python3-tk git xdg-utils alsa-utils smartmontools lm-sensors udisks2 libglib2.0-bin || true
elif command -v dnf >/dev/null 2>&1; then
  say "Detectado dnf. Instalando Tk, ALSA, SMART y utilidades…"
  run_pkg_install dnf install -y python3 python3-pip python3-tkinter git xdg-utils alsa-utils smartmontools lm_sensors udisks2 glib2 || true
elif command -v pacman >/dev/null 2>&1; then
  say "Detectado pacman. Instalando Tk, ALSA, SMART y utilidades…"
  run_pkg_install pacman -Sy --needed --noconfirm python python-pip tk git xdg-utils alsa-utils smartmontools lm_sensors udisks2 glib2 || true
elif command -v zypper >/dev/null 2>&1; then
  say "Detectado zypper. Instalando Tk, ALSA, SMART y utilidades…"
  run_pkg_install zypper --non-interactive install python3 python3-pip python3-tk git xdg-utils alsa-utils smartmontools sensors udisks2 glib2-tools || true
else
  say "No reconocí el gestor de paquetes. Instala manualmente: Python 3.12+, Tk, venv, alsa-utils, smartmontools, udisks2/gdbus, xdg-utils y git."
fi

PY="$(command -v python3 || true)"
if [[ -z "$PY" ]]; then
  say "ERROR: python3 no está disponible."
  exit 2
fi

if ! "$PY" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
then
  say "ERROR: CorePulse requiere Python 3.12 o superior. Encontrado: $($PY --version 2>&1)"
  exit 3
fi

VENV="$ROOT/.venv-linux"
if [[ ! -x "$VENV/bin/python" ]]; then
  say "Creando entorno virtual .venv-linux…"
  "$PY" -m venv "$VENV" || {
    say "ERROR: no se pudo crear el entorno virtual. Instala el paquete python3-venv de tu distribución."
    exit 4
  }
fi

say "Instalando dependencias Python…"
"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV/bin/python" -m pip install -r "$ROOT/requirements-linux.txt"

say "Comprobando arranque mínimo…"
"$VENV/bin/python" - <<'PY'
from core.startup_readiness import collect_launch_gate
from core.version import VERSION
r = collect_launch_gate(VERSION)
print(f"CorePulse V{VERSION} · Linux launch gate: {'OK' if r.ready else 'ERROR'}")
if not r.ready:
    for item in r.items:
        if item.required and not item.ok:
            print(f"- {item.label}: {item.detail}")
    raise SystemExit(5)
PY

chmod +x "$ROOT/Ejecutar_CorePulse_Linux.sh" "$ROOT/CorePulse_Linux_Launcher.sh" "$ROOT/CorePulse" 2>/dev/null || true

# Instalación de acceso directo por usuario. No requiere root y utiliza un
# puntero estable para que las actualizaciones side-by-side puedan convertirse
# en la versión que abre el menú sin reescribir rutas antiguas.
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
COREPULSE_HOME="$DATA_HOME/CorePulse"
APP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
CURRENT_LINK="$COREPULSE_HOME/current"
mkdir -p "$COREPULSE_HOME" "$APP_DIR" "$ICON_DIR" 2>/dev/null || true
ln -sfn "$ROOT" "$CURRENT_LINK" 2>/dev/null || true

ICON_SOURCE="$ROOT/assets/CorePulseIcon.png"
if [[ -f "$ICON_SOURCE" ]]; then
  cp -f "$ICON_SOURCE" "$ICON_DIR/corepulse.png" 2>/dev/null || true
fi

DESKTOP_FILE="$APP_DIR/corepulse.desktop"
cat > "$DESKTOP_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Version=1.0
Name=CorePulse
GenericName=Hardware Monitoring & Diagnostics
Comment=Monitoreo, diagnóstico y mantenimiento de hardware
Exec=$CURRENT_LINK/CorePulse_Linux_Launcher.sh
Icon=corepulse
Terminal=false
Categories=System;Utility;
StartupNotify=true
StartupWMClass=CorePulse
DESKTOP
chmod +x "$DESKTOP_FILE" 2>/dev/null || true
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

say ""
say "LISTO. CorePulse ya puede abrirse sin comandos."
say "- En esta carpeta: doble clic en CorePulse_Linux.desktop (o CorePulse)."
say "- Menú de aplicaciones: busca CorePulse."
say "SMART, NVIDIA y audio se detectan automáticamente si el sistema los expone."
