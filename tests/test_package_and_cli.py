"""Smoke tests: the package imports and the CLI skeleton runs."""
import importlib

import pytest

from edinet_replay import __version__, cli

MODULES = [
    "edinet_replay.client",
    "edinet_replay.catalog",
    "edinet_replay.selectors",
    "edinet_replay.package",
    "edinet_replay.taxonomy",
    "edinet_replay.extract",
    "edinet_replay.models",
    "edinet_replay.hashing",
    "edinet_replay.cli",
]


def test_version():
    assert __version__ == "0.1.0"


@pytest.mark.parametrize("name", MODULES)
def test_all_modules_import(name):
    importlib.import_module(name)


def test_cli_no_command_prints_help_and_returns_zero(capsys):
    assert cli.main([]) == 0
    assert "edinet-replay" in capsys.readouterr().out


def test_cli_subcommand_is_not_implemented():
    with pytest.raises(SystemExit):
        cli.main(["fetch", "--date", "2026-07-01"])
