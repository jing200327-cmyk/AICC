import pandas as pd
import json
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ================= 读取 Excel =================
df = pd.read_excel(r"/Users/tangtangtang/工作/冰兰智能/建银-线索处理/骏马众城/华腾5-11月.xlsx")

print(f"✅ 成功读取Excel文件")
print(f"📊 数据形状: {df.shape}")
print(f"📋 列名: {list(df.columns)}")

output_lines = []


# ================= 工具函数 =================
def format_license_plate(plate):
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
    elif '车牌' in df.columns and pd.notna(row['车牌']):
        car_no = format_license_plate(row['车牌'])

    # ---------- 车系/车型 ----------
    car_type = ""
    if '车系' in df.columns and pd.notna(row['车系']):
        car_type = str(row['车系']).strip()
    elif '车型' in df.columns and pd.notna(row['车型']):
        car_type = str(row['车型']).strip()

    # ---------- 进厂行驶里程 ----------
    last_maintain_mileage = ""
    if '进厂行驶里程' in df.columns and pd.notna(row['进厂行驶里程']):
        last_maintain_mileage = parse_mileage(row['进厂行驶里程'])

    # ---------- 进厂日期 ----------
    last_maintain_time = ""
    if '进厂时间' in df.columns and pd.notna(row['进厂时间']):
        last_maintain_time = parse_date(row['进厂时间'])
    elif '日期' in df.columns and pd.notna(row['日期']):
        last_maintain_time = parse_date(row['日期'])

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
        "assigned_store": "骏马众诚店"
    }

    output_lines.append(json.dumps(record, ensure_ascii=False, separators=(',', ':')))


# ================= 保存文件 =================
save_path = r'/Users/tangtangtang/工作/冰兰智能/建银-线索处理/骏马众城/华腾5-11月.txt'
os.makedirs(os.path.dirname(save_path), exist_ok=True)

with open(save_path, 'w', encoding='utf-8') as f:
    for line in output_lines:
        f.write(line + '\n')

print(f"\n✅ 数据已保存到 {save_path}")
print(f"📊 共生成 {len(output_lines)} 条记录")

print("\n📄 前5条数据预览：")
for i, line in enumerate(output_lines[:5]):
    print(f"{i + 1}: {line}")