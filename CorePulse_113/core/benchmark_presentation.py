"""Presentación humana de resultados de benchmark sin rankings inventados.

El motor conserva mediciones técnicas reales. Este módulo añade jerarquía visual,
frases cortas y conclusiones conservadoras para que una persona no técnica pueda
entender qué se midió sin convertir una prueba local en un ranking inexistente.
"""
from __future__ import annotations


def _num(value):
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _short(text, n=130):
    value = str(text or '').replace('\r', ' ').replace('\n', ' ').strip()
    return value if len(value) <= n else value[: n - 1] + '…'


def human_number(value, digits=1):
    """Formatea un número con separadores españoles; N/A permanece N/A."""
    n = _num(value)
    if n is None:
        return 'N/A'
    text = f'{n:,.{max(0, int(digits))}f}'
    return text.replace(',', '\x00').replace('.', ',').replace('\x00', '.')


def benchmark_card_data(key, result):
    """Convierte un resultado técnico en una tarjeta corta y fácil de leer.

    Mantiene las claves históricas ``explanation``/``interpretation`` para no
    romper integraciones, pero la UI nueva prioriza ``meaning``, ``verdict`` y
    ``technical_detail``.
    """
    key = str(key or '').lower().strip()
    r = result if isinstance(result, dict) else {}
    raw_status = str(r.get('status') or '').upper().strip()
    if raw_status == 'SKIPPED':
        return {
            'title': key.upper() or 'RESULTADO',
            'subtitle': 'Componente no seleccionado',
            'status': 'Omitida',
            'short_status': 'Omitida',
            'tone': 'muted',
            'headline': 'No ejecutado',
            'secondary': _short(r.get('reason') or 'No seleccionado por el usuario'),
            'verdict': 'Este componente no formó parte de la prueba elegida.',
            'meaning': 'CorePulse sólo ejecuta los componentes seleccionados; no interpreta una prueba omitida como un fallo.',
            'technical_detail': _short(r.get('reason') or 'No seleccionado por el usuario'),
            'explanation': 'La prueba fue omitida por configuración.',
            'interpretation': 'No hay medición para este componente en esta ejecución.',
        }
    duration = _num(r.get('duration_s'))
    duration_text = f'{human_number(duration, 1)} s' if duration is not None else 'N/A'

    if key == 'cpu':
        value = _num(r.get('value'))
        throughput = _num(r.get('throughput_mbps'))
        single_ops = _num(r.get('single_thread_ops_s'))
        multi_ops = _num(r.get('multi_thread_ops_s'))
        threads = r.get('threads')
        available = value is not None
        headline = 'Sin resultado'
        if throughput is not None:
            headline = f'{human_number(throughput, 0)} MB/s SHA-256'
        elif available:
            headline = f'{human_number(value, 0)} operaciones/s'
        secondary_parts = []
        if single_ops is not None:
            secondary_parts.append(f'1 hilo {human_number(single_ops, 0)} ops/s')
        if multi_ops is not None and threads:
            secondary_parts.append(f'{threads} hilos {human_number(multi_ops, 0)} ops/s')
        secondary = ' · '.join(secondary_parts) or f'Duración: {duration_text}'
        explanation = 'CorePulse mantiene una carga SHA-256 real: primero mide un hilo y luego varios hilos en paralelo.'
        interpretation = 'Cuanto más alto, más trabajo criptográfico sostuvo este mismo PC durante la prueba. No equivale a Cinebench ni a un ranking externo.'
        return {
            'title': 'CPU', 'subtitle': 'Carga sostenida del procesador',
            'status': 'Prueba completada' if available else 'No disponible',
            'short_status': 'Medido' if available else 'N/A',
            'tone': 'green' if available else 'muted',
            'headline': headline,
            'secondary': secondary,
            'verdict': 'Carga multinúcleo completada' if available else 'No hay una medición disponible',
            'meaning': 'Mide trabajo real de CPU durante varios segundos, incluyendo tramo por hilo y tramo multinúcleo. Para este mismo PC, más alto significa más rendimiento sostenido.',
            'technical_detail': f"SHA-256 sostenido · {threads or 1} hilos · Duración {duration_text}",
            'explanation': explanation,
            'interpretation': interpretation,
        }

    if key == 'ram':
        value = _num(r.get('value'))
        transferred = _num(r.get('transferred_mb'))
        buffer_mb = _num(r.get('buffer_mb'))
        rounds = r.get('rounds')
        available = value is not None
        headline = 'Sin resultado'
        if available:
            headline = f'{human_number(value / 1000.0, 2)} GB/s' if value >= 1000 else f'{human_number(value, 0)} MB/s'
        transferred_text = f'{human_number((transferred or 0) / 1024.0, 1)} GB copiados' if transferred is not None else 'Copia de memoria local'
        explanation = 'CorePulse copia bloques grandes de memoria repetidamente durante una ventana sostenida de tiempo.'
        interpretation = 'Sirve para comparar este mismo equipo entre ejecuciones. No representa por sí sola la frecuencia nominal DDR ni reemplaza una herramienta de laboratorio.'
        detail = f'{transferred_text} · bloque {human_number(buffer_mb, 0)} MB' if buffer_mb is not None else transferred_text
        if rounds is not None:
            detail += f' · {rounds} rondas'
        return {
            'title': 'RAM', 'subtitle': 'Ancho de banda de memoria sostenido',
            'status': 'Prueba completada' if available else 'No disponible',
            'short_status': 'Medida' if available else 'N/A',
            'tone': 'green' if available else 'muted', 'headline': headline,
            'secondary': transferred_text,
            'verdict': 'Ancho de banda sostenido medido' if available else 'No hay una medición disponible',
            'meaning': 'Mide cuánto volumen de memoria pudo copiar CorePulse por segundo durante varios segundos continuos.',
            'technical_detail': f'{detail} · Duración {duration_text}',
            'explanation': explanation,
            'interpretation': interpretation,
        }

    if key == 'ssd':
        read_mbps = _num(r.get('read_mbps'))
        write_mbps = _num(r.get('write_mbps'))
        size_mb = _num(r.get('size_mb'))
        available = read_mbps is not None or write_mbps is not None
        headline = f'{human_number(read_mbps, 0)} MB/s de lectura' if read_mbps is not None else 'Lectura N/A'
        write_text = f'{human_number(write_mbps, 0)} MB/s de escritura' if write_mbps is not None else 'Escritura N/A'
        display_headline = f'Lectura {human_number(read_mbps, 0)} MB/s' if read_mbps is not None else 'Lectura N/A'
        display_secondary = f'Escritura {human_number(write_mbps, 0)} MB/s' if write_mbps is not None else 'Escritura N/A'
        sample_text = f'archivo temporal de {human_number(size_mb, 0)} MB' if size_mb is not None else 'archivo temporal local'
        explanation = 'CorePulse crea, lee y elimina un archivo temporal para medir E/S secuencial real.'
        interpretation = 'El resultado corresponde a la unidad donde Windows aloja la carpeta temporal usada por la prueba.'
        return {
            'title': 'SSD', 'subtitle': 'Velocidad de almacenamiento',
            'status': 'Prueba completada' if available else 'No disponible',
            'short_status': 'Medido' if available else 'N/A',
            'tone': 'cyan' if available else 'muted', 'headline': headline,
            'secondary': write_text, 'display_headline': display_headline, 'display_secondary': display_secondary,
            'verdict': 'Lectura y escritura medidas' if available else 'No hay una medición disponible',
            'meaning': 'Mide transferencias secuenciales del disco usado por la carpeta temporal de Windows. Más alto significa más velocidad en esta prueba.',
            'technical_detail': f'{sample_text} · Duración {duration_text}',
            'explanation': explanation,
            'interpretation': interpretation,
        }

    if key == 'gpu':
        value = _num(r.get('value'))
        status = str(r.get('status') or '').upper().strip()
        reason = _short(r.get('reason') or '')
        renderer = _short(r.get('renderer') or '')
        fps = _num(r.get('frames_per_s'))
        if status == 'UNAVAILABLE' or (value is None and status != 'ERROR'):
            return {
                'title': 'GPU', 'subtitle': 'Carga gráfica OpenGL', 'status': 'No disponible', 'short_status': 'N/A', 'tone': 'muted',
                'headline': 'Sin aceleración gráfica medible',
                'secondary': reason or 'Windows no expuso un contexto OpenGL acelerado.',
                'verdict': 'La prueba gráfica no estuvo disponible',
                'meaning': 'CPU, RAM y SSD siguen siendo válidos. CorePulse deja la GPU como N/A en lugar de inventar una puntuación.',
                'technical_detail': reason or 'Proveedor: CorePulse OpenGL render workload',
                'explanation': 'CorePulse intenta crear una carga OpenGL real sin instalar un benchmark externo.',
                'interpretation': 'Si el controlador no ofrece aceleración, la medición se mantiene como N/A.',
            }
        if status == 'ERROR':
            return {
                'title': 'GPU', 'subtitle': 'Carga gráfica OpenGL', 'status': 'No se pudo completar', 'short_status': 'Aviso', 'tone': 'amber',
                'headline': 'Prueba gráfica incompleta', 'secondary': reason or 'El contexto gráfico devolvió un error.',
                'verdict': 'La carga gráfica no terminó',
                'meaning': 'El resto del benchmark sigue siendo válido. La GPU queda marcada con el error real en vez de una puntuación estimada.',
                'technical_detail': reason or 'Proveedor: CorePulse OpenGL render workload',
                'explanation': 'El resto del benchmark sigue siendo válido aunque la carga OpenGL falle.',
                'interpretation': 'Reintentar puede ayudar; CorePulse no sustituye el dato por una estimación.',
            }
        headline = f'{human_number(value, 1)} M triángulos/s' if value is not None else 'Carga gráfica completada'
        secondary_parts = []
        if fps is not None:
            secondary_parts.append(f'{human_number(fps, 1)} ciclos/s')
        if renderer:
            secondary_parts.append(renderer)
        secondary = ' · '.join(secondary_parts) or f'Duración: {duration_text}'
        return {
            'title': 'GPU', 'subtitle': 'Carga gráfica OpenGL', 'status': 'Prueba 3D completada', 'short_status': 'Medida', 'tone': 'purple',
            'headline': headline, 'secondary': secondary,
            'display_headline': headline, 'display_secondary': secondary,
            'verdict': 'Carga gráfica real completada',
            'meaning': 'CorePulse renderiza geometría real en un contexto OpenGL acelerado y mide el trabajo sostenido. El nombre del renderer indica qué GPU atendió la prueba.',
            'technical_detail': f'OpenGL · {renderer or "renderer N/A"} · Duración {duration_text}',
            'explanation': 'La prueba genera trabajo gráfico local real; no usa el antiguo valor predeterminado de WinSAT D3D.',
            'interpretation': 'Úsala para comparar este mismo PC entre ejecuciones; no equivale a 3DMark ni predice FPS de un juego concreto.',
        }

    return {
        'title': str(key or 'Resultado').upper(), 'subtitle': 'Resultado del benchmark',
        'status': 'No disponible', 'short_status': 'N/A', 'tone': 'muted', 'headline': 'N/A', 'secondary': '',
        'verdict': 'No hay una medición disponible', 'meaning': 'No hay información disponible.', 'technical_detail': '',
        'explanation': 'No hay información disponible.', 'interpretation': '',
    }


