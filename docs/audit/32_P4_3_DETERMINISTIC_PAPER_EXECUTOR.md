# P4-3 deterministic paper executor

Created `services/paper/executor.py` and the bounded in-memory idempotency
store. Public APIs are `execute_paper_order` and
`InMemoryPaperExecutionIdempotencyStore`. Gates are: type, time, authorization
status/flags/blockers, request validity, exact linkage/identity, then duplicate
lookup. Usable requests return `FILLED`; all authorization/identity/time gates
return `BLOCKED`; a claimed key returns `DUPLICATE`.

The implementation imports only P4 contracts and standard-library time/UUID.
It does not import legacy execution, brokers, providers, repositories,
databases, filesystems, or credentials. The store is per-instance in-memory and
keeps only bounded result identity/status. P4-3 is implemented but uncertified;
no order repository/state transitions or persistent exactly-once guarantee exist.

Manual commands:
```powershell
venv\Scripts\python.exe -m pytest tests/test_deterministic_paper_executor.py -q
venv\Scripts\python.exe -m pytest tests/test_paper_executor_idempotency.py -q
venv\Scripts\python.exe -m pytest tests/test_paper_executor_isolation.py -q
venv\Scripts\python.exe -c "from services.paper import execute_paper_order, InMemoryPaperExecutionIdempotencyStore; print('P4-3 imports passed')"
```
