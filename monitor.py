#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arsenal 转会新闻监控
===================
数据源：
  - Romano  : Telegram 官方频道 @FabrizioRomano
  - Ornstein: The Athletic 作者页 (选项2) + Arsenal 聚合 TG 频道 @arsenalbreaking (选项3)
过滤：只推送含 Arsenal 关键词的内容
推送：Bark -> iPhone (免费, 国内可达, 免代理)

部署：GitHub Actions 定时运行（美国节点直连 TG API 与 Bark 服务器，全程免代理）。
依赖：仅 requests（HTML 解析用标准库）。
"""

import os
import re
import json
import sys
from pathlib import Path
from html.parser import HTMLParser

import requests

# ---------------------------------------------------------------------------
# 配置（敏感信息走环境变量 / GitHub Secrets；其余可在本文件直接改）
# ---------------------------------------------------------------------------
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
BARK_KEY = os.environ.get("BARK_KEY", "")
BARK_SERVER = os.environ.get("BARK_SERVER", "https://api.day.app").rstrip("/")

# Telegram 公共频道（用户名，不带 @）
TG_CHANNELS = ["FabrizioRomano", "arsenalbreaking"]

# The Athletic — Ornstein 作者页
ATHLETIC_AUTHOR_URL = "https://www.theathletic.com/author/david-ornstein/"
ATHLETIC_FEED_URL = "https://www.theathletic.com/author/david-ornstein/feed/"

# Arsenal 过滤关键词（大小写不敏感）
ARSENAL_KEYWORDS = ["arsenal", "#afc", "gunners", "the gunners"]

STATE_FILE = Path(os.environ.get("STATE_PATH", "state.json"))
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

session = requests.Session()
session.headers.update(UA)

URL_RE = re.compile(r"https?://[^\s)]+")


# ---------------------------------------------------------------------------
# 状态（去重）持久化
# ---------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"seen": [], "tg_offset": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 过滤
# ---------------------------------------------------------------------------
def is_arsenal(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(k in low for k in ARSENAL_KEYWORDS)


def extract_url(text: str):
    m = URL_RE.search(text or "")
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def tg_api(method: str, **params) -> dict:
    r = session.post(
        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/{method}",
        json=params,
        timeout=20,
    )
    return r.json()


def tg_join(chat_username: str) -> None:
    """尝试让 bot 加入公共频道以接收 channel_post 更新。"""
    try:
        tg_api("joinChat", chat_id="@" + chat_username)
        print(f"[tg] 已尝试加入频道 @{chat_username}")
    except Exception as e:
        print(f"[tg] 加入 @{chat_username} 失败（可手动在频道内添加 bot 为成员）: {e}")


def tg_get_updates(offset):
    """拉取并排空 channel_post 更新，返回 (updates, next_offset)。"""
    all_updates = []
    o = offset
    for _ in range(3):
        params = {"timeout": 15, "allowed_updates": json.dumps(["channel_post"])}
        if o:
            params["offset"] = o
        try:
            r = session.get(
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getUpdates",
                params=params,
                timeout=20,
            )
            data = r.json()
        except Exception as e:
            print(f"[tg] getUpdates 异常: {e}")
            break
        if not data.get("ok"):
            print(f"[tg] getUpdates 错误: {data}")
            break
        ups = data.get("result", [])
        if not ups:
            break
        all_updates.extend(ups)
        o = max(u["update_id"] for u in ups) + 1
        if len(ups) < 100:
            break
    return all_updates, o


# ---------------------------------------------------------------------------
# The Athletic 抓取
# ---------------------------------------------------------------------------
class AthleticParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles = []
        self._capture = False
        self._url = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            d = dict(attrs)
            href = d.get("href", "") or ""
            # 只认文章链接（含年份路径），排除导航链接
            if "nytimes.com/athletic" in href and re.search(r"/20\d{2}/\d{2}/\d{2}/", href):
                self._capture = True
                self._url = href
                self._buf = []

    def handle_endtag(self, tag):
        if tag == "a" and self._capture:
            title = " ".join("".join(self._buf).split()).strip()
            if title and self._url and len(title) > 5:
                self.articles.append((title, self._url))
            self._capture = False
            self._url = None
            self._buf = []

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)


def parse_rss(xml_text: str):
    out = []
    for m in re.finditer(
        r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>",
        xml_text,
        re.S,
    ):
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        link = m.group(2).strip()
        if title and link:
            out.append((title, link))
    return out


def athletic_fetch():
    """先试 RSS，失败回退 HTML 解析作者页。"""
    try:
        r = session.get(ATHLETIC_FEED_URL, timeout=30)
        if r.status_code == 200 and ("<rss" in r.text or "<feed" in r.text):
            items = parse_rss(r.text)
            if items:
                return items
    except Exception as e:
        print(f"[athletic] RSS 失败: {e}")

    try:
        r = session.get(ATHLETIC_AUTHOR_URL, timeout=30)
        r.raise_for_status()
        p = AthleticParser()
        p.feed(r.text)
        # 去重（同一 URL 只留一次）
        seen = set()
        uniq = []
        for title, url in p.articles:
            if url in seen:
                continue
            seen.add(url)
            uniq.append((title, url))
        return uniq
    except Exception as e:
        print(f"[athletic] HTML 解析失败: {e}")
        return []


# ---------------------------------------------------------------------------
# Bark 推送
# ---------------------------------------------------------------------------
def bark_push(title: str, body: str, url: str = None) -> object:
    payload = {"title": title, "body": body}
    if url:
        payload["url"] = url
    try:
        r = session.post(f"{BARK_SERVER}/{BARK_KEY}", json=payload, timeout=20)
        return r.status_code
    except Exception as e:
        print(f"[bark] 推送失败: {e}")
        return None


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    if not TG_BOT_TOKEN:
        print("缺少环境变量 TG_BOT_TOKEN")
        sys.exit(1)
    if not BARK_KEY:
        print("缺少环境变量 BARK_KEY")
        sys.exit(1)

    state = load_state()
    seen_set = set(state.get("seen", []))

    new_items = []  # (key, title, body, url)

    # ---- 1) Telegram 频道 ----
    for ch in TG_CHANNELS:
        tg_join(ch)

    updates, next_offset = tg_get_updates(state.get("tg_offset"))
    for upd in updates:
        cp = upd.get("channel_post")
        if not cp:
            continue
        chat = cp.get("chat", {})
        uname = (chat.get("username") or "").lower()
        if uname not in [c.lower() for c in TG_CHANNELS]:
            continue
        text = cp.get("text") or cp.get("caption") or ""
        mid = cp.get("message_id")
        key = f"tg:{chat.get('id')}:{mid}"
        if key in seen_set:
            continue
        if not is_arsenal(text):
            # 仍计入 seen，避免反复拉取非 Arsenal 消息
            seen_set.add(key)
            continue
        src = "Romano" if uname == "fabrizioromano" else "TG聚合"
        new_items.append((key, f"🔴 Arsenal · {src}", text, extract_url(text)))
        seen_set.add(key)

    if updates:
        state["tg_offset"] = next_offset

    # ---- 2) The Athletic (Ornstein) ----
    for title, url in athletic_fetch():
        key = f"athletic:{url}"
        if key in seen_set:
            continue
        if not is_arsenal(title):
            seen_set.add(key)
            continue
        new_items.append((key, "⚪ Arsenal · Ornstein", title, url))
        seen_set.add(key)

    # ---- 3) 推送 ----
    for key, title, body, url in new_items:
        code = bark_push(title, body[:400], url)
        print(f"[push] {title} | {body[:50]!r} -> HTTP {code}")

    state["seen"] = list(seen_set)[-2000:]  # 限制体积
    save_state(state)
    print(f"完成：本次新增 {len(new_items)} 条，历史去重池 {len(seen_set)} 条。")


if __name__ == "__main__":
    main()
