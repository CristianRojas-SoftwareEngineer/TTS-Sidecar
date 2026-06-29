#!/usr/bin/env python3
"""
Installer script for Chatterbox TTS.
Downloads the model and configures the environment.
Run as: python install.py
Or after Nuitka compilation: ./tts-sidecar install
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

# Import shared logging utilities
sys.path.insert(0, str(Path(__file__).parent))
from build_utils import log, StageTimer


def get_install_dir():
    """Get the installation directory for models and config."""
    install_dir = os.environ.get("TTS_SIDECAR_HOME")
    if install_dir:
        return Path(install_dir)

    system = platform.system()
    home = Path.home()

    if system == "Windows":
        base = home / "AppData" / "Local"
    elif system == "Darwin":
        base = home / "Library" / "Application Support"
    else:
        base = home / ".local" / "share"

    return base / "tts-sidecar"


def install_dependencies():
    """Install Python dependencies."""
    with StageTimer("Dependencies", "Installing Python dependencies"):
        deps = ["chatterbox-tts"]
        system = platform.system()
        if system == "Windows":
            deps.append("pycaw")
        elif system == "Linux":
            deps.append("sounddevice")
            deps.append("pyalsaaudio")
        subprocess.run(
            [sys.executable, "-m", "pip", "install"] + deps,
            check=True
        )


def download_model(install_dir: Path):
    """Download the Chatterbox model."""
    with StageTimer("Download", "Downloading Chatterbox Multilingual V3 model"):
        try:
            from chatterbox.tts import ChatterboxTTS
            model_path = install_dir / "models" / "chatterbox-multilingual"
            model_path.mkdir(parents=True, exist_ok=True)
            log(f"Downloading to: {model_path}")
            ChatterboxTTS.from_pretrained("ResembleAI/chatterbox-multilingual")
        except Exception as e:
            log(f"Model download failed: {e}")
            raise


def create_directories(install_dir: Path):
    """Create necessary directories."""
    with StageTimer("Dirs", "Creating directories"):
        (install_dir / "models").mkdir(parents=True, exist_ok=True)
        (install_dir / "voices").mkdir(parents=True, exist_ok=True)
        (install_dir / "config").mkdir(parents=True, exist_ok=True)
        log(f"Install directory: {install_dir}")


def create_config(install_dir: Path):
    """Create default configuration."""
    import json
    with StageTimer("Config", "Creating configuration"):
        config = {
            "model_path": str(install_dir / "models" / "chatterbox-multilingual"),
            "voices_path": str(install_dir / "voices"),
            "device": "cpu",
            "language": "es",
        }
        config_path = install_dir / "config" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        log(f"Config saved: {config_path}")


def main():
    import time
    start = time.time()
    print()
    log("=== INSTALL STARTED ===")
    log(f"Platform: {platform.system()} {platform.release()}")
    log(f"Python: {sys.version.split()[0]}")

    install_dir = get_install_dir()
    log(f"Install directory: {install_dir}")

    create_directories(install_dir)
    install_dependencies()
    download_model(install_dir)
    create_config(install_dir)

    log("=== INSTALL COMPLETED ===", time.time() - start)
    print()


if __name__ == "__main__":
    main()
