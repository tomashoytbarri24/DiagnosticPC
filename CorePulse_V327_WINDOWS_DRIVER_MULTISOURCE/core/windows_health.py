"""Analizadores de Windows para inicio, servicios, eventos, drivers, cambios y restore.

Todas las operaciones degradan a N/A fuera de Windows y ninguna desactiva servicios
ni controladores automáticamente.
"""
from __future__ import annotations

import ctypes
import json
from datetime import datetime, timezone
import logging
import os
import platform
import re
import subprocess
from core.cancellable_process import run as run_cancellable
import time
from pathlib import Path
from core.runtime_paths import data_path
from typing import Any, Dict, List

import psutil

HW_STATE = data_path('hardware_baseline.json')
logger = logging.getLogger('CorePulse.WindowsHealth')


def _friendly_ps_error(raw: str, returncode=None) -> str:
    """Convierte stderr técnico en un mensaje útil para UI. El detalle queda en logs."""
    value = str(raw or '').strip()
    low = value.lower()
    if 'access is denied' in low or 'acceso denegado' in low or 'unauthorizedaccess' in low:
        return 'Windows rechazó la consulta por permisos. Ejecuta CorePulse como administrador y vuelve a intentarlo.'
    if 'get-winevent' in low and ('does not exist' in low or 'no se encuentra' in low or 'cannot find' in low):
        return 'El registro de eventos requerido no está disponible en este Windows.'
    if 'parsererror' in low or 'parser error' in low or 'canalización vac' in low:
        return 'Windows no pudo interpretar la consulta interna. El detalle técnico fue registrado en los logs.'
    if 'timed out' in low or 'tiempo de espera' in low:
        return 'La consulta de Windows superó el tiempo límite.'
    if returncode not in (None, 0):
        return f'Windows no pudo completar la consulta (código {returncode}). El detalle técnico fue registrado en los logs.'
    return 'Windows no pudo completar esta consulta. El detalle técnico fue registrado en los logs.'


def _ps(script: str, timeout: int = 25):
    """Ejecuta PowerShell sin consola visible y conserva el error técnico sólo en logs."""
    if platform.system() != 'Windows':
        return None, 'Windows requerido'
    # Windows PowerShell 5.1 usa la página de códigos de la consola por defecto.
    # Forzamos UTF-8 para que JSON, nombres de dispositivos y mensajes con acentos
    # lleguen íntegros a Python.
    prefix = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$OutputEncoding=[System.Text.Encoding]::UTF8; "
    )
    cmd = [
        'powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
        '-ExecutionPolicy', 'Bypass', '-Command', prefix + str(script),
    ]
    try:
        cp = run_cancellable(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            shell=False,
        )
        if cp.returncode != 0:
            raw = (cp.stderr or cp.stdout or f'PowerShell exit {cp.returncode}').strip()
            logger.error('[WINDOWS_HEALTH][POWERSHELL] returncode=%s stderr=%s', cp.returncode, raw[:4000])
            return None, _friendly_ps_error(raw, cp.returncode)
        return (cp.stdout or '').strip(), None
    except subprocess.TimeoutExpired as exc:
        logger.error('[WINDOWS_HEALTH][POWERSHELL] timeout=%ss command=%s', timeout, str(script)[:800])
        return None, 'La consulta de Windows superó el tiempo límite.'
    except Exception as exc:
        logger.exception('[WINDOWS_HEALTH][POWERSHELL] fallo inesperado')
        return None, _friendly_ps_error(str(exc))


def _json_ps(script: str, timeout: int = 30):
    """Ejecuta un bloque PowerShell y serializa su RESULTADO de forma segura.

    No concatena ``| ConvertTo-Json`` al final del texto recibido. En Windows
    PowerShell 5.1, si el script termina con un salto de línea, eso puede dejar
    el operador ``|`` al comienzo de una línea y producir ``ParserError:
    no se permiten elementos de canalización vacíos``.
    """
    wrapped = f"""
$ErrorActionPreference='Stop'
$result = & {{
{script}
}}
if ($null -eq $result) {{
    Write-Output '[]'
}} else {{
    ConvertTo-Json -InputObject @($result) -Depth 6 -Compress
}}
"""
    out, err = _ps(wrapped, timeout=timeout)
    if err:
        return [], err
    if not out:
        return [], None
    try:
        obj = json.loads(out)
        if obj is None:
            return [], None
        return obj if isinstance(obj, list) else [obj], None
    except Exception as exc:
        logger.error('[WINDOWS_HEALTH][JSON] salida inválida: %s', str(out)[:4000])
        return [], 'Windows respondió con datos que CorePulse no pudo interpretar. El detalle técnico fue registrado en los logs.'


def is_admin():
    if platform.system() != 'Windows': return False
    try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception: return False


def analyze_startup() -> Dict[str, Any]:
    """Analiza el inicio con inventario reversible y evidencia de impacto de Windows.

    V121 mantiene compatibilidad con la política histórica NO_AUTO_DISABLE: nunca
    desactiva por sí solo. Las acciones explícitas se limitan a entradas de usuario
    que el módulo ``startup_analyzer`` puede restaurar exactamente.
    """
    try:
        from core.startup_analyzer import collect_startup_items
        result = collect_startup_items()
    except Exception as exc:
        logger.exception('[WINDOWS_HEALTH] Falló Startup Analyzer mejorado')
        result = {'items': [], 'count': 0, 'error': f'{type(exc).__name__}: {exc}', 'source': 'N/A', 'policy': 'USER_REVERSIBLE_ONLY_NO_SYSTEM_AUTO_DISABLE'}

    # Win32_StartupCommand conserva cobertura adicional para entradas que Windows
    # expone fuera de los orígenes reversibles conocidos. Esas filas se muestran
    # sólo en observación: CorePulse no intenta modificarlas.
    wmi_script = r"""
    Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location,User
    """
    wmi_rows, _wmi_err = _json_ps(wmi_script, timeout=20)
    known = set()
    for item in result.get('items') or []:
        if isinstance(item, dict):
            known.add((str(item.get('name') or '').casefold(), str(item.get('command') or '').casefold()))
    for index, row in enumerate(wmi_rows):
        if not isinstance(row, dict):
            continue
        sig = (str(row.get('Name') or '').casefold(), str(row.get('Command') or '').casefold())
        if sig in known:
            continue
        result.setdefault('items', []).append({
            'source_id': f'wmi:{index}:{row.get("Name") or "startup"}',
            'source_type': 'wmi_observe_only', 'scope': 'WINDOWS',
            'name': row.get('Name'), 'command': row.get('Command'),
            'location': row.get('Location'), 'user': row.get('User'),
            'publisher': 'N/A', 'running_memory_mb': None, 'impact': 'NO_MEDIDO',
            'enabled': True, 'state': 'Habilitado', 'safe_to_disable': False,
            'action_reason': 'Windows expone esta entrada sin un origen reversible que CorePulse pueda modificar con seguridad.',
        })

    # Conserva la evidencia Diagnostics-Performance 101 para clasificar impacto
    # cuando Windows ha registrado una degradación real del arranque.
    perf_script = r"""
    $start=(Get-Date).AddDays(-30);
    Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=101; StartTime=$start} -ErrorAction SilentlyContinue |
      Select-Object -First 80 TimeCreated,Message
    """
    perf_rows, _perf_err = _json_ps(perf_script, timeout=20)
    perf_text = '\n'.join(str(x.get('Message') or '') for x in perf_rows if isinstance(x, dict)).lower()
    for item in result.get('items') or []:
        if not isinstance(item, dict) or not item.get('enabled'):
            continue
        exe = Path(str(item.get('executable') or '')).name.lower()
        name = str(item.get('name') or '').lower()
        degraded = bool((exe and exe in perf_text) or (name and name in perf_text))
        item['degradation_event_seen'] = degraded
        if degraded:
            item['impact'] = 'ALTO (evento de degradación)'
        item['impact_basis'] = 'Evento 101 de Diagnostics-Performance cuando existe; RAM actual sólo como contexto secundario'
    rows = result.get('items') or []
    result['count'] = len(rows)
    result['enabled_count'] = sum(1 for x in rows if isinstance(x, dict) and x.get('enabled', True))
    result['disabled_count'] = sum(1 for x in rows if isinstance(x, dict) and not x.get('enabled', True))
    result['source'] = str(result.get('source') or '') + ' + Win32_StartupCommand + Diagnostics-Performance 101'
    result['policy'] = 'NO_AUTO_DISABLE_USER_REVERSIBLE_ONLY'
    return result


