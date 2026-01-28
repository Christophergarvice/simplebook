#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

from ingest.qfx.qfx_ingest import ingest_qfx
from ledger.sqlite_store import SQLiteStore
from reports.basic_summary import summarize
from modules.module3_checks import detect_checks, print_check_debug_sample

DEBUG = os.getenv("SB_DEBUG") == "1"
DB_PATH = "data/simplebook.db"


def cmd_import(args: list[str]) -> None:
    if len(args) != 1:
        print("Usage: sb import <qfx_file>")
        sys.exit(1)

    qfx_path = args[0]

    store = SQLiteStore(DB_PATH)
    store.init_db()

    txs = ingest_qfx(qfx_path)
    inserted = store.upsert_transactions(txs)

    print(f"Imported: {len(txs)}")
    print(f"Inserted (new): {inserted}")
    print(f"DB total: {store.count_transactions()}")


def cmd_months(args: list[str]) -> None:
    limit = 60
    if len(args) == 1:
        try:
            limit = int(args[0])
        except ValueError:
            print("Usage: sb months [limit]")
            sys.exit(1)
    elif len(args) > 1:
        print("Usage: sb months [limit]")
        sys.exit(1)

    store = SQLiteStore(DB_PATH)
    store.init_db()

    months = store.list_months()
    if not months:
        print("No transactions found in DB.")
        return

    print("\nMonths in DB (newest first):")
    for ym, c in months[:limit]:
        print(f"{ym}  ({c})")


def cmd_report(args: list[str]) -> None:
    if len(args) != 1 or "-" not in args[0]:
        print("Usage: sb report YYYY-MM")
        sys.exit(1)

    year_s, month_s = args[0].split("-", 1)
    year = int(year_s)
    month = int(month_s)

    store = SQLiteStore(DB_PATH)
    store.init_db()

    txs = store.list_by_month(year, month, limit=10000)

    # Module 3: check detection + optional debug dump
    checks = detect_checks(txs)
    if DEBUG:
        print_check_debug_sample(checks)

    s = summarize(txs)

    print(f"\nMonth: {year}-{month:02d}")
    print("Count  :", s.count)
    print("Credits:", s.credits_count, "Total:", s.credits_total)
    print("Debits :", s.debits_count, "Total:", s.debits_total)
    print("Net    :", s.net_total)

    print("\nTop spend breakdown: (disabled for now)")

    # --- Needs Review (v0.1) ---
    needs_review: list[tuple[object, str]] = []
    for t in txs:
        amt = abs(float(t.amount or 0))
        name_u = (t.name or "").upper().strip()
        memo_s = (t.memo or "").strip()

        if amt >= 500 and not memo_s:
            needs_review.append((t, "large amount, missing memo"))
            continue

        if not name_u or name_u in {"POS", "ONLINE", "PAYMENT"}:
            needs_review.append((t, "generic or missing name"))
            continue

    if needs_review:
        print("\nNeeds Review:")
        for t, reason in needs_review[:15]:
            print(f"  {t.posted_date}  {t.amount:10.2f}  {t.name}  ({reason})")
    else:
        print("\nNeeds Review: none")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: sb <command> [args]")
        print("Commands: import, months, report")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "import":
        cmd_import(args)
    elif command == "months":
        cmd_months(args)
    elif command == "report":
        cmd_report(args)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()


