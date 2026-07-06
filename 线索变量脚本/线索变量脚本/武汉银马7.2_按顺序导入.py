import argparse
import json
import os
from datetime import datetime

import pandas as pd
from dateutil.relativedelta import relativedelta


EXCEL_PATH = r"E:\ai\workflow\线索变量脚本\建银线索\武汉银马\2026年7月招揽(定期保养+流失+质保到期) -.xlsx"
OUTPUT_DIR = r"E:\ai\workflow\线索变量脚本\建银线索\武汉银马"
DEFAULT_SHEET = "定期保养"

SORT_MONTH_ORDER = {
    "2025-11": 1,
    "2026-01": 2,
    "2025-12": 3,
    "2025-08": 4,
    "2025-09": 5,
    "2025-10": 6,
}


def format_license_plate(plate):
    if pd.isna(plate):
        return ""

    plate = str(plate).strip()
    if not plate or plate.lower() in ["nan", "null", "none"]:
        return ""

    return plate[0] + "." + plate[1:] if len(plate) >= 2 else plate


def parse_date(date_value):
    if pd.isna(date_value):
        return ""

    try:
        if hasattr(date_value, "strftime"):
            return date_value.strftime("%Y-%m-%d")

        date_str = str(date_value).strip()
        if not date_str or date_str.lower() in ["nan", "nat", "null", "none"]:
            return ""

        date_formats = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
            "%Y年%m月%d日", "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S", "%Y年%m月%d日 %H:%M:%S"
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass

        if " " in date_str:
            return date_str.split(" ")[0]

        return date_str[:10]

    except Exception:
        return ""


def parse_mileage(mileage_value):
    if pd.isna(mileage_value):
        return ""

    mileage = str(mileage_value).strip()
    if not mileage or mileage.lower() in ["nan", "null", "none"]:
        return ""

    if mileage.endswith(".0"):
        mileage = mileage[:-2]

    return mileage


def choose_sheet(excel_path, requested_sheet=None):
    excel_file = pd.ExcelFile(excel_path)
    sheet_names = excel_file.sheet_names

    if requested_sheet:
        if requested_sheet in sheet_names:
            return requested_sheet
        matches = [name for name in sheet_names if requested_sheet in name]
        if len(matches) == 1:
            return matches[0]
        raise ValueError(f"未找到唯一匹配的sheet: {requested_sheet}; 可选sheet: {sheet_names}")

    if len(sheet_names) == 1:
        return sheet_names[0]

    print("检测到当前Excel包含多个sheet，请确认本次线索导入处理哪个sheet：")
    for i, name in enumerate(sheet_names, start=1):
        print(f"{i}. {name}")

    choice = input(f"请输入sheet序号或名称，直接回车默认处理 {DEFAULT_SHEET}: ").strip()
    if not choice:
        return DEFAULT_SHEET

    if choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(sheet_names):
            return sheet_names[index]

    if choice in sheet_names:
        return choice

    matches = [name for name in sheet_names if choice in name]
    if len(matches) == 1:
        return matches[0]

    raise ValueError(f"无法识别sheet选择: {choice}")


def find_date_column(df):
    possible_date_columns = ["进厂日期", "进厂时间", "销售日期", "最后保养日期"]

    for col in df.columns:
        for possible in possible_date_columns:
            if possible in str(col):
                return col

    date_columns = [col for col in df.columns if "日期" in str(col) or "时间" in str(col)]
    return date_columns[0] if date_columns else None


def find_mileage_column(df):
    possible_mileage_columns = ["进厂行驶里程", "行驶里程", "进厂里程", "里程"]

    for col in df.columns:
        for possible in possible_mileage_columns:
            if possible in str(col):
                return col

    return None


