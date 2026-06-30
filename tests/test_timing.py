"""Tests para las utilidades de timing.py."""

import pytest
import sys
from pathlib import Path
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from chatterbox_tts.timing import log, timed_command, timed, StageTimer


class TestLog:
    def test_log_without_duration(self, capsys):
        log("test message")
        out = capsys.readouterr().out
        assert "test message" in out
        # Formato: [HH:MM:SS] test message...
        assert "test message..." in out

    def test_log_with_duration(self, capsys):
        log("test operation", duration=1.5)
        out = capsys.readouterr().out
        assert "test operation" in out
        assert "Done (1.5s)" in out


class TestTimedCommand:
    def test_timed_command_start_finish(self, capsys):
        @timed_command
        def dummy_cmd(args):
            print("inside command")
            return 42

        class Args:
            pass

        result = dummy_cmd(Args())
        out = capsys.readouterr().out
        assert "Starting dummy_cmd..." in out
        assert "Finished in" in out
        assert "inside command" in out
        assert result == 42

    def test_timed_command_error(self, capsys):
        @timed_command
        def failing_cmd(args):
            raise ValueError("test error")

        class Args:
            pass

        with pytest.raises(ValueError):
            failing_cmd(Args())
        out = capsys.readouterr().out
        assert "Failed after" in out
        assert "test error" in out


class TestTimedDecorator:
    def test_timed_decorator(self, capsys):
        @timed("MyStage")
        def some_work():
            print("working")

        some_work()
        out = capsys.readouterr().out
        assert "[MyStage]" in out
        assert "working" in out


class TestStageTimer:
    def test_stage_timer_entry_exit(self, capsys):
        with StageTimer("TestStage", "doing work"):
            print("inside stage")
        out = capsys.readouterr().out
        assert "[TestStage] doing work..." in out
        assert "[TestStage]" in out
        assert "Done (" in out
        assert "inside stage" in out

    def test_stage_timer_no_description(self, capsys):
        with StageTimer("X"):
            pass
        out = capsys.readouterr().out
        assert "[X] X..." in out

    def test_stage_timer_exception(self, capsys):
        with pytest.raises(RuntimeError):
            with StageTimer("Fail"):
                raise RuntimeError("boom")
        # Debe registrar el fin de la etapa incluso cuando hay excepción
        out = capsys.readouterr().out
        assert "[Fail]" in out
