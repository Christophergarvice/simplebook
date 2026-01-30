# SimpleBook defaults (tweak later via CLI/UI)

ASSUME_ALL_INCOME_IS_RENTAL = True
REVIEW_AMOUNT_THRESHOLD = 500.0

# (needle, category, confidence, note)
VENDOR_RULES = [
    ("AMERICAN EXPRESS", "Credit Card Payment", "hard", None),
    ("AMEX",             "Credit Card Payment", "hard", None),
    ("CITI",             "Credit Card Payment", "hard", None),
    ("CITIBANK",         "Credit Card Payment", "hard", None),
    ("AT&T",             "Phone Expense",       "hard", None),
    ("HOME DEPOT",       "Credit Card Payment", "guess", "verify if always CC payment"),
    ("TRANSFER TO CASH APP",   "Personal Transfer", "guess", None),
    ("TRANSFER FROM CASH APP", "Rental Income",     "guess", None),
    ("TRANSFER TO",      "Personal Transfer",   "guess", None),
]

