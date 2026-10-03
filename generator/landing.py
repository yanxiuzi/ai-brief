#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公开试读站的落地页渲染（转化版）。

单独成文件的原因：这一页是"销售员"，需要经常调整文案与结构，
和 bot.py 的生产逻辑分开，改版时不用担心弄坏生成流程。
"""
from __future__ import annotations

import html as _html


CSS = """
  :root { --ink:#1b1f24; --sub:#5b6472; --line:#e6e8ec; --brand:#0f62fe; --bg:#f5f6f8; --ok:#0b7a3b; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.75 -apple-system,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif; }
  .wrap { max-width:800px; margin:0 auto; padding:22px 14px 60px; }
  .card { background:#fff; border:1px solid var(--line); border-radius:16px; overflow:hidden; }
  .nav { display:flex; justify-content:space-between; align-items:center; padding:13px 28px;
         border-bottom:1px solid var(--line); font-size:13px; color:var(--sub); }
  .nav a { color:var(--brand); text-decoration:none; margin-left:14px; }
  .hero { padding:32px 28px 26px; background:linear-gradient(180deg,#f7faff,#fff); border-bottom:1px solid var(--line); }
  .brand { color:var(--brand); font-weight:700; letter-spacing:.06em; font-size:13px; }
  .hero h1 { font-size:29px; line-height:1.42; margin:10px 0 12px; }
  .hero .sub { color:#4a5462; font-size:15.5px; margin:0 0 20px; }
  .btn { display:inline-block; padding:13px 30px; background:#0f62fe; color:#fff !important;
         text-decoration:none; border-radius:999px; font-weight:600; font-size:16px;
         box-shadow:0 4px 14px rgba(15,98,254,.22); }
  .stats { display:flex; gap:20px; flex-wrap:wrap; margin:20px 0 0; font-size:13px; color:var(--sub); }
  .stats b { color:var(--ok); font-size:15px; }
  .body { padding:6px 28px 26px; }
  h2 { font-size:18px; margin:30px 0 12px; padding-left:10px; border-left:4px solid var(--brand); }
  .benefits { display:grid; grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); gap:12px; }
  .benefit { border:1px solid var(--line); border-radius:12px; padding:15px 16px; background:#fcfdff; }
  .benefit .t { font-weight:700; font-size:15px; margin-bottom:5px; }
  .benefit .d { font-size:13.5px; color:#4a5462; line-height:1.7; }
  .compare { width:100%; border-collapse:collapse; font-size:14px; }
  .compare th, .compare td { border:1px solid var(--line); padding:9px 12px; text-align:left; }
  .compare th { background:#f5f8ff; font-weight:600; }
  .compare td.y { color:var(--ok); font-weight:600; }
  .compare td.n { color:#9aa2ae; }
  .item { border:1px solid var(--line); border-radius:12px; padding:16px 18px; margin:12px 0; }
  .item h3 { font-size:16px; margin:0 0 8px; }
  .item p { margin:0 0 10px; color:#2c343d; }
  .meta { font-size:13px; color:var(--sub); }
  .meta b { color:var(--ok); font-weight:600; }
  .src { font-size:12px; color:#8b93a1; margin-top:6px; word-break:break-all; }
  .pay { display:flex; gap:26px; align-items:center; flex-wrap:wrap; justify-content:center;
         padding:24px; border:1px solid #cdeadb; background:#f0fbf5; border-radius:14px; }
  .pay img { width:156px; height:156px; border:1px solid #d7e3d9; border-radius:10px; background:#fff; padding:4px; }
  .pay .info { max-width:330px; }
  .pay .p-title { font-size:19px; font-weight:700; color:var(--ok); margin-bottom:8px; line-height:1.5; }
  .pay .p-note { font-size:14px; color:#2c343d; margin-bottom:14px; }
  .hint { font-size:13px; color:#8a6414; background:#fffbeb; border:1px solid #f2e2b8;
          padding:11px 14px; border-radius:10px; margin-top:12px; }
  .faq-item { border-bottom:1px solid var(--line); padding:14px 0; }
  .faq-item .q { font-weight:600; margin-bottom:5px; }
  .faq-item .a { color:#4a5462; font-size:14px; }
  .archive { padding:22px 28px 28px; border-top:1px solid var(--line); }
  .archive h2 { border:0; padding:0; font-size:16px; margin:0 0 12px; }
  .archive ul { margin:0; padding-left:18px; }
  .archive li { margin:7px 0; }
  .archive a { color:var(--brand); text-decoration:none; font-size:14px; }
  .foot { padding:18px 28px 26px; color:#8b93a1; font-size:12px; border-top:1px solid var(--line); }
  .foot a { color:var(--brand); text-decoration:none; }
  .mock { display:inline-block; margin-left:8px; padding:2px 8px; border-radius:99px;
    background:#fff4e5; color:#b25e00; font-size:12px; }
  @media (max-width:560px) {
    .hero { padding:24px 18px 20px; } .hero h1 { font-size:23px; }
    .body, .archive, .nav, .foot { padding-left:18px; padding-right:18px; }
    .pay img { width:132px; height:132px; }
  }
"""

DEFAULT_BENEFITS = [
    ("省时间", "8 个信息源（量子位、极客公园、爱范儿、TechCrunch、OpenAI 官方等）替你筛完，3 分钟看完。"),
    ("可核实", "每条都附原文来源链接，点开就能自己核对，不是二手转述。"),
    ("能落地", "每条都写清「对你的价值」：能怎么用、什么时候别用、有什么坑。"),
    ("可回查", "全部历史归档随时翻阅，错过一期也能补上。"),
]

DEFAULT_FAQ = [
    ("这些资讯网上不都是免费的吗？",
     "免费的是「信息」，我们卖的是「筛完的 3 分钟」。省下的是你自己刷 8 个源、分辨真假、再想清楚跟自己有什么关系的时间。"),
    ("内容可靠吗？",
     "每条都附来源链接，可以点开核对。当天没有抓到素材时，会明确标注「模型知识，建议核实」，不会假装是新闻。"),
    ("每天要花多久看？",
     "3 分钟。时间紧的话只看「对你的价值」那一行也够，那是我们觉得最值钱的部分。"),
    ("怎么收到？会漏看吗？",
     "加入知识星球后，每天 8:30 更新推送，历史内容在星球里随时可查，不会刷过去就没了。"),
    ("更新会断吗？",
     "内容生产全流程自动化，目前每天稳定更新。万一中断会提前说明，不会悄悄消失。"),
    ("不满意怎么办？",
     "如果内容对你没用，可以随时退出，没有自动续费的坑。我们更希望你是因为「真的省了时间」而留下。"),
]


def render(site_cfg: dict, cfg: dict, pub: dict, date_key: str, issues: list, is_mock: bool) -> str:
    def esc(v: object) -> str:
        return _html.escape(str(v or ""))

    brand = site_cfg.get("title") or cfg.get("brand") or "AI 情报站"
    tagline = site_cfg.get("tagline") or "每天早上 8:30，3 分钟看完 AI 圈真正重要的变化"
    subs = site_cfg.get("subscribe_url") or "#"
    base = (site_cfg.get("base_url") or "").rstrip("/")
    rss_url = f"{base}/feed.xml" if base else "feed.xml"
    contact = site_cfg.get("contact") or ""
    per_section = int(cfg.get("items_per_section") or 3)
    section_count = len(cfg.get("sections") or [])
    full_total = per_section * section_count
    pub_total = sum(len(s.get("items") or []) for s in (pub.get("sections") or []))

    # 今日试读
    parts: list[str] = []
    for sec in pub.get("sections", []):
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

    # 价值主张
    benefits = site_cfg.get("benefits") or DEFAULT_BENEFITS
    benefit_html = "".join(
        f'<div class="benefit"><div class="t">{esc(b[0])}</div><div class="d">{esc(b[1])}</div></div>'
        for b in benefits
    )

    # 公开版 vs 完整版
    compare = (
        '<table class="compare"><tr><th>内容</th><th>公开试读版</th><th>完整版（知识星球）</th></tr>'
        f'<tr><td>每日条目</td><td class="n">每栏 1 条（共 {pub_total} 条）</td>'
        f'<td class="y">每栏 {per_section} 条（共 {full_total} 条）</td></tr>'
        '<tr><td>来源链接</td><td class="y">✅</td><td class="y">✅</td></tr>'
        '<tr><td>「对你的价值」分析</td><td class="n">部分</td><td class="y">全部</td></tr>'
        '<tr><td>「今天就能做」行动清单</td><td class="n">❌</td><td class="y">✅</td></tr>'
        '<tr><td>历史归档</td><td class="n">部分</td><td class="y">全部</td></tr>'
        '<tr><td>每天 8:30 自动推送</td><td class="n">❌</td><td class="y">✅</td></tr>'
        "</table>"
    )

    # 订阅区
    pay = (
        '<div class="pay">'
        '<img src="assets/qr.png" alt="扫码加入知识星球">'
        '<div class="info">'
        f'<div class="p-title">{esc(site_cfg.get("price_note") or "加入知识星球，看完整版")}</div>'
        f'<div class="p-note">{esc(site_cfg.get("delivery_note") or "每天 8:30 自动推送 + 全部历史归档，随时可回查。")}</div>'
        f'<a class="btn" href="{esc(subs)}">立即加入</a>'
        "</div></div>"
    )

    # FAQ
    faq_items = site_cfg.get("faq") or DEFAULT_FAQ
    faq_html = "".join(
        f'<div class="faq-item"><div class="q">{esc(q)}</div><div class="a">{esc(a)}</div></div>'
        for q, a in faq_items
    )

    # 往期
    lis = "".join(
        f'<li><a href="issues/{esc(i.get("date"))}.html">{esc(i.get("date"))}　{esc(i.get("title"))}</a></li>'
        for i in issues[:30]
    ) or "<li>（第一期正在路上）</li>"

    mock_note = '<div class="hint">本页为演示数据（mock），非真实资讯。</div>' if is_mock else ""
    contact_html = f'　·　白标合作 / 内容供应：{esc(contact)}' if contact else ""

    return (
        '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(brand)}</title>\n"
        f'<meta name="description" content="{esc(tagline)}">\n'
        f'<meta property="og:title" content="{esc(brand)}">\n'
        f'<meta property="og:description" content="{esc(tagline)}">\n'
        f'<meta property="og:image" content="{esc(base)}/assets/cover.png">\n'
        '<meta property="og:type" content="website">\n'
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"Periodical","name":"' + esc(brand) + '",'
        '"description":"' + esc(tagline) + '","inLanguage":"zh-CN"}'
        "</script>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n<div class=\"wrap\">\n<div class=\"card\">\n"
        '<div class="nav"><span>每日更新 · 自动生成</span>'
        f'<span><a href="{esc(rss_url)}">RSS 订阅</a><a href="#subscribe">立即订阅</a></span></div>\n'
        '<div class="hero">'
        f'<div class="brand">{esc(cfg.get("brand"))}{"<span class=\'mock\'>示例数据</span>" if is_mock else ""}</div>'
        f"<h1>{esc(tagline)}</h1>"
        f'<p class="sub">{esc(site_cfg.get("intro") or "模型发布、产品更新、工具玩法、变现机会，每条都附来源链接。")}</p>'
        f'<a class="btn" href="{esc(subs)}">加入知识星球 · 看完整版</a>'
        '<div class="stats">'
        f"<span><b>{len(issues)}</b> 期已更新</span>"
        f"<span><b>{len(cfg.get('source_urls') or [])}</b> 个信息源</span>"
        "<span>每天 <b>08:30</b> 自动送达</span>"
        "</div></div>\n"
        '<div class="body">'
        "<h2>你会得到什么</h2>"
        f'<div class="benefits">{benefit_html}</div>'
        "<h2>公开版 vs 完整版</h2>"
        f"{compare}"
        "<h2>今日试读（{date}）</h2>".replace("{date}", esc(date_key))
        + "".join(parts) +
        '<h2 id="subscribe">订阅完整版</h2>'
        f"{pay}"
        '<div class="hint">公开版每个栏目只放 1 条；完整版含全部条目、'
        "「今天就能做」行动清单，以及可随时回查的历史归档。</div>"
        "<h2>常见问题</h2>"
        f'<div class="faq">{faq_html}</div>'
        "</div>\n"
        f'<div class="archive"><h2>往期归档</h2><ul>{lis}</ul></div>\n'
        f'<div class="foot">RSS 订阅：<a href="{esc(rss_url)}">feed.xml</a>'
        f"　·　由「{esc(cfg.get('brand'))}」自动生成{contact_html}<br>"
        "内容仅供参考，不构成投资、法律或医疗建议。</div>\n"
        f"{mock_note}"
        "</div>\n</div>\n</body>\n</html>\n"
    )