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
import hashlib
import time
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
CATALOG_CACHE_ROOT = CACHE_ROOT / "catalog-search"
CATALOG_CACHE_TTL = 12 * 60 * 60
CATALOG_HTTP_TIMEOUT = 4
INVENTORY_CACHE_FILE = CACHE_ROOT / "installed-candidates.json"
INVENTORY_CACHE_TTL = 10 * 60
SCAN_CACHE_FILE = CACHE_ROOT / "last-scan-v327.json"
SCAN_CACHE_TTL = 15 * 60
BACKUP_ROOT = CACHE_ROOT / "backups"
INTEL_BLUETOOTH_PAGE = "https://www.intel.com/content/www/us/en/download/18649/intel-wireless-bluetooth-drivers-for-windows-10-and-windows-11.html"
VENDOR_CACHE_ROOT = CACHE_ROOT / "vendor-search"
VENDOR_CACHE_TTL = 6 * 60 * 60
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CorePulse/327"

_VENDOR_SUPPORT = (
    (("nvidia", "geforce"), "NVIDIA", "https://www.nvidia.com/Download/index.aspx"),
    (("intel", "killer"), "Intel", "https://www.intel.com/content/www/us/en/support/detect.html"),
    (("advanced micro devices", "amd", "radeon"), "AMD", "https://www.amd.com/en/support/download/drivers.html"),
    (("realtek",), "Realtek", "https://www.realtek.com/Download/Index"),
    (("acer",), "Acer", "https://www.acer.com/support/drivers-and-manuals"),
    (("micro-star", "msi"), "MSI", "https://www.msi.com/support/download"),
)



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
        with urllib.request.urlopen(req, timeout=max(4, int(timeout))) as response:
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

