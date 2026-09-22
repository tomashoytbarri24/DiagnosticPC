"""Presentación humana de resultados de benchmark sin rankings inventados.

El motor conserva mediciones técnicas reales. Este módulo añade jerarquía visual,
frases cortas y conclusiones conservadoras para que una persona no técnica pueda
entender qué se midió sin convertir una prueba local en un ranking inexistente.
"""
from __future__ import annotations

from core.benchmark_version import GPU_BENCHMARK_LABEL, GPU_PROVIDER


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
        compression = r.get('compression') if isinstance(r.get('compression'), dict) else {}
        if single_ops is not None:
            secondary_parts.append(f'1 hilo {human_number(single_ops, 0)} ops/s')
        if multi_ops is not None and threads:
            secondary_parts.append(f'{threads} hilos {human_number(multi_ops, 0)} ops/s')
        if compression.get('compression_mbps') is not None:
            secondary_parts.append(f"Comp. {human_number(compression.get('compression_mbps'), 0)} MB/s")
        if compression.get('decompression_mbps') is not None:
            secondary_parts.append(f"Decomp. {human_number(compression.get('decompression_mbps'), 0)} MB/s")
        image = r.get('image_processing') if isinstance(r.get('image_processing'), dict) else {}
        if image.get('value') is not None:
            secondary_parts.append(f"Imagen {human_number(image.get('value'), 2)} MPix/s")
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
            'meaning': 'Mide cargas reales de CPU por áreas prácticas: SHA-256 mono/multihilo, compresión, descompresión y procesamiento de imagen. Las áreas de ALU/FP/SIMD/caché que el backend no puede aislar quedan N/A, nunca estimadas.',
            'technical_detail': f"Benchmark CPU V4 por áreas · 3 muestras · {threads or 1} hilos · Calidad {r.get('measurement_quality') or 'N/A'} · Duración {duration_text}",
            'explanation': explanation,
            'interpretation': interpretation,
        }

    if key == 'ram':
        value = _num(r.get('value'))
        write_mbps = _num(r.get('write_mbps'))
        transferred = _num(r.get('transferred_mb'))
        buffer_mb = _num(r.get('buffer_mb'))
        rounds = r.get('rounds')
        available = value is not None
        headline = 'Sin resultado'
        if available:
            headline = f'{human_number(value / 1000.0, 2)} GB/s' if value >= 1000 else f'{human_number(value, 0)} MB/s'
        transferred_text = f'{human_number((transferred or 0) / 1024.0, 1)} GB copiados' if transferred is not None else 'Copia de memoria local'
        explanation = 'CorePulse realiza tres pruebas reales de copia de memoria y verifica byte a byte el contenido fuera del intervalo cronometrado.'
        interpretation = 'Sirve para comparar este mismo equipo entre ejecuciones. No representa por sí sola la frecuencia nominal DDR ni reemplaza una herramienta de laboratorio.'
        detail = f'{transferred_text} · bloque {human_number(buffer_mb, 0)} MB' if buffer_mb is not None else transferred_text
        if rounds is not None:
            detail += f' · {rounds} rondas'
        return {
            'title': 'RAM', 'subtitle': 'Tasa de copia sostenida de memoria',
            'status': 'Prueba completada' if available else 'No disponible',
            'short_status': 'Medida' if available else 'N/A',
            'tone': 'green' if available else 'muted', 'headline': headline,
            'secondary': transferred_text,
            'verdict': 'Tasa de copia sostenida medida' if available else 'No hay una medición disponible',
            'meaning': 'Mide escritura nativa (memset) y copia nativa (memmove) en tres muestras, con verificación posterior. La lectura pura y la latencia quedan N/A mientras no exista un backend nativo que pueda aislarlas correctamente.',
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
        cache_resistant = r.get('cache_resistant') is True
        io_mode = str(r.get('io_mode') or 'N/A')
        explanation = ('CorePulse usa E/S secuencial directa de Windows con NO_BUFFERING/WRITE_THROUGH para reducir la influencia de caché.'
                       if cache_resistant else 'CorePulse crea, lee y elimina un archivo temporal para medir E/S secuencial real; esta ejecución usó un fallback potencialmente cacheable.')
        interpretation = 'El resultado corresponde al volumen probado. Benchmark V4 usa tres muestras secuenciales y, en Windows, añade Random 4K QD1 con E/S directa cuando está disponible.'
        return {
            'title': 'SSD', 'subtitle': 'Velocidad de almacenamiento',
            'status': 'Prueba completada' if available else 'No disponible',
            'short_status': 'Medido' if available else 'N/A',
            'tone': 'cyan' if available else 'muted', 'headline': headline,
            'secondary': write_text, 'display_headline': display_headline, 'display_secondary': display_secondary,
            'verdict': 'Lectura y escritura medidas' if available else 'No hay una medición disponible',
            'meaning': ('Mide transferencias secuenciales del volumen probado intentando evitar la caché del sistema.' if cache_resistant else 'Mide transferencias secuenciales reales del volumen probado, pero Windows puede haber usado caché en esta ejecución.'),
            'technical_detail': f'{sample_text} · {io_mode} · Duración {duration_text}',
            'explanation': explanation,
            'interpretation': interpretation,
        }

    if key == 'gpu':
        value = _num(r.get('value'))
        status = str(r.get('status') or '').upper().strip()
        reason = _short(r.get('reason') or '')
        renderer = _short(r.get('renderer') or '')
        api = _short(r.get('api') or 'DirectX 11')
        primary_scene = _short(r.get('primary_scene') or 'high')
        if status == 'UNAVAILABLE' or (value is None and status not in {'ERROR','PARTIAL','CANCELLED'}):
            return {
                'title': 'GPU', 'subtitle': 'Benchmark 3D DirectX 11', 'status': 'No disponible', 'short_status': 'N/A', 'tone': 'muted',
                'headline': 'Sin benchmark DirectX medible',
                'secondary': reason or 'Direct3D 11 no pudo inicializar un adaptador de hardware.',
                'verdict': 'La prueba gráfica no estuvo disponible',
                'meaning': 'CPU, RAM y SSD siguen siendo válidos. CorePulse deja GPU como N/A en vez de mezclar otra metodología.',
                'technical_detail': reason or f'Proveedor: {GPU_PROVIDER}',
                'explanation': f'El benchmark {GPU_BENCHMARK_LABEL} requiere Direct3D 11 de hardware y no hace fallback silencioso a otra metodología.',
                'interpretation': 'Revisa el controlador gráfico o la compatibilidad DirectX; no se crea una puntuación estimada.',
            }
        if status == 'ERROR':
            return {
                'title': 'GPU', 'subtitle': 'Benchmark 3D DirectX 11', 'status': 'No se pudo completar', 'short_status': 'Aviso', 'tone': 'amber',
                'headline': 'Prueba DirectX incompleta', 'secondary': reason or 'Direct3D devolvió un error.',
                'verdict': 'La carga gráfica no terminó',
                'meaning': 'El resto del benchmark sigue siendo válido. La GPU queda con el error real y no con un valor estimado.',
                'technical_detail': reason or f'Proveedor: {GPU_PROVIDER}',
                'explanation': 'CorePulse conserva la causa concreta del fallo para que la prueba pueda corregirse o repetirse.',
                'interpretation': 'No comparar esta ejecución con una sesión completa.',
            }
        low = _num(r.get('fps_1pct_low') if r.get('fps_1pct_low') is not None else r.get('one_percent_low_fps'))
        headline = f'{human_number(value, 1)} FPS' if value is not None else 'Escenas DirectX completadas'
        secondary_parts = [f'Escena primaria: {primary_scene}']
        if low is not None:
            secondary_parts.append(f'1% Low {human_number(low, 1)} FPS')
        gpu_ft = _num(r.get('gpu_frame_time_avg_ms'))
        if gpu_ft is not None:
            secondary_parts.append(f'GPU {human_number(gpu_ft, 2)} ms')
        if renderer:
            secondary_parts.append(renderer)
        secondary = ' · '.join(secondary_parts)
        return {
            'title': 'GPU', 'subtitle': f'Benchmark {GPU_BENCHMARK_LABEL} · DirectX 11 · tiempo determinista', 'status': 'Prueba 3D completada', 'short_status': 'Medida', 'tone': 'purple',
            'headline': headline, 'secondary': secondary, 'display_headline': headline, 'display_secondary': secondary,
            'verdict': 'Escenas 3D progresivas medidas con DirectX',
            'meaning': 'CorePulse renderiza Valle, Bosque, Lago y Extreme con terreno, agua con Fresnel y microdetalle, vegetación 3D, rocas, nubes soft-card y shaders progresivamente más pesados.',
            'technical_detail': f'{api} · {renderer or "adaptador N/A"} · Duración {duration_text}',
            'explanation': f'El perfil estándar hace 5 s de warm-up global, settle por fase y 8 frames de prime descartados. Cada fase medida termina por reloj de pared y la cámara usa ese mismo reloj, mientras FPS/1% Low cronometran sólo render+Present. Callbacks, telemetría, message pump y lectura de queries quedan fuera del frametime. Extreme es la referencia principal de {GPU_BENCHMARK_LABEL} y el tiempo GPU se obtiene con timestamp queries cuando el driver las valida.',
            'interpretation': f'Compara sólo sesiones {GPU_BENCHMARK_LABEL} con la misma resolución y metodología. El resultado no equivale a 3DMark ni predice un juego concreto.',
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

    # V162: Benchmark mide y describe; la interpretación térmica vive en Diagnóstico.
    return {'label': label, 'value': value, 'change': change, 'tone': tone}



def _telemetry_max(telemetry, key):
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    row = telemetry.get(key) if isinstance(telemetry.get(key), dict) else {}
    return _num(row.get('max'))


def benchmark_component_reading(key, result, *, telemetry=None, safety_stop=None):
    """Lectura CorePulse basada sólo en evidencia de esta ejecución.

    No intenta decidir si un componente es "rápido" o "lento" frente a otros
    equipos. Sí puede decir si la prueba terminó, si verificó integridad, si la
    propia medición fue estable y si se observaron condiciones térmicas de
    atención. Cualquier conclusión que no esté respaldada queda como N/A.
    """
    key = str(key or '').lower().strip()
    row = result if isinstance(result, dict) else {}
    status = str(row.get('status') or '').upper().strip()
    telemetry = telemetry if isinstance(telemetry, dict) else {}
    reason = _short(row.get('reason') or '', 180)

    def out(label, tone, summary, scope='', short=''):
        return {
            'label': str(label),
            'tone': str(tone),
            'summary': str(summary),
            'scope': str(scope or ''),
            'short': str(short or summary or ''),
        }

    if safety_stop or status == 'SAFETY_STOP':
        return out(
            'DETENIDO POR SEGURIDAD', 'red',
            f"CorePulse interrumpió la carga para proteger el equipo. {reason or str(safety_stop or '').strip()}".strip(),
            'El rendimiento de una ejecución detenida no debe compararse con una sesión completa.',
        )
    if status in {'ERROR', 'UNAVAILABLE'}:
        return out(
            'NO EVALUABLE', 'muted',
            reason or 'La prueba no produjo una medición válida; CorePulse no rellena el dato.',
            'N/A no significa que el componente esté averiado: significa que esta prueba no pudo evaluarlo.',
        )
    if status in {'CANCELLED', 'SKIPPED'}:
        return out(
            'NO EVALUABLE', 'muted',
            reason or ('La prueba fue cancelada.' if status == 'CANCELLED' else 'La prueba no fue seleccionada.'),
            'No se emite una conclusión sin una ejecución completa.',
        )
    if status == 'PARTIAL':
        return out(
            'PRUEBA PARCIAL · REVISAR', 'amber',
            reason or 'Se obtuvieron datos reales, pero no toda la prueba terminó con evidencia suficiente.',
            'Conserva la evidencia, pero no la compares como si fuera una ejecución completa.',
        )

    if key == 'cpu':
        quality = str(row.get('measurement_quality') or 'N/A').upper()
        integrity = row.get('integrity_ok')
        temp = _telemetry_max(telemetry, 'cpu_temp')
        hot = temp is not None and temp >= 95.0
        variable = quality == 'VARIABLE'
        if integrity is False:
            return out(
                'REVISAR RESULTADO', 'red',
                'La carga terminó, pero una verificación interna de la prueba no fue satisfactoria.',
                'Esto describe la validez del benchmark; no diagnostica por sí solo una falla física del CPU.',
            )
        if hot and variable:
            return out(
                'FUNCIONA · CALIENTE Y VARIABLE', 'amber',
                f'El CPU completó las cargas reales, pero la medición fue variable y alcanzó {human_number(temp, 1)} °C.',
                'Repite en condiciones equivalentes y revisa refrigeración antes de usar este resultado como referencia.',
                f'Completó la prueba, pero llegó a {human_number(temp, 0)} °C y varió entre muestras.',
            )
        if hot:
            return out(
                'FUNCIONA · TEMPERATURA ALTA', 'amber',
                f'El CPU completó la prueba, pero alcanzó {human_number(temp, 1)} °C durante la ejecución.',
                'El benchmark confirma ejecución; la temperatura alta merece revisión térmica.',
                f'Completó la prueba, pero alcanzó {human_number(temp, 0)} °C.',
            )
        if variable:
            return out(
                'FUNCIONA · RESULTADO VARIABLE', 'amber',
                'El CPU completó las cargas, pero las muestras variaron más que la tolerancia interna del benchmark.',
                'Para comparar sesiones, repite con el mismo perfil de energía y condiciones térmicas.',
                'Completó la prueba, pero el rendimiento varió entre muestras.',
            )
        return out(
            'FUNCIONA CORRECTAMENTE EN ESTA PRUEBA', 'green',
            'Las cargas del CPU terminaron con datos válidos y una medición estable.',
            'Esto valida esta ejecución; no clasifica el CPU frente a otros modelos sin una referencia comparable.',
            'Cargas completadas con una medición estable.',
        )

    if key == 'ram':
        quality = str(row.get('measurement_quality') or 'N/A').upper()
        integrity = row.get('integrity_ok')
        if integrity is False:
            return out(
                'REVISAR INTEGRIDAD', 'red',
                'La copia de memoria no coincidió con la verificación posterior esperada.',
                'Repite la prueba antes de concluir que existe una falla física de RAM.',
            )
        if integrity is not True:
            return out(
                'MEDICIÓN SIN VERIFICACIÓN COMPLETA', 'amber',
                'Hay rendimiento medido, pero CorePulse no tiene confirmación completa de integridad para esta ejecución.',
                'No se considera equivalente a una prueba de RAM verificada.',
            )
        if quality == 'VARIABLE':
            cv = _num(row.get('bandwidth_cv_percent'))
            extra = f' La variación entre muestras fue {human_number(cv, 1)}%.' if cv is not None else ''
            return out(
                'FUNCIONA · RESULTADO VARIABLE', 'amber',
                'La RAM pasó la verificación de integridad, pero el ancho de banda no fue uniforme entre muestras.' + extra,
                'La memoria movió datos correctamente; repite si quieres una referencia de rendimiento más estable.',
                'Integridad OK; el rendimiento varió entre muestras.',
            )
        return out(
            'FUNCIONA CORRECTAMENTE EN ESTA PRUEBA', 'green',
            'La copia terminó y la verificación byte a byte coincidió con los datos esperados.',
            'Este benchmark confirma integridad de la copia y estabilidad de la medición, no reemplaza un test prolongado de memoria.',
            'Integridad OK y medición estable en esta prueba.',
        )

    if key == 'ssd':
        quality = str(row.get('measurement_quality') or 'N/A').upper()
        read = _num(row.get('read_mbps'))
        write = _num(row.get('write_mbps'))
        random4k = row.get('random_4k') if isinstance(row.get('random_4k'), dict) else {}
        random_ok = str(random4k.get('status') or '').upper() == 'OK'
        if read is None and write is None:
            return out(
                'NO EVALUABLE', 'muted',
                'La prueba no obtuvo lectura ni escritura válidas.',
                'CorePulse deja el rendimiento como N/A en vez de estimarlo.',
            )
        if quality == 'VARIABLE':
            return out(
                'FUNCIONA · RESULTADO VARIABLE', 'amber',
                'El SSD completó E/S real, pero las muestras variaron más que la tolerancia interna del benchmark.',
                'Esto evalúa rendimiento de E/S del volumen probado; salud física y desgaste se evalúan con SMART.',
                'E/S completada; el rendimiento varió entre muestras.',
            )
        random_text = ' y Random 4K QD1' if random_ok else ''
        return out(
            'E/S FUNCIONANDO CORRECTAMENTE', 'green',
            f'Lectura y escritura secuencial{random_text} terminaron con datos válidos. La salud física y el desgaste se evalúan aparte con SMART.',
            'Este benchmark mide rendimiento del volumen probado; no sustituye SMART ni determina desgaste del SSD.',
            'Lectura y escritura completadas con datos válidos.',
        )

    if key == 'gpu':
        fps = _num(row.get('frames_per_s') if row.get('frames_per_s') is not None else row.get('value'))
        low = _num(row.get('one_percent_low_fps') if row.get('one_percent_low_fps') is not None else row.get('fps_1pct_low'))
        scenes = row.get('scenes') if isinstance(row.get('scenes'), list) else []
        valid_scenes = sum(1 for scene in scenes if isinstance(scene, dict) and str(scene.get('status') or '').upper() == 'OK')
        scene_count = len(scenes)
        temp = _telemetry_max(telemetry, 'gpu_temp')
        hot = temp is not None and temp >= 88.0
        ratio = (low / fps * 100.0) if fps and low is not None and fps > 0 else None
        phase_results = row.get('phase_results') if isinstance(row.get('phase_results'), list) else []
        phase_ratios = []
        for phase in phase_results:
            if not isinstance(phase, dict):
                continue
            pfps = _num(phase.get('frames_per_s'))
            plow = _num(phase.get('one_percent_low_fps'))
            if pfps and plow is not None and pfps > 0:
                phase_ratios.append(plow / pfps * 100.0)
        worst_ratio = min(phase_ratios) if phase_ratios else ratio
        irregular = worst_ratio is not None and worst_ratio < 50.0
        uniformity = ''
        if ratio is not None:
            uniformity = f' El 1% Low de Extreme equivale al {human_number(ratio, 0)}% de su promedio.'
        if worst_ratio is not None and phase_ratios:
            uniformity += f' En la escena menos uniforme, el 1% Low fue {human_number(worst_ratio, 0)}% del FPS medio.'
        completed = status == 'OK' and (scene_count == 0 or valid_scenes == scene_count) and fps is not None
        if not completed:
            return out(
                'PRUEBA GRÁFICA INCOMPLETA', 'amber',
                reason or f'CorePulse obtuvo {valid_scenes}/{scene_count or 4} escenas válidas.',
                f'Compara rendimiento sólo con ejecuciones completas {GPU_BENCHMARK_LABEL} a la misma resolución.',
                f'Se completaron {valid_scenes}/{scene_count or 4} escenas; faltó evidencia para cerrar la prueba.',
            )
        scene_text = f'{valid_scenes}/{scene_count} escenas' if scene_count else 'la escena principal'
        if hot and irregular:
            return out(
                'COMPLETADA · CALIENTE E IRREGULAR', 'amber',
                f'La GPU completó {scene_text}, pero alcanzó {human_number(temp, 1)} °C y la entrega de frames fue irregular.' + uniformity,
                'Esto describe esta ejecución; no demuestra por sí solo una falla física ni clasifica la GPU frente a otros modelos.',
                f'{scene_text.capitalize()} válidas; temperatura alta y 1% Low irregular.',
            )
        if hot:
            return out(
                'COMPLETADA · TEMPERATURA ALTA', 'amber',
                f'La GPU completó {scene_text} con FPS reales, pero alcanzó {human_number(temp, 1)} °C.' + uniformity,
                f'La prueba confirma ejecución; no decide si {human_number(fps, 1)} FPS es “bueno” frente a otras GPUs sin una referencia {GPU_BENCHMARK_LABEL} equivalente.',
                f'{scene_text.capitalize()} válidas; alcanzó {human_number(temp, 0)} °C.',
            )
        if irregular:
            return out(
                'PRUEBA COMPLETADA · ENTREGA IRREGULAR', 'amber',
                f'La GPU completó {scene_text} con FPS reales, pero el 1% Low quedó muy alejado del promedio en al menos una escena.' + uniformity,
                'Puede reflejar picos de frametime de esta ejecución. Repite en condiciones equivalentes antes de atribuirlo al hardware.',
                f'{scene_text.capitalize()} válidas; hubo diferencias grandes entre FPS medio y 1% Low.',
            )
        return out(
            'FUNCIONA CORRECTAMENTE EN ESTA PRUEBA', 'green',
            f'La GPU completó {scene_text} con mediciones reales de FPS y 1% Low.' + uniformity,
            f'CorePulse valida esta ejecución; el nivel absoluto de rendimiento se compara sólo contra sesiones {GPU_BENCHMARK_LABEL} equivalentes.',
            f'{scene_text.capitalize()} válidas y entrega de frames consistente.',
        )

    return out('NO EVALUABLE', 'muted', 'No hay una lectura específica disponible para este componente.')


def benchmark_run_conclusion(selected, visual, suite, *, tele_visual=None, tele_suite=None):
    """Resumen corto y accionable de una ejecución completa.

    Prioriza observaciones reales y evita repetir todas las explicaciones largas
    de cada componente. No usa rankings externos ni umbrales de rendimiento
    entre modelos distintos.
    """
    selected = [str(x).lower() for x in (selected or [])]
    suite = suite if isinstance(suite, dict) else {}
    visual = visual if isinstance(visual, dict) else {}
    tele_visual = tele_visual if isinstance(tele_visual, dict) else {}
    tele_suite = tele_suite if isinstance(tele_suite, dict) else {}
    stop_reason = suite.get('safety_stop')
    rows = {
        'gpu': benchmark_component_reading('gpu', visual, telemetry=tele_visual, safety_stop=stop_reason),
        'cpu': benchmark_component_reading('cpu', suite.get('cpu') or {}, telemetry=tele_suite, safety_stop=stop_reason),
        'ram': benchmark_component_reading('ram', suite.get('ram') or {}, telemetry=tele_suite, safety_stop=stop_reason),
        'ssd': benchmark_component_reading('ssd', suite.get('ssd') or {}, telemetry=tele_suite, safety_stop=stop_reason),
    }
    names = {'gpu': 'GPU', 'cpu': 'CPU', 'ram': 'RAM', 'ssd': 'SSD'}
    tones = [str(rows[k].get('tone') or '').lower() for k in selected if k in rows]
    if 'red' in tones:
        headline, tone = 'Requiere atención', 'red'
    elif 'amber' in tones:
        headline, tone = 'Benchmark completado con observaciones', 'amber'
    else:
        headline, tone = 'Todo lo medido funcionó correctamente en esta prueba', 'green'
    items = []
    for key in ('cpu', 'gpu', 'ram', 'ssd'):
        if key not in selected:
            continue
        reading = rows[key]
        short = str(reading.get('short') or reading.get('summary') or '').strip()
        items.append({
            'component': names[key],
            'text': short,
            'tone': str(reading.get('tone') or 'muted'),
            'label': str(reading.get('label') or 'NO EVALUABLE'),
        })
    return {
        'headline': headline,
        'tone': tone,
        'items': items[:4],
        'note': 'Las conclusiones describen esta ejecución. CorePulse no inventa rankings ni atribuye una variación aislada a una falla física.',
    }

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
        if deltas:
            return 'Rendimiento y cambios de telemetría medidos; Diagnóstico interpreta temperatura, frecuencia y throttling.', 'cyan'
        return 'Resultado listo para comparar con futuras ejecuciones equivalentes en este mismo PC.', 'cyan'

    if key == 'ram':
        return 'Tasa de copia sostenida medida; Diagnóstico interpreta presión de memoria usando el contexto completo.', 'cyan'

    if key == 'ssd':
        return 'Lectura y escritura secuencial completadas correctamente.', 'cyan'

    if key == 'gpu':
        row = deltas.get('gpu_temp') if isinstance(deltas.get('gpu_temp'), dict) else {}
        after = _num(row.get('after'))
        if after is not None and after >= 90:
            return 'Atención: la GPU terminó con una temperatura muy alta.', 'red'
        if after is not None and after >= 80:
            return 'La GPU terminó caliente; revisa el cambio de temperatura.', 'amber'
        return f'Escenas DirectX 11 completadas; compara sólo ejecuciones {GPU_BENCHMARK_LABEL} equivalentes.', 'purple'

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

