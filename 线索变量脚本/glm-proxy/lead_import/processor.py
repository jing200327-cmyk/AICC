from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta

from .models import StoreScript


class LeadProcessingError(Exception):
    pass


def format_license_plate(plate) -> str:
    if pd.isna(plate):
        return ""
    plate = str(plate).strip()
    if not plate or plate.lower() in ["nan", "null", "none"]:
        return ""
    return plate[0] + "." + plate[1:] if len(plate) >= 2 else plate


def parse_date(date_value) -> str:
    if pd.isna(date_value):
        return ""
    if hasattr(date_value, "strftime"):
        return date_value.strftime("%Y-%m-%d")
    date_str = str(date_value).strip()
    if not date_str or date_str.lower() in ["nan", "nat", "null", "none"]:
        return ""
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y年%m月%d日",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y年%m月%d日 %H:%M:%S",
        "%Y%m%d%H%M%S",
        "%Y%m%d",
        "%Y%m%d.0",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str.split(" ")[0][:10]


def parse_mileage(value) -> str:
    if pd.isna(value):
        return ""
    mileage = str(value).strip()
    if not mileage or mileage.lower() in ["nan", "null", "none"]:
        return ""
    return mileage[:-2] if mileage.endswith(".0") else mileage


def find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in df.columns:
        column_text = str(column)
        if any(candidate in column_text for candidate in candidates):
            return column
    return None


def read_input(input_path: Path) -> pd.DataFrame:
    suffix = input_path.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        with pd.ExcelFile(input_path) as excel:
            return pd.read_excel(excel, sheet_name=excel.sheet_names[0])
    if suffix == ".csv":
        return pd.read_csv(input_path)
    raise LeadProcessingError("Unsupported file type")


def generate_txt(input_path: Path, output_path: Path, store: StoreScript) -> int:
    df = read_input(input_path)
    if df.empty or len(df.columns) == 0:
        raise LeadProcessingError("Input table is empty")

    plate_col = find_column(df, ["车牌号", "车牌"])
    type_col = find_column(df, ["车型", "车系"])
    date_col = find_column(df, ["进厂日期", "进厂时间", "销售日期", "最后进厂", "最后维修日期", "最后保养日期", "上次进厂时间", "日期", "时间"])
    mileage_col = find_column(df, ["进厂行驶里程", "行驶里程", "上次进厂公里数", "进厂里程", "里程", "上次保养里程"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for _, row in df.iterrows():
            last_maintain_time = parse_date(row[date_col]) if date_col and pd.notna(row[date_col]) else ""
            advised_maintain_time = ""
            if last_maintain_time:
                try:
                    advised_maintain_time = (
                        datetime.strptime(last_maintain_time, "%Y-%m-%d") + relativedelta(months=6)
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    advised_maintain_time = ""
            record = {
                "carNo": format_license_plate(row[plate_col]) if plate_col and pd.notna(row[plate_col]) else "",
                "carType": str(row[type_col]).strip() if type_col and pd.notna(row[type_col]) else "",
                "last_maintain_mileage": parse_mileage(row[mileage_col]) if mileage_col and pd.notna(row[mileage_col]) else "",
                "last_maintain_time": last_maintain_time,
                "advised_maintain_time": advised_maintain_time,
                "duration": "6",
                "powerType": "油车",
                "assigned_store": store.store_name,
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count
