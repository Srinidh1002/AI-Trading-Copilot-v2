# Epoch naming vs. eligibility

`src/mcx/mcx_version.py` is the sole authority on whether a market's
trades count toward certification. The rule is:

    certification_eligible == True  -> counts toward /100
    certification_eligible == False -> observation only

Some products (GOLDM, NATGASMINI) carry an epoch *name* of
`*_PRECERT_V1` but were flipped to `certification_eligible=True` in
Phase 9.20. The name is historical; the flag is authoritative. Do not
rename the epoch — doing so would orphan the existing state files and
reset the counter.

If you ever want the name to match the flag, it must be done at the
start of a new epoch, with a deliberate counter reset and archival.
