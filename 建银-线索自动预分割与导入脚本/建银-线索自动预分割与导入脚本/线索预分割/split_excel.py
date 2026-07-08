import pandas as pd
import os
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime

# ========================== 配置参数 ==========================

# 切分单位数量（每多少行切分为一个文件）
CHUNK_SIZE = 45

# 获取当前脚本所在的文件夹（绝对路径）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 最终文件列表（全部自动拼接）
INPUT_FILES = [
    os.path.join(SCRIPT_DIR, "银马-模板.xlsx"),
    os.path.join(SCRIPT_DIR, "武汉骏马-模板.xlsx"),
    os.path.join(SCRIPT_DIR, "美诚林肯-模板.xlsx"),
    os.path.join(SCRIPT_DIR, "合肥马自达-模板.xlsx"),
    os.path.join(SCRIPT_DIR, "天翔林肯-模板.xlsx"),
]

# 序号起始值
START_NUMBER = 2
# 是否创建测试文件（取前几行数据单独生成一个文件）
CREATE_TEST_FILE = True
# 测试文件的行数
TEST_FILE_ROWS = 5

# ========================== 函数定义 ==========================

PHONE_PATTERN = re.compile(r"1\d{10}|0\d{2,3}-?\d{7,8}|0\d{9,11}")
MULTI_PHONE_SEPARATOR_PATTERN = re.compile(r"[,，、;；/\\|\r\n\t]+")


def extract_first_phone(phone_str):
    phone_text = (
        phone_str
        .replace("－", "-")
        .replace("—", "-")
        .replace("–", "-")
    )
    compact_text = re.sub(r"[\s\u3000]+", "", phone_text)

    match = PHONE_PATTERN.search(compact_text)
    if match:
        return match.group(0)

    for part in MULTI_PHONE_SEPARATOR_PATTERN.split(phone_text):
        part = re.sub(r"[\s\u3000]+", "", part)
        if part:
            return part

    return compact_text

def normalize_phone(phone):
    if pd.isna(phone):
        return ""

    phone_str = str(phone).strip()
    if not phone_str:
        return ""

    phone_str = extract_first_phone(phone_str)

    numeric_text = phone_str.replace(",", "")
    if re.fullmatch(r"[+-]?\d+(\.\d+)?([eE][+-]?\d+)?", numeric_text) and not re.fullmatch(r"[+-]?0\d+", numeric_text):
        try:
            number = Decimal(numeric_text)
            if number == number.to_integral_value():
                return format(number.quantize(Decimal(1)), "f")
        except InvalidOperation:
            pass

    return phone_str


def is_valid_phone(phone):
    phone_str = normalize_phone(phone)
    if not phone_str:
        return False

    digits = re.sub(r"\D", "", phone_str)

    # 手机号：1 开头，共 11 位。
    if re.fullmatch(r"1\d{10}", digits):
        return True

    # 座机号：允许 10、11、12 位数字，可带区号分隔符，如 027-84459325。
    if phone_str.startswith("0") and 10 <= len(digits) <= 12:
        return True

    return False

