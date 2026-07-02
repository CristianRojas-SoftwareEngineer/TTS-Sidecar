"""
Gestión del registro de voces, libre de modelo.

Hogar único de las rutas del directorio de voces y de las operaciones de registro
(listar, eliminar, resolver rutas). El modelo de voces es de **dos niveles**:

- **Usuario**: voces escribibles en `data_root()/voices` (user-data-dir por SO
  cuando está congelado; `src/voices` en modo fuente históricamente, hoy vacío).
- **Fábrica**: voces de solo lectura empaquetadas en `bundled_voices_dir()`
  (raíz del repo en modo fuente; `sys._MEIPASS` congelado).

La resolución de un nombre busca primero en usuario y luego en fábrica, de modo
que un usuario puede sobrescribir una voz de fábrica registrando una propia con
el mismo nombre. Ninguna función aquí importa ni carga el modelo: son operaciones
puras de sistema de archivos.
"""

import os
import re
import shutil

from . import paths

# Nombres de voz admitidos: un único segmento de ruta sin separadores ni escapes.
_VOICE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_voice_name(name: str) -> str:
    """Valida un nombre de voz antes de componer cualquier ruta con él.

    Rechaza nombres vacíos, con separadores de ruta, rutas absolutas o `..`,
    eliminando la clase de escapes de ruta (p. ej. `voice remove --name ..`
    resolvería al padre del registro y lo borraría).
    """
    if not name or not _VOICE_NAME_RE.match(name) or ".." in name or name == ".":
        raise ValueError(
            f"Nombre de voz inválido: {name!r}. "
            "Usa solo letras, números, punto, guion y guion bajo (sin '..' ni separadores de ruta)."
        )
    return name


def voices_root() -> str:
    """Directorio base de las voces de usuario (escribible)."""
    return os.path.join(paths.data_root(), "voices")


def factory_voices_root() -> str:
    """Directorio base de las voces de fábrica (solo lectura)."""
    return paths.bundled_voices_dir()


def voice_dir(name: str) -> str:
    """Directorio de una voz de usuario concreta (destino de escritura)."""
    _validate_voice_name(name)
    root = voices_root()
    target = os.path.join(root, name)
    # Defensa en profundidad: la ruta resuelta debe quedar dentro del registro.
    real_root = os.path.realpath(root)
    if os.path.realpath(target) != os.path.join(real_root, name):
        raise ValueError(f"Nombre de voz inválido: {name!r} (escapa del registro de voces)")
    return target


def _is_valid_voice_dir(candidate: str) -> bool:
    """Una voz es válida solo con sus dos audios: reference.wav (timbre) y
    speech.wav (conditioning), igual que exige `voice add`."""
    return os.path.exists(os.path.join(candidate, "reference.wav")) and os.path.exists(
        os.path.join(candidate, "speech.wav")
    )


def _resolve_voice_dir(name: str) -> str | None:
    """Devuelve el directorio de una voz con precedencia usuario→fábrica, o None."""
    _validate_voice_name(name)
    for root in (voices_root(), factory_voices_root()):
        candidate = os.path.join(root, name)
        if _is_valid_voice_dir(candidate):
            return candidate
    return None


def list_voices() -> list[str]:
    """Listar todas las voces disponibles (usuario + fábrica, sin duplicados)."""
    seen = []
    for root in (voices_root(), factory_voices_root()):
        if not os.path.exists(root):
            continue
        for entry in sorted(os.listdir(root)):
            candidate = os.path.join(root, entry)
            if entry not in seen and os.path.isdir(candidate) and _is_valid_voice_dir(candidate):
                seen.append(entry)
    return seen


def remove_voice(name: str) -> bool:
    """Eliminar una voz de usuario. Devuelve True si existía y se borró.

    Solo opera sobre voces de usuario; las de fábrica son de solo lectura.
    """
    target = voice_dir(name)
    # Solo se borran directorios que sean voces válidas: un directorio arbitrario
    # dentro del registro (o el registro mismo) nunca es objetivo de rmtree.
    if os.path.exists(target) and _is_valid_voice_dir(target):
        shutil.rmtree(target)
        return True
    return False


def voice_paths(name: str) -> tuple[str, str]:
    """
    Resolver el nombre de una voz a sus rutas de audio (reference, speech).

    Busca con precedencia usuario→fábrica y valida la existencia de ambos archivos.
    """
    target = _resolve_voice_dir(name)
    if target is None:
        raise FileNotFoundError(
            f"Voz '{name}' no encontrada (ni en las voces de usuario ni en las de fábrica). "
            f"Regístrala con 'tts-sidecar voice add' o usa la voz 'default'."
        )
    ref_path = os.path.join(target, "reference.wav")
    speech_path = os.path.join(target, "speech.wav")
    if not os.path.exists(ref_path):
        raise FileNotFoundError(f"Voz '{name}': reference.wav no encontrado en {ref_path}")
    if not os.path.exists(speech_path):
        raise FileNotFoundError(f"Voz '{name}': speech.wav no encontrado en {speech_path}")
    return (ref_path, speech_path)