def analyze_services(limit: int | None = None) -> Dict[str, Any]:
    # V0.10.2.81w — el análisis normal ya no corta arbitrariamente en 250.
    # `limit` se conserva sólo para pruebas/diagnóstico dirigido.
    limit_clause = ''
    if limit is not None:
        try:
            safe_limit = max(1, int(limit))
            limit_clause = f' | Select-Object -First {safe_limit}'
        except Exception:
            limit_clause = ''
    script = rf"""
    Get-CimInstance Win32_Service | Select-Object Name,DisplayName,State,StartMode,PathName,ProcessId{limit_clause}
    """
    rows, err = _json_ps(script, timeout=35)
    items = []
    for row in rows:
        if not isinstance(row, dict): continue
        pid = row.get('ProcessId')
        mem = None
        if pid:
            try: mem = psutil.Process(int(pid)).memory_info().rss / (1024*1024)
            except Exception: pass
        path = str(row.get('PathName') or '')
        windows_component = ('\\windows\\system32' in path.lower() or path.lower().startswith('c:\\windows'))
        items.append({**row, 'memory_mb': mem, 'windows_component': windows_component,
                      'load_flag': 'PESADO' if mem is not None and mem >= 300 else 'NORMAL' if mem is not None else 'N/A',
                      'action_policy': 'OBSERVE_ONLY_CRITICAL_SERVICES_NEVER_AUTO_DISABLED'})
    items.sort(key=lambda x: (x.get('memory_mb') is not None, x.get('memory_mb') or 0), reverse=True)
    return {'items': items, 'count': len(items), 'error': err, 'source': 'Win32_Service + psutil', 'policy': 'ANALYZE_ONLY'}


def _classify_stability_event(row: Dict[str, Any]) -> str:
    """Clasifica eventos por ID + proveedor real, nunca sólo por número de evento."""
    try:
        eid = int(row.get('Id') or 0)
    except Exception:
        eid = 0
    provider = str(row.get('ProviderName') or '').strip().lower()

    # WHEA: los IDs 18/19/20/46 sólo son errores de hardware cuando el
    # proveedor es realmente Microsoft-Windows-WHEA-Logger.
    if provider in ('microsoft-windows-whea-logger', 'whea-logger') or 'whea-logger' in provider:
        return 'whea' if eid in (18, 19, 20, 46) else 'other'

    # Kernel-Power 41 indica que Windows detectó un arranque después de un
    # apagado/reinicio no limpio. No identifica por sí solo la causa física.
    if eid == 41 and ('microsoft-windows-kernel-power' in provider or provider == 'kernel-power'):
        return 'kernel_power'

    # EventLog 6008 registra un apagado inesperado observado por Windows.
    if eid == 6008 and provider in ('eventlog', 'event log'):
        return 'unexpected_shutdown'

    # WER-SystemErrorReporting 1001 es la evidencia de bugcheck/BSOD que
    # queremos distinguir de otros eventos 1001 usados por proveedores ajenos.
    if eid == 1001 and (
        'wer-systemerrorreporting' in provider
        or 'systemerrorreporting' in provider
        or provider.endswith('bugcheck')
    ):
        return 'bsod_bugcheck'

    # Errores de aplicaciones se muestran como contexto, pero no se convierten
    # en WHEA/BSOD ni en evidencia de fallo de hardware.
    if eid == 1000 and provider == 'application error':
        return 'app_error'
    if eid == 1002 and provider == 'application hang':
        return 'app_hang'
    return 'other'


def _stability_event_user_text(kind: str) -> tuple[str, str]:
    labels = {
        'bsod_bugcheck': (
            'Pantallazo azul (BSOD)',
            'Windows registró un pantallazo azul. Si se repite, conviene revisar el código de detención, controladores y hardware relacionado.',
        ),
        'whea': (
            'Error de hardware (WHEA)',
            'Windows registró un error de hardware mediante WHEA. Si se repite, conviene revisar temperaturas, CPU, RAM, GPU, alimentación o el componente indicado por el evento.',
        ),
        'kernel_power': (
            'Reinicio o apagado no limpio',
            'Windows detectó que el equipo volvió a iniciar sin un cierre normal. Puede deberse a corte de energía, bloqueo, reinicio forzado u otra causa; este evento por sí solo no identifica el origen.',
        ),
        'unexpected_shutdown': (
            'Apagado inesperado',
            'Windows registró un apagado inesperado. Conviene correlacionarlo con otros eventos cercanos antes de atribuir una causa.',
        ),
        'app_error': (
            'Aplicación cerrada con error',
            'Una aplicación se cerró con error. Esto no equivale a un pantallazo azul ni a un fallo de hardware.',
        ),
        'app_hang': (
            'Aplicación sin responder',
            'Una aplicación dejó de responder. Esto no equivale a un pantallazo azul ni a un fallo de hardware.',
        ),
    }
    return labels.get(kind, ('Evento relacionado', 'Evento registrado por Windows sin clasificación crítica de CorePulse.'))


def _event_epoch(value: Any) -> float | None:
    """Convierte TimeCreated de PowerShell a epoch sin inventar una hora."""
    raw = str(value or '').strip()
    if not raw:
        return None
    match = re.search(r'/Date\((\d+)', raw)
    if match:
        try:
            return int(match.group(1)) / 1000.0
        except Exception:
            return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except Exception:
        return None


def _event_display_time(value: Any) -> str:
    raw = str(value or '').strip()
    epoch = _event_epoch(raw)
    if epoch is None:
        return raw or 'N/A'
    try:
        return datetime.fromtimestamp(epoch).strftime('%d-%m-%Y %H:%M')
    except Exception:
        return raw or 'N/A'


def _fallback_app_name(message: Any) -> str | None:
    """Extrae nombre de aplicación sólo desde texto real de Event Log si el payload no lo entregó."""
    msg = str(message or '')
    patterns = (
        r'Faulting application name:\s*([^,\r\n]+)',
        r'Nombre de (?:la )?aplicaci[oó]n con errores:\s*([^,\r\n]+)',
        r'Nombre de (?:la )?aplicaci[oó]n que presenta errores:\s*([^,\r\n]+)',
        r'Nombre de aplicaci[oó]n:\s*([^,\r\n]+)',
    )
    for pattern in patterns:
        m = re.search(pattern, msg, flags=re.IGNORECASE)
        if m:
            value = str(m.group(1) or '').strip()
            return value or None
    return None


