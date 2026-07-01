"""Tests de get_version, la fuente única de versión de los scripts de build."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from build_utils import get_version


def test_lee_version_de_init_sintetico(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('__version__ = "1.2.3"\n', encoding="utf-8")
    assert get_version(init) == "1.2.3"


def test_acepta_comillas_simples(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text("__version__ = '4.5.6'\n", encoding="utf-8")
    assert get_version(init) == "4.5.6"


def test_sin_version_lanza_runtime_error(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('"""Módulo sin versión."""\n', encoding="utf-8")
    with pytest.raises(RuntimeError):
        get_version(init)


def test_default_lee_la_version_real_del_repo():
    from chatterbox_tts import __version__
    assert get_version() == __version__
