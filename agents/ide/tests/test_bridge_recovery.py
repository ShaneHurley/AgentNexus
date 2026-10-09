from ide_bridge.exit_codes import exit_code_from_dc_row


def test_uncertain_recovery_and_pending_cancellation_are_blocked():
    assert exit_code_from_dc_row({"status": "RECONCILIATION_REQUIRED"}) == 3
    assert exit_code_from_dc_row({"status": "CANCEL_REQUESTED"}) == 3


def test_approval_is_an_acknowledged_action():
    assert exit_code_from_dc_row({"kind": "plan", "decided": True, "state": "approved"}) == 0
    assert exit_code_from_dc_row({"kind": "plan", "decided": False, "state": "pending"}) == 3
