"""生成 iCalendar 订阅源与配套订阅页面。

用法：
    python build.py                     # 生成 去年 ~ 未来 10 年
    python build.py --start 2024 --end 2040
    python build.py --serve             # 生成后启动本地预览（含正确的 MIME）

输出：
    docs/china-festivals.ics           订阅源本体
    docs/index.html                    订阅引导页（含 iOS 添加步骤）
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

import ics_builder
import festivals

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
TEMPLATE = ROOT / "templates" / "index.template.html"
ICS_NAME = "china-festivals.ics"


def _payload(events: list[festivals.Event], meta: dict) -> dict:
    today = date.today()
    upcoming = [e for e in events if e.end > today][:12]
    years = [meta["start_year"], meta["end_year"]]
    focus_year = today.year
    year_view: dict[str, list[dict]] = {}
    for y in (focus_year, focus_year + 1):
        if meta["start_year"] <= y <= meta["end_year"]:
            year_view[str(y)] = [
                {
                    "d": e.start.isoformat(),
                    "e": (e.end).isoformat(),
                    "s": e.summary,
                    "c": e.category,
                }
                for e in events
                if e.start.year == y or (e.start.year == y - 1 and e.end.year == y and e.days > 1)
            ]

    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "today": today.isoformat(),
        "range": f"{years[0]}–{years[1]}",
        "startYear": meta["start_year"],
        "endYear": meta["end_year"],
        "total": meta["total"],
        "officialYears": meta["official_years"],
        "fallbackYears": meta["fallback_years"],
        "focusYear": focus_year,
        "upcoming": [
            {
                "d": e.start.isoformat(),
                "e": e.end.isoformat(),
                "s": e.summary,
                "c": e.category,
                "desc": e.description.split("\n")[0],
                "days": e.days,
            }
            for e in upcoming
        ],
        "yearView": year_view,
    }


def _inject(template: str, data: dict) -> str:
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    if "__CAL_DATA__" not in template:
        raise SystemExit("模板缺少 __CAL_DATA__ 占位符")
    return template.replace("__CAL_DATA__", blob)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成中国传统节日 iCalendar 订阅源")
    parser.add_argument("--start", type=int, default=max(2024, date.today().year - 1),
                        help="起始年份（默认去年）")
    parser.add_argument("--end", type=int, default=date.today().year + 10,
                        help="结束年份（默认未来 10 年）")
    parser.add_argument("--serve", action="store_true", help="生成后启动本地预览服务器")
    parser.add_argument("--port", type=int, default=8000, help="预览端口")
    args = parser.parse_args(argv)

    if args.start > args.end:
        raise SystemExit("起始年份不能大于结束年份")

    events, meta = festivals.build_events(args.start, args.end)

    DOCS.mkdir(exist_ok=True)
    ics_path = DOCS / ICS_NAME
    size = ics_builder.write_ics(ics_path, events, meta)

    payload = _payload(events, meta)
    template = TEMPLATE.read_text(encoding="utf-8")
    (DOCS / "index.html").write_text(_inject(template, payload), encoding="utf-8")

    print(f"已生成 {ics_path.relative_to(ROOT)}  ({meta['total']} 条日程, {size / 1024:.1f} KB)")
    print(f"覆盖年份：{meta['start_year']}–{meta['end_year']}")
    print(f"已收录官方调休安排：{meta['official_years'] or '无'}")
    if meta["fallback_years"]:
        print(f"仅法定天数（待官方公布）：{meta['fallback_years']}")
    print(f"订阅页面：{(DOCS / 'index.html').relative_to(ROOT)}")

    if args.serve:
        from serve import serve
        serve(DOCS, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
