# -*- coding: utf-8 -*-
import pandas as pd
import json
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ================= 璇诲彇 Excel =================
df = pd.read_excel(r"E:\ai\workflow\线索变量脚本\建银线索\林肯美诚\260701线索名单.xlsx", sheet_name="Sheet1")
save_path = r'E:\ai\workflow\线索变量脚本\建银线索\林肯美诚\260701线索名单.txt'

print(f"鉁?鎴愬姛璇诲彇Excel鏂囦欢")
print(f"馃搳 鏁版嵁褰㈢姸: {df.shape}")
print(f"馃搵 鍒楀悕: {list(df.columns)}")

output_lines = []


# ================= 宸ュ叿鍑芥暟 =================
def format_license_plate(plate):
    """
    椴乊GJ779 鈫?椴?YGJ779
    """
    if pd.isna(plate):
        return ""

    plate = str(plate).strip()
    if not plate or plate.lower() in ['nan', 'null', 'none']:
        return ""

    return plate[0] + '.' + plate[1:] if len(plate) >= 2 else plate


def parse_date(date_value):
    if pd.isna(date_value):
        return ""

    try:
        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%Y-%m-%d')

        date_str = str(date_value).strip()
        if not date_str or date_str.lower() in ['nan', 'nat', 'null', 'none']:
            return ""

        date_formats = [
            '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
            '%Y年%m月%d日', '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S', '%Y年%m月%d日 %H:%M:%S'
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except:
                pass

        if ' ' in date_str:
            return date_str.split(' ')[0]

        return date_str[:10]

    except:
        return ""


def parse_mileage(mileage_value):
    if pd.isna(mileage_value):
        return ""

    mileage = str(mileage_value).strip()
    if not mileage or mileage.lower() in ['nan', 'null', 'none']:
        return ""

    if mileage.endswith('.0'):
        mileage = mileage[:-2]

    return mileage


# ================= 主处理循环 =================
for index, row in df.iterrows():

    # ---------- 车牌号 ----------
    car_no = ""
    if '车牌号' in df.columns and pd.notna(row['车牌号']):
        car_no = format_license_plate(row['车牌号'])

    # ---------- 车型 ----------
    car_type = ""
    if '车型' in df.columns and pd.notna(row['车型']):
        car_type = str(row['车型']).strip()

    # ---------- 找最后进厂日期 ----------
    last_date_column = None
    possible_date_columns = ['进厂日期', '最后进厂', '最后维修日期', '最后保养日期', '上次进厂时间']

    for col in df.columns:
        for p in possible_date_columns:
            if p in str(col):
                last_date_column = col
                break
        if last_date_column:
            break

    if not last_date_column:
        date_columns = [c for c in df.columns if '日期' in str(c) or '时间' in str(c)]
        if date_columns:
            last_date_column = date_columns[0]

    last_maintain_time = ""
    if last_date_column and pd.notna(row[last_date_column]):
        last_maintain_time = parse_date(row[last_date_column])

    # ---------- 找进厂行驶里程 ----------
    last_maintain_mileage = ""
    possible_mileage_columns = ['进厂行驶里程', '行驶里程', '上次进厂公里数', '里程']

    mileage_column = None
    for col in df.columns:
        for p in possible_mileage_columns:
            if p in str(col):
                mileage_column = col
                break
        if mileage_column:
            break

    if mileage_column and pd.notna(row[mileage_column]):
        last_maintain_mileage = parse_mileage(row[mileage_column])

    # ---------- 计算 6 个月后 ----------
    advised_maintain_time = ""
    if last_maintain_time:
        try:
            last_date = datetime.strptime(last_maintain_time, '%Y-%m-%d')
            advised_maintain_time = (last_date + relativedelta(months=6)).strftime('%Y-%m-%d')
        except:
            pass

    # ---------- 生成记录 ----------
    record = {
        "carNo": car_no,
        "carType": car_type,
        "last_maintain_mileage": last_maintain_mileage,
        "last_maintain_time": last_maintain_time,
        "advised_maintain_time": advised_maintain_time,
        "duration": "6",
        "powerType": "油车",
        "assigned_store": "林肯美诚店"
    }

    output_lines.append(json.dumps(record, ensure_ascii=False, separators=(',', ':')))


# ================= 保存文件 =================
os.makedirs(os.path.dirname(save_path), exist_ok=True)

with open(save_path, 'w', encoding='utf-8') as f:
    for line in output_lines:
        f.write(line + '\n')

print(f"\n成功：数据已保存到 {save_path}")
print(f"共生成 {len(output_lines)} 条记录")

print("\n前 5 条数据预览：")
for i, line in enumerate(output_lines[:5]):
    print(f"{i + 1}: {line}")