_DELTA_META = {
    'cpu_temp': ('Temperatura del CPU', '°C', 1),
    'cpu_ghz': ('Velocidad del CPU', 'GHz', 2),
    'ram_usage': ('Uso de memoria RAM', '%', 1),
    'gpu_temp': ('Temperatura de la GPU', '°C', 1),
}


def benchmark_delta_data(key, delta_row):
    """Humaniza una foto antes/después sin presentarla como máximo/mínimo."""
    label, unit, digits = _DELTA_META.get(str(key), (str(key), '', 1))
    d = delta_row if isinstance(delta_row, dict) else {}
    before = _num(d.get('before')); after = _num(d.get('after')); delta = _num(d.get('delta'))
    if before is None or after is None:
        return {'label': label, 'value': 'N/A', 'change': 'Sin datos suficientes para comparar.', 'tone': 'muted'}

    value = f'{human_number(before, digits)} {unit} → {human_number(after, digits)} {unit}'.replace('  ', ' ')
    if delta is None or abs(delta) < (0.005 if digits >= 2 else 0.05):
        change = 'Sin cambio apreciable entre ambas mediciones.'; tone = 'green'
    else:
        verb = 'Subió' if delta > 0 else 'Bajó'
        change = f'{verb} {human_number(abs(delta), digits)} {unit}.'.replace('  ', ' '); tone = 'cyan'

    # Avisos descriptivos conservadores; no son un diagnóstico térmico universal.
    if key == 'cpu_temp' and after >= 90:
        change += ' Lectura muy alta al finalizar la prueba.'; tone = 'red'
    elif key == 'cpu_temp' and after >= 80:
        change += ' Lectura alta al finalizar la prueba.'; tone = 'amber'
    elif key == 'gpu_temp' and after >= 90:
        change += ' Lectura muy alta al finalizar la prueba.'; tone = 'red'
    elif key == 'gpu_temp' and after >= 80:
        change += ' Lectura alta al finalizar la prueba.'; tone = 'amber'
    elif key == 'ram_usage' and after >= 95:
        change += ' La memoria quedó casi llena.'; tone = 'red'
    elif key == 'ram_usage' and after >= 85:
        change += ' El uso de memoria quedó elevado.'; tone = 'amber'
    elif key == 'cpu_ghz' and delta is not None and delta <= -0.20:
        change += ' La frecuencia terminó claramente más baja.'; tone = 'amber'
    return {'label': label, 'value': value, 'change': change, 'tone': tone}


