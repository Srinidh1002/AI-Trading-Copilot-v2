from services.observability import sanitize_audit_value
def test_redaction_preserves_status_and_input():
    value={"token":"secret","authorization_status":"ANALYSIS_ONLY","nested":[{"api_key":"x"}]}; result=sanitize_audit_value(value)
    assert result["token"] == "[REDACTED]" and result["authorization_status"] == "ANALYSIS_ONLY" and value["token"] == "secret"
def test_unknown_objects_do_not_invoke_string_conversion():
    class Unsafe:
        def __str__(self): raise AssertionError("must not run")
    assert sanitize_audit_value(Unsafe()) == "[UNSUPPORTED:Unsafe]"
