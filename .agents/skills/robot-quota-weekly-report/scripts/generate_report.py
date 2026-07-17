from __future__ import annotations

import argparse
import sys
from pathlib import Path


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


APP_ROOT = repository_root() / '线索变量脚本' / 'glm-proxy'
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from robot_quota.report_renderer import (
    compute_stats,
    parse_excel,
    render_daily,
    render_weekly,
    write_stats_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description='生成外呼机器人用量日报或周报图片')
    parser.add_argument('input_path')
    parser.add_argument('output_path')
    parser.add_argument('title', nargs='?', default='')
    parser.add_argument('--mode', choices=('auto', 'daily', 'weekly'), default='auto')
    args = parser.parse_args()

    input_path = Path(args.input_path)
    output_path = Path(args.output_path)
    days = parse_excel(input_path)
    if not days:
        raise SystemExit('未能从表格中解析出日期列，请检查输入格式。')
    stats = compute_stats(days)
    mode = args.mode
    if mode == 'auto':
        mode = 'daily' if len(days) == 1 else 'weekly'

    if mode == 'daily':
        first_day = next(iter(days))
        stats['all_entries'] = days[first_day]
        render_daily(stats, output_path, title=args.title or '外呼机器人用量日报')
    else:
        day_labels = stats['day_labels']
        subtitle = f'统计周期：{day_labels[0]} - {day_labels[-1]}'
        render_weekly(
            stats,
            output_path,
            title=args.title or '外呼机器人用量周报',
            subtitle=subtitle,
        )

    stats_path = output_path.with_name(f'{output_path.stem}_stats.json')
    write_stats_json(stats, stats_path)
    print(f'已生成: {output_path}')
    print(f'已生成统计数据: {stats_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
