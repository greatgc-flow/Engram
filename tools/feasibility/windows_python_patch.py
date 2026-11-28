"""Prove a Windows patch transaction and exact pin with two real publisher archives."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SYSTEM = Path(__file__).resolve().parents[2] / "_sys"
sys.path.insert(0, str(SYSTEM))
from core import env_manifest, python_cli, python_install, python_provider, python_registry, repair, updater  # noqa: E402
from core.python_artifact import Artifact  # noqa: E402


def version(exe):
    return subprocess.check_output([exe, "-I", "-B", "--version"], text=True, timeout=30).strip()


def main(cache):
    if sys.platform != "win32":
        raise RuntimeError("The patch proof requires Windows.")
    artifact = Artifact(**json.loads(Path(__file__).with_name("windows-python-patch.lock.json").read_bytes()))
    series = "3.14"
    with tempfile.TemporaryDirectory(prefix="engram-patch-") as tmp:
        base = Path(tmp)
        root = base / "system"
        project = base / "project 한글"
        (project / ".git").mkdir(parents=True)
        os.environ["ENGRAM_CALLER_CWD"] = str(project)
        env_manifest.write_manifest(root, {"schema_version": 1, "install_id": "wp3-patch-fixture",
                                            "root": {"physical": tmp, "logical": tmp}})

        def cli(*args):
            result = python_cli.run({"sys_dir": root, "args": [*args, "--json"]})
            if result["exit_code"]:
                raise RuntimeError(f"{args[0]} failed: {result}")
            return result

        initial = python_registry.new_document(root)
        # Seed the old release only in this disposable fixture using the real verifier and apply.
        baseline = python_install.InstallPlan(initial, [{"series": series, "status": "READY"}],
                                              [(series, artifact, cache / python_provider.asset_name(artifact))],
                                              offline=True)
        assert python_install.apply(root, baseline)["revision"] == 1
        old_path = Path(cli("where", series)["executable"])
        assert version(old_path) == "Python " + artifact.version
        pin = cli("pin", series)
        pin_before = Path(pin["pin"]).read_bytes()

        before = python_registry.registry_path(root).read_bytes()
        preview = cli("update", "--check", "--offline", "--cache-dir", str(cache))
        assert preview["plan"][0]["installed"] == artifact.version
        assert preview["plan"][0]["status"] == "READY"
        assert python_registry.registry_path(root).read_bytes() == before

        destination_cache = root / "data/setup-files/python-archives"
        destination_cache.mkdir(parents=True)
        shutil.copyfile(cache / preview["plan"][0]["asset"], destination_cache / preview["plan"][0]["asset"])

        def scoped_update(*flags):
            return updater.run({"sys_dir": root, "base_dir": base, "command": "update",
                                "args": ["--only", "python-versions", "--offline", "--json", *flags]})

        assert scoped_update()["plan"] == preview["plan"]
        assert python_registry.registry_path(root).read_bytes() == before
        updated = scoped_update("--yes")
        assert updated["revision"] == 2 and updated["plan"][0]["status"] == "UPDATED"
        new_version = updated["plan"][0]["version"]
        assert Path(pin["pin"]).read_bytes() == pin_before
        assert Path(cli("where", series)["executable"]).samefile(old_path)
        assert version(old_path) == "Python " + artifact.version
        cli("unpin")
        new_path = Path(cli("where", series)["executable"])
        assert not new_path.samefile(old_path) and version(new_path) == "Python " + new_version
        assert cli("update", "--offline", "--cache-dir", str(cache), "--yes")["revision"] == 2
        old_path.parent.rename(base / "held-previous-build")
        state = python_registry.registry_path(root).read_bytes()

        def repair_cli(*flags):
            return repair.repair_main({"sys_dir": root, "base_dir": base, "command": "repair",
                                       "args": ["--only", "python-versions", "--offline", "--json", *flags]})

        missing = repair_cli("--dry-run")
        assert missing["exit_code"] == 11 and "Missing offline archive" in missing["detail"]
        assert not old_path.parent.exists()
        name = python_provider.asset_name(artifact)
        shutil.copyfile(cache / name, destination_cache / name)
        preview_restore = repair_cli("--dry-run")
        assert preview_restore["exit_code"] == 0 and len(preview_restore["plan"]["steps"]) == 1
        assert not old_path.parent.exists()
        restored = repair_cli("--apply", "--yes")
        assert restored["exit_code"] == 0, restored
        assert version(old_path) == "Python " + artifact.version
        assert version(new_path) == "Python " + new_version
        assert python_registry.registry_path(root).read_bytes() == state
        print(json.dumps({"python_patch": "PASS", "old": artifact.version, "new": new_version,
                          "exact_pin_preserved": True, "old_executable_retained": True,
                          "offline_exact_restore": True, "unified_extra_scope": True, "revision": 2}))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
