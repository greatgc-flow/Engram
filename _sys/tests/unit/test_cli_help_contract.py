"""CLI help contract (frozen surface).

Static checks over core/help/*.txt (the single source of every `engram <verb> --help` and of `engram help`),
plus behavior checks: consistent unknown-option/unknown-verb errors (exit 2, 'Did you mean', no traceback),
`engram help <verb>`, and the --dry-run alias on dry-run-by-default verbs.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

SYS_DIR = find_root(__file__)
REPO = SYS_DIR.parent
sys.path.insert(0, str(SYS_DIR))
from core import cli_help  # noqa: E402

HELP_DIR = SYS_DIR / "core" / "help"
ENGRAM_CMD = REPO / "engram.cmd"
VERBS = cli_help.verbs()
GROUPS = ("Daily use:", "Health & repair:", "Backups & state:", "Removal:")
SECTIONS = ("Usage:", "Description:", "Options:", "Examples:", "Exit codes:", "See also:")


def _text(verb):
    return (HELP_DIR / f"{verb}.txt").read_text(encoding="utf-8")


def _rows(index_text):
    """(group, verb) for every command-table row before 'Common workflows:'."""
    out, group = [], None
    for line in index_text.split("Common workflows:")[0].split("\n"):
        if line.rstrip() in GROUPS:
            group = line.rstrip()
        m = re.match(r"^  engram (\w+)\s{2,}\S", line)
        if m:
            out.append((group, m.group(1)))
    return out


def test_all_public_verbs_have_a_help_file():
    assert set(VERBS) == {"open", "update", "doctor", "menu", "tidy", "snapshots", "repair", "relocate",
                          "uninstall", "backup", "restore", "reset", "version"}


def test_every_public_verb_in_engram_cmd_has_help_and_vice_versa():
    cmd = ENGRAM_CMD.read_text(encoding="utf-8")
    routed = set(re.findall(r'^if /i "%SUBCMD%"=="(\w+)" goto :cmd_\w+$', cmd, re.M)) | {"version"}
    assert routed == set(VERBS)


@pytest.mark.parametrize("verb", VERBS)
def test_verb_help_layout(verb):
    text = _text(verb)
    lines = text.split("\n")
    assert lines[0].startswith(f"engram {verb} - "), "first line is 'engram <verb> - <summary>'"
    positions = []
    for heading in SECTIONS:
        idx = [i for i, l in enumerate(lines) if l.startswith(heading)]
        assert len(idx) == 1, f"{verb}: section {heading!r} must appear exactly once"
        positions.append(idx[0])
    assert positions == sorted(positions), f"{verb}: sections out of order"
    assert text.split("Usage:")[1].split("\n")[0].strip().startswith(f"engram {verb}")


@pytest.mark.parametrize("verb", VERBS)
def test_verb_help_has_three_realistic_examples(verb):
    examples = [l.strip() for l in cli_help.section(verb, "Examples:") if l.strip()]
    assert len(examples) >= 3, verb
    assert sum(1 for l in examples if l.startswith("engram ")) >= 3, verb


@pytest.mark.parametrize("verb", VERBS)
def test_every_option_states_its_default(verb):
    block, blocks = None, []
    for line in cli_help.section(verb, "Options:"):
        if re.match(r"^  \S", line):
            block = [line]
            blocks.append(block)
        elif block is not None and line.strip():
            block.append(line)
    flag_blocks = [b for b in blocks if b[0].lstrip().startswith("-")]
    assert flag_blocks, verb
    for b in flag_blocks:
        assert "default" in " ".join(b), f"{verb}: option without a stated default: {b[0].strip()}"


@pytest.mark.parametrize("verb", VERBS)
def test_every_verb_documents_exit_codes_and_see_also(verb):
    codes = [l for l in cli_help.section(verb, "Exit codes:") if l.strip()]
    assert any(re.match(r"^\s+0\s", l) for l in codes), f"{verb}: exit code 0 undocumented"
    assert [l for l in cli_help.section(verb, "See also:") if l.strip()], verb


@pytest.mark.parametrize("name", VERBS + ["index"])
def test_help_files_are_ascii_and_fit_80_columns(name):
    text = (HELP_DIR / f"{name}.txt").read_text(encoding="utf-8")
    assert text.isascii(), name
    assert "\r" not in text
    assert max(len(l) for l in text.split("\n")) <= 79, name


def test_engram_help_lists_every_public_verb_exactly_once_in_one_group():
    rows = _rows((HELP_DIR / "index.txt").read_text(encoding="utf-8"))
    listed = [v for _, v in rows]
    assert sorted(listed) == sorted(VERBS), "index must list exactly the public verbs"
    assert len(listed) == len(set(listed)), "a verb appears in more than one group"
    assert all(g in GROUPS for g, _ in rows), "every verb sits in a known group"
    assert {g for g, _ in rows} == set(GROUPS), "no empty group"


def test_engram_help_has_workflows_and_pointers():
    text = (HELP_DIR / "index.txt").read_text(encoding="utf-8")
    assert "engram <command> --help" in text and "engram help <command>" in text
    workflows = text.split("Common workflows:")[1].split("Exit codes")[0]
    lines = [l for l in workflows.split("\n") if "engram" in l]
    assert 8 <= len(lines) <= 14
    for needle in ("engram repair", "engram relocate", "engram snapshots", "tidy --adopt-legacy",
                   "tidy --purge-legacy", "update --only python", "engram backup", "engram restore",
                   "engram reset", "engram uninstall"):
        assert needle in workflows, needle


def test_documented_flags_are_the_shared_vocabulary():
    for verb in ("tidy", "repair", "relocate", "restore", "reset", "snapshots"):
        assert "--dry-run" in cli_help.option_names(verb), verb   # no-op alias of the default
        assert "--apply" in cli_help.option_names(verb), verb
    for verb in ("repair", "relocate"):
        assert "--yes" in cli_help.option_names(verb)
    assert "--json" in cli_help.option_names("doctor")


# ---- behavior ------------------------------------------------------------------------------------------

def _dispatch(*args):
    env = dict(os.environ, PYTHONUTF8="1")
    return subprocess.run([sys.executable, str(SYS_DIR / "core" / "dispatcher.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                          cwd=str(REPO), timeout=120)


@pytest.mark.parametrize("verb", [v for v in VERBS if v not in ("menu", "version")])
def test_unknown_option_is_a_clean_usage_error(verb):
    pipeline = "start" if verb == "open" else verb
    proc = _dispatch(pipeline, "--aply")
    out = proc.stdout + proc.stderr
    assert proc.returncode == 2, (verb, proc.returncode, out)
    assert "Traceback" not in out
    assert "--aply" in out and f"engram {verb}" in out
    assert f"Run 'engram {verb} --help'" in out


@pytest.mark.parametrize("verb", ["tidy", "repair", "relocate", "restore", "reset", "uninstall"])
def test_unknown_option_suggests_the_near_match(verb):
    args = ["x.zip", "--aply"] if verb == "restore" else ["--aply"]
    proc = _dispatch(verb, *args)
    assert proc.returncode == 2
    assert "Did you mean '--apply'?" in proc.stdout


def test_snapshots_unknown_option_and_action_are_clean():
    proc = _dispatch("snapshots", "restore", "x", "--aply")
    assert proc.returncode == 2 and "Traceback" not in proc.stdout + proc.stderr
    assert "Did you mean '--apply'?" in proc.stdout
    proc = _dispatch("snapshots", "lst")
    assert proc.returncode == 2 and "Did you mean 'list'?" in proc.stdout


@pytest.mark.parametrize("verb", [v for v in VERBS if v not in ("menu", "version")])
def test_dispatcher_prints_the_same_help_file(verb):
    pipeline = "start" if verb == "open" else verb
    for flag in ("--help", "-h", "/?"):
        proc = _dispatch(pipeline, flag)
        assert proc.returncode == 0, (verb, flag)
        assert proc.stdout.replace("\r\n", "\n") == _text(verb), (verb, flag)


def test_update_unknown_component_has_a_hint():
    proc = _dispatch("update", "--only", "claud")
    assert proc.returncode == 2
    assert "Traceback" not in proc.stdout + proc.stderr
    assert "Did you mean 'claude'?" in proc.stdout


def test_update_parser_accepts_every_documented_flag():
    from core import updater
    args = updater._parse_args(["--yes", "--check", "--dry-run", "--refresh", "--only", "python",
                                "--allow-major-runtime-upgrade", "--to", "3.13.1", "--all-packages",
                                "--force", "--offline"])
    assert args.to_version == "3.13.1" and args.offline and args.force and args.all_packages


@pytest.mark.parametrize("command", ["repair", "relocate"])
def test_repair_engine_accepts_dry_run_and_short_yes(tmp_path, monkeypatch, command):
    from core import repair

    def parsed(*a, **k):
        raise RuntimeError("parsed")        # reached only when argument parsing succeeded
    monkeypatch.setattr(repair, "detect", parsed)
    ctx = {"sys_dir": tmp_path, "base_dir": tmp_path, "command": command, "args": ["--dry-run", "-y", "--apply"]}
    with pytest.raises(RuntimeError, match="parsed"):
        repair._repair_engine_main(ctx, repair.build_plan)


def test_cli_parser_error_format(capsys):
    p = cli_help.CliParser("tidy")
    p.add_argument("--apply", action="store_true")
    with pytest.raises(SystemExit) as exc:
        p.parse_args(["--aply"])
    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "[Error] Unknown option '--aply' for 'engram tidy'." in out
    assert "Did you mean '--apply'?" in out and "Run 'engram tidy --help' for usage." in out


# ---- engram.cmd: help <verb>, unknown command ----------------------------------------------------------

@pytest.fixture
def cmd_root(tmp_path):
    root = tmp_path / "a&b!"
    core = root / "_sys" / "core"
    core.mkdir(parents=True)
    (root / "engram.cmd").write_text(ENGRAM_CMD.read_text(encoding="utf-8"), encoding="utf-8")
    (core / "version.json").write_text('{"version": "9.9.9"}', encoding="utf-8")
    (core / "dispatch.bat").write_text("@echo off\r\necho DISPATCH=%*\r\nexit /b 0\r\n", encoding="utf-8")
    shutil.copytree(HELP_DIR, core / "help")
    shutil.copy(SYS_DIR / "core" / "cli_help.py", core / "cli_help.py")
    py = root / "_sys" / "env" / "python"
    py.mkdir(parents=True)
    shutil.copy(sys.executable, py / "python.exe")
    state = root / "_sys" / "data" / "state"
    state.mkdir(parents=True)
    (state / "layout.json").write_text('{"layout_version": 2}', encoding="utf-8")
    return root


def _engram(root, *args):
    line = " ".join(args)
    return subprocess.run(f'cmd.exe /c ""{root / "engram.cmd"}" {line}"', cwd=str(root), capture_output=True,
                          text=True, encoding="mbcs", errors="replace", timeout=60)


@pytest.mark.parametrize("verb", VERBS)
def test_help_verb_equals_verb_help_file(cmd_root, verb):
    proc = _engram(cmd_root, "help", verb)
    assert proc.returncode == 0
    assert proc.stdout.replace("\r\n", "\n") == _text(verb)


def test_help_unknown_topic_suggests_and_exits_2(cmd_root):
    proc = _engram(cmd_root, "help", "tidyy")
    assert proc.returncode == 2
    assert "Unknown command: tidyy" in proc.stdout and "Did you mean 'tidy'?" in proc.stdout
    assert "Run 'engram help'" in proc.stdout


def test_unknown_command_suggests_near_match(cmd_root):
    proc = _engram(cmd_root, "snapshot")
    assert proc.returncode == 2
    assert "Unknown command: snapshot" in proc.stdout and "Did you mean 'snapshots'?" in proc.stdout


def test_help_index_has_banner_and_all_verbs(cmd_root):
    proc = _engram(cmd_root, "help")
    assert proc.returncode == 0 and "Engram 9.9.9" in proc.stdout
    for verb in VERBS:
        assert f"engram {verb}" in proc.stdout


def test_unknown_menu_subcommand_suggests(cmd_root):
    proc = _engram(cmd_root, "menu", "enabel")
    assert proc.returncode == 2 and "Did you mean 'enable'?" in proc.stdout


# ---- --dry-run is a harmless no-op alias that always wins -------------------------------------------------

def test_reset_dry_run_wins_over_apply(tmp_path, capsys):
    from checks.backup_personal_data import run_reset
    base = tmp_path / "base"
    (base / ".engram" / "claude").mkdir(parents=True)
    (base / ".engram" / "claude" / "CLAUDE.md").write_text("x", encoding="utf-8")
    run_reset({"base_dir": base, "sys_dir": base / "_sys", "args": ["--apply", "--yes", "--dry-run"]})
    assert (base / ".engram" / "claude" / "CLAUDE.md").exists()
    assert "DRY-RUN" in capsys.readouterr().out


def test_reset_dry_run_alone_is_accepted(tmp_path, capsys):
    from checks.backup_personal_data import run_reset
    base = tmp_path / "base"
    (base / ".engram").mkdir(parents=True)
    run_reset({"base_dir": base, "sys_dir": base / "_sys", "args": ["--dry-run"]})
    assert (base / ".engram").exists()


def test_snapshots_restore_dry_run_wins_over_apply(tmp_path, capsys):
    from core import backups
    sys_dir = tmp_path / "Engram" / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    src = tmp_path / "src" / "state-x"
    src.mkdir(parents=True)
    (src / "f.txt").write_text("data", encoding="utf-8")
    ref = backups.create(sys_dir, "state", src, reason="t", op_id="op", label="x", now="2026-10-10T00:00:00Z")
    backups.commit(ref, now="2026-10-10T00:00:00Z")
    res = backups.snapshots_main({"base_dir": sys_dir.parent, "sys_dir": sys_dir, "command": "snapshots",
                                  "args": ["restore", ref.path.name, "--apply", "--dry-run"]})
    assert res["status"] == "success" and not src.exists()
    assert "[dry-run]" in capsys.readouterr().out


def test_restore_dry_run_alias_is_accepted(tmp_path, capsys):
    from checks.backup_personal_data import run_restore
    base = tmp_path / "base"
    base.mkdir()
    # an invalid archive path fails AFTER argument parsing: exit 1 (invalid path), never exit 2 (usage)
    with pytest.raises(SystemExit) as exc:
        run_restore({"base_dir": base, "sys_dir": base / "_sys", "args": [str(tmp_path / "nope.zip"), "--dry-run"]})
    assert exc.value.code != 2


# ---- docs stay in sync with the help files -------------------------------------------------------------------

def test_cli_reference_embeds_every_help_file_verbatim():
    doc = (REPO / "docs" / "cli_reference.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    for verb in VERBS:
        assert _text(verb).rstrip("\n") in doc, f"docs/cli_reference.md is stale for 'engram {verb}'"
        assert f"#### engram {verb}" in doc


def test_readme_and_docs_index_link_the_cli_reference():
    assert "docs/cli_reference.md" in (REPO / "README.md").read_text(encoding="utf-8")
    assert "cli_reference.md" in (REPO / "docs" / "README.md").read_text(encoding="utf-8")
    assert "cli_reference.md" in (REPO / "docs" / "env_resilience_guide.md").read_text(encoding="utf-8")
    assert "cli_reference.md" in (REPO / "docs" / "user_lifecycle_guide.md").read_text(encoding="utf-8")


# ---- no Python needed for help; user text never executes ---------------------------------------------------

@pytest.mark.parametrize("verb", VERBS)
@pytest.mark.parametrize("form", ["--help", "-h", "/?", "help", "HELPVERB"])
def test_every_verb_help_works_without_python(cmd_root, verb, form):
    (cmd_root / "_sys" / "env" / "python" / "python.exe").unlink()
    (cmd_root / "_sys" / "core" / "dispatch.bat").unlink()
    proc = _engram(cmd_root, *(["help", verb] if form == "HELPVERB" else [verb, form]))
    assert proc.returncode == 0, (verb, form, proc.stdout)
    assert proc.stdout.replace("\r\n", "\n") == _text(verb), (verb, form)


@pytest.mark.parametrize("payload", [
    "a&canary", "a|canary", "a>canary_out", "a<canary", "a^&canary", "a%PATH%b", "a!b!c", "x&&canary",
    "a'&canary", "(a)&canary", "a&echo", "a;canary", "a,canary",
])
@pytest.mark.parametrize("shape", ["help", "unknown", "menu"])
def test_user_text_is_never_executed(cmd_root, payload, shape):
    canary = cmd_root / "canary"
    (cmd_root / "canary.cmd").write_text(f'@echo off\r\necho x> "{canary}"\r\n', encoding="utf-8")
    quoted = f'"{payload}"'
    args = {"help": ["help", quoted], "unknown": [quoted], "menu": ["menu", quoted]}[shape]
    proc = _engram(cmd_root, *args)
    assert not canary.exists(), (payload, shape, proc.stdout)
    assert not (cmd_root / "canary_out").exists()
    assert proc.returncode == 2
    assert "[Error] Unknown" in proc.stdout
    if "%" not in payload and "!" not in payload:
        assert payload in proc.stdout, proc.stdout
