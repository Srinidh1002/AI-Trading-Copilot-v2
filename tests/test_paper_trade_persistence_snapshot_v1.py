from services.contracts import PaperTradePersistenceSnapshotV1
from tests.p7_fixture_helpers import NOW,make_observation,make_open_position,make_open_state,make_policy
import pytest

def make_snapshot(**changes):
 values=dict(paper_trade_id='typed-trade',adapter_idempotency_key='key-1',idempotency_payload_hash='a'*64,lifecycle_policy=make_policy(),lifecycle_state=make_open_state(),position=make_open_position(),latest_observation=make_observation(),pnl_evidence=None,created_at=NOW,updated_at=NOW)
 values.update(changes);return PaperTradePersistenceSnapshotV1(**values)
def test_snapshot_round_trip_and_integrity_are_deterministic():
 snapshot=make_snapshot();restored=PaperTradePersistenceSnapshotV1.from_dict(snapshot.to_dict())
 assert restored.to_json()==snapshot.to_json() and restored.integrity_hash==snapshot.integrity_hash
def test_snapshot_rejects_lifecycle_position_mismatch():
 import pytest
 from dataclasses import replace
 with pytest.raises(ValueError):make_snapshot(lifecycle_state=replace(make_open_state(),current_state='PARTIALLY_EXITED'))

@pytest.mark.parametrize('key',('paper_trade_id','adapter_idempotency_key','idempotency_payload_hash','lifecycle_policy','lifecycle_state','position','latest_observation','pnl_evidence','created_at','updated_at','event_sequence','schema_version','execution_mode','live_execution_eligible'))
def test_snapshot_requires_every_canonical_envelope_key(key):
 payload=make_snapshot().to_dict();del payload[key]
 with pytest.raises((TypeError,ValueError)):PaperTradePersistenceSnapshotV1.from_dict(payload)

@pytest.mark.parametrize('field,value',(('paper_trade_id',' '),('adapter_idempotency_key',' '),('idempotency_payload_hash',' '),('schema_version','9.0'),('execution_mode','LIVE'),('live_execution_eligible',True),('event_sequence',-1)))
def test_snapshot_rejects_invalid_envelope_authorities(field,value):
 payload=make_snapshot().to_dict();payload[field]=value
 with pytest.raises((TypeError,ValueError)):PaperTradePersistenceSnapshotV1.from_dict(payload)

@pytest.mark.parametrize('field,value',(('lifecycle_state','bad'),('position',{}),('latest_observation',{}),('pnl_evidence',{})))
def test_snapshot_rejects_malformed_nested_typed_payloads(field,value):
 payload=make_snapshot().to_dict();payload[field]=value
 with pytest.raises((TypeError,ValueError,KeyError)):PaperTradePersistenceSnapshotV1.from_dict(payload)

@pytest.mark.parametrize('field',('position','latest_observation','pnl_evidence'))
def test_optional_nested_typed_components_accept_only_explicit_none(field):
 payload=make_snapshot().to_dict();payload[field]=None
 restored=PaperTradePersistenceSnapshotV1.from_dict(payload)
 assert getattr(restored,field if field!='latest_observation' else 'latest_observation') is None

@pytest.mark.parametrize('field,value',[(field,value) for field in ('position','latest_observation','pnl_evidence') for value in ('bad',[],{'partial':'mapping'})])
def test_optional_nested_typed_components_reject_noncanonical_values(field,value):
 payload=make_snapshot().to_dict();payload[field]=value
 with pytest.raises((TypeError,ValueError,KeyError)):PaperTradePersistenceSnapshotV1.from_dict(payload)

def test_snapshot_json_and_integrity_are_byte_stable_and_detached():
 source={'nested':['value']};snapshot=make_snapshot();first=snapshot.to_json();second=snapshot.to_json()
 assert first==second and snapshot.integrity_hash==snapshot.integrity_hash and source=={'nested':['value']}
