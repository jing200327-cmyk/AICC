# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

HEADER_FILL = PatternFill(start_color="4E83FD", end_color="4E83FD", fill_type="solid")
SECTION_FILL = PatternFill(start_color="BACEFD", end_color="BACEFD", fill_type="solid")
SUBSECTION_FILL = PatternFill(start_color="DEE0E3", end_color="DEE0E3", fill_type="solid")
HEADER_FONT = Font(bold=True, size=11)
DATA_FONT = Font(size=10)
WHITE_FONT = Font(bold=True, size=11, color="FFFFFF")

THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin'),
)

TRACKING_DIR = Path(__file__).parent.parent / "_tracking"


def _safe_div(a, b):
    return round(a / b * 100, 2) if b else 0.0


def _load_tracking(company: str, year_month: str) -> dict:
    TRACKING_DIR.mkdir(exist_ok=True)
    month_dir = TRACKING_DIR / year_month
    fp = month_dir / f"{company}.json"
    legacy_fp = TRACKING_DIR / f"{company}_{year_month}.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding='utf-8'))
    if legacy_fp.exists():
        return json.loads(legacy_fp.read_text(encoding='utf-8'))
    return {}


def _load_tracking_with_aliases(company: str, year_month: str, aliases: list[str] | None = None) -> dict:
    records = _load_tracking(company, year_month)
    if records:
        return records

    for alias in aliases or []:
        if alias and alias != company:
            records = _load_tracking(alias, year_month)
            if records:
                return records
    return {}