def _fallback_module_name(message: Any) -> str | None:
    msg = str(message or '')
    patterns = (
        r'Faulting module name:\s*([^,\r\n]+)',
        r'Nombre del m[oó]dulo con errores:\s*([^,\r\n]+)',
        r'Nombre del m[oó]dulo que presenta errores:\s*([^,\r\n]+)',
    )
    for pattern in patterns:
        m = re.search(pattern, msg, flags=re.IGNORECASE)
        if m:
            value = str(m.group(1) or '').strip()
            return value or None
    return None


def _dedupe_exact_stability_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Elimina sólo duplicados exactos del registro; no fusiona incidentes distintos."""
    output = []
    seen = set()
    for item in items:
        record_id = item.get('RecordId')
        if record_id not in (None, ''):
            key = ('record', str(item.get('ProviderName') or '').lower(), str(record_id))
        else:
            key = (
                'fallback', str(item.get('kind') or ''), str(item.get('TimeCreated') or ''),
                str(item.get('Id') or ''), str(item.get('ApplicationName') or '').lower(),
                str(item.get('FaultingModule') or '').lower(), str(item.get('Message') or '')[:160],
            )
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _unique_power_incidents(items: List[Dict[str, Any]], merge_window_seconds: int = 300) -> int:
    """Evita contar Kernel-Power 41 + EventLog 6008 como dos apagados cuando son el mismo incidente."""
    events = [x for x in items if x.get('kind') in ('kernel_power', 'unexpected_shutdown')]
    epochs = sorted(e for e in (_event_epoch(x.get('TimeCreated')) for x in events) if e is not None)
    missing = sum(1 for x in events if _event_epoch(x.get('TimeCreated')) is None)
    incidents = 0
    last = None
    for epoch in epochs:
        if last is None or abs(epoch - last) > merge_window_seconds:
            incidents += 1
        last = epoch
    return incidents + missing


def _stability_summary(counts: Dict[str, int], days: int, *, power_incidents: int | None = None, affected_apps: int = 0) -> str:
    bsod = int(counts.get('bsod_bugcheck') or 0)
    whea = int(counts.get('whea') or 0)
    power = int(power_incidents if power_incidents is not None else (int(counts.get('kernel_power') or 0) + int(counts.get('unexpected_shutdown') or 0)))
    apps = int(counts.get('app_error') or 0) + int(counts.get('app_hang') or 0)
    if bsod or whea:
        parts = []
        if bsod:
            parts.append(f'{bsod} pantallazo(s) azul(es)')
        if whea:
            parts.append(f'{whea} error(es) WHEA de hardware')
        return 'Se detectaron ' + ' y '.join(parts) + f' en los últimos {days} días. Revisa los eventos listados antes de concluir la causa.'
    if power:
        return f'No se detectaron BSOD ni errores WHEA reales. Windows registró {power} apagado(s) o reinicio(s) no limpio(s) en los últimos {days} días.'
    if apps:
        affected = f' en {affected_apps} aplicación(es)' if affected_apps else ''
        return f'No se detectaron fallos críticos del sistema. Windows registró {apps} evento(s) de cierre o bloqueo de aplicaciones{affected} en los últimos {days} días.'
    return f'No se detectaron BSOD, errores WHEA ni apagados inesperados en los últimos {days} días.'


def _normalize_exception_code(value: Any) -> str:
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    if raw.startswith('0x'):
        return raw
    # Event 1000 a veces expone el código sin prefijo.
    if re.fullmatch(r'[0-9a-f]{8}', raw):
        return '0x' + raw
    return raw


def _application_action_guidance(stat: Dict[str, Any]) -> Dict[str, Any]:
    """Construye orientación escalonada sin convertir correlación en causalidad.

    Event ID 1000/1002 confirma que una aplicación falló o dejó de responder.
    Por sí solo NO demuestra corrupción de instalación, RAM defectuosa, driver
    culpable ni DLL de Windows dañada. La recomendación se limita a pasos cuya
    intensidad está justificada por la evidencia disponible.
    """
    name = str(stat.get('ApplicationName') or 'Aplicación').strip() or 'Aplicación'
    total = max(0, int(stat.get('Total') or 0))
    errors = max(0, int(stat.get('Errors') or 0))
    hangs = max(0, int(stat.get('Hangs') or 0))
    module = str(stat.get('TopModule') or '').strip()
    exception = _normalize_exception_code(stat.get('TopException'))
    module_count = max(0, int(stat.get('TopModuleCount') or 0))
    exception_count = max(0, int(stat.get('TopExceptionCount') or 0))
    version = str(stat.get('ApplicationVersion') or '').strip()

    evidence = []
    if errors:
        evidence.append(f'{errors} cierre(s) con error')
    if hangs:
        evidence.append(f'{hangs} bloqueo(s)')
    if module:
        if module_count > 1:
            evidence.append(f'módulo más frecuente: {module} ({module_count} evento(s))')
        else:
            evidence.append(f'módulo registrado: {module}')
    if exception:
        if exception_count > 1:
            evidence.append(f'código más frecuente: {exception} ({exception_count} evento(s))')
        else:
            evidence.append(f'código registrado: {exception}')
    if version:
        evidence.append(f'versión: {version}')

    finding = (
        f'Windows registró {total} evento(s) de estabilidad para {name}: '
        f'{errors} cierre(s) con error y {hangs} bloqueo(s).'
    )
    finding_confidence = 'ALTA' if total > 0 else 'N/A'

    # La repetición aumenta la confianza en el PATRÓN, no en su causa.
    if total >= 5:
        interpretation = 'El fallo es repetitivo y merece seguimiento; la frecuencia no identifica por sí sola la causa.'
    elif total >= 2:
        interpretation = 'El fallo se repitió más de una vez, pero todavía no determina una causa concreta.'
    else:
        interpretation = 'Hay un incidente registrado. Un evento aislado no justifica una reparación invasiva.'

    if exception == '0xc0000005':
        interpretation += ' Windows registró una violación de acceso a memoria dentro del proceso; este código no demuestra RAM defectuosa ni identifica el componente culpable.'
    elif exception == '0xe0434352':
        interpretation += ' Windows registró una excepción administrada/CLR; el código no contiene por sí solo la excepción .NET exacta ni su origen.'
    elif exception == '0xc0000409':
        interpretation += ' Windows registró una terminación de tipo fast-fail/stack-buffer-overrun; el evento no identifica qué componente provocó el estado.'
    elif exception == '0xc0000374':
        interpretation += ' Windows registró corrupción de heap dentro del proceso; el evento no permite atribuir la causa a RAM, Windows o la aplicación sin más evidencia.'

    if module and module.lower() in ('kernelbase.dll', 'ntdll.dll'):
        interpretation += f' {module} aparece como módulo asociado al cierre, pero eso no demuestra que esa DLL de Windows esté dañada.'

    cause = 'No determinada con la evidencia disponible en estos eventos.'
    cause_confidence = 'BAJA'

    if total <= 1:
        action = (
            f'Comprueba si {name} vuelve a fallar antes de hacer cambios. '
            'Si no se repite, conserva el evento como antecedente y evita reinstalar de entrada.'
        )
    else:
        action = (
            f'Comprueba si existe una actualización oficial de {name} y, si la aplicación ofrece una función de verificar o reparar archivos, úsala primero. '
            'Después reproduce el escenario y revisa si aparecen eventos nuevos.'
        )

    if exception == '0xe0434352':
        action += ' Si el fabricante de la aplicación exige un runtime .NET concreto, verifica ese requisito con su instalador o documentación oficial.'
    elif exception in ('0xc0000005', '0xc0000409', '0xc0000374'):
        action += ' Si usas extensiones, plugins u overlays dentro de esa aplicación, puedes desactivarlos temporalmente sólo para aislar la causa y volver a probar.'

    escalation = (
        f'Considera reparar o reinstalar {name} sólo si el fallo continúa después de actualizar/verificar y los eventos siguen concentrados en esa aplicación. '
        'Si el mismo patrón comienza a aparecer en varias aplicaciones no relacionadas, amplía el diagnóstico a controladores, memoria y estabilidad general antes de reinstalar programas uno por uno.'
    )

    return {
        'kind': 'application',
        'title': f'{name} · {total} evento(s)',
        'finding': finding,
        'finding_confidence': finding_confidence,
        'interpretation': interpretation,
        'cause': cause,
        'cause_confidence': cause_confidence,
        'action': action,
        'escalation': escalation,
        'evidence': ' · '.join(evidence) if evidence else 'Evento de aplicación registrado por Windows',
        'application': name,
    }


def _stability_action_plan(
    counts: Dict[str, int],
    days: int,
    *,
    power_incidents: int = 0,
    app_stats: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Plan evidence-gated: hallazgo confirmado != causa confirmada.

    La frecuencia sólo prioriza qué revisar primero. Ningún umbral convierte un
    evento de aplicación en una orden automática de reparar/reinstalar.
    """
    actions: List[Dict[str, Any]] = []
    bsod = max(0, int(counts.get('bsod_bugcheck') or 0))
    whea = max(0, int(counts.get('whea') or 0))
    power = max(0, int(power_incidents or 0))

    if whea:
        actions.append({
            'kind': 'whea',
            'title': f'Errores de hardware WHEA · {whea}',
            'finding': f'Windows registró {whea} evento(s) del proveedor Microsoft-Windows-WHEA-Logger en los últimos {days} días.',
            'finding_confidence': 'ALTA',
            'interpretation': 'WHEA confirma que Windows recibió un registro de error de hardware/firmware; este resumen no identifica por sí solo el componente exacto.',
            'cause': 'Componente exacto no determinado con el resumen disponible.',
            'cause_confidence': 'MEDIA',
            'action': 'Abre el detalle del evento WHEA y correlaciónalo con temperaturas, carga, firmware y el componente que Windows indique antes de cambiar piezas o controladores.',
            'escalation': 'Si el mismo componente o banco/CPU/bus aparece repetidamente, pasa a un diagnóstico dirigido de ese componente. No reemplaces hardware sólo por el contador.',
            'evidence': f'{whea} evento(s) Microsoft-Windows-WHEA-Logger en {days} días',
        })
    if bsod:
        actions.append({
            'kind': 'bsod',
            'title': f'Pantallazos azules · {bsod}',
            'finding': f'Windows registró {bsod} bugcheck(s) en los últimos {days} días.',
            'finding_confidence': 'ALTA',
            'interpretation': 'El bugcheck confirma un fallo del sistema, pero el contador por sí solo no identifica el driver o componente responsable.',
            'cause': 'No determinada con el contador de bugchecks.',
            'cause_confidence': 'BAJA',
            'action': 'Revisa el código de detención y, cuando exista, el minidump asociado. Correlaciona fecha/hora con drivers, temperaturas y cambios recientes.',
            'escalation': 'Sólo aplica una corrección dirigida cuando el stop code, dump o patrón repetido apunte al mismo componente/driver.',
            'evidence': f'{bsod} evento(s) de bugcheck registrados por Windows en {days} días',
        })
    if power:
        actions.append({
            'kind': 'power',
            'title': f'Apagados o reinicios no limpios · {power}',
            'finding': f'Windows registró {power} incidente(s) de apagado/reinicio no limpio en los últimos {days} días.',
            'finding_confidence': 'ALTA',
            'interpretation': 'El evento confirma que Windows no terminó el apagado normalmente; no permite saber si fue corte de energía, botón forzado, temperatura, fuente u otra causa.',
            'cause': 'No determinada con Kernel-Power/EventLog por sí solos.',
            'cause_confidence': 'BAJA',
            'action': 'Primero confirma si esos reinicios fueron intencionales o hubo cortes de energía conocidos. Si fueron inesperados, revisa los eventos inmediatamente anteriores y las temperaturas/alimentación.',
            'escalation': 'Si vuelve a ocurrir sin causa conocida, correlaciona cada incidente con sensores y eventos previos antes de concluir que existe una falla de hardware.',
            'evidence': f'{power} incidente(s) deduplicado(s) de Kernel-Power/EventLog en {days} días',
        })

    stats = [x for x in (app_stats or []) if isinstance(x, dict)]
    stats.sort(key=lambda x: (-int(x.get('Total') or 0), str(x.get('ApplicationName') or '').lower()))
    for stat in stats[:3]:
        actions.append(_application_action_guidance(stat))

    if not actions:
        actions.append({
            'kind': 'none',
            'title': 'Sin acciones prioritarias',
            'finding': f'No se detectaron eventos de estabilidad prioritarios en los últimos {days} días.',
            'finding_confidence': 'ALTA',
            'interpretation': 'CorePulse no encontró BSOD, WHEA, apagados no limpios ni fallos de aplicaciones dentro del período analizado.',
            'cause': 'No aplica.',
            'cause_confidence': 'N/A',
            'action': 'No es necesario realizar cambios por esta sección. Continúa el monitoreo normal.',
            'escalation': 'Vuelve a analizar si aparece un síntoma nuevo o Windows registra eventos de estabilidad.',
            'evidence': 'Sin eventos clasificados en el período analizado',
        })
    return actions


