"""
Native audio playback for Windows, Linux, and macOS.
Uses platform-specific APIs for optimal performance.
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
    Cross-platform audio playback using native APIs.

    Platform priority:
    1. Windows: pycaw (COM) or winsound (fallback)
    2. Linux: pyalsaaudio or sounddevice
    3. macOS: pyobjc-framework-AVFoundation
    4. Fallback: simpleaudio
    """

    def __init__(self):
        self.system = platform.system()
        self._player = self._init_player()

    def _init_player(self):
        """Initialize the appropriate audio player for the platform."""
        if self.system == "Windows":
            return self._init_windows()
        elif self.system == "Darwin":
            return self._init_macos()
        elif self.system == "Linux":
            return self._init_linux()
        else:
            raise RuntimeError(f"Unsupported platform: {self.system}")

    def _init_windows(self):
        """Initialize Windows audio player."""
        # Use built-in winsound - no external dependencies needed
        return WindowsAudioPlayer()

    def _init_macos(self):
        """Initialize macOS audio player."""
        try:
            import subprocess
            # Use afplay via subprocess (built-in macOS)
            return MacOSAudioPlayer()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize macOS audio: {e}")

    def _init_linux(self):
        """Initialize Linux audio player."""
        try:
            import sounddevice as sd
            return SoundDevicePlayer(sd)
        except ImportError:
            try:
                import simpleaudio as sa
                return SimpleAudioPlayer(sa)
            except ImportError:
                raise ImportError(
                    "No audio playback library available for Linux. "
                    "Install one of: sounddevice, simpleaudio"
                )

    def play(self, audio_bytes: bytes) -> None:
        """Play audio from WAV bytes."""
        self._player.play(audio_bytes)

    def play_file(self, file_path: str) -> None:
        """Play audio from a WAV file."""
        with open(file_path, 'rb') as f:
            audio_bytes = f.read()
        self.play(audio_bytes)


class WindowsAudioPlayer:
    """Windows audio playback using winsound (built-in)."""

    def __init__(self, audio_client=None):
        # audio_client parameter kept for compatibility but not used
        pass

    def play(self, audio_bytes: bytes) -> None:
        """Play WAV bytes on Windows using built-in winsound."""
        import winsound
        import tempfile
        import os

        # Write to temp file (winsound.PlaySound needs a file path)
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            winsound.PlaySound(temp_path, winsound.SND_FILENAME)
        finally:
            os.unlink(temp_path)


class MacOSAudioPlayer:
    """macOS audio playback using afplay (built-in)."""

    def __init__(self):
        import subprocess
        self.subprocess = subprocess

    def play(self, audio_bytes: bytes) -> None:
        """Play audio using afplay."""
        import tempfile
        import os

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(audio_bytes)
            temp_path = f.name

        try:
            self.subprocess.run(['afplay', temp_path], check=True)
        finally:
            os.unlink(temp_path)


class SoundDevicePlayer:
    """Cross-platform audio using sounddevice (portaudio)."""

    def __init__(self, sd):
        self.sd = sd

    def play(self, audio_bytes: bytes) -> None:
        """Play WAV bytes using sounddevice."""
        wav_io = io.BytesIO(audio_bytes)
        with wave.open(wav_io, 'rb') as wf:
            n_channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            audio_data = wf.readframes(wf.getnframes())

        # Convert to numpy
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        audio_np = audio_np.astype(np.float32) / 32768.0

        # Play synchronously
        self.sd.play(audio_np, samplerate=sample_rate, blocking=True)


class SimpleAudioPlayer:
    """Fallback audio player using simpleaudio."""

    def __init__(self, sa_module):
        self.sa = sa_module

    def play(self, audio_bytes: bytes) -> None:
        """Play WAV bytes using simpleaudio."""
        wav_io = io.BytesIO(audio_bytes)
        with wave.open(wav_io, 'rb') as wf:
            sample_rate = wf.getframerate()
            audio_data = wf.readframes(wf.getnframes())

        # Parse and convert
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        audio_np = audio_np.astype(np.float32) / 32768.0

        # Play
        play_obj = self.sa.play_buffer(
            (audio_np * 32767).astype(np.int16),
            num_channels=1,
            bytes_per_sample=2,
            sample_rate=sample_rate
        )
        play_obj.wait()


def get_audio_devices() -> list[dict]:
    """
    Get list of available audio output devices.

    Returns:
        List of device info dicts with 'id', 'name', 'latency' keys
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
        # Use system_profiler for device list (simplified)
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
