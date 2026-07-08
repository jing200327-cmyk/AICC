#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
import subprocess
import os
from datetime import datetime
from pathlib import Path

# Windows console encoding fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def get_base_dir() -> Path:
    """Return the project directory even when __file__ is unavailable."""
    file_name = globals().get("__file__")
    if file_name:
        return Path(file_name).resolve().parent

    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and argv0 not in ("-c", ""):
        argv_path = Path(argv0)
        if argv_path.exists():
            return argv_path.resolve().parent

    return Path.cwd().resolve()


BASE_DIR = get_base_dir()
TOOLS_DIR = BASE_DIR.joinpath("tools")

sys.path.insert(0, str(TOOLS_DIR))
from recorder import crawl, ACCOUNTS


def extract_conclusions(text: str, company: str, date: str) -> list[tuple[str, str]]:
    """从 process_clue_report 的完整输出中提取一个或多个结论部分"""
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


def process_account(acc: dict, files: dict[str, Path], today: str, out_dir: Path, report_dir: Path) -> bool:
    name = acc["name"]
    if not files:
        print(f"  {name}: 无爬取结果，跳过")
        return False

    clue_file = files["clue"]
    call_file = files["call"]

    if not call_file.exists():
        print(f"  {name}: 话单文件不存在，跳过")
        return False

    cmd = [
        sys.executable,
        str(TOOLS_DIR.joinpath("process_clue_report.py")),
        "--call_file", str(call_file),
        "--company", name,
        "--date", today,
        "--output_dir", str(out_dir),
    ]
    if clue_file.exists():
        cmd += ["--xiansuo_file", str(clue_file)]
    if acc.get("group_by_call_field"):
        cmd += ["--group_by_call_field", acc["group_by_call_field"]]
    if acc.get("exclude_clue_ids"):
        cmd += ["--exclude_clue_ids", ",".join(acc["exclude_clue_ids"])]
    if acc.get("mtd_start_date"):
        cmd += ["--mtd_start_date", acc["mtd_start_date"]]
    if acc.get("required_group_values"):
        cmd += ["--required_group_values", ",".join(acc["required_group_values"])]
    if acc.get("merge_summary_title"):
        cmd += ["--merge_summary_title", acc["merge_summary_title"]]
    if acc.get("group_display_names"):
        cmd += [
            "--group_display_names",
            json.dumps(acc["group_display_names"], ensure_ascii=False),
        ]
    if acc.get("group_summary_names"):
        cmd += [
            "--group_summary_names",
            json.dumps(acc["group_summary_names"], ensure_ascii=False),
        ]

    print(f"\n  处理 {name}...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    full_output = (result.stdout or "") + (result.stderr or "")
    print(full_output, end="")

    if result.returncode != 0:
        print(f"  {name} 处理失败 (exit code {result.returncode})")
        return False

    wrote_report = False
    for report_name, conclusion in extract_conclusions(full_output, name, today):
        txt_path = report_dir / f"{report_name}_每日报告_{today}.txt"
        txt_path.write_text(conclusion, encoding="utf-8")
        print(f"  {report_name} 处理完成 ✅ 报告: {txt_path.name}")
        wrote_report = True
    return wrote_report



def select_accounts() -> list[dict]:
    store = (os.environ.get("REPORT_STORE") or "all").strip()
    if not store or store.lower() == "all" or store == "所有":
        return ACCOUNTS

    selected = [acc for acc in ACCOUNTS if acc.get("name") == store]
    if not selected:
        available = "、".join(acc.get("name", "") for acc in ACCOUNTS)
        raise ValueError(f"REPORT_STORE={store} 未在 ACCOUNTS 中配置，可选门店：{available}")
    return selected

def retry_changsha_if_needed(files: dict, today: str, out_dir: Path, report_dir: Path) -> None:
    changsha = next((acc for acc in ACCOUNTS if acc["name"] == "长沙"), None)
    if changsha is None:
        return

    raw_dir = out_dir / "原始数据"
    call_file = raw_dir / f"长沙-aicc-话单-{today}.xlsx"
    clue_file = raw_dir / f"长沙-outcall-线索明细-{today}.xlsx"
    report_file = report_dir / f"长沙_每日报告_{today}.txt"

    if call_file.exists() and report_file.exists():
        print("\n长沙检查：话单和日报均已产出，无需重爬。")
        return

    missing = []
    if not call_file.exists():
        missing.append("话单")
    if not report_file.exists():
        missing.append("日报")
    print(f"\n长沙检查：缺少{'、'.join(missing)}，自动单独重爬一次长沙...")

    retry_files = crawl(out_dir, accounts=[changsha])
    if retry_files.get("长沙"):
        files["长沙"] = retry_files["长沙"]
        process_account(changsha, retry_files["长沙"], today, out_dir, report_dir)

    if call_file.exists() and report_file.exists():
        print("长沙检查：重爬后已补齐话单和日报。")
    else:
        print("长沙检查：重爬后仍未补齐，请稍后再试或检查平台导出接口。")


def main():
    today = os.environ.get("REPORT_DATE") or datetime.now().strftime("%y%m%d")
    out_dir = BASE_DIR.joinpath("data", today)
    accounts = select_accounts()

    # === Step 1: 爬取数据 ===
    print("=" * 60)
    print(f"Step 1/2: 爬取数据 → {out_dir}/")
    print("=" * 60)
    files = crawl(out_dir, accounts=accounts)
    for name, f in files.items():
        print(f"  {name}: clue={f['clue'].name}, call={f['call'].name}")

    # === Step 2: 数据处理与报表生成 ===
    print("\n" + "=" * 60)
    print("Step 2/2: 处理数据生成报告")
    print("=" * 60)

    report_dir = out_dir.joinpath("每日报告")
    report_dir.mkdir(parents=True, exist_ok=True)

    for acc in accounts:
        name = acc["name"]
        process_account(acc, files.get(name), today, out_dir, report_dir)

    if any(acc.get("name") == "长沙" for acc in accounts):
        retry_changsha_if_needed(files, today, out_dir, report_dir)


if __name__ == "__main__":
    main()
