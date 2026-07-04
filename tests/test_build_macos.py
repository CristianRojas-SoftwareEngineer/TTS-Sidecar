"""Tests estáticos de los templates generados por build_macos.py (R-24).

Aserciones de cadena sobre las funciones puras: _path_install_script,
_path_uninstall_script, _info_plist_content.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from build_macos import (
    _info_plist_content,
    _minimum_system_version,
    _path_install_script,
    _path_uninstall_script,
)


def test_info_plist_version_and_lsminimum():
    """Info.plist debe llevar la versión y el LSMinimumSystemVersion derivado del toolchain (N-07)."""
    plist = _info_plist_content("9.9.9", icon_name="tts-sidecar")
    assert "<key>CFBundleShortVersionString</key>" in plist
    assert "<string>9.9.9</string>" in plist
    assert "<key>LSMinimumSystemVersion</key>" in plist
    assert f"<string>{_minimum_system_version()}</string>" in plist
    assert "GPL-3.0-or-later" in plist


def test_minimum_system_version_uses_deployment_target(monkeypatch):
    """N-07: prioriza MACOSX_DEPLOYMENT_TARGET; cae a mac_ver() si falta."""
    import build_macos

    monkeypatch.setattr(
        build_macos.sysconfig, "get_config_var", lambda name: "14.4"
    )
    assert build_macos._minimum_system_version() == "14.4"

    monkeypatch.setattr(build_macos.sysconfig, "get_config_var", lambda name: None)
    monkeypatch.setattr(
        build_macos.platform, "mac_ver", lambda: ("15.1.1", ("", "", ""), "")
    )
    assert build_macos._minimum_system_version() == "15.0"

    monkeypatch.setattr(build_macos.platform, "mac_ver", lambda: ("", ("", "", ""), ""))
    assert build_macos._minimum_system_version() == "12.0"


def test_install_script_shebang_set_e_sudo_symlink_and_setup_offer():
    """El .command de instalación: set -e, sudo ln -sf, y oferta de setup."""
    script = _path_install_script("tts-sidecar-arm64.app")
    assert script.startswith("#!/bin/bash\n")
    assert "set -e" in script
    assert "sudo mkdir -p /usr/local/bin" in script
    assert "sudo ln -sf" in script
    assert "/usr/local/bin/tts-sidecar" in script
    # Oferta de descargar el modelo (tts-sidecar setup) en el contexto del usuario
    assert "tts-sidecar setup" in script
    assert "Descargar ahora el modelo de voz" in script
    assert "s/n" in script  # prompt interactivo


def test_uninstall_script_rejects_non_symlink():
    """Desinstalación: solo elimina si es symlink; rechaza archivo regular homónimo."""
    script = _path_uninstall_script()
    assert script.startswith("#!/bin/bash\n")
    assert "set -e" in script
    assert 'if [ -L "$LINK" ]; then' in script
    assert 'elif [ -e "$LINK" ]; then' in script
    assert "no es un symlink" in script
    assert "exit 1" in script