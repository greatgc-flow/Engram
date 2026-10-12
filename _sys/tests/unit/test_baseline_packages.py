"""The baseline distributions, import names and restore requirements share one owner."""
from core import baseline_packages, provisioner, python_manager, repair, venv_manager, venv_repair


def test_all_five_consumers_import_the_same_baseline():
    for consumer in (provisioner, python_manager, repair, venv_manager, venv_repair):
        assert consumer.BASELINE_PACKAGES is baseline_packages.BASELINE_PACKAGES
    mapping = dict(baseline_packages.BASELINE_PACKAGES)
    assert mapping == {"filelock": "filelock", "psutil": "psutil",
                       "pydantic": "pydantic", "pywinpty": "winpty"}
    assert "winpty" not in mapping
    assert set(venv_manager.BASELINE_MODULES) == set(mapping.values())
    assert repair._BASELINE_PIP_NAMES == frozenset(mapping)


def test_restore_and_readiness_requirements_preserve_baseline_pins():
    snapshot = {"packages": [
        {"name": "psutil", "version": "7.0", "requested": True},
        {"name": "pydantic", "version": "2.12", "requested": True},
        {"name": "pydantic-core", "version": "2.40", "requested": False},
        {"name": "user-package", "version": "1.0", "requested": True},
    ]}
    plan = venv_repair.restore_packages_step_data(snapshot)
    specs = python_manager.baseline_install_specs(snapshot)
    assert set(specs) == {"filelock", "pywinpty", "psutil==7.0", "pydantic==2.12"}
    assert plan["t1"] == ["psutil==7.0", "pydantic==2.12"]
    assert plan["t2"] == ["user-package==1.0"]
    assert "pydantic-core==2.40" in plan["constraints_text"]
    assert "psutil" not in plan["constraints_text"]
