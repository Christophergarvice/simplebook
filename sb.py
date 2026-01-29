#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

from ingest.qfx.qfx_ingest import ingest_qfx
from ledger.sqlite_store import SQLiteStore
from reports.basic_summary import summarize
from modules.module3_checks import detect_checks, print_check_debug_sample
from ledger.review_store import (
    load_review_items,
    save_review_items,
    upsert_review_item,
    find_next_open,
    make_review_id,
)

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
def _build_needs_review(txs: list[object]) -> list[tuple[object, str]]:
    needs: list[tuple[object, str]] = []
    for t in txs:
        amt = abs(float(getattr(t, "amount", 0) or 0))
        name = (getattr(t, "name", "") or "").strip()
        memo = (getattr(t, "memo", "") or "").strip()

        # v0.1 heuristic (aggressive)
        if amt >= 500 and not memo:
            needs.append((t, "large amount, missing memo"))
            continue

        if not name:
            needs.append((t, "missing name"))
            continue

    return needs


def cmd_review(args: list[str]) -> None:
    if len(args) != 1 or "-" not in args[0]:
        print("Usage: sb review YYYY-MM")
        sys.exit(1)

    ym = args[0]
    year_s, month_s = ym.split("-", 1)
    year = int(year_s)
    month = int(month_s)

    store = SQLiteStore(DB_PATH)
    store.init_db()
    txs = store.list_by_month(year, month, limit=100000)

    needs = _build_needs_review(txs)

    items = load_review_items(ym)

    added = 0
    for t, reason in needs:
        rid = make_review_id(t)
        base = {
            "id": rid,
            "ym": ym,
            "posted_date": getattr(t, "posted_date", None),
            "amount": float(getattr(t, "amount", 0) or 0),
            "name": getattr(t, "name", None),
            "memo": getattr(t, "memo", None),
            "reason": reason,
        }
        if rid not in items:
            added += 1
        upsert_review_item(items, rid, base)

    save_review_items(ym, items)

    open_count = sum(1 for v in items.values() if v.get("status", "open") == "open")
    resolved_count = sum(1 for v in items.values() if v.get("status") == "resolved")

    print(f"Review file updated: data/review_{ym}.jsonl")
    print(f"Found needs_review this run: {len(needs)} (new: {added})")
    print(f"Open: {open_count} | Resolved: {resolved_count}")
    print(f"Next: python3 sb.py review-next {ym}")


def cmd_review_next(args: list[str]) -> None:
    if len(args) != 1 or "-" not in args[0]:
        print("Usage: sb review-next YYYY-MM")
        sys.exit(1)

    ym = args[0]
    items = load_review_items(ym)
    nxt = find_next_open(items)
    if not nxt:
        print(f"No open review items for {ym}. 🎉")
        return

    print("\nNEXT REVIEW ITEM")
    print("ID        :", nxt.get("id"))
    print("Date      :", nxt.get("posted_date"))
    print("Amount    :", f'{nxt.get("amount", 0):.2f}')
    print("Name      :", nxt.get("name"))
    print("Memo      :", nxt.get("memo"))
    print("Reason    :", nxt.get("reason"))
    print("\nTo resolve it, run something like:")
    print(f'python3 sb.py review-set {ym} {nxt.get("id")} status=resolved category="Materials" vendor="Home Depot" note="lot 12 remodel"')


def cmd_review_set(args: list[str]) -> None:
    if len(args) < 3:
        print('Usage: sb review-set YYYY-MM <id> key=value [key=value ...]')
        sys.exit(1)

    ym = args[0]
    rid = args[1]
    kvs = args[2:]

    items = load_review_items(ym)
    obj = items.get(rid)
    if not obj:
        print(f"Review id not found: {rid}")
        print(f"Tip: run: python3 sb.py review {ym}")
        sys.exit(1)

    for kv in kvs:
        if "=" not in kv:
            print(f"Bad field (expected key=value): {kv}")
            sys.exit(1)
        k, v = kv.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        obj[k] = v

    items[rid] = obj
    save_review_items(ym, items)
    print(f"Updated {rid} in data/review_{ym}.jsonl")

if __name__ == "__main__":
    main()


