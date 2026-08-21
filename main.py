"""Daily 1-min short-video topic picker — bulletproof version."""
from __future__ import annotations

import sys
import os
import time
from datetime import datetime, timezone

print("[boot] start", flush=True)

# try 1: import everything we need
try:
    from pathlib import Path
    from sources import FETCHERS
    from dedup_score import dedupe, score, write_report
    print("[boot] imports ok", flush=True)
except Exception as e:
    print(f"[boot] IMPORT FAILED: {type(e).__name__}: {e}", flush=True)
    # write a minimal report so workflow doesn't hang
    try:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        Path("output").mkdir(parents=True, exist_ok=True)
        Path("output") / f"{date}.md"
        Path("output", f"{date}.md").write_text(
            f"# 选题包 · {date}\n\n"
            f"Import error: {type(e).__name__}: {e}\n",
            encoding="utf-8",
        )
        print(f"[boot] wrote fallback: output/{date}.md", flush=True)
    except Exception as ee:
        print(f"[boot] fallback write failed: {ee}", flush=True)
    sys.exit(0)


def fetch_all(enabled=None):
    enabled = enabled or list(FETCHERS.keys())
    items = []
    errors = {}
    for name, fn in FETCHERS.items():
        if name not in enabled:
            continue
        t0 = time.time()
        try:
            got = fn() or []
            print(f"[fetch] {name:12s}  +{len(got):4d}  ({time.time()-t0:.1f}s)", flush=True)
            items.extend(got)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            print(f"[fetch] {name:12s}  ERROR  {msg}", flush=True)
            errors[name] = msg
    return items, errors


def main():
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"=== {date} ===", flush=True)
    print(f"[cwd] {os.getcwd()}", flush=True)

    Path("output").mkdir(parents=True, exist_ok=True)

    raw, errors = fetch_all()
    print(f"[raw] {len(raw)} items, {len(errors)} errors", flush=True)

    # ALWAYS write a file — never silently produce nothing
    out = Path("output") / f"{date}.md"
    try:
        if raw:
            merged = dedupe(raw)
            ranked = score(merged)
            top = ranked[:20]
            out_path = write_report(top, out_dir="output", date=date)
            print(f"[done] -> {out_path}", flush=True)
        else:
            out.write_text(
                f"# 选题包 · {date}\n\n"
                f"> 全部数据源抓取失败。\n\n"
                f"失败源: {', '.join(errors.keys()) or '未知'}\n",
                encoding="utf-8",
            )
            print(f"[done] -> {out} (empty fallback)", flush=True)
    except Exception as e:
        print(f"[done] write_report failed: {e}", flush=True)
        # last-ditch: write a minimal file
        out.write_text(
            f"# 选题包 · {date}\n\nError: {e}\n",
            encoding="utf-8",
        )
        print(f"[done] wrote error fallback: {out}", flush=True)

    return 0


if __name__ == "__&#8203;main__":
    sys.exit(main())
