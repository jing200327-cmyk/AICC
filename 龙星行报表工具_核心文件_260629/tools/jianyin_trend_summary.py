#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
JY_DIR = BASE_DIR / "建银门店日报"
STORES = ["售后银马", "武汉骏马店", "林肯美诚售后", "合肥建银马自达店", "天翔林肯店"]


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%y%m%d")


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.00%"
    return f"{numerator / denominator * 100:.2f}%"


def read_report(store: str, date_key: str) -> dict | None:
    path = JY_DIR / date_key / "每日报告" / f"{store}_每日报告_{date_key}.txt"
    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8", errors="ignore")
    new_match = re.search(r"推送新增线索量\s*(\d+)\s*条", text)
    connected_match = re.search(r"①\s*接通线索\s*(\d+)\s*条", text)
    intent_match = re.search(r"-\s*意向线索（(\d+)\s*条", text)

    top_reasons = []
    in_top = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("未接通原因TOP3"):
            in_top = True
            continue
        if in_top:
            if not line or line.startswith("③") or line.startswith("="):
                break
            reason_match = re.match(r"-\s*(.+?)：(\d+)\s*条", line)
            if reason_match:
                top_reasons.append((reason_match.group(1), int(reason_match.group(2))))

    new_count = int(new_match.group(1)) if new_match else 0
    connected_count = int(connected_match.group(1)) if connected_match else 0
    intent_count = int(intent_match.group(1)) if intent_match else 0

    return {
        "date": date_key,
        "store": store,
        "new": new_count,
        "connected": connected_count,
        "intent": intent_count,
        "connect_rate": pct(connected_count, new_count),
        "intent_rate": pct(intent_count, connected_count),
        "top_reasons": top_reasons,
        "path": path,
    }


def fmt_reasons(reasons: list[tuple[str, int]]) -> str:
    if not reasons:
        return "无"
    return "；".join(f"{reason} {count}" for reason, count in reasons)


def trend_arrow(values: list[int]) -> str:
    if not values:
        return "无数据"
    return " -> ".join(str(v) for v in values)


def rate_arrow(values: list[str]) -> str:
    if not values:
        return "无数据"
    return " -> ".join(values)


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总建银 5 店每日指标和近三天趋势")
    parser.add_argument("--date", default=datetime.now().strftime("%y%m%d"), help="报告日期，格式 YYMMDD")
    args = parser.parse_args()

    end = parse_date(args.date)
    dates = [(end - timedelta(days=offset)).strftime("%y%m%d") for offset in range(2, -1, -1)]
    today_key = args.date

    print(f"# 建银 5 店 {today_key} 每日指标与近三天趋势")
    print()
    print("口径：接通率=接通线索/新增线索；意向率=意向线索/接通线索。")
    print()

    print("## 今日指标")
    print("| 门店 | 新增 | 接通 | 意向 | 接通率 | 意向率 | TOP未接通原因 |")
    print("|---|---:|---:|---:|---:|---:|---|")
    for store in STORES:
        report = read_report(store, today_key)
        if report is None:
            print(f"| {store} | 缺报告 |  |  |  |  |  |")
            continue
        print(
            f"| {store} | {report['new']} | {report['connected']} | {report['intent']} | "
            f"{report['connect_rate']} | {report['intent_rate']} | {fmt_reasons(report['top_reasons'])} |"
        )

    print()
    print("## 近三天趋势")
    print(f"日期顺序：{' -> '.join(dates)}")
    print()
    for store in STORES:
        reports = [read_report(store, date_key) for date_key in dates]
        existing = [item for item in reports if item is not None]
        if not existing:
            print(f"- {store}: 近三天缺少报告。")
            continue

        new_values = [item["new"] if item else 0 for item in reports]
        connected_values = [item["connected"] if item else 0 for item in reports]
        intent_values = [item["intent"] if item else 0 for item in reports]
        connect_rates = [item["connect_rate"] if item else "缺" for item in reports]
        intent_rates = [item["intent_rate"] if item else "缺" for item in reports]

        print(
            f"- {store}: 新增 {trend_arrow(new_values)}；接通 {trend_arrow(connected_values)}；"
            f"意向 {trend_arrow(intent_values)}；接通率 {rate_arrow(connect_rates)}；"
            f"意向率 {rate_arrow(intent_rates)}。"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
