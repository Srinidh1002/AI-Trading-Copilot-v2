from services.certification.task8_live_candidate_adapter import adapt_task8_live_candidate


def test_strict_candidate_adapter_is_callable():
    assert callable(adapt_task8_live_candidate)
