import io
import sys
from _sys.core.hub_error import HubError

def test_hub_error_remediation_peer_substitution(monkeypatch):
    """
    Test that the {peer} placeholder in remediation hints is properly 
    substituted with the actual peer name in the stderr output.
    """
    fake_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", fake_stderr)
    
    HubError._display(
        tier="T2",
        error_type="PEER_TIMEOUT",
        peer="cx",
        action="action_ask",
        message="timeout",
        stacktrace=None,
        whys=[]
    )
    
    output = fake_stderr.getvalue()
    
    # Verify that the placeholder was replaced
    assert "{peer}" not in output, "The {peer} placeholder was not substituted in the output!"
    # Verify the specific peer string is present in the remediation suggestion
    assert "hub.py health-check --peer cx" in output
    assert "hub.py ask --to cx" in output
