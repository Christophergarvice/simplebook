from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def review_path_for_month(ym: str) -> Path:
    return Path("data") / f"review_{ym}.jsonl"


def make_review_id(t: Any) -> str:
    raw = getattr(t, "raw", None) or {}
    fitid = raw.get("fitid") or getattr(t, "fitid", None)
    if fitid:
        return str(fitid)

    posted = _safe_str(getattr(t, "posted_date", "")).strip()
    amt = _safe_str(getattr(t, "amount", "")).strip()
    name = _safe_str(getattr(t, "name", "")).strip()
    return f"{posted}|{amt}|{name}"


def load_review_items(ym: str) -> dict[str, dict[str, Any]]:
    path = review_path_for_month(ym)
    items: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return items

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        rid = str(obj.get("id", "")).strip()
        if rid:
            items[rid] = obj
    return items


def save_review_items(ym: str, items: dict[str, dict[str, Any]]) -> None:
    path = review_path_for_month(ym)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for rid in sorted(items.keys()):
        lines.append(json.dumps(items[rid], ensure_ascii=False))

    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def upsert_review_item(
    items: dict[str, dict[str, Any]],
    review_id: str,
    base: dict[str, Any],
) -> None:
    existing = items.get(review_id)
    if existing:
        keep = {
            "status": existing.get("status", "open"),
            "category": existing.get("category"),
            "vendor": existing.get("vendor"),
            "note": existing.get("note"),
        }
        existing.update(base)
        for k, v in keep.items():
            if v is not None:
                existing[k] = v
        if "status" not in existing:
            existing["status"] = "open"
    else:
        obj = dict(base)
        obj.setdefault("status", "open")
        items[review_id] = obj


def find_next_open(items: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for rid in sorted(items.keys()):
        if items[rid].get("status", "open") == "open":
            return items[rid]
    return None

