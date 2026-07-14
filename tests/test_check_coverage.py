"""Tests del gate de cobertura por módulo (scripts/check_coverage.py).

Deterministas: usan fixtures sintéticas de coverage.json, nunca cobertura real
(esa la ejercita el job `coverage` de CI, no la suite local). Homólogo a
tests/test_third_party_licenses.py.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from check_coverage import check, load_module_coverage, main


def _write_coverage_json(tmp_path, files: dict) -> Path:
    payload = {
        "files": {
            path: {"summary": {"percent_covered": pct}}
            for path, pct in files.items()
        }
    }
    json_path = tmp_path / "coverage.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    return json_path


class TestLoadModuleCoverage:
    def test_maps_path_to_percent_covered(self, tmp_path):
        json_path = _write_coverage_json(
            tmp_path,
            {"src/tts_sidecar/cli.py": 87.5, "src/tts_sidecar/voices.py": 92.0},
        )
        result = load_module_coverage(json_path)
        assert result["tts_sidecar/cli.py"] == 87.5
        assert result["tts_sidecar/voices.py"] == 92.0

    def test_normalizes_windows_separators(self, tmp_path):
        json_path = _write_coverage_json(
            tmp_path, {"src\\tts_sidecar\\daemon\\server.py": 60.0}
        )
        result = load_module_coverage(json_path)
        assert result["tts_sidecar/daemon/server.py"] == 60.0


class TestCheck:
    def test_module_below_floor_fails(self):
        coverage = {"tts_sidecar/cli.py": 40.0}
        floors = {"tts_sidecar/cli.py": 60.0}
        failures = check(coverage, floors)
        assert failures == [("tts_sidecar/cli.py", 40.0, 60.0)]

    def test_module_at_or_above_floor_passes(self):
        coverage = {"tts_sidecar/cli.py": 60.0, "tts_sidecar/voices.py": 99.0}
        floors = {"tts_sidecar/cli.py": 60.0, "tts_sidecar/voices.py": 50.0}
        assert check(coverage, floors) == []

    def test_missing_module_treated_as_zero(self):
        coverage = {}
        floors = {"tts_sidecar/cli.py": 10.0}
        failures = check(coverage, floors)
        assert failures == [("tts_sidecar/cli.py", 0.0, 10.0)]

    def test_non_contract_module_not_gated(self):
        # Un módulo fuera de MODULE_FLOORS ni siquiera se evalúa en check();
        # el reporte (no-gateado) es responsabilidad de main(), no de check().
        coverage = {"tts_sidecar/engine.py": 5.0}
        floors = {"tts_sidecar/cli.py": 10.0}
        failures = check(coverage, floors)
        assert failures == [("tts_sidecar/cli.py", 0.0, 10.0)]


class TestMainCli:
    def test_exits_1_when_module_below_floor(self, tmp_path, monkeypatch, capsys):
        json_path = _write_coverage_json(tmp_path, {"tts_sidecar/cli.py": 10.0})
        monkeypatch.setattr(
            "check_coverage.MODULE_FLOORS", {"tts_sidecar/cli.py": 80.0}
        )
        exit_code = main([str(json_path)])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "FALLA" in captured.out
        assert "gate de cobertura falló" in captured.err

    def test_exits_0_when_all_floors_met(self, tmp_path, monkeypatch, capsys):
        json_path = _write_coverage_json(tmp_path, {"tts_sidecar/cli.py": 85.0})
        monkeypatch.setattr(
            "check_coverage.MODULE_FLOORS", {"tts_sidecar/cli.py": 80.0}
        )
        exit_code = main([str(json_path)])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "OK" in captured.out

    def test_missing_argv_returns_1(self):
        assert main([]) == 1

    @pytest.mark.parametrize("malformed", ["not json", "{}"])
    def test_malformed_json_raises(self, tmp_path, malformed):
        json_path = tmp_path / "coverage.json"
        json_path.write_text(malformed, encoding="utf-8")
        with pytest.raises((json.JSONDecodeError, KeyError)):
            main([str(json_path)])
