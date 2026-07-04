"""
Definiciones del protocolo IPC del daemon de tts-sidecar.
"""

from pydantic import BaseModel, Field
from typing import Optional

# Tope de texto por petición: acota el trabajo del T3 y evita el DoS local
# trivial de un payload ilimitado.
MAX_TEXT_LENGTH = 5000

# Tope de longitud para las rutas de audio: por encima del límite práctico de
# ruta en los tres SO soportados (Windows MAX_PATH extendido, Linux/macOS
# PATH_MAX), evita payloads desproporcionados antes de que lleguen a la
# validación de directorio permitido de /synthesize (SUGGESTION-01).
MAX_AUDIO_PATH_LENGTH = 4096


class SynthesizeRequest(BaseModel):
    """Request de síntesis de habla.

    El daemon sirve un único modelo y compute backend fijados al arrancar; la
    petición no lleva `model` ni `compute_backend` (el servidor los ignoraría).
    """
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    voice_audio: Optional[str] = Field(default=None, max_length=MAX_AUDIO_PATH_LENGTH)
    speech_audio: Optional[str] = Field(default=None, max_length=MAX_AUDIO_PATH_LENGTH)


class HealthResponse(BaseModel):
    """Respuesta del health check."""
    status: str
    """Estado del daemon: 'healthy', 'initializing' o 'error'."""
    model_loaded: bool
    """True cuando el modelo está completamente cargado en memoria."""
    uptime_seconds: float
    """Segundos transcurridos desde el inicio del daemon."""


class VoicesResponse(BaseModel):
    """Lista de voces registradas."""
    voices: list[str]
