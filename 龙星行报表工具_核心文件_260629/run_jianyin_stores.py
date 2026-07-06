#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import subprocess
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUT_DIR = BASE_DIR / "建银门店日报"

NEW_ACCOUNTS = [
    {"name": "售后银马", "username": "jyshym1234", "password": "123456"},
    {"name": "武汉骏马店", "username": "jywhjm12345", "password": "123456wuhanjunma"},
    {"name": "林肯美诚售后", "username": "jyshmc123456", "password": "123456"},
    {"name": "合肥建银马自达店", "username": "jyshmzd", "password": "123456"},
    {"name": "天翔林肯店", "username": "jywhtx", "password": "tx123456"},
]

sys.path.insert(0, str(BASE_DIR / "tools"))
from recorder import crawl


def collect_existing_files(out_dir: Path, date: str, accounts: list[dict]) -> tuple[dict[str, dict[str, Path]], list[dict]]:
    raw_dir = out_dir / "原始数据"
    existing = {}
    accounts_to_crawl = []

    for acc in accounts:
        name = acc["name"]
        clue_file = raw_dir / f"{name}-outcall-线索明细-{date}.xlsx"
        call_file = raw_dir / f"{name}-aicc-话单-{date}.xlsx"
        if clue_file.exists() and call_file.exists():
            existing[name] = {"clue": clue_file, "call": call_file}
        else:
            accounts_to_crawl.append(acc)

    return existing, accounts_to_crawl


def extract_conclusions(text: str, company: str, date: str) -> list[tuple[str, str]]:
    """从 process_clue_report 的完整输出中提取每日报告结论。"""
    lines = text.splitlines()
    starts = [
        i for i, line in enumerate(lines)
        if line.startswith("【") and f" {date}】" in line and "推送新增线索量" in line
    ]
    conclusions = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        for i in range(start + 1, end):
            if lines[i].strip().startswith("=" * 5):
                end = i
                break
        result = "\n".join(lines[start:end]).strip()
        label = lines[start].split("】", 1)[0].lstrip("【")
        if label.endswith(f" {date}"):
            label = label[:-(len(date) + 1)]
        if result:
            conclusions.append((label or company, result))

    if conclusions:
        return conclusions

    return [(company, "")]


def main():
    today = os.environ.get("REPORT_DATE") or datetime.now().strftime("%y%m%d")
    out_dir = OUT_DIR / today

    print("=" * 60)
    print("准备 5 家门店原始数据...")
    print("=" * 60)
    files, accounts_to_crawl = collect_existing_files(out_dir, today, NEW_ACCOUNTS)
    for name, f in files.items():
        print(f"  {name}: 原始数据已存在，跳过爬取")

    if accounts_to_crawl:
        print(f"\n需要爬取 {len(accounts_to_crawl)} 家门店数据...")
        files.update(crawl(out_dir, accounts=accounts_to_crawl))
    else:
        print("\n5 家门店原始数据均已存在，本次不重新爬取。")

    for name, f in files.items():
        print(f"  {name}: clue={f['clue'].name}, call={f['call'].name}")

    print("\n" + "=" * 60)
    print("生成每日报告...")
    print("=" * 60)

    for acc in NEW_ACCOUNTS:
        name = acc["name"]
        f = files.get(name)
        if not f:
            print(f"  {name}: 无爬取结果，跳过")
            continue

        call_file = f["call"]
        clue_file = f["clue"]

        if not call_file.exists():
            print(f"  {name}: 话单文件不存在，跳过")
            continue

        cmd = [
            sys.executable,
            str(BASE_DIR / "tools" / "process_clue_report.py"),
            "--call_file", str(call_file),
            "--company", name,
            "--date", today,
            "--output_dir", str(out_dir),
        ]
        if clue_file.exists():
            cmd += ["--xiansuo_file", str(clue_file)]

        print(f"\n  处理 {name}...")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        full_output = (result.stdout or "") + (result.stderr or "")
        print(full_output, end="")

        if result.returncode != 0:
            print(f"  {name} 处理失败 (exit code {result.returncode})")
        else:
            for report_name, conclusion in extract_conclusions(full_output, name, today):
                txt_path = out_dir / "每日报告" / f"{report_name}_每日报告_{today}.txt"
                txt_path.parent.mkdir(parents=True, exist_ok=True)
                txt_path.write_text(conclusion, encoding="utf-8")
                print(f"  {report_name} 处理完成 ✅ 报告: {txt_path.name}")

    print(f"\n所有报告已保存至: {out_dir}/")


if __name__ == "__main__":
    main()
