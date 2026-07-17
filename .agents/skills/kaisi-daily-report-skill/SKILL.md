---
name: kaisi-daily-report
description: Generate 开思 failed-activation outbound-call daily reports from CSV exports, including report.json, Markdown 日报, and onepage HTML/PNG. Use when the user provides 开思/战败激活/未活跃客户激活外呼 call-detail CSV data and asks for 日报, 阶段日报, onepage, VOC, Buy-in, 抗拒点, 漏斗, or Good Case output.
---

# 开思日报生成

## Use When

Use this skill when the task is to turn a 开思 outbound-call detail CSV into a fixed-format daily report:

- `report.json`: structured metrics and VOC tags
- Markdown 日报
- onepage HTML
- onepage PNG

The user may describe the data as 开思、战败激活、未活跃客户激活外呼、正式 POC 数据、外呼明细、结果 CSV.

## Required Inputs

Ask for or infer these values:

- Input CSV path
- Report date, format `YYYY-MM-DD`
- Cutoff time, format `HH:MM`
- Optional title, default `开思未活跃客户激活外呼`
- Optional output directory

The CSV should contain these columns:

```text
通话ID
客户姓名
呼叫号码
客户真实号码
通话时长
通话状态
对话内容
质检结果
小结
```

## Generate

Run the bundled generator:

```bash
python3 <skill_dir>/scripts/run_daily.py \
  --input <csv_path> \
  --date <YYYY-MM-DD> \
  --cutoff <HH:MM> \
  --title 开思未活跃客户激活外呼
```

Use `--output-dir <dir>` when the user wants outputs in a specific folder. Without `--output-dir`, the script writes to:

```text
<skill_dir>/outputs/<date>/
```

The script generates:

```text
report.json
开思MM.DD截止HH点MM外呼日报.md
开思MM.DD截止HH点MM外呼进度汇报onepage.html
开思MM.DD截止HH点MM外呼进度汇报onepage.png
```

## Reporting Rules

Core funnel:

- 呼出: all CSV rows
- 接通: `通话状态` starts with `已接通`
- 未接通: `通话状态` starts with `未接通`
- 有效/无效/待定: extracted from `客户线索状态` in `质检结果` or `小结`
- 接通后待定: pending rows among connected rows only
- Unknown line status is kept as `未判定` and reported separately when relevant

VOC:

- 有效客户: analyze `Buy-in 点` only
- 待定/无效客户: analyze `抗拒点`
- Do not present effective-customer objection analysis as a main conclusion
- `未知` is excluded from explicit-label percentage denominators but should be kept in notes

Good Case:

- Select from effective leads
- Include `CallID`
- Include masked phone number, e.g. `15160444333 -> 151****4333`
- Prefer cases with clear follow-up value: 微信承接、平台回看/自助查询、活动/优惠兴趣、配件需求场景

## Validate

After generation, check these artifacts exist:

```text
report.json
*.md
*onepage.html
*onepage.png
```

Then compile the scripts:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/kaisi_pycache \
python3 -m py_compile <skill_dir>/scripts/run_daily.py <skill_dir>/scripts/render_html.py
```

If PNG generation fails, the likely cause is missing Playwright/Chromium. The HTML and Markdown can still be used. When installation is allowed, install:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

## Response Style

When reporting completion to the user, give the generated file paths and the top-line metrics. Keep the explanation concise unless the user asks for audit details.
