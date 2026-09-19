"""Prueba explícita: evidencia de API separada de confirmación humana.

Sólo se persisten resultados y nombres/identidades. La voz nunca se escribe.
"""
import copy
import json
import math
import os
import threading
import time
import uuid
from pathlib import Path

from core.runtime_paths import data_path
from core.audio_backend import AudioBackend, AudioError

ANSWERS = {'Sí': 'VERIFICADO', 'No': 'PROBLEMA REPORTADO', 'No estoy seguro': 'NO CONCLUYENTE'}
RECENT_SECONDS = 24 * 3600


def empty_result(reason='Prueba guiada no realizada.'):
    return {'schema': 1, 'timestamp': None, 'devices': {}, 'technical': {},
            'answers': {}, 'status': 'NO EVALUADO', 'reason': reason}


def summary(result):
    answers = result.get('answers', {})
    if 'PROBLEMA REPORTADO' in answers.values():
        return 'PROBLEMA REPORTADO'
    if all(answers.get(key) == 'VERIFICADO' for key in ('left', 'right', 'both', 'microphone')):
        return 'AUDIO VERIFICADO'
    return 'VERIFICACIÓN PARCIAL' if answers else 'NO EVALUADO'


class AudioTest:
    def __init__(self, provider=None, path=None):
        self.provider = provider or AudioBackend()
        self.path = Path(path) if path else data_path('audio_test_latest.json')
        self.result = empty_result()
        self.recording = None
        self.cancel = threading.Event()
        self.closed = False
        self.pending = None
        self.lock = threading.RLock()

    def save(self):
        with self.lock:
            self.result['status'] = summary(self.result)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
            try:
                temp.write_text(json.dumps(self.result, ensure_ascii=False), encoding='utf-8')
                os.replace(temp, self.path)
            finally:
                temp.unlink(missing_ok=True)

    def refresh(self):
        devices = self.provider.devices()
        with self.lock:
            if self.closed:
                return
            before = self.result.get('devices', {})
            if before and any(before.get(k, {}).get('id') != devices[k].get('id') for k in ('output', 'input')):
                self.clear_recording()
                self.result = empty_result('Cambió el dispositivo predeterminado; repite la prueba.')
                self.pending = None
                self.save()
            self.result['devices'] = devices
        return devices

    def clear_recording(self):
        if self.recording:
            self.recording[0].clear()
        self.recording = None

    def _begin(self, key, direction):
        if self.closed:
            raise AudioError('Prueba cerrada.')
        self.pending = None
        self.result['answers'].pop(key, None)
        self.result['technical'].pop(key, None)
        self.result['timestamp'] = time.time()
        self.save()  # Invalida el resultado anterior antes de iniciar otra carga.
        devices = self.refresh()
        info = devices[direction]
        if not info.get('available'):
            raise AudioError(info.get('error') or 'Dispositivo no disponible: N/A.')
        return info

    def play(self, key):
        info = self._begin(key, 'output')
        if key == 'microphone' and not self.recording:
            raise AudioError('Primero graba una prueba.')
        self.provider.play('both' if key == 'microphone' else key, info['id'], self.cancel,
                           recording=self.recording if key == 'microphone' else None)
        self._completed(key, {'api_completed': True})

    def record(self, on_level):
        self.clear_recording()
        self.result['technical'].pop('capture', None)
        info = self._begin('microphone', 'input')
        peak = 0.
        def level(value):
            nonlocal peak
            if math.isfinite(value):
                peak = max(peak, value)
                on_level(value)
        recording = self.provider.record(info['id'], self.cancel, level)
        if recording[1] <= 0 or len(recording[0]) < recording[1] * 4.5:
            recording[0].clear()
            raise AudioError('Grabación incompleta; repite la prueba.')
        with self.lock:
            if self.closed or self.cancel.is_set():
                recording[0].clear()
                raise AudioError('Grabación cancelada.')
            self.recording = recording
            self.result['technical']['capture'] = {'frames': len(recording[0]), 'sample_rate': recording[1],
                'duration_s': len(recording[0]) / recording[1], 'peak': peak,
                'signal_detected': peak > 0., 'completed': True}
            self.save()

    def _completed(self, key, technical):
        with self.lock:
            if self.closed or self.cancel.is_set():
                raise AudioError('Prueba cancelada.')
            self.result['technical'][key] = technical
            self.pending = key
            self.save()

    def confirm(self, answer):
        with self.lock:
            if self.closed or self.pending is None or answer not in ANSWERS:
                raise AudioError('No hay una reproducción finalizada pendiente de confirmación.')
            ids = self.provider.default_ids()
            if any(ids.get(k) != self.result['devices'].get(k, {}).get('id') for k in ('output', 'input')):
                self.result = empty_result('Cambió el dispositivo; confirmación descartada.')
                self.pending = None
                self.clear_recording()
                self.save()
                raise AudioError('Cambió el dispositivo predeterminado. Repite la prueba.')
            self.result['answers'][self.pending] = ANSWERS[answer]
            self.result['timestamp'] = time.time()
            self.pending = None
            self.save()

    def close(self):
        with self.lock:
            self.closed = True
            self.cancel.set()
            self.pending = None
            self.clear_recording()



def automatic_audio_probe(provider=None, progress_callback=None, cancel_check=None):
    """Prueba técnica automática usada por Diagnóstico.

    Reproduce tonos breves por izquierda/derecha/ambos y abre el stream de
    captura durante ~1 s. Esto verifica ruta/API/dispositivo, no pretende
    sustituir la confirmación humana de que el sonido se oyó correctamente.
    No cambia el volumen maestro y no persiste la grabación.
    """
    provider = provider or AudioBackend()
    cancel = threading.Event()
    result = empty_result('Prueba técnica automática no iniciada.')
    result['mode'] = 'AUTOMATIC_TECHNICAL'
    result['timestamp'] = time.time()
    result['technical'] = {}
    result['errors'] = []

    def cancelled():
        try:
            return bool(callable(cancel_check) and cancel_check())
        except Exception:
            return False

    def emit(frac, stage, detail=''):
        if callable(progress_callback):
            try:
                progress_callback(max(0.0, min(1.0, float(frac))), str(stage), str(detail or ''))
            except Exception:
                pass

    try:
        devices = provider.devices()
    except Exception as exc:
        result['reason'] = f'No se pudieron consultar dispositivos de audio: {type(exc).__name__}: {exc}'
        result['status'] = 'NO EVALUADO'
        result['errors'].append(result['reason'])
        return result
    result['devices'] = devices if isinstance(devices, dict) else {}

    output = result['devices'].get('output') if isinstance(result['devices'].get('output'), dict) else {}
    input_dev = result['devices'].get('input') if isinstance(result['devices'].get('input'), dict) else {}
    if not output.get('available'):
        message = str(output.get('error') or 'Salida de audio no disponible')
        result['errors'].append(message)
    else:
        for index, key in enumerate(('left', 'right', 'both')):
            if cancelled():
                cancel.set()
                result['status'] = 'CANCELLED'
                result['reason'] = 'Prueba de audio cancelada.'
                return result
            emit(0.08 + index * 0.20, f'Audio · {key}', str(output.get('name') or 'Salida predeterminada'))
            try:
                provider.play(key, output.get('id'), cancel)
                result['technical'][key] = {'api_completed': True}
            except Exception as exc:
                result['technical'][key] = {'api_completed': False, 'error': f'{type(exc).__name__}: {exc}'}
                result['errors'].append(f'{key}: {exc}')

    if cancelled():
        cancel.set()
        result['status'] = 'CANCELLED'
        result['reason'] = 'Prueba de audio cancelada.'
        return result

    emit(0.72, 'Audio · micrófono', str(input_dev.get('name') or 'Entrada predeterminada'))
    if not input_dev.get('available'):
        result['technical']['capture'] = {'completed': False, 'error': str(input_dev.get('error') or 'Entrada no disponible')}
        result['errors'].append(str(input_dev.get('error') or 'Entrada de audio no disponible'))
    else:
        peak = 0.0
        def on_level(value):
            nonlocal peak
            try:
                if math.isfinite(float(value)):
                    peak = max(peak, float(value))
            except Exception:
                pass
        try:
            try:
                samples, rate = provider.record(input_dev.get('id'), cancel, on_level, duration_s=0.8)
            except TypeError:
                # Compatibilidad con proveedores antiguos/de prueba.
                samples, rate = provider.record(input_dev.get('id'), cancel, on_level)
            result['technical']['capture'] = {
                'completed': True, 'frames': len(samples or []), 'sample_rate': rate,
                'duration_s': (len(samples or []) / float(rate)) if rate else None,
                'peak': peak, 'signal_detected': peak > 0.0,
            }
        except Exception as exc:
            result['technical']['capture'] = {'completed': False, 'error': f'{type(exc).__name__}: {exc}'}
            result['errors'].append(f'microphone: {exc}')

    output_ok = all(bool((result['technical'].get(key) or {}).get('api_completed')) for key in ('left', 'right', 'both'))
    input_ok = bool((result['technical'].get('capture') or {}).get('completed'))
    result['status'] = 'AUDIO TÉCNICO OK' if output_ok and input_ok else 'VERIFICACIÓN PARCIAL' if output_ok or input_ok else 'PROBLEMA REPORTADO'
    result['reason'] = ('Rutas de reproducción y captura verificadas automáticamente.' if output_ok and input_ok
                        else 'La comprobación automática no pudo completar todas las rutas de audio.')
    emit(1.0, 'Audio completado', result['status'])
    return result