def _read_json_cache(path: Path, ttl: float) -> Any:
    try:
        if path.exists() and (time.time() - path.stat().st_mtime) <= float(ttl):
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _write_json_cache(path: Path, payload: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _official_support_profile(provider: Any, device_name: Any = "") -> dict[str, str]:
    haystack = f"{provider or ''} {device_name or ''}".casefold()
    for tokens, name, url in _VENDOR_SUPPORT:
        if any(token in haystack for token in tokens):
            return {"official_vendor": name, "official_url": url}
    return {"official_vendor": "", "official_url": ""}



def _model_tokens(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for value in values or []:
        raw = str(value or "")
        for match in re.finditer(r"(?i)\b(?:BE|AX)\d{3,4}[A-Z]?\b|\b(?:9560|9462|9461|9260|1550)\b", raw):
            token = match.group(0).upper()
            if re.fullmatch(r"AX\d{4}[IS]", token):
                token = token[:-1]
            if token not in out:
                out.append(token)
    return out


def _vendor_cache_file(key: str) -> Path:
    digest = hashlib.sha256(str(key or "").encode("utf-8", errors="ignore")).hexdigest()[:24]
    return VENDOR_CACHE_ROOT / f"{digest}.json"


def _vendor_page_text(url: str, *, force_refresh: bool = False) -> str:
    cache_file = _vendor_cache_file(url)
    if not force_refresh:
        cached = _read_json_cache(cache_file, VENDOR_CACHE_TTL)
        if isinstance(cached, dict) and isinstance(cached.get("html"), str):
            return cached["html"]
    page = _http_text(url, timeout=CATALOG_HTTP_TIMEOUT)
    _write_json_cache(cache_file, {"html": page, "fetched": time.time()})
    return page


def _extract_direct_vendor_url(page: str, filename: str = "") -> str:
    raw = html.unescape(str(page or "")).replace("\\/", "/")
    candidates = re.findall(r"https?://downloadmirror\.intel\.com/[^\"'<>\s]+", raw, flags=re.I)
    if filename:
        exact = [u for u in candidates if filename.casefold() in urllib.parse.unquote(u).casefold()]
        if exact:
            return exact[0]
    exe = [u for u in candidates if re.search(r"(?i)\.(?:exe|zip)(?:\?|$)", u)]
    return exe[0] if exe else ""


def _intel_wireless_bluetooth_update(device: dict[str, Any], *, force_refresh: bool = False) -> dict[str, Any] | None:
    name = str(device.get("device_name") or "")
    provider = str(device.get("provider") or "")
    cls = str(device.get("device_class") or "").upper()
    haystack = f"{provider} {name}".casefold()
    if cls != "BLUETOOTH" or "intel" not in haystack or "bluetooth" not in haystack:
        return None
    installed = str(device.get("current_version") or "").strip()
    if not installed:
        return None
    page = _vendor_page_text(INTEL_BLUETOOTH_PAGE, force_refresh=force_refresh)
    plain = _strip_tags(page)
    models = _model_tokens(list(device.get("system_device_names") or []) + [name])
    supported = any(model.casefold() in plain.casefold() for model in models)
    ids = [str(x or "").upper() for x in (device.get("hardware_ids") or [])]
    parts = _version_tuple(installed)
    modern_branch = bool(parts and parts[0] >= 22)
    intel_usb = any("VID_8087" in item for item in ids)
    if not supported and not (intel_usb and modern_branch):
        return None
    versions = re.findall(r"(?i)Driver\s+version\s+([0-9]+(?:\.[0-9]+){2,4})", plain)
    package_versions = re.findall(r"(?i)(?:Wireless Bluetooth(?:®)?\s+(?:version|Package version)|Package version)\s+([0-9]+(?:\.[0-9]+){2,4})", plain)
    available = max(versions, key=_version_tuple) if versions else (max(package_versions, key=_version_tuple) if package_versions else "")
    if not available or not _is_newer(available, installed):
        return None
    file_m = re.search(r"(?i)\b(BT-[0-9.]+-64UWD-Win10-Win11\.exe)\b", plain)
    filename = file_m.group(1) if file_m else f"Intel-Wireless-Bluetooth-{available}.exe"
    sha_m = re.search(r"(?i)SHA256\s*:?\s*([0-9A-F]{64})", plain)
    direct_url = _extract_direct_vendor_url(page, filename)
    package_version = max(package_versions, key=_version_tuple) if package_versions else available
    uid = f"vendor-intel-bluetooth-{available}"
    return {
        "update_id": uid, "revision": 0, "title": f"Intel Wireless Bluetooth {package_version}",
        "available_version": available, "package_version": package_version,
        "device_name": name or "Intel Wireless Bluetooth", "driver_class": cls,
        "provider": provider or "Intel", "current_version": installed,
        "current_inf": str(device.get("inf_name") or ""),
        "hardware_id": (device.get("hardware_ids") or [""])[0],
        "instance_id": str(device.get("instance_id") or ""),
        "is_downloaded": _cached_package_path(uid) is not None,
        "source": "Intel Download Center oficial", "source_kind": "vendor_installer",
        "compatibility_source": "Familia Intel detectada + lista oficial de productos compatibles",
        "preferred_source": "Intel oficial", "official_vendor": "Intel",
        "official_url": INTEL_BLUETOOTH_PAGE, "vendor_page_url": INTEL_BLUETOOTH_PAGE,
        "vendor_download_url": direct_url, "vendor_filename": filename,
        "vendor_sha256": sha_m.group(1).upper() if sha_m else "",
        "package_kind": "EXE", "installer_mode": "interactive_elevated",
        "bulk_install_allowed": True, "max_download_size": _size_bytes(plain),
        "note": "Fuente oficial Intel; el instalador valida nuevamente el hardware compatible.",
    }


def _vendor_update_for_device(device: dict[str, Any], *, force_refresh: bool = False) -> dict[str, Any] | None:
    for resolver in (_intel_wireless_bluetooth_update,):
        try:
            item = resolver(device, force_refresh=force_refresh)
        except Exception:
            item = None
        if item:
            return item
    return None


def _enrich_selected_device_ids(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if os.name != "nt" or not devices:
        return devices
    instance_ids = [str(x.get("instance_id") or "") for x in devices if str(x.get("instance_id") or "")]
    if not instance_ids:
        return devices
    script = r'''$ErrorActionPreference='SilentlyContinue'
$ids = $env:COREPULSE_INSTANCE_IDS | ConvertFrom-Json
$rows=@()
foreach($id in $ids){
  $hw=@(); $compat=@()
  try { $p=Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue; if($p -and $p.Data){$hw=@($p.Data)}} catch {}
  try { $p=Get-PnpDeviceProperty -InstanceId $id -KeyName 'DEVPKEY_Device_CompatibleIds' -ErrorAction SilentlyContinue; if($p -and $p.Data){$compat=@($p.Data)}} catch {}
  $rows += [pscustomobject]@{instance_id=$id;hardware_ids=$hw;compatible_ids=$compat}
}
$rows | ConvertTo-Json -Depth 4 -Compress'''
    try:
        payload = _run_ps(script, timeout=30, env={"COREPULSE_INSTANCE_IDS": json.dumps(instance_ids)})
    except Exception:
        return devices
    rows = [payload] if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    by_id = {str(x.get("instance_id") or ""): x for x in rows if isinstance(x, dict)}
    for device in devices:
        row = by_id.get(str(device.get("instance_id") or ""))
        if not row:
            continue
        hw = row.get("hardware_ids") or []
        comp = row.get("compatible_ids") or []
        if isinstance(hw, str): hw = [hw]
        if isinstance(comp, str): comp = [comp]
        merged_hw, merged_comp = [], []
        for value in list(hw) + list(device.get("hardware_ids") or []):
            norm = _normalize_hw_id(value)
            if norm and norm not in merged_hw: merged_hw.append(norm)
        for value in comp:
            norm = _normalize_hw_id(value)
            if norm and norm not in merged_comp: merged_comp.append(norm)
        if merged_hw: device["hardware_ids"] = merged_hw[:8]
        device["compatible_ids"] = merged_comp[:8]
    return devices


def invalidate_driver_caches() -> None:
    for path in (INVENTORY_CACHE_FILE, SCAN_CACHE_FILE):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def _candidates_from_health_inventory(inventory: Any, limit: int = 20, instance_ids: set[str] | None = None) -> list[dict[str, Any]]:
    """Convierte el inventario ya leído por Análisis de Windows en candidatos web.

    Evita volver a ejecutar dos consultas CIM costosas sólo para Driver Hub. El
    DeviceID ya contiene un identificador de familia suficiente para consultar el
    catálogo; si no existe, el elemento se omite en vez de inventar compatibilidad.
    """
    data = inventory if isinstance(inventory, dict) else {}
    rows = [x for x in (data.get("items") or []) if isinstance(x, dict)]
    system_device_names = [str(x.get("DeviceName") or x.get("device_name") or "") for x in rows if str(x.get("DeviceName") or x.get("device_name") or "")]
    wanted = {str(x) for x in (instance_ids or set()) if str(x)}
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in rows:
        instance_id = str(source.get("DeviceID") or source.get("instance_id") or "").strip()
        if wanted and instance_id not in wanted:
            continue
        if not instance_id:
            continue
        raw_ids = source.get('HardwareID') or source.get('hardware_ids') or source.get('hardware_id') or []
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]
        hardware_ids = [_normalize_hw_id(x) for x in raw_ids if _normalize_hw_id(x)]
        if not hardware_ids:
            parts = instance_id.split("\\")
            if len(parts) >= 2:
                fallback_id = _normalize_hw_id(parts[0] + "\\" + parts[1])
                if fallback_id:
                    hardware_ids = [fallback_id]
        if not hardware_ids:
            continue
        device_name = str(source.get("DeviceName") or source.get("device_name") or "").strip()
        provider = str(source.get("DriverProviderName") or source.get("provider") or "").strip()
        current_version = str(source.get("DriverVersion") or source.get("current_version") or "").strip()
        key = (device_name.casefold(), provider.casefold(), current_version)
        if key in seen:
            continue
        seen.add(key)
        status = str(source.get("status") or "").upper()
        try:
            priority = int(source.get("hardware_priority") or source.get("priority") or 0)
        except Exception:
            priority = 0
        if not wanted and priority <= 0:
            continue
        attention = 4 if status == "DEVICE_PROBLEM" else 1 if status == "UNSIGNED" else 0
        row = {
            "device_name": device_name,
            "device_class": str(source.get("DeviceClass") or source.get("device_class") or ""),
            "provider": provider,
            "current_version": current_version,
            "instance_id": instance_id,
            "inf_name": str(source.get("InfName") or source.get("inf_name") or ""),
            "hardware_ids": hardware_ids[:4],
            "system_device_names": system_device_names,
            "priority": priority,
            "attention_score": attention,
        }
        row.update(_official_support_profile(provider, device_name))
        candidates.append(row)

    candidates.sort(
        key=lambda x: (int(x.get("attention_score") or 0), int(x.get("priority") or 0), str(x.get("device_name") or "").casefold()),
        reverse=True,
    )
    max_count = max(1, int(limit))
    if wanted:
        return candidates[:max_count]

    def family(item: dict[str, Any]) -> str:
        cls = str(item.get("device_class") or "").upper()
        if cls in {"MEDIA", "AUDIOENDPOINT"}: return "AUDIO"
        if cls in {"HDC", "SCSIADAPTER", "DISKDRIVE", "STORAGEVOLUMES"}: return "STORAGE"
        if cls in {"USB", "USBDEVICE"}: return "USB"
        return cls

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    # La primera pasada cubre las familias que un actualizador tipo Driver Booster
    # debe revisar siempre, en vez de gastar los 5 cupos en incidencias secundarias.
    for fam in ("DISPLAY", "NET", "AUDIO", "STORAGE", "BLUETOOTH"):
        item = next((x for x in candidates if family(x) == fam and str(x.get("instance_id") or "") not in selected_ids), None)
        if item is not None:
            selected.append(item); selected_ids.add(str(item.get("instance_id") or ""))
            if len(selected) >= max_count:
                return selected
    for item in candidates:
        iid = str(item.get("instance_id") or "")
        if iid in selected_ids: continue
        selected.append(item); selected_ids.add(iid)
        if len(selected) >= max_count: break
    return selected


def _installed_driver_candidates(limit: int = 20, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Devuelve sólo dispositivos físicos/relevantes con IDs de hardware reales.

    V323 conserva durante unos minutos el inventario WMI ya enumerado. Eso evita
    repetir el sondeo de cientos de filas cada vez que se abre Driver Hub.
    """
    cached_rows = None if force_refresh else _read_json_cache(INVENTORY_CACHE_FILE, INVENTORY_CACHE_TTL)
    if isinstance(cached_rows, list):
        rows = [x for x in cached_rows if isinstance(x, dict)]
    else:
        script = r'''
$ErrorActionPreference='SilentlyContinue'
$rows=@()
$dev=@{}
Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | ForEach-Object {
  if($_.PNPDeviceID){
    $status=if($null -ne $_.Status){[string]$_.Status}else{'N/A'}
    $code=if($null -ne $_.ConfigManagerErrorCode){[int]$_.ConfigManagerErrorCode}else{0}
    $dev[$_.PNPDeviceID]=[pscustomobject]@{status=$status;code=$code}
  }
}
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
  if(($provider -match '^Microsoft( Corporation)?$') -and ($name -match 'WAN Miniport|Wi-Fi Direct Virtual Adapter|Kernel Debug Network Adapter|Bluetooth Device \(Personal Area Network\)|Microsoft Streaming Service Proxy|Generic Software Device|Local Print Queue|Virtual Adapter|Root Enumerator')){ continue }
  $ids=@()
  if($d.HardWareID){ $ids=@([string]$d.HardWareID) }
  if($ids.Count -eq 0){
    $parts=([string]$d.DeviceID -split '\\')
    if($parts.Count -ge 2){ $ids=@([string]($parts[0]+'\'+$parts[1])) }
  }
  if($ids.Count -eq 0){ continue }
  $state=$dev[[string]$d.DeviceID]
  $rows += [pscustomobject]@{
    device_name=$name; device_class=$class; provider=$provider; current_version=[string]$d.DriverVersion;
    current_date=if($d.DriverDate){[string]$d.DriverDate}else{$null}; instance_id=[string]$d.DeviceID;
    inf_name=[string]$d.InfName; hardware_ids=$ids; priority=$priority; is_signed=$d.IsSigned;
    device_status=if($state){[string]$state.status}else{'N/A'};
    config_error_code=if($state){[int]$state.code}else{0}
  }
}
$rows | Sort-Object @{Expression='priority';Descending=$true},device_name | ConvertTo-Json -Depth 5 -Compress
'''
        payload = _run_ps(script, timeout=45)
        if isinstance(payload, dict):
            rows = [payload]
        elif isinstance(payload, list):
            rows = [x for x in payload if isinstance(x, dict)]
        else:
            rows = []
        _write_json_cache(INVENTORY_CACHE_FILE, rows)

    seen: set[tuple[str, str, str]] = set()
    candidates: list[dict[str, Any]] = []
    for source_row in rows:
        row = dict(source_row)
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
        provider_cf = str(row.get("provider") or "").strip().casefold()
        current_date = str(row.get("current_date") or "")
        age_years = None
        m = re.search(r"Date\((\d+)", current_date)
        if m:
            try:
                age_years = (time.time() - int(m.group(1)) / 1000.0) / (365.25 * 86400)
            except Exception:
                age_years = None
        elif current_date:
            try:
                from datetime import datetime
                parsed = datetime.fromisoformat(current_date.replace("Z", "+00:00"))
                age_years = (time.time() - parsed.timestamp()) / (365.25 * 86400)
            except Exception:
                age_years = None
        microsoft_provider = provider_cf in {"microsoft", "microsoft corporation"}
        row["age_years"] = age_years
        row["old_actionable"] = bool(age_years is not None and age_years > 5 and not microsoft_provider)
        try:
            config_error = int(row.get("config_error_code") or 0)
        except Exception:
            config_error = 0
        device_status = str(row.get("device_status") or "").strip().upper()
        row["device_problem"] = bool(config_error != 0 or device_status not in {"", "OK", "N/A"})
        row["attention_score"] = (4 if row["device_problem"] else 0) + (2 if row["old_actionable"] else 0) + (1 if row.get("is_signed") is False else 0)
        row.update(_official_support_profile(row.get("provider"), row.get("device_name")))
        candidates.append(row)

    candidates.sort(
        key=lambda x: (
            int(x.get("attention_score") or 0),
            int(x.get("priority") or 0),
            str(x.get("device_name") or "").casefold(),
        ),
        reverse=True,
    )

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
    selected_keys: set[tuple[str, str]] = set()
    family_order = (
        "DISPLAY", "NET", "AUDIO", "STORAGE", "BLUETOOTH",
        "SOFTWARECOMPONENT", "FIRMWARE", "SYSTEM", "USB",
    )
    for fam in family_order:
        item = next((x for x in candidates if family(x) == fam and (str(x.get("instance_id")), str(x.get("current_version"))) not in selected_keys), None)
        if item is not None:
            selected.append(item)
            selected_keys.add((str(item.get("instance_id")), str(item.get("current_version"))))
            if len(selected) >= max_count:
                return selected
    for item in candidates:
        key = (str(item.get("instance_id")), str(item.get("current_version")))
        if key in selected_keys:
            continue
        selected.append(item)
        selected_keys.add(key)
        if len(selected) >= max_count:
            break
    return selected

def _catalog_cache_file(hardware_id: str) -> Path:
    digest = hashlib.sha256(_normalize_hw_id(hardware_id).encode("utf-8", errors="ignore")).hexdigest()[:24]
    return CATALOG_CACHE_ROOT / f"{digest}.json"


def _catalog_rows_for_hardware_id(hardware_id: str) -> list[dict[str, Any]]:
    """Consulta el catálogo con caché local corta para evitar esperas repetidas.

    La caché contiene sólo metadatos públicos del catálogo. Nunca guarda credenciales
    ni inventa una actualización. Si expira, se vuelve a validar online.
    """
    cache_file = _catalog_cache_file(hardware_id)
    try:
        if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) <= CATALOG_CACHE_TTL:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(cached, list):
                return [x for x in cached if isinstance(x, dict)]
    except Exception:
        pass

    query = str(hardware_id or "").strip()
    url = CATALOG_SEARCH.format(urllib.parse.quote(query, safe=""))
    text = _http_text(url, timeout=CATALOG_HTTP_TIMEOUT)
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
        cells = [_strip_tags(x) for x in re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", fragment)]
        version = _extract_version(title, row_text)
        date_text = ""
        for cell in cells:
            if re.fullmatch(r"\s*\d{1,2}[/-]\d{1,2}[/-]\d{4}\s*", cell):
                date_text = cell.strip(); break
        rows.append({
            "update_id": guid,
            "title": title or "Paquete de controlador",
            "available_version": version,
            "available_date": date_text,
            "row_text": row_text,
            "max_download_size": _size_bytes(row_text),
        })
    try:
        CATALOG_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return rows


def _best_catalog_update_only(device: dict[str, Any]) -> dict[str, Any] | None:
    installed = str(device.get("current_version") or "").strip()
    if not installed:
        return None
    attempted = False
    successful_query = False
    last_error: Exception | None = None
    query_ids = []
    for value in list(device.get("hardware_ids") or []) + list(device.get("compatible_ids") or []):
        norm = _normalize_hw_id(value)
        if norm and norm not in query_ids:
            query_ids.append(norm)
    for hardware_id in query_ids[:6]:
        attempted = True
        try:
            rows = _catalog_rows_for_hardware_id(hardware_id)
            successful_query = True
        except DriverUpdateError as exc:
            last_error = exc
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
            support = _official_support_profile(provider, device.get("device_name"))
            return {
                **row,
                "revision": 0,
                "device_name": str(device.get("device_name") or "Dispositivo"),
                "driver_class": str(device.get("device_class") or ""),
                "provider": provider,
                "current_version": installed,
                "current_inf": str(device.get("inf_name") or ""),
                "hardware_id": hardware_id,
                "instance_id": str(device.get("instance_id") or ""),
                "is_downloaded": _cached_package_path(row.get("update_id")) is not None,
                "source": "Microsoft Update Catalog directo",
                "compatibility_source": "Hardware ID + Microsoft Update Catalog",
                "preferred_source": (support.get("official_vendor") + " oficial") if support.get("official_vendor") else "Microsoft Update Catalog",
                "official_vendor": support.get("official_vendor") or "",
                "official_url": support.get("official_url") or "",
                "bulk_install_allowed": str(device.get("device_class") or "").upper() != "FIRMWARE",
            }
    if attempted and not successful_query and last_error is not None:
        raise DriverUpdateError(str(last_error))
    return None


def _best_driver_update(device: dict[str, Any], *, force_refresh: bool = False) -> dict[str, Any] | None:
    vendor = _vendor_update_for_device(device, force_refresh=force_refresh)
    if vendor:
        return vendor
    return _best_catalog_update_only(device)


def scan_driver_updates(*, max_devices: int = 5, force_refresh: bool = False, local_inventory: Any = None, instance_ids: Iterable[str] | None = None) -> dict[str, Any]:
    """Busca drivers por Hardware ID con respuesta rápida, caché y consultas paralelas.

    V324 reutiliza primero el inventario que Análisis de Windows ya tiene en memoria.
    Así no vuelve a recorrer cientos de dispositivos con CIM antes de consultar la red.
    Si el usuario selecciona incidencias concretas, sólo se consultan esas filas.
    """
    started = time.monotonic()
    wanted = {str(x) for x in (instance_ids or []) if str(x)}
    use_global_cache = not wanted
    if not force_refresh and use_global_cache:
        cached = _read_json_cache(SCAN_CACHE_FILE, SCAN_CACHE_TTL)
        if isinstance(cached, dict) and isinstance(cached.get("items"), list):
            result = dict(cached)
            result["items"] = [dict(x) for x in (result.get("items") or []) if isinstance(x, dict)]
            for item in result["items"]:
                item["is_downloaded"] = _cached_package_path(item.get("update_id")) is not None
            result["cache_hit"] = True
            result["elapsed_seconds"] = round(time.monotonic() - started, 2)
            result["note"] = "Resultado reciente verificado · usa Buscar de nuevo después de instalar para refrescar."
            return result

    devices = _candidates_from_health_inventory(local_inventory, limit=max_devices, instance_ids=wanted) if isinstance(local_inventory, dict) else []
    if not devices:
        devices = _installed_driver_candidates(limit=max_devices, force_refresh=force_refresh)
        if wanted:
            devices = [x for x in devices if str(x.get("instance_id") or "") in wanted]
    devices = _enrich_selected_device_ids(devices)
    if isinstance(local_inventory, dict):
        peer_names = [str(x.get("DeviceName") or x.get("device_name") or "") for x in (local_inventory.get("items") or []) if isinstance(x, dict)]
        for device in devices:
            device.setdefault("system_device_names", peer_names)

    if not devices:
        result = {
            "items": [], "count": 0, "checked_devices": 0, "attention_devices": 0,
            "source": "Microsoft Update Catalog directo", "error": None,
            "elapsed_seconds": round(time.monotonic() - started, 2), "cache_hit": False,
            "note": "No se encontraron dispositivos relevantes con IDs de hardware consultables.", "device_results": [],
        }
        if use_global_cache:
            _write_json_cache(SCAN_CACHE_FILE, result)
        return result

    found: list[dict[str, Any]] = []
    errors: list[str] = []
    device_results: list[dict[str, Any]] = []
    workers = min(8, max(1, len(devices)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="CorePulseDriverCatalog") as pool:
        future_map = {pool.submit(_best_driver_update, d, force_refresh=bool(force_refresh)): d for d in devices}
        for future in as_completed(future_map):
            device = future_map[future]
            base_result = {
                "instance_id": str(device.get("instance_id") or ""),
                "device_name": str(device.get("device_name") or "Dispositivo"),
                "current_version": str(device.get("current_version") or ""),
            }
            try:
                item = future.result()
                if item:
                    found.append(item)
                    device_results.append({**base_result, "status": "UPDATE_AVAILABLE", "available_version": str(item.get("available_version") or "")})
                else:
                    device_results.append({**base_result, "status": "NO_UPDATE", "available_version": ""})
            except Exception as exc:
                message = str(exc)
                errors.append(message)
                device_results.append({**base_result, "status": "ERROR", "available_version": "", "error": message})
    found.sort(key=lambda x: (str(x.get("driver_class") or "").upper() == "FIRMWARE", str(x.get("device_name") or "").casefold()))
    result = {
        "items": found,
        "count": len(found),
        "checked_devices": len(devices),
        "attention_devices": sum(1 for d in devices if int(d.get("attention_score") or 0) > 0),
        "source": "Fuentes oficiales + Microsoft Update Catalog",
        "error": None if found or not errors else errors[0],
        "warnings": errors[:3],
        "device_results": device_results,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "cache_hit": False,
        "note": "Resolución multi-fuente: fabricante oficial cuando puede validarse la familia; Catalog por Hardware/Compatible ID como fallback. Firmware queda fuera de instalación masiva.",
    }
    if use_global_cache:
        _write_json_cache(SCAN_CACHE_FILE, result)
    return result

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
    candidates = sorted([p for p in root.iterdir() if p.is_file() and p.suffix.lower() in {".cab", ".msu", ".zip", ".exe"}])
    return candidates[0] if candidates else None


def _filename_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    name = urllib.parse.unquote(os.path.basename(path)).strip()
    return name or "driver_package.cab"



def _vendor_package_url(metadata: dict[str, Any]) -> tuple[str, str]:
    url = str(metadata.get("vendor_download_url") or "").strip()
    filename = str(metadata.get("vendor_filename") or "").strip()
    if url:
        return url, filename or _filename_from_url(url)
    page_url = str(metadata.get("vendor_page_url") or metadata.get("official_url") or "").strip()
    if not page_url:
        raise DriverUpdateError("La fuente oficial no expuso una página de descarga.")
    page = _vendor_page_text(page_url, force_refresh=True)
    if not filename:
        plain = _strip_tags(page)
        m = re.search(r"(?i)\b([A-Za-z0-9_.-]+\.(?:exe|zip))\b", plain)
        filename = m.group(1) if m else "driver-oficial.exe"
    url = _extract_direct_vendor_url(page, filename)
    if not url:
        raise DriverUpdateError("El fabricante confirmó la actualización, pero su página no expuso una URL directa automatizable. Usa el botón Fabricante para descargarla manualmente.")
    return url, filename


def _download_vendor_package(update_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    cached = _cached_package_path(update_id)
    if cached is not None and cached.stat().st_size > 0:
        return {"ok": True, "mode": "download", "downloaded": True, "path": str(cached), "source": str(metadata.get("source") or "Fabricante oficial")}
    url, filename = _vendor_package_url(metadata)
    root = _cache_dir(update_id)
    root.mkdir(parents=True, exist_ok=True)
    target = root / (filename or _filename_from_url(url))
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as response, open(target, "wb") as fh:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
    except Exception as exc:
        try: target.unlink(missing_ok=True)
        except Exception: pass
        raise DriverUpdateError(f"No se pudo descargar el paquete oficial: {exc}") from exc
    expected = str(metadata.get("vendor_sha256") or "").strip().upper()
    if expected:
        actual = hashlib.sha256(target.read_bytes()).hexdigest().upper()
        if actual != expected:
            try: target.unlink(missing_ok=True)
            except Exception: pass
            raise DriverUpdateError("El SHA-256 del paquete oficial no coincide. CorePulse canceló la descarga.")
    return {"ok": True, "mode": "download", "downloaded": True, "path": str(target), "bytes": int(target.stat().st_size), "source": str(metadata.get("source") or "Fabricante oficial")}


def _authenticode_status(path: Path) -> dict[str, Any]:
    script = r'''$ErrorActionPreference='SilentlyContinue'
$s=Get-AuthenticodeSignature -FilePath $env:COREPULSE_PACKAGE
[pscustomobject]@{status=[string]$s.Status;subject=if($s.SignerCertificate){[string]$s.SignerCertificate.Subject}else{''}} | ConvertTo-Json -Compress'''
    try:
        result = _run_ps(script, timeout=45, env={"COREPULSE_PACKAGE": str(path)})
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def download_driver_update(update_id: str, revision: int = 0, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Descarga desde fabricante oficial o Catalog, sin Windows Update Agent."""
    metadata = metadata if isinstance(metadata, dict) else {}
    if str(metadata.get("source_kind") or "") == "vendor_installer" or str(update_id).startswith("vendor-"):
        return _download_vendor_package(update_id, metadata)
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


def backup_installed_driver(inf_name: str | None, device_name: str = "") -> dict[str, Any]:
    """Exporta el paquete actual del Driver Store antes de reemplazarlo.

    Sólo los paquetes OEM (oemNN.inf) se exportan de forma individual. Los drivers
    inbox de Windows se consideran recuperables por el propio sistema y no se copian.
    """
    inf = str(inf_name or "").strip()
    if not inf:
        return {"ok": True, "skipped": True, "reason": "INF actual no disponible"}
    if not re.fullmatch(r"(?i)oem\d+\.inf", inf):
        return {"ok": True, "skipped": True, "reason": "Driver inbox de Windows"}
    safe_name = re.sub(r"[^0-9A-Za-z._-]+", "_", str(device_name or "driver")).strip("_")[:72] or "driver"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = BACKUP_ROOT / f"{stamp}_{safe_name}_{inf[:-4]}"
    target.mkdir(parents=True, exist_ok=True)
    pnputil = shutil.which("pnputil.exe") or shutil.which("pnputil") or str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "pnputil.exe")
    proc = subprocess.run(
        [pnputil, "/export-driver", inf, str(target)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise DriverUpdateError("No se pudo respaldar el driver actual antes de instalar. " + (output[-1200:] or f"PnPUtil {proc.returncode}"))
    return {"ok": True, "skipped": False, "path": str(target), "inf_name": inf}


def install_driver_update(update_id: str, revision: int = 0, *, current_inf: str | None = None, device_name: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Instala desde fabricante oficial o PnPUtil según el tipo de paquete."""
    if os.name != "nt":
        raise DriverUpdateError("La instalación de controladores está disponible sólo en Windows.")
    metadata = metadata if isinstance(metadata, dict) else {}
    package = _cached_package_path(update_id)
    if package is None:
        download_driver_update(update_id, revision, metadata=metadata)
        package = _cached_package_path(update_id)
    if package is None:
        raise DriverUpdateError("No se encontró el paquete descargado.")

    if str(metadata.get("source_kind") or "") == "vendor_installer" or str(update_id).startswith("vendor-"):
        if package.suffix.lower() != ".exe":
            raise DriverUpdateError("El paquete oficial no tiene un formato instalable reconocido.")
        sig = _authenticode_status(package)
        if str(sig.get("status") or "").casefold() != "valid":
            raise DriverUpdateError("La firma Authenticode del instalador oficial no es válida. CorePulse no lo ejecutará.")
        expected_vendor = str(metadata.get("official_vendor") or "").casefold()
        subject = str(sig.get("subject") or "")
        if expected_vendor and expected_vendor not in subject.casefold():
            raise DriverUpdateError(f"La firma es válida, pero el firmante no coincide con {metadata.get('official_vendor')}. CorePulse canceló la instalación.")
        backup = backup_installed_driver(current_inf, device_name)
        script = r'''$ErrorActionPreference='Stop'
$p=$env:COREPULSE_VENDOR_INSTALLER
$proc=Start-Process -FilePath $p -Verb RunAs -Wait -PassThru
[pscustomobject]@{ok=($proc.ExitCode -eq 0);exit_code=[int]$proc.ExitCode}|ConvertTo-Json -Compress'''
        result = _run_ps(script, timeout=900, env={"COREPULSE_VENDOR_INSTALLER": str(package)})
        ok = bool(isinstance(result, dict) and result.get("ok"))
        if not ok:
            raise DriverUpdateError(f"El instalador oficial terminó con código {result.get('exit_code') if isinstance(result, dict) else 'desconocido'}.")
        invalidate_driver_caches()
        return {"ok": True, "mode": "vendor_install", "result_code": int(result.get("exit_code") or 0), "result_label": "CORRECTO", "reboot_required": False, "path": str(package), "backup": backup, "source": str(metadata.get("source") or "Fabricante oficial"), "output": "Instalador oficial completado."}

    root = _cache_dir(update_id)
    extract_dir = _extract_package(package, root)
    infs = list(extract_dir.rglob("*.inf"))
    if not infs:
        raise DriverUpdateError("El paquete no contiene archivos INF instalables.")
    if not _valid_catalog_signature(extract_dir):
        raise DriverUpdateError("No se pudo validar una firma de catálogo del paquete. CorePulse no lo instalará.")
    backup = backup_installed_driver(current_inf, device_name)
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
    invalidate_driver_caches()
    return {
        "ok": True, "mode": "install", "result_code": int(proc.returncode),
        "result_label": "CORRECTO", "reboot_required": reboot,
        "path": str(package), "backup": backup,
        "source": "PnPUtil + Microsoft Update Catalog directo",
        "output": output[-4000:],
    }


def download_all_driver_updates(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for item in list(items or []):
        uid = str((item or {}).get("update_id") or "")
        if not uid:
            continue
        try:
            result = download_driver_update(uid, int((item or {}).get("revision") or 0), metadata=item)
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
            result = install_driver_update(
                uid, int((item or {}).get("revision") or 0),
                current_inf=str((item or {}).get("current_inf") or ""),
                device_name=str((item or {}).get("device_name") or ""),
                metadata=item,
            )
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
    "backup_installed_driver",
    "invalidate_driver_caches",
]
