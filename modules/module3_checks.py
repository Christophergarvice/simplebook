from __future__ import annotations
from typing import Iterable

def detect_checks(txs: Iterable[object]) -> list[object]:
    """
    Returns transactions that look like checks.
    """
    checks: list[object] = []
    for t in txs:
        t_type = ((getattr(t, "type", "") or "")).upper()
        name = ((getattr(t, "name", "") or "")).upper()
        checknum = getattr(t, "checknum", None)

        if checknum or (t_type == "CHECK") or ("CHECK" in name):
            checks.append(t)
    return checks


def print_check_debug_sample(checks: list[object]) -> None:
    """
    Prints debug info about checks. Safe if list is empty.
    """
    if not checks:
        return

    sample = checks[0]

    print(f"\nDetected checks: {len(checks)}")
    print("\nSample check transaction raw:")
    print("name:", getattr(sample, "name", None))
    print("memo:", getattr(sample, "memo", None))
    print("type:", getattr(sample, "type", None))
    print("checknum:", getattr(sample, "checknum", None))

    raw = getattr(sample, "raw", None)
    if isinstance(raw, dict):
        print("raw keys:", list(raw.keys()))
        for k in [
            "checknum",
            "fitid",
            "trntype",
            "name",
            "memo",
            "posted_raw",
            "posted_date",
            "amount",
        ]:
            if k in raw:
                print(f"raw[{k}]:", raw[k])

