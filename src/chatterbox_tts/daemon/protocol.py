"""
Definiciones del protocolo IPC del daemon de tts-sidecar.
"""

from pydantic import BaseModel
from typing import Optional


class SynthesizeRequest(BaseModel):
    """Request de síntesis de habla."""
    text: str
    voice_audio: Optional[str] = None
    speech_audio: Optional[str] = None
    model: str = "es-mx-latam"
    device: str = "cpu"


class HealthResponse(BaseModel):
    """Respuesta del health check."""
    status: str
    """Estado del daemon: 'healthy', 'initializing' o 'error'."""
    model_loaded: bool
    """True cuando el modelo está completamente cargado en memoria."""
    uptime_seconds: float
    """Segundos transcurridos desde el inicio del daemon."""


class ErrorResponse(BaseModel):
    """Respuesta de error."""
    error: str
    code: str


class VoicesResponse(BaseModel):
    """Lista de voces registradas."""
    voices: list[str]