def recent_audio_result(path=None, provider=None, now=None):
    """Consulta pasiva para Diagnóstico: jamás llama play/record/devices."""
    try:
        target = Path(path) if path else data_path('audio_test_latest.json')
        if not target.is_file():
            return empty_result()
        result = json.loads(target.read_text(encoding='utf-8'))
        age = (time.time() if now is None else now) - float(result.get('timestamp') or 0)
        if result.get('schema') != 1 or not 0 <= age <= RECENT_SECONDS:
            return empty_result('Sin prueba de las últimas 24 horas.')
        ids = (provider or AudioBackend()).default_ids()
        if any(ids.get(k) != result.get('devices', {}).get(k, {}).get('id') for k in ('output', 'input')):
            return empty_result('Dispositivos predeterminados cambiados; repetir prueba.')
        # No confiar en el status persistido ni en confirmaciones sin ejecución.
        answers = result.get('answers', {})
        tech = result.get('technical', {})
        result['answers'] = {k: v for k, v in answers.items()
                             if k in ('left', 'right', 'both', 'microphone')
                             and v in ANSWERS.values() and tech.get(k, {}).get('api_completed')}
        if not tech.get('capture', {}).get('completed'):
            result['answers'].pop('microphone', None)
        result['status'] = summary(result)
        return copy.deepcopy(result)
    except Exception:
        return empty_result('Evidencia de audio no disponible o no verificable.')


def evidence_rows(result):
    result = result or empty_result()
    devices = result.get('devices', {})
    answers = result.get('answers', {})
    capture = result.get('technical', {}).get('capture', {})
    stereo = devices.get('output', {}).get('stereo')
    return [('Salida', devices.get('output', {}).get('name') or 'N/A'),
            ('Canal izquierdo', answers.get('left', 'N/A' if stereo is False else 'NO EVALUADO')),
            ('Canal derecho', answers.get('right', 'N/A' if stereo is False else 'NO EVALUADO')),
            ('Ambos canales', answers.get('both', 'NO EVALUADO')),
            ('Micrófono', devices.get('input', {}).get('name') or 'N/A'),
            ('Señal capturada', 'SÍ' if capture.get('signal_detected') else 'NO' if capture.get('completed') else 'N/A'),
            ('Pico de amplitud (0–1)', str(round(capture['peak'], 4)) if 'peak' in capture else 'N/A'),
            ('Reproducción del micrófono', answers.get('microphone', 'NO EVALUADO'))]
