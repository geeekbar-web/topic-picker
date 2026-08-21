"""Daily 1-min short-video topic picker.

Usage:
    python3.11 main.py                          # generate today's viral topic pack
    GROQ_API_KEY=gsk_xxx python3.11 main.py     # enable AI-enhanced scripts
    python3.11 main.py --top 30 --no-ai         # more topics, no AI
"""
from __future__ import annotations

# ---- debug: 抓 import 错误,确保 GitHub Actions 能看到真实问题 ----
import sys, traceback
try:
    import argparse, os, time
    from datetime import datetime, timezone
    from pathlib import Path
    from sources import FETCHERS
    from dedup_score import dedupe, score, write_report
except Exception:
    print("=" * 50, flush=True)
    print("IMPORT ERROR:", flush=True)
    traceback.print_exc()
    print("=" * 50, flush=True)
    sys.exit(99)


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


def main(argv=None):
    p = argparse.ArgumentParser(description="Daily 1-min short-video topic picker")
    p.add_argument("date", nargs="?", default=None,
                   help="Report date (YYYY-MM-DD); defaults to today UTC")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--no-ai", action="store_true",
                   help="Skip AI enhancement even if GROQ_API_KEY is set")
    p.add_argument("--sources", default=None,
                   help="Comma-separated source names to enable (default: all)")
    p.add_argument("--out", default="output")
    args = p.parse_args(argv)

    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"=== 1-min Short-Video Topic Picker · {date} ===", flush=True)
    print(f"[cwd]   {os.getcwd()}", flush=True)
    enabled = args.sources.split(",") if args.sources else None
    raw, errors = fetch_all(enabled)

    if not raw:
        # 兜底:就算全失败也生成空报告,让 workflow 不至于静默失败
        print("[warn]  no items fetched — writing empty report", flush=True)
        Path(args.out).mkdir(parents=True, exist_ok=True)
        out = Path(args.out) / f"{date}.md"
        out.write_text(
            f"# 🔥 1 分钟短视频选题包 · {date}\n\n"
            f"> 今日数据源抓取失败,将在明天自动重试。\n\n"
            f"_失败源: {', '.join(errors.keys()) or '全部'}_\n",
            encoding="utf-8",
        )
        print(f"[done]  -> {out}  (empty fallback)", flush=True)
        return 0

    merged = dedupe(raw)
    print(f"[dedup] {len(raw)} raw  ->  {len(merged)} unique", flush=True)

    ranked = score(merged)
    top = ranked[: args.top]
    print(f"[score] kept top {len(top)} of {len(ranked)}", flush=True)

    use_ai = (not args.no_ai) and bool(os.environ.get("GROQ_API_KEY"))
    print(f"[ai]    {'enabled (Groq)' if use_ai else 'disabled (rule-based)'}", flush=True)

    out_path = write_report(top, out_dir=args.out, date=date, use_ai=use_ai)
    print(f"[done]  -> {out_path}", flush=True)

    if os.environ.get("SMTP_HOST"):
        try:
            from emailer import send_report
            send_report(out_path)
        except Exception as e:
            print(f"[email] error: {e}", flush=True)

    if errors:
        print(f"[warn]  {len(errors)} source(s) failed: {', '.join(errors)}", flush=True)
    return 0


if __name__ == "__&#8203;main__":
    sys.exit(main())
