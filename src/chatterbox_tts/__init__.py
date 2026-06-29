"""
Chatterbox TTS - Text-to-Speech with voice cloning
100% local, MIT licensed, Spanish Latin American support
"""

__version__ = "0.1.0"
__author__ = "TTS Sidecar Team"
__license__ = "MIT"

# Lazy imports to allow --help without dependencies installed
def __getattr__(name):
    if name == "ChatterboxEngine":
        from .engine import ChatterboxEngine
        return ChatterboxEngine
    if name == "AudioPlayer":
        from .audio import AudioPlayer
        return AudioPlayer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = []
