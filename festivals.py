"""中国传统节日 + 法定节假日 / 调休安排 的事件模型。

节日分两类：
1. 农历节日：由 lunar.py 实时推算，任意年份都准确，无需维护数据表；
2. 节气节日：清明、冬至、寒食，按太阳黄经推算；
3. 法定假期与调休：来自 data/holidays.json（国务院办公厅公布的实际安排）。
   未收录的年份按《全国年节及纪念日放假办法》的法定天数兜底，绝不臆造调休日。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import lunar

DATA_FILE = Path(__file__).resolve().parent / "data" / "holidays.json"
WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

CATEGORY_TRADITIONAL = "传统节日"
CATEGORY_SOLAR_TERM = "节气"
CATEGORY_HOLIDAY = "法定假期"
CATEGORY_WORKDAY = "调休上班"


@dataclass
class Event:
    uid: str
    start: date
    end: date                      # 不含（全天事件）
    summary: str
    description: str
    category: str
    alarm_minutes: int | None = None
    sort_key: tuple = field(default=())

    def __post_init__(self) -> None:
        if not self.sort_key:
            self.sort_key = (self.start, self.end, self.summary)

    @property
    def days(self) -> int:
        return (self.end - self.start).days


# --------------------------------------------------------------------------
# 节日定义
# --------------------------------------------------------------------------
# (名称, 农历月, 农历日, 说明)
LUNAR_FESTIVALS: list[tuple[str, int, int, str]] = [
    ("腊八节", 12, 8, "腊月初八，喝腊八粥、腌腊八蒜，年味自此渐浓。"),
    ("小年·北方", 12, 23, "腊月廿三，祭灶、扫尘。北方大部分地区以腊月廿三为小年。"),
    ("小年·南方", 12, 24, "腊月廿四，南方大部分地区以腊月廿四为小年。"),
    ("春节", 1, 1, "农历正月初一，中国最重要的传统节日。除旧布新、祭祖守岁、走亲访友。"),
    ("元宵节", 1, 15, "正月十五，赏花灯、猜灯谜、吃元宵，是春节年俗的收尾。"),
    ("龙抬头", 2, 2, "二月初二，又称春耕节、青龙节，民间有理发“剃龙头”、吃“龙食”的习俗。"),
    ("上巳节", 3, 3, "三月初三，古时水边祓禊、踏青游春；今广西壮族“三月三”歌圩。"),
    ("端午节", 5, 5, "五月初五，纪念屈原，赛龙舟、吃粽子、挂艾草、佩香囊。"),
    ("七夕节", 7, 7, "七月初七，牛郎织女鹊桥相会，又称乞巧节、女儿节。"),
    ("中元节", 7, 15, "七月十五，又称鬼节、盂兰盆节，民间祭祖荐新。"),
    ("中秋节", 8, 15, "八月十五，赏月、吃月饼、家人团聚，象征团圆。"),
    ("重阳节", 9, 9, "九月初九，登高、赏菊、插茱萸、敬老，又称老年节。"),
    ("寒衣节", 10, 1, "十月初一，又称十月朝，民间送寒衣、祭先祖。"),
]

# 高考式“节气型”节日：(名称, 黄经, 说明)
SOLAR_FESTIVALS: list[tuple[str, float, str]] = [
    ("清明节", 15.0, "既是二十四节气之一，也是最重要的祭祀节日，扫墓祭祖、踏青郊游。"),
    ("冬至", 270.0, "二十四节气之一，北半球白昼最短。北方吃饺子，南方吃汤圆，民间有“冬至大如年”之说。"),
]


def _fmt_date(d: date) -> str:
    return f"{d.month} 月 {d.day} 日（{WEEKDAYS[d.weekday()]}）"


def _fmt_range(start: date, end_inclusive: date) -> str:
    if start == end_inclusive:
        return _fmt_date(start)
    return f"{_fmt_date(start)}至{_fmt_date(end_inclusive)}"


def _lines(*items: str) -> str:
    return "\n".join(i for i in items if i)


def _slug(name: str) -> str:
    """稳定的节假日起见：用于 UID，避免同名日期（如中秋与国庆同日）冲突。"""
    return hashlib.md5(name.encode("utf-8")).hexdigest()[:8]


# --------------------------------------------------------------------------
# 1) 农历传统节日
# --------------------------------------------------------------------------
def lunar_festival_events(start_year: int, end_year: int) -> list[Event]:
    events: list[Event] = []
    lo, hi = date(start_year, 1, 1), date(end_year, 12, 31)
    for ly in range(start_year - 1, end_year + 1):
        # 除夕：腊月最后一天
        eve = lunar.lunar_new_year_eve(ly)
        if lo <= eve <= hi:
            last_day = lunar.lunar_month_days(ly, 12)
            events.append(Event(
                uid=f"festival-{eve:%Y%m%d}-chuxi@cn-festivals",
                start=eve,
                end=eve + timedelta(days=1),
                summary=f"除夕 · {lunar.lunar_month_name(12)}{lunar.lunar_day_name(last_day)}",
                description=_lines(
                    "一年最后一天，贴春联、吃年夜饭、守岁迎新。",
                    f"次日为{lunar.chinese_new_year(ly + 1).year} 年春节"
                    if lunar.chinese_new_year(ly + 1).year == eve.year + 1 else "",
                ),
                category=CATEGORY_TRADITIONAL,
                alarm_minutes=8 * 60,
            ))

        for name, month, day, desc in LUNAR_FESTIVALS:
            try:
                d = lunar.lunar_to_solar(ly, month, day)
            except ValueError:
                continue
            if not (lo <= d <= hi):
                continue
            events.append(Event(
                uid=f"festival-{d:%Y%m%d}-{ly}-{month}-{day}@cn-festivals",
                start=d,
                end=d + timedelta(days=1),
                summary=f"{name} · {lunar.lunar_month_name(month)}{lunar.lunar_day_name(day)}",
                description=desc,
                category=CATEGORY_TRADITIONAL,
                alarm_minutes=8 * 60,
            ))
    return events


# --------------------------------------------------------------------------
# 2) 节气型节日
# --------------------------------------------------------------------------
def solar_festival_events(start_year: int, end_year: int) -> list[Event]:
    events: list[Event] = []
    for year in range(start_year, end_year + 1):
        for name, angle, desc in SOLAR_FESTIVALS:
            d = lunar.solar_term_date(year, angle)
            events.append(Event(
                uid=f"festival-{d:%Y%m%d}-{int(angle)}@cn-festivals",
                start=d,
                end=d + timedelta(days=1),
                summary=name,
                description=desc,
                category=CATEGORY_SOLAR_TERM,
                alarm_minutes=8 * 60,
            ))
        qm = lunar.qingming(year)
        hanshi = qm - timedelta(days=1)
        events.append(Event(
            uid=f"festival-{hanshi:%Y%m%d}-hanshi@cn-festivals",
            start=hanshi,
            end=hanshi + timedelta(days=1),
            summary="寒食节",
            description="清明前一日，古时禁烟火、吃冷食，后与清明节俗融合。",
            category=CATEGORY_SOLAR_TERM,
            alarm_minutes=8 * 60,
        ))
    return events


# --------------------------------------------------------------------------
# 3) 法定假期 / 调休
# --------------------------------------------------------------------------
def load_holiday_data(path: Path = DATA_FILE) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _statutory_fallback(year: int) -> list[dict]:
    """未收录年度：按《全国年节及纪念日放假办法》法定天数生成，不臆造调休。"""
    cny = lunar.chinese_new_year(year)
    eve = cny - timedelta(days=1)          # 该年春节前一天，即当年除夕
    return [
        {"name": "元旦", "start": date(year, 1, 1), "end": date(year, 1, 1),
         "statutory_days": 1, "note": "法定节假日 1 天"},
        {"name": "春节", "start": eve, "end": cny + timedelta(days=2),
         "statutory_days": 4, "note": "法定节假日 4 天（除夕、正月初一至初三）"},
        {"name": "清明节", "start": lunar.qingming(year), "end": lunar.qingming(year),
         "statutory_days": 1, "note": "法定节假日 1 天"},
        {"name": "劳动节", "start": date(year, 5, 1), "end": date(year, 5, 2),
         "statutory_days": 2, "note": "法定节假日 2 天"},
        {"name": "端午节", "start": lunar.lunar_to_solar(year, 5, 5),
         "end": lunar.lunar_to_solar(year, 5, 5), "statutory_days": 1,
         "note": "法定节假日 1 天"},
        {"name": "中秋节", "start": lunar.lunar_to_solar(year, 8, 15),
         "end": lunar.lunar_to_solar(year, 8, 15), "statutory_days": 1,
         "note": "法定节假日 1 天"},
        {"name": "国庆节", "start": date(year, 10, 1), "end": date(year, 10, 3),
         "statutory_days": 3, "note": "法定节假日 3 天"},
    ]


def holiday_events(start_year: int, end_year: int, data: dict) -> tuple[list[Event], list[int], list[int]]:
    official = {int(y["year"]): y for y in data.get("years", [])}
    events: list[Event] = []
    covered: list[int] = []
    fallback: list[int] = []

    for year in range(start_year, end_year + 1):
        rec = official.get(year)
        if rec:
            covered.append(year)
            notice = rec.get("notice", "")
            workdays = rec.get("workdays", [])
            for p in rec["periods"]:
                s = date.fromisoformat(p["start"])
                e = date.fromisoformat(p["end"])
                total = (e - s).days + 1
                related = sorted(
                    date.fromisoformat(wd["date"])
                    for wd in workdays
                    if wd.get("for") and (wd["for"] == p["name"] or wd["for"] in p["name"])
                )
                makeup = "、".join(
                    f"{d.month} 月 {d.day} 日（{WEEKDAYS[d.weekday()]}）" for d in related
                )
                events.append(Event(
                    uid=f"holiday-{s:%Y%m%d}-{year}-{_slug(p['name'])}@cn-festivals",
                    start=s,
                    end=e + timedelta(days=1),
                    summary=f"{p['name']}假期 · 共 {total} 天",
                    description=_lines(
                        f"放假：{_fmt_range(s, e)}，共 {total} 天",
                        f"其中法定节假日 {p['statutory_days']} 天",
                        f"调休上班：{makeup}" if makeup else "",
                        p.get("note", ""),
                        f"依据：{notice}" if notice else "",
                    ),
                    category=CATEGORY_HOLIDAY,
                    alarm_minutes=-4 * 60,
                ))
            for wd in workdays:
                d = date.fromisoformat(wd["date"])
                events.append(Event(
                    uid=f"workday-{d:%Y%m%d}@cn-festivals",
                    start=d,
                    end=d + timedelta(days=1),
                    summary=f"调休上班（{WEEKDAYS[d.weekday()]}）",
                    description=_lines(
                        f"{_fmt_date(d)}因{wd.get('for', '节假日')}调休，需正常上班。",
                        f"依据：{notice}" if notice else "",
                    ),
                    category=CATEGORY_WORKDAY,
                    alarm_minutes=-4 * 60,
                ))
        else:
            fallback.append(year)
            for p in _statutory_fallback(year):
                s, e = p["start"], p["end"]
                total = (e - s).days + 1
                events.append(Event(
                    uid=f"holiday-{s:%Y%m%d}-{year}-{_slug(p['name'])}-statutory@cn-festivals",
                    start=s,
                    end=e + timedelta(days=1),
                    summary=f"{p['name']} · 法定假日 {total} 天",
                    description=_lines(
                        f"法定节假日：{_fmt_range(s, e)}，共 {total} 天",
                        p["note"],
                        "国务院办公厅尚未公布该年度调休安排，此处仅列出法定天数；"
                        "正式安排公布后更新数据源即可自动同步。",
                    ),
                    category=CATEGORY_HOLIDAY,
                    alarm_minutes=-4 * 60,
                ))
    return events, covered, fallback


def build_events(start_year: int, end_year: int, data: dict | None = None) -> tuple[list[Event], dict]:
    data = data or load_holiday_data()
    events = (
        lunar_festival_events(start_year, end_year)
        + solar_festival_events(start_year, end_year)
    )
    hol, covered, fallback = holiday_events(start_year, end_year, data)
    events += hol
    events.sort(key=lambda e: e.sort_key)
    meta = {
        "start_year": start_year,
        "end_year": end_year,
        "official_years": covered,
        "fallback_years": fallback,
        "total": len(events),
    }
    return events, meta
