"""Gestión segura de perfiles y Game Boost de CorePulse."""
from .profile_manager import PerformanceProfileManager
from .game_detector import GameDetector
from .power_manager import PowerManager
from .game_boost import GameBoostOptimizer

__all__ = ['PerformanceProfileManager', 'GameDetector', 'PowerManager', 'GameBoostOptimizer']