def analyze_crashes(days: int = 7, max_events: int = 500) -> Dict[str, Any]:
    """Analiza estabilidad con conteos completos por categoría y detalle paginable.

    `max_events` limita sólo cuántos detalles se transfieren a la UI; los contadores
    se calculan sobre todas las coincidencias reales del período. Así una categoría
    ruidosa no puede ocultar WHEA/BSOD/Kernel-Power más antiguos.
    """
    days = max(1, min(90, int(days)))
    max_events = max(25, min(2000, int(max_events)))
    script = rf"""
    $start=(Get-Date).AddDays(-{days});
    function Convert-CorePulseEvent($event, [string]$kind) {{
        $props=@($event.Properties | ForEach-Object {{ $_.Value }});
        $app=$null; $module=$null; $appVersion=$null; $exceptionCode=$null; $appPath=$null; $modulePath=$null;
        if($kind -eq 'app_error') {{
            if($props.Count -gt 0) {{ $app=[string]$props[0] }};
            if($props.Count -gt 1) {{ $appVersion=[string]$props[1] }};
            if($props.Count -gt 3) {{ $module=[string]$props[3] }};
            if($props.Count -gt 6) {{ $exceptionCode=[string]$props[6] }};
            if($props.Count -gt 10) {{ $appPath=[string]$props[10] }};
            if($props.Count -gt 11) {{ $modulePath=[string]$props[11] }};
        }} elseif($kind -eq 'app_hang') {{
            if($props.Count -gt 0) {{ $app=[string]$props[0] }};
            if($props.Count -gt 1) {{ $appVersion=[string]$props[1] }};
        }}
        [pscustomobject]@{{
            TimeCreated=if($event.TimeCreated){{$event.TimeCreated.ToString('o')}}else{{$null}};
            Id=$event.Id; ProviderName=$event.ProviderName; LevelDisplayName=$event.LevelDisplayName;
            Message=$event.Message; RecordId=$event.RecordId; Kind=$kind;
            ApplicationName=$app; ApplicationVersion=$appVersion; FaultingModule=$module;
            ExceptionCode=$exceptionCode; ApplicationPath=$appPath; ModulePath=$modulePath
        }}
    }}
    $whea=@(Get-WinEvent -FilterHashtable @{{LogName='System'; ProviderName='Microsoft-Windows-WHEA-Logger'; StartTime=$start; Id=18,19,20,46}} -ErrorAction SilentlyContinue);
    $power=@(Get-WinEvent -FilterHashtable @{{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; StartTime=$start; Id=41}} -ErrorAction SilentlyContinue);
    $shutdown=@(Get-WinEvent -FilterHashtable @{{LogName='System'; ProviderName='EventLog'; StartTime=$start; Id=6008}} -ErrorAction SilentlyContinue);
    $bug=@(Get-WinEvent -FilterHashtable @{{LogName='System'; ProviderName='Microsoft-Windows-WER-SystemErrorReporting'; StartTime=$start; Id=1001}} -ErrorAction SilentlyContinue);
    $appError=@(Get-WinEvent -FilterHashtable @{{LogName='Application'; ProviderName='Application Error'; StartTime=$start; Id=1000}} -ErrorAction SilentlyContinue);
    $appHang=@(Get-WinEvent -FilterHashtable @{{LogName='Application'; ProviderName='Application Hang'; StartTime=$start; Id=1002}} -ErrorAction SilentlyContinue);
    $systemItems=@();
    $systemItems += @($whea | ForEach-Object {{ Convert-CorePulseEvent $_ 'whea' }});
    $systemItems += @($power | ForEach-Object {{ Convert-CorePulseEvent $_ 'kernel_power' }});
    $systemItems += @($shutdown | ForEach-Object {{ Convert-CorePulseEvent $_ 'unexpected_shutdown' }});
    $systemItems += @($bug | ForEach-Object {{ Convert-CorePulseEvent $_ 'bsod_bugcheck' }});
    $appItems=@();
    $appItems += @($appError | ForEach-Object {{ Convert-CorePulseEvent $_ 'app_error' }});
    $appItems += @($appHang | ForEach-Object {{ Convert-CorePulseEvent $_ 'app_hang' }});
    $all=@($systemItems + $appItems);

    # Resumen completo por aplicación: se calcula sobre todos los eventos del período,
    # no sólo sobre las filas que se envían a la tabla.
    $appStats=@();
    foreach($group in @($appItems | Where-Object {{ $_.ApplicationName }} | Group-Object ApplicationName)) {{
        $entries=@($group.Group);
        $errors=@($entries | Where-Object {{ $_.Kind -eq 'app_error' }}).Count;
        $hangs=@($entries | Where-Object {{ $_.Kind -eq 'app_hang' }}).Count;
        $modules=@($entries | ForEach-Object {{ $_.FaultingModule }} | Where-Object {{ $_ }} | Group-Object | Sort-Object Count -Descending);
        $exceptions=@($entries | ForEach-Object {{ $_.ExceptionCode }} | Where-Object {{ $_ }} | Group-Object | Sort-Object Count -Descending);
        [string]$topModule=if($modules.Count -gt 0){{$modules[0].Name}}else{{$null}};
        [int]$topModuleCount=if($modules.Count -gt 0){{$modules[0].Count}}else{{0}};
        [string]$topException=if($exceptions.Count -gt 0){{$exceptions[0].Name}}else{{$null}};
        [int]$topExceptionCount=if($exceptions.Count -gt 0){{$exceptions[0].Count}}else{{0}};
        [string]$version=($entries | ForEach-Object {{ $_.ApplicationVersion }} | Where-Object {{ $_ }} | Select-Object -First 1);
        [string]$path=($entries | ForEach-Object {{ $_.ApplicationPath }} | Where-Object {{ $_ }} | Select-Object -First 1);
        $appStats += [pscustomobject]@{{
            ApplicationName=$group.Name; Total=$entries.Count; Errors=$errors; Hangs=$hangs;
            TopModule=$topModule; TopModuleCount=$topModuleCount; TopException=$topException; TopExceptionCount=$topExceptionCount;
            ApplicationVersion=$version; ApplicationPath=$path
        }};
    }}
    $appStats=@($appStats | Sort-Object @{{Expression='Total';Descending=$true}}, ApplicationName);

    # Los detalles críticos/de sistema tienen prioridad. Una avalancha de errores
    # de aplicaciones nunca debe desplazar WHEA/BSOD/Kernel-Power de la tabla.
    $detail=@();
    if($systemItems.Count -ge {max_events}) {{
        $detail=@($systemItems | Sort-Object TimeCreated -Descending | Select-Object -First {max_events});
    }} else {{
        $detail=@($systemItems);
        $remaining={max_events}-$detail.Count;
        if($remaining -gt 0) {{
            $detail += @($appItems | Sort-Object TimeCreated -Descending | Select-Object -First $remaining);
        }}
        $detail=@($detail | Sort-Object TimeCreated -Descending);
    }}

    # Kernel-Power 41 y EventLog 6008 suelen representar el mismo reinicio.
    # Se agrupan por proximidad temporal para exponer incidentes, no dos registros.
    $powerTimes=@($power.TimeCreated + $shutdown.TimeCreated | Where-Object {{ $_ -ne $null }} | Sort-Object);
    $powerIncidents=0; $lastPower=$null;
    foreach($t in $powerTimes) {{
        if($null -eq $lastPower -or [math]::Abs(($t-$lastPower).TotalSeconds) -gt 300) {{ $powerIncidents++ }};
        $lastPower=$t;
    }}

    $affectedApps=@();
    foreach($e in @($appError+$appHang)) {{
        try {{
            $props=@($e.Properties | ForEach-Object {{ $_.Value }});
            if($props.Count -gt 0 -and $null -ne $props[0]) {{
                $name=([string]$props[0]).Trim();
                if($name) {{ $affectedApps += $name }}
            }}
        }} catch {{}}
    }}
    $affectedApps=@($affectedApps | Sort-Object -Unique);

    [pscustomobject]@{{
        Counts=[pscustomobject]@{{
            bsod_bugcheck=$bug.Count; whea=$whea.Count; kernel_power=$power.Count;
            unexpected_shutdown=$shutdown.Count; app_error=$appError.Count; app_hang=$appHang.Count
        }};
        PowerIncidentCount=$powerIncidents;
        AffectedApps=$affectedApps;
        AppStats=$appStats;
        MatchedTotal=$all.Count;
        DisplayLimit={max_events};
        Truncated=($all.Count -gt $detail.Count);
        Items=$detail
    }}
    """
    rows, err = _json_ps(script, timeout=55)

    counts = {
        'bsod_bugcheck': 0, 'whea': 0, 'kernel_power': 0,
        'app_error': 0, 'app_hang': 0, 'unexpected_shutdown': 0,
    }
    raw_items: List[Dict[str, Any]] = []
    matched_total = 0
    truncated = False

    # Respuesta nueva: un objeto con conteos completos + detalles. Se conserva
    # compatibilidad con la forma antigua para pruebas y degradación segura.
    payload = rows[0] if len(rows) == 1 and isinstance(rows[0], dict) and 'Counts' in rows[0] else None
    if payload is not None:
        raw_counts = payload.get('Counts') or {}
        for key in counts:
            try:
                counts[key] = max(0, int(raw_counts.get(key) or 0))
            except Exception:
                counts[key] = 0
        raw_items = [x for x in (payload.get('Items') or []) if isinstance(x, dict)]
        matched_total = int(payload.get('MatchedTotal') or sum(counts.values()))
        truncated = bool(payload.get('Truncated'))
        payload_power_incidents = payload.get('PowerIncidentCount')
        raw_affected_apps = payload.get('AffectedApps') or []
        if isinstance(raw_affected_apps, str):
            raw_affected_apps = [raw_affected_apps]
        payload_affected_apps = [str(x).strip() for x in raw_affected_apps if str(x).strip()]
        raw_app_stats = payload.get('AppStats') or []
        if isinstance(raw_app_stats, dict):
            raw_app_stats = [raw_app_stats]
        payload_app_stats = [x for x in raw_app_stats if isinstance(x, dict)]
    else:
        payload_power_incidents = None
        payload_affected_apps = []
        payload_app_stats = []
        raw_items = [x for x in rows if isinstance(x, dict)]
        matched_total = len(raw_items)

    items = []
    for row in raw_items:
        kind = str(row.get('Kind') or '').strip().lower() or _classify_stability_event(row)
        if kind not in counts:
            continue
        if payload is None:
            counts[kind] += 1
        label, explanation = _stability_event_user_text(kind)
        app_name = str(row.get('ApplicationName') or '').strip() or _fallback_app_name(row.get('Message'))
        module_name = str(row.get('FaultingModule') or '').strip() or _fallback_module_name(row.get('Message'))
        component = app_name or (
            'Hardware reportado por WHEA' if kind == 'whea' else
            'Windows / sistema' if kind in ('bsod_bugcheck', 'kernel_power', 'unexpected_shutdown') else
            str(row.get('ProviderName') or 'N/A')
        )
        detail = explanation
        if kind == 'app_error' and app_name:
            detail = f'{app_name} se cerró con error.' + (f' Módulo relacionado: {module_name}.' if module_name else '')
        elif kind == 'app_hang' and app_name:
            detail = f'{app_name} dejó de responder.'
        items.append({
            **row,
            'kind': kind,
            'user_label': label,
            'user_summary': explanation,
            'component_name': component,
            'user_detail': detail,
            'display_time': _event_display_time(row.get('TimeCreated')),
            'ApplicationName': app_name,
            'ApplicationVersion': str(row.get('ApplicationVersion') or '').strip() or None,
            'FaultingModule': module_name,
            'ExceptionCode': _normalize_exception_code(row.get('ExceptionCode')) or None,
            'ApplicationPath': str(row.get('ApplicationPath') or '').strip() or None,
            'ModulePath': str(row.get('ModulePath') or '').strip() or None,
            'Message': str(row.get('Message') or '')[:1200],
        })

    items = _dedupe_exact_stability_items(items)
    if payload_power_incidents is not None:
        try:
            power_incidents = max(0, int(payload_power_incidents))
        except Exception:
            power_incidents = _unique_power_incidents(items)
    else:
        power_incidents = _unique_power_incidents(items)

    if payload_affected_apps:
        affected_apps = sorted({name.lower(): name for name in payload_affected_apps}.values(), key=str.lower)
    else:
        affected_apps = sorted({
            str(x.get('ApplicationName') or '').strip()
            for x in items if x.get('kind') in ('app_error', 'app_hang') and str(x.get('ApplicationName') or '').strip()
        }, key=str.lower)
    if payload_app_stats:
        app_stats = []
        for stat in payload_app_stats:
            try:
                total = max(0, int(stat.get('Total') or 0))
            except Exception:
                total = 0
            try:
                errors = max(0, int(stat.get('Errors') or 0))
            except Exception:
                errors = 0
            try:
                hangs = max(0, int(stat.get('Hangs') or 0))
            except Exception:
                hangs = 0
            app_stats.append({
                'ApplicationName': str(stat.get('ApplicationName') or '').strip(),
                'Total': total,
                'Errors': errors,
                'Hangs': hangs,
                'TopModule': str(stat.get('TopModule') or '').strip() or None,
                'TopModuleCount': max(0, int(stat.get('TopModuleCount') or 0)),
                'TopException': _normalize_exception_code(stat.get('TopException')) or None,
                'TopExceptionCount': max(0, int(stat.get('TopExceptionCount') or 0)),
                'ApplicationVersion': str(stat.get('ApplicationVersion') or '').strip() or None,
                'ApplicationPath': str(stat.get('ApplicationPath') or '').strip() or None,
            })
        app_stats = [x for x in app_stats if x.get('ApplicationName')]
    else:
        # Compatibilidad con payload antiguo: resume únicamente los detalles reales
        # disponibles, sin inventar recuentos fuera de lo observado.
        grouped = {}
        for item in items:
            if item.get('kind') not in ('app_error', 'app_hang'):
                continue
            name = str(item.get('ApplicationName') or '').strip()
            if not name:
                continue
            key = name.lower()
            stat = grouped.setdefault(key, {
                'ApplicationName': name, 'Total': 0, 'Errors': 0, 'Hangs': 0,
                'TopModule': None, 'TopModuleCount': 0, 'TopException': None, 'TopExceptionCount': 0,
                'ApplicationVersion': item.get('ApplicationVersion'),
                'ApplicationPath': item.get('ApplicationPath'),
            })
            stat['Total'] += 1
            if item.get('kind') == 'app_error':
                stat['Errors'] += 1
            else:
                stat['Hangs'] += 1
            if item.get('FaultingModule'):
                if not stat.get('TopModule'):
                    stat['TopModule'] = item.get('FaultingModule')
                if str(item.get('FaultingModule')).lower() == str(stat.get('TopModule') or '').lower():
                    stat['TopModuleCount'] += 1
            if item.get('ExceptionCode'):
                if not stat.get('TopException'):
                    stat['TopException'] = item.get('ExceptionCode')
                if str(item.get('ExceptionCode')).lower() == str(stat.get('TopException') or '').lower():
                    stat['TopExceptionCount'] += 1
        app_stats = list(grouped.values())

    app_issue_count = int(counts['app_error']) + int(counts['app_hang'])
    action_plan = _stability_action_plan(
        counts, days, power_incidents=power_incidents, app_stats=app_stats
    )
    severity = (
        'CRITICAL' if counts['whea'] or counts['bsod_bugcheck']
        else 'WARNING' if power_incidents
        else 'INFO' if app_issue_count
        else 'NORMAL'
    )
    return {
        'items': items,
        'counts': counts,
        'severity': severity,
        'days': days,
        'critical_count': int(counts['whea']) + int(counts['bsod_bugcheck']),
        'power_event_count': power_incidents,
        'power_log_records': int(counts['kernel_power']) + int(counts['unexpected_shutdown']),
        'app_issue_count': app_issue_count,
        'affected_app_count': len(affected_apps),
        'affected_apps': affected_apps,
        'app_stats': app_stats,
        'action_plan': action_plan,
        'matched_total': matched_total,
        'details_truncated': truncated,
        'summary': _stability_summary(counts, days, power_incidents=power_incidents, affected_apps=len(affected_apps)),
        'classification_policy': 'PROVIDER_AND_EVENT_ID_REQUIRED + COMPLETE_CATEGORY_COUNTS + EXACT_RECORD_DEDUPE + EVIDENCE_GATED_RECOMMENDATIONS',
        'error': err,
        'source': 'Windows Event Log / Get-WinEvent',
    }


