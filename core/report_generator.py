"""Punto público de generación del informe PDF de CorePulse.

Esta capa coordina diagnóstico certificado, interpretación IA opcional y renderizado.
La ausencia de IA nunca invalida el informe técnico ni crea telemetría sustituta.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from core.ai_report_engine import analyze_report_with_ai
from core.pdf_context import build_strict_pdf_context
from core.report_builder import build_pdf_report
from core.version import VERSION_LABEL

VERSION = VERSION_LABEL
PDF_DOMAIN_POLICY = 'HARDWARE_RELEVANCE_AND_ACTION_PLAN_ARE_INDEPENDENT'
PDF_UX_POLICY = 'COMPACT_EXECUTIVE_CONDITIONAL_HISTORY_TECHNICAL_ANNEX'


def _save_ai_snapshot(ai: Dict[str, Any]) -> None:
    """Guarda la última interpretación sin exponer secretos ni alterar el diagnóstico."""
    try:
        path = Path('data') / 'current_ai_report.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(ai, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        os.replace(tmp, path)
    except Exception:
        pass


def generate_pdf_report(telemetry, disks, score, output_path, diagnostic_result=None, *args, **kwargs):
    """Genera y devuelve la ruta del PDF final a partir del diagnóstico actual."""
    if not isinstance(diagnostic_result, dict):
        raise RuntimeError(f'{VERSION_LABEL}: no hay un resultado de diagnóstico actual para exportar.')

    clean_telemetry = telemetry if isinstance(telemetry, dict) else {}
    clean_disks = disks if isinstance(disks, list) else []
    ctx = build_strict_pdf_context(diagnostic_result)
    ai = analyze_report_with_ai(diagnostic_result, clean_telemetry, clean_disks)
    _save_ai_snapshot(ai)
    return build_pdf_report(
        telemetry=clean_telemetry,
        disks=clean_disks,
        score=score,
        output_path=output_path,
        diagnostic_result=diagnostic_result,
        ai=ai,
        ctx=ctx,
    )


__all__ = ['generate_pdf_report', 'VERSION', 'PDF_DOMAIN_POLICY', 'PDF_UX_POLICY']
