#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""龙星行最近一周趋势分析"""
import json
from pathlib import Path
from datetime import datetime, timedelta

TRACKING_DIR = Path(__file__).parent / "_tracking"


def tracking_path(store: str, year_month: str) -> Path:
    month_dir = TRACKING_DIR / year_month
    new_path = month_dir / f"{store}.json"
    legacy_path = TRACKING_DIR / f"{store}_{year_month}.json"
    return new_path if new_path.exists() else legacy_path
STORES = ["长沙", "翔鹏", "骏宜"]
today = datetime.now()
# 最近7天
dates = [(today - timedelta(days=i)).strftime("%y%m%d") for i in range(6, -1, -1)]

print("=" * 90)
print(f"龙星行 最近一周趋势分析（{dates[0]} ~ {dates[-1]}）")
print("=" * 90)

for store in STORES:
    fp = tracking_path(store, "2605")
    data = json.loads(fp.read_text(encoding='utf-8'))

    print(f"\n【{store}】")
    print(f"{'日期':<8} {'呼叫通次':>8} {'新增线索':>8} {'接通量':>6} {'有效线索':>8} {'接通率':>8} {'有效率':>8}")
    print("-" * 58)

    week_total = {"呼叫通次": 0, "新增线索量": 0, "接通量": 0, "有效线索量": 0}
    valid_days = 0

    for d in dates:
        row = data.get(d, {})
        calls = row.get("呼叫通次", 0)
        total = row.get("新增线索量", 0)
        jietong = row.get("新增线索接通量", 0)
        youxiao = row.get("有效线索量", 0)

        jietong_rate = f"{jietong/calls*100:.1f}%" if calls > 0 else "-"
        youxiao_rate = f"{youxiao/jietong*100:.1f}%" if jietong > 0 else "-"

        print(f"{d:<8} {calls:>8} {total:>8} {jietong:>6} {youxiao:>8} {jietong_rate:>8} {youxiao_rate:>8}")

        if calls > 0:
            week_total["呼叫通次"] += calls
            week_total["新增线索量"] += total
            week_total["接通量"] += jietong
            week_total["有效线索量"] += youxiao
            valid_days += 1

    # 日均
    if valid_days > 0:
        avg_calls = week_total["呼叫通次"] / valid_days
        avg_total = week_total["新增线索量"] / valid_days
        avg_jietong = week_total["接通量"] / valid_days
        avg_youxiao = week_total["有效线索量"] / valid_days
        avg_jr = f"{week_total['接通量']/week_total['呼叫通次']*100:.1f}%"
        avg_yr = f"{week_total['有效线索量']/week_total['接通量']*100:.1f}%" if week_total['接通量'] > 0 else "-"
        print("-" * 58)
        print(f"{'周均(有效日)':<8} {avg_calls:>8.0f} {avg_total:>8.0f} {avg_jietong:>6.0f} {avg_youxiao:>8.0f} {avg_jr:>8} {avg_yr:>8}")
        print(f"(有效日: {valid_days}/7 天)")

# 三店汇总
print(f"\n{'='*90}")
print("三店合计 一周汇总")
print(f"{'='*90}")
print(f"{'门店':<8} {'总呼叫':>8} {'总线索':>8} {'总接通':>8} {'总有效':>8} {'接通率':>8} {'有效率':>8} {'日均线索':>8}")
print("-" * 70)

grand_totals = {"呼叫通次": 0, "新增线索量": 0, "接通量": 0, "有效线索量": 0}

for store in STORES:
    fp = tracking_path(store, "2605")
    data = json.loads(fp.read_text(encoding='utf-8'))

    store_total = {"呼叫通次": 0, "新增线索量": 0, "接通量": 0, "有效线索量": 0}
    valid_days = 0
    for d in dates:
        row = data.get(d, {})
        calls = row.get("呼叫通次", 0)
        if calls > 0:
            store_total["呼叫通次"] += calls
            store_total["新增线索量"] += row.get("新增线索量", 0)
            store_total["接通量"] += row.get("新增线索接通量", 0)
            store_total["有效线索量"] += row.get("有效线索量", 0)
            valid_days += 1

    avg_daily_xiansuo = store_total["新增线索量"] / valid_days if valid_days > 0 else 0
    jr = f"{store_total['接通量']/store_total['呼叫通次']*100:.1f}%"
    yr = f"{store_total['有效线索量']/store_total['接通量']*100:.1f}%" if store_total['接通量'] > 0 else "-"
    print(f"{store:<8} {store_total['呼叫通次']:>8} {store_total['新增线索量']:>8} {store_total['接通量']:>8} {store_total['有效线索量']:>8} {jr:>8} {yr:>8} {avg_daily_xiansuo:>8.0f}")
    grand_totals["呼叫通次"] += store_total["呼叫通次"]
    grand_totals["新增线索量"] += store_total["新增线索量"]
    grand_totals["接通量"] += store_total["接通量"]
    grand_totals["有效线索量"] += store_total["有效线索量"]

print("-" * 70)
jr_total = f"{grand_totals['接通量']/grand_totals['呼叫通次']*100:.1f}%"
yr_total = f"{grand_totals['有效线索量']/grand_totals['接通量']*100:.1f}%" if grand_totals['接通量'] > 0 else "-"
print(f"{'合计':<8} {grand_totals['呼叫通次']:>8} {grand_totals['新增线索量']:>8} {grand_totals['接通量']:>8} {grand_totals['有效线索量']:>8} {jr_total:>8} {yr_total:>8}")

# 趋势描述
print(f"\n{'='*90}")
print("趋势总结")
print(f"{'='*90}")

for store in STORES:
    fp = tracking_path(store, "2605")
    data = json.loads(fp.read_text(encoding='utf-8'))

    # 取前半周 vs 后半周
    mid = len(dates) // 2
    early = dates[:mid]
    late = dates[mid:]

    def avg_of_dates(date_list, key):
        vals = [data.get(d, {}).get(key, 0) for d in date_list if data.get(d, {}).get("呼叫通次", 0) > 0]
        return sum(vals) / len(vals) if vals else 0

    early_total = avg_of_dates(early, "新增线索量")
    late_total = avg_of_dates(late, "新增线索量")
    early_jr = avg_of_dates(early, "新增线索接通量") / avg_of_dates(early, "呼叫通次") * 100 if avg_of_dates(early, "呼叫通次") > 0 else 0
    late_jr = avg_of_dates(late, "新增线索接通量") / avg_of_dates(late, "呼叫通次") * 100 if avg_of_dates(late, "呼叫通次") > 0 else 0

    trend_xiansuo = "上升" if late_total > early_total else ("下降" if late_total < early_total else "持平")
    trend_jr = "上升" if late_jr > early_jr else ("下降" if late_jr < early_jr else "持平")
    print(f"  {store}：日均线索量 {early_total:.0f}→{late_total:.0f}（{trend_xiansuo}），接通率 {early_jr:.1f}%→{late_jr:.1f}%（{trend_jr}）")

removed_script = Path(__file__).parent / "process_missing_dates.py"
if removed_script.exists():
    removed_script.unlink()

print(f"\n汇总表详见 data/ 下各日期目录的 汇总表/")
