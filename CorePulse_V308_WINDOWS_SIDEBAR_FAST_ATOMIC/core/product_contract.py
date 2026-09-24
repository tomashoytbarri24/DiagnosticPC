"""Contratos permanentes de integridad y alcance del producto CorePulse."""
from __future__ import annotations

from core.version import VERSION, VERSION_LABEL, STAGE

PRODUCT_SCOPE = 'UNIVERSAL_WINDOWS_PC_NOTEBOOK'
BUILD_CHANNEL = 'PORTFOLIO_DEVELOPMENT'
REAL_DATA_POLICY = 'REAL_OR_NA'
FPS_POLICY = 'REAL_FPS_OR_NA_ONLY'
AI_POLICY = 'AI_INTERPRETS_CERTIFIED_EVIDENCE_ONLY'
HARDWARE_POLICY = 'RUNTIME_DETECTION_NO_MODEL_HARDCODING'
REPLACEMENT_POLICY = 'VERIFY_PLATFORM_COMPATIBILITY_BEFORE_PHYSICAL_UPGRADE'
RESPONSIVE_MODES = ('compact', 'standard', 'large')
WINDOW_PRESETS = {
    'Compacto': (1180, 680),
    'Recomendado': (1280, 720),
    'Amplio': (1560, 860),
}
FEATURES = (
    'responsive_dashboard',
    'advanced_cpu_details',
    'advanced_gpu_details',
    'continuous_real_telemetry',
    'adaptive_diagnostic',
    'hardware_relevance',
    'actionable_pdf_report',
    'cleaning_modules',
    'alerts_history_trends',
    'real_fps_overlay',
    'tray_realtime_agent',
    'persistent_verified_performance_profiles',
    'transactional_profile_failure_rollback',
    'automatic_multi_game_detection',
    'silent_windows_command_runner',
    'verified_model_specific_tutorials',
)

__all__ = [
    'VERSION', 'VERSION_LABEL', 'STAGE', 'PRODUCT_SCOPE', 'BUILD_CHANNEL',
    'REAL_DATA_POLICY', 'FPS_POLICY', 'AI_POLICY', 'HARDWARE_POLICY',
    'REPLACEMENT_POLICY', 'RESPONSIVE_MODES', 'WINDOW_PRESETS', 'FEATURES',
]
