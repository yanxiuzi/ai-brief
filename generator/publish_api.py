#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 GitHub Contents API 发布 site/ 目录。

为什么不用 git push：国内直连 GitHub 时 push 常被重置（curl 28 / SSL_read），
而 API 的短请求稳定得多。适合本项目的纯静态站点（文件小、数量少）。

用法（PowerShell）:
    $env:GITHUB_TOKEN = "你的令牌"
    python publish_api.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
REPO = "yanxiuzi/ai-brief"
BRANCH = "main"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def api(method: str, path: str, token: str, body: dict | None = None):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-brief-publisher",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except Exception:  # noqa: BLE001
            return exc.code, {"message": raw[:200]}
    except Exception as exc:  # noqa: BLE001
        return 0, {"message": repr(exc)}


def main() -> int:
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        print("[错误] 未设置 GITHUB_TOKEN 环境变量。")
        return 1
    if not SITE.exists():
        print(f"[错误] 找不到站点目录：{SITE}")
        return 1

    files = sorted(
        p for p in SITE.rglob("*")
        if p.is_file() and ".git" not in p.parts
    )
    if not files:
        print("[错误] site/ 目录里没有文件，先运行 python bot.py")
        return 1

    ok = 0
    for f in files:
        rel = f.relative_to(SITE).as_posix()
        content = base64.b64encode(f.read_bytes()).decode("ascii")
        status, info = api("GET", f"/repos/{REPO}/contents/{rel}?ref={BRANCH}", token)
        body = {"message": f"更新 {rel}", "content": content, "branch": BRANCH}
        if status == 200 and info.get("sha"):
            body["sha"] = info["sha"]
        status, res = api("PUT", f"/repos/{REPO}/contents/{rel}", token, body)
        if status in (200, 201):
            print(f"  [ok] {rel}")
            ok += 1
        else:
            print(f"  [失败] {rel} → HTTP {status}: {res.get('message')}")

    print(f"完成：{ok}/{len(files)} 个文件已发布到 https://github.com/{REPO}")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    raise SystemExit(main())