def _driver_hardware_priority(row: Dict[str, Any]) -> tuple[int, str]:
    """Prioriza controladores que representan hardware útil para el usuario.

    Win32_PnPSignedDriver también devuelve una gran cantidad de dispositivos
    virtuales/inbox de Windows (WAN Miniport, colas de impresión, etc.). Esos
    registros son válidos, pero no deben desplazar de la vista principal a GPU,
    red, audio, almacenamiento, Bluetooth o controladores de plataforma.

    La clasificación usa únicamente DeviceClass/DeviceName/Provider reales.
    """
    device_class = str(row.get('DeviceClass') or '').strip().upper()
    name = str(row.get('DeviceName') or '').strip()
    provider = str(row.get('DriverProviderName') or '').strip()
    text = f'{name} {provider}'.casefold()

    # Los dispositivos virtuales/inbox de Windows siguen formando parte del
    # inventario y del conteo, pero no desplazan hardware físico relevante en
    # la tabla principal.
    if _microsoft_inbox_driver(row):
        return 0, 'WINDOWS / VIRTUAL'

    if device_class == 'DISPLAY':
        return 100, 'GPU / VIDEO'
    if device_class == 'NET':
        return 95, 'RED'
    if device_class in ('MEDIA', 'AUDIOENDPOINT'):
        return 90, 'AUDIO'
    if device_class in ('HDC', 'SCSIADAPTER', 'STORAGEVOLUMES', 'DISKDRIVE') or any(
        token in text for token in ('nvme', 'sata', 'ahci', 'raid', 'storage controller', 'rst', 'vmd')
    ):
        return 88, 'ALMACENAMIENTO'
    if device_class == 'BLUETOOTH' or 'bluetooth' in text:
        return 84, 'BLUETOOTH'
    if device_class in ('USB', 'USBDEVICE') or any(token in text for token in ('xhci', 'usb host controller')):
        return 78, 'USB'
    if device_class == 'SYSTEM' and any(token in text for token in (
        'chipset', 'smbus', 'management engine', 'serial io', 'gpio',
        'pci express root', 'pcie root', 'dynamic tuning', 'platform',
        'thermal framework', 'amd gpio', 'amd pci', 'intel(r) pci',
    )):
        return 82, 'CHIPSET / PLATAFORMA'
    return 0, 'OTRO'


