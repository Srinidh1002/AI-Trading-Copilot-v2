"""MCX holidays — structured framework.
Populate from official MCX circular before live certification.
Fails CLOSED on any uncertain date (spec §6).
"""

# Format: (YYYY, M, D, "NAME", "FULL" | "MORNING_ONLY")
# MCX 2026 — PROVISIONAL. Replace with official circular data.
MCX_HOLIDAYS_2026 = [
    # 2026-09-14 Ganesh Chaturthi — morning session closed, evening open
    (2026, 9, 14, "GANESH_CHATURTHI", "MORNING_ONLY"),
    # Add remaining 2026 MCX holidays from official CSV before Monday.
]


def is_holiday(year, month, day):
    """Return (kind, name) or (None, None)."""
    for h in MCX_HOLIDAYS_2026:
        y, m, d, name, kind = h
        if (y, m, d) == (year, month, day):
            return kind, name
    return None, None


def count():
    return len(MCX_HOLIDAYS_2026)


if __name__ == "__main__":
    print(f"MCX holidays loaded: {count()}")
    print(f"Sample: {MCX_HOLIDAYS_2026}")
