#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

from ingest.qfx.qfx_ingest import ingest_qfx
from ledger.sqlite_store import SQLiteStore
from reports.basic_summary import summarize
from modules.module3_checks import detect_checks, print_check_debug_sample
from rules.rules_v1 import classify_tx
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

    # --- Needs Review (v0.3) --- (ignores memo)
    needs_review: list[tuple[object, str]] = []
    for t in txs:
        amt = abs(float(t.amount or 0))
        name_u = (t.name or "").upper().strip()

        is_large = amt >= 500
        is_generic = (not name_u) or (name_u in {"POS", "ONLINE", "PAYMENT"})
        is_transferish = "TRANSFER" in name_u
        is_checkish = ("CHECK" in name_u) or bool(getattr(t, "checknum", None))

        # Flag large items that are ambiguous / need human labeling
        if is_large and (is_generic or is_transferish or is_checkish):
            needs_review.append((t, "large + needs classification"))
            continue

        # Flag generic names even if not large
        if is_generic:
            needs_review.append((t, "generic or missing name"))
            continue

    if needs_review:
        print("\nNeeds Review:")
        for t, reason in needs_review[:15]:
            r = classify_tx(t)
            cat = r.category or "Uncategorized"
            note = f" | {r.note}" if r.note else ""
            print(f"  {t.posted_date}  {t.amount:10.2f}  {t.name}  [{cat}]{note}  ({reason})")
    else:
        print("\nNeeds Review: none")


def _parse_ym(args: list[str], usage: str) -> str:
    if len(args) != 1 or "-" not in args[0]:
        print(usage)
        sys.exit(1)
    return args[0]


def cmd_review(args: list[str]) -> None:
    ym = _parse_ym(args, "Usage: sb review YYYY-MM")
    year_s, month_s = ym.split("-", 1)
    year = int(year_s)
    month = int(month_s)

    store = SQLiteStore(DB_PATH)
    store.init_db()
    txs = store.list_by_month(year, month, limit=100000)

    items = load_review_items(ym)

    # Build/refresh review items based on current rules
    for t in txs:
        amt = abs(float(t.amount or 0))
        name_u = (t.name or "").upper().strip()
        memo_s = (t.memo or "").strip()

        reason = None
        if amt >= 500 and not memo_s:
            reason = "large amount, missing memo"
        elif not name_u or name_u in {"POS", "ONLINE", "PAYMENT"}:
            reason = "generic or missing name"

        if not reason:
            continue

        rid = make_review_id(t)
        base = {
            "id": rid,
            "ym": ym,
            "posted_date": t.posted_date,
            "amount": float(t.amount or 0),
            "name": t.name,
            "memo": t.memo,
            "reason": reason,
        }
        upsert_review_item(items, rid, base)

    save_review_items(ym, items)

    open_ct = sum(1 for v in items.values() if v.get("status", "open") == "open")
    resolved_ct = sum(1 for v in items.values() if v.get("status") == "resolved")

    print(f"[review] {ym} saved -> data/review_{ym}.jsonl")
    print(f"Open: {open_ct}  Resolved: {resolved_ct}  Total: {len(items)}")


def cmd_review_next(args: list[str]) -> None:
    ym = _parse_ym(args, "Usage: sb review-next YYYY-MM")

    items = load_review_items(ym)
    nxt = find_next_open(items)
    if not nxt:
        print(f"[review-next] {ym}: no open items 🎉")
        return

    rid = nxt["id"]
    print(f"[review-next] {ym}")
    print(f"ID     : {rid}")
    print(f"Date   : {nxt.get('posted_date')}")
    print(f"Amount : {nxt.get('amount')}")
    print(f"Name   : {nxt.get('name')}")
    memo = (nxt.get("memo") or "").strip()
    if memo:
        print(f"Memo   : {memo}")
    print(f"Reason : {nxt.get('reason')}")
    print("")
    print("Resolve example:")
    print(f'  python3 sb.py review-set {ym} "{rid}" status=resolved category="..." vendor="..." note="..."')


def cmd_review_set(args: list[str]) -> None:
    if len(args) < 2:
        print('Usage: sb review-set YYYY-MM "<id>" key=value [key=value ...]')
        sys.exit(1)

    ym = args[0]
    rid = args[1]
    kvs = args[2:]

    items = load_review_items(ym)
    if rid not in items:
        print(f"[review-set] ID not found: {rid}")
        sys.exit(1)

    for kv in kvs:
        if "=" not in kv:
            print(f"[review-set] bad field (expected key=value): {kv}")
            sys.exit(1)
        k, v = kv.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        items[rid][k] = v

    save_review_items(ym, items)
    print(f"[review-set] updated {rid}")


def cmd_review_status(args: list[str]) -> None:
    ym = _parse_ym(args, "Usage: sb review-status YYYY-MM")

    items = load_review_items(ym)
    if not items:
        print(f"[review-status] No review file found for {ym}. Run: python3 sb.py review {ym}")
        return

    total = len(items)
    resolved = [it for it in items.values() if it.get("status") == "resolved"]
    open_ = [it for it in items.values() if it.get("status", "open") == "open"]

    print(f"[review-status] {ym}")
    print(f"Open: {len(open_)}  Resolved: {len(resolved)}  Total: {total}")

    by_cat: dict[str, float] = {}
    by_vendor: dict[str, float] = {}

    for it in resolved:
        amt = float(it.get("amount") or 0.0)
        cat = (it.get("category") or "Uncategorized").strip()
        ven = (it.get("vendor") or "Unknown").strip()
        by_cat[cat] = by_cat.get(cat, 0.0) + amt
        by_vendor[ven] = by_vendor.get(ven, 0.0) + amt

    if resolved:
        print("\nResolved totals by category:")
        for cat, tot in sorted(by_cat.items(), key=lambda kv: abs(kv[1]), reverse=True):
            print(f"  {tot:10.2f}  {cat}")

        print("\nResolved totals by vendor:")
        for ven, tot in sorted(by_vendor.items(), key=lambda kv: abs(kv[1]), reverse=True):
            print(f"  {tot:10.2f}  {ven}")
    else:
        print("\nNo resolved items yet.")

    if open_:
        print("\nNext open items (preview):")

        def _key(it):
            return (it.get("posted_date") or "", -(abs(float(it.get("amount") or 0.0))))

        for it in sorted(open_, key=_key)[:10]:
            print(
                f"  {it.get('posted_date')}  {float(it.get('amount') or 0.0):10.2f}  {it.get('name')}  ({it.get('reason')})"
            )
    else:
        print("\nAll items resolved ✅")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: sb <command> [args]")
        print("Commands: import, months, report, review, review-next, review-set, review-status")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "import":
        cmd_import(args)
    elif command == "months":
        cmd_months(args)
    elif command == "report":
        cmd_report(args)
    elif command == "review":
        cmd_review(args)
    elif command == "review-next":
        cmd_review_next(args)
    elif command == "review-set":
        cmd_review_set(args)
    elif command == "review-status":
        cmd_review_status(args)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
