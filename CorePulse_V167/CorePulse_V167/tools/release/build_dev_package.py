"""Construye el ZIP limpio usado por la prerelease automática de Desarrollo."""
from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path, PurePosixPath
import re
import zipfile

EXCLUDED_DIRS = {
    '.git', '.github', '.venv', 'venv', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'data', 'logs', 'dist',
}
EXCLUDED_NAMES = {
    '.env', 'dependency_install.log',
}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo', '.log'}


def read_version(project: Path) -> str:
    version_file = project / 'core' / 'version.py'
    if not version_file.is_file():
        raise RuntimeError('Falta core/version.py.')
    tree = ast.parse(version_file.read_text(encoding='utf-8'), filename=str(version_file))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'VERSION':
                    value = ast.literal_eval(node.value)
                    version = str(value).strip()
                    if re.fullmatch(r'\d+', version):
                        return version
    raise RuntimeError('core/version.py no declara VERSION con un entero válido.')


def should_include(project: Path, path: Path) -> bool:
    rel = path.relative_to(project)
    lowered = [part.casefold() for part in rel.parts]
    if any(part in {item.casefold() for item in EXCLUDED_DIRS} for part in lowered[:-1]):
        return False
    if path.name.casefold() in {item.casefold() for item in EXCLUDED_NAMES}:
        return False
    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return False
    if path.is_symlink():
        raise RuntimeError(f'No se permiten enlaces simbólicos en el paquete: {rel}')
    return path.is_file()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def build(project: Path, output: Path) -> dict:
    project = project.resolve()
    if not (project / 'main.py').is_file():
        raise RuntimeError('La carpeta seleccionada no parece una raíz de CorePulse.')
    version = read_version(project)
    expected_name = f'CorePulse_V{version}'
    if project.name.casefold() != expected_name.casefold():
        raise RuntimeError(f'La carpeta debe llamarse {expected_name}; se recibió {project.name}.')

    output.mkdir(parents=True, exist_ok=True)
    zip_path = output / f'{expected_name}.zip'
    temp = zip_path.with_suffix('.zip.part')
    temp.unlink(missing_ok=True)

    files = [path for path in project.rglob('*') if should_include(project, path)]
    if not files:
        raise RuntimeError('No hay archivos para empaquetar.')

    with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files, key=lambda p: p.relative_to(project).as_posix().casefold()):
            rel = PurePosixPath(expected_name) / PurePosixPath(path.relative_to(project).as_posix())
            archive.write(path, rel.as_posix())
    temp.replace(zip_path)

    digest = sha256(zip_path)
    checksum = output / f'{zip_path.name}.sha256'
    checksum.write_text(f'{digest}  {zip_path.name}\n', encoding='utf-8', newline='\n')
    return {
        'version': version,
        'zip': str(zip_path),
        'sha256': digest,
        'sha256_file': str(checksum),
        'files': len(files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = build(Path(args.project), Path(args.output))
    print(f"CorePulse V{result['version']}: {result['files']} archivos empaquetados")
    print(result['zip'])
    print(result['sha256_file'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
