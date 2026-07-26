"""Tests for S2 hub CLI choice/dispatch parity."""
from __future__ import annotations

from pathlib import Path

from _sys.checks import check_cli_dispatch_parity as checker
from _sys.checks._common import WorktreeView


def _source(choices: str, dispatch: str) -> str:
    return (
        "import argparse\n"
        "\n"
        "def first_handler():\n"
        "    return None\n"
        "\n"
        "def unrelated_name():\n"
        "    return None\n"
        "\n"
        "def main():\n"
        "    parser = argparse.ArgumentParser()\n"
        f"    parser.add_argument('action', choices={choices})\n"
        "    parser.add_argument('--policy', choices=['fresh', 'reuse'])\n"
        "    args = parser.parse_args()\n"
        "    act = args.action\n"
        f"{dispatch}\n"
    )


def test_if_elif_parity_does_not_depend_on_handler_name_conversion():
    source = _source(
        "['hyphenated-action', 'other']",
        (
            "    if act == 'hyphenated-action':\n"
            "        unrelated_name()\n"
            "    elif act == 'other':\n"
            "        first_handler()"
        ),
    )
    assert checker.check_parity_source(source) == []


def test_reports_choice_without_dispatch_and_dispatch_without_choice():
    source = _source(
        "['declared-only', 'shared']",
        (
            "    if act == 'shared':\n"
            "        first_handler()\n"
            "    elif act == 'branch-only':\n"
            "        unrelated_name()"
        ),
    )
    findings = checker.check_parity_source(source)
    assert {finding.code for finding in findings} == {
        "CLI_CHOICE_WITHOUT_DISPATCH",
        "CLI_DISPATCH_WITHOUT_CHOICE",
    }
    assert any("'declared-only'" in finding.message for finding in findings)
    assert any("'branch-only'" in finding.message for finding in findings)


def test_invoked_dict_dispatch_keys_count_as_real_branches():
    source = _source(
        "['one', 'two']",
        (
            "    handlers = {'one': first_handler, 'two': unrelated_name}\n"
            "    handler = handlers.get(act)\n"
            "    handler()"
        ),
    )
    assert checker.check_parity_source(source) == []


def test_uninvoked_dict_is_not_dispatch():
    source = _source(
        "['one']",
        "    handlers = {'one': first_handler}",
    )
    findings = checker.check_parity_source(source)
    assert [finding.code for finding in findings] == [
        "CLI_CHOICE_WITHOUT_DISPATCH"
    ]


def test_non_action_choices_are_ignored():
    source = _source(
        "['one']",
        (
            "    if act == 'one':\n"
            "        first_handler()"
        ),
    )
    assert checker.check_parity_source(source) == []


def test_real_live_hub_choices_and_dispatch_are_in_parity():
    root = Path(__file__).resolve().parents[3]
    assert checker.check_view(WorktreeView(root)) == []
