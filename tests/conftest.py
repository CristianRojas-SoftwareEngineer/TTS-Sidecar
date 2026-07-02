"""Fixtures de pytest para los tests de tts-sidecar."""

import pytest
import sys
from pathlib import Path

# Asegura que src/ esté en el path para imports relativos al proyecto
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_engine():
    """Mock de ChatterboxEngine para los tests del CLI."""
    class MockEngine:
        def __init__(self):
            self.list_voices_calls = []

        def speak(self, text, voice_audio=None, speech_audio=None, output_path=None, verbose=False):
            # Devuelve un header WAV mínimo (44 bytes)
            return b"RIFF" + b"\x00" * 40

        def add_voice(self, name, reference_audio, speech_audio):
            return f"/path/to/{name}/reference.wav", f"/path/to/{name}/speech.wav"

        def remove_voice(self, name):
            return True

        def list_voices(self):
            return ["crist", "testcli"]

    return MockEngine()


@pytest.fixture
def mock_daemon_client():
    """Mock de DaemonIPCClient para los tests del CLI."""
    class MockDaemonClient:
        def __init__(self):
            self.calls = []

        def synthesize(self, text, voice_audio=None, speech_audio=None,
                        model=None, compute_backend=None):
            self.calls.append({"text": text})
            # Devuelve un WAV mínimo
            return b"RIFF" + b"\x00" * 40

        def is_running(self):
            return True

    return MockDaemonClient()
