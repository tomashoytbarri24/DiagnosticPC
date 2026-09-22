import json

from core import benchmark_engine


def test_gpu_v12_last_result_is_created_and_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark_engine, 'executable_root', lambda: tmp_path)
    first = {
        'kind': 'GPU', 'status': 'OK', 'frames_per_s': 61.25,
        'gpu_frame_time_avg_ms': None, 'policy': 'REAL_OR_NA',
    }
    path = benchmark_engine.save_last_gpu_v12_result(first)

    assert path == (tmp_path / 'resultados' / 'benchmark_gpu_v12_ultimo_resultado.json').resolve()
    assert json.loads(path.read_text(encoding='utf-8')) == first

    second = {
        'kind': 'GPU', 'status': 'OK', 'frames_per_s': 72.5,
        'gpu_frame_time_avg_ms': float('nan'), 'policy': 'REAL_OR_NA',
    }
    same_path = benchmark_engine.save_last_gpu_v12_result(second)
    saved = json.loads(same_path.read_text(encoding='utf-8'))

    assert same_path == path
    assert saved['frames_per_s'] == 72.5
    assert saved['gpu_frame_time_avg_ms'] == 'N/A'
    assert not path.with_name(path.name + '.tmp').exists()
