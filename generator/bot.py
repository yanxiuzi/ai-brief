#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 简报机器人 v0.1 —— 把 API token 变成可交付、可出售的信息产品（最小可用版）

用法:
    python bot.py --mock              # 离线演示：不联网、不花 token，先看成品长什么样
    python bot.py                     # 正式运行：读取 config.json，调用大模型生成一期简报
    python bot.py --date 2026-10-04   # 指定期号日期

产出（默认写在脚本同目录）:
    latest.md / latest.html           最新一期
    archive/YYYY-MM-DD.md / .html     历史归档

依赖: 仅 Python 标准库（3.9+），无需 pip install。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html as _html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

DEFAULT_CONFIG: dict = {
    "brand": "晨间情报局",
    "niche": "AI 工具与独立开发者副业",
    "audience": "想用 AI 做副业、接单、做产品的职场人",
    "language": "zh-CN",
    "sections": ["今日要闻", "工具与产品", "变现机会", "风险与避坑"],
    "items_per_section": 3,
    "fetch_web": False,
    "source_urls": [],
    "output_dir": ".",
    "llm": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.3,
        "max_tokens": 3500,
        "timeout_sec": 120,
    },
    "deliver": {
        "webhook_url": "",
        "webhook_kind": "wecom",
    },
}


# ---------------------------------------------------------------- 基础工具

