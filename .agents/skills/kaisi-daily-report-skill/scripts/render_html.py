# -*- coding: utf-8 -*-
"""Render the daily report one-pager via HTML/CSS + headless Chromium.

The previous version drew the PNG with PIL using hard-coded pixel
coordinates, which overflowed whenever the data changed. Here we build a
responsive HTML document (flex/grid + automatic text wrapping) and let
Chromium paint it, so the layout adapts to the content automatically.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


PALETTE = ["#2369E8", "#20B9DD", "#FF8A1F", "#9DB1C7", "#7FC5D0", "#8CA6C8", "#AEBBD0", "#C6D1E1"]

BUYIN_ACTIONS = {
    "微信承接": "加企微/群，后续发单代查",
    "活动/优惠兴趣": "发活动明细，引导领券/油品",
    "平台回看/自助查询": "引导自助查询/平台回看",
    "配件需求场景": "承接冷门件询价",
    "微信加群": "加企微/群，后续发单代查",
    "优惠活动": "发活动明细，引导领券/油品",
    "冷门找件": "承接冷门件询价",
}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def quotes_html(quotes: list[str], limit: int = 2) -> str:
    items = [f"“{esc(q)}”" for q in quotes[:limit]]
    return " ".join(items)


def bar_row(label: str, value_text: str, pct: float, color: str) -> str:
    width = max(0.0, min(100.0, pct))
    return f"""
      <div class="bar-row">
        <div class="bar-head">
          <span class="bar-label">{esc(label)}</span>
          <span class="bar-value">{esc(value_text)}</span>
        </div>
        <div class="bar-track"><div class="bar-fill" style="width:{width:.1f}%;background:{color}"></div></div>
      </div>"""


def conic_donut(items: list[dict[str, Any]]) -> str:
    total = sum(i["count"] for i in items) or 1
    stops = []
    acc = 0.0
    for idx, item in enumerate(items):
        color = PALETTE[idx % len(PALETTE)]
        start = acc / total * 360
        acc += item["count"]
        end = acc / total * 360
        stops.append(f"{color} {start:.2f}deg {end:.2f}deg")
    gradient = ", ".join(stops)
    legend = "".join(
        f"""
        <div class="legend-row">
          <span class="dot" style="background:{PALETTE[idx % len(PALETTE)]}"></span>
          <span class="legend-name">{esc(item['name'])}</span>
          <span class="legend-count">{item['count']}</span>
          <span class="legend-rate">{item['rate']:.1f}%</span>
        </div>"""
        for idx, item in enumerate(items)
    )
    return f"""
      <div class="donut-wrap">
        <div class="donut" style="background:conic-gradient({gradient})"><div class="donut-hole"></div></div>
        <div class="legend">{legend}</div>
      </div>"""


def kpi_card(label: str, value: Any, unit: str, sub: str, accent: str, value_color: str) -> str:
    return f"""
      <div class="kpi">
        <div class="kpi-bar" style="background:{accent}"></div>
        <div class="kpi-label">{esc(label)}</div>
        <div class="kpi-value" style="color:{value_color}">{esc(value)}<span class="kpi-unit">{esc(unit)}</span></div>
        <div class="kpi-sub">{esc(sub)}</div>
      </div>"""


def voc_table(title: str, note: str, headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = ""
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        body += f"<tr>{cells}</tr>"
    note_html = f'<div class="card-note">{esc(note)}</div>' if note else ""
    return f"""
      <div class="voc-card">
        <div class="voc-title">{esc(title)}</div>
        <table class="voc-table">
          <thead><tr>{head}</tr></thead>
          <tbody>{body}</tbody>
        </table>
        {note_html}
      </div>"""


def build_html(report: dict[str, Any]) -> str:
    m = report["metrics"]
    meta = report["meta"]
    voc = report["voc"]
    report_label = meta.get("report_label") or "阶段日报"

    kpis = "".join([
        kpi_card("呼出总量", m["outbound"], "通", "占全部 100.0%", "#2369E8", "#0756D9"),
        kpi_card("接通总量", m["connected"], "通", f"接通率 {m['connect_rate']:.1f}%", "#1BBCEB", "#0756D9"),
        kpi_card("有效线索", m["valid"], "条", f"呼出到有效 {m['valid_per_outbound']:.1f}%", "#28B84A", "#1E9E3E"),
        kpi_card("接通后待定", m["pending_after_connected"], "条", f"占接通 {m['pending_per_connected']:.1f}%", "#FF8A1F", "#E07B12"),
        kpi_card("无效", m["invalid"], "条", f"占接通 {m['invalid_per_connected']:.1f}%", "#F0453E", "#D93025"),
        kpi_card("未接通", m["unconnected"], "通", f"占全部 {m['unconnected_rate']:.1f}%", "#9DB1C7", "#5B6B7E"),
    ])

    pending_invalid = m["pending_after_connected"] + m["invalid"]
    loss_before_connect = m["outbound"] - m["connected"]
    loss_before_connect_rate = (loss_before_connect / m["outbound"] * 100) if m["outbound"] else 0
    convert_after_connect = (m["valid"] / m["connected"] * 100) if m["connected"] else 0
    funnel = f"""
      <div class="funnel-viz">
        <div class="funnel-seg seg1">
          <div class="funnel-label">呼出</div>
          <div class="funnel-main">{m['outbound']}<span>通</span></div>
          <div class="funnel-rate">100.0%</div>
        </div>
        <div class="funnel-midline">未接通 {m['unconnected']}通 ▼ 接通率 {m['connect_rate']:.1f}%</div>
        <div class="funnel-seg seg2">
          <div class="funnel-label">接通</div>
          <div class="funnel-main">{m['connected']}<span>通</span></div>
          <div class="funnel-rate">{m['connect_rate']:.1f}%</div>
        </div>
        <div class="funnel-midline">待定+无效 {pending_invalid}通 ▼ 转化率 {convert_after_connect:.1f}%</div>
        <div class="funnel-seg seg3">
          <div class="funnel-label">有效线索</div>
          <div class="funnel-main">{m['valid']}<span>条</span></div>
          <div class="funnel-rate">呼出转化 {m['valid_per_outbound']:.1f}%</div>
        </div>
        <div class="funnel-loss">最大损耗在接通前（-{loss_before_connect_rate:.1f}%）</div>
        <div class="funnel-path">全链路：呼出 {m['outbound']} → 接通 {m['connected']} → 有效 {m['valid']}</div>
      </div>"""

    # Content quality stacked bar.
    cq = report["content_quality"]
    cq_total = m["connected"] or 1
    human_pct = cq["human_content"] / cq_total * 100
    nonhuman_pct = cq["non_human_or_message"] / cq_total * 100
    blank_pct = cq["blank_or_short"] / cq_total * 100
    quality = f"""
      <div class="quality-sub">接通 {m['connected']} 通中，真人有内容占 {cq['human_rate_connected']:.1f}%</div>
      <div class="quality-stack">
        <div class="quality-seg human" style="width:{human_pct:.1f}%">真人 {human_pct:.1f}%</div>
        <div class="quality-seg message" style="width:{nonhuman_pct:.1f}%">留言 {nonhuman_pct:.1f}%</div>
        <div class="quality-seg blank" style="width:{blank_pct:.1f}%">空白/秒挂 {blank_pct:.1f}%</div>
      </div>
      <div class="quality-legend">
        <span><i style="background:#16A085"></i>真人内容 {cq['human_content']}</span>
        <span><i style="background:#95A5A6"></i>留言/助理 {cq['non_human_or_message']}</span>
        <span><i style="background:#E74C3C"></i>空白/秒挂 {cq['blank_or_short']}</span>
      </div>"""

    # VOC tables.
    att_known = sum(x["count"] for x in voc.get("buyin", []))
    att_rows = [
        [esc(x["name"]), str(x["count"]), f"{x['rate']:.1f}%", quotes_html(voc.get("buyin_quotes", {}).get(x["name"], []))]
        for x in voc.get("buyin", [])[:5]
    ]
    att_table = voc_table(
        f"有效客户 Buy-in 点（明确 {att_known} 条）",
        f"另有 {voc.get('buyin_unknown', 0)} 条未知，不计入占比",
        ["Buy-in", "数量", "占比", "典型原声"],
        att_rows,
    )

    obj_known = sum(x["count"] for x in voc["objection"])
    obj_rows = [
        [esc(x["name"]), str(x["count"]), f"{x['rate']:.1f}%", quotes_html(voc["objection_quotes"].get(x["name"], []))]
        for x in voc["objection"][:5]
    ]
    obj_table = voc_table(
        f"待定/无效抗拒点（明确 {obj_known} 条）",
        f"分母 {voc['objection_base']} 条，另有 {voc['objection_unknown']} 条未知",
        ["抗拒点", "数量", "占比", "典型原声"],
        obj_rows,
    )

    buyin_rows = [
        [esc(x["name"]), str(x["count"]), f"{x['rate']:.1f}%", esc(BUYIN_ACTIONS.get(x["name"], "人工协助跟进"))]
        for x in voc.get("buyin", voc["effective_attention"])[:6]
    ]
    buyin_table = voc_table(
        f"有效客户 Buy-in 点（{m['valid']} 条）",
        "",
        ["Buy-in 点", "数量", "占比", "后续承接"],
        buyin_rows,
    )

    # VOC summary + insights.
    top_attention = "、".join(x["name"] for x in voc.get("buyin", [])[:2]) or "暂无明确 Buy-in"
    top_objection = "、".join(x["name"] for x in voc["objection"][:2]) or "暂无明确抗拒"
    summary_items = [
        ("有效客户看 Buy-in", f"明确 Buy-in 集中在{top_attention}"),
        ("待定/无效看抗拒点", f"明确抗拒集中在{top_objection}"),
        ("话术优化方向", "围绕加微信代查/报价单，以及不会用平台时有人协助展开"),
    ]
    summary = "".join(
        f"""
        <div class="sum-row">
          <span class="sum-bullet"></span>
          <div><div class="sum-title">{esc(t)}</div><div class="sum-body">{esc(b)}</div></div>
        </div>"""
        for t, b in summary_items
    )

    insights = [
        "有效线索全部来自接通样本",
        f"接通后待定占接通 {m['pending_per_connected']:.1f}%",
        "微信加群/代查是重要承接点",
        "平台不会用时，需提供代查服务",
        "加强首轮推进，减少短接通和空白通话",
    ]
    insight_html = "".join(f"<li>{esc(x)}</li>" for x in insights)

    # Good cases.
    cases = ""
    for idx, case in enumerate(report["cases"][:3], 1):
        cases += f"""
        <div class="case">
          <div class="case-head">
            <div class="case-no">CASE<br><b>{idx:02d}</b></div>
            <div class="case-title">{esc(case['title'])}</div>
          </div>
          <div class="case-meta">客户：{esc(case['customer'])} ｜ 时长 {esc(case['duration'])} 秒</div>
          <div class="case-meta sub">CallID：{esc(case.get('call_id', '-'))}</div>
          <div class="case-meta sub">手机号：{esc(case['phone'])}</div>
          <div class="case-tags">
            <span class="tag green">有效</span>
            <span class="tag blue">Buy-in：{esc(case.get('buyin', case.get('attention', '')))}</span>
            <span class="tag blue">承接：后续触达</span>
          </div>
          <div class="case-quote">{quotes_html(case['quotes'], 1)}</div>
        </div>"""

    css = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; }
    .page { width: 1920px; background: #F3F6FA; padding: 28px 32px 36px; color: #14213D; }
    .header { display:flex; justify-content:space-between; align-items:flex-end;
      background:#13293D; border-radius:22px; padding:24px 36px; color:#fff; }
    .header h1 { font-size:38px; line-height:1.2; }
    .header .meta { font-size:18px; color:#BFD1E3; margin-top:8px; }
    .header .right { text-align:right; font-size:18px; color:#BFD1E3; }
    .header .right b { display:block; color:#fff; font-size:20px; margin-top:4px; }

    .kpis { display:grid; grid-template-columns:repeat(6,1fr); gap:16px; margin-top:18px; }
    .kpi { position:relative; background:#fff; border:1px solid #DCE4ED; border-radius:16px;
      padding:18px 20px 16px 26px; overflow:hidden; }
    .kpi-bar { position:absolute; left:0; top:0; bottom:0; width:8px; }
    .kpi-label { font-size:18px; color:#607080; }
    .kpi-value { font-size:46px; font-weight:700; line-height:1.1; margin-top:4px; }
    .kpi-unit { font-size:18px; font-weight:500; color:#13234A; margin-left:4px; }
    .kpi-sub { font-size:16px; color:#7A8794; margin-top:8px; }

    .grid { display:grid; grid-template-columns: 1fr 1.7fr; gap:18px; margin-top:18px; align-items:start; }
    .col { display:flex; flex-direction:column; gap:18px; }
    .panel { background:#fff; border:1px solid #DCE4ED; border-radius:18px; padding:22px 24px; }
    .panel h2 { font-size:24px; color:#0357D8; margin-bottom:6px; }
    .panel .desc { font-size:16px; color:#637282; margin-bottom:14px; }

    .funnel-viz { display:flex; flex-direction:column; align-items:center; padding:6px 0 2px; }
    .funnel-seg { height:96px; color:#fff; display:flex; flex-direction:column; align-items:center;
      justify-content:center; clip-path:polygon(0 0,100% 0,82% 100%,18% 100%); }
    .funnel-seg.seg1 { width:92%; background:#2369E8; }
    .funnel-seg.seg2 { width:60%; background:#20B9DD; }
    .funnel-seg.seg3 { width:32%; background:#25C751; height:92px; }
    .funnel-label { font-size:17px; font-weight:700; }
    .funnel-main { font-size:32px; font-weight:800; line-height:1.1; }
    .funnel-main span { font-size:17px; margin-left:2px; font-weight:600; }
    .funnel-rate { font-size:15px; font-weight:600; opacity:.95; margin-top:2px; }
    .funnel-midline { color:#7A8794; font-size:14px; margin:6px 0; }
    .funnel-loss { color:#0F1E35; font-size:16px; font-weight:700; margin-top:12px; }
    .funnel-path { color:#607080; font-size:14px; margin-top:6px; }
    .tagline { margin-top:10px; background:#F7FBFF; border:1px solid #C9DCF8; border-radius:8px;
      padding:10px 14px; font-size:15px; color:#0F1E35; }

    .quality-sub { font-size:17px; color:#607080; margin-bottom:14px; }
    .quality-stack { display:flex; width:100%; height:36px; overflow:hidden; border-radius:10px;
      background:#ECF1F6; }
    .quality-seg { display:flex; align-items:center; justify-content:center; min-width:44px;
      color:#fff; font-size:15px; font-weight:700; white-space:nowrap; }
    .quality-seg.human { background:#16A085; }
    .quality-seg.message { background:#95A5A6; }
    .quality-seg.blank { background:#E74C3C; }
    .quality-legend { display:flex; justify-content:flex-end; gap:18px; margin-top:10px;
      color:#607080; font-size:14px; flex-wrap:wrap; }
    .quality-legend span { white-space:nowrap; }
    .quality-legend i { display:inline-block; width:9px; height:9px; border-radius:3px; margin-right:5px; }

    .donut-wrap { display:flex; align-items:center; gap:24px; }
    .donut { width:200px; height:200px; border-radius:50%; flex-shrink:0; position:relative; }
    .donut-hole { position:absolute; inset:26%; background:#fff; border-radius:50%; }
    .legend { flex:1; display:flex; flex-direction:column; gap:9px; }
    .legend-row { display:grid; grid-template-columns:16px 1fr 44px 60px; align-items:center; gap:8px; font-size:16px; }
    .dot { width:14px; height:14px; border-radius:4px; }
    .legend-name { color:#0F1E35; }
    .legend-count { text-align:right; font-weight:700; color:#0F1E35; }
    .legend-rate { text-align:right; color:#0F1E35; }

    .voc-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    .voc-card { background:#fff; border:1px solid #CDE0FA; border-radius:14px; padding:16px 18px; }
    .voc-full { grid-column: 1 / -1; }
    .voc-title { font-size:20px; font-weight:700; color:#0357D8; margin-bottom:10px; }
    .voc-table { width:100%; border-collapse:collapse; font-size:15px; table-layout:fixed; }
    .voc-table th { background:#ECF4FF; color:#0B3B8C; font-weight:700; text-align:left;
      padding:8px 10px; font-size:15px; }
    .voc-table th:nth-child(1), .voc-table td:nth-child(1) { width:18%; white-space:nowrap; }
    .voc-table th:nth-child(2), .voc-table td:nth-child(2) { width:12%; text-align:right; white-space:nowrap; }
    .voc-table th:nth-child(3), .voc-table td:nth-child(3) { width:12%; text-align:right; white-space:nowrap; }
    .voc-table th:nth-child(4), .voc-table td:nth-child(4) { width:58%; }
    .voc-table td { padding:8px 10px; border-bottom:1px solid #E7EEF8; color:#0F1E35; vertical-align:top;
      word-break:keep-all; overflow-wrap:normal; }
    .voc-table td:last-child { color:#1B54C7; word-break:normal; overflow-wrap:anywhere; line-height:1.45; }
    .voc-full .voc-table th:nth-child(1), .voc-full .voc-table td:nth-child(1) { width:24%; }
    .voc-full .voc-table th:nth-child(2), .voc-full .voc-table td:nth-child(2) { width:10%; }
    .voc-full .voc-table th:nth-child(3), .voc-full .voc-table td:nth-child(3) { width:10%; }
    .voc-full .voc-table th:nth-child(4), .voc-full .voc-table td:nth-child(4) { width:56%; white-space:nowrap; color:#0F1E35; }
    .card-note { margin-top:10px; background:#F7FBFF; border:1px solid #C9DCF8; border-radius:7px;
      padding:7px 10px; font-size:14px; color:#506070; }

    .side { display:flex; flex-direction:column; gap:18px; }
    .sum-card { background:#F8FBFF; border:1px solid #DCE9FA; border-radius:16px; padding:18px 20px; }
    .sum-card h3 { font-size:22px; color:#0357D8; margin-bottom:12px; }
    .sum-row { display:flex; gap:12px; margin-bottom:14px; }
    .sum-bullet { width:12px; height:12px; border-radius:50%; background:#2E70E8; margin-top:6px; flex-shrink:0; }
    .sum-title { font-size:18px; font-weight:700; color:#0357D8; }
    .sum-body { font-size:15px; color:#0F1E35; margin-top:3px; line-height:1.4; }
    .insight-card { background:#FFF9EA; border:1px solid #F2D8A8; border-radius:16px; padding:18px 20px; }
    .insight-card h3 { font-size:22px; color:#E48700; margin-bottom:12px; }
    .insight-card ul { list-style:none; }
    .insight-card li { position:relative; padding-left:20px; font-size:16px; color:#0F1E35; margin:9px 0; line-height:1.4; }
    .insight-card li::before { content:"•"; position:absolute; left:0; color:#1F64E0; font-weight:700; }

    .cases-panel { margin-top:18px; }
    .cases { display:grid; grid-template-columns:repeat(3,1fr); gap:18px; }
    .case { background:#fff; border:1px solid #CDE0FA; border-radius:14px; padding:16px 18px; }
    .case-head { display:flex; gap:14px; align-items:flex-start; }
    .case-no { background:#1F64E0; color:#fff; border-radius:9px; padding:8px 0; width:60px; text-align:center;
      font-size:14px; line-height:1.2; flex-shrink:0; }
    .case-no b { font-size:26px; }
    .case-title { font-size:20px; font-weight:700; color:#0357D8; line-height:1.3; }
    .case-meta { font-size:14px; color:#0F1E35; margin-top:10px; }
    .case-meta.sub { color:#506070; margin-top:4px; overflow-wrap:anywhere; word-break:break-word; }
    .case-tags { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
    .tag { font-size:14px; border-radius:7px; padding:4px 10px; }
    .tag.green { background:#DFF8E7; color:#178B3B; font-weight:700; }
    .tag.blue { background:#EDF4FF; color:#0357D8; }
    .case-quote { margin-top:12px; background:#F1F6FF; border-radius:8px; padding:10px 12px;
      font-size:15px; color:#1B54C7; line-height:1.4; }

    .footer { margin-top:18px; background:#13293D; border-radius:16px; padding:14px 22px;
      color:#fff; font-size:16px; }
    """

    body = f"""
    <div class="page">
      <div class="header">
        <div>
          <h1>{esc(meta['title'])} · {esc(report_label)}</h1>
          <div class="meta">统计日期：{esc(meta['date'])}（截止约 {esc(meta['cutoff'])}）｜数据来源：{esc(meta['source_file'])}｜样本 {m['outbound']} 条</div>
        </div>
        <div class="right">外呼复盘<b>客户汇报版</b></div>
      </div>

      <div class="kpis">{kpis}</div>

      <div class="grid">
        <div class="col">
          <div class="panel">
            <h2>漏斗转化</h2>
            <div class="desc">最大瓶颈在接通前；接通后主要卡在待定与沟通轮次不足。</div>
            {funnel}
            <div class="tagline">说明：有效 = 已接通且真人有内容的有效线索，呼出到有效 {m['valid_per_outbound']:.1f}%。</div>
          </div>
          <div class="panel">
            <h2>未接通原因归类（{m['unconnected']} 通）</h2>
            {conic_donut(report['unconnected_breakdown'])}
            <div class="tagline">备注：语音留言 / 暂时无法拨通不计入接通后待定。</div>
          </div>
          <div class="panel">
            <h2>接通内容质量</h2>
            {quality}
          </div>
        </div>

        <div class="col">
          <div class="panel">
            <h2>VOC 分析（有效看关注，待定/无效看抗拒）</h2>
            <div class="desc">{report['content_quality']['human_content']} 条真人有内容为主分母；未知不计入明确占比。</div>
            <div class="voc-grid">
              {att_table}
              {obj_table}
              <div class="voc-full">{buyin_table}</div>
            </div>
          </div>
          <div class="side" style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">
            <div class="sum-card">
              <h3>→ VOC 总结</h3>
              {summary}
            </div>
            <div class="insight-card">
              <h3>★ 重点洞察</h3>
              <ul>{insight_html}</ul>
            </div>
          </div>
        </div>
      </div>

      <div class="panel cases-panel">
        <h2>机器人能力 Good Case（有效案例精选）</h2>
        <div class="cases">{cases}</div>
      </div>

      <div class="footer">注：本报告基于 {esc(meta['date'])} 截止 {esc(meta['cutoff'])} 的数据样本，仅供阶段性参考。</div>
    </div>
    """

    return f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>"""


def render_png(report: dict[str, Any], png_path: Path, html_path: Path | None = None) -> None:
    from playwright.sync_api import sync_playwright

    doc = build_html(report)
    if html_path is not None:
        html_path.write_text(doc, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
        page.set_content(doc, wait_until="networkidle")
        element = page.query_selector(".page")
        element.screenshot(path=str(png_path))
        browser.close()


if __name__ == "__main__":
    import sys

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("onepage.png")
    render_png(data, out, out.with_suffix(".html"))
    print(out)