def _microsoft_inbox_driver(row: Dict[str, Any]) -> bool:
    provider = str(row.get('DriverProviderName') or '').strip().casefold()
    name = str(row.get('DeviceName') or '').strip().casefold()
    device_class = str(row.get('DeviceClass') or '').strip().upper()
    device_id = str(row.get('DeviceID') or '').strip().casefold()
    if provider not in ('microsoft', 'microsoft corporation'):
        return False
    # Componentes inbox/virtuales de Windows pueden conservar fechas históricas
    # por compatibilidad. No deben parecer "drivers viejos" que el usuario tenga
    # que perseguir manualmente. Si alguno presenta una incidencia real seguirá
    # apareciendo porque DEVICE_PROBLEM tiene prioridad sobre este filtro.
    virtual_tokens = (
        'wan miniport', 'wi-fi direct virtual adapter', 'wifi direct virtual adapter',
        'kernel debug network adapter', 'bluetooth device (personal area network)',
        'microsoft streaming service proxy', 'remote desktop', 'virtual adapter',
        'virtual ethernet', 'virtual disk', 'root enumerator', 'generic software device',
        'local print queue', 'software device',
    )
    return (
        any(token in name for token in virtual_tokens)
        or device_class in ('PRINTQUEUE', 'SOFTWAREDEVICE')
        or device_id.startswith('root\\')
        or device_id.startswith('sw\\')
    )


