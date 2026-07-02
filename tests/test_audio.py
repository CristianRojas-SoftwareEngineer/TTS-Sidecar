"""Tests de la capa de reproducción y enumeración de audio (SUGGESTION-03)."""

import io
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from chatterbox_tts.audio import (
    SoundDevicePlayer,
    get_audio_devices,
    get_audio_devices_with_status,
)


def _wav_bytes(n_channels: int, n_frames: int = 480, sample_rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = np.zeros(n_frames * n_channels, dtype=np.int16)
        wf.writeframes(frames.tobytes())
    return buffer.getvalue()


class TestSoundDevicePlayer:
    def test_mono_se_reproduce_plano(self):
        sd = MagicMock()
        SoundDevicePlayer(sd).play(_wav_bytes(n_channels=1))
        (audio_np,), kwargs = sd.play.call_args
        assert audio_np.ndim == 1
        assert kwargs["samplerate"] == 24000

    def test_estereo_se_reproduce_con_dos_canales(self):
        """Sin el reshape, un WAV estéreo sonaría como mono al doble de velocidad."""
        sd = MagicMock()
        SoundDevicePlayer(sd).play(_wav_bytes(n_channels=2, n_frames=480))
        (audio_np,), _ = sd.play.call_args
        assert audio_np.shape == (480, 2)

    def test_rechaza_ancho_de_muestra_distinto_de_16_bits(self):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(3)  # 24 bits, no soportado
            wf.setframerate(24000)
            wf.writeframes(b"\x00" * 3 * 480)
        with pytest.raises(ValueError, match="ancho de muestra"):
            SoundDevicePlayer(MagicMock()).play(buffer.getvalue())


class TestGetAudioDevicesWindows:
    @patch("platform.system", return_value="Windows")
    def test_fallo_de_pycaw_degrada_al_fallback(self, _system):
        """Un fallo COM (RDP, host sin audio) no debe crashear 'devices'."""
        pycaw_mock = MagicMock()
        pycaw_mock.pycaw.AudioUtilities.GetDeviceEnumerator.side_effect = OSError("COM error")
        with patch.dict(sys.modules, {"pycaw": pycaw_mock, "pycaw.pycaw": pycaw_mock.pycaw}):
            devices = get_audio_devices()
        assert devices == [{"id": 0, "name": "Default", "latency": 0.1}]


class TestGetAudioDevicesLinuxMacOS:
    @patch("platform.system", return_value="Linux")
    def test_fallo_no_import_error_degrada_al_fallback(self, _system):
        """Un PortAudioError en tiempo de enumeración no debe crashear 'devices'."""
        sd_mock = MagicMock()
        sd_mock.query_devices.side_effect = OSError("PortAudio error")
        with patch.dict(sys.modules, {"sounddevice": sd_mock}):
            devices, degraded = get_audio_devices_with_status()
        assert degraded is True
        assert devices == [{"id": 0, "name": "Default", "latency": 0.1}]
