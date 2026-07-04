"""Tests para los modelos Pydantic de daemon/protocol.py."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from tts_sidecar.daemon.protocol import (
    MAX_TEXT_LENGTH,
    MAX_AUDIO_PATH_LENGTH,
    SynthesizeRequest,
    HealthResponse,
    VoicesResponse,
)


class TestSynthesizeRequest:
    def test_valid_request(self):
        req = SynthesizeRequest(text="hola mundo")
        assert req.text == "hola mundo"

    def test_full_request(self):
        req = SynthesizeRequest(
            text="test",
            voice_audio="/path/to/voice.wav",
            speech_audio="/path/to/speech.wav",
        )
        assert req.text == "test"
        assert req.voice_audio == "/path/to/voice.wav"
        assert req.speech_audio == "/path/to/speech.wav"

    def test_missing_text(self):
        with pytest.raises(ValueError):
            SynthesizeRequest()

    def test_texto_vacio_rechazado(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="")

    def test_texto_excesivo_rechazado(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="a" * (MAX_TEXT_LENGTH + 1))

    def test_texto_en_el_limite_aceptado(self):
        assert len(SynthesizeRequest(text="a" * MAX_TEXT_LENGTH).text) == MAX_TEXT_LENGTH

    def test_protocolo_sin_model_ni_compute_backend(self):
        campos = SynthesizeRequest.model_fields
        assert "model" not in campos
        assert "compute_backend" not in campos

    def test_ruta_audio_excesiva_rechazada(self):
        """SUGGESTION-01: voice_audio/speech_audio tienen tope de longitud."""
        ruta_excesiva = "a" * (MAX_AUDIO_PATH_LENGTH + 1)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", voice_audio=ruta_excesiva)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", speech_audio=ruta_excesiva)

    def test_ruta_audio_en_el_limite_aceptada(self):
        ruta = "a" * MAX_AUDIO_PATH_LENGTH
        req = SynthesizeRequest(text="hola", voice_audio=ruta)
        assert len(req.voice_audio) == MAX_AUDIO_PATH_LENGTH


class TestHealthResponse:
    def test_healthy_response(self):
        resp = HealthResponse(status="healthy", model_loaded=True, uptime_seconds=10.5)
        assert resp.status == "healthy"
        assert resp.model_loaded is True
        assert resp.uptime_seconds == 10.5

    def test_initializing_response(self):
        resp = HealthResponse(status="initializing", model_loaded=False, uptime_seconds=0.0)
        assert resp.status == "initializing"
        assert resp.model_loaded is False


class TestVoicesResponse:
    def test_voices_response(self):
        resp = VoicesResponse(voices=["crist", "testcli"])
        assert resp.voices == ["crist", "testcli"]

    def test_empty_voices(self):
        resp = VoicesResponse(voices=[])
        assert resp.voices == []
