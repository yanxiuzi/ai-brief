# AI 日报自动生成流水线（ai-brief-generator）

<p align="center">
  <b>把任意 LLM 变成一条每天自动运转的内容生产线</b><br>
  抓 RSS → 结构化 → LLM 提炼 → 生成日报 → 发布静态站 + RSS → 归档，全程无人值守
</p>

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="deps" src="https://img.shields.io/badge/dependencies-0-brightgreen">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green">
</p>

**▶ 在线示例（每天自动更新，没人管它）：** https://yanxiuzi.github.io/ai-brief/

---

## 它解决什么问题

每天要刷十几个信息源，刷完还记不住重点。这个项目把 **抓取 → 筛选 → 提炼 → 排版 → 发布 → 归档** 整条链路自动化。

跑起来之后，你每天早上会得到：

| 产出 | 说明 |
| --- | --- |
| 结构化日报 | 4 个栏目 × N 条，每条附**来源链接** + 一句**「对你的价值」** |
| 公开试读站 | 每栏只放 1 条，天然是引流页，可直接托管在 GitHub Pages |
| RSS 源 | 可被阅读器/聚合站抓取，是被动获客入口 |
| 完整版 + 历史归档 | 留给付费渠道交付 |

## 特性

- **零第三方依赖** —— 只用 `urllib` / `xml` / `json` / `pathlib`。部署时不用 `pip install`，定时任务里就少一个失败点。
- **任意 OpenAI 兼容接口** —— 本机 Ollama、vLLM、Claude Code Router、DeepSeek、OpenAI 都能接。
- **公开版 / 完整版双轨** —— 公开站负责被搜到，完整版负责收钱。
- **强制「对你的价值」字段** —— `Prompt` 里硬性要求每条写一句「对你的价值」，写不出来的条目直接丢弃。这比任何相关性算法都好用：它把「筛选」变成了「能不能写出人话」。
- **失败即停** —— 抓取失败不生成，生成失败不发布，绝不产出半成品。
- **GitHub Contents API 发布** —— 绕开国内 `git push` 常被连接重置（curl 28 / SSL_read）的问题。
- **`--mock` 模式** —— 不花一分钱 token 就能把全流程跑通。

## 快速开始

```bash
git clone https://github.com/yanxiuzi/ai-brief.git
cd ai-brief/generator

cp config.example.json config.json     # 1. 改模型地址 & 信源
export CCR_API_KEY=your_api_key        # 2. 填密钥（Windows: set CCR_API_KEY=...）

python bot.py --mock                   # 3. 先用假数据跑通，不花 token
python bot.py                          # 4. 真跑一期，产出 latest.md / site/
```

发布到 GitHub Pages：

```bash
export GITHUB_TOKEN=ghp_xxx
python publish_api.py
```

## 每天自动运行

**Windows（计划任务）**

```powershell
powershell -ExecutionPolicy Bypass -File .\install_daily_task.ps1 -Time 07:40
```

**Linux / macOS（cron）**

```cron
40 7 * * * cd /path/to/generator && ./run_once.sh
```

> 定时任务有个坑值得记：**注册完一定要回读一次任务状态确认**。写完脚本、看到「已注册」就以为成了，是这套流水线最典型的静默失败。

## 配置说明（config.json）

| 字段 | 作用 |
| --- | --- |
| `llm.base_url` / `llm.model` | OpenAI 兼容接口地址与模型名 |
| `llm.api_key_env` | 读哪个环境变量当密钥 |
| `source_urls` | RSS/Atom 源列表（建议中英各半，减少信息茧房） |
| `sections` / `items_per_section` | 日报栏目与每栏条数 |
| `site.public_items_per_section` | 公开站每栏放几条（试读用） |
| `site.subscribe_url` | 订阅/付费入口链接 |
| `site.base_url` | 站点根地址（用于 RSS 与归档链接） |
| `deliver.webhook_url` | 可选：企业微信/飞书机器人推送 |

## 目录结构

```
generator/
  bot.py                  # 主程序：抓取 → 生成 → 渲染 → 归档
  landing.py              # 生成公开落地页（卖点 / 对比表 / FAQ / 订阅区）
  publish_api.py          # 用 GitHub Contents API 发布静态站
  config.example.json     # 配置模板
  run_once.ps1            # 跑一期 + 发布（Windows）
  install_daily_task.ps1  # 注册每日计划任务
```

## English

**ai-brief-generator** turns any OpenAI-compatible LLM into an unattended daily
content pipeline: fetch RSS → structure → summarize → render → publish a static
site + RSS feed. Zero third-party dependencies (Python stdlib only).
Live demo: https://yanxiuzi.github.io/ai-brief/

## License

MIT
