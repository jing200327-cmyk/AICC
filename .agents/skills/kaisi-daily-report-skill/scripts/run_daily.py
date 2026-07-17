# -*- coding: utf-8 -*-
"""Generate daily call report artifacts from one CSV file.

Pipeline:
  CSV/XLSX export -> report.json -> Markdown report -> onepage PNG
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import render_html


ROOT = Path(__file__).resolve().parents[1]


ATTENTION_FALLBACK = {
    "微信加群": ["加微信", "微信", "群"],
    "优惠活动": ["优惠", "活动", "券", "油品"],
    "冷门找件": ["冷门", "找件", "配件"],
    "平台使用": ["app", "APP", "平台", "不会用", "不怎么会用"],
}

OBJECTION_FALLBACK = {
    "需求变化": ["生意不好", "没生意", "没需要", "暂时不需要", "有需要再说", "目前没"],
    "使用习惯": ["不习惯", "很少", "不常用", "没登", "不用平台"],
    "平台体验": ["不会用", "不怎么会用", "操作", "平台"],
    "价格原因": ["价格", "贵", "多少钱"],
    "信任问题": ["售后", "业务经理", "信任", "没解决"],
}

BUYIN_RULES = [
    ("微信承接", ["加微信", "微信加一下", "加微信吧", "加您微信", "微信"]),
    ("活动/优惠兴趣", ["优惠活动", "优惠", "活动", "券", "油品"]),
    ("平台回看/自助查询", ["登上去看", "看一下", "自己查", "再去弄", "平台", "app", "APP"]),
    ("已有顾问/人工承接", ["业务员", "专门联系的人", "咨询", "联系他们"]),
    ("配件需求场景", ["配件", "什么配件", "少了配件", "找的啥"]),
    ("后续需求再联系", ["有需要", "有的话", "再联系", "再说", "研究一下", "到时候"]),
]

BUYIN_ACTIONS = {
    "微信承接": "加企微/群，后续发单代查",
    "活动/优惠兴趣": "发活动明细，引导领券/油品",
    "平台回看/自助查询": "发平台入口/权益，提醒回访",
    "已有顾问/人工承接": "转交顾问，延续人工关系",
    "配件需求场景": "承接配件/冷门件询价",
    "后续需求再联系": "进入二次触达池",
    "非真人有效待确认": "人工确认是否真实客户意向",
}


def pct(num: int | float, den: int | float) -> float:
    return 0.0 if not den else round(num / den * 100, 1)


def pct_str(num: int | float, den: int | float) -> str:
    return f"{pct(num, den):.1f}%"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def extract_line_value(text: str, key: str) -> str:
    m = re.search(rf"{re.escape(key)}[:：]\s*([^\n\r]*)", text)
    return m.group(1).strip() if m else ""


def extract_after_phrase(text: str, phrase: str) -> str:
    m = re.search(rf"{re.escape(phrase)}([^，,\n\r。；; ]+)", text)
    return m.group(1).strip() if m else ""


def lead_state(row: dict[str, str]) -> str:
    text = f"{row.get('质检结果') or ''}\n{row.get('小结') or ''}"
    return extract_line_value(text, "客户线索状态") or "未判定"


def attention_label(row: dict[str, str]) -> str:
    text = f"{row.get('质检结果') or ''}\n{row.get('小结') or ''}"
    label = extract_after_phrase(text, "当前关注")
    if label and label != "未知":
        return label
    dialogue = "\n".join(customer_lines(row))
    for name, words in ATTENTION_FALLBACK.items():
        if any(w in dialogue for w in words):
            return name
    return "未知"


def objection_label(row: dict[str, str]) -> str:
    text = f"{row.get('质检结果') or ''}\n{row.get('小结') or ''}"
    label = extract_after_phrase(text, "核心抗拒点")
    if label and label != "未知":
        return label
    dialogue = "\n".join(customer_lines(row))
    for name, words in OBJECTION_FALLBACK.items():
        if any(w in dialogue for w in words):
            return name
    return "未知"


def buyin_label(row: dict[str, str]) -> str:
    if is_nonhuman_or_message(row):
        return "非真人有效待确认"
    dialogue = "\n".join(customer_lines(row))
    att = attention_label(row)
    positive = any(w in dialogue for w in ["可以", "好", "行", "嗯"])
    if att == "微信加群" and positive:
        return "微信承接"
    if att == "优惠活动" and positive:
        return "活动/优惠兴趣"
    if att == "冷门找件":
        return "配件需求场景"
    for label, words in BUYIN_RULES:
        if any(w in dialogue for w in words):
            return label
    return "未知"


def buyin_evidence(row: dict[str, str]) -> list[str]:
    label = buyin_label(row)
    lines = meaningful_quotes(row)
    if label == "未知":
        return lines[:2]
    if label == "非真人有效待确认":
        return [line for line in customer_lines(row) if "智能助理" in line or "转达" in line or "优惠活动" in line][:2]
    keywords = dict(BUYIN_RULES).get(label, [])
    selected = [line for line in lines if any(k in line for k in keywords)]
    if not selected and label == "微信承接":
        selected = [line for line in lines if any(k in line for k in ["可以", "好", "行"])]
    if not selected and label == "活动/优惠兴趣":
        selected = [line for line in lines if any(k in line for k in ["好", "有", "需要", "听"])]
    if not selected and label == "配件需求场景":
        selected = [line for line in lines if "配件" in line or "找" in line]
    for line in lines:
        if line not in selected:
            selected.append(line)
    return selected[:3]


def customer_lines(row: dict[str, str]) -> list[str]:
    lines = []
    for raw in (row.get("对话内容") or "").splitlines():
        raw = raw.strip()
        if raw.startswith("客户:") or raw.startswith("客户："):
            value = raw.split(":", 1)[-1] if ":" in raw else raw.split("：", 1)[-1]
            value = value.strip()
            if value:
                lines.append(value)
    return lines


def meaningful_quotes(row: dict[str, str]) -> list[str]:
    weak = {
        "喂",
        "喂！",
        "嗯",
        "嗯。",
        "哎",
        "哎。",
        "好",
        "好！",
        "好的",
        "好的好的",
        "对",
        "对。",
    }
    quotes = []
    for line in customer_lines(row):
        clean = line.strip()
        if clean in weak:
            continue
        if len(clean) < 4:
            continue
        if len(clean) > 34 and not any(k in clean for k in ["生意", "优惠", "微信", "不习惯", "不会用", "很少", "平台"]):
            continue
        if clean not in quotes:
            quotes.append(clean)
    return quotes


def select_case_quotes(row: dict[str, str], attention: str) -> list[str]:
    quotes = meaningful_quotes(row)
    keyword_map = {
        "微信加群": ["微信", "加微信", "可以", "不习惯", "不会用", "生意"],
        "优惠活动": ["优惠", "活动", "券", "油品", "价格"],
        "平台使用": ["不会用", "不怎么会用", "平台", "APP"],
    }
    keys = keyword_map.get(attention, ["微信", "优惠", "平台"])
    selected = [q for q in quotes if any(k in q for k in keys)]
    for q in quotes:
        if q not in selected:
            selected.append(q)
    return selected[:4]


def case_title(row: dict[str, str], attention: str) -> str:
    dialogue = "\n".join(customer_lines(row))
    if "不怎么会用" in dialogue or "不会用" in dialogue:
        return "不会用平台，转为微信代查"
    if "不习惯" in dialogue or "很少" in dialogue:
        return "不常用平台，但愿意微信对接"
    if "生意" in dialogue or "没生意" in dialogue:
        return "生意差但愿意加微信，完成后续承接"
    if attention == "优惠活动":
        return "关注优惠活动，进入后续触达"
    if attention == "微信加群":
        return "愿意加微信，完成后续承接"
    return "有效客户完成后续承接"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) >= 11:
        phone = digits[-11:]
        return f"{phone[:3]}****{phone[-4:]}"
    if "****" in (value or ""):
        return value
    return value or "-"


def short_call_id(value: str) -> str:
    return f"{value[:8]}..." if value and len(value) > 11 else (value or "-")


def is_connected(row: dict[str, str]) -> bool:
    return (row.get("通话状态") or "").startswith("已接通")


def is_unconnected(row: dict[str, str]) -> bool:
    return (row.get("通话状态") or "").startswith("未接通")


def is_human_content(row: dict[str, str]) -> bool:
    if not is_connected(row):
        return False
    if is_nonhuman_or_message(row):
        return False
    return bool(customer_lines(row))


def is_nonhuman_or_message(row: dict[str, str]) -> bool:
    dialogue = row.get("对话内容") or ""
    keywords = ["智能助理", "机主", "留言", "转告", "自动韵达服务"]
    return bool(customer_lines(row)) and any(k in dialogue for k in keywords)


def status_bucket(status: str) -> str:
    if "无应答" in status:
        return "无应答"
    if "暂时无法拨通" in status:
        return "暂时无法拨通/语音留言"
    if "拒接" in status:
        return "拒接"
    if "线路限制" in status:
        return "线路限制"
    if "占线" in status:
        return "占线"
    if any(x in status for x in ["停机", "关机", "黑名单"]):
        return "停机/关机/黑名单"
    if "空号" in status:
        return "空号"
    return "其他"


def counter_items(counter: Counter, denominator: int, key_name: str) -> list[dict[str, Any]]:
    return [
        {"name": name, "count": count, "rate": pct(count, denominator)}
        for name, count in counter.most_common()
    ]


def typical_quotes(rows: list[dict[str, str]], label_name: str, label_func, limit: int = 3) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in rows:
        label = label_func(row)
        if label == "未知":
            continue
        if label_name and label != label_name:
            continue
        quotes = result.setdefault(label, [])
        for line in customer_lines(row):
            if 4 <= len(line) <= 24 and line not in quotes:
                quotes.append(line)
            if len(quotes) >= limit:
                break
    return result


def buyin_quotes(rows: list[dict[str, str]], limit: int = 3) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in rows:
        label = buyin_label(row)
        if label == "未知":
            continue
        quotes = result.setdefault(label, [])
        for line in buyin_evidence(row):
            if line and line not in quotes:
                quotes.append(line)
            if len(quotes) >= limit:
                break
    return result


def build_report(input_path: Path, date: str, cutoff: str, title: str) -> dict[str, Any]:
    rows = read_rows(input_path)
    connected = [r for r in rows if is_connected(r)]
    unconnected = [r for r in rows if is_unconnected(r)]
    human = [r for r in connected if is_human_content(r)]
    states = Counter(lead_state(r) for r in rows)
    connected_states = Counter(lead_state(r) for r in connected)
    valid_rows = [r for r in rows if lead_state(r) == "有效"]
    invalid_rows = [r for r in rows if lead_state(r) == "无效"]
    pending_connected = [r for r in connected if lead_state(r) == "待定"]
    unknown_connected = [r for r in connected if lead_state(r) == "未判定"]

    effective_attention_counter = Counter(attention_label(r) for r in valid_rows)
    buyin_counter = Counter(buyin_label(r) for r in valid_rows)
    objection_rows = [r for r in human if lead_state(r) in {"待定", "无效"}]
    objection_counter = Counter(objection_label(r) for r in objection_rows)

    attention_known = sum(v for k, v in effective_attention_counter.items() if k != "未知")
    buyin_known = sum(v for k, v in buyin_counter.items() if k != "未知")
    objection_known = sum(v for k, v in objection_counter.items() if k != "未知")
    effective_attention_known = sum(v for k, v in effective_attention_counter.items() if k != "未知")

    unconnected_counter = Counter(status_bucket(r.get("通话状态") or "") for r in unconnected)
    status_counter = Counter(r.get("通话状态") or "未知" for r in rows)

    case_candidates = [r for r in valid_rows if is_human_content(r)]
    cases = []
    used_call_ids = set()
    case_priority = [
        lambda r: "生意" in "\n".join(customer_lines(r)) and attention_label(r) != "未知",
        lambda r: ("不怎么会用" in "\n".join(customer_lines(r)) or "不会用" in "\n".join(customer_lines(r))) and attention_label(r) != "未知",
        lambda r: ("不习惯" in "\n".join(customer_lines(r)) or "很少" in "\n".join(customer_lines(r))) and attention_label(r) != "未知",
        lambda r: buyin_label(r) not in {"未知", "非真人有效待确认"},
        lambda r: attention_label(r) != "未知",
    ]
    for matcher in case_priority:
        target_rows = [
            r
            for r in case_candidates
            if matcher(r)
            and r.get("通话ID") not in used_call_ids
            and len(meaningful_quotes(r)) >= 2
        ]
        if not target_rows:
            continue
        row = sorted(target_rows, key=lambda r: int(float(r.get("通话时长") or 0)), reverse=True)[0]
        att = attention_label(row)
        buyin = buyin_label(row)
        quotes = buyin_evidence(row)
        used_call_ids.add(row.get("通话ID"))
        cases.append(
            {
                "call_id": row.get("通话ID"),
                "call_id_short": short_call_id(row.get("通话ID") or ""),
                "customer": row.get("客户姓名"),
                "phone": mask_phone(row.get("客户真实号码") or row.get("呼叫号码") or ""),
                "duration": int(float(row.get("通话时长") or 0)),
                "title": case_title(row, att),
                "attention": att,
                "buyin": buyin,
                "quotes": quotes[:4],
            }
        )
        if len(cases) >= 3:
            break

    report = {
        "meta": {
            "title": title,
            "date": date,
            "cutoff": cutoff,
            "source_file": input_path.name,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": {
            "outbound": len(rows),
            "connected": len(connected),
            "unconnected": len(unconnected),
            "valid": len(valid_rows),
            "invalid": len(invalid_rows),
            "pending_after_connected": len(pending_connected),
            "unknown_after_connected": len(unknown_connected),
            "connect_rate": pct(len(connected), len(rows)),
            "unconnected_rate": pct(len(unconnected), len(rows)),
            "valid_per_outbound": pct(len(valid_rows), len(rows)),
            "valid_per_connected": pct(len(valid_rows), len(connected)),
            "pending_per_connected": pct(len(pending_connected), len(connected)),
            "invalid_per_connected": pct(len(invalid_rows), len(connected)),
        },
        "status_breakdown": counter_items(status_counter, len(rows), "status"),
        "unconnected_breakdown": counter_items(unconnected_counter, len(unconnected), "reason"),
        "content_quality": {
            "human_content": len(human),
            "non_human_or_message": sum(1 for r in connected if is_nonhuman_or_message(r)),
            "blank_or_short": len(connected) - len(human) - sum(1 for r in connected if is_nonhuman_or_message(r)),
            "human_rate_connected": pct(len(human), len(connected)),
        },
        "voc": {
            "base": len(human),
            "objection_base": len(objection_rows),
            "attention_unknown": effective_attention_counter.get("未知", 0),
            "buyin_unknown": buyin_counter.get("未知", 0),
            "objection_unknown": objection_counter.get("未知", 0),
            "attention": counter_items(
                Counter({k: v for k, v in effective_attention_counter.items() if k != "未知"}), attention_known, "attention"
            ),
            "objection": counter_items(
                Counter({k: v for k, v in objection_counter.items() if k != "未知"}), objection_known, "objection"
            ),
            "effective_attention": counter_items(
                Counter({k: v for k, v in effective_attention_counter.items() if k != "未知"}),
                effective_attention_known,
                "attention",
            ),
            "buyin": counter_items(
                Counter({k: v for k, v in buyin_counter.items() if k != "未知"}),
                buyin_known,
                "buyin",
            ),
            "attention_quotes": typical_quotes(valid_rows, "", attention_label),
            "buyin_quotes": buyin_quotes(valid_rows),
            "objection_quotes": typical_quotes(objection_rows, "", objection_label),
        },
        "cases": cases,
        "insights": [
            f"截止 {cutoff} 共呼出 {len(rows)} 通，接通 {len(connected)} 通，接通率 {pct_str(len(connected), len(rows))}。",
            f"有效线索 {len(valid_rows)} 条，呼出到有效 {pct_str(len(valid_rows), len(rows))}，接通到有效 {pct_str(len(valid_rows), len(connected))}。",
            f"接通后待定 {len(pending_connected)} 条，占接通 {pct_str(len(pending_connected), len(connected))}，是当前最大接通后损耗。",
            f"有效客户侧重看 Buy-in 点；待定和无效客户侧重看抗拒点，抗拒点分母为 {len(objection_rows)} 条真人有内容的待定/无效接通。",
        ],
    }
    return report


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    aligns = ["---"] + ["---:" for _ in headers[1:]]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(aligns) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def write_md(report: dict[str, Any], path: Path) -> None:
    m = report["metrics"]
    meta = report["meta"]
    lines = [
        f"# {meta['title']}阶段日报",
        "",
        f"数据来源：`{meta['source_file']}`  ",
        f"统计日期：{meta['date']}，截止约 {meta['cutoff']}  ",
        f"统计对象：CSV 中全部有效通话明细，共 {m['outbound']} 条",
        "",
        "## 一、分析口径",
        "",
        f"- 呼出：CSV 中全部通话记录，共 {m['outbound']} 条。",
        f"- 接通：`通话状态` 以 `已接通` 开头的记录，共 {m['connected']} 条。",
        f"- 未接通：`通话状态` 以 `未接通` 开头的记录，共 {m['unconnected']} 条。",
        "- 有效/无效/待定：从 `质检结果` 或 `小结` 中的 `客户线索状态` 提取。",
        "- VOC 分析：有效客户看 Buy-in 点；待定和无效客户看抗拒点；`未知` 仅作为数据质量备注，不参与明确标签占比。",
        "",
        "## 二、阶段核心结论",
        "",
    ]
    lines += [f"{i}. {x}" for i, x in enumerate(report["insights"], 1)]
    lines += [
        "",
        "## 三、整体漏斗",
        "",
        md_table(
            ["环节", "数量", "占上一级", "占总呼出"],
            [
                ["呼出", m["outbound"], "100.0%", "100.0%"],
                ["接通", m["connected"], f"{m['connect_rate']:.1f}%", f"{m['connect_rate']:.1f}%"],
                ["有效", m["valid"], f"{m['valid_per_connected']:.1f}%", f"{m['valid_per_outbound']:.1f}%"],
                ["无效", m["invalid"], f"{m['invalid_per_connected']:.1f}%", pct_str(m["invalid"], m["outbound"])],
                [
                    "待定",
                    m["pending_after_connected"],
                    f"{m['pending_per_connected']:.1f}%",
                    pct_str(m["pending_after_connected"], m["outbound"]),
                ],
                [
                    "接通但未判定",
                    m["unknown_after_connected"],
                    pct_str(m["unknown_after_connected"], m["connected"]),
                    pct_str(m["unknown_after_connected"], m["outbound"]),
                ],
                ["未接通", m["unconnected"], "-", f"{m['unconnected_rate']:.1f}%"],
            ],
        ),
        "",
        "## 四、未接通原因归类",
        "",
        md_table(
            ["未接通原因", "数量", "占未接通"],
            [[x["name"], x["count"], f"{x['rate']:.1f}%"] for x in report["unconnected_breakdown"]],
        ),
        "",
        "## 五、接通内容质量",
        "",
        md_table(
            ["内容类型", "数量", "占接通"],
            [
                [
                    "真人有内容",
                    report["content_quality"]["human_content"],
                    f"{report['content_quality']['human_rate_connected']:.1f}%",
                ],
                [
                    "非真人接听/留言/通信助理",
                    report["content_quality"]["non_human_or_message"],
                    pct_str(report["content_quality"]["non_human_or_message"], m["connected"]),
                ],
                [
                    "接通后无有效内容/空白/秒挂",
                    report["content_quality"]["blank_or_short"],
                    pct_str(report["content_quality"]["blank_or_short"], m["connected"]),
                ],
            ],
        ),
        "",
        "## 六、VOC 分析",
        "",
        f"有效客户 Buy-in 点分母为 {m['valid']} 条有效线索；待定/无效客户抗拒点分母为 {report['voc']['objection_base']} 条真人有内容的待定/无效接通记录。",
        "",
        "### 6.1 有效客户 Buy-in 点",
        "",
        md_table(
            ["Buy-in 点", "数量", "占明确 Buy-in"],
            [[x["name"], x["count"], f"{x['rate']:.1f}%"] for x in report["voc"]["buyin"]],
        ),
        "",
        f"备注：有效线索中另有 {report['voc']['buyin_unknown']} 条 `未知`，不参与明确 Buy-in 占比。",
        "",
        "### 6.2 待定/无效客户抗拒点",
        "",
        md_table(
            ["抗拒点", "数量", "占明确抗拒点"],
            [[x["name"], x["count"], f"{x['rate']:.1f}%"] for x in report["voc"]["objection"]],
        ),
        "",
        f"备注：待定/无效客户中另有 {report['voc']['objection_unknown']} 条 `未知`，不参与明确抗拒点占比。",
        "",
        "## 七、有效线索画像",
        "",
        "有效客户不再分析抗拒点，仅保留客户愿意继续承接的 Buy-in 点。",
        "",
        "### 7.1 有效客户 Buy-in 点",
        "",
        md_table(
            ["Buy-in 点", "数量", "占明确 Buy-in"],
            [[x["name"], x["count"], f"{x['rate']:.1f}%"] for x in report["voc"]["buyin"]],
        ),
        "",
        "## 八、机器人能力 Good Case",
        "",
    ]
    for i, case in enumerate(report["cases"], 1):
        quote = " ".join(f"“{q}”" for q in case["quotes"][:3])
        lines += [
            f"### Case {i}：{case['title']}",
            "",
            f"- CallID：`{case['call_id']}`",
            f"- 手机号：{case['phone']}",
            f"- 客户：{case['customer']}",
            f"- 通话时长：{case['duration']} 秒",
            f"- 标签：有效；Buy-in={case['buyin']}",
            f"- 典型原声：{quote}",
            "",
        ]
    lines += [
        "## 九、一句话结论",
        "",
        f"{meta['date']} 截止 {meta['cutoff']} 的外呼接通率为 {m['connect_rate']:.1f}%，有效线索 {m['valid']} 条。当前有效客户的核心 Buy-in 点应围绕微信承接、活动优惠、平台回看和后续需求触达展开。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def cutoff_label(value: str) -> str:
    if ":" not in value:
        return value
    hour, minute = value.split(":", 1)
    return f"{hour}点" if minute == "00" else f"{hour}点{minute}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--title", default="开思未活跃客户激活外呼")
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else ROOT / "outputs" / args.date
    output_dir.mkdir(parents=True, exist_ok=True)

    report = build_report(input_path, args.date, args.cutoff, args.title)
    json_path = output_dir / "report.json"
    time_label = cutoff_label(args.cutoff)
    md_path = output_dir / f"开思{args.date[5:7]}.{args.date[8:10]}截止{time_label}外呼日报.md"
    png_path = output_dir / f"开思{args.date[5:7]}.{args.date[8:10]}截止{time_label}外呼进度汇报onepage.png"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(report, md_path)
    html_path = output_dir / png_path.with_suffix(".html").name
    render_html.render_png(report, png_path, html_path)

    print(json_path)
    print(md_path)
    print(png_path)
    print(
        json.dumps(
            {
                "outbound": report["metrics"]["outbound"],
                "connected": report["metrics"]["connected"],
                "valid": report["metrics"]["valid"],
                "pending_after_connected": report["metrics"]["pending_after_connected"],
                "unconnected": report["metrics"]["unconnected"],
                "voc_base": report["voc"]["base"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
