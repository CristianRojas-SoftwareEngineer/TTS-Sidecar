"""
Utilidades compartidas para los scripts de build.
Provee logging con timestamp [HH:MM:SS], tracking de etapas y el empaquetado
de los avisos de licencia en el bundle distribuible.
"""

import shutil
import time
from datetime import datetime
from pathlib import Path

# Archivos de cumplimiento de licencia que deben viajar dentro de cada artefacto
# distribuible (PyInstaller elimina los avisos de licencia de las dependencias).
LICENSE_FILES = ("LICENSE", "THIRD-PARTY-LICENSES.md")


def copy_license_files(dest_dir) -> None:
    """Copia LICENSE y THIRD-PARTY-LICENSES.md desde la raíz del proyecto a dest_dir.

    Se invoca tras PyInstaller en cada plataforma para que el bundle distribuible
    (onedir de Windows/Linux, .app de macOS) incluya los avisos de licencia que
    GPLv3 y las licencias permisivas de terceros exigen preservar al redistribuir.
    """
    project_root = Path(__file__).parent.parent
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for name in LICENSE_FILES:
        src = project_root / name
        if src.exists():
            shutil.copy2(src, dest / name)
            log(f"Licencia empaquetada: {name} -> {dest}")
        else:
            log(f"WARNING: no se encontró {name} en la raíz; no se empaquetó")


def get_version(init_path: Path = None) -> str:
    """Lee la versión de src/chatterbox_tts/__init__.py.

    Fuente única de versión para los tres scripts de build (Windows, Linux,
    macOS) y el generador del instalador Inno Setup. `init_path` permite
    apuntar a otro __init__.py (tests).
    """
    if init_path is None:
        init_path = Path(__file__).parent.parent / "src" / "chatterbox_tts" / "__init__.py"
    for line in init_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("__version__"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                return parts[1].strip().strip('"').strip("'")
    raise RuntimeError("Could not find __version__ in __init__.py")


def _format_duration(seconds: float) -> str:
    """Formatea segundos a string legible.

    - < 60s       → '45.2s'
    - 60s–3599s   → '1m 32.5s'
    - ≥ 3600s     → '1h 23m 45.0s'
    """
    if seconds >= 3600:
        h = int(seconds // 3600)
        remainder = seconds - h * 3600
        m = int(remainder // 60)
        s = remainder - m * 60
        return f"{h}h {m}m {s:.1f}s"
    if seconds >= 60:
        m = int(seconds // 60)
        s = seconds - m * 60
        return f"{m}m {s:.1f}s"
    return f"{seconds:.1f}s"


def log(msg: str, duration: float = None):
    """Imprime un mensaje de log con formato consistente.

    Sin duration: [HH:MM:SS] Mensaje...
    Con duration: [HH:MM:SS] Mensaje -> Done (1m 32s)
    """
    now = datetime.now().strftime("%H:%M:%S")
    if duration is not None:
        print(f"[{now}] {msg} -> Done ({_format_duration(duration)})")
    else:
        print(f"[{now}] {msg}...")


class StageTimer:
    """Context manager para temporizar una etapa de build.

    Uso:
        with StageTimer("NombreEtapa", "Descripción"):
            # código a temporizar
    """

    def __init__(self, name: str, description: str = None):
        self.name = name
        self.description = description or name
        self.start = None

    def __enter__(self):
        self.start = time.time()
        print()
        log(f"[{self.name}] {self.description}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start
        log(f"[{self.name}]", duration)
        print()
        return False


class BuildTimer:
    """Context manager para temporizar el proceso de build completo.

    A diferencia de StageTimer (que mide etapas individuales), BuildTimer
    envuelve todo el build e imprime cabeceras de inicio y fin globales.
    """

    def __init__(self):
        self.start = None
        self.duration = None

    def __enter__(self):
        self.start = time.time()
        print()
        log("=== BUILD INICIADO ===")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = time.time() - self.start
        if exc_type is None:
            log("=== BUILD COMPLETADO ===", self.duration)
        else:
            log("=== BUILD FALLIDO ===", self.duration)
        print()
        return False
