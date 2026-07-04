"""Tests estáticos de los templates generados por build_linux.py (R-24).

Calcan el patrón de tests/test_create_installer_windows.py: aserciones de
cadena sobre las funciones puras que emiten los artifacts (AppRun, .desktop).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from build_linux import _apprun_script, _desktop_entry


def test_apprun_shebang_and_delegation():
    """El script AppRun debe tener shebang POSIX y delegar en el ejecutable
    del bundle pasando todos los argumentos ("$@")."""
    script = _apprun_script()
    assert script.startswith("#!/bin/sh\n")
    assert 'HERE="$(dirname "$(readlink -f "$0")")"' in script
    assert 'exec "$HERE/usr/bin/tts-sidecar" "$@"' in script


def test_desktop_entry_application_type_and_terminal():
    """El .desktop debe ser Type=Application y Terminal=true (salida CLI visible)."""
    desktop = _desktop_entry()
    assert "Type=Application" in desktop
    assert "Name=tts-sidecar" in desktop
    assert "Exec=tts-sidecar" in desktop
    assert "Icon=tts-sidecar" in desktop
    assert "Terminal=true" in desktop
    assert desktop.count("\n") >= 6  # al menos 6 líneas (clave=valor)