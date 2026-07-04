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
    ProgressEvent,
    ResultEvent,
    ErrorEvent,
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

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="")

    def test_excessive_text_rejected(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="a" * (MAX_TEXT_LENGTH + 1))

    def test_text_at_limit_accepted(self):
        assert len(SynthesizeRequest(text="a" * MAX_TEXT_LENGTH).text) == MAX_TEXT_LENGTH

    def test_protocol_without_model_or_compute_backend(self):
        campos = SynthesizeRequest.model_fields
        assert "model" not in campos
        assert "compute_backend" not in campos

    def test_excessive_audio_path_rejected(self):
        """SUGGESTION-01: voice_audio/speech_audio tienen tope de longitud."""
        ruta_excesiva = "a" * (MAX_AUDIO_PATH_LENGTH + 1)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", voice_audio=ruta_excesiva)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", speech_audio=ruta_excesiva)

    def test_audio_path_at_limit_accepted(self):
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


class TestStreamEvents:
    """Esquema NDJSON de /synthesize: progress / result / error."""

    def test_progress_event_defaults(self):
        ev = ProgressEvent()
        assert ev.event == "progress"
        assert ev.stage is None and ev.tokens is None and ev.elapsed is None

    def test_progress_event_with_tokens(self):
        ev = ProgressEvent(stage="t3", tokens=210)
        assert ev.event == "progress"
        assert ev.stage == "t3"
        assert ev.tokens == 210

    def test_progress_event_fixed_literal(self):
        """El discriminador `event` es un literal: no admite otros valores."""
        with pytest.raises(ValueError):
            ProgressEvent(event="result")

    def test_result_event(self):
        ev = ResultEvent(audio_b64="QUJD", t3_time=9.7, s3gen_time=7.0)
        assert ev.event == "result"
        assert ev.audio_b64 == "QUJD"
        assert ev.t3_time == 9.7
        assert ev.s3gen_time == 7.0

    def test_result_event_default_times(self):
        ev = ResultEvent(audio_b64="QUJD")
        assert ev.t3_time == 0.0 and ev.s3gen_time == 0.0

    def test_result_event_requires_audio(self):
        with pytest.raises(ValueError):
            ResultEvent()

    def test_error_event(self):
        ev = ErrorEvent(detail="Error interno de síntesis")
        assert ev.event == "error"
        assert ev.detail == "Error interno de síntesis"

    def test_error_event_requires_detail(self):
        with pytest.raises(ValueError):
            ErrorEvent()

    def test_json_serialization_includes_event(self):
        """Cada línea NDJSON lleva el discriminador `event` para el parseo del cliente."""
        import json

        assert json.loads(ProgressEvent(stage="t3", tokens=10).model_dump_json())["event"] == "progress"
        assert json.loads(ResultEvent(audio_b64="QUJD").model_dump_json())["event"] == "result"
        assert json.loads(ErrorEvent(detail="x").model_dump_json())["event"] == "error"