def _save_tracking(company: str, year_month: str, records: dict):
    TRACKING_DIR.mkdir(exist_ok=True)
    month_dir = TRACKING_DIR / year_month
    month_dir.mkdir(exist_ok=True)
    (month_dir / f"{company}.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')


def _previous_date_key(date: str) -> str:
    return (datetime.strptime(date, "%y%m%d") - timedelta(days=1)).strftime("%y%m%d")


def _load_previous_tracking(company: str, date: str, aliases: list[str] | None = None) -> dict:
    prev_date = _previous_date_key(date)
    prev_tracking = _load_tracking_with_aliases(company, prev_date[:4], aliases)
    return prev_tracking.get(prev_date, {})


def generate_daily_summary(company: str, date: str, data: dict, output_dir: str | Path,
                           monthly_stats: dict | None = None) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    year_month = date[:4]

    # === Tracking ===
    tracking = _load_tracking(company, year_month)
    tracking[date] = {
        "呼叫通次": data.get("call_count", 0),
        "新增线索量": data.get("total", 0),
        "新增线索接通量": data.get("jietong_count", 0),
        "有效线索量": data.get("yixiang_count", 0),
        "已接通通话平均时长分钟": data.get("connected_avg_duration_minutes", 0),
    }
    _save_tracking(company, year_month, tracking)

    # MTD 指标 = 来自当日下载的全月线索/话单表
    if monthly_stats:
        mtd_total = monthly_stats.get("累计线索量", 0)
        mtd_jietong = monthly_stats.get("累计接通量", 0)
        mtd_yixiang = monthly_stats.get("累计有效线索量", 0)
        mtd_call_count = monthly_stats.get("累计呼叫通次", 0)
    else:
        mtd_total = data.get("total", 0)
        mtd_jietong = data.get("jietong_count", 0)
        mtd_yixiang = data.get("yixiang_count", 0)
        mtd_call_count = 0

    # 昨日对比数据：月初时需要从上月 tracking 文件读取前一天。
    yesterday = _load_previous_tracking(company, date)

    # ===== 生成 Excel =====
    wb = Workbook()
    ws = wb.active
    ws.title = company

    ws.column_dimensions['A'].width = 24
    ws.column_dimensions['B'].width = 8
    ws.column_dimensions['C'].width = 16

    for col, val in [(1, "业务场景"), (2, "单位"), (3, company)]:
        cell = ws.cell(row=1, column=col, value=val)
        cell.font = WHITE_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center')
        cell.border = THIN_BORDER

    def _section_row(row_num, label):
        for c in range(1, 4):
            ws.cell(row=row_num, column=c).fill = SECTION_FILL
            ws.cell(row=row_num, column=c).border = THIN_BORDER
        ws.cell(row=row_num, column=1, value=label).font = HEADER_FONT

    def _subsection_row(row_num, label):
        for c in range(1, 4):
            ws.cell(row=row_num, column=c).fill = SUBSECTION_FILL
            ws.cell(row=row_num, column=c).border = THIN_BORDER
        ws.cell(row=row_num, column=1, value=label).font = HEADER_FONT

    def _data_row(row_num, name, unit, value):
        ws.cell(row=row_num, column=1, value=name).font = DATA_FONT
        ws.cell(row=row_num, column=1).border = THIN_BORDER
        ws.cell(row=row_num, column=2, value=unit).font = DATA_FONT
        ws.cell(row=row_num, column=2).border = THIN_BORDER
        cell = ws.cell(row=row_num, column=3, value=value)
        cell.font = DATA_FONT
        cell.border = THIN_BORDER

    def _pct_row(row_num, name, unit, value):
        ws.cell(row=row_num, column=1, value=name).font = DATA_FONT
        ws.cell(row=row_num, column=1).border = THIN_BORDER
        ws.cell(row=row_num, column=2, value=unit).font = DATA_FONT
        ws.cell(row=row_num, column=2).border = THIN_BORDER
        cell = ws.cell(row=row_num, column=3, value=value)
        cell.font = DATA_FONT
        cell.number_format = '0.00"%"'
        cell.border = THIN_BORDER

    r = 1

    date_display = f"20{date[:2]}-{date[2:4]}-{date[4:6]}"

    # === MTD Section ===
    r += 1; _section_row(r, f"MTD (截止：{date_display})")

    mtd_avg_call = round(mtd_call_count / mtd_total, 2) if mtd_total else 0.0
    mtd_jietong_rate = _safe_div(mtd_jietong, mtd_total)
    mtd_youxiao_rate = _safe_div(mtd_yixiang, mtd_jietong)
    mtd_overall_rate = _safe_div(mtd_yixiang, mtd_total)

    r += 1; _subsection_row(r, "规模指标")
    r += 1; _data_row(r, "累计线索量", "条", mtd_total)
    r += 1; _data_row(r, "接通量", "条", mtd_jietong)
    r += 1; _data_row(r, "有效线索量", "条", mtd_yixiang)
    r += 1; _data_row(r, "呼叫通次", "次", mtd_call_count)
    r += 1; _data_row(r, "平均呼叫通次", "次/条", mtd_avg_call)

    r += 1; _subsection_row(r, "检测指标")
    r += 1; _pct_row(r, "接通率", "%", mtd_jietong_rate)
    r += 1; _pct_row(r, "接通有效率", "%", mtd_youxiao_rate)
    r += 1; _pct_row(r, "整体有效率", "%", mtd_overall_rate)

    # === Daily Report Section ===
    r += 1; _section_row(r, f"Daily Report ({date_display})")

    today_total = data.get("total", 0)
    today_jietong = data.get("jietong_count", 0)
    today_call = data.get("call_count", 0)
    today_yixiang = data.get("yixiang_count", 0)
    today_connected_avg_duration_minutes = data.get("connected_avg_duration_minutes")

    yest_total = yesterday.get("新增线索量", 0) if yesterday else 0
    yest_jietong = yesterday.get("新增线索接通量", 0) if yesterday else 0
    yest_yixiang = yesterday.get("有效线索量", 0) if yesterday else 0

    r += 1; _subsection_row(r, "规模指标")
    r += 1; _data_row(r, "新增线索量", "条", today_total)
    r += 1; _data_row(r, "昨日全天对比", "条", yest_total if yesterday else "")
    r += 1; _data_row(r, "新增线索接通量", "条", today_jietong)
    r += 1; _data_row(r, "新增线索呼叫通次", "次", today_call)
    if today_connected_avg_duration_minutes is not None:
        r += 1; _data_row(r, "已接通通话平均时长（向上取整）", "分钟", today_connected_avg_duration_minutes)
    r += 1; _data_row(r, "平均呼叫通次", "次/条", round(today_call / today_total, 2) if today_total else 0.0)

    r += 1; _subsection_row(r, "检测指标")

    today_jietong_rate = _safe_div(today_jietong, today_total)
    yest_jietong_rate = _safe_div(yest_jietong, yest_total)
    today_youxiao_rate = _safe_div(today_yixiang, today_jietong)
    today_overall_rate = _safe_div(today_yixiang, today_total)
    yest_overall_rate = _safe_div(yest_yixiang, yest_total)

    r += 1; _pct_row(r, "接通率", "%", today_jietong_rate)
    r += 1; _pct_row(r, "昨日全天对比", "%", yest_jietong_rate if yesterday else "")
    r += 1; _pct_row(r, "接通有效率", "%", today_youxiao_rate)
    r += 1; _pct_row(r, "整体有效率", "%", today_overall_rate)
    r += 1; _pct_row(r, "昨日全天对比", "%", yest_overall_rate if yesterday else "")

    filepath = out_dir / f"{company}_日度月度汇总表_{date}.xlsx"
    wb.save(filepath)
    return filepath


def generate_multi_daily_summary(title: str, date: str, grouped_data: list[dict],
                                 output_dir: str | Path) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    year_month = date[:4]
    date_display = f"20{date[:2]}-{date[2:4]}-{date[4:6]}"

    prepared = []
    for item in grouped_data:
        company = item["company"]
        tracking_company = item.get("tracking_company", company)
        data = item["data"]
        monthly_stats = item.get("monthly_stats") or {}

        tracking_aliases = item.get("tracking_aliases") or []
        tracking = _load_tracking_with_aliases(tracking_company, year_month, tracking_aliases)
        tracking[date] = {
            "呼叫通次": data.get("call_count", 0),
            "新增线索量": data.get("total", 0),
            "新增线索接通量": data.get("jietong_count", 0),
            "有效线索量": data.get("yixiang_count", 0),
            "已接通通话平均时长分钟": data.get("connected_avg_duration_minutes", 0),
        }
        _save_tracking(tracking_company, year_month, tracking)

        yesterday = _load_previous_tracking(tracking_company, date, tracking_aliases)

        mtd_total = monthly_stats.get("累计线索量", data.get("total", 0))
        mtd_jietong = monthly_stats.get("累计接通量", data.get("jietong_count", 0))
        mtd_yixiang = monthly_stats.get("累计有效线索量", data.get("yixiang_count", 0))
        mtd_call_count = monthly_stats.get("累计呼叫通次", 0)

        today_total = data.get("total", 0)
        today_jietong = data.get("jietong_count", 0)
        today_call = data.get("call_count", 0)
        today_yixiang = data.get("yixiang_count", 0)
        today_connected_avg_duration_minutes = data.get("connected_avg_duration_minutes")
        yest_total = yesterday.get("新增线索量", 0) if yesterday else 0
        yest_jietong = yesterday.get("新增线索接通量", 0) if yesterday else 0
        yest_yixiang = yesterday.get("有效线索量", 0) if yesterday else 0

        prepared.append({
            "company": company,
            "mtd_total": mtd_total,
            "mtd_jietong": mtd_jietong,
            "mtd_yixiang": mtd_yixiang,
            "mtd_call_count": mtd_call_count,
            "mtd_avg_call": round(mtd_call_count / mtd_total, 2) if mtd_total else 0.0,
            "mtd_jietong_rate": _safe_div(mtd_jietong, mtd_total),
            "mtd_youxiao_rate": _safe_div(mtd_yixiang, mtd_jietong),
            "mtd_overall_rate": _safe_div(mtd_yixiang, mtd_total),
            "today_total": today_total,
            "yest_total": yest_total if yesterday else "",
            "today_jietong": today_jietong,
            "today_small_round_count": data.get("small_round_count"),
            "today_hangup_after_connect_count": data.get("hangup_after_connect_count"),
            "today_call": today_call,
            "today_connected_avg_duration_minutes": today_connected_avg_duration_minutes,
            "today_avg_call": round(today_call / today_total, 2) if today_total else 0.0,
            "today_jietong_rate": _safe_div(today_jietong, today_total),
            "yest_jietong_rate": _safe_div(yest_jietong, yest_total) if yesterday else "",
            "today_youxiao_rate": _safe_div(today_yixiang, today_jietong),
            "today_overall_rate": _safe_div(today_yixiang, today_total),
            "yest_overall_rate": _safe_div(yest_yixiang, yest_total) if yesterday else "",
        })

    wb = Workbook()
    ws = wb.active
    ws.title = title

    total_cols = 2 + len(prepared)
    ws.column_dimensions['A'].width = 42
    ws.column_dimensions['B'].width = 10
    for idx in range(3, total_cols + 1):
        ws.column_dimensions[chr(64 + idx)].width = 30

    headers = ["业务场景", "单位"] + [item["company"] for item in prepared]
    for col, val in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=val)
        cell.font = WHITE_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center')
        cell.border = THIN_BORDER

    def _section_row(row_num, label):
        for c in range(1, total_cols + 1):
            ws.cell(row=row_num, column=c).fill = SECTION_FILL
            ws.cell(row=row_num, column=c).border = THIN_BORDER
        ws.cell(row=row_num, column=1, value=label).font = HEADER_FONT

    def _subsection_row(row_num, label):
        for c in range(1, total_cols + 1):
            ws.cell(row=row_num, column=c).fill = SUBSECTION_FILL
            ws.cell(row=row_num, column=c).border = THIN_BORDER
        ws.cell(row=row_num, column=1, value=label).font = HEADER_FONT

    def _data_row(row_num, name, unit, key):
        ws.cell(row=row_num, column=1, value=name).font = DATA_FONT
        ws.cell(row=row_num, column=1).border = THIN_BORDER
        ws.cell(row=row_num, column=1).alignment = Alignment(wrap_text=True)
        ws.cell(row=row_num, column=2, value=unit).font = DATA_FONT
        ws.cell(row=row_num, column=2).border = THIN_BORDER
        ws.cell(row=row_num, column=2).alignment = Alignment(horizontal='center')
        for idx, item in enumerate(prepared, start=3):
            cell = ws.cell(row=row_num, column=idx, value=item[key])
            cell.font = DATA_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal='center')

    def _label_row(row_num, name):
        ws.cell(row=row_num, column=1, value=name).font = DATA_FONT
        ws.cell(row=row_num, column=1).border = THIN_BORDER
        ws.cell(row=row_num, column=1).alignment = Alignment(wrap_text=True)
        ws.cell(row=row_num, column=2, value="").font = DATA_FONT
        ws.cell(row=row_num, column=2).border = THIN_BORDER
        ws.cell(row=row_num, column=2).alignment = Alignment(horizontal='center')
        for idx in range(3, total_cols + 1):
            cell = ws.cell(row=row_num, column=idx, value="")
            cell.font = DATA_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal='center')

    def _pct_row(row_num, name, unit, key):
        ws.cell(row=row_num, column=1, value=name).font = DATA_FONT
        ws.cell(row=row_num, column=1).border = THIN_BORDER
        ws.cell(row=row_num, column=1).alignment = Alignment(wrap_text=True)
        ws.cell(row=row_num, column=2, value=unit).font = DATA_FONT
        ws.cell(row=row_num, column=2).border = THIN_BORDER
        ws.cell(row=row_num, column=2).alignment = Alignment(horizontal='center')
        for idx, item in enumerate(prepared, start=3):
            cell = ws.cell(row=row_num, column=idx, value=item[key])
            cell.font = DATA_FONT
            cell.number_format = '0.00"%"'
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal='center')

    r = 1
    r += 1; _section_row(r, f"MTD (截止：{date_display})")
    r += 1; _subsection_row(r, "规模指标")
    r += 1; _data_row(r, "累计线索量", "条", "mtd_total")
    r += 1; _data_row(r, "接通量", "条", "mtd_jietong")
    r += 1; _data_row(r, "有效线索量", "条", "mtd_yixiang")
    r += 1; _data_row(r, "呼叫通次", "次", "mtd_call_count")
    r += 1; _data_row(r, "平均呼叫通次", "次/条", "mtd_avg_call")

    r += 1; _subsection_row(r, "检测指标")
    r += 1; _pct_row(r, "接通率", "%", "mtd_jietong_rate")
    r += 1; _pct_row(r, "接通有效率", "%", "mtd_youxiao_rate")
    r += 1; _pct_row(r, "整体有效率", "%", "mtd_overall_rate")

    r += 1; _section_row(r, f"Daily Report ({date_display})")
    r += 1; _subsection_row(r, "规模指标")
    r += 1; _data_row(r, "新增线索量", "条", "today_total")
    r += 1; _data_row(r, "昨日全天对比", "条", "yest_total")
    r += 1; _data_row(r, "新增线索接通量", "条", "today_jietong")
    if title == "广州新车":
        r += 1; _label_row(r, "其中：")
        r += 1; _data_row(r, "  沟通小于等于2轮", "条", "today_small_round_count")
        r += 1; _data_row(r, "  接通后挂断", "条", "today_hangup_after_connect_count")
    r += 1; _data_row(r, "新增线索呼叫通次", "次", "today_call")
    if any(item.get("today_connected_avg_duration_minutes") is not None for item in prepared):
        r += 1; _data_row(r, "已接通通话平均时长（向上取整）", "分钟", "today_connected_avg_duration_minutes")
    r += 1; _data_row(r, "平均呼叫通次", "次/条", "today_avg_call")

    r += 1; _subsection_row(r, "检测指标")
    r += 1; _pct_row(r, "接通率（=新增线索接通量/新增线索量）", "%", "today_jietong_rate")
    r += 1; _pct_row(r, "昨日全天对比", "%", "yest_jietong_rate")
    r += 1; _pct_row(r, "接通有效率（=有效线索量/新增线索接通量）", "%", "today_youxiao_rate")
    r += 1; _pct_row(r, "整体有效率（=有效线索量/新增线索量）", "%", "today_overall_rate")
    r += 1; _pct_row(r, "昨日全天对比", "%", "yest_overall_rate")

    filepath = out_dir / f"{title}_日度月度汇总表_{date}.xlsx"
    wb.save(filepath)
    return filepath
