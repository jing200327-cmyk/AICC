#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from daily_summary import generate_daily_summary, generate_multi_daily_summary


def _col(df, name, prefer_call=False):
    if name in df.columns:
        return name
    suffixes = ['_通话', '_线索'] if prefer_call else ['_线索', '_通话']
    for suffix in suffixes:
        candidate = f'{name}{suffix}'
        if candidate in df.columns:
            return candidate
    return name


def normalize_id(id_val):
    if pd.isna(id_val):
        return ''
    s = str(id_val)
    s = (
        s.replace('\u00a0', '')
        .replace('\u3000', '')
        .replace('\ufeff', '')
        .strip()
    )
    if not s or s.lower() in {'nan', 'none', 'null'}:
        return ''
    if re.fullmatch(r'\d+\.0+', s):
        s = s.split('.', 1)[0]
    elif re.fullmatch(r'[+-]?\d+(?:\.\d+)?[eE][+-]?\d+', s):
        try:
            decimal_value = Decimal(s)
            if decimal_value == decimal_value.to_integral_value():
                s = str(decimal_value.quantize(Decimal(1)))
        except InvalidOperation:
            pass
    return s


def normalize_id_column(df: pd.DataFrame, label: str) -> pd.DataFrame:
    if '线索ID' not in df.columns:
        raise KeyError(f"{label}缺少线索ID列")
    df = df.copy()
    before_empty = int(df['线索ID'].isna().sum())
    df['线索ID'] = df['线索ID'].apply(normalize_id)
    after_empty = int((df['线索ID'] == '').sum())
    if after_empty:
        print(f"  {label}线索ID为空: {after_empty} 条（原始空值 {before_empty} 条）")
    return df

def parse_exclude_ids(raw: str | None) -> set[str]:
    if not raw:
        return set()
    parts = re.split(r'[\s,，]+', raw)
    return {normalize_id(part) for part in parts if normalize_id(part)}


def filter_excluded_clues(df, exclude_ids: set[str], label: str):
    if not exclude_ids or '线索ID' not in df.columns:
        return df
    before = len(df)
    df = df[~df['线索ID'].isin(exclude_ids)].copy()
    removed = before - len(df)
    print(f"  {label}剔除指定线索: {removed} 条")
    return df


def safe_output_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', '_', str(name)).strip() or "未命名"


def guangzhou_robot_name(name: str) -> str:
    display_name = safe_output_name(name)
    if display_name.startswith("龙星行-"):
        display_name = display_name[len("龙星行-"):]
    return display_name or "未命名"


def build_group_tracking_name(parent_company: str, report_company: str) -> str:
    # Use the visible grouped report name as the canonical tracking key so
    # manually补录的数据 and generated汇总表 use the same file consistently.
    return safe_output_name(report_company)


def cleanup_merged_summary_artifacts(summary_dir: str, date_str: str, merged_title: str, grouped_names: list[str]):
    merged_filename = f"{merged_title}_日度月度汇总表_{date_str}.xlsx"
    for name in grouped_names:
        candidate = os.path.join(summary_dir, f"{safe_output_name(name)}_日度月度汇总表_{date_str}.xlsx")
        if os.path.exists(candidate) and os.path.basename(candidate) != merged_filename:
            os.remove(candidate)
            print(f"  已清理旧分组汇总表: {os.path.basename(candidate)}")


def calculate_connected_avg_duration_minutes(df_call: pd.DataFrame) -> int:
    if df_call.empty or '通话状态' not in df_call.columns or '通话时长' not in df_call.columns:
        return 0
    connected_mask = df_call['通话状态'].astype(str).str.contains('已接通', na=False)
    connected_calls = df_call.loc[connected_mask].copy()
    if connected_calls.empty:
        return 0
    durations = pd.to_numeric(connected_calls['通话时长'], errors='coerce').dropna()
    if durations.empty:
        return 0
    avg_minutes = durations.mean() / 60
    return int(math.ceil(avg_minutes))


# ========== 脱敏号码处理 ==========

def is_desensitized_phone(phone):
    if pd.isna(phone) or phone == '' or phone == 'nan':
        return False
    phone_str = str(phone)
    pattern = r'^\d{3}\*{4}\d{4}$'
    return bool(re.match(pattern, phone_str))


def mask_phone(phone):
    if pd.isna(phone) or phone == '' or phone == 'nan':
        return phone
    phone_str = str(phone).strip()
    if len(phone_str) == 11 and phone_str.isdigit():
        return phone_str[:3] + '****' + phone_str[7:]
    return phone_str


def normalize_and_mask_phones(df_xian, df_call):
    print(f"\n【步骤0】脱敏号码检查与处理")

    df_xian = df_xian.copy()
    df_call = df_call.copy()

    df_xian['客户手机号'] = df_xian['客户手机号'].astype(str)
    df_call['客户真实号码'] = df_call['客户真实号码'].astype(str)

    xian_phones = df_xian['客户手机号'].dropna()
    xian_phones = xian_phones[xian_phones != '']
    xian_phones = xian_phones[xian_phones != 'nan']

    call_phones = df_call['客户真实号码'].dropna()
    call_phones = call_phones[call_phones != '']
    call_phones = call_phones[call_phones != 'nan']

    xian_desensitized = xian_phones[xian_phones.apply(is_desensitized_phone)]
    call_desensitized = call_phones[call_phones.apply(is_desensitized_phone)]

    print(f"  线索明细表 - 脱敏号码数量: {len(xian_desensitized)}")
    print(f"  通话列表 - 脱敏号码数量: {len(call_desensitized)}")

    if len(xian_desensitized) > 0 or len(call_desensitized) > 0:
        print(f"\n  检测到脱敏号码，正在同步处理...")

        def get_prefix(phone):
            phone_str = str(phone)
            if len(phone_str) == 11 and phone_str.isdigit():
                return phone_str[:3]
            if is_desensitized_phone(phone_str):
                return phone_str[:3]
            return ''

        def get_suffix(phone):
            phone_str = str(phone)
            if len(phone_str) == 11 and phone_str.isdigit():
                return phone_str[7:]
            if is_desensitized_phone(phone_str):
                return phone_str[-4:]
            return ''

        xian_mask_prefix = set(xian_phones.apply(get_prefix))
        xian_mask_suffix = set(xian_phones.apply(get_suffix))

        call_mask_prefix = set(call_phones.apply(get_prefix))
        call_mask_suffix = set(call_phones.apply(get_suffix))

        if len(xian_desensitized) > 0:
            print(f"  线索明细表存在脱敏号码，通话列表对应号码同步脱敏...")
            df_call['客户真实号码'] = df_call['客户真实号码'].apply(
                lambda x: mask_phone(x) if (
                    len(str(x)) == 11 and str(x).isdigit() and
                    get_prefix(x) in xian_mask_prefix and get_suffix(x) in xian_mask_suffix
                ) else x
            )

        if len(call_desensitized) > 0:
            print(f"  通话列表存在脱敏号码，线索明细表对应号码同步脱敏...")
            df_xian['客户手机号'] = df_xian['客户手机号'].apply(
                lambda x: mask_phone(x) if (
                    len(str(x)) == 11 and str(x).isdigit() and
                    get_prefix(x) in call_mask_prefix and get_suffix(x) in call_mask_suffix
                ) else x
            )

        xian_masked_count = df_xian['客户手机号'].apply(is_desensitized_phone).sum()
        call_masked_count = df_call['客户真实号码'].apply(is_desensitized_phone).sum()
        print(f"  处理后 - 线索明细表脱敏号码: {xian_masked_count}")
        print(f"  处理后 - 通话列表脱敏号码: {call_masked_count}")

    return df_xian, df_call


