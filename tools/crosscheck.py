"""开发期交叉校验：把自研农历算法与 lunardate 逐日比对（1900—2099）。

仅用于本地验证，不参与订阅源生成：

    pip install lunardate
    python tools/crosscheck.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

sys.path.insert(0, ".")

import lunar  # noqa: E402
from lunardate import LunarDate  # noqa: E402


def main() -> int:
    errors = 0
    # 1) 春节（正月初一）逐年比对
    for year in range(1901, 2099):
        mine = lunar.chinese_new_year(year)
        ref = LunarDate(year, 1, 1).to_solar_date()
        if mine != ref:
            print(f"[春节] {year}: 自研 {mine} != lunardate {ref}")
            errors += 1

    # 2) 正月初一 / 八月十五 / 十二月初一 逐年比对
    for year in range(1901, 2099):
        for month, day in ((1, 15), (5, 5), (8, 15), (9, 9), (12, 23)):
            mine = lunar.lunar_to_solar(year, month, day)
            ref = LunarDate(year, month, day).to_solar_date()
            if mine != ref:
                print(f"[{year}-{month:02d}-{day:02d}] 自研 {mine} != lunardate {ref}")
                errors += 1

    # 3) 逐日往返：从 1901-01-01 到 2098-12-31，全量比对
    d = date(1901, 1, 1)
    stop = date(2098, 12, 31)
    while d <= stop:
        y, m, dd, leap = lunar.solar_to_lunar(d)
        ref = LunarDate.from_solar_date(d.year, d.month, d.day)
        if (y, m, dd, bool(leap)) != (ref.year, ref.month, ref.day, bool(ref.is_leap_month)):
            print(f"[反查] {d}: 自研 {(y, m, dd, leap)} != lunardate "
                  f"{(ref.year, ref.month, ref.day, bool(ref.is_leap_month))}")
            errors += 1
            if errors > 40:
                print("错误过多，提前终止")
                return 1
        d += timedelta(days=1)

    # 4) 节气抽样：与公开日历核对（清明 / 冬至）
    checks = [
        (2024, 15, date(2024, 4, 4)), (2025, 15, date(2025, 4, 4)),
        (2026, 15, date(2026, 4, 5)), (2027, 15, date(2027, 4, 5)),
        (2024, 270, date(2024, 12, 21)), (2025, 270, date(2025, 12, 21)),
        (2026, 270, date(2026, 12, 22)), (2027, 270, date(2027, 12, 22)),
    ]
    for year, angle, expect in checks:
        got = lunar.solar_term_date(year, angle)
        flag = "OK " if got == expect else "BAD"
        print(f"[节气] {flag} {year} 黄经{angle}: {got} (期望 {expect})")
        if got != expect:
            errors += 1

    print(f"\n完成，共 {errors} 处不一致")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