def benchmark_component_conclusion(key, suite, compare=None):
    """Da una conclusión corta usando sólo evidencia disponible.

    No convierte las dos muestras antes/después en un diagnóstico de throttling;
    únicamente resume la lectura final y las diferencias observadas.
    """
    key = str(key or '').lower().strip()
    suite = suite if isinstance(suite, dict) else {}
    compare = compare if isinstance(compare, dict) else {}
    card = benchmark_card_data(key, suite.get(key) or {})
    if card.get('status') not in ('Prueba completada', 'Prueba 3D completada'):
        return card.get('verdict') or 'Sin conclusión disponible', card.get('tone', 'muted')

    deltas = compare.get('deltas') if compare.get('available') and isinstance(compare.get('deltas'), dict) else {}
    if key == 'cpu':
        temp = deltas.get('cpu_temp') if isinstance(deltas.get('cpu_temp'), dict) else {}
        clock = deltas.get('cpu_ghz') if isinstance(deltas.get('cpu_ghz'), dict) else {}
        after_temp = _num(temp.get('after')); clock_delta = _num(clock.get('delta'))
        if after_temp is not None and after_temp >= 90:
            return 'Atención: el CPU terminó con una temperatura muy alta.', 'red'
        if clock_delta is not None and clock_delta <= -0.20:
            return 'Atención: la frecuencia del CPU terminó claramente más baja.', 'amber'
        if after_temp is not None and after_temp >= 80:
            return 'El CPU terminó caliente; revisa la sección de cambios de temperatura.', 'amber'
        if deltas:
            return 'Las lecturas finales no muestran una alerta clara de temperatura o frecuencia.', 'green'
        return 'Resultado listo para comparar con futuras ejecuciones en este mismo PC.', 'cyan'

    if key == 'ram':
        row = deltas.get('ram_usage') if isinstance(deltas.get('ram_usage'), dict) else {}
        after = _num(row.get('after'))
        if after is not None and after >= 95:
            return 'Atención: la memoria quedó casi llena al terminar.', 'red'
        if after is not None and after >= 85:
            return 'La memoria terminó con un uso elevado.', 'amber'
        if after is not None:
            return 'La prueba de memoria terminó sin una alerta clara de uso.', 'green'
        return 'Velocidad de copia lista para comparar con futuras ejecuciones.', 'cyan'

    if key == 'ssd':
        return 'Lectura y escritura secuencial completadas correctamente.', 'cyan'

    if key == 'gpu':
        row = deltas.get('gpu_temp') if isinstance(deltas.get('gpu_temp'), dict) else {}
        after = _num(row.get('after'))
        if after is not None and after >= 90:
            return 'Atención: la GPU terminó con una temperatura muy alta.', 'red'
        if after is not None and after >= 80:
            return 'La GPU terminó caliente; revisa el cambio de temperatura.', 'amber'
        return 'Carga gráfica OpenGL completada; úsala para comparar este PC entre ejecuciones.', 'purple'

    return card.get('verdict') or 'Medición completada', card.get('tone', 'muted')