# ========== 通话列表去重 ==========

def write_excel_artifact(frame: pd.DataFrame, target_path: str | Path) -> Path:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        frame.to_excel(target, index=False, engine='openpyxl')
        return target
    except PermissionError:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        fallback = target.with_name(f'{target.stem}_本次生成_{timestamp}{target.suffix}')
        frame.to_excel(fallback, index=False, engine='openpyxl')
        return fallback


def deduplicate_calls(df_call, output_dir='.', company=''):
    print(f"\n【步骤1】通话列表去重")

    df_call = df_call.copy()
    original_count = len(df_call)

    unique_ids = df_call['线索ID'].nunique()

    print(f"  原始通话记录: {original_count} 条")
    print(f"  唯一线索ID数: {unique_ids} 个")

    df_call['结束时间'] = pd.to_datetime(df_call['结束时间'], errors='coerce')

    call_counts = df_call.groupby('线索ID')['线索ID'].transform('size')
    duplicate_calls = df_call.loc[call_counts > 1].copy()
    if not duplicate_calls.empty:
        duplicate_calls['同线索当日话单数'] = call_counts.loc[
            duplicate_calls.index
        ].astype(int)

    df_dedup = df_call.sort_values('结束时间', ascending=False).drop_duplicates(
        subset=['线索ID'], keep='first'
    )

    print(f"  去重后通话记录: {len(df_dedup)} 条")

    if company:
        dedup_file = Path(output_dir) / f'{company}_通话列表_去重.xlsx'
        written = write_excel_artifact(df_dedup, dedup_file)
        print(f"  已保存: {dedup_file}")

        if not duplicate_calls.empty:
            duplicate_file = Path(output_dir) / f'{company}_重复线索话单.xlsx'
            write_excel_artifact(duplicate_calls, duplicate_file)

    return df_dedup


def _nonempty_text(series: pd.Series) -> pd.Series:
    return (
        series.notna()
        & ~series.astype(str).str.strip().str.lower().isin(
            ['', 'nan', 'none', 'null']
        )
    )


def _latest_group_mapping(
    calls: pd.DataFrame | None,
    group_field: str,
) -> pd.Series:
    if (
        calls is None
        or calls.empty
        or '线索ID' not in calls.columns
        or group_field not in calls.columns
    ):
        return pd.Series(dtype='object')

    mapping_calls = normalize_id_column(calls, '机器人映射话单')
    if '结束时间' in mapping_calls.columns:
        mapping_calls = mapping_calls.copy()
        mapping_calls['结束时间'] = pd.to_datetime(
            mapping_calls['结束时间'], errors='coerce'
        )
        mapping_calls = mapping_calls.sort_values('结束时间', ascending=False)
    mapping_calls = mapping_calls[
        _nonempty_text(mapping_calls[group_field])
    ].drop_duplicates('线索ID', keep='first')
    if mapping_calls.empty:
        return pd.Series(dtype='object')
    return mapping_calls.set_index('线索ID')[group_field]


