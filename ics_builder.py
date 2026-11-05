"""RFC 5545 (iCalendar) 序列化，针对 iOS 订阅（webcal）做兼容处理。

要点：
* 严格 CRLF 行尾，75 字节折行且不切断 UTF-8 多字节字符；
* 全天事件用 DTSTART;VALUE=DATE / DTEND;VALUE=DATE（结束日为次日）；
* UID 基于日期生成，重复拉取不会产生重复日程；
* X-PUBLISHED-TTL / REFRESH-INTERVAL 提示客户端刷新间隔。
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Iterable

from festivals import Event

PRODID = "-//cn-festivals//CN Festivals & Holidays//ZH-CN"
CALENDAR_NAME = "中国传统节日 · 法定假期"
CALENDAR_DESC = (
    "中国传统节日、二十四节气，以及法定节假日放假天数与调休上班安排。"
    "农历节日按天文算法逐年推算，假期安排来自国务院办公厅公布数据。"
)


def _escape_text(value: str) -> str:
    out = (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )
    return out


def _fold(line: str, limit: int = 75) -> list[str]:
    """按 UTF-8 字节数折行，续行以单个空格开头。"""
    if len(line.encode("utf-8")) <= limit:
        return [line]
    chunks: list[bytes] = []
    current = bytearray()
    caps = limit
    for ch in line:
        b = ch.encode("utf-8")
        if len(current) + len(b) > caps:
            chunks.append(bytes(current))
            current = bytearray()
            caps = limit - 1          # 续行需预留 1 字节给前导空格
        current.extend(b)
    if current:
        chunks.append(bytes(current))
    result = [chunks[0].decode("utf-8")]
    result += [" " + c.decode("utf-8") for c in chunks[1:]]
    return result


def _fmt_date(d: date) -> str:
    return f"{d:%Y%m%d}"


def _fmt_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _event_lines(event: Event, stamp: datetime) -> list[str]:
    uid = event.uid
    if len(uid) > 240:  # 极少数超长 UID：改用摘要
        uid = hashlib.sha1(uid.encode("utf-8")).hexdigest() + "@cn-festivals"

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_fmt_utc(stamp)}",
        f"DTSTART;VALUE=DATE:{_fmt_date(event.start)}",
        f"DTEND;VALUE=DATE:{_fmt_date(event.end)}",
        f"SUMMARY:{_escape_text(event.summary)}",
        f"DESCRIPTION:{_escape_text(event.description)}",
        f"CATEGORIES:{_escape_text(event.category)}",
        "TRANSP:OPAQUE" if event.category == "调休上班" else "TRANSP:TRANSPARENT",
        "STATUS:CONFIRMED",
        "SEQUENCE:0",
    ]
    if event.alarm_minutes is not None:
        minutes = event.alarm_minutes
        sign = "-" if minutes < 0 else ""
        hours, mins = divmod(abs(minutes), 60)
        trigger = f"{sign}PT{hours}H" + (f"{mins}M" if mins else "")
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape_text(event.summary)}",
            f"TRIGGER:{trigger}",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def render(events: Iterable[Event], meta: dict, now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_text(CALENDAR_NAME)}",
        f"X-WR-CALDESC:{_escape_text(CALENDAR_DESC)}",
        "X-WR-TIMEZONE:Asia/Shanghai",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
        f"X-WR-RELCALID:cn-festivals-{meta.get('start_year')}-{meta.get('end_year')}@cn-festivals",
    ]
    for event in events:
        lines.extend(_event_lines(event, stamp))
    lines.append("END:VCALENDAR")

    folded: list[str] = []
    for line in lines:
        folded.extend(_fold(line))
    return "\r\n".join(folded) + "\r\n"


def write_ics(path, events, meta: dict, now: datetime | None = None) -> int:
    content = render(events, meta, now)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    return len(content.encode("utf-8"))
