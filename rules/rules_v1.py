from __future__ import annotations
from config.defaults import ASSUME_ALL_INCOME_IS_RENTAL, VENDOR_RULES
from dataclasses import dataclass
import html


@dataclass
class RuleResult:
    category: str | None = None
    confidence: str = "guess"   # "hard" or "guess"
    note: str | None = None


def _clean(s: str | None) -> str:
    # Handles AT&amp;T -> AT&T, etc.
    return html.unescape(s or "").strip()


def classify_tx(t) -> RuleResult:
    """
    Lightweight rule-based classifier for SimpleBook v0.1.
    t is a Transaction object (your models/transaction.py).
    """
    name = _clean(getattr(t, "name", "")).upper()
    memo = _clean(getattr(t, "memo", ""))
    amt = float(getattr(t, "amount", 0) or 0)

    # --- INCOME (config-driven)
    if amt > 0 and ASSUME_ALL_INCOME_IS_RENTAL:
        return RuleResult(category="Rental Income", confidence="guess")

    # --- EXPENSES / TRANSFERS
    # Credit card payments
    if "AMERICAN EXPRESS" in name or "AMEX" in name:
        return RuleResult(category="Credit Card Payment", confidence="hard")
    if "CITI" in name or "CITIBANK" in name:
        return RuleResult(category="Credit Card Payment", confidence="hard")

    # Phone
    if "AT&T" in name or "ATT" in name:
        return RuleResult(category="Phone Expense", confidence="hard")

    # Home Depot (you said it was a CC payment in your flow)
    if "HOME DEPOT" in name:
        return RuleResult(category="Credit Card Payment", confidence="guess", note="verify if this is always CC payment")

    # Transfers to/from Cash App: your mapping
    if "CASH APP" in name and ("TRANSFER TO" in name or "TRANSFER" in name):
        return RuleResult(category="Personal Transfer", confidence="guess")

    # Meta Pay: you treated as rental income if positive; if negative, treat as personal unless we learn otherwise
    if "META PAY" in name:
        return RuleResult(category="Personal Transfer", confidence="guess")

    # Transfers to #### (like Transfer To 8694)
    if "TRANSFER TO" in name:
        return RuleResult(category="Personal Transfer", confidence="guess")

    # Checks with unknown payee
    if "CHECK #" in name or (getattr(t, "checknum", None) is not None):
        return RuleResult(category=None, confidence="guess", note="unknown check payee")

    # Default: unknown
    return RuleResult(category=None, confidence="guess")

