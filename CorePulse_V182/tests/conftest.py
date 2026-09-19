from __future__ import annotations

import re

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-windows-real",
        action="store_true",
        default=False,
        help="ejecuta pruebas marcadas windows_real (requiere Windows/hardware real)",
    )


def pytest_collection_modifyitems(config, items):
    run_windows_real = bool(config.getoption("--run-windows-real"))
    for item in items:
        name = item.path.name
        match = re.match(r"test_v(\d+)_", name)
        if match and int(match.group(1)) < 162:
            item.add_marker(pytest.mark.legacy_snapshot)
        if "windows_real" in item.keywords and not run_windows_real:
            item.add_marker(pytest.mark.skip(reason="requiere --run-windows-real y un PC Windows real"))
