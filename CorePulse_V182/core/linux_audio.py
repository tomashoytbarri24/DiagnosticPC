"""Backend de prueba de audio para Linux usando ALSA (aplay/arecord).

No cambia el volumen maestro ni mezcla del sistema. Si alsa-utils no está
instalado, la capacidad se reporta como N/A en lugar de simular una prueba.
"""
from __future__ import annotations

import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import wave

from core.audio_common import AudioError


TEST_TONE_AMPLITUDE = 0.32


def _run_text(args: list[str], timeout=2.0) -> str | None:
    try:
        cp = subprocess.run(args, capture_output=True, text=True, errors='replace', timeout=timeout)
        return (cp.stdout or '').strip() if cp.returncode == 0 else None
    except Exception:
        return None


def _default_endpoint(kind: str) -> str:
    pactl = shutil.which('pactl')
    if pactl:
        sub = 'sink' if kind == 'output' else 'source'
        value = _run_text([pactl, f'get-default-{sub}'])
        if value:
            return value
    return 'default'


def _wait_process(proc: subprocess.Popen, cancel, timeout: float):
    end = time.monotonic() + timeout
    while proc.poll() is None:
        if cancel.is_set():
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            raise AudioError('Prueba cancelada.')
        if time.monotonic() >= end:
            try:
                proc.kill()
            except Exception:
                pass
            raise AudioError('El dispositivo de audio no respondió a tiempo.')
        time.sleep(0.05)
    if proc.returncode != 0:
        err = ''
        try:
            err = (proc.stderr.read() if proc.stderr else '') or ''
        except Exception:
            pass
        raise AudioError(f'Audio Linux no pudo completar la operación: {err.strip() or f"código {proc.returncode}"}')


def _write_tone(path: Path, channel: str, rate: int = 44100):
    channels = 2
    duration = 0.65
    frames = int(rate * duration)
    payload = bytearray()
    for i in range(frames):
        env = min(1.0, i / max(1, rate * .02), (frames - 1 - i) / max(1, rate * .02))
        sample = TEST_TONE_AMPLITUDE * env * math.sin(2 * math.pi * 440 * i / rate)
        val = int(max(-32768, min(32767, sample * 32767)))
        left = val if channel in ('left', 'both') else 0
        right = val if channel in ('right', 'both') else 0
        payload.extend(struct.pack('<hh', left, right))
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(payload))


def _write_recording_playback(path: Path, recording, rate: int = 44100):
    source, source_rate = recording
    source = list(source or [])
    if not source or not source_rate:
        raise AudioError('La grabación no contiene audio reproducible.')
    peak = max((abs(float(v)) for v in source), default=0.0)
    gain = min(1.0, .25 / peak) if peak else 1.0
    count = max(1, int(len(source) * rate / float(source_rate)))
    payload = bytearray()
    for i in range(count):
        pos = min(len(source) - 1, int(i * float(source_rate) / rate))
        sample = max(-1.0, min(1.0, float(source[pos]) * gain))
        val = int(sample * 32767)
        payload.extend(struct.pack('<hh', val, val))
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(payload))


def _read_wav_mono(path: Path):
    with wave.open(str(path), 'rb') as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if width != 2:
        raise AudioError('Formato de captura ALSA no compatible.')
    values = [v[0] / 32768.0 for v in struct.iter_unpack('<h', frames)]
    if channels > 1:
        mono = []
        for i in range(0, len(values), channels):
            block = values[i:i + channels]
            if block:
                mono.append(sum(block) / len(block))
        values = mono
    return values, rate


class LinuxAudio:
    def __init__(self):
        self.aplay = shutil.which('aplay')
        self.arecord = shutil.which('arecord')

    def default_ids(self):
        return {
            'output': f"alsa:{_default_endpoint('output')}" if self.aplay else None,
            'input': f"alsa:{_default_endpoint('input')}" if self.arecord else None,
        }

    def devices(self):
        ids = self.default_ids()
        out_name = _default_endpoint('output')
        in_name = _default_endpoint('input')
        return {
            'output': {
                'available': bool(self.aplay), 'id': ids.get('output'),
                'name': f'Linux audio · {out_name}' if self.aplay else 'N/A',
                'channels': 2, 'rate': 44100, 'bits': 16, 'align': 4,
                'tag': 1, 'stereo': True, 'mask': 3,
                'error': None if self.aplay else 'Instala alsa-utils para habilitar aplay.',
            },
            'input': {
                'available': bool(self.arecord), 'id': ids.get('input'),
                'name': f'Linux audio · {in_name}' if self.arecord else 'N/A',
                'channels': 1, 'rate': 44100, 'bits': 16, 'align': 2,
                'tag': 1, 'stereo': False, 'mask': None,
                'error': None if self.arecord else 'Instala alsa-utils para habilitar arecord.',
            },
        }

    def _check_expected(self, direction: str, expected):
        current = self.default_ids().get(direction)
        if current != expected:
            raise AudioError('Cambió el dispositivo predeterminado. Actualiza dispositivos y repite la prueba.')

    def play(self, channel, expected, cancel, recording=None):
        if not self.aplay:
            raise AudioError('Audio Linux no disponible: falta aplay (paquete alsa-utils).')
        self._check_expected('output', expected)
        if cancel.is_set():
            raise AudioError('Prueba cancelada.')
        with tempfile.TemporaryDirectory(prefix='corepulse-audio-') as tmp:
            path = Path(tmp) / 'test.wav'
            if recording is None:
                _write_tone(path, channel)
            else:
                _write_recording_playback(path, recording)
            proc = subprocess.Popen([self.aplay, '-q', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            _wait_process(proc, cancel, timeout=12.0)

    def record(self, expected, cancel, on_level, duration_s=5.0):
        if not self.arecord:
            raise AudioError('Micrófono Linux no disponible: falta arecord (paquete alsa-utils).')
        self._check_expected('input', expected)
        if cancel.is_set():
            raise AudioError('Grabación cancelada.')
        duration_s = max(0.5, min(5.0, float(duration_s)))
        with tempfile.TemporaryDirectory(prefix='corepulse-mic-') as tmp:
            path = Path(tmp) / 'capture.wav'
            # arecord sólo acepta segundos enteros para -d; un segundo basta para
            # comprobar automáticamente que el stream de captura abre y entrega datos.
            capture_seconds = max(1, int(math.ceil(duration_s)))
            cmd = [self.arecord, '-q', '-d', str(capture_seconds), '-f', 'S16_LE', '-r', '44100', '-c', '1', '-t', 'wav', str(path)]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            _wait_process(proc, cancel, timeout=max(4.0, capture_seconds + 3.0))
            samples, rate = _read_wav_mono(path)
        peak = max((abs(v) for v in samples), default=0.0)
        try:
            on_level(peak)
        except Exception:
            pass
        return samples, rate