def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_env_file(path: Path) -> None:
    """轻量 .env 支持：KEY=VALUE，已存在的环境变量优先。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def today_str() -> str:
    now = _dt.datetime.now()
    return f"{now:%Y-%m-%d} {WEEKDAYS[now.weekday()]}"


# ---------------------------------------------------------------- 素材抓取

_DROP_BLOCK = re.compile(r"<(script|style|noscript|svg|head)[^>]*>.*?</\1>", re.S | re.I)
_ANY_TAG = re.compile(r"<[^>]+>")
_MANY_BLANK = re.compile(r"\n{2,}")
_MANY_SPACE = re.compile(r"[ \t\r\f\v]+")


def strip_html(raw: str) -> str:
    raw = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", raw, flags=re.S)
    raw = _DROP_BLOCK.sub(" ", raw)
    raw = _ANY_TAG.sub(" ", raw)
    raw = _html.unescape(raw)
    lines = [_MANY_SPACE.sub(" ", ln).strip() for ln in raw.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return _MANY_BLANK.sub("\n", text).strip()


def _tag_text(xml: str, tag: str) -> str:
    matched = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.S | re.I)
    return strip_html(matched.group(1)).strip() if matched else ""


def parse_feed(text: str, max_items: int = 14, limit: int = 3500) -> str | None:
    """把 RSS/Atom 解析成「时间 + 标题 + 链接 + 摘要」，比整页纯文本更适合喂给模型。"""
    items = re.findall(r"<item[\s>].*?</item>", text, re.S | re.I)
    if not items:
        items = re.findall(r"<entry[\s>].*?</entry>", text, re.S | re.I)
    if not items:
        return None
    lines = []
    for it in items[:max_items]:
        title = _tag_text(it, "title")
        if not title:
            continue
        date = _tag_text(it, "pubDate") or _tag_text(it, "updated") or _tag_text(it, "published")
        link = _tag_text(it, "link")
        if not link:
            matched = re.search(r'<link[^>]*href="([^"]+)"', it, re.I)
            link = matched.group(1) if matched else ""
        desc = _tag_text(it, "description") or _tag_text(it, "summary") or _tag_text(it, "content")
        line = f"- [{date[:29]}] {title}" if date else f"- {title}"
        if link:
            line += f"\n  链接: {link}"
        if desc:
            line += f"\n  摘要: {desc[:400]}"
        lines.append(line)
    if not lines:
        return None
    return "\n".join(lines)[:limit]


def fetch_source(url: str, timeout: int = 20, limit: int = 3000) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (briefing-bot/0.1)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(600_000)
            charset = resp.headers.get_content_charset() or "utf-8"
    except Exception as exc:  # noqa: BLE001 - 素材抓取失败不应中断整个流程
        print(f"  [warn] 抓取失败 {url} -> {exc}")
        return None
    try:
        decoded = raw.decode(charset, errors="replace")
    except LookupError:
        decoded = raw.decode("utf-8", errors="replace")

    title = ""
    matched = re.search(r"<title[^>]*>(.*?)</title>", decoded, re.S | re.I)
    if matched:
        title = _html.unescape(matched.group(1)).strip()[:120]

    body = parse_feed(decoded) or strip_html(decoded)[:limit]
    if len(body) < 80:
        print(f"  [warn] 抓取内容过短，已跳过 {url}")
        return None
    return {"url": url, "title": title or url, "text": body}

# ---------------------------------------------------------------- 模型调用

def build_messages(cfg: dict, materials: list[dict], date_str: str) -> list[dict]:
    sys_prompt = (
        "你是一位资深行业情报编辑，为付费订阅者撰写每日简报。硬性要求：\n"
        "1) 只输出一个 JSON 对象，不要输出任何解释文字或 Markdown 代码块；\n"
        "2) 只要提供了【素材】，事实、数字、公司名必须来自素材，素材没写的一律不编；\n"
        "3) 没有素材时，允许基于你自己的知识撰写，但每条的 source 字段必须写「模型知识，建议核实」，"
        "并且绝对禁止编造链接、引用、发布时间与精确数字；\n"
        "4) 每条都要写清 why 字段：这件事对读者有什么用、能怎么用、或要小心什么；\n"
        "5) 语气直接、具体，避免空话套话，面向中文读者；\n"
        '6) JSON 结构必须是：{"title": string, "one_liner": string, '
        '"sections": [{"name": string, "items": [{"headline": string, "summary": string, '
        '"why": string, "source": string}]}], "action_items": [string, string, string]}；\n'
        f"7) sections 必须严格按此顺序使用这些名字：{cfg['sections']}；\n"
        f"8) 每个 section 输出 {cfg['items_per_section']} 条。"
    )
    user_parts = [
        f"日期：{date_str}",
        f"细分领域：{cfg['niche']}",
        f"目标读者：{cfg['audience']}",
        f"品牌名：{cfg['brand']}",
    ]
    if materials:
        blocks = [
            f"--- 素材 {i}｜来源链接: {m['url']}\n标题: {m['title']}\n{m['text']}"
            for i, m in enumerate(materials, 1)
        ]
        user_parts.append("\n【素材】（事实必须来自以下内容）\n" + "\n\n".join(blocks))
    else:
        user_parts.append("\n【素材】无。请基于你的知识撰写，所有条目 source 写「模型知识，建议核实」。")
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def call_llm(cfg: dict, messages: list[dict]) -> tuple[str, dict]:
    llm = cfg["llm"]
    api_key = (os.environ.get(llm["api_key_env"]) or "").strip()
    if not api_key:
        raise SystemExit(
            f"\n[错误] 环境变量 {llm['api_key_env']} 未设置，无法调用模型。\n"
            f"  · 想先看成品效果：python bot.py --mock\n"
            f"  · 正式运行：把 API Key 写进 {HERE / '.env'}（参考 .env.example），"
            f"或在 PowerShell 里执行 $env:{llm['api_key_env']}=\"你的Key\"\n"
            f"  · 换供应商：改 config.json 里的 llm.base_url / llm.model / llm.api_key_env\n"
        )

    endpoint = llm["base_url"].rstrip("/") + "/chat/completions"
    body = {
        "model": llm["model"],
        "messages": messages,
        "temperature": llm.get("temperature", 0.3),
        "max_tokens": llm.get("max_tokens", 3500),
        "response_format": {"type": "json_object"},
    }
    last_err = ""
    for attempt in range(1, 4):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=llm.get("timeout_sec", 120)) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            choice = (payload.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = (message.get("content") or "").strip()
            usage = payload.get("usage") or {}
            if not content:
                # 推理模型（如 DeepSeek 系列）会先花 token 思考，max_tokens 太小时 content 会为空
                current = int(body.get("max_tokens") or 0)
                if 0 < current < 32000:
                    body["max_tokens"] = min(current * 2, 32000)
                    last_err = (f"模型只产出推理内容（reasoning_content），已把 max_tokens 提到 "
                                f"{body['max_tokens']} 重试")
                    print(f"  [retry] {last_err}")
                    continue
                raise SystemExit(
                    "[错误] 模型返回了空内容，通常是 max_tokens 太小（token 全被推理过程占用）。\n"
                    f"  当前 max_tokens = {current}，模型 = {llm['model']}；推理模型建议 >= 8000。"
                )
            return content, usage
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_err = f"HTTP {exc.code}: {detail}"
            if exc.code == 400 and "response_format" in detail:
                body.pop("response_format", None)
                last_err += "（该接口不支持 response_format，已改用普通模式重试）"
                continue
            if exc.code in (400, 401, 403, 404):
                break
        except Exception as exc:  # noqa: BLE001
            last_err = repr(exc)
        if attempt < 3:
            wait = 2 ** attempt
            print(f"  [retry] 第 {attempt} 次失败：{last_err}，{wait}s 后重试…")
            time.sleep(wait)
    raise SystemExit(f"[错误] 调用模型失败：{last_err}")


def extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("模型返回的内容不是合法 JSON")

# ---------------------------------------------------------------- 演示数据

def mock_payload(cfg: dict) -> dict:
    def item(name: str, idx: int) -> dict:
        return {
            "headline": f"【示例】{name}·第 {idx} 条：这里是一条真实运行时由模型生成的标题",
            "summary": "这里是 80–150 字的摘要，讲清楚「发生了什么、涉及谁、关键数字是多少」。"
                       "正式运行时，它会来自你抓取的素材或模型知识，mock 模式下不会联网。",
            "why": "这里写「对读者意味着什么」：能省多少时间、能怎么用、或有什么风险要避开。",
            "source": "示例数据（mock）",
        }

    sections = [
        {"name": name, "items": [item(name, i) for i in range(1, cfg["items_per_section"] + 1)]}
        for name in cfg["sections"]
    ]
    return {
        "title": f"{cfg['brand']} · 每日简报（示例期）",
        "one_liner": "这是 mock 模式生成的样例，用来确认排版与流程；填好 API Key 后运行 "
                     "python bot.py，内容会被替换成真实简报。",
        "sections": sections,
        "action_items": [
            "把 config.json 的 niche / audience 改成你要卖的方向",
            "注册一个模型 API Key 并写入 .env",
            "先免费发给 5 位目标读者，收集反馈再定价",
        ],
    }


# ---------------------------------------------------------------- 渲染输出

def render_markdown(payload: dict, cfg: dict, date_str: str, is_mock: bool) -> str:
    lines = [f"# {payload.get('title') or cfg['brand']}", ""]
    if is_mock:
        lines += ["> ⚠️ 本文件为 mock 演示数据，不是真实资讯。", ""]
    lines += [f"**{date_str}**", "", f"> {payload.get('one_liner', '')}", ""]

    for sec in payload.get("sections", []):
        lines += [f"## {sec.get('name', '')}", ""]
        for it in sec.get("items", []):
            lines += [
                f"### {it.get('headline', '')}",
                "",
                it.get("summary", ""),
                "",
                f"- **对你的价值**：{it.get('why', '')}",
                f"- **来源**：{it.get('source', '')}",
                "",
            ]

    actions = payload.get("action_items") or []
    if actions:
        lines += ["## 今天就能做", ""]
        lines += [f"{i}. {a}" for i, a in enumerate(actions, 1)]
        lines += [""]

    lines += [
        "---",
        f"由「{cfg['brand']}」自动生成 · 内容仅供参考，不构成投资、法律或医疗建议。",
        "",
    ]
    return "\n".join(lines)


CSS = """
  :root { --ink:#1b1f24; --sub:#5b6472; --line:#e6e8ec; --brand:#0f62fe; --bg:#f5f6f8; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.75 -apple-system,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif; }
  .wrap { max-width:780px; margin:0 auto; padding:28px 14px 64px; }
  .card { background:#fff; border:1px solid var(--line); border-radius:16px; overflow:hidden; }
  .hero { padding:30px 30px 22px; border-bottom:1px solid var(--line); background:linear-gradient(180deg,#fbfcff,#fff); }
  .brand { color:var(--brand); font-weight:700; letter-spacing:.06em; font-size:13px; }
  h1 { font-size:26px; line-height:1.35; margin:10px 0 6px; }
  .date { color:var(--sub); font-size:13px; }
  .one-liner { margin:16px 0 0; padding:12px 14px; background:#f2f6ff; border-left:3px solid var(--brand);
    border-radius:0 8px 8px 0; color:#26303d; font-size:15px; }
  .body { padding:8px 30px 26px; }
  h2 { font-size:18px; margin:28px 0 12px; padding-left:10px; border-left:4px solid var(--brand); }
  .item { border:1px solid var(--line); border-radius:12px; padding:16px 18px; margin:12px 0; }
  .item h3 { font-size:16px; margin:0 0 8px; }
  .item p { margin:0 0 10px; color:#2c343d; }
  .meta { font-size:13px; color:var(--sub); }
  .meta b { color:#0b7a3b; font-weight:600; }
  .src { font-size:12px; color:#8b93a1; margin-top:6px; word-break:break-all; }
  .actions { margin:26px 0 0; padding:18px 20px; background:#f0fbf5; border:1px solid #cdeadb; border-radius:12px; }
  .actions h2 { border:0; padding:0; margin:0 0 10px; font-size:16px; color:#0b7a3b; }
  .actions li { margin:6px 0; }
  .foot { padding:18px 30px 26px; color:#8b93a1; font-size:12px; border-top:1px solid var(--line); }
  .mock { display:inline-block; margin-left:8px; padding:2px 8px; border-radius:99px;
    background:#fff4e5; color:#b25e00; font-size:12px; }
"""


def render_html(payload: dict, cfg: dict, date_str: str, is_mock: bool) -> str:
    def esc(v: object) -> str:
        return _html.escape(str(v or ""))

    parts: list[str] = []
    for sec in payload.get("sections", []):
        parts.append(f"<h2>{esc(sec.get('name'))}</h2>")
        for it in sec.get("items", []):
            parts.append(
                '<div class="item">'
                f"<h3>{esc(it.get('headline'))}</h3>"
                f"<p>{esc(it.get('summary'))}</p>"
                f'<div class="meta"><b>对你的价值</b>：{esc(it.get("why"))}</div>'
                f'<div class="src">来源：{esc(it.get("source"))}</div>'
                "</div>"
            )

    actions_html = ""
    actions = payload.get("action_items") or []
    if actions:
        lis = "".join(f"<li>{esc(a)}</li>" for a in actions)
        actions_html = f'<div class="actions"><h2>今天就能做</h2><ul>{lis}</ul></div>'

    mock_badge = '<span class="mock">示例数据</span>' if is_mock else ""
    return (
        '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(payload.get('title') or cfg['brand'])}</title>\n"
        f'<style>{CSS}</style>\n</head>\n<body>\n<div class="wrap">\n<div class="card">\n'
        '<div class="hero">'
        f'<div class="brand">{esc(cfg["brand"])}{mock_badge}</div>'
        f"<h1>{esc(payload.get('title'))}</h1>"
        f'<div class="date">{esc(date_str)}</div>'
        f'<div class="one-liner">{esc(payload.get("one_liner"))}</div>'
        "</div>\n"
        f'<div class="body">{"".join(parts)}{actions_html}</div>\n'
        f'<div class="foot">由「{esc(cfg["brand"])}」自动生成 · 内容仅供参考，'
        "不构成投资、法律或医疗建议。</div>\n"
        "</div>\n</div>\n</body>\n</html>\n"
    )

def build_push_text(payload: dict, cfg: dict, date_str: str) -> str:
    lines = [f"【{cfg['brand']}】{date_str}"]
    if payload.get("one_liner"):
        lines += ["", str(payload["one_liner"])]
    for sec in (payload.get("sections") or [])[:2]:
        lines += ["", f"· {sec.get('name', '')}"]
        for it in (sec.get("items") or [])[:3]:
            lines.append(f"  - {it.get('headline', '')}")
    lines += ["", "完整版：latest.html"]
    return "\n".join(lines)


def push_webhook(cfg: dict, title: str, text: str) -> None:
    conf = cfg.get("deliver") or {}
    url = (conf.get("webhook_url") or "").strip()
    if not url:
        return
    kind = (conf.get("webhook_kind") or "wecom").lower()
    if kind == "feishu":
        body = {"msg_type": "text", "content": {"text": f"{title}\n{text}"}}
    else:  # 企业微信 / 钉钉 / 通用
        body = {"msgtype": "text", "text": {"content": f"{title}\n{text}"}}
    req = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"  [webhook] 已推送到群机器人（{kind}），HTTP {resp.status}")
    except Exception as exc:  # noqa: BLE001
        print(f"  [webhook] 推送失败：{exc}")


# ---------------------------------------------------------------- 静态站点 / RSS

SITE_CSS = """
  .cta { margin:26px 0 6px; padding:22px 24px; border:1px solid #cdeadb; background:#f0fbf5; border-radius:14px; }
  .cta-t { font-size:18px; font-weight:700; color:#0b7a3b; }
  .cta-p { font-size:15px; margin:6px 0 14px; color:#2c343d; }
  .btn { display:inline-block; padding:11px 26px; background:#0f62fe; color:#fff !important;
         text-decoration:none; border-radius:999px; font-weight:600; font-size:15px; }
  .cta-n { margin-top:12px; font-size:13px; color:#5b6472; }
  .archive { padding:22px 30px 30px; }
  .archive h2 { border:0; padding:0; font-size:16px; margin:0 0 12px; }
  .archive ul { margin:0; padding-left:18px; }
  .archive li { margin:7px 0; }
  .archive a { color:#0f62fe; text-decoration:none; font-size:14px; }
  .top-note { padding:14px 30px; background:#fffbeb; border-bottom:1px solid #f2e2b8;
              font-size:13px; color:#8a6414; }
"""


def public_payload(payload: dict, keep: int) -> dict:
    """公开试读版：每个栏目只保留前 keep 条，完整版留给付费用户。"""
    keep = max(1, int(keep))
    out = dict(payload)
    out["sections"] = [
        {**sec, "items": (sec.get("items") or [])[:keep]}
        for sec in (payload.get("sections") or [])
    ]
    return out


def load_issues(site_dir: Path) -> list:
    path = site_dir / "issues.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:  # noqa: BLE001
        return []


def render_site_index(site_cfg: dict, cfg: dict, pub: dict, date_key: str,
                      issues: list, is_mock: bool) -> str:
    """公开试读站落地页：委托给 landing.py（销售页，独立维护，方便改文案）。"""
    import landing
    return landing.render(site_cfg, cfg, pub, date_key, issues, is_mock)


def render_rss(site_cfg: dict, cfg: dict, issues: list) -> str:
    def esc(v: object) -> str:
        return _html.escape(str(v or ""), quote=True)

    base = (site_cfg.get("base_url") or "").rstrip("/")
    link_for = lambda d: f"{base}/issues/{d}.html" if base else f"issues/{d}.html"  # noqa: E731

    items = []
    for i in issues[:30]:
        d = str(i.get("date") or "")
        items.append(
            "<item>"
            f"<title>{esc(i.get('title'))}</title>"
            f"<link>{esc(link_for(d))}</link>"
            f"<guid isPermaLink=\"false\">{esc(cfg['brand'])}-{esc(d)}</guid>"
            f"<description>{esc(i.get('one_liner'))}</description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{esc(site_cfg.get('title') or cfg['brand'])}</title>"
        f"<link>{esc(base or '')}</link>"
        f"<description>{esc(site_cfg.get('tagline'))}</description>"
        f"<language>zh-cn</language>{''.join(items)}"
        "</channel></rss>\n"
    )


def build_site_files(cfg: dict, payload: dict, date_key: str, date_str: str,
                     is_mock: bool, out_dir: Path) -> dict:
    """生成公开站相关文件（返回 路径 -> 内容）。"""
    site_cfg = cfg.get("site") or {}
    if not site_cfg.get("enabled"):
        return {}
    keep = int(site_cfg.get("public_items_per_section", 1) or 1)
    pub = public_payload(payload, keep)
    site_dir = out_dir / "site"
    issues_dir = site_dir / "issues"

    issues = [i for i in load_issues(site_dir) if str(i.get("date")) != date_key]
    issues.append({
        "date": date_key,
        "title": str(payload.get("title") or "")[:80],
        "one_liner": str(payload.get("one_liner") or "")[:160],
    })
    issues.sort(key=lambda item: str(item.get("date")), reverse=True)
    issues = issues[:90]

    out = {
        issues_dir / f"{date_key}.html": render_html(pub, cfg, date_str, is_mock),
        site_dir / "issues.json": json.dumps(issues, ensure_ascii=False, indent=2),
        site_dir / "index.html": render_site_index(site_cfg, cfg, pub, date_key, issues, is_mock),
        site_dir / "feed.xml": render_rss(site_cfg, cfg, issues),
    }
    # 附件：二维码 / 分享封面（存在才复制）
    for asset in ("qr.png", "cover.png"):
        src = HERE / "assets" / asset
        if src.exists():
            out[site_dir / "assets" / asset] = src.read_bytes()
    return out


def rebuild_site(cfg: dict, out_dir: Path, archive_dir: Path) -> int:
    """不调用模型：用归档 JSON 重建公开站（改价格/链接后用，省 token）。"""
    jsons = sorted(archive_dir.glob("*.json"))
    if not jsons:
        print("[错误] 归档里没有内容 JSON，请先跑一次 python bot.py（新版会自动保存）。")
        return 1
    latest = jsons[-1]
    date_key = latest.stem
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[错误] 读取 {latest} 失败：{exc}")
        return 1
    files = build_site_files(cfg, payload, date_key, date_key, False, out_dir)
    if not files:
        print("[错误] config.json 里 site.enabled 不是 true。")
        return 1
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    print("→ 已重建公开站（未调用模型）：")
    for path in files:
        print(f"    {path}")
    print("完成 OK")
    return 0


# ---------------------------------------------------------------- 主流程

def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass

    parser = argparse.ArgumentParser(description="AI 简报机器人（MVP）")
    parser.add_argument("--config", default=str(HERE / "config.json"), help="配置文件路径")
    parser.add_argument("--mock", action="store_true", help="离线演示，不调用模型")
    parser.add_argument("--date", default="", help="期号日期，如 2026-10-04（默认今天）")
    parser.add_argument("--rebuild-site", action="store_true",
                        help="不调用模型，用已归档内容重建公开站（改价格/订阅链接后用）")
    args = parser.parse_args(argv)

    load_env_file(HERE / ".env")

    config_path = Path(args.config)
    user_cfg: dict = {}
    if config_path.exists():
        user_cfg = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        print(f"  [warn] 未找到 {config_path}，使用内置默认配置。")
    cfg = deep_merge(DEFAULT_CONFIG, user_cfg)

    out_dir = Path(cfg.get("output_dir") or ".")
    if not out_dir.is_absolute():
        out_dir = (HERE / out_dir).resolve()
    if args.mock:
        # 演示模式写到 mock/ 子目录，绝不覆盖真实归档与已发布站点
        out_dir = out_dir / "mock"
    archive_dir = out_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    if args.rebuild_site:
        return rebuild_site(cfg, out_dir, archive_dir)

    date_str = args.date.strip() or today_str()
    date_key = date_str.split()[0]

    mode = "MOCK（演示）" if args.mock else "正式"
    print("=" * 62)
    print(f"「{cfg['brand']}」简报生成中…  期号：{date_str}  模式：{mode}")
    if args.mock:
        print("提示：演示模式输出到 mock/ 子目录，不会覆盖真实归档。")
    print(f"细分领域：{cfg['niche']}")
    print("=" * 62)

    materials: list[dict] = []
    if cfg.get("fetch_web") and cfg.get("source_urls") and not args.mock:
        print(f"→ 抓取素材 {len(cfg['source_urls'])} 个来源…")
        for url in cfg["source_urls"]:
            got = fetch_source(url)
            if got:
                materials.append(got)
                print(f"  [ok] {got['title'][:60]}")
        print(f"  共获得 {len(materials)} 份素材。")

    usage: dict = {}
    if args.mock:
        payload = mock_payload(cfg)
    else:
        print("→ 调用大模型生成内容…")
        raw, usage = call_llm(cfg, build_messages(cfg, materials, date_str))
        payload = extract_json(raw)

    md = render_markdown(payload, cfg, date_str, args.mock)
    html_doc = render_html(payload, cfg, date_str, args.mock)

    files = {
        out_dir / "latest.md": md,
        out_dir / "latest.html": html_doc,
        archive_dir / f"{date_key}.md": md,
        archive_dir / f"{date_key}.html": html_doc,
        archive_dir / f"{date_key}.json": json.dumps(payload, ensure_ascii=False, indent=2),
    }

    site_cfg = cfg.get("site") or {}
    site_dir = out_dir / "site"
    files.update(build_site_files(cfg, payload, date_key, date_str, args.mock, out_dir))

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    print("→ 已生成：")
    print(f"    {out_dir / 'latest.md'}")
    print(f"    {out_dir / 'latest.html'}")
    print(f"    {archive_dir / (date_key + '.md')}")
    if site_cfg.get("enabled"):
        print(f"    {site_dir / 'index.html'}  <- 公开试读站（可部署到 GitHub Pages / 任意静态托管）")
        print(f"    {site_dir / 'feed.xml'}    <- RSS 订阅源")
    if usage:
        print(f"→ token 用量：输入 {usage.get('prompt_tokens', '?')}，输出 {usage.get('completion_tokens', '?')}")

    if not args.mock:
        push_webhook(cfg, str(payload.get("title") or cfg["brand"]), build_push_text(payload, cfg, date_str))

    print("完成 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())