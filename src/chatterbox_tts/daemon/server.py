"""
Servidor FastAPI del daemon de tts-sidecar.
Expone endpoints HTTP para síntesis TTS con el modelo persistente en memoria.
"""

import logging
import os
import threading

from fastapi import FastAPI, HTTPException, Response

from .. import voices
from .protocol import (
    SynthesizeRequest,
    HealthResponse,
    VoicesResponse,
)


# Estado global (asignado por run.py antes de arrancar uvicorn)
_engine = None
_start_time = None
_server = None


def set_engine(engine):
    """Asigna la instancia global del engine."""
    global _engine
    _engine = engine


def set_server(server):
    """Registra la instancia de uvicorn.Server para permitir el apagado graceful."""
    global _server
    _server = server


def set_start_time(timestamp: float):
    """Registra el timestamp de inicio del servidor."""
    global _start_time
    _start_time = timestamp


# Aplicación FastAPI
app = FastAPI(
    title="tts-sidecar-daemon",
    description="Daemon TTS persistente con modelo cacheado en memoria",
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Endpoint de health check."""
    import time
    return HealthResponse(
        status="healthy" if _engine else "initializing",
        model_loaded=_engine is not None,
        uptime_seconds=time.time() - _start_time if _start_time else 0,
    )


# Serializa la síntesis completa (preparación de conds + generate): engine.speak
# muta estado global del modelo (tts.conds) y dos peticiones concurrentes
# cruzarían voces.
_synthesis_lock = threading.Lock()


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest) -> Response:
    """
    Sintetiza texto a audio usando el modelo cacheado en memoria.

    Endpoint síncrono (def): FastAPI lo despacha a su threadpool, de modo que
    una síntesis larga no bloquea el event loop y /health sigue respondiendo.
    Devuelve el audio como binario WAV.
    """
    if not _engine:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

    # Valida las rutas de audio antes de que lleguen a librosa.load: deben
    # existir, ser .wav y quedar contenidas en un directorio permitido
    # (WARNING-02: sin esto, cualquier proceso local podía hacer que el daemon
    # leyera un .wav arbitrario del sistema de archivos). Los mensajes de error
    # no exponen rutas del sistema.
    allowed_dirs = [os.path.realpath(d) for d in voices.allowed_audio_dirs()]
    # Cada ruta se resuelve a su forma canónica UNA sola vez aquí y esa misma
    # ruta (no la cruda de la petición) es la que se pasa a _engine.speak: sin
    # esto, quedaba una ventana entre validar y usar en la que el archivo podía
    # cambiar (symlink swap) sin volver a pasar por la validación.
    real_paths: dict[str, str] = {}
    for field, path in (("voice_audio", req.voice_audio), ("speech_audio", req.speech_audio)):
        if path is None:
            continue
        if not path.lower().endswith(".wav") or not os.path.isfile(path):
            raise HTTPException(
                status_code=400,
                detail=f"{field}: se requiere una ruta a un archivo .wav existente",
            )
        real_path = os.path.realpath(path)
        if not any(
            real_path == d or real_path.startswith(d + os.sep) for d in allowed_dirs
        ):
            raise HTTPException(
                status_code=400,
                detail=f"{field}: la ruta no está en un directorio permitido",
            )
        try:
            with open(real_path, "rb") as f:
                header = f.read(12)
        except OSError:
            header = b""
        if len(header) < 12 or header[0:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise HTTPException(
                status_code=400,
                detail=f"{field}: el archivo no es un WAV válido",
            )
        real_paths[field] = real_path

    try:
        with _synthesis_lock:
            audio_bytes = _engine.speak(
                text=req.text,
                voice_audio=real_paths.get("voice_audio"),
                speech_audio=real_paths.get("speech_audio"),
                verbose=True,
            )

        timing = getattr(_engine, '_synthesis_timing', {})
        headers = {
            "Content-Disposition": "attachment; filename=synth.wav",
            "X-T3-Time": f"{timing.get('t3', 0):.1f}",
            "X-S3Gen-Time": f"{timing.get('s3gen', 0):.1f}",
        }

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers=headers,
        )

    except FileNotFoundError as e:
        # El detalle real (con rutas) queda solo en el log del servidor.
        logging.getLogger(__name__).warning("synthesize: recurso no encontrado: %s", e)
        raise HTTPException(status_code=404, detail="Recurso de voz no encontrado")
    except Exception as e:
        logging.getLogger(__name__).error("synthesize: error interno: %s", e)
        raise HTTPException(status_code=500, detail="Error interno de síntesis")


@app.get("/voices", response_model=VoicesResponse)
async def list_voices():
    """Lista las voces registradas."""
    if not _engine:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

    return VoicesResponse(voices=_engine.list_voices())


@app.post("/shutdown")
async def shutdown():
    """Endpoint de cierre graceful del daemon.

    Señaliza `should_exit` sobre la instancia de uvicorn.Server para que el
    servidor termine su ciclo de vida de forma ordenada. Se responde antes de
    que uvicorn cierre: el flag se procesa en la siguiente iteración del loop.

    Riesgo aceptado (SUGGESTION-02): no lleva token ni confirmación explícita.
    El daemon bindea exclusivamente a 127.0.0.1 (ver run.py), por lo que solo
    un proceso con acceso local a la máquina puede invocarlo; se acepta ese
    riesgo residual en vez de añadir un secreto que el propio cliente IPC
    tendría que gestionar y persistir.
    """
    if _server is not None:
        _server.should_exit = True
        return {"status": "shutting_down"}
    # Sin instancia registrada (no debería ocurrir): el kill por PID es la red de seguridad.
    raise HTTPException(status_code=503, detail="Servidor no disponible para apagado graceful")