_CM_ERROR_TEXT = {
    1: 'Windows indica que el dispositivo no está configurado correctamente.',
    3: 'El controlador puede estar dañado o Windows no dispone de recursos suficientes.',
    10: 'El dispositivo no puede iniciarse.',
    12: 'El dispositivo no encuentra suficientes recursos libres.',
    14: 'Windows requiere reiniciar el equipo para completar la configuración.',
    18: 'Windows recomienda reinstalar el controlador.',
    19: 'La configuración del dispositivo en el Registro está incompleta o dañada.',
    21: 'Windows está quitando el dispositivo.',
    22: 'El dispositivo está deshabilitado.',
    24: 'El dispositivo no está presente, no funciona o no tiene todos sus controladores.',
    28: 'Los controladores del dispositivo no están instalados.',
    29: 'El firmware del dispositivo lo ha deshabilitado o no le asignó recursos.',
    31: 'Windows no puede cargar los controladores necesarios para este dispositivo.',
    32: 'El servicio/controlador requerido para este dispositivo está deshabilitado.',
    37: 'Windows no pudo inicializar el controlador del dispositivo.',
    39: 'El controlador está dañado o falta un archivo necesario.',
    41: 'Windows cargó el controlador, pero no encuentra el dispositivo.',
    43: 'Windows detuvo el dispositivo porque informó de un problema.',
    45: 'El dispositivo no está conectado actualmente.',
    47: 'El dispositivo está preparado para extracción segura.',
    48: 'Windows bloqueó el controlador por incompatibilidad o problemas conocidos.',
    52: 'Windows no puede verificar la firma digital del controlador requerido.',
}


def _config_manager_problem_detail(code_num: int, device_status: str) -> str:
    if code_num:
        return f'Código {code_num} · {_CM_ERROR_TEXT.get(code_num, "Windows reporta una incidencia de configuración para este dispositivo.")}'
    status = str(device_status or '').strip()
    if status and status.upper() not in ('OK', 'N/A'):
        return f'Estado Windows: {status}'
    return ''


