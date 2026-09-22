"""CorePulse Driver Direct: detección y gestión de drivers sin Windows Update Agent.

La fuente online es el Microsoft Update Catalog consultado directamente por ID de
hardware. CorePulse no usa la sesión COM de Windows Update. Los paquetes se
bajan por HTTPS, se guardan en una caché local, se extraen y Windows decide la
compatibilidad final al instalar con PnPUtil.

Importante: el sitio del Update Catalog no ofrece una API pública estable para
este flujo. Por eso el parser es deliberadamente conservador: si no puede
confirmar ID, versión o URL de paquete, devuelve N/A en vez de inventar una
actualización.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable


CATALOG_SEARCH = "https://www.catalog.update.microsoft.com/Search.aspx?q={}"
CATALOG_DOWNLOAD = "https://www.catalog.update.microsoft.com/DownloadDialog.aspx"
CACHE_ROOT = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "CorePulse" / "drivers"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CorePulse/259"


class DriverUpdateError(RuntimeError):
    pass


def _powershell_exe() -> str:
    for name in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        found = shutil.which(name)
        if found:
            return found
    raise DriverUpdateError("PowerShell no está disponible en este equipo.")


def _run_ps(script: str, *, timeout: int = 120, env: dict[str, str] | None = None) -> Any:
    if os.name != "nt":
        raise DriverUpdateError("La gestión de controladores está disponible sólo en Windows.")
    proc = subprocess.run(
        [_powershell_exe(), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(30, int(timeout)),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env={**os.environ, **(env or {})},
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DriverUpdateError(detail or f"PowerShell devolvió código {proc.returncode}.")
    raw = (proc.stdout or "").strip()
    if not raw:
        return {}
    for candidate in reversed([line.strip() for line in raw.splitlines() if line.strip()]):
        try:
            return json.loads(candidate)
        except Exception:
            continue
    raise DriverUpdateError("Windows respondió, pero no devolvió un resultado JSON válido.")


def _http_text(url: str, *, data: bytes | None = None, timeout: int = 45) -> str:
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded" if data is not None else "text/html",
        },
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(10, int(timeout))) as response:
            payload = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    except Exception as exc:
        raise DriverUpdateError(f"No se pudo consultar el catálogo de controladores: {exc}") from exc


def _strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value or "")
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _version_tuple(value: Any) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(value or ""))
    if not parts:
        return ()
    return tuple(int(p) for p in parts[:8])


def _is_newer(candidate: Any, installed: Any) -> bool:
    a = _version_tuple(candidate)
    b = _version_tuple(installed)
    if not a or not b:
        return False
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def _extract_version(title: str, row_text: str = "") -> str | None:
    text = f"{title} {row_text}"
    # Prefer 4-part driver versions; fall back to 3/2-part only when unambiguous.
    matches = re.findall(r"(?<!\d)(\d+(?:\.\d+){3,5})(?!\d)", text)
    if matches:
        return matches[-1]
    matches = re.findall(r"(?<!\d)(\d+(?:\.\d+){2})(?!\d)", text)
    return matches[-1] if matches else None


def _size_bytes(text: str) -> int:
    m = re.search(r"(?i)(\d+(?:[\.,]\d+)?)\s*(KB|MB|GB)\b", text or "")
    if not m:
        return 0
    amount = float(m.group(1).replace(",", "."))
    factor = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[m.group(2).upper()]
    return int(amount * factor)


def _normalize_hw_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _installed_driver_candidates(limit: int = 16) -> list[dict[str, Any]]:
    """Devuelve sólo dispositivos físicos/relevantes con IDs de hardware reales."""
    script = r'''
$ErrorActionPreference='SilentlyContinue'
$rows=@()
$drivers=Get-CimInstance Win32_PnPSignedDriver
foreach($d in $drivers){
  if(-not $d.DeviceID){ continue }
  $class=[string]$d.DeviceClass
  $provider=[string]$d.DriverProviderName
  $name=[string]$d.DeviceName
  $priority=0
  switch -Regex ($class.ToUpperInvariant()) {
    '^DISPLAY$' {$priority=100;break}
    '^NET$' {$priority=96;break}
    '^(MEDIA|AUDIOENDPOINT)$' {$priority=94;break}
    '^(HDC|SCSIADAPTER|DISKDRIVE|STORAGEVOLUMES)$' {$priority=92;break}
    '^BLUETOOTH$' {$priority=90;break}
    '^(USB|USBDEVICE)$' {$priority=86;break}
    '^SYSTEM$' {$priority=82;break}
    '^SOFTWARECOMPONENT$' {$priority=78;break}
    '^FIRMWARE$' {$priority=70;break}
  }
  if($priority -le 0){ continue }
  # Quita dispositivos puramente genéricos de Microsoft que llenan la lista.
  if(($provider -match '^Microsoft( Corporation)?$') -and ($name -match 'WAN Miniport|Generic Software Device|Local Print Queue')){ continue }
  $ids=@()
  try {
    $p=Get-PnpDeviceProperty -InstanceId $d.DeviceID -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction Stop
    if($p.Data){ $ids=@($p.Data | ForEach-Object {[string]$_}) }
  } catch {}
  if($ids.Count -eq 0){ continue }
  $rows += [pscustomobject]@{
    device_name=$name; device_class=$class; provider=$provider; current_version=[string]$d.DriverVersion;
    current_date=if($d.DriverDate){[string]$d.DriverDate}else{$null}; instance_id=[string]$d.DeviceID;
    hardware_ids=$ids; priority=$priority
  }
}
$rows | Sort-Object @{Expression='priority';Descending=$true},device_name | ConvertTo-Json -Depth 5 -Compress
'''
    payload = _run_ps(script, timeout=90)
    if isinstance(payload, dict):
        rows = [payload]
    elif isinstance(payload, list):
        rows = [x for x in payload if isinstance(x, dict)]
    else:
        rows = []
    seen: set[tuple[str, str, str]] = set()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        ids = row.get("hardware_ids")
        if isinstance(ids, str):
            ids = [ids]
        ids = [_normalize_hw_id(x) for x in (ids or []) if _normalize_hw_id(x)]
        if not ids:
            continue
        key = (
            str(row.get("device_name") or "").casefold(),
            str(row.get("provider") or "").casefold(),
            str(row.get("current_version") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        row["hardware_ids"] = ids[:4]
        candidates.append(row)

    # No llenamos el cupo sólo con USB/System. Primero reservamos una plaza por
    # familia relevante para que GPU/red/audio/almacenamiento, software components
    # y firmware tengan oportunidad real de consultar el catálogo. Después se
    # completa por prioridad. Es una selección de backend; la UI sigue mostrando
    # exclusivamente actualizaciones confirmadas.
    def family(item: dict[str, Any]) -> str:
        cls = str(item.get("device_class") or "").upper()
        if cls in {"MEDIA", "AUDIOENDPOINT"}:
            return "AUDIO"
        if cls in {"HDC", "SCSIADAPTER", "DISKDRIVE", "STORAGEVOLUMES"}:
            return "STORAGE"
        if cls in {"USB", "USBDEVICE"}:
            return "USB"
        return cls

    max_count = max(1, int(limit))
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    family_order = (
        "DISPLAY", "NET", "AUDIO", "STORAGE", "BLUETOOTH",
        "SOFTWARECOMPONENT", "FIRMWARE", "SYSTEM", "USB",
    )
    for fam in family_order:
        item = next((x for x in candidates if family(x) == fam and id(x) not in selected_ids), None)
        if item is not None:
            selected.append(item)
            selected_ids.add(id(item))
            if len(selected) >= max_count:
                return selected
    for item in candidates:
        if id(item) in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(id(item))
        if len(selected) >= max_count:
            break
    return selected


def _catalog_rows_for_hardware_id(hardware_id: str) -> list[dict[str, Any]]:
    query = f'"{hardware_id}"'
    url = CATALOG_SEARCH.format(urllib.parse.quote(query, safe=""))
    text = _http_text(url, timeout=40)
    rows: list[dict[str, Any]] = []
    # Cada resultado del catálogo contiene un goToDetails(<GUID>) dentro de su <tr>.
    for match in re.finditer(r"(?is)<tr\b[^>]*>(.*?)</tr>", text):
        fragment = match.group(1)
        guid_m = re.search(r"goToDetails\(['\"]([0-9a-fA-F-]{36})['\"]\)", fragment)
        if not guid_m:
            continue
        guid = guid_m.group(1).lower()
        title_m = re.search(rf"(?is)<a\b[^>]*id=['\"]{re.escape(guid)}_link['\"][^>]*>(.*?)</a>", fragment)
        if not title_m:
            title_m = re.search(r"(?is)<a\b[^>]*>(.*?)</a>", fragment)
        title = _strip_tags(title_m.group(1)) if title_m else ""
        row_text = _strip_tags(fragment)
        version = _extract_version(title, row_text)
        rows.append({
            "update_id": guid,
            "title": title or "Paquete de controlador",
            "available_version": version,
            "row_text": row_text,
            "max_download_size": _size_bytes(row_text),
        })
    return rows


def _best_catalog_update(device: dict[str, Any]) -> dict[str, Any] | None:
    installed = str(device.get("current_version") or "").strip()
    if not installed:
        return None
    for hardware_id in list(device.get("hardware_ids") or [])[:3]:
        try:
            rows = _catalog_rows_for_hardware_id(hardware_id)
        except DriverUpdateError:
            continue
        for row in rows:
            candidate = str(row.get("available_version") or "").strip()
            if not candidate or not _is_newer(candidate, installed):
                continue
            title = str(row.get("title") or "")
            provider = str(device.get("provider") or "").strip()
            # El ID de hardware es la autoridad de compatibilidad. El proveedor se
            # usa sólo como señal blanda para evitar resultados obviamente ajenos.
            if provider and provider.casefold() not in title.casefold():
                provider_token = provider.split()[0].casefold()
                if provider_token and provider_token not in title.casefold():
                    # No descartamos OEM/software components: muchos títulos usan
                    # la marca del componente en vez del proveedor instalado.
                    if str(device.get("device_class") or "").upper() not in {"SOFTWARECOMPONENT", "FIRMWARE", "SYSTEM"}:
                        continue
            return {
                **row,
                "revision": 0,
                "device_name": str(device.get("device_name") or "Dispositivo"),
                "driver_class": str(device.get("device_class") or ""),
                "provider": provider,
                "current_version": installed,
                "hardware_id": hardware_id,
                "is_downloaded": _cached_package_path(row.get("update_id")) is not None,
                "source": "Microsoft Update Catalog directo",
                "bulk_install_allowed": str(device.get("device_class") or "").upper() != "FIRMWARE",
            }
    return None


def scan_driver_updates(*, max_devices: int = 16) -> dict[str, Any]:
    """Busca drivers nuevos por ID de hardware sin usar Windows Update Agent."""
    devices = _installed_driver_candidates(limit=max_devices)
    if not devices:
        return {
            "items": [], "count": 0, "checked_devices": 0,
            "source": "Microsoft Update Catalog directo", "error": None,
            "note": "No se encontraron dispositivos relevantes con IDs de hardware consultables.",
        }
    found: list[dict[str, Any]] = []
    errors: list[str] = []
    workers = min(4, max(1, len(devices)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="CorePulseDriverCatalog") as pool:
        future_map = {pool.submit(_best_catalog_update, d): d for d in devices}
        for future in as_completed(future_map):
            try:
                item = future.result()
                if item:
                    found.append(item)
            except Exception as exc:
                errors.append(str(exc))
    found.sort(key=lambda x: (str(x.get("driver_class") or "").upper() == "FIRMWARE", str(x.get("device_name") or "").casefold()))
    return {
        "items": found,
        "count": len(found),
        "checked_devices": len(devices),
        "source": "Microsoft Update Catalog directo",
        "error": None if found or not errors else errors[0],
        "warnings": errors[:3],
        "note": "Compatibilidad final validada por Windows/PnPUtil al instalar; firmware queda fuera de Instalar todo.",
    }


def _download_urls(update_id: str) -> list[str]:
    update_id = str(update_id or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f-]{36}", update_id):
        raise DriverUpdateError("El paquete no tiene un identificador válido del catálogo.")
    post = json.dumps({"size": 0, "updateID": update_id, "uidInfo": update_id}, separators=(",", ":"))
    body = urllib.parse.urlencode({"updateIDs": f"[{post}]"}).encode("utf-8")
    text = _http_text(CATALOG_DOWNLOAD, data=body, timeout=45)
    text = text.replace("www.download.windowsupdate", "download.windowsupdate")
    pattern = r"https?://(?:dl\.delivery\.mp\.microsoft\.com|download\.windowsupdate\.com|catalog\.s\.download\.windowsupdate\.com)/[^'\"<>\s]+"
    urls = []
    for m in re.finditer(pattern, text, flags=re.I):
        url = html.unescape(m.group(0)).replace("\\u0026", "&")
        if url not in urls:
            urls.append(url)
    return urls


def _cache_dir(update_id: Any) -> Path:
    safe = re.sub(r"[^0-9a-zA-Z-]", "", str(update_id or "")) or "unknown"
    return CACHE_ROOT / safe


def _cached_package_path(update_id: Any) -> Path | None:
    root = _cache_dir(update_id)
    if not root.is_dir():
        return None
    candidates = sorted([p for p in root.iterdir() if p.is_file() and p.suffix.lower() in {".cab", ".msu", ".zip"}])
    return candidates[0] if candidates else None


def _filename_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    name = urllib.parse.unquote(os.path.basename(path)).strip()
    return name or "driver_package.cab"


def download_driver_update(update_id: str, revision: int = 0) -> dict[str, Any]:
    """Descarga el CAB/MSU directamente; no usa la caché ni el agente de Windows Update."""
    cached = _cached_package_path(update_id)
    if cached is not None and cached.stat().st_size > 0:
        return {"ok": True, "mode": "download", "downloaded": True, "path": str(cached), "source": "Catalog directo"}
    urls = _download_urls(update_id)
    if not urls:
        raise DriverUpdateError("El catálogo no devolvió una URL de descarga para este paquete.")
    # Drivers suelen ser CAB. Si hay varios idiomas/formatos, priorizamos CAB.
    urls.sort(key=lambda u: (0 if ".cab" in u.lower() else 1, 0 if ".msu" in u.lower() else 1, len(u)))
    url = urls[0]
    root = _cache_dir(update_id)
    root.mkdir(parents=True, exist_ok=True)
    target = root / _filename_from_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as response, open(target, "wb") as fh:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
    except Exception as exc:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        raise DriverUpdateError(f"No se pudo descargar el paquete: {exc}") from exc
    if not target.exists() or target.stat().st_size <= 0:
        raise DriverUpdateError("La descarga terminó sin crear un paquete válido.")
    return {
        "ok": True, "mode": "download", "downloaded": True,
        "path": str(target), "bytes": int(target.stat().st_size),
        "source": "Microsoft Update Catalog directo",
    }


def _extract_package(package: Path, root: Path) -> Path:
    extract_dir = root / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True, exist_ok=True)
    suffix = package.suffix.lower()
    if suffix == ".cab":
        cmd = ["expand.exe", "-F:*", str(package), str(extract_dir)]
    elif suffix == ".zip":
        shutil.unpack_archive(str(package), str(extract_dir))
        return extract_dir
    elif suffix == ".msu":
        cmd = ["expand.exe", "-F:*", str(package), str(extract_dir)]
    else:
        raise DriverUpdateError(f"Formato de paquete no compatible: {suffix or 'desconocido'}")
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", timeout=180,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if proc.returncode != 0:
        raise DriverUpdateError((proc.stderr or proc.stdout or "No se pudo extraer el paquete.").strip())
    return extract_dir


def _valid_catalog_signature(extract_dir: Path) -> bool:
    cats = list(extract_dir.rglob("*.cat"))
    if not cats:
        return False
    # Validamos al menos un catálogo Authenticode. PnPUtil vuelve a validar la
    # firma y compatibilidad durante la instalación.
    paths = "|".join(str(p) for p in cats[:12])
    script = r'''
$ErrorActionPreference='SilentlyContinue'
$ok=$false
foreach($p in ([string]$env:COREPULSE_CAT_FILES -split '\|')){
  if(-not $p){continue}
  try { if((Get-AuthenticodeSignature -FilePath $p).Status -eq 'Valid'){ $ok=$true; break } } catch {}
}
[pscustomobject]@{ok=$ok}|ConvertTo-Json -Compress
'''
    try:
        result = _run_ps(script, timeout=60, env={"COREPULSE_CAT_FILES": paths})
        return bool(isinstance(result, dict) and result.get("ok"))
    except Exception:
        return False


def install_driver_update(update_id: str, revision: int = 0) -> dict[str, Any]:
    """Instala desde la caché directa usando PnPUtil; requiere elevación."""
    if os.name != "nt":
        raise DriverUpdateError("La instalación de controladores está disponible sólo en Windows.")
    package = _cached_package_path(update_id)
    if package is None:
        download_driver_update(update_id, revision)
        package = _cached_package_path(update_id)
    if package is None:
        raise DriverUpdateError("No se encontró el paquete descargado.")
    root = _cache_dir(update_id)
    extract_dir = _extract_package(package, root)
    infs = list(extract_dir.rglob("*.inf"))
    if not infs:
        raise DriverUpdateError("El paquete no contiene archivos INF instalables.")
    if not _valid_catalog_signature(extract_dir):
        raise DriverUpdateError("No se pudo validar una firma de catálogo del paquete. CorePulse no lo instalará.")
    pnputil = shutil.which("pnputil.exe") or shutil.which("pnputil") or str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "pnputil.exe")
    pattern = str(extract_dir / "*.inf")
    proc = subprocess.run(
        [pnputil, "/add-driver", pattern, "/subdirs", "/install"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", timeout=300,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise DriverUpdateError(output or f"PnPUtil devolvió código {proc.returncode}.")
    reboot = bool(re.search(r"(?i)restart|reboot|reinici", output))
    return {
        "ok": True, "mode": "install", "result_code": int(proc.returncode),
        "result_label": "CORRECTO", "reboot_required": reboot,
        "path": str(package), "source": "PnPUtil + Microsoft Update Catalog directo",
        "output": output[-4000:],
    }


def download_all_driver_updates(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for item in list(items or []):
        uid = str((item or {}).get("update_id") or "")
        if not uid:
            continue
        try:
            result = download_driver_update(uid, int((item or {}).get("revision") or 0))
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        results.append({"update_id": uid, "device_name": (item or {}).get("device_name"), **result})
    return {"ok": bool(results) and all(bool(x.get("ok")) for x in results), "results": results}


def install_all_driver_updates(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    results = []
    skipped = []
    for item in list(items or []):
        uid = str((item or {}).get("update_id") or "")
        if not uid:
            continue
        if not bool((item or {}).get("bulk_install_allowed", True)):
            skipped.append({"update_id": uid, "device_name": (item or {}).get("device_name"), "reason": "Firmware excluido de instalación masiva"})
            continue
        try:
            result = install_driver_update(uid, int((item or {}).get("revision") or 0))
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        results.append({"update_id": uid, "device_name": (item or {}).get("device_name"), **result})
    return {
        "ok": bool(results) and all(bool(x.get("ok")) for x in results),
        "results": results, "skipped": skipped,
        "reboot_required": any(bool(x.get("reboot_required")) for x in results),
    }


__all__ = [
    "DriverUpdateError",
    "scan_driver_updates",
    "download_driver_update",
    "install_driver_update",
    "download_all_driver_updates",
    "install_all_driver_updates",
]
