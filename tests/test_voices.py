"""Tests de la resolución y listado de voces (criterio dual-audio).

Una voz solo es válida con sus dos archivos: reference.wav (timbre) y
speech.wav (conditioning). Cubre _resolve_voice_dir y list_voices con la
precedencia usuario→fábrica sobre directorios temporales.
"""

import pytest

from chatterbox_tts import voices


@pytest.fixture
def voice_roots(tmp_path, monkeypatch):
    """Redirige las raíces usuario/fábrica a directorios temporales vacíos."""
    user_root = tmp_path / "user"
    factory_root = tmp_path / "factory"
    user_root.mkdir()
    factory_root.mkdir()
    monkeypatch.setattr(voices, "voices_root", lambda: str(user_root))
    monkeypatch.setattr(voices, "factory_voices_root", lambda: str(factory_root))
    return user_root, factory_root


def _make_voice(root, name, reference=True, speech=True):
    voice = root / name
    voice.mkdir()
    if reference:
        (voice / "reference.wav").write_bytes(b"RIFF")
    if speech:
        (voice / "speech.wav").write_bytes(b"RIFF")
    return voice


class TestResolveVoiceDir:
    def test_voz_completa_se_resuelve(self, voice_roots):
        user_root, _ = voice_roots
        expected = _make_voice(user_root, "mia")
        assert voices._resolve_voice_dir("mia") == str(expected)

    def test_voz_solo_reference_no_se_resuelve(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia", speech=False)
        assert voices._resolve_voice_dir("mia") is None

    def test_voz_solo_speech_no_se_resuelve(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia", reference=False)
        assert voices._resolve_voice_dir("mia") is None

    def test_precedencia_usuario_sobre_fabrica(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(factory_root, "default")
        expected = _make_voice(user_root, "default")
        assert voices._resolve_voice_dir("default") == str(expected)

    def test_usuario_incompleta_cae_a_fabrica(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "default", speech=False)
        expected = _make_voice(factory_root, "default")
        assert voices._resolve_voice_dir("default") == str(expected)


class TestListVoices:
    def test_lista_solo_voces_completas(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "completa")
        _make_voice(user_root, "sin_speech", speech=False)
        _make_voice(factory_root, "default")
        assert voices.list_voices() == ["completa", "default"]

    def test_sin_duplicados_entre_niveles(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "default")
        _make_voice(factory_root, "default")
        assert voices.list_voices() == ["default"]


class TestSanitizacionDeNombres:
    @pytest.mark.parametrize("name", ["..", "../x", "a/b", "a\\b", "C:\\abs", "/abs", "", "."])
    def test_voice_dir_rechaza_nombres_maliciosos(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.voice_dir(name)

    @pytest.mark.parametrize("name", ["..", "../x", "a/b", "a\\b", "C:\\abs"])
    def test_remove_voice_rechaza_nombres_maliciosos(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.remove_voice(name)

    @pytest.mark.parametrize("name", ["..", "../x", "a/b"])
    def test_voice_paths_rechaza_nombres_maliciosos(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.voice_paths(name)

    def test_remove_voice_no_borra_directorios_que_no_son_voces(self, voice_roots):
        user_root, _ = voice_roots
        intruso = user_root / "no_es_voz"
        intruso.mkdir()
        (intruso / "datos.txt").write_text("importante")
        assert voices.remove_voice("no_es_voz") is False
        assert intruso.exists()

    def test_remove_voice_borra_voz_valida(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia")
        assert voices.remove_voice("mia") is True
        assert not (user_root / "mia").exists()


def test_voice_paths_de_voz_listada_nunca_falla(voice_roots):
    """La invariante que motivó el cambio: toda voz listada es resoluble."""
    user_root, _ = voice_roots
    _make_voice(user_root, "completa")
    _make_voice(user_root, "sin_speech", speech=False)
    for name in voices.list_voices():
        ref, speech = voices.voice_paths(name)
        assert ref.endswith("reference.wav")
        assert speech.endswith("speech.wav")
