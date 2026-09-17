"""Automatización de prereleases de desarrollo para CorePulse.

El publicador de perfiles instala un workflow administrado en la raíz del clon.
Ese workflow se ejecuta en cada push a ``*/corepulse-dev`` y crea/actualiza una
prerelease por versión, sin guardar credenciales dentro de CorePulse.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

WORKFLOW_RELATIVE_PATH = Path('.github/workflows/corepulse-development-release.yml')
WORKFLOW_MARKER = '# Managed by CorePulse · development release automation'

WORKFLOW_TEMPLATE = r'''# Managed by CorePulse · development release automation
name: CorePulse Development Release

on:
  push:
    branches:
      - '**/corepulse-dev'
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: corepulse-development-release-${{ github.ref }}
  cancel-in-progress: true

jobs:
  package-development-release:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Locate current CorePulse source
        id: corepulse
        shell: bash
        run: |
          python - <<'PY'
          import os
          import re
          from pathlib import Path

          candidates = []
          for folder in Path('.').iterdir():
              if not folder.is_dir():
                  continue
              match = re.fullmatch(r'(?i)CorePulse_V(\d+)', folder.name)
              version_file = folder / 'core' / 'version.py'
              if not match or not version_file.is_file():
                  continue
              text = version_file.read_text(encoding='utf-8', errors='replace')
              version_match = re.search(r'^VERSION\s*=\s*[\"\']([^\"\']+)[\"\']', text, re.M)
              if not version_match:
                  continue
              version = version_match.group(1).strip()
              if version != match.group(1):
                  continue
              candidates.append((int(match.group(1)), folder, version))

          if not candidates:
              raise SystemExit('No se encontró una carpeta CorePulse_VN válida en la raíz del repositorio.')

          _, folder, version = max(candidates, key=lambda item: item[0])
          output = Path(os.environ['GITHUB_OUTPUT'])
          with output.open('a', encoding='utf-8') as handle:
              handle.write(f'root={folder.as_posix()}\n')
              handle.write(f'version={version}\n')
          print(f'CorePulse detectado: {folder} · V{version}')
          PY

      - name: Build clean ZIP and SHA-256
        shell: bash
        run: |
          python "${{ steps.corepulse.outputs.root }}/tools/release/build_dev_package.py" \
            --project "${{ steps.corepulse.outputs.root }}" \
            --output "${{ runner.temp }}/corepulse-release"

      - name: Create or update development prerelease
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          VERSION: ${{ steps.corepulse.outputs.version }}
          RELEASE_DIR: ${{ runner.temp }}/corepulse-release
        run: |
          set -euo pipefail
          gh --version
          TAG="V${VERSION}-dev"
          ZIP="${RELEASE_DIR}/CorePulse_V${VERSION}.zip"
          SHA="${ZIP}.sha256"
          NOTES="${RELEASE_DIR}/release-notes.md"

          cat > "$NOTES" <<EOF
          Prerelease automática de desarrollo de CorePulse V${VERSION}.

          - Rama: ${GITHUB_REF_NAME}
          - Commit: ${GITHUB_SHA}
          - Generada automáticamente por GitHub Actions.
          - Incluye ZIP fuente verificado y SHA-256.

          Esta release alimenta el canal Desarrollo de CorePulse. No es una release estable.
          EOF

          if gh release view "$TAG" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
            gh release upload "$TAG" "$ZIP" "$SHA" --clobber --repo "$GITHUB_REPOSITORY"
            gh release edit "$TAG" \
              --repo "$GITHUB_REPOSITORY" \
              --title "CorePulse V${VERSION} Development" \
              --prerelease \
              --notes-file "$NOTES"
          else
            gh release create "$TAG" "$ZIP" "$SHA" \
              --repo "$GITHUB_REPOSITORY" \
              --target "$GITHUB_SHA" \
              --title "CorePulse V${VERSION} Development" \
              --prerelease \
              --notes-file "$NOTES"
          fi

          echo "Development release lista: ${TAG}"
'''


@dataclass(frozen=True)
class ManagedWorkflowState:
    enabled: bool
    needed: bool
    exists: bool
    managed: bool
    path: Path
    blocker: str | None = None


def is_development_branch(branch: str | None) -> bool:
    value = str(branch or '').strip().replace('\\', '/').casefold()
    return value == 'corepulse-dev' or value.endswith('/corepulse-dev')


def inspect_managed_workflow(repo_root: str | Path, branch: str | None) -> ManagedWorkflowState:
    repo = Path(repo_root)
    path = repo / WORKFLOW_RELATIVE_PATH
    enabled = is_development_branch(branch)
    if not enabled:
        return ManagedWorkflowState(False, False, path.exists(), False, path)
    if not path.exists():
        return ManagedWorkflowState(True, True, False, True, path)
    try:
        current = path.read_text(encoding='utf-8')
    except Exception:
        return ManagedWorkflowState(True, False, True, False, path,
            'No se pudo leer el workflow de GitHub Actions existente.')
    managed = WORKFLOW_MARKER in current
    if not managed and current != WORKFLOW_TEMPLATE:
        return ManagedWorkflowState(
            True, False, True, False, path,
            'Ya existe .github/workflows/corepulse-development-release.yml y no está administrado por CorePulse. '
            'Renómbralo o elimínalo antes de activar la automatización de releases.'
        )
    return ManagedWorkflowState(True, current != WORKFLOW_TEMPLATE, True, True, path)


def materialize_managed_workflow(repo_root: str | Path, branch: str | None) -> dict:
    """Escribe el workflow si la rama usa automatización.

    Devuelve suficiente información para restaurar el archivo si la publicación
    falla antes de crear el commit.
    """
    state = inspect_managed_workflow(repo_root, branch)
    if state.blocker:
        raise RuntimeError(state.blocker)
    if not state.enabled or not state.needed:
        return {'changed': False, 'path': str(state.path), 'existed': state.exists, 'previous': None}
    previous = state.path.read_bytes() if state.path.exists() else None
    state.path.parent.mkdir(parents=True, exist_ok=True)
    state.path.write_text(WORKFLOW_TEMPLATE, encoding='utf-8', newline='\n')
    return {
        'changed': True,
        'path': str(state.path),
        'existed': previous is not None,
        'previous': previous,
    }


def restore_managed_workflow(change: dict | None) -> None:
    if not change or not change.get('changed'):
        return
    path = Path(str(change.get('path') or ''))
    previous = change.get('previous')
    try:
        if previous is None:
            path.unlink(missing_ok=True)
            parent = path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
            github = parent.parent
            if github.exists() and not any(github.iterdir()):
                github.rmdir()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(previous)
    except Exception:
        pass


__all__ = [
    'WORKFLOW_RELATIVE_PATH', 'WORKFLOW_MARKER', 'WORKFLOW_TEMPLATE',
    'ManagedWorkflowState', 'is_development_branch', 'inspect_managed_workflow',
    'materialize_managed_workflow', 'restore_managed_workflow',
]