def sort_by_import_order(df, date_column):
    if not date_column:
        print("未找到日期列，跳过按年月排序")
        return df

    sort_date = pd.to_datetime(df[date_column], errors="coerce")
    sort_month = sort_date.dt.strftime("%Y-%m")
    sort_order = sort_month.map(SORT_MONTH_ORDER).fillna(999).astype(int)

    extra_months = sorted(month for month in sort_month.dropna().unique() if month not in SORT_MONTH_ORDER)
    invalid_count = int(sort_date.isna().sum())

    sorted_df = (
        df.assign(_sort_date=sort_date, _sort_order=sort_order)
        .sort_values(["_sort_order", "_sort_date"], ascending=[True, True], kind="mergesort")
        .drop(columns=["_sort_date", "_sort_order"])
        .reset_index(drop=True)
    )

    print(f"已按 {date_column} 排序，年月顺序: 2025-11 -> 2026-01 -> 2025-12 -> 2025-08 -> 2025-09 -> 2025-10 -> 其它年月")
    print(f"其它年月: {extra_months if extra_months else '无'}")
    print(f"无法识别日期行数: {invalid_count}")
    return sorted_df


def build_records(df):
    output_lines = []
    last_date_column = find_date_column(df)
    mileage_column = find_mileage_column(df)

    print(f"本次使用日期列: {last_date_column if last_date_column else '未找到'}")
    print(f"本次使用里程列: {mileage_column if mileage_column else '未找到'}")

    for _, row in df.iterrows():
        car_no = ""
        if "车牌号" in df.columns and pd.notna(row["车牌号"]):
            car_no = format_license_plate(row["车牌号"])

        car_type = ""
        if "车型" in df.columns and pd.notna(row["车型"]):
            car_type = str(row["车型"]).strip()
        elif "车系" in df.columns and pd.notna(row["车系"]):
            car_type = str(row["车系"]).strip()

        last_maintain_time = ""
        if last_date_column and pd.notna(row[last_date_column]):
            last_maintain_time = parse_date(row[last_date_column])

        last_maintain_mileage = ""
        if mileage_column and pd.notna(row[mileage_column]):
            last_maintain_mileage = parse_mileage(row[mileage_column])

        advised_maintain_time = ""
        if last_maintain_time:
            try:
                last_date = datetime.strptime(last_maintain_time, "%Y-%m-%d")
                advised_maintain_time = (last_date + relativedelta(months=6)).strftime("%Y-%m-%d")
            except Exception:
                pass

        record = {
            "carNo": car_no,
            "carType": car_type,
            "last_maintain_mileage": last_maintain_mileage,
            "last_maintain_time": last_maintain_time,
            "advised_maintain_time": advised_maintain_time,
            "duration": "6",
            "powerType": "油车",
            "assigned_store": "武汉银马店"
        }
        output_lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))

    return output_lines


def safe_filename(name):
    for char in '<>:"/\\|?*':
        name = name.replace(char, "_")
    return name


def process_sheet(sheet_name, output_path=None):
    df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name)
    print(f"成功读取Excel文件: {EXCEL_PATH}")
    print(f"处理sheet: {sheet_name}")
    print(f"数据形状: {df.shape}")
    print(f"列名: {list(df.columns)}")

    date_column = find_date_column(df)
    df = sort_by_import_order(df, date_column)
    output_lines = build_records(df)

    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, f"2026年7月招揽_{safe_filename(sheet_name)}.txt")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for line in output_lines:
            f.write(line + "\n")

    print(f"数据已保存到 {output_path}")
    print(f"共生成 {len(output_lines)} 条记录")
    print("前5条数据预览:")
    for i, line in enumerate(output_lines[:5], start=1):
        print(f"{i}: {line}")

    return output_path, len(output_lines)


def main():
    parser = argparse.ArgumentParser(description="武汉银马线索变量导出脚本")
    parser.add_argument("--sheet", help="要处理的sheet名称；支持输入唯一片段，如 首保")
    parser.add_argument("--output", help="输出txt路径；不传则按sheet名称自动生成")
    args = parser.parse_args()

    sheet_name = choose_sheet(EXCEL_PATH, args.sheet)
    process_sheet(sheet_name, args.output)


if __name__ == "__main__":
    main()
