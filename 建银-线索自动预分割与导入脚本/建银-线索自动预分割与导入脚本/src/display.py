"""
CLI 显示模块 — 三阶段：扫描预览(console) → 处理(Live) → 完成(console)
"""
import asyncio
import sys
from datetime import datetime
from typing import Dict, List, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .tenant_processor import TenantStatus


class DisplayState:
    def __init__(self):
        self.phase = "init"
        self.message = ""
        self.sub_message = ""
        self.env = ""
        self.base_url = ""
        self.statuses: Dict[str, TenantStatus] = {}
        self.tenant_files_info: Dict[str, List[str]] = {}
        self.preview_info: Optional[dict] = None
        self.confirm_history: List[dict] = []
        self.pending_commands: List[str] = []
        self.terminate_requested: Dict[str, bool] = {}


def build_scan_panel(state: DisplayState) -> Panel:
    lines = [state.message]
    if state.sub_message:
        lines.append(state.sub_message)
    if state.tenant_files_info:
        lines.append("")
        for name, batches in state.tenant_files_info.items():
            if batches:
                lines.append(f"  [bold]{name}[/bold]  {len(batches)} 批次: {', '.join(batches)}")
    return Panel(
        "\n".join(lines),
        title=f"[bold blue]线索全自动导入 — {state.env} ({state.base_url})[/bold blue]",
        border_style="blue",
    )


def build_preview_panel(state: DisplayState) -> Panel:
    pd = state.preview_info
    if not pd:
        return Panel("无预览数据", title="预览")

    file_table = Table(box=box.SIMPLE_HEAVY, show_lines=True, width=None)
    file_table.add_column("#", style="dim", width=4)
    for h in pd["headers"]:
        label = h[:16] + "…" if len(h) > 16 else h
        file_table.add_column(label, overflow="fold", max_width=20)

    for idx, row in enumerate(pd["first_rows"], 1):
        file_table.add_row(
            str(idx),
            *[str(c)[:40] if c is not None else "" for c in row]
        )

    total = pd["total"]
    if total > len(pd["first_rows"]) + len(pd["last_rows"]):
        file_table.add_row("", *["..."] * len(pd["headers"]), style="dim italic")

    if pd["first_rows"] != pd["last_rows"]:
        start = total - len(pd["last_rows"]) + 1
        for offset, row in enumerate(pd["last_rows"]):
            file_table.add_row(
                str(start + offset),
                *[str(c)[:40] if c is not None else "" for c in row]
            )

    renderables = [file_table]
    duplicate_check = pd.get("duplicate_check")
    if duplicate_check:
        # 预检查结果直接挂在预览表下面，红字代表命中重复导入风险。
        styles = {
            "duplicate": "bold red",
            "warning": "yellow",
            "error": "yellow",
            "ok": "green",
        }
        messages = duplicate_check.get("messages")
        if not messages and duplicate_check.get("message"):
            messages = [{
                "status": duplicate_check.get("status"),
                "text": duplicate_check.get("message"),
            }]
        for idx, message in enumerate(messages or []):
            style = styles.get(message.get("status"), "dim")
            prefix = "\n" if idx == 0 else ""
            renderables.append(Text(prefix + message.get("text", ""), style=style))

    return Panel(
        Group(*renderables),
        title=f"[bold yellow]数据预览 — {pd['tenant']} / {pd['batch']}[/bold yellow]",
        subtitle=f"[dim]文件: {pd['file_name']}  |  线索数: {total} 条[/dim]",
        border_style="yellow",
    )


def build_confirm_history_text(state: DisplayState) -> str:
    if not state.confirm_history:
        return ""
    lines = ["[bold]──── 确认记录 ────[/bold]"]
    for entry in state.confirm_history:
        icon = "[green]✓[/green]" if entry["result"] == "y" else "[red]✗[/red]"
        label = "已确认" if entry["result"] == "y" else "已跳过"
        lines.append(f"  {icon}  {entry['tenant']} / {entry['batch']:12s}  {label}")
    return "\n".join(lines)