def benchmark_overall_summary(suite):
    suite = suite if isinstance(suite, dict) else {}
    statuses = {key: benchmark_card_data(key, suite.get(key) or {}) for key in ('cpu', 'ram', 'ssd', 'gpu')}
    if suite.get('safety_stop'):
        return 'Benchmark detenido por seguridad', str(suite.get('safety_stop')), 'red', statuses

    selected = suite.get('selected_components')
    if not isinstance(selected, (list, tuple)) or not selected:
        selected = ['cpu', 'ram', 'ssd', 'gpu']
    selected = [str(key).lower() for key in selected if str(key).lower() in statuses]

    failed = []
    for key in selected:
        status = statuses[key]['status']
        if key == 'gpu':
            ok = status in ('Prueba 3D completada', 'No disponible')
        else:
            ok = status == 'Prueba completada'
        if not ok:
            failed.append(key)

    profile_label = str(suite.get('profile_label') or suite.get('profile') or '').strip()
    measured_names = ', '.join(key.upper() for key in selected)
    if failed:
        return (
            'Resultados parciales',
            f"Perfil {profile_label or 'configurado'} · se midieron {measured_names}. Alguna prueba no pudo completarse; CorePulse conserva sólo los datos reales.",
            'amber',
            statuses,
        )

    if len(selected) < 4:
        return (
            'Benchmark personalizado completado',
            f"Perfil {profile_label or 'configurado'} · componentes medidos: {measured_names}. Las pruebas omitidas no se consideran fallos.",
            'green',
            statuses,
        )

    gpu_status = statuses['gpu']['status']
    if gpu_status == 'No disponible':
        return 'Benchmark completado', f"Perfil {profile_label or 'configurado'} completado. CPU, RAM y SSD tienen resultados; la GPU quedó N/A porque no hubo aceleración gráfica medible.", 'green', statuses
    return 'Benchmark completado', f"Perfil {profile_label or 'configurado'} completado con CPU, RAM, SSD y GPU. CorePulse no compara este resultado contra otros PCs ni inventa rankings.", 'green', statuses

