# B4.6 Shadow Brain V1 — scoped freeze review

Base: `b1-brain-architecture` at `027b8927586add52feb45feb01e0f6ef9aee41a3`.

Source export SHA-256:
`d3578c50c55f8ce5a2694febb25b7cc9cbdee8393223aa96cf4ea7f59ae73766`.

Decision: the journal R1 changes are ready for a scoped freeze after the maintained
Windows CI suite and Brain suite pass together and the four-file commit is created.
This is a baseline-relative regression review, not a fully passing repository.
No X-roadmap work or production wiring is included.

## What is frozen

- Existing V1 Shadow semantics, contracts, composer and persistence remain unchanged.
- The journal claims its immutable slot before publishing its result, then publishes
  the manifest last. A losing conflicting writer cannot leave another result record.
- Enumeration, replay and verification require the exact referenced record set.
  Missing/orphan records, unexpected directory entries, duplicate references and
  static symlink/junction artifacts fail closed.
- An interrupted capture fails verification. An exact retry can finish publication;
  a conflicting retry preserves existing artifacts and fails.
- No production module imports the journal in the supplied source. Package exports,
  providers, broker submission, PAPER policy and certification remain unchanged.

## Evidence

| Gate | Baseline | Patched |
| --- | ---: | ---: |
| Exported Brain suite on Linux | 653 passed | 692 passed |
| Broad offline run: passed | 17,668 | 17,707 |
| Broad offline run: failed | 674 | 674 |
| Broad offline run: collection errors | 148 | 148 |
| Maintained CI suite in source export | 310 passed, 9 failed | 310 passed, 9 failed |

Windows Brain verification reported **682 passed, 10 skipped**, exit 0. The ten
skips are WinError 1314 symlink-creation privilege cases; all ten passed on Linux.

Every existing broad-run test retained the same outcome. There were no removed
tests, no newly failing tests, and no newly failing collection modules. Exactly
39 added R1 cases passed. Normalized collection error details were identical.
Three failed-test text differences were timestamps or path-dependent truncation
in diagnostics; their failure reasons and outcomes did not change.

The broad run used `--continue-on-collection-errors`, so executable tests ran while
the 148 collection failures remained visible. Both source copies used the same
Linux/Python 3.12 environment, without broker credentials and with IPv4/IPv6 socket
creation blocked for the runner and its descendants. It was not an exact replica
of the Windows dependency lock or the full Windows working directory.

The pre-patch comparison includes the user's original untracked journal and original
test, restored from the verified pre-application backup. It is the pre-R1 working
candidate, not a claim that those untracked files existed in the base Git commit.

Full supplied-source syntax parsing passed. The journal implementation and new R1
tests passed the configured correctness/import lint checks.

## Baseline limitations remain open

The broad failures are not all production defects. They combine source-export and
environment limitations with existing compatibility problems:

- 556 failed tests reported missing files, including 434 references to Windows venv
  paths, plus omitted documents, runtime data, scripts and legacy entrypoints.
- 97 collection failures encountered the unavailable optional `ta` dependency in
  the comparison environment. Other missing dependencies/modules also remain.
- Legacy tests request absent APIs such as `PaperTradeExitReason`,
  `Task9LiveStreamCollectorLock`, and `calculate_indicators`.
- Some old modules request credentials, network data or interactive stdin during
  collection. The offline review did not supply credentials or permit networking.
- The nine maintained-CI failures were confined to scheduled-task tests reading
  `tools/start_supervisor_if_fresh.ps1` and `tools/install_supervisor_task.ps1`.
  The export command omitted `.ps1` files. The final local gate copies those exact
  tracked files and requires all maintained-CI tests to pass; it does not exclude them.

These findings are recorded for separate repository maintenance. They must not be
represented as a green full-repository suite, repaired live trading logic, or PAPER
certification. Resolving them by broad runtime changes is outside this four-file
zero-authority journal freeze.

## Operational limits

Readers may fail closed during active multi-file publication; retry after writers
quiesce. Old orphan or temporary artifacts remain visible for explicit recovery;
they are not silently deleted or adopted. This patch does not promise a multi-file
atomic transaction, arbitrary power-loss durability, or protection from a hostile
process rewriting filesystem paths concurrently.

## Freeze scope

Only these four files belong in the freeze commit:

1. `services/brain/shadow_result_journal_v1.py`
2. `tests/test_brain_shadow_result_journal_v1.py`
3. `tests/test_brain_shadow_result_journal_r1.py`
4. `docs/brain/B4_6_JOURNAL_R1_REVIEW.md`

The local finalizer runs source syntax checks and the 32 maintained-CI plus 16 Brain
test modules in a temporary source copy, checks the test count and allowed skips,
rechecks the original worktree, updates this record and commits only these files.
The final Git hash is printed after commit. No push, campaign stop/restart, broker
action, certification update or X1 work is performed.

## Local freeze gate

All 32 maintained CI modules plus 16 Brain modules: **1001 passed, 10 skipped**. Syntax check passed. Skips, if present, are only the ten WinError 1314 symlink-capability cases already passed on Linux.

This document becomes the scoped freeze record when committed with the three journal implementation/test files. Full-repository baseline debt remains open. X1 has not started.