def build_status_panel(state: DisplayState) -> Panel:
    table = Table(title=f"线索全自动导入 — 环境: {state.env} ({state.base_url})")
    table.add_column("#", style="dim", width=3)
    table.add_column("租户", style="cyan", width=11)
    table.add_column("状态", style="yellow", width=9)
    table.add_column("当前批次", style="green", width=14)
    table.add_column("线索(窗口)", width=10)
    table.add_column("进度", width=6)
    table.add_column("外呼任务", style="magenta", width=14)
    table.add_column("任务状态", width=8)
    table.add_column("等待队列", style="dim", width=16)
    table.add_column("信息", style="dim", width=20)
    table.add_column("操作", width=12)

    active_idx = 0
    for name, st in state.statuses.items():
        d = st.to_dict()
        inactive_states = (
            "初始化", "无批次", "已终止", "配置缺失", "登录失败",
            "无文件", "全部完成", "处理完成", "已跳过",
        )
        is_active = d["state"] not in inactive_states
        is_terminated = d["state"] == "已终止"

        if is_active:
            active_idx += 1
            idx_str = f"[bold]{active_idx}[/bold]"
            op = f"[bold red]{active_idx}[/bold red][red]终止[/red]"
        elif is_terminated:
            idx_str = "-"
            op = "[bold white on red] 已终止 [/bold white on red]"
        else:
            idx_str = "-"
            op = "[dim]-[/dim]"

        table.add_row(
            idx_str,
            d["tenant"][:11], d["state"][:9], d["batch"][:14],
            d["leads"][:10], d["progress"][:6],
            d["task"][:14], d["task_state"][:8],
            d.get("queue", "-")[:16],
            d.get("msg", "-")[:20],
            op,
        )

    now = datetime.now().strftime("%H:%M:%S")
    return Panel(table, subtitle=f"刷新: {now}  |  按编号+回车终止对应租户")


def build_done_panel(state: DisplayState) -> Panel:
    table = Table(
        box=box.SIMPLE,
        expand=True,
        show_edge=False,
        pad_edge=False,
    )
    table.add_column("租户", width=15, no_wrap=True)
    table.add_column("状态", width=15, no_wrap=True)
    table.add_column("进度", width=20, no_wrap=True)
    table.add_column("信息", overflow="fold")

    for name, st in state.statuses.items():
        progress = f"{st.completed_batches}/{st.total_batches}"
        table.add_row(
            f"[bold]{st.tenant_name}[/bold]",
            st.state,
            progress,
            st.message,
        )
        for result in st.batch_results:
            icon = "[green]✓[/green]" if result["ok"] else "[red]✗[/red]"
            table.add_row(
                f"  {icon} {result['batch']}",
                "[dim]批次结果[/dim]",
                "",
                result["message"],
            )

    return Panel(
        Group(Text(state.message, style="bold green"), Text(""), table),
        title="[bold green]处理完成[/bold green]",
        border_style="green",
    )


def process_commands(state: DisplayState):
    while state.pending_commands:
        cmd = state.pending_commands.pop(0).strip()
        try:
            idx = int(cmd) - 1
            inactive_states = (
                "初始化", "无批次", "已终止", "配置缺失", "登录失败",
                "无文件", "全部完成", "处理完成", "已跳过",
            )
            active_names = [
                name for name, st in state.statuses.items()
                if st.state not in inactive_states
            ]
            if 0 <= idx < len(active_names):
                tenant_name = active_names[idx]
                if not state.terminate_requested.get(tenant_name):
                    state.terminate_requested[tenant_name] = True
                    state.statuses[tenant_name].request_terminate()
        except ValueError:
            pass


def _read_stdin_line(timeout: float = 0.5) -> str:
    import select
    if select.select([sys.stdin], [], [], timeout)[0]:
        return sys.stdin.readline()
    return ""


async def command_reader(state: DisplayState, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            cmd = await asyncio.to_thread(_read_stdin_line, 0.5)
            cmd = cmd.strip()
            if cmd:
                state.pending_commands.append(cmd)
        except (EOFError, ValueError):
            break
        except Exception:
            break


async def live_status_loop(
    state: DisplayState,
    stop_event: asyncio.Event,
    interval: float = 0.8,
):
    is_tty = sys.stdout.isatty()
    console = Console()
    with Live(
        console=console,
        screen=is_tty,
        refresh_per_second=2 if is_tty else 1,
        transient=False,
    ) as live:
        while not stop_event.is_set():
            process_commands(state)
            live.update(build_status_panel(state))
            await asyncio.sleep(interval)
