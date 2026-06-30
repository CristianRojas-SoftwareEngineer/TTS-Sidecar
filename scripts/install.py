#!/usr/bin/env python3
"""
Script de instalación para Chatterbox TTS.
Descarga el modelo y configura el entorno.
Ejecutar como: python install.py

Nota: este script es un artefacto histórico. La provisión del modelo se realiza
hoy con el comando integrado en el CLI: tts-sidecar setup
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

# Importar utilidades de logging compartidas
sys.path.insert(0, str(Path(__file__).parent))
from build_utils import log, StageTimer


def get_install_dir():
    """Devuelve el directorio de instalación de modelos y configuración."""
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
    """Instala las dependencias Python."""
    with StageTimer("Dependencies", "Instalando dependencias Python"):
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
    """Descarga el modelo Chatterbox."""
    with StageTimer("Download", "Descargando modelo Chatterbox Multilingual V3"):
        try:
            from chatterbox.tts import ChatterboxTTS
            # TODO: model_path no se usa; el modelo descargado por from_pretrained
            # va a la caché de HuggingFace (~/.cache/huggingface/hub), no a este path
            model_path = install_dir / "models" / "chatterbox-multilingual"
            model_path.mkdir(parents=True, exist_ok=True)
            log(f"Descargando a: {model_path}")
            ChatterboxTTS.from_pretrained("ResembleAI/Chatterbox-Multilingual-es-mx-latam")
        except Exception as e:
            log(f"Descarga del modelo fallida: {e}")
            raise


def create_directories(install_dir: Path):
    """Crea los directorios necesarios."""
    with StageTimer("Dirs", "Creando directorios"):
        (install_dir / "models").mkdir(parents=True, exist_ok=True)
        (install_dir / "voices").mkdir(parents=True, exist_ok=True)
        (install_dir / "config").mkdir(parents=True, exist_ok=True)
        log(f"Directorio de instalación: {install_dir}")


def create_config(install_dir: Path):
    """Crea la configuración por defecto."""
    import json
    with StageTimer("Config", "Creando configuración"):
        # TODO: config.json no es leído por ningún módulo del engine ni del CLI;
        # la configuración se gestiona vía argumentos CLI y variables de entorno
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
        log(f"Configuración guardada: {config_path}")


def main():
    import time
    start = time.time()
    print()
    log("=== INSTALACIÓN INICIADA ===")
    log(f"Plataforma: {platform.system()} {platform.release()}")
    log(f"Python: {sys.version.split()[0]}")

    install_dir = get_install_dir()
    log(f"Directorio de instalación: {install_dir}")

    create_directories(install_dir)
    install_dependencies()
    download_model(install_dir)
    create_config(install_dir)

    log("=== INSTALACIÓN COMPLETADA ===", time.time() - start)
    print()


if __name__ == "__main__":
    main()
