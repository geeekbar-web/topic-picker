"""Viral short-video topic pickers.

Each fetcher returns list[dict] with this shape:
    {
        "title":   str,         # 话题标题
        "url":     str,         # 原始链接
        "source":  str,         # 来源标签(中文)
        "heat":    float,       # 热度分(可能为 0)
        "time":    datetime|None,
        "summary": str,         # 摘要 / 上下文(后续生成脚本用)
    }
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Callable

import feedparser
import requests
from dateutil import parser as dateparser

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
TIMEOUT = 12

NEWSNOW_BASE = "https://newsnow.busiyi.world/api/s"
NEWSNOW_SOURCES = [
    ("weibo",  "微博热搜",   "全民级话题,流量大,易爆"),
    ("douyin", "抖音热点",   "短视频爆款本身,天然适合做内容"),
    ("zhihu",  "知乎热榜",   "有深度讨论,有热度数字,适合做「为什么」类内容"),
    ("baidu",  "百度热搜",   "生活/民生/小技巧最多"),
    ("tieba",  "百度贴吧",   "年轻人/二次元/游戏圈话题"),
    ("bilibili", "B站热门", "视频化社区,内容感强"),
]


def _newsnow(sid: str) -> list[dict]:
    try:
        r = requests.get(
            f"{NEWSNOW_BASE}?id={sid}",
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        print(f"  [newsnow] {sid} HTTP {r.status_code} len={len(r.text)}", flush=True)
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception as e:
        print(f"  [newsnow] {sid} EXC: {type(e).__name__}: {e}", flush=True)
        return []
    items = data.get("items") or []
    print(f"  [newsnow] {sid} got {len(items)} items", flush=True)
    result: list[dict] = []
    for i, it in enumerate(items):
        title = (it.get("title") or "").strip()
        url = it.get("url") or it.get("mobileUrl") or ""
        if not title or not url:
            continue
        heat = 0.0
        extra = it.get("extra") or {}
        if isinstance(extra, dict):
            info = str(extra.get("info", ""))
            m = re.search(r"([\d.]+)\s*万", info)
            if m:
                heat = float(m.group(1)) * 10000.0
        rank_heat = max(1.0, 100.0 - i * 3.0)
        heat = heat or rank_heat
        result.append({
            "title":   title,
            "url":     url,
            "source":  next((lbl for s, lbl, _ in NEWSNOW_SOURCES if s == sid), sid),
            "heat":    heat,
            "time":    None,
            "summary": (extra.get("hover") or "").strip() if isinstance(extra, dict) else "",
        })
    return result



def fetch_weibo()    -> list[dict]: return _newsnow("weibo")
def fetch_douyin()   -> list[dict]: return _newsnow("douyin")
def fetch_zhihu()    -> list[dict]: return _newsnow("zhihu")
def fetch_baidu()    -> list[dict]: return _newsnow("baidu")
def fetch_tieba()    -> list[dict]: return _newsnow("tieba")
def fetch_bilibili() -> list[dict]: return _newsnow("bilibili")


def fetch_producthunt() -> list[dict]:
    try:
        r = requests.get(
            "https://www.producthunt.com/",
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            print(f"[producthunt] HTTP {r.status_code}")
            return []
        html = r.text
    except Exception as e:
        print(f"[producthunt] {e}")
        return []
    items: list[dict] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'<a[^>]+href="(/posts/[a-z0-9\-]+)"[^>]*>([^<]{3,80})</a>',
        re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        slug, name = m.group(1), m.group(2).strip()
        if slug in seen or len(name) < 3:
            continue
        seen.add(slug)
        items.append({
            "title":   f"{name} — Product Hunt 今日新品",
            "url":     "https://www.producthunt.com" + slug,
            "source":  "Product Hunt",
            "heat":    80.0 - len(items) * 2.0,
            "time":    datetime.utcnow(),
            "summary": "今日 PH 首页新品,适合做「海外新工具盘点」内容",
        })
        if len(items) >= 12:
            break
    return items


def fetch_xiaohongshu() -> list[dict]:
    try:
        r = requests.get(
            f"{NEWSNOW_BASE}?id=xiaohongshu",
            headers={"User-Agent": UA, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception:
        return []
    items: list[dict] = []
    for i, it in enumerate(data.get("items") or []):
        title = (it.get("title") or "").strip()
        url = it.get("url") or it.get("mobileUrl") or ""
        if not title or not url:
            continue
        items.append({
            "title":   title,
            "url":     url,
            "source":  "小红书热帖",
            "heat":    max(1.0, 100.0 - i * 3.0),
            "time":    None,
            "summary": (it.get("extra") or {}).get("hover", "") if isinstance(it.get("extra"), dict) else "",
        })
    return items


def fetch_github_trending() -> list[dict]:
    from selectolax.parser import HTMLParser
    try:
        r = requests.get(
            "https://github.com/trending?since=daily",
            headers={"User-Agent": UA},
            timeout=TIMEOUT,
        )
    except Exception as e:
        print(f"[github] {e}")
        return []
    if r.status_code != 200:
        return []
    items: list[dict] = []
    tree = HTMLParser(r.text)
    for article in tree.css("article.Box-row"):
        a = article.css_first("h2 a")
        if not a:
            continue
        full_name = a.text(strip=True).replace(" ", "").replace("\n", "")
        href = a.attributes.get("href", "")
        desc_el = article.css_first("p.col-9")
        desc = desc_el.text(strip=True) if desc_el else ""
        title = f"{full_name} — {desc}" if desc else full_name
        items.append({
            "title":   title,
            "url":     "https://github.com" + href if href.startswith("/") else href,
            "source":  "GitHub 今日飙升",
            "heat":    50.0 - len(items) * 1.5,
            "time":    datetime.utcnow(),
            "summary": desc,
        })
        if len(items) >= 10:
            break
    return items


FETCHERS: dict[str, Callable[[], list[dict]]] = {
    "weibo":       fetch_weibo,
    "douyin":      fetch_douyin,
    "zhihu":       fetch_zhihu,
    "baidu":       fetch_baidu,
    "tieba":       fetch_tieba,
    "bilibili":    fetch_bilibili,
    "xiaohongshu": fetch_xiaohongshu,
    "producthunt": fetch_producthunt,
    "github":      fetch_github_trending,
}


if __name__ == "__&#8203;main__":
    for name, fn in FETCHERS.items():
        t0 = time.time()
        try:
            data = fn()
            sample = data[0]["title"][:40] if data else "(empty)"
            print(f"{name:12s}  {len(data):4d} items  ({time.time()-t0:.1f}s)  e.g. {sample}")
        except Exception as e:
            print(f"{name:12s}  ERROR: {e}")
