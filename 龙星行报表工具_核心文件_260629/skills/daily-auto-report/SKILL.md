---
name: daily-auto-report
description: Run the Longxinghang and Jianyin daily reporting workflow for the local report project. Use when the user asks to crawl or produce daily reports, daily summary workbooks, Jianyin 5-store daily metrics, top missed-call reasons, or three-day trend feedback for 龙星行/建银报表数据.
---

# Daily Auto Report

## Project

Work in:

`/Users/tangtangtang/工作/冰兰智能/龙星行-报表数据/报告产出脚本`

Use the project virtualenv:

`venv/bin/python`

## Daily Workflow

1. Run Longxinghang:
   `venv/bin/python main.py`
2. Run Jianyin:
   `venv/bin/python run_jianyin_stores.py`
3. Generate Jianyin feedback:
   `venv/bin/python tools/jianyin_trend_summary.py --date YYMMDD`

Use the current Asia/Shanghai date as `YYMMDD` unless the user specifies another date.

## Required Feedback

After the daily run, report:

- Output paths for 龙星行 and 建银 `每日报告` / `汇总表`.
- For 建银 5 店: 每日新增、接通、意向、接通率、意向率、TOP 未接通原因.
- For 建银 5 店: 近三天趋势, ordered oldest to newest.

Metric definitions:

- 接通率 = 接通线索 / 新增线索.
- 意向率 = 意向线索 / 接通线索.

## Operational Notes

- `recorder` skips a store when both same-day raw clue and call files already exist.
- If crawling times out or download clicks hang, rerun the same daily workflow; existing raw files should be skipped and missing files retried.
- Longxinghang `main.py` must check 长沙 after the normal run. If the 长沙 call file or daily report is missing, it should automatically crawl 长沙 once more and regenerate the report/summary when the call file becomes available.
- Keep warnings visible in the final feedback when scripts print unmatched data, validation exceptions, or missing reports.

See [references/workflow.md](references/workflow.md) for output folders and command details.
