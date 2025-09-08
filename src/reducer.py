from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from telegram.helpers import escape_markdown

from .influx import NodePoint


logger = logging.getLogger(__name__)


@dataclass
class NodeStatus:
    name: str
    up: bool
    degraded: bool
    latency_ms: Optional[int]
    reason: Optional[str]  # e.g., "no recent heartbeat"
    protocol: Optional[str]


def reduce_status(
    data: Dict[str, NodePoint], *, minutes: int, latency_warn_ms: Optional[int]
) -> Dict[str, NodeStatus]:
    """
    Reduce per name according to spec:
    - alive = most recent alive value within the window
    - latency = most recent delay_ms within the window
    - If no data in window => DOWN (unknown/dead)
    - DEGRADED if up and latency > threshold
    """
    out: Dict[str, NodeStatus] = {}
    for name, node in data.items():
        alive = node.alive
        # Consider data present if either alive or latency seen in window
        has_any = (node.alive_time is not None) or (node.latency_time is not None)
        if not has_any:
            out[name] = NodeStatus(
                name=name,
                up=False,
                degraded=False,
                latency_ms=None,
                reason="no recent heartbeat",
                protocol=node.protocol,
            )
            continue

        if alive is True:
            degraded = False
            if latency_warn_ms is not None:
                if node.latency_ms is not None and node.latency_ms > latency_warn_ms:
                    degraded = True
            out[name] = NodeStatus(
                name=name,
                up=True,
                degraded=degraded,
                latency_ms=node.latency_ms,
                reason=None,
                protocol=node.protocol,
            )
        else:
            # alive False or missing alive -> DOWN
            reason = "no recent heartbeat" if alive is None else None
            out[name] = NodeStatus(
                name=name,
                up=False,
                degraded=False,
                latency_ms=None,
                reason=reason,
                protocol=node.protocol,
            )

    return out


def format_markdown_v2(
    title: str,
    statuses: Dict[str, NodeStatus],
    *,
    minutes: int,
    show_protocol: bool,
    now: Optional[datetime] = None,
) -> str:
    """Create a compact, stable-ordered MarkdownV2 message."""
    now = now or datetime.now(timezone.utc)
    # Group: UP (not degraded), DEGRADED, DOWN; alpha by name within each
    ups: List[NodeStatus] = []
    degs: List[NodeStatus] = []
    downs: List[NodeStatus] = []
    for s in statuses.values():
        if s.up and not s.degraded:
            ups.append(s)
        elif s.up and s.degraded:
            degs.append(s)
        else:
            downs.append(s)

    def key(ns: NodeStatus) -> str:
        return ns.name.lower()

    ups.sort(key=key)
    degs.sort(key=key)
    downs.sort(key=key)

    lines: List[str] = []
    safe_title = escape_markdown(f"{title} (last {minutes}m)", version=2)
    lines.append(f"*{safe_title}*")
    lines.append("")

    def fmt(ns: NodeStatus) -> str:
        if ns.up:
            if ns.degraded:
                emoji = "⚠️"
            else:
                emoji = "✅"
        else:
            emoji = "❌"

        name = escape_markdown(ns.name, version=2)
        tail: str
        # Wrap protocol in escaped parentheses for MarkdownV2 safety
        proto = (
            f" \\({escape_markdown(ns.protocol, version=2)}\\)" if (show_protocol and ns.protocol) else ""
        )
        if ns.up:
            if ns.latency_ms is not None:
                tail = f" — {ns.latency_ms} ms"
            else:
                tail = ""
        else:
            if ns.reason:
                # Build raw; escape once at final join
                tail = f" — {ns.reason}"
            else:
                tail = ""

        return f"{emoji} {name}{proto}{escape_markdown(tail, version=2)}"

    for group in (ups, degs, downs):
        for item in group:
            lines.append(fmt(item))

    lines.append("")
    # _Updated: 2025-...Z_
    ts = now.strftime("%Y-%m-%d %H:%M:%SZ")
    upd = escape_markdown(f"Updated: {ts}", version=2)
    lines.append(f"_{upd}_")

    return "\n".join(lines)


def payload_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _format_cn_datetime(now: datetime) -> str:
    """Return Chinese-style datetime like 2025/9/2 上午12:59:05 (local-time-like in UTC)."""
    # Use UTC provided in callers; adapt to 12h with CN markers.
    y = now.year
    m = now.month
    d = now.day
    hour24 = now.hour
    minute = now.minute
    second = now.second
    am = hour24 < 12
    # 12-hour clock: 0 -> 12 AM, 13 -> 1 PM
    hour12 = hour24 % 12
    if hour12 == 0:
        hour12 = 12
    meridian = "上午" if am else "下午"
    return f"{y}/{m}/{d} {meridian}{hour12:02d}:{minute:02d}:{second:02d}"


def format_board_zh(
    *,
    now: datetime,
    domestic_alerts: list[str],
    foreign_alerts: list[str],
) -> str:
    """Chinese board layout in MarkdownV2 with escaping.

    Example:
    监视公告牌
    更新日期：2025/9/2 上午12:59:05

    国内当前报警节点如下：
    ❌ Azure-SG
    ...

    国外当前报警节点如下：
    无
    如何解读：只要国内国外其中有一个报警即为节点不可用
    """
    lines: list[str] = []
    title = escape_markdown("监视公告牌", version=2)
    lines.append(title)
    cn_dt = _format_cn_datetime(now)
    lines.append(escape_markdown(f"更新日期：{cn_dt}", version=2))

    # Domestic section
    lines.append("")
    lines.append(escape_markdown("国内当前报警节点如下：", version=2))
    if domestic_alerts:
        for n in sorted(domestic_alerts, key=lambda s: s.lower()):
            name = escape_markdown(n, version=2)
            lines.append(f"❌ {name}")
    else:
        lines.append(escape_markdown("无", version=2))

    # Foreign section
    lines.append("")
    lines.append(escape_markdown("国外当前报警节点如下：", version=2))
    if foreign_alerts:
        for n in sorted(foreign_alerts, key=lambda s: s.lower()):
            name = escape_markdown(n, version=2)
            lines.append(f"❌ {name}")
    else:
        lines.append(escape_markdown("无", version=2))

    # Interpretation note
    lines.append(escape_markdown("如何解读：只要国内国外其中有一个报警即为节点不可用", version=2))

    return "\n".join(lines)
