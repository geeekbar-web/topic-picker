"""Normalize, dedupe, score, and render 1-minute short-video topic packs."""
from __future__ import annotations

import os
import re
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from dateutil import parser as dateparser

_PUNCT_RE = re.compile(r"[^\w\s\u4e00-\u9fff]+", re.UNICODE)
_WS_RE = re.compile(r"\s+")

_STOP = {
    "的", "了", "是", "在", "和", "与", "或", "也", "都", "就", "不", "没",
    "a", "the", "is", "are", "of", "to", "in", "for", "and", "or",
}

def normalize_title(t: str) -> str:
    if not t:
        return ""
    t = t.lower()
    t = _PUNCT_RE.sub(" ", t)
    tokens = [w for w in _WS_RE.split(t) if w and w not in _STOP and len(w) >= 2]
    return " ".join(tokens[:10])


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def dedupe(items: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for it in items:
        key = normalize_title(it.get("title", ""))
        if not key:
            continue
        if key not in groups:
            groups[key] = {
                "title":   it["title"].strip(),
                "url":     it.get("url", ""),
                "source":  it.get("source", ""),
                "sources": [it.get("source", "")],
                "heat":    float(it.get("heat", 0)),
                "time":    it.get("time"),
                "summary": (it.get("summary") or "").strip(),
                "domains": {domain_of(it.get("url", ""))},
            }
        else:
            g = groups[key]
            g["sources"].append(it.get("source", ""))
            g["domains"].add(domain_of(it.get("url", "")))
            g["heat"] = max(g["heat"], float(it.get("heat", 0)))
            new_sum = (it.get("summary") or "").strip()
            if len(new_sum) > len(g["summary"]):
                g["summary"] = new_sum
    return list(groups.values())


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


SIGNAL_TAGS = {
    "controversy":  ["起诉", "驳回", "违法", "违规", "抵制", "禁止", "封禁", "下架",
                     "道歉", "反驳", "质疑", "翻车", "造假", "骗局", "被骂", "打脸"],
    "money":        ["1元", "免费", "白嫖", "省钱", "便宜", "涨价", "降价", "月薪",
                     "工资", "补贴", "赔偿", "赔偿金", "上市", "融资", "估值"],
    "lifestyle":    ["午休", "睡觉", "美食", "旅行", "穿搭", "化妆", "瘦身", "减肥",
                     "家装", "收纳", "养猫", "养狗", "遛娃", "仪式感"],
    "tech_quirk":   ["AI", "机器人", "APP", "小程序", "代码", "开源", "工具", "神器",
                     "黑科技", "技巧", "一键", "自动"],
    "emotional":    ["崩溃", "哭了", "泪目", "心疼", "暖心", "治愈", "扎心", "破防",
                     "愤怒", "离谱", "炸了", "笑死", "尴尬", "窒息"],
    "social":       ["女生", "男生", "00后", "90后", "打工人", "职场", "老板", "同事",
                     "相亲", "恋爱", "分手", "结婚", "婆媳", "室友"],
}


def tag_topic(title: str) -> list[str]:
    tags = []
    for cat, words in SIGNAL_TAGS.items():
        if any(w in title for w in words):
            tags.append(cat)
    return tags or ["general"]


SOURCE_WEIGHT = {
    "微博热搜":   1.0,
    "抖音热点":   1.0,
    "知乎热榜":   0.9,
    "百度热搜":   0.85,
    "百度贴吧":   0.8,
    "B站热门":   0.8,
    "小红书热帖": 0.95,
    "GitHub 今日飙升": 0.7,
    "Product Hunt": 0.7,
}


def score(items: list[dict]) -> list[dict]:
    heats = _minmax([it["heat"] for it in items])
    for it, h in zip(items, heats):
        distinct = len(set(it["sources"]))
        cross = min(1.0, max(0, distinct - 1) / 2.0)
        sw = max((SOURCE_WEIGHT.get(s, 0.7) for s in it["sources"]), default=0.7)
        tags = tag_topic(it["title"])
        virality = 0.0
        if "controversy" in tags or "emotional" in tags: virality += 0.15
        if "money" in tags:        virality += 0.10
        if "lifestyle" in tags:    virality += 0.08
        if "tech_quirk" in tags:   virality += 0.05
        if "social" in tags:       virality += 0.05
        virality += 0.10 * cross
        raw = 0.55 * h + 0.20 * cross + 0.15 * (sw - 0.7) / 0.3 + 0.10 + virality
        raw = max(0.0, min(1.2, raw))
        it["score"] = round(raw * 100, 1)
        it["cross_sources"] = sorted(set(it["sources"]))
        it["tags"] = tags
    items.sort(key=lambda x: -x["score"])
    return items


HOOK_TEMPLATES = {
    "controversy": [
        "这件事,90% 的人都搞错了。",
        "全网都在骂,但我看完觉得…",
        "你以为这是小事?其实已经炸了。",
    ],
    "money": [
        "免费的东西,才是最贵的。",
        "这个羊毛,薅到就是赚到。",
        "一天一块钱,过上你想要的生活。",
    ],
    "lifestyle": [
        "这个习惯,改变了我一整天。",
        "我试了一周,真的有效果。",
        "姐妹们别再这样做了!",
    ],
    "tech_quirk": [
        "这个工具,凭什么刷屏全网?",
        "一个动作,省了我两小时。",
        "2025 年了,还有人不知道这个?",
    ],
    "emotional": [
        "看到最后,真的绷不住了。",
        "全网破防,我也一样。",
        "评论区已哭晕。",
    ],
    "social": [
        "00 后整顿职场,这次又赢了。",
        "打工人看完沉默了。",
        "这个现象,你身边一定也有。",
    ],
    "general": [
        "今天这个瓜,有点大。",
        "这条新闻,我看了三遍。",
        "现在全网都在讨论这件事。",
    ],
}

VISUAL_TEMPLATES = {
    "controversy": "红黄大字 + 慢速 zoom-in + 争议截图/原帖 + 弹幕式分屏",
    "money":       "金额数字放大 + 价格对比表 + 廉价 BGM 反转",
    "lifestyle":   "生活画面 + 慢动作 + 暖色调 + 文字气泡",
    "tech_quirk":  "录屏演示 + 步骤数字高亮 + 黑客帝国风代码雨",
    "emotional":   "慢镜头 + 钢琴 BGM + 黑屏白字金句 + 留白 1 秒",
    "social":      "群体画像 + 街采片段 + 投票浮窗",
    "general":     "新闻截图 + 红框标注 + 快切节奏",
}

CTA_TEMPLATES = [
    "你身边有这种人吗?评论区告诉我。",
    "这件事你怎么看?打在评论区。",
    "转发给你那个还不知道的朋友。",
    "关注我,每天一条新鲜事。",
]


def _pick(templates: list[str], seed: str) -> str:
    if not templates:
        return ""
    h = sum(ord(c) for c in seed) if seed else 0
    return templates[h % len(templates)]


def _format_heat(n: float) -> str:
    if n >= 1_0000_0000:
        return f"{n/1_0000_0000:.1f}亿热度"
    if n >= 10000:
        return f"{n/10000:.0f}万热度"
    if n > 0:
        return f"{int(n)} 热度"
    return "热度未知"


def build_script_pack(item: dict) -> dict:
    title = item["title"]
    tags = item.get("tags") or ["general"]
    primary = tags[0]
    summary = (item.get("summary") or "").strip()

    num_match = re.search(r"(\d+(?:\.\d+)?)\s*([万千百亿]|小时|分钟|天|月|年|岁|%|元|块|次|条|个|人|万)?", title)
    question_words = ["为什么", "怎么", "如何", "什么", "谁", "哪"]
    is_question = any(w in title for w in question_words)

    if num_match and not is_question:
        hook = f"就因为这个数字,全网都炸了。"
    elif is_question:
        hook = f"这个问题,90% 的人答错。"
    elif "禁止" in title or "驳回" in title or "起诉" in title:
        hook = "这件事,大结局了。"
    elif any(w in title for w in ["翻车", "破防", "哭了", "崩溃", "难绷"]):
        hook = "看到最后,我也没绷住。"
    elif "新" in title or "首发" in title or "上市" in title or "推出" in title:
        hook = "刚出来,我就想第一时间告诉你。"
    else:
        hook = _pick(HOOK_TEMPLATES.get(primary, HOOK_TEMPLATES["general"]), title)

    if not summary:
        summary = f"这条话题正在 {','.join(item['cross_sources'])} 同时刷屏,值得一聊。"

    angles = _generate_angles(title, summary, primary)
    visual = VISUAL_TEMPLATES.get(primary, VISUAL_TEMPLATES["general"])

    if "结婚" in title or "彩礼" in title or "离婚" in title:
        cta = "彩礼这件事,你们那边什么规矩?评论区聊聊。"
    elif "孩子" in title or "家长" in title or "学生" in title or "休学" in title:
        cta = "如果你是家长 / 孩子,看到这条会不会也破防?"
    elif "00后" in title or "打工人" in title or "职场" in title or "老板" in title or "工位" in title:
        cta = "打工人集合,这件事你经历过吗?评论区报到。"
    elif "免费" in title or "1元" in title or "羊毛" in title or "省钱" in title:
        cta = "这种羊毛你薅过吗?评论区晒你的战绩。"
    elif "起诉" in title or "驳回" in title or "违法" in title or "合法" in title:
        cta = "支持 / 反对?评论区投个票。"
    elif "AI" in title or "机器人" in title:
        cta = "AI 时代你怎么看?评论区和百万粉丝对个话。"
    else:
        cta = _pick(CTA_TEMPLATES, title)

    timing = [
        ("0-3s",  f"Hook: {hook}"),
        ("3-20s", f"背景陈述: {summary[:80]}{'…' if len(summary) > 80 else ''}"),
        ("20-50s", "核心观点(3 个):\n" + "\n".join(f"  • {a}" for a in angles)),
        ("50-60s", f"金句收尾 + CTA: {cta}"),
    ]

    return {
        "hook": hook, "background": summary, "angles": angles,
        "visual": visual, "timing": timing, "cta": cta, "primary_tag": primary,
    }


def _generate_angles(title: str, summary: str, primary: str) -> list[str]:
    angles: list[str] = []
    entity = ""
    m = re.search(r"[「」\"'](.+?)[「」\"']", title)
    if m:
        entity = m.group(1)[:15]
    if not entity:
        m = re.search(r"[\u4e00-\u9fff]{2,8}", title)
        if m:
            entity = m.group(0)
    if entity and len(entity) >= 2 and entity not in title[:3]:
        angles.append(f"先把「{entity}」这件事讲明白 — 所有人都在问。")
    else:
        angles.append("先把最核心的事实摆出来,别让观众猜。")

    if primary in ("controversy", "emotional"):
        angles.append("为什么大家反应这么大?有 3 层原因(经济 / 情绪 / 制度)。")
    elif primary == "money":
        angles.append("表面看是数字游戏,背后其实是一整条隐藏的产业链。")
    elif primary == "lifestyle":
        angles.append("看似是个人选择,其实是被设计好的 — 你也在被影响。")
    elif primary == "tech_quirk":
        angles.append("它的爆火说明一个老问题一直没被好好解决。")
    elif primary == "social":
        angles.append("这届人的反应,和上一代已经完全不同。")
    else:
        angles.append("为什么突然火?有 3 个原因,排第一个的很多人没想到。")

    if "结婚" in title or "彩礼" in title or "离婚" in title:
        angles.append("如果是你 / 你身边人,你会怎么处理?评论区聊聊。")
    elif "孩子" in title or "家长" in title or "学生" in title:
        angles.append("如果你是家长 / 学生,看到这条可能比想象中更扎心。")
    elif "00后" in title or "打工人" in title or "职场" in title or "老板" in title:
        angles.append("代入你自己 — 这种情况,你会不会也这样做?")
    elif "印度" in title or "日本" in title or "韩国" in title or "LV" in title or "小米" in title:
        angles.append("别光看热闹 — 这件事其实和我们每个人都有关系。")
    else:
        angles.append("最后一问:你是支持、反对方,还是觉得没那么简单?")
    return angles


def render_markdown(items: list[dict], date: str, use_ai: bool = False) -> str:
    lines: list[str] = []
    lines.append(f"# 🔥 1 分钟短视频选题包 · {date}")
    lines.append("")
    lines.append(f"> 共 {len(items)} 条选题,跨 {len({s for it in items for s in it['cross_sources']})} 个中文社交平台 + GitHub 飙升榜")
    lines.append("")

    for i, it in enumerate(items, 1):
        pack = build_script_pack(it)
        srcs = " · ".join(it["cross_sources"])
        heat = _format_heat(it["heat"])
        tags = " ".join(f"`#{t}`" for t in it["tags"])

        lines.append(f"---")
        lines.append("")
        lines.append(f"## 🎬 #{i}  {it['title']}  ⭐ {it['score']:.0f}")
        lines.append("")
        lines.append(f"**热度**: {heat}  ·  **来源**: {srcs}  ·  **标签**: {tags}")
        lines.append(f"**原文**: {it['url']}")
        lines.append("")
        lines.append(f"### 🎯 Hook(0-3 秒抓人)")
        lines.append(f"> {pack['hook']}")
        lines.append("")
        lines.append(f"### 📖 背景(15 秒)")
        lines.append(pack["background"])
        lines.append("")
        lines.append(f"### 💡 三个角度(每个 5-7 秒)")
        for j, a in enumerate(pack["angles"], 1):
            lines.append(f"{j}. {a}")
        lines.append("")
        lines.append(f"### 🎥 视觉/拍摄建议")
        lines.append(pack["visual"])
        lines.append("")
        lines.append(f"### ⏱️ 60 秒节奏")
        for when, what in pack["timing"]:
            lines.append(f"- **{when}**  {what}")
        lines.append("")
        lines.append(f"### 💬 CTA 收尾")
        lines.append(f"> {pack['cta']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_本包由 `topic-picker` 自动生成 · 每天跑一次 `python3.11 main.py` 即可刷新_")
    return "\n".join(lines)


def write_report(items: list[dict], out_dir: str = "/workspace/output",
                 date: str | None = None, use_ai: bool = False) -> Path:
    date = date or datetime.utcnow().strftime("%Y-%m-%d")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out = Path(out_dir) / f"{date}.md"
    out.write_text(render_markdown(items, date, use_ai=use_ai), encoding="utf-8")
    return out