def analyze_drivers(limit: int = 400) -> Dict[str, Any]:
    # Importante: no aplicamos Select-Object -First antes de clasificar. El orden
    # que devuelve WMI no garantiza que GPU/red/audio/almacenamiento aparezcan
    # dentro de los primeros N registros. Primero leemos el inventario real y
    # luego priorizamos en Python.
    script = r"""
    $dev=@{}; Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | ForEach-Object { if($_.PNPDeviceID){ $status=if($null -ne $_.Status){[string]$_.Status}else{'N/A'}; $code=if($null -ne $_.ConfigManagerErrorCode){[string]$_.ConfigManagerErrorCode}else{''}; $dev[$_.PNPDeviceID]=$status+'|'+$code } };
    Get-CimInstance Win32_PnPSignedDriver | ForEach-Object {
      $st=$dev[$_.DeviceID]; $parts=if($st){$st -split '\|'}else{@('N/A','')};
      [pscustomobject]@{DeviceName=$_.DeviceName;DeviceClass=$_.DeviceClass;DriverVersion=$_.DriverVersion;DriverProviderName=$_.DriverProviderName;DriverDate=$_.DriverDate;IsSigned=$_.IsSigned;InfName=$_.InfName;DeviceID=$_.DeviceID;HardwareID=$_.HardWareID;DeviceStatus=$parts[0];ConfigManagerErrorCode=if($parts.Count -gt 1){$parts[1]}else{$null}}
    }
    """
    rows, err = _json_ps(script, timeout=50)
    now = time.time(); items=[]; unsigned=0; old=0; problems=0
    for row in rows:
        if not isinstance(row, dict):
            continue
        signed = row.get('IsSigned')
        if signed is False:
            unsigned += 1
        date = str(row.get('DriverDate') or '')
        age_years = None
        m = re.search(r'Date\((\d+)', date)
        if m:
            try:
                age_years=(now-(int(m.group(1))/1000.0))/(365.25*86400)
            except Exception:
                pass
        elif date:
            try:
                from datetime import datetime
                parsed = datetime.fromisoformat(date.replace('Z','+00:00'))
                age_years = (now - parsed.timestamp()) / (365.25*86400)
            except Exception:
                pass

        importance, category = _driver_hardware_priority(row)

        # Los paquetes inbox/genéricos de Microsoft pueden conservar fechas
        # históricas por compatibilidad/ranking. "Antiguo" sólo se usa como
        # señal accionable para hardware relevante de terceros; nunca equivale
        # a una actualización confirmada.
        inbox_generic = _microsoft_inbox_driver(row)
        provider_cf = str(row.get('DriverProviderName') or '').strip().casefold()
        microsoft_provider = provider_cf in ('microsoft', 'microsoft corporation')
        old_actionable = bool(
            age_years is not None and age_years > 5
            and importance > 0 and not inbox_generic and not microsoft_provider
        )
        if old_actionable:
            old += 1

        code = row.get('ConfigManagerErrorCode')
        try:
            code_num=int(code) if code not in (None,'') else 0
        except Exception:
            code_num=0
        device_status = str(row.get('DeviceStatus') or '')
        device_bad = code_num != 0 or device_status.upper() not in ('OK','N/A','')
        if device_bad:
            problems += 1

        status = 'DEVICE_PROBLEM' if device_bad else 'UNSIGNED' if signed is False else 'OLD' if old_actionable else 'OK'
        items.append({
            **row,
            'age_years': age_years,
            'status': status,
            'hardware_priority': importance,
            'hardware_category': category,
            'microsoft_inbox_generic': inbox_generic,
            'config_manager_error_code': code_num,
            'problem_detail': _config_manager_problem_detail(code_num, device_status) if device_bad else '',
        })

    # 1) Problemas reales/no firmados siempre arriba.
    # 2) Luego hardware que el usuario realmente necesita revisar.
    # 3) Dentro de la misma prioridad, drivers antiguos de terceros antes que OK.
    items.sort(
        key=lambda x: (
            x.get('status') in ('DEVICE_PROBLEM','UNSIGNED'),
            int(x.get('hardware_priority') or 0),
            x.get('status') == 'OLD',
            x.get('age_years') or 0,
        ),
        reverse=True,
    )
    scanned_count = len(items)
    try:
        safe_limit = max(1, int(limit))
    except Exception:
        safe_limit = 400
    visible_items = items[:safe_limit]
    important_count = sum(1 for x in items if int(x.get('hardware_priority') or 0) > 0 and not bool(x.get('microsoft_inbox_generic')))
    return {
        'items': visible_items,
        'count': scanned_count,
        'important_count': important_count,
        'unsigned': unsigned,
        'device_problems': problems,
        'review_count': problems + unsigned,
        'older_than_5y': old,
        'error': err,
        'source': 'Win32_PnPSignedDriver + Win32_PnPEntity',
        'note': 'Incidencias y controladores sin firma se cuentan por separado. Antigüedad no implica por sí sola un problema ni confirma una actualización; los componentes virtuales/inbox de Microsoft no se marcan como antiguos.',
    }


def _stable_inventory(inv: Dict[str, Any]):
    if not isinstance(inv, dict): return {}
    cpu = inv.get('cpu') if isinstance(inv.get('cpu'), dict) else {}
    ram = inv.get('ram') if isinstance(inv.get('ram'), dict) else {}
    storage = inv.get('storage') if isinstance(inv.get('storage'), list) else []
    gpus = inv.get('gpus') if isinstance(inv.get('gpus'), list) else []
    ident = inv.get('identity') if isinstance(inv.get('identity'), dict) else {}
    bios = ident.get('bios') if isinstance(ident.get('bios'), dict) else {}
    board = ident.get('motherboard') if isinstance(ident.get('motherboard'), dict) else {}
    return {
        'identity': {
            'manufacturer': ident.get('manufacturer'), 'model': ident.get('model'),
            'bios_version': bios.get('version'), 'bios_release_date': bios.get('release_date'),
            'motherboard_manufacturer': board.get('manufacturer'), 'motherboard_model': board.get('model'),
        },
        'cpu': {'name': cpu.get('name')},
        'ram': {
            'module_total_gb': ram.get('module_total_gb'), 'module_count': ram.get('module_count'),
            'modules': [{k:m.get(k) for k in ('capacity_gb','manufacturer','part_number','slot','bank','configured_speed_mhz','speed_mhz')} for m in ram.get('modules',[]) if isinstance(m,dict)]
        },
        'gpus': [{k:g.get(k) for k in ('name','driver_version','pnp_device_id')} for g in gpus if isinstance(g,dict)],
        'storage': [{k:s.get(k) for k in ('name','model','serial','serial_number','firmware','capacity_gb','total_space_gb')} for s in storage if isinstance(s,dict)],
    }


def compare_hardware_inventory(inventory: Dict[str, Any], save_if_missing=True) -> Dict[str, Any]:
    current = _stable_inventory(inventory)
    previous = None
    try:
        if HW_STATE.exists(): previous = json.loads(HW_STATE.read_text(encoding='utf-8'))
    except Exception: previous = None
    if previous is None:
        if save_if_missing:
            HW_STATE.parent.mkdir(parents=True, exist_ok=True); HW_STATE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'baseline_exists': False, 'changes': [], 'current': current}
    changes=[]
    for key in ('identity','cpu','ram','gpus','storage'):
        if previous.get(key) != current.get(key): changes.append({'component': key.upper(), 'before': previous.get(key), 'after': current.get(key)})
    return {'baseline_exists': True, 'changes': changes, 'current': current, 'previous': previous}


def save_hardware_baseline(inventory: Dict[str, Any]):
    current = _stable_inventory(inventory)
    HW_STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp=HW_STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(HW_STATE)
    return current


def restore_point_status() -> Dict[str, Any]:
    """Lista los puntos de restauración reales visibles para Windows.

    V125 deja de limitar la consulta a cinco filas y normaliza la fecha en
    PowerShell para que la UI no tenga que interpretar el formato DMTF/WMI.
    No habilita Restaurar sistema ni crea puntos por sí sola.
    """
    if platform.system() != 'Windows':
        return {'available': False, 'admin': False, 'reason': 'Windows requerido', 'points': [], 'count': 0}
    script = r"""
    Get-ComputerRestorePoint -ErrorAction Stop |
      Sort-Object SequenceNumber -Descending |
      ForEach-Object {
        $created = $null
        try {
          if ($_.CreationTime -is [string]) {
            $created = [System.Management.ManagementDateTimeConverter]::ToDateTime($_.CreationTime)
          } else {
            $created = [datetime]$_.CreationTime
          }
        } catch {
          $created = $null
        }
        [pscustomobject]@{
          SequenceNumber = $_.SequenceNumber
          Description = $_.Description
          CreationTime = if ($created) { $created.ToString('yyyy-MM-dd HH:mm:ss') } else { [string]$_.CreationTime }
          RestorePointType = $_.RestorePointType
          EventType = $_.EventType
        }
      }
    """
    rows, err = _json_ps(script, timeout=25)
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    return {
        'available': err is None,
        'admin': is_admin(),
        'points': rows,
        'count': len(rows),
        'error': err,
        'source': 'Get-ComputerRestorePoint',
    }


def create_restore_point(description='CorePulse - antes de cambios') -> Dict[str, Any]:
    if platform.system() != 'Windows': return {'ok': False, 'error': 'Windows requerido'}
    if not is_admin(): return {'ok': False, 'error': 'Se requieren privilegios de administrador'}
    safe = str(description).replace("'", "''")[:120]
    out, err = _ps(f"Checkpoint-Computer -Description '{safe}' -RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop; 'OK'", timeout=90)
    return {'ok': err is None and 'OK' in (out or ''), 'error': err, 'description': description, 'source': 'Checkpoint-Computer'}
