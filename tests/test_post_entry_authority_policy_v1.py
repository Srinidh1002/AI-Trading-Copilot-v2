import pytest
from services.contracts.post_entry_authority_policy_v1 import PostEntryAuthorityPolicyV1
def test_entry_brain_cannot_become_exit_authority():
 assert PostEntryAuthorityPolicyV1().exit_authority=="PAPER_LIFECYCLE_EVALUATOR"
 with pytest.raises(ValueError): PostEntryAuthorityPolicyV1(entry_brain_may_mutate_position=True)
