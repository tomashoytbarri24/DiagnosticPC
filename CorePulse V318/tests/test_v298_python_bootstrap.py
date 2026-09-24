from pathlib import Path

import core.python_compat as compat


def test_bootstrap_does_nothing_when_current_python_has_essentials(monkeypatch):
    monkeypatch.setattr(compat, 'missing_source_imports', lambda: [])
    assert compat.bootstrap_validated_runtime(__file__) is False


def test_bootstrap_provisions_when_pointer_is_missing(monkeypatch, tmp_path):
    target = tmp_path / 'python.exe'
    target.write_text('', encoding='utf-8')
    called = {'provision': 0, 'exec': 0}

    monkeypatch.setattr(compat, 'missing_source_imports', lambda: ['customtkinter'])
    monkeypatch.setattr(compat, 'enforce_minimum_python', lambda: None)
    monkeypatch.setattr(compat, 'validated_runtime_python', lambda: None)
    monkeypatch.setattr(compat, 'provision_runtime_for_current_python', lambda: called.__setitem__('provision', 1) or target)
    monkeypatch.setattr(compat.Path, 'resolve', lambda self: self)

    def fake_execve(exe, argv, env):
        called['exec'] += 1
        assert Path(exe) == target
        assert env['COREPULSE_RUNTIME_BOOTSTRAPPED'] == '1'
        raise RuntimeError('exec-called')

    monkeypatch.setattr(compat.os, 'execve', fake_execve)
    try:
        compat.bootstrap_validated_runtime(__file__)
    except RuntimeError as exc:
        assert str(exc) == 'exec-called'
    else:
        raise AssertionError('os.execve was not invoked')

    assert called == {'provision': 1, 'exec': 1}


def test_registered_runtime_is_reused_before_provisioning(monkeypatch, tmp_path):
    target = tmp_path / 'python.exe'
    target.write_text('', encoding='utf-8')
    monkeypatch.setattr(compat, 'missing_source_imports', lambda: ['customtkinter'])
    monkeypatch.setattr(compat, 'enforce_minimum_python', lambda: None)
    monkeypatch.setattr(compat, 'validated_runtime_python', lambda: target)
    monkeypatch.setattr(compat, '_runtime_matches_current_minor', lambda _target: True)
    monkeypatch.setattr(compat, 'provision_runtime_for_current_python', lambda: (_ for _ in ()).throw(AssertionError('should not provision')))
    monkeypatch.setattr(compat.Path, 'resolve', lambda self: self)

    def fake_execve(exe, argv, env):
        assert Path(exe) == target
        raise RuntimeError('exec-called')

    monkeypatch.setattr(compat.os, 'execve', fake_execve)
    try:
        compat.bootstrap_validated_runtime(__file__)
    except RuntimeError as exc:
        assert str(exc) == 'exec-called'


def test_runtime_minor_mismatch_forces_provision(monkeypatch, tmp_path):
    old_target = tmp_path / 'old-python.exe'
    new_target = tmp_path / 'new-python.exe'
    old_target.write_text('', encoding='utf-8')
    new_target.write_text('', encoding='utf-8')
    called = {'provision': 0}

    monkeypatch.setattr(compat, 'missing_source_imports', lambda: ['customtkinter'])
    monkeypatch.setattr(compat, 'enforce_minimum_python', lambda: None)
    monkeypatch.setattr(compat, 'validated_runtime_python', lambda: old_target)
    monkeypatch.setattr(compat, '_runtime_matches_current_minor', lambda _target: False)
    monkeypatch.setattr(compat, 'provision_runtime_for_current_python', lambda: called.__setitem__('provision', 1) or new_target)
    monkeypatch.setattr(compat.Path, 'resolve', lambda self: self)

    def fake_execve(exe, argv, env):
        assert Path(exe) == new_target
        raise RuntimeError('exec-called')

    monkeypatch.setattr(compat.os, 'execve', fake_execve)
    try:
        compat.bootstrap_validated_runtime(__file__)
    except RuntimeError as exc:
        assert str(exc) == 'exec-called'
    assert called['provision'] == 1
