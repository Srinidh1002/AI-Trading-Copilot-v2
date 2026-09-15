import pytest
from services.contracts.provider_capability_registry_v1 import default_provider_capability_registry

def test_only_proven_greeks_iv_are_marked_supported():
    registry=default_provider_capability_registry()
    assert registry.state("NIFTY","NSE","NFO","greeks")=="SUPPORTED"
    assert registry.state("SENSEX","BSE","BFO","greeks")=="UNSUPPORTED"
    assert registry.state("SENSEX","BSE","BFO","iv")=="UNSUPPORTED"
    assert registry.state("NIFTY","NSE","NFO","spot")=="SUPPORTED"

def test_registry_is_immutable_and_complete():
    registry=default_provider_capability_registry()
    with pytest.raises(TypeError): registry.capabilities[("NIFTY","NSE","NFO")]["spot"]="SUPPORTED"