def build_daily_reporting_population(
    df_xian: pd.DataFrame,
    df_call: pd.DataFrame,
    filter_date: pd.Timestamp,
    group_by_call_field: str | None = None,
    required_group_values: list[str] | None = None,
    df_call_mtd: pd.DataFrame | None = None,
    unmatched_group_name: str = '未匹配机器人',
    output_dir: str | Path | None = None,
    company: str = '',
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Build one row per target-day clue, enriched with its terminal daily call."""
    target_date = pd.Timestamp(filter_date).date()
    clues = normalize_id_column(df_xian, '线索明细')
    calls = normalize_id_column(df_call, '通话列表')

    if '线索下发时间' in clues.columns:
        clues = clues.copy()
        clues['线索下发时间'] = pd.to_datetime(
            clues['线索下发时间'], errors='coerce'
        )
        clues = clues[clues['线索下发时间'].dt.date == target_date]
    clues = clues[clues['线索ID'] != ''].drop_duplicates(
        '线索ID', keep='first'
    ).copy()

    if '结束时间' in calls.columns:
        calls = calls.copy()
        calls['结束时间'] = pd.to_datetime(calls['结束时间'], errors='coerce')
        calls = calls[calls['结束时间'].dt.date == target_date]
        calls = calls.sort_values('结束时间', ascending=False)
    calls = calls[calls['线索ID'] != ''].drop_duplicates(
        '线索ID', keep='first'
    ).copy()

    clue_ids = set(clues['线索ID'])
    call_ids = set(calls['线索ID'])
    history_calls = calls[~calls['线索ID'].isin(clue_ids)].copy()
    daily_calls = calls[calls['线索ID'].isin(clue_ids)].copy()
    population = clues.merge(
        daily_calls,
        on='线索ID',
        how='left',
        suffixes=('_线索', '_通话'),
    )

    if '客户意向等级' in population.columns:
        call_intent_col = _col(population, '意向等级', prefer_call=True)
        if call_intent_col in population.columns:
            clue_intent = population['客户意向等级'].astype('object')
            population['客户意向等级'] = clue_intent.where(
                _nonempty_text(clue_intent), population[call_intent_col]
            )

    if group_by_call_field:
        call_group_col = f'{group_by_call_field}_通话'
        clue_group_col = f'{group_by_call_field}_线索'
        if call_group_col in population.columns:
            groups = population[call_group_col].astype('object')
        elif (
            group_by_call_field in daily_calls.columns
            and group_by_call_field not in clues.columns
            and group_by_call_field in population.columns
        ):
            groups = population[group_by_call_field].astype('object')
        else:
            groups = pd.Series(pd.NA, index=population.index, dtype='object')

        if clue_group_col in population.columns:
            clue_groups = population[clue_group_col]
        elif group_by_call_field in clues.columns:
            clue_groups = population[group_by_call_field]
        else:
            clue_groups = pd.Series(pd.NA, index=population.index)
        groups = groups.where(_nonempty_text(groups), clue_groups)

        historical_mapping = _latest_group_mapping(
            df_call_mtd, group_by_call_field
        )
        if not historical_mapping.empty:
            mapped = population['线索ID'].map(historical_mapping)
            groups = groups.where(_nonempty_text(groups), mapped)

        required_groups = [
            str(value).strip()
            for value in required_group_values or []
            if str(value).strip()
        ]
        if len(required_groups) == 1:
            groups = groups.where(_nonempty_text(groups), required_groups[0])
        population[group_by_call_field] = groups.where(
            _nonempty_text(groups), unmatched_group_name
        )
        if output_dir and company:
            unmatched_rows = population[
                population[group_by_call_field].astype(str).str.strip().eq(
                    unmatched_group_name
                )
            ]
            if not unmatched_rows.empty:
                write_excel_artifact(
                    unmatched_rows,
                    Path(output_dir)
                    / f'匹配结果_{company}_未匹配机器人线索表.xlsx',
                )

    diagnostics = {
        'daily_dispatched_clues': len(clue_ids),
        'daily_called_clues': len(call_ids),
        'daily_dispatched_called_clues': len(clue_ids & call_ids),
        'daily_called_historical_clues': len(call_ids - clue_ids),
        'daily_uncalled_clues': len(clue_ids - call_ids),
        'daily_population': len(population),
    }

    if output_dir and company:
        output_path = Path(output_dir)
        call_id_col = _col(population, '通话ID', prefer_call=True)
        matched_mask = (
            population[call_id_col].notna()
            if call_id_col in population.columns
            else pd.Series(False, index=population.index)
        )
        write_excel_artifact(
            population[matched_mask],
            output_path / f'匹配结果_{company}_当日线索通话记录表.xlsx',
        )
        write_excel_artifact(
            population[~matched_mask],
            output_path / f'匹配结果_{company}_无话单新增线索表.xlsx',
        )
        write_excel_artifact(
            history_calls,
            output_path / f'匹配结果_{company}_历史线索通话记录表_补充.xlsx',
        )

    return population, history_calls, diagnostics


def count_calls_for_clue_population(
    df_call: pd.DataFrame,
    population: pd.DataFrame,
) -> int:
    if '线索ID' not in df_call.columns or '线索ID' not in population.columns:
        return 0
    clue_ids = set(population['线索ID'].map(normalize_id))
    return int(df_call['线索ID'].map(normalize_id).isin(clue_ids).sum())


def reconcile_group_population(
    population: pd.DataFrame,
    group_field: str,
    required_group_values: list[str],
    unmatched_group_name: str = '未匹配机器人',
) -> dict[str, int]:
    groups = population[group_field].astype(str).str.strip()
    required = {str(value).strip() for value in required_group_values}
    unmatched = groups.eq(unmatched_group_name) | groups.str.lower().isin(
        ['', 'nan', 'none', 'null']
    )
    included = groups.isin(required)
    return {
        'source_total': int(len(population)),
        'included': int(included.sum()),
        'excluded': int((~included & ~unmatched).sum()),
        'unmatched': int(unmatched.sum()),
    }


def validate_group_reconciliation(
    reconciliation: dict[str, int],
    company: str,
) -> None:
    accounted = (
        reconciliation['included']
        + reconciliation['excluded']
        + reconciliation['unmatched']
    )
    if accounted != reconciliation['source_total']:
        raise ValueError(
            f'{company} 分组总量校验失败：源线索 '
            f'{reconciliation["source_total"]}，已归类 {accounted}'
        )
    if reconciliation['unmatched']:
        raise ValueError(
            f'{company} 有 {reconciliation["unmatched"]} 条当日新增线索'
            '无法匹配机器人，禁止生成可能偏小的分组日报'
        )


def parse_group_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r'[,，]+', raw) if part.strip()]


def parse_group_display_names(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"group_display_names 不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("group_display_names 必须是 JSON 对象")
    result = {}
    for key, value in data.items():
        group_name = str(key).strip()
        display_name = safe_output_name(value)
        if group_name and display_name:
            result[group_name] = display_name
    return result


def build_monthly_stats(df_mtd, df_call_mtd):
    """Build an auditable MTD snapshot from the complete month-to-date files."""
    clues = df_mtd.drop_duplicates(subset=['线索ID'], keep='first').copy()
    calls = df_call_mtd.copy()
    talk_status_col = _col(clues, '通话状态')
    clue_status_col = _col(clues, '线索状态')
    connected_mask = clues[talk_status_col].astype(str).str.contains(
        '已接通', na=False
    )
    effective_mask = clues[clue_status_col].astype(str).str.contains(
        '有效', na=False
    )
    return {
        "累计线索量": int(len(clues)),
        "累计接通量": int(connected_mask.sum()),
        "累计有效线索量": int(effective_mask.sum()),
        "累计呼叫通次": int(len(calls)),
    }


def build_monthly_stats_by_group(
    df_mtd,
    df_call_mtd,
    group_by_call_field,
    unmatched_group_name="未匹配机器人",
):
    if group_by_call_field not in df_call_mtd.columns:
        raise ValueError(f"通话列表缺少分组字段: {group_by_call_field}")

    df_call_dedup = df_call_mtd.sort_values('结束时间', ascending=False).drop_duplicates(
        subset=['线索ID'], keep='first'
    )
    call_group_col = '__call_group__'
    merged = df_mtd.merge(
        df_call_dedup[['线索ID', group_by_call_field]].rename(
            columns={group_by_call_field: call_group_col}
        ),
        on='线索ID',
        how='left',
    )
    group_col = group_by_call_field
    if group_col in merged.columns:
        clue_group_valid = (
            merged[group_col].notna()
            & ~merged[group_col].astype(str).str.strip().str.lower().isin(
                ['', 'nan', 'none', 'null']
            )
        )
        merged[group_col] = merged[group_col].where(
            clue_group_valid,
            merged[call_group_col],
        )
    else:
        merged[group_col] = merged[call_group_col]
    merged = merged.drop(columns=[call_group_col])
    missing_group_mask = (
        merged[group_col].isna()
        | merged[group_col].astype(str).str.strip().str.lower().isin(
            ['', 'nan', 'none', 'null']
        )
    )
    if missing_group_mask.any():
        missing_count = int(missing_group_mask.sum())
        raise ValueError(
            f"MTD中有 {missing_count} 条线索无法通过线索或话单匹配到"
            f"{group_by_call_field}，禁止生成不完整汇总"
        )
    merged = merged[~missing_group_mask].copy()

    clue_status_col = _col(merged, '线索状态')

    stats = {}
    for group_value, group_df in merged.groupby(group_col, dropna=True):
        group_name = str(group_value).strip()
        if not group_name or group_name == 'nan':
            continue
        group_calls = df_call_mtd[df_call_mtd[group_by_call_field].astype(str).str.strip() == group_name]
        talk_status_col = _col(group_df, '通话状态')
        connected_mask = group_df[talk_status_col].astype(str).str.contains(
            '已接通', na=False
        )
        effective_mask = group_df[clue_status_col].astype(str).str.contains('有效', na=False)
        stats[group_name] = {
            "累计线索量": len(group_df),
            "累计接通量": int(connected_mask.sum()),
            "累计有效线索量": int(effective_mask.sum()),
            "累计呼叫通次": int(len(group_calls)),
        }
    return stats


# ========== 数据质量检查 ==========

TIME_LIKE_VALUE_RE = re.compile(
    r'^(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:\s?[AP]M)?$',
    re.IGNORECASE,
)


def summarize_time_like_values(values: pd.Series) -> tuple[int, list[str]]:
    values = values.astype(str).str.strip()
    matches = values[values.apply(lambda x: bool(TIME_LIKE_VALUE_RE.match(x)))]
    return len(matches), matches.head(10).tolist()


def limit_clue_records_for_matching(df_xian, limit_count: int | None):
    if limit_count is None:
        return df_xian
    if limit_count <= 0:
        raise ValueError("clue_match_limit 必须是大于 0 的整数")

    before = len(df_xian)
    df_limited = df_xian.head(limit_count).copy()
    print(f"  线索明细匹配限制: 仅使用前 {len(df_limited)} 条记录参与匹配（筛选后原始共 {before} 条）")
    return df_limited

def check_phone_numbers(df_xian):
    print(f"\n【数据质量检查】检查客户手机号格式")

    df_xian = df_xian.copy()
    df_xian['客户手机号'] = df_xian['客户手机号'].astype(str)

    valid_phones = df_xian['客户手机号'].dropna()
    valid_phones = valid_phones[valid_phones != '']
    valid_phones = valid_phones[valid_phones != 'nan']

    valid_11 = valid_phones[valid_phones.str.len() == 11]
    invalid_phones = valid_phones[valid_phones.str.len() != 11]

    total_valid = len(valid_phones)
    total_invalid = len(invalid_phones)

    print(f"  线索明细表 - 有效手机号记录: {total_valid} 条")
    print(f"  线索明细表 - 11位手机号: {len(valid_11)} 条")
    print(f"  线索明细表 - 非11位手机号: {total_invalid} 条")

    warning_msg = ""
    if total_invalid > 0:
        time_like_count, time_like_samples = summarize_time_like_values(invalid_phones)
        print(f"\n  发现 {total_invalid} 条非11位手机号记录！")

        invalid_len_dist = invalid_phones.str.len().value_counts().sort_index()
        print(f"\n  非11位手机号长度分布：")
        for length, count in invalid_len_dist.items():
            print(f"    {length}位: {count} 条")

        invalid_samples = invalid_phones.head(10).tolist()
        print(f"\n  非11位手机号样本（前10条）：")
        for sample in invalid_samples:
            print(f"    - {sample}")

        if time_like_count > 0:
            print(f"\n  检测到 {time_like_count} 条手机号呈时间格式，疑似源文件导出异常：")
            for sample in time_like_samples:
                print(f"    - {sample}")

        print(f"\n  注意事项：")
        print(f"    非11位的手机号可能是以下情况：")
        print(f"    1. 客户填写了错误或不完整的手机号")
        print(f"    2. 客户填写了座机号码或短号")
        print(f"    3. 数据录入错误（如多填或少填数字）")
        print(f"    4. 测试数据或虚拟号码")
        print(f"    5. 客户隐私保护使用了中间位加密的号码")

        warning_msg = (f"\n线索明细表警告：发现 {total_invalid} 条非11位手机号记录，请检查数据来源！\n"
                       f"   非11位的手机号可能存在数据质量问题，建议核实后重新导入。")
        if time_like_count > 0:
            warning_msg += f"\n   其中 {time_like_count} 条手机号呈时间格式，疑似源文件导出异常。"

    return df_xian, warning_msg, total_invalid


def check_call_phone_numbers(df_call):
    print(f"\n【数据质量检查】检查通话列表客户真实号码格式")

    df_call = df_call.copy()
    df_call['客户真实号码'] = df_call['客户真实号码'].astype(str)

    valid_phones = df_call['客户真实号码'].dropna()
    valid_phones = valid_phones[valid_phones != '']
    valid_phones = valid_phones[valid_phones != 'nan']

    valid_11 = valid_phones[valid_phones.str.len() == 11]
    invalid_phones = valid_phones[valid_phones.str.len() != 11]

    total_valid = len(valid_phones)
    total_invalid = len(invalid_phones)

    print(f"  通话列表 - 有效号码记录: {total_valid} 条")
    print(f"  通话列表 - 11位号码: {len(valid_11)} 条")
    print(f"  通话列表 - 非11位号码: {total_invalid} 条")

    warning_msg = ""
    if total_invalid > 0:
        time_like_count, time_like_samples = summarize_time_like_values(invalid_phones)
        print(f"\n  发现 {total_invalid} 条非11位号码记录！")

        invalid_len_dist = invalid_phones.str.len().value_counts().sort_index()
        print(f"\n  非11位号码长度分布：")
        for length, count in invalid_len_dist.items():
            print(f"    {length}位: {count} 条")

        invalid_samples = invalid_phones.head(10).tolist()
        print(f"\n  非11位号码样本（前10条）：")
        for sample in invalid_samples:
            print(f"    - {sample}")

        if time_like_count > 0:
            print(f"\n  检测到 {time_like_count} 条号码呈时间格式，疑似源文件导出异常：")
            for sample in time_like_samples:
                print(f"    - {sample}")

        print(f"\n  注意事项：")
        print(f"    非11位的号码可能是以下情况：")
        print(f"    1. 客户填写了错误或不完整的手机号")
        print(f"    2. 客户填写了座机号码或短号")
        print(f"    3. 数据录入错误（如多填或少填数字）")
        print(f"    4. 测试数据或虚拟号码")
        print(f"    5. 客户隐私保护使用了中间位加密的号码")

        warning_msg = (f"\n通话列表警告：发现 {total_invalid} 条非11位号码记录，请检查数据来源！\n"
                       f"   非11位的号码可能存在数据质量问题，建议核实后重新导入。\n"
                       f"   请注意：由于号码字段异常，线索匹配可能不完整，\n"
                       f"      建议检查线索量（尤其是重呼线索量）是否与数据看板一致。")
        if time_like_count > 0:
            warning_msg += f"\n   其中 {time_like_count} 条号码呈时间格式，疑似源文件导出异常。"

    return df_call, warning_msg, total_invalid


# ========== 线索与通话匹配 ==========

def match_records(df_xian, df_call, output_dir='.', company=''):
    print(f"\n【步骤2】线索与通话匹配（基于线索ID）")

    df_call = df_call.copy()
    df_xian = df_xian.copy()

    print(f"  线索明细: {len(df_xian)} 条")
    print(f"  去重通话记录: {len(df_call)} 条")

    merged = df_xian.merge(
        df_call,
        on='线索ID',
        how='left',
        suffixes=('_线索', '_通话')
    )

    call_id_col = _col(merged, '通话ID', prefer_call=True)
    df_today = merged[merged[call_id_col].notna()]
    print(f"  当日线索通话记录: {len(df_today)} 条")

    df_history = merged[merged[call_id_col].isna()]
    print(f"  无通话匹配线索: {len(df_history)} 条")

    xian_ids = set(df_xian['线索ID'].unique())
    extra_calls = df_call[~df_call['线索ID'].isin(xian_ids)]
    print(f"  通话表中不在线索明细(按线索ID): {len(extra_calls)} 条")

    df_today.to_excel(
        os.path.join(output_dir, f'匹配结果_{company}_当日线索通话记录表.xlsx'),
        index=False, engine='openpyxl'
    )
    print(f"  已保存: 匹配结果_{company}_当日线索通话记录表.xlsx")

    df_history.to_excel(
        os.path.join(output_dir, f'匹配结果_{company}_历史线索通话记录表.xlsx'),
        index=False, engine='openpyxl'
    )
    print(f"  已保存: 匹配结果_{company}_历史线索通话记录表.xlsx")

    extra_calls.to_excel(
        os.path.join(output_dir, f'匹配结果_{company}_历史线索通话记录表_补充.xlsx'),
        index=False, engine='openpyxl'
    )
    print(f"  已保存: 匹配结果_{company}_历史线索通话记录表_补充.xlsx")

    return df_today, extra_calls


# ========== 报告生成 ==========

def normalize_unconnected_reason(value) -> str:
    if pd.isna(value) or str(value).strip().lower() in {
        '', 'nan', 'none', 'null'
    }:
        return '无话单/未外呼'
    if '线路限制' in str(value):
        return '线路限制'
    return str(value).strip()


def generate_report(df_today, df_history, company='', date='', phone_warning='', invalid_phone_count=0, total_xiansuo=0):
    df_today = df_today.copy()

    call_status_col = _col(df_today, '通话状态', prefer_call=True)
    call_status_detail_col = _col(df_today, '通话状态详情')
    xian_status_col = _col(df_today, '线索状态')
    intent_col = _col(df_today, '客户意向等级')
    duration_col = _col(df_today, '通话时长', prefer_call=True)
    call_id_col = _col(df_today, '通话ID', prefer_call=True)
    xian_id_col = _col(df_today, '线索ID')
    phone_col = _col(df_today, '客户真实号码', prefer_call=True)

    df_today['是否接通'] = df_today[call_status_col].apply(
        lambda x: '接通' if pd.notna(x) and '已接通' in str(x) else '未接通'
    )

    total = total_xiansuo if total_xiansuo > 0 else len(df_today)

    jietong = df_today[df_today['是否接通'] == '接通']
    weijietong = df_today[df_today['是否接通'] == '未接通']

    jietong_count = len(jietong)
    jietong_status_detail = jietong[call_status_detail_col].astype(str).str.strip()
    small_round_count = int((jietong_status_detail == '沟通小于等于2轮').sum())
    hangup_after_connect_count = int((jietong_status_detail == '接通后挂断').sum())

    yixiang = jietong[jietong[xian_status_col] == '有效']

    wuxiao = jietong[jietong[xian_status_col] == '无效']
    wuxiao_wuyixiang = wuxiao[wuxiao[intent_col] == '无意向']
    wuxiao_yichegou = wuxiao[wuxiao[intent_col] == '已购车']

    daiding = jietong[
        (jietong[xian_status_col] == '待定') |
        (jietong[xian_status_col].isna()) |
        (jietong[xian_status_col] == '')
    ]

    weibiaoming = daiding[daiding[intent_col] == '意向未知']

    weibiaoming_ids = set(weibiaoming.index)
    daiding_qita = daiding[~daiding.index.isin(weibiaoming_ids)]
    daiding_qita = daiding_qita.copy()
    daiding_qita[duration_col] = pd.to_numeric(daiding_qita[duration_col], errors='coerce')
    daiding_15s = daiding_qita[daiding_qita[duration_col] <= 15]

    yixiang_count = len(yixiang)
    wuxiao_count = len(wuxiao)
    wuyixiang_count = len(wuxiao_wuyixiang)
    yichegou_count = len(wuxiao_yichegou)
    buming_count = len(daiding)
    weibiaoming_count = len(weibiaoming)
    daiding_15s_count = len(daiding_15s)

    mismatch_count = buming_count - weibiaoming_count - daiding_15s_count
    if mismatch_count != 0:
        mismatch_records = daiding_qita[
            (daiding_qita[duration_col] > 15) | (daiding_qita[duration_col].isna())
        ]
        print(f"\n校验异常：未表明意向({weibiaoming_count}) + 接通<=15秒({daiding_15s_count}) = {weibiaoming_count + daiding_15s_count} != 意向不明线索({buming_count})，差异 {abs(mismatch_count)} 条")
        print(f"以下记录属于意向不明但既非未表明意向也非接通<=15秒：")

        detail_cols = [call_id_col, xian_id_col, phone_col, duration_col, call_status_col, intent_col, xian_status_col]
        available_cols = [c for c in detail_cols if c in mismatch_records.columns]
        if len(mismatch_records) > 0:
            print(mismatch_records[available_cols].to_string(index=False))
        else:
            print("（未定位到异常记录，请检查数据逻辑）")

    header = f"【{company} {date}】" if date else f"【{company}】"

    if invalid_phone_count > 0:
        print(f"\n{header}推送新增线索量 {total} 条（含非11位手机号 {invalid_phone_count} 条），其中：")
    else:
        print(f"\n{header}推送新增线索量 {total} 条，其中：")

    jietong_ratio = jietong_count / total * 100 if total > 0 else 0
    print(f"① 接通线索 {jietong_count} 条（{jietong_ratio:.2f}%）")

    yixiang_ratio = yixiang_count / jietong_count * 100 if jietong_count > 0 else 0
    print(f"- 意向线索（{yixiang_count} 条，接通数占比{yixiang_ratio:.0f}%）")
    print(f"  - 状态：有效")
    print()

    wuxiao_ratio = wuxiao_count / jietong_count * 100 if jietong_count > 0 else 0
    print(f"- 无效线索（{wuxiao_count} 条，接通数占比{wuxiao_ratio:.0f}%）")
    print(f"  - 无意向：{wuyixiang_count} 条")
    print(f"  - 已购车：{yichegou_count} 条")
    print()

    buming_ratio = buming_count / jietong_count * 100 if jietong_count > 0 else 0
    print(f"- 意向不明线索（{buming_count} 条，接通数占比{buming_ratio:.0f}%）")
    print(f"  - 未表明意向：{weibiaoming_count} 条")
    print(f"  - 接通<=15秒：{daiding_15s_count} 条")
    print()

    weijietong_ratio = len(weijietong) / total * 100 if total > 0 else 0
    print(f"② 未接通线索（{len(weijietong)} 条，{weijietong_ratio:.2f}%）")
    print()

    weijietong_copy = weijietong.copy()
    weijietong_copy['通话状态_合并'] = weijietong_copy[
        call_status_col
    ].apply(normalize_unconnected_reason)

    print(f"未接通原因TOP3：")
    status_counts = weijietong_copy['通话状态_合并'].value_counts()
    for status, count in status_counts.head(3).items():
        print(f"- {status}：{count} 条")

    print()

    print(f"③ 线索重呼情况：")
    df_history = df_history.copy()
    history_status_col = _col(df_history, '通话状态', prefer_call=True)
    df_history['是否接通'] = df_history[history_status_col].apply(
        lambda x: '接通' if pd.notna(x) and '已接通' in str(x) else '未接通'
    )

    chonghu_total = len(df_history)
    chonghu_jietong = df_history[df_history['是否接通'] == '接通']
    chonghu_weijietong = df_history[df_history['是否接通'] == '未接通']

    history_intent_col = _col(df_history, '意向等级', prefer_call=True)
    yixiang_chonghu = chonghu_jietong[chonghu_jietong[history_intent_col] == '高意向']

    print(f"- 线索量 {chonghu_total} 条")
    print(f"- 接通 {len(chonghu_jietong)} 条")
    print(f"  - 其中意向线索 {len(yixiang_chonghu)} 条")
    print(f"- 未接通 {len(chonghu_weijietong)} 条")

    print(f"\n{'='*60}")

    # 构建结构化数据用于月度表
    top_items = list(status_counts.head(3).items())
    return {
        "total": total,
        "jietong_count": jietong_count,
        "yixiang_count": yixiang_count,
        "wuxiao_count": wuxiao_count,
        "wuyixiang_count": wuyixiang_count,
        "yichegou_count": yichegou_count,
        "buming_count": buming_count,
        "weibiaoming_count": weibiaoming_count,
        "daiding_15s_count": daiding_15s_count,
        "small_round_count": small_round_count,
        "hangup_after_connect_count": hangup_after_connect_count,
        "weijietong_count": len(weijietong),
        "top1_name": top_items[0][0] if len(top_items) >= 1 else "",
        "top1_count": top_items[0][1] if len(top_items) >= 1 else 0,
        "top2_name": top_items[1][0] if len(top_items) >= 2 else "",
        "top2_count": top_items[1][1] if len(top_items) >= 2 else 0,
        "top3_name": top_items[2][0] if len(top_items) >= 3 else "",
        "top3_count": top_items[2][1] if len(top_items) >= 3 else 0,
        "chonghu_total": chonghu_total,
        "chonghu_jietong": len(chonghu_jietong),
        "chonghu_yixiang": len(yixiang_chonghu),
        "chonghu_weijietong": len(chonghu_weijietong),
    }


def generate_guangzhou_lxh_report(df_today, company='', date='', total_xiansuo=0):
    df_today = df_today.copy()

    call_status_col = _col(df_today, '通话状态', prefer_call=True)
    clue_intent_col = _col(df_today, '客户意向等级')
    call_status_detail_col = _col(df_today, '通话状态详情')

    df_today['是否接通'] = df_today[call_status_col].apply(
        lambda x: '接通' if pd.notna(x) and '已接通' in str(x) else '未接通'
    )

    total = total_xiansuo if total_xiansuo > 0 else len(df_today)
    jietong = df_today[df_today['是否接通'] == '接通']
    weijietong = df_today[df_today['是否接通'] == '未接通']

    jietong_count = len(jietong)
    yixiang = jietong[jietong[clue_intent_col].astype(str).str.strip() == '高意向']
    wuxiao = jietong[~jietong.index.isin(yixiang.index)]

    no_valid_dialog_values = {'接通后挂断', '沟通小于等于2轮'}
    status_detail = wuxiao[call_status_detail_col].astype(str).str.strip()
    wuxiao_no_dialog = wuxiao[status_detail.isin(no_valid_dialog_values)]
    wuxiao_no_arrival_time = wuxiao[~wuxiao.index.isin(wuxiao_no_dialog.index)]

    yixiang_count = len(yixiang)
    wuxiao_count = len(wuxiao)
    no_dialog_count = len(wuxiao_no_dialog)
    no_arrival_time_count = len(wuxiao_no_arrival_time)

    header = f"【{company} {date}】" if date else f"【{company}】"
    print(f"\n{header}推送新增线索量 {total} 条，其中：")

    jietong_ratio = jietong_count / total * 100 if total > 0 else 0
    print(f"① 接通线索 {jietong_count} 条（{jietong_ratio:.2f}%）")

    yixiang_ratio = yixiang_count / jietong_count * 100 if jietong_count > 0 else 0
    print(f"- 意向线索（{yixiang_count} 条，接通数占比{yixiang_ratio:.0f}%）")
    print(f"  - 客户意向等级：高意向")
    print()

    wuxiao_ratio = wuxiao_count / jietong_count * 100 if jietong_count > 0 else 0
    print(f"- 无效线索（{wuxiao_count} 条，接通数占比{wuxiao_ratio:.0f}%）")
    print(f"  - 无有效对话内容：{no_dialog_count} 条")
    print(f"  - 没有明确进店时间：{no_arrival_time_count} 条")
    print()

    weijietong_count = len(weijietong)
    weijietong_ratio = weijietong_count / total * 100 if total > 0 else 0
    print(f"② 未接通线索（{weijietong_count} 条，{weijietong_ratio:.2f}%）")
    print()

    weijietong_copy = weijietong.copy()
    weijietong_copy['通话状态_合并'] = weijietong_copy[
        call_status_col
    ].apply(normalize_unconnected_reason)

    print(f"未接通原因TOP3：")
    status_counts = weijietong_copy['通话状态_合并'].value_counts()
    for status, count in status_counts.head(3).items():
        ratio = count / weijietong_count * 100 if weijietong_count > 0 else 0
        print(f"- {status}：{count} 条（{ratio:.2f}%）")

    print(f"\n{'='*60}")

    top_items = list(status_counts.head(3).items())
    return {
        "total": total,
        "jietong_count": jietong_count,
        "yixiang_count": yixiang_count,
        "wuxiao_count": wuxiao_count,
        "wuyixiang_count": 0,
        "yichegou_count": 0,
        "buming_count": 0,
        "weibiaoming_count": 0,
        "daiding_15s_count": 0,
        "weijietong_count": weijietong_count,
        "top1_name": top_items[0][0] if len(top_items) >= 1 else "",
        "top1_count": top_items[0][1] if len(top_items) >= 1 else 0,
        "top2_name": top_items[1][0] if len(top_items) >= 2 else "",
        "top2_count": top_items[1][1] if len(top_items) >= 2 else 0,
        "top3_name": top_items[2][0] if len(top_items) >= 3 else "",
        "top3_count": top_items[2][1] if len(top_items) >= 3 else 0,
        "chonghu_total": 0,
        "chonghu_jietong": 0,
        "chonghu_yixiang": 0,
        "chonghu_weijietong": 0,
    }


def empty_report_data():
    return {
        "total": 0,
        "jietong_count": 0,
        "yixiang_count": 0,
        "wuxiao_count": 0,
        "wuyixiang_count": 0,
        "yichegou_count": 0,
        "buming_count": 0,
        "weibiaoming_count": 0,
        "daiding_15s_count": 0,
        "weijietong_count": 0,
        "top1_name": "",
        "top1_count": 0,
        "top2_name": "",
        "top2_count": 0,
        "top3_name": "",
        "top3_count": 0,
        "chonghu_total": 0,
        "chonghu_jietong": 0,
        "chonghu_yixiang": 0,
        "chonghu_weijietong": 0,
    }


def generate_history_only_report(df_call_dedup, company='', date=''):
    df_call_dedup = df_call_dedup.copy()

    df_call_dedup['是否接通'] = df_call_dedup['通话状态'].apply(
        lambda x: '接通' if pd.notna(x) and '已接通' in str(x) else '未接通'
    )

    total = len(df_call_dedup)
    jietong = df_call_dedup[df_call_dedup['是否接通'] == '接通']
    weijietong = df_call_dedup[df_call_dedup['是否接通'] == '未接通']

    yixiang = jietong[jietong['意向等级'] == '高意向']

    header = f"【{company} {date}】" if date else f"【{company}】"
    print(f"\n{header}推送新增线索量 0 条")

    print(f"① 线索重呼情况：")
    print(f"- 线索量 {total} 条")
    print(f"- 接通 {len(jietong)} 条")
    print(f"  - 其中意向线索 {len(yixiang)} 条")
    print(f"- 未接通 {len(weijietong)} 条")

    print(f"\n{'='*60}")


# ========== 主入口 ==========

def main():
    parser = argparse.ArgumentParser(
        description='线索数据处理与报表生成'
    )
    parser.add_argument(
        '--call_file',
        required=True,
        help='通话列表导出表路径'
    )
    parser.add_argument(
        '--xiansuo_file',
        default=None,
        help='线索明细表路径（可选，不提供则仅生成历史线索报告）'
    )
    parser.add_argument(
        '--company',
        required=True,
        help='公司名称（用于输出文件命名及报告标题）'
    )
    parser.add_argument(
        '--date',
        default=None,
        help='日期（YYMMDD格式，不传则默认当天，如260501）'
    )
    parser.add_argument(
        '--output_dir',
        default='.',
        help='输出目录（默认当前目录）'
    )
    parser.add_argument(
        '--group_by_call_field',
        default=None,
        help='可选：按通话列表字段分组分别统计，例如 机器人'
    )
    parser.add_argument(
        '--exclude_clue_ids',
        default=None,
        help='可选：统计前剔除的线索ID，支持逗号或空白分隔'
    )
    parser.add_argument(
        '--mtd_start_date',
        default=None,
        help='可选：MTD 起始日期（YYMMDD），不传则按原逻辑统计月初至指定日期'
    )
    parser.add_argument(
        '--required_group_values',
        default=None,
        help='可选：强制输出的分组字段值，逗号分隔；用于当天无数据但汇总表仍需保留列'
    )
    parser.add_argument(
        '--merge_summary_title',
        default=None,
        help='可选：按分组汇总时合并成一个汇总表的文件标题'
    )
    parser.add_argument(
        '--group_display_names',
        default=None,
        help='可选：分组展示名称映射，JSON 对象，键为原始分组值，值为展示名称'
    )
    parser.add_argument(
        '--group_summary_names',
        default=None,
        help='可选：分组汇总表名称映射，JSON 对象，键为原始分组值，值为汇总表名称'
    )
    parser.add_argument(
        '--unmatched_group_name',
        default='未匹配机器人',
        help='可选：MTD线索无法通过话单匹配到分组字段时的归属名称'
    )
    parser.add_argument(
        '--clue_match_limit',
        type=int,
        default=None,
        help='可选：仅使用按日期筛选后的前 N 条线索明细参与匹配和当日报告'
    )

    args = parser.parse_args()
    exclude_ids = parse_exclude_ids(args.exclude_clue_ids)
    required_group_values = parse_group_values(args.required_group_values)
    group_display_names = parse_group_display_names(args.group_display_names)
    group_summary_names = parse_group_display_names(args.group_summary_names)

    if not os.path.exists(args.call_file):
        print(f"错误：通话列表文件不存在: {args.call_file}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    # 子文件夹
    intermediate_dir = os.path.join(args.output_dir, "中间文件")
    summary_dir = os.path.join(args.output_dir, "汇总表")
    os.makedirs(intermediate_dir, exist_ok=True)
    os.makedirs(summary_dir, exist_ok=True)

    print("=" * 60)
    print("线索数据处理与报表生成")
    print("=" * 60)

    # 读取通话列表
    df_call = pd.read_excel(args.call_file, engine='openpyxl', dtype={'线索ID': str})
    df_call = normalize_id_column(df_call, '通话列表')
    if args.group_by_call_field and args.group_by_call_field not in df_call.columns:
        print(f"错误：通话列表缺少分组字段: {args.group_by_call_field}")
        sys.exit(1)
    df_call = filter_excluded_clues(df_call, exclude_ids, "通话列表")

    # 按日期筛选通话列表（根据"结束时间"）
    date_str = args.date or datetime.now().strftime('%y%m%d')
    filter_date = pd.to_datetime(date_str, format='%y%m%d')
    mtd_start_date = pd.to_datetime(args.mtd_start_date, format='%y%m%d') if args.mtd_start_date else None
    df_call['结束时间'] = pd.to_datetime(df_call['结束时间'], errors='coerce')
    # 日报指标只使用目标日话单；机器人归属允许使用完整月度快照。
    # 历史补跑时，线索可能在下发日没有通话、之后才首次呼叫，若把映射
    # 话单截断到目标日会导致多机器人日报静默漏数。
    df_call_mapping = df_call.copy()

    if mtd_start_date is not None:
        print(f"\n机器人历史映射起始日期: {mtd_start_date.date()}")

    print(f"\n按日期筛选通话列表：结束时间 == {filter_date.date()}")
    before = len(df_call)
    df_call = df_call[df_call['结束时间'].dt.date == filter_date.date()]
    print(f"  筛选前: {before} 条，筛选后: {len(df_call)} 条")

    # 步骤1：通话列表去重
    df_call_dedup = deduplicate_calls(df_call, intermediate_dir, args.company)

    if args.xiansuo_file:
        if not os.path.exists(args.xiansuo_file):
            print(f"错误：线索明细文件不存在: {args.xiansuo_file}")
            sys.exit(1)

        df_xian = pd.read_excel(args.xiansuo_file, engine='openpyxl', dtype={'线索ID': str})
        df_xian = normalize_id_column(df_xian, '线索明细')
        df_xian = filter_excluded_clues(df_xian, exclude_ids, "线索明细")

        # 提前转换时间列
        df_xian['线索下发时间'] = pd.to_datetime(df_xian['线索下发时间'], errors='coerce')

        mtd_begin = (
            mtd_start_date
            if mtd_start_date is not None
            else filter_date.replace(day=1)
        )
        df_xian_mtd = df_xian[
            (df_xian['线索下发时间'].dt.date >= mtd_begin.date())
            & (df_xian['线索下发时间'].dt.date <= filter_date.date())
        ].drop_duplicates(subset=['线索ID'], keep='first').copy()
        df_call_mtd = df_call_mapping[
            (df_call_mapping['结束时间'].dt.date >= mtd_begin.date())
            & (df_call_mapping['结束时间'].dt.date <= filter_date.date())
        ].copy()
        monthly_stats = build_monthly_stats(df_xian_mtd, df_call_mtd)
        monthly_stats_by_group = {}
        if args.group_by_call_field:
            monthly_stats_by_group = build_monthly_stats_by_group(
                df_xian_mtd,
                df_call_mtd,
                args.group_by_call_field,
                unmatched_group_name=args.unmatched_group_name,
            )
            empty_mtd_stats = {
                '累计线索量': 0,
                '累计接通量': 0,
                '累计有效线索量': 0,
                '累计呼叫通次': 0,
            }
            for group_name in required_group_values:
                monthly_stats_by_group.setdefault(
                    group_name,
                    dict(empty_mtd_stats),
                )
        print(
            "\nMTD完整快照: "
            f"线索 {monthly_stats['累计线索量']}，"
            f"接通 {monthly_stats['累计接通量']}，"
            f"有效 {monthly_stats['累计有效线索量']}，"
            f"呼叫通次 {monthly_stats['累计呼叫通次']}"
        )

        print(f"\n按日期筛选线索明细：线索下发时间 == {filter_date.date()}")
        before = len(df_xian)
        df_xian = df_xian[df_xian['线索下发时间'].dt.date == filter_date.date()]
        print(f"  筛选前: {before} 条，筛选后: {len(df_xian)} 条")
        df_xian = limit_clue_records_for_matching(df_xian, args.clue_match_limit)

        df_xian, df_call_dedup = normalize_and_mask_phones(df_xian, df_call_dedup)

        df_xian, phone_warning_xian, invalid_xian_count = check_phone_numbers(df_xian)
        df_call_dedup, phone_warning_call, invalid_call_count = check_call_phone_numbers(df_call_dedup)

        phone_warning = phone_warning_xian + phone_warning_call
        invalid_phone_count = invalid_xian_count

        df_today, df_history, daily_diagnostics = build_daily_reporting_population(
            df_xian,
            df_call_dedup,
            filter_date,
            group_by_call_field=args.group_by_call_field,
            required_group_values=required_group_values,
            df_call_mtd=df_call_mapping,
            unmatched_group_name=args.unmatched_group_name,
            output_dir=intermediate_dir,
            company=args.company,
        )
        call_count_total = count_calls_for_clue_population(df_call, df_today)
        print(
            "  当日口径校验: "
            f"新增 {daily_diagnostics['daily_dispatched_clues']}，"
            f"有话单 {daily_diagnostics['daily_dispatched_called_clues']}，"
            f"无话单 {daily_diagnostics['daily_uncalled_clues']}，"
            f"历史重呼 {daily_diagnostics['daily_called_historical_clues']}"
        )

        if args.group_by_call_field:
            group_col = _col(df_today, args.group_by_call_field, prefer_call=True)
            history_group_col = _col(df_history, args.group_by_call_field, prefer_call=True)
            groups = sorted({
                str(v).strip()
                for v in list(df_today[group_col].dropna()) + list(df_history[history_group_col].dropna())
                if str(v).strip() and str(v).strip() != 'nan'
            })
            groups = set(groups) | set(monthly_stats_by_group.keys())
            if required_group_values:
                groups = groups & set(required_group_values)
                groups |= set(required_group_values)
            groups = sorted(groups)
            reconciliation = reconcile_group_population(
                df_today,
                group_col,
                required_group_values,
                unmatched_group_name=args.unmatched_group_name,
            )
            print(
                "  分组口径校验: "
                f"源线索 {reconciliation['source_total']}，"
                f"纳入配置机器人 {reconciliation['included']}，"
                f"明确排除 {reconciliation['excluded']}，"
                f"未匹配 {reconciliation['unmatched']}"
            )
            validate_group_reconciliation(reconciliation, args.company)
            print(f"\n按 {args.group_by_call_field} 分组统计: {', '.join(groups) if groups else '无'}")
            combined_summary_items = []
            grouped_artifact_names = []

            for group_name in groups:
                if group_name in group_display_names:
                    report_company = group_display_names[group_name]
                elif args.company == "广州龙星行":
                    report_company = guangzhou_robot_name(group_name)
                else:
                    report_company = f"{args.company}-{safe_output_name(group_name)}"
                summary_company = group_summary_names.get(group_name, report_company)
                today_group = df_today[df_today[group_col].astype(str).str.strip() == group_name]
                history_group = df_history[df_history[history_group_col].astype(str).str.strip() == group_name]
                if args.company == "广州龙星行":
                    if group_name == args.unmatched_group_name and len(today_group) == 0:
                        report_data = empty_report_data()
                    else:
                        report_data = generate_guangzhou_lxh_report(
                            today_group,
                            company=report_company, date=args.date,
                            total_xiansuo=len(today_group)
                        )
                else:
                    report_data = generate_report(
                        today_group, history_group,
                        company=report_company, date=args.date,
                        phone_warning=phone_warning,
                        invalid_phone_count=0,
                        total_xiansuo=len(today_group)
                    )

                if report_data:
                    # 仅统计属于该组当日新线索的呼叫（排除对前几天线索的重呼）
                    group_clue_ids = set(today_group['线索ID'].unique())
                    call_group = df_call[
                        (df_call[args.group_by_call_field].astype(str).str.strip() == group_name) &
                        (df_call['线索ID'].isin(group_clue_ids))
                    ]
                    report_data["call_count"] = int(len(call_group))
                    report_data["connected_avg_duration_minutes"] = calculate_connected_avg_duration_minutes(call_group)
                    if args.merge_summary_title or args.company == "广州龙星行":
                        tracking_company = build_group_tracking_name(args.company, report_company)
                        legacy_tracking_company = f"{args.company}-{safe_output_name(group_name)}"
                        grouped_artifact_names.extend([report_company, legacy_tracking_company])
                        combined_summary_items.append({
                            "company": summary_company,
                            "tracking_company": tracking_company,
                            "tracking_aliases": [legacy_tracking_company],
                            "data": report_data,
                            "monthly_stats": monthly_stats_by_group.get(group_name, {}),
                        })
                    else:
                        generate_daily_summary(
                            company=summary_company,
                            date=date_str,
                            data=report_data,
                            output_dir=summary_dir,
                            monthly_stats=monthly_stats_by_group.get(group_name, {}),
                        )
            if combined_summary_items:
                cleanup_merged_summary_artifacts(
                    summary_dir,
                    date_str,
                    args.merge_summary_title or "广州售后",
                    grouped_artifact_names,
                )
                generate_multi_daily_summary(
                    title=args.merge_summary_title or "广州售后",
                    date=date_str,
                    grouped_data=combined_summary_items,
                    output_dir=summary_dir,
                )
        else:
            report_data = generate_report(
                df_today, df_history,
                company=args.company, date=args.date,
                phone_warning=phone_warning,
                invalid_phone_count=invalid_phone_count,
                total_xiansuo=len(df_today)
            )

            if report_data:
                report_data["call_count"] = call_count_total
                generate_daily_summary(
                    company=args.company,
                    date=date_str,
                    data=report_data,
                    output_dir=summary_dir,
                    monthly_stats=monthly_stats,
                )

        if phone_warning:
            print(phone_warning)
    else:
        df_call_dedup, phone_warning_call, _ = check_call_phone_numbers(df_call_dedup)

        generate_history_only_report(df_call_dedup, args.company, args.date)

        if phone_warning_call:
            print(phone_warning_call)

    print("\n处理完成！")


if __name__ == '__main__':
    main()
