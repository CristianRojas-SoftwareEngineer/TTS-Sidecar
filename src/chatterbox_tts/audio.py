"""
Reproducción de audio nativa para Windows, Linux y macOS.
Usa APIs nativas de cada SO para un rendimiento óptimo.
"""

import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import platform
import sys
import wave
import io
from typing import Optional

import numpy as np


class AudioPlayer:
    """
    Reproducción de audio multiplataforma usando APIs nativas.

    Prioridad por plataforma:
    1. Windows: pycaw (COM) o winsound (fallback)
    2. Linux: pyalsaaudio o sounddevice
    3. macOS: afplay (nativo)
    4. Fallback: simpleaudio
    """

    def __init__(self):
        self.system = platform.system()
        self._player = self._init_player()

    def _init_player(self):
        """Inicializa el player de audio apropiado para la plataforma."""
        if self.system == "Windows":
            return self._init_windows()
        elif self.system == "Darwin":
            return self._init_macos()
        elif self.system == "Linux":
            return self._init_linux()
        else:
            raise RuntimeError(f"Plataforma no soportada: {self.system}")

    def _init_windows(self):
        """Inicializa el player de audio para Windows."""
        # winsound es built-in: no requiere dependencias externas
        return WindowsAudioPlayer()

    def _init_macos(self):
        """Inicializa el player de audio para macOS usando afplay (built-in)."""
        try:
            import subprocess  # noqa: F401 — verificación de disponibilidad
            return MacOSAudioPlayer()
        except Exception as e:
            raise RuntimeError(f"Error al inicializar audio en macOS: {e}")

    def _init_linux(self):
        """Inicializa el player de audio para Linux."""
        try:
            import sounddevice as sd
            return SoundDevicePlayer(sd)
        except ImportError:
            try:
                import simpleaudio as sa
                return SimpleAudioPlayer(sa)
            except ImportError:
                raise ImportError(
                    "No hay librería de reproducción de audio disponible para Linux. "
                    "Instala una de: sounddevice, simpleaudio"
                )

    def play(self, audio_bytes: bytes) -> None:
        """Reproduce audio desde bytes WAV."""
        self._player.play(audio_bytes)

    def play_file(self, file_path: str) -> None:
        """Reproduce audio desde un archivo WAV."""
        with open(file_path, 'rb') as f:
            audio_bytes = f.read()
        self.play(audio_bytes)


class WindowsAudioPlayer:
    """Reproducción de audio en Windows usando winsound (built-in)."""

    def __init__(self, audio_client=None):
        # audio_client se conserva por compatibilidad con firmas anteriores pero no se usa
        pass

    def play(self, audio_bytes: bytes) -> None:
        """Reproduce bytes WAV en Windows usando winsound built-in."""
        import winsound
        import tempfile
        import os

        # winsound.PlaySound requiere una ruta de archivo, no bytes en memoria
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            winsound.PlaySound(temp_path, winsound.SND_FILENAME)
        finally:
            os.unlink(temp_path)


class MacOSAudioPlayer:
    """Reproducción de audio en macOS usando afplay (built-in)."""

    def __init__(self):
        import subprocess
        self.subprocess = subprocess

    def play(self, audio_bytes: bytes) -> None:
        """Reproduce audio usando afplay."""
        import tempfile
        import os

        # afplay requiere una ruta de archivo
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            self.subprocess.run(['afplay', temp_path], check=True)
        finally:
            os.unlink(temp_path)


class SoundDevicePlayer:
    """Reproducción de audio multiplataforma usando sounddevice (PortAudio)."""

    def __init__(self, sd):
        self.sd = sd

    def play(self, audio_bytes: bytes) -> None:
        """Reproduce bytes WAV usando sounddevice."""
        wav_io = io.BytesIO(audio_bytes)
        with wave.open(wav_io, 'rb') as wf:
            n_channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            audio_data = wf.readframes(wf.getnframes())

        # Convierte a float32 normalizado en [-1, 1]
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        audio_np = audio_np.astype(np.float32) / 32768.0

        self.sd.play(audio_np, samplerate=sample_rate, blocking=True)


class SimpleAudioPlayer:
    """Player de audio de fallback usando simpleaudio."""

    def __init__(self, sa_module):
        self.sa = sa_module

    def play(self, audio_bytes: bytes) -> None:
        """Reproduce bytes WAV usando simpleaudio."""
        wav_io = io.BytesIO(audio_bytes)
        with wave.open(wav_io, 'rb') as wf:
            sample_rate = wf.getframerate()
            audio_data = wf.readframes(wf.getnframes())

        # Convierte a float32 y luego a int16 para simpleaudio
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        audio_np = audio_np.astype(np.float32) / 32768.0

        play_obj = self.sa.play_buffer(
            (audio_np * 32767).astype(np.int16),
            num_channels=1,
            bytes_per_sample=2,
            sample_rate=sample_rate
        )
        play_obj.wait()


def get_audio_devices() -> list[dict]:
    """
    Lista los dispositivos de salida de audio disponibles.

    Returns:
        Lista de dicts con claves 'id', 'name', 'latency'
    """
    system = platform.system()

    if system == "Windows":
        try:
            from pycaw.pycaw import AudioUtilities
            devices = AudioUtilities.GetAllDevices()
            return [
                {"id": i, "name": d.FriendlyName, "latency": getattr(d, 'Latency', 0.0)}
                for i, d in enumerate(devices)
            ]
        except ImportError:
            return [{"id": 0, "name": "Default", "latency": 0.1}]

    elif system == "Darwin":
        # TODO: implementar enumeración real vía CoreAudio/AVFoundation;
        # por ahora devuelve lista fija (afplay usa el dispositivo de salida por defecto)
        return [{"id": 0, "name": "Built-in Output", "latency": 0.1}]

    elif system == "Linux":
        try:
            import sounddevice as sd
            return [
                {"id": i, "name": info['name'], "latency": info['default_latency']}
                for i, info in enumerate(sd.query_devices())
                if info['max_output_channels'] > 0
            ]
        except ImportError:
            return [{"id": 0, "name": "Default", "latency": 0.1}]

    return [{"id": 0, "name": "Default", "latency": 0.1}]
