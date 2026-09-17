from services.paper_orchestration.complete_cycle_execution_context import CompleteCycleAuthoritySetV1
def noop(*args): return object()
def test_authority_set_accepts_callable_certified_boundaries():
    value=CompleteCycleAuthoritySetV1(data_authority=noop,session_authority=noop,analysis_authority=noop,opportunity_authority=noop,p6_input_factory=noop,new_entry_input_factory=noop)
    assert value.execution_mode=='PAPER' and value.live_execution_eligible is False
def test_authority_set_rejects_non_callable_dependency():
    try: CompleteCycleAuthoritySetV1(data_authority=object(),session_authority=noop,analysis_authority=noop,opportunity_authority=noop,p6_input_factory=noop,new_entry_input_factory=noop)
    except TypeError as exc: assert 'data_authority' in str(exc)
    else: raise AssertionError('expected TypeError')
