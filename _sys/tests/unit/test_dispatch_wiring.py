import json
from pathlib import Path

def test_actual_dispatch_wiring():
    """
    Verify the actual runtime delegation contract for installation/provisioning.
    Asserts reality, not a wished-for design:
    - dispatch.json routes 'install' to 'provision.deploy' (core.provisioner.deploy)
    - setup.py delegates to core.provisioner.deploy directly (legacy compat)
    """
    root_dir = Path(__file__).parent.parent.parent.parent
    sys_dir = root_dir / "_sys"
    
    # 1. Assert modern wiring (dispatcher.py -> dispatch.json -> core.provisioner.deploy)
    dispatch_file = sys_dir / "dispatch.json"
    assert dispatch_file.exists()
    dispatch_data = json.loads(dispatch_file.read_text(encoding="utf-8"))
    
    install_pipeline = dispatch_data["pipelines"]["install"]
    assert install_pipeline[0] == "provision.deploy", "install pipeline must start with provision.deploy"
    
    provision_op = dispatch_data["operations"]["provision.deploy"]
    assert provision_op["module"] == "core.provisioner", "provision.deploy must map to core.provisioner"
    assert provision_op["method"] == "deploy", "provision.deploy must call deploy method"

    # 2. Assert legacy wiring (setup.py -> core.provisioner.deploy)
    setup_file = sys_dir / "core" / "setup.py"
    assert setup_file.exists()
    setup_content = setup_file.read_text(encoding="utf-8")
    assert "from core.provisioner import deploy" in setup_content, "setup.py must import deploy from core.provisioner"
    assert "deploy(ctx)" in setup_content, "setup.py must call deploy(ctx)"
