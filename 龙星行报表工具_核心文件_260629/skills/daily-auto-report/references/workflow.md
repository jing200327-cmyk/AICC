# Daily Report Workflow Reference

## Commands

Run from:

`/Users/tangtangtang/工作/冰兰智能/龙星行-报表数据/报告产出脚本`

Longxinghang:

`venv/bin/python main.py`

After the normal Longxinghang run, `main.py` performs a 长沙 completeness check. If the 长沙 AICC call file or daily report is missing, it automatically retries only 长沙 once and reruns report generation for 长沙 when possible.

Jianyin:

`venv/bin/python run_jianyin_stores.py`

Jianyin trend feedback:

`venv/bin/python tools/jianyin_trend_summary.py --date YYMMDD`

## Output Folders

Longxinghang:

- `data/YYMMDD/每日报告`
- `data/YYMMDD/汇总表`

Jianyin:

- `建银门店日报/YYMMDD/每日报告`
- `建银门店日报/YYMMDD/汇总表`

## Jianyin Stores

- 售后银马
- 武汉骏马店
- 林肯美诚售后
- 合肥建银马自达店
- 天翔林肯店

## Final Response Shape

Keep the final response concise:

1. State whether both daily jobs completed.
2. Link the four output folders.
3. Paste the output from `tools/jianyin_trend_summary.py`.
4. Mention any warnings or failed/missing files.
