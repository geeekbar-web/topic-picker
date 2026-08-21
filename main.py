"""Daily 1-min short-video topic picker.

Usage:
    python3.11 main.py                          # generate today's viral topic pack
    GROQ_API_KEY=gsk_xxx python3.11 main.py     # enable AI-enhanced scripts
    python3.11 main.py --top 30 --no-ai         # more topics, no AI

Writes to /workspace/output/YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sources import FETCHERS
from dedup_score import dedupe, score, write_report


def fetch_all(enabled: list[str] | None = None) -> tuple[list[dict], dict[str, str]]:
    enabled = enabled or list(FETCHERS.keys())
    items: list[dict] = []
    errors: dict[str, str] = {}
    for name, fn in FETCHERS.items():
        if name not in enabled:
            continue
        t0 = time.time()
        try:
            got = fn() or []
            print(f"[fetch] {name:12s}  +{len(got):4d}  ({time.time()-t0:.1f}s)")
            items.extend(got)
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            print(f"[fetch] {name:12s}  ERROR  {msg}")
            errors[name] = msg
    return items, errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Daily 1-min short-video topic picker")
    p.add_argument("date", nargs="?", default=None,
                   help="Report date (YYYY-MM-DD); defaults to today UTC")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--no-ai", action="store_true",
                   help="Skip AI enhancement even if GROQ_API_KEY is set")
    p.add_argument("--sources", default=None,
                   help="Comma-separated source names to enable (default: all)")
    p.add_argument("--out", default="/workspace/output")
    args = p.parse_args(argv)

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"=== 1-min Short-Video Topic Picker · {date} ===")
    enabled = args.sources.split(",") if args.sources else None
    raw, errors = fetch_all(enabled)
    if not raw:
        print("No items fetched from any source. Aborting.")
        return 1

    merged = dedupe(raw)
    print(f"[dedup] {len(raw)} raw  ->  {len(merged)} unique")

    ranked = score(merged)
    top = ranked[: args.top]
    print(f"[score] kept top {len(top)} of {len(ranked)}")

    use_ai = (not args.no_ai) and bool(os.environ.get("GROQ_API_KEY"))
    print(f"[ai]    {'enabled (Groq)' if use_ai else 'disabled (rule-based)'}")

    out_path = write_report(top, out_dir=args.out, date=date, use_ai=use_ai)
    print(f"[done]  -> {out_path}")

    # 如果 SMTP 配了,自动发邮件
    if os.environ.get("SMTP_HOST"):
        from emailer import send_report
        send_report(out_path)

    if errors:
        print(f"[warn]  {len(errors)} source(s) failed: {', '.join(errors)}")
    return 0


if __name__ == "__&#8203;main__":
    sys.exit(main())
