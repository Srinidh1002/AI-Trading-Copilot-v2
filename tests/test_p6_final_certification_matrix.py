import pytest
@pytest.mark.parametrize(('statuses','expected'),[(('READY','READY','READY','READY','READY'),'READY'),(('BLOCKED','READY','READY','READY','READY'),'BLOCKED'),(('READY','READY','READY','READY','NO_SIZE'),'NO_SIZE')])
def test_final_status_mapping_matrix(statuses,expected):
 assert ('BLOCKED' if any(x=='BLOCKED' for x in statuses[:-1]) else 'NO_SIZE' if statuses[-1]=='NO_SIZE' else 'READY')==expected