def split_excel(input_file, chunk_size=CHUNK_SIZE, start_number=START_NUMBER, create_test_file=CREATE_TEST_FILE):
    if not os.path.exists(input_file):
        print(f"错误: 文件不存在 - {input_file}")
        return

    df = pd.read_excel(input_file, converters={'被叫号码': normalize_phone, '客户真实手机号': normalize_phone})
    total_rows = len(df)

    # 1. 校验列名
    required_columns = ['客户姓氏', '被叫号码', '客户真实手机号', '意向车型', '来源平台', '变量']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"错误: 缺少必要列 - {missing_columns}")
        return
    print("列名校验通过！")

    # 将号码列转为文本格式，兼容 Excel 数字/科学计数法显示。
    df['被叫号码'] = df['被叫号码'].apply(normalize_phone)
    df['客户真实手机号'] = df['客户真实手机号'].apply(normalize_phone)
    print("号码列已转为文本格式")

    base_name = os.path.splitext(os.path.basename(input_file))[0].split('-')[0]
    output_dir = os.path.dirname(input_file)

    # 创建当日文件夹（YYDD格式）
    today = datetime.now()
    daily_folder = today.strftime("%y%m%d")
    output_dir = os.path.join(output_dir, daily_folder)
    os.makedirs(output_dir, exist_ok=True)

    output_name_template = base_name + "-{n}"
    test_file_name = output_name_template.replace("-{n}", "-测试")

    print(f"输入文件: {input_file}")
    print(f"总行数: {total_rows}")
    print(f"输出目录: {output_dir}")


    test_file_count = 0
    total_invalid = 0

    # 处理测试文件
    if create_test_file and total_rows > TEST_FILE_ROWS:
        test_df = df.iloc[:TEST_FILE_ROWS]
        test_file_path = os.path.join(output_dir, f"{test_file_name}.xlsx")
        
        # 检查测试文件是否已存在
        if os.path.exists(test_file_path):
            print(f"\n⚠️  警告: 测试文件已存在 - {test_file_path}")
            confirm = input("是否覆盖？(y/N): ")
            if confirm.lower() != 'y':
                print("操作已取消")
                return
        
        # 校验测试文件中的手机号
        test_invalid = []
        test_valid_df = pd.DataFrame()
        
        for idx, row in test_df.iterrows():
            if not is_valid_phone(row['被叫号码']) or not is_valid_phone(row['客户真实手机号']):
                test_invalid.append({
                    '行号': idx + 2,  # Excel行号从2开始
                    '客户姓氏': row['客户姓氏'],
                    '被叫号码': row['被叫号码'],
                    '客户真实手机号': row['客户真实手机号']
                })
            else:
                test_valid_df = pd.concat([test_valid_df, pd.DataFrame([row])], ignore_index=True)
        
        if test_invalid:
            print(f"\n⚠️  测试文件中发现 {len(test_invalid)} 条无效手机号记录，将被剔除：")
            for rec in test_invalid:
                print(f"  行{rec['行号']}: {rec['客户姓氏']} - 被叫: {rec['被叫号码']}, 手机: {rec['客户真实手机号']}")
            total_invalid += len(test_invalid)
        
        test_valid_df.to_excel(test_file_path, index=False)
        print(f"测试文件: {test_file_path} (有效记录: {len(test_valid_df)})")
        test_file_count = 1

    # 处理剩余数据
    remaining_df = df.iloc[TEST_FILE_ROWS:] if create_test_file and total_rows > TEST_FILE_ROWS else df
    remaining_rows = len(remaining_df)
    num_files = (remaining_rows + chunk_size - 1) // chunk_size if remaining_rows > 0 else 0

    print(f"每文件行数: {chunk_size}")
    print(f"将生成文件数: {num_files}")
    print()

    for i in range(num_files):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, remaining_rows)
        chunk_df = remaining_df.iloc[start_idx:end_idx]

        # 校验并剔除无效记录
        chunk_invalid = []
        chunk_valid_df = pd.DataFrame()
        
        for idx, row in chunk_df.iterrows():
            excel_row = idx + 2  # Excel行号从2开始
            if not is_valid_phone(row['被叫号码']) or not is_valid_phone(row['客户真实手机号']):
                chunk_invalid.append({
                    '行号': excel_row,
                    '客户姓氏': row['客户姓氏'],
                    '被叫号码': row['被叫号码'],
                    '客户真实手机号': row['客户真实手机号']
                })
            else:
                chunk_valid_df = pd.concat([chunk_valid_df, pd.DataFrame([row])], ignore_index=True)
        
        if chunk_invalid:
            print(f"\n⚠️  文件 {i+1} 中发现 {len(chunk_invalid)} 条无效手机号记录，将被剔除：")
            for rec in chunk_invalid:
                print(f"  行{rec['行号']}: {rec['客户姓氏']} - 被叫: {rec['被叫号码']}, 手机: {rec['客户真实手机号']}")
            total_invalid += len(chunk_invalid)
        
        output_name = output_name_template.format(n=start_number + i)
        output_file = os.path.join(output_dir, f"{output_name}.xlsx")
        
        # 检查文件是否已存在
        if os.path.exists(output_file):
            print(f"\n⚠️  警告: 文件已存在 - {output_file}")
            confirm = input("是否覆盖？(y/N): ")
            if confirm.lower() != 'y':
                print("操作已取消")
                return
        
        chunk_valid_df.to_excel(output_file, index=False)
        print(f"已生成: {output_file} (有效记录: {len(chunk_valid_df)})")

    total_files = num_files + test_file_count
    print(f"\n切分完成！共生成 {total_files} 个文件")
    if total_invalid > 0:
        print(f"\n⚠️  总共剔除 {total_invalid} 条无效手机号记录")

if __name__ == "__main__":
    for INPUT_FILE in INPUT_FILES:
        split_excel(
            input_file=INPUT_FILE,
            chunk_size=CHUNK_SIZE,
            start_number=START_NUMBER,
            create_test_file=CREATE_TEST_FILE
        )



