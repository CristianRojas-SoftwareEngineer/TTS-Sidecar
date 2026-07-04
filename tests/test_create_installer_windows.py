"""Tests estáticos del script Inno Setup generado para el instalador de Windows."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from create_installer_windows import generate_iss


@pytest.fixture
def iss(tmp_path):
    """ISS generado con rutas temporales y versión sintética."""
    source_dir = tmp_path / "onedir"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    info_after = tmp_path / "info.txt"
    info_after.write_text("info", encoding="utf-8")
    return generate_iss(source_dir, output_dir, "9.9.9", info_after)


def test_nombre_del_instalador_incluye_version_y_sufijo(iss):
    # A-03: vocabulario de arquitectura unificado al estilo `uname -m` (x86_64),
    # en paridad con los AppImage de Linux.
    assert "OutputBaseFilename=tts-sidecar-9.9.9-x86_64-setup" in iss


def test_setup_postinstalacion_persiste_la_consola(iss):
    # W-03: el setup post-instalación se lanza vía `cmd /k` para que la consola
    # quede abierta mostrando el resultado (éxito o fallo) hasta que el usuario
    # la cierre — paridad con la Terminal persistente del .command de macOS.
    assert 'Filename: {cmd}; Parameters: "/k ""{app}\\tts-sidecar.exe"" setup"' in iss
    assert "postinstall skipifsilent runasoriginaluser nowait" in iss


def test_agrega_path_condicionado_por_needsaddpath(iss):
    assert "function NeedsAddPath(Param: string): boolean;" in iss
    assert "Check: NeedsAddPath(ExpandConstant('{app}'))" in iss


def test_desinstalacion_recorta_la_entrada_de_path(iss):
    # W-01: el desinstalador debe revertir la entrada {app} del PATH de HKLM.
    assert "procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);" in iss
    assert "usUninstall" in iss
    assert "RegWriteExpandStringValue(HKLM," in iss


def test_sin_clave_uninstall_manual(iss):
    # W-02: Inno Setup genera su propia entrada ({AppId}_is1); la clave manual
    # duplicaría el programa en «Aplicaciones y características».
    assert "CurrentVersion\\Uninstall\\tts-sidecar" not in iss


def test_info_after_ofrece_codigo_fuente_gplv3():
    """R-34: la página InfoAfter del instalador debe ofrecer el código fuente
    bajo GPLv3 y enlazar al repositorio (GPLv3 §6)."""
    from create_installer_windows import info_after_text

    text = info_after_text()
    assert "GPLv3" in text or "GPL-3.0" in text
    assert "github.com/CristianRojas-SoftwareEngineer/TTS-Sidecar" in text
    # Debe seguir explicando la provisión del modelo (compatibilidad con W-03).
    assert "tts-sidecar setup" in text
    # N-08: el instalador NO incluye el código fuente junto al programa; la
    # oferta GPLv3 §6d correcta es la disponibilidad pública en el repositorio.
    assert "accompanido" not in text
    assert "LICENSE.txt" not in text
    assert "disponible públicamente" in text


def test_main_compila_el_instalador_con_iscc_mockeado(tmp_path, monkeypatch):
    """N-01: main() debe llegar a invocar ISCC con un .iss válido. La regresión
    de 8a18fad dejó el bloque de compilación inalcanzable dentro de
    info_after_text(): main() retornaba tras mkdir sin compilar nada, y ningún
    test lo detectaba porque solo se ejercitaban funciones puras."""
    import create_installer_windows as ciw

    onedir = tmp_path / "onedir"
    onedir.mkdir()
    (onedir / "tts-sidecar.exe").write_bytes(b"MZ")
    output_dir = tmp_path / "out"

    fake_iscc = str(tmp_path / "ISCC.exe")
    invocations = []
    iss_contents = []

    def fake_run(cmd, **kwargs):
        invocations.append(cmd)
        # El .iss es un tempfile que main() borra en su finally: se lee aquí.
        iss_contents.append(Path(cmd[1]).read_text(encoding="utf-8"))

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        # Simula el artefacto que ISCC dejaría en OutputDir.
        version = ciw.get_version()
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"tts-sidecar-{version}-x86_64-setup.exe").write_bytes(b"MZ")
        return Result()

    monkeypatch.setattr(
        sys, "argv",
        ["create_installer_windows.py", str(onedir), "--output", str(output_dir)],
    )
    monkeypatch.setattr(ciw, "get_inno_setup_path", lambda: fake_iscc)
    monkeypatch.setattr(ciw, "ensure_build_dependency", lambda *a, **k: True)
    monkeypatch.setattr(ciw, "ensure_ico", lambda _dir: None)
    monkeypatch.setattr(ciw.subprocess, "run", fake_run)

    ciw.main()

    # Si main() retorna sin invocar ISCC, la regresión N-01 ha vuelto.
    assert len(invocations) == 1
    cmd = invocations[0]
    assert cmd[0] == fake_iscc
    assert cmd[1].endswith(".iss")
    assert "OutputBaseFilename=tts-sidecar-" in iss_contents[0]
