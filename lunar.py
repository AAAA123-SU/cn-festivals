"""公历 / 农历 / 二十四节气 互算 —— 纯标准库实现，无第三方依赖。

算法依据：
* Jean Meeus《Astronomical Algorithms》(2nd ed.) 第 25 章（太阳视黄经）
  与第 49 章（朔望月，含行星摄动修正），理论时刻精度好于 1 分钟；
* GB/T 33661-2017《农历的编算和颁行》：
  - 以东经 120°（UTC+8，北京时间）为准；
  - 含冬至的月为十一月；
  - 两个十一月之间若有 13 个朔望月，则第一个不含中气的月为闰月；
* ΔT（TT - UT）采用 Espenak & Meeus 多项式，覆盖 1900—2150 年。

因此春节、中秋等农历节日的公历日期在 1900—2100 年范围内可直接推算，
不需要逐年维护数据表。
"""

from __future__ import annotations

import math
from datetime import date
from functools import lru_cache

__all__ = [
    "delta_t_seconds",
    "apparent_solar_longitude",
    "new_moon_date",
    "solar_term_date",
    "winter_solstice",
    "qingming",
    "chinese_new_year",
    "lunar_new_year_eve",
    "lunar_to_solar",
    "solar_to_lunar",
    "lunar_month_length",
    "lunar_month_days",
    "lunar_date_text",
    "lunar_month_name",
    "lunar_day_name",
]

J2000 = 2451545.0
_SYNODIC_MONTH = 29.530588861
_RAD = math.pi / 180.0

# 二十四节气的太阳视黄经（度）
TERM_NAMES = [
    (315, "立春"), (330, "雨水"), (345, "惊蛰"), (0, "春分"),
    (15, "清明"), (30, "谷雨"), (45, "立夏"), (60, "小满"),
    (75, "芒种"), (90, "夏至"), (105, "小暑"), (120, "大暑"),
    (135, "立秋"), (150, "处暑"), (165, "白露"), (180, "秋分"),
    (195, "寒露"), (210, "霜降"), (225, "立冬"), (240, "小雪"),
    (255, "大雪"), (270, "冬至"), (285, "小寒"), (300, "大寒"),
]

# 中气（用于置闰判断）：黄经为 30° 整数倍的节气
_MAJOR_TERM_ANGLES = tuple(range(0, 360, 30))


def _sind(x: float) -> float:
    return math.sin(x * _RAD)


def _cosd(x: float) -> float:
    return math.cos(x * _RAD)


# --------------------------------------------------------------------------
# 天文历表：ΔT、太阳视黄经、朔
# --------------------------------------------------------------------------
def delta_t_seconds(decimal_year: float) -> float:
    """TT 与 UT 之差（秒），Espenak & Meeus 分段多项式。"""
    y = decimal_year
    if y < 1900:
        t = (y - 1860) / 100.0
        return -0.5 + 32.0 * t * t
    if y < 1920:
        t = y - 1900
        return -2.79 + 1.494119 * t - 0.0598939 * t ** 2 + 0.0061966 * t ** 3 - 0.000197 * t ** 4
    if y < 1941:
        t = y - 1920
        return 21.20 + 0.84493 * t - 0.076100 * t ** 2 + 0.0020936 * t ** 3
    if y < 1961:
        t = y - 1950
        return 29.07 + 0.407 * t - t ** 2 / 233.0 + t ** 3 / 2547.0
    if y < 1986:
        t = y - 1975
        return 45.45 + 1.067 * t - t ** 2 / 260.0 - t ** 3 / 718.0
    if y < 2005:
        t = y - 2000
        return (63.86 + 0.3345 * t - 0.060374 * t ** 2 + 0.0017275 * t ** 3
                + 0.000651814 * t ** 4 + 0.00002373599 * t ** 5)
    if y < 2050:
        t = y - 2000
        return 62.92 + 0.32217 * t + 0.005589 * t ** 2
    if y < 2150:
        return -20 + 32.0 * ((y - 1820) / 100.0) ** 2 - 0.5628 * (2150 - y)
    t = (y - 1820) / 100.0
    return -20 + 32.0 * t * t


def apparent_solar_longitude(jde: float) -> float:
    """太阳视黄经（度，0—360），参数为 TT 儒略日。"""
    t = (jde - J2000) / 36525.0
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    center = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * _sind(m)
              + (0.019993 - 0.000101 * t) * _sind(2 * m)
              + 0.000289 * _sind(3 * m))
    true_long = l0 + center
    omega = 125.04 - 1934.136 * t
    return (true_long - 0.00569 - 0.00478 * _sind(omega)) % 360.0


def _jde_to_beijing_date(jde_tt: float) -> date:
    """TT 儒略日 -> 北京时间所在公历日期。"""
    decimal_year = 2000.0 + (jde_tt - J2000) / 365.25
    jd_ut = jde_tt - delta_t_seconds(decimal_year) / 86400.0
    jd_beijing = jd_ut + 8.0 / 24.0
    return date.fromordinal(int(math.floor(jd_beijing + 0.5)) - 1721425)


def _new_moon_jde(k: float) -> float:
    """第 k 个朔的 TT 儒略日（k=0 对应 2000-01-06 附近的新月）。"""
    t = k / 1236.85
    jde = (2451550.09766 + _SYNODIC_MONTH * k + 0.00015437 * t ** 2
           - 0.000000150 * t ** 3 + 0.00000000073 * t ** 4)
    e = 1 - 0.002516 * t - 0.0000074 * t ** 2
    m = 2.5534 + 29.10535670 * k - 0.0000014 * t ** 2 - 0.00000011 * t ** 3
    mp = (201.5643 + 385.81693528 * k + 0.0107582 * t ** 2
          + 0.00001238 * t ** 3 - 0.000000058 * t ** 4)
    f = (160.7108 + 390.67050284 * k - 0.0016118 * t ** 2
         - 0.00000227 * t ** 3 + 0.000000011 * t ** 4)
    om = 124.7746 - 1.56375588 * k + 0.0020672 * t ** 2 + 0.00000215 * t ** 3

    corr = (-0.40720 * _sind(mp)
            + 0.17241 * e * _sind(m)
            + 0.01608 * _sind(2 * mp)
            + 0.01039 * _sind(2 * f)
            + 0.00739 * e * _sind(mp - m)
            - 0.00514 * e * _sind(mp + m)
            + 0.00208 * e * e * _sind(2 * m)
            - 0.00111 * _sind(mp - 2 * f)
            - 0.00057 * _sind(mp + 2 * f)
            + 0.00056 * e * _sind(2 * mp + m)
            - 0.00042 * _sind(3 * mp)
            + 0.00042 * e * _sind(m + 2 * f)
            + 0.00038 * e * _sind(m - 2 * f)
            - 0.00024 * e * _sind(2 * mp - m)
            - 0.00017 * _sind(om)
            - 0.00007 * _sind(mp + 2 * m)
            + 0.00004 * _sind(2 * mp - 2 * f)
            + 0.00004 * _sind(3 * m)
            + 0.00003 * _sind(mp + m - 2 * f)
            + 0.00003 * _sind(2 * mp + 2 * f)
            - 0.00003 * _sind(mp + m + 2 * f)
            + 0.00003 * _sind(mp - m + 2 * f)
            - 0.00002 * _sind(mp - m - 2 * f)
            - 0.00002 * _sind(3 * mp + m)
            + 0.00002 * _sind(4 * mp))

    a_coef = [
        (299.77 + 0.107408 * k - 0.009173 * t ** 2, 0.000325),
        (251.88 + 0.016321 * k, 0.000165),
        (251.83 + 26.651886 * k, 0.000164),
        (349.42 + 36.412478 * k, 0.000126),
        (84.66 + 18.206239 * k, 0.000110),
        (141.74 + 53.303771 * k, 0.000062),
        (207.14 + 2.453732 * k, 0.000060),
        (154.84 + 7.306860 * k, 0.000056),
        (34.52 + 27.261239 * k, 0.000047),
        (207.19 + 0.121824 * k, 0.000042),
        (291.34 + 1.844379 * k, 0.000040),
        (161.72 + 24.198154 * k, 0.000037),
        (239.56 + 25.513099 * k, 0.000035),
        (331.55 + 3.592518 * k, 0.000023),
    ]
    for angle, coef in a_coef:
        corr += coef * _sind(angle)
    return jde + corr


@lru_cache(maxsize=None)
def new_moon_date(k: int) -> date:
    """第 k 个朔所在的北京时间日期。"""
    return _jde_to_beijing_date(_new_moon_jde(k))


def _new_moon_index_near(d: date) -> int:
    return int(round((d.toordinal() + 1721425 - 2451550.09766) / _SYNODIC_MONTH))


def _new_moon_on_or_before(d: date) -> date:
    k = _new_moon_index_near(d)
    while new_moon_date(k) > d:
        k -= 1
    while new_moon_date(k + 1) <= d:
        k += 1
    return new_moon_date(k)


def _new_moons_between(start: date, end: date) -> list[date]:
    """[start, end) 内的全部朔日（含 start 本身）。"""
    k = _new_moon_index_near(start)
    while new_moon_date(k) >= start and k - 1 > -100000:
        if new_moon_date(k - 1) < start:
            break
        k -= 1
    result: list[date] = []
    while new_moon_date(k) < end:
        d = new_moon_date(k)
        if d >= start:
            result.append(d)
        k += 1
    return result


def _solar_term_jde(year: int, angle: float) -> float:
    """求某公历年内太阳视黄经达到 angle 的 TT 儒略日。"""
    jan1_jdn = date(year, 1, 1).toordinal() + 1721425
    doy_guess = (79.0 + angle * 1.0146) % 365.2422  # 春分(0°)约 3/20
    jde = jan1_jdn + doy_guess - 0.5
    for _ in range(8):
        lam = apparent_solar_longitude(jde)
        diff = ((angle - lam + 180.0) % 360.0) - 180.0
        if abs(diff) < 1e-7:
            break
        jde += diff * 365.2422 / 360.0
    return jde


@lru_cache(maxsize=None)
def solar_term_date(year: int, angle: float) -> date:
    """某公历年内指定黄经的节气日期（北京时间）。"""
    return _jde_to_beijing_date(_solar_term_jde(year, angle))


def winter_solstice(year: int) -> date:
    """冬至（黄经 270°）。"""
    return solar_term_date(year, 270)


def qingming(year: int) -> date:
    """清明（黄经 15°）。"""
    return solar_term_date(year, 15)


def solar_term_name(angle: float) -> str:
    for a, name in TERM_NAMES:
        if a == angle:
            return name
    raise ValueError(f"非法节气黄经: {angle}")


# --------------------------------------------------------------------------
# 农历编排：岁（sui）与月份
# --------------------------------------------------------------------------
def _major_term_dates(year_lo: int, year_hi: int) -> list[date]:
    dates: list[date] = []
    for y in range(year_lo, year_hi + 1):
        for angle in _MAJOR_TERM_ANGLES:
            dates.append(solar_term_date(y, angle))
    return sorted(dates)


@lru_cache(maxsize=None)
def _sui(g: int) -> tuple[tuple[date, int, bool], ...]:
    """以公历 g 年冬至所在月（十一月）为起点的“岁”。

    返回 ((月首日, 月序, 是否闰月), ...)，月序从 11 开始递增（11,12,1,...,10）。
    """
    ws = winter_solstice(g)
    ws_next = winter_solstice(g + 1)
    start = _new_moon_on_or_before(ws)
    end = _new_moon_on_or_before(ws_next)

    starts = _new_moons_between(start, end)
    if len(starts) not in (12, 13):
        raise ValueError(f"{g} 年岁内朔望月数量异常: {len(starts)}")

    major = _major_term_dates(g, g + 1)
    has_leap = len(starts) == 13
    leap_used = False
    months: list[tuple[date, int, bool]] = []
    number = 11
    for i, s in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else end
        contains_major = any(s <= t < nxt for t in major)
        if has_leap and not leap_used and i > 0 and not contains_major:
            months.append((s, number, True))  # 闰月沿用上一个月的月序
            leap_used = True
            continue
        if i > 0:
            number = number % 12 + 1
        months.append((s, number, False))
    return tuple(months)


@lru_cache(maxsize=None)
def _year_months(lunar_year: int) -> tuple[tuple[date, int, bool], ...]:
    """农历年的全部月份，按时间顺序，从正月开始。"""
    prev_sui = [m for m in _sui(lunar_year - 1) if m[1] <= 10]
    next_sui = [m for m in _sui(lunar_year) if m[1] >= 11]
    months = prev_sui + next_sui
    if not months or months[0][1] != 1:
        raise ValueError(f"农历 {lunar_year} 年正月解析失败")
    return tuple(months)


def _month_end(start: date, lunar_year: int, index: int) -> date:
    months = _year_months(lunar_year)
    if index + 1 < len(months):
        return months[index + 1][0]
    return _year_months(lunar_year + 1)[0][0]


def lunar_month_days(lunar_year: int, month: int, is_leap: bool = False) -> int:
    months = _year_months(lunar_year)
    for i, (start, m, leap) in enumerate(months):
        if m == month and leap == is_leap:
            return (_month_end(start, lunar_year, i) - start).days
    raise ValueError(f"农历 {lunar_year} 年不存在 {'闰' if is_leap else ''}{month} 月")


def lunar_to_solar(lunar_year: int, month: int, day: int, is_leap: bool = False) -> date:
    """农历 -> 公历。day 允许超过当月天数时自动进位（仅限除夕等场景需自查）。"""
    months = _year_months(lunar_year)
    for i, (start, m, leap) in enumerate(months):
        if m == month and leap == is_leap:
            length = (_month_end(start, lunar_year, i) - start).days
            if not 1 <= day <= length:
                raise ValueError(
                    f"农历 {lunar_year} 年{'闰' if is_leap else ''}{month} 月只有 {length} 天"
                )
            return start.fromordinal(start.toordinal() + day - 1)
    raise ValueError(f"农历 {lunar_year} 年不存在 {'闰' if is_leap else ''}{month} 月")


def solar_to_lunar(d: date) -> tuple[int, int, int, bool]:
    """公历 -> (农历年, 月, 日, 是否闰月)。"""
    for lunar_year in (d.year, d.year - 1):
        months = _year_months(lunar_year)
        for i, (start, m, leap) in enumerate(months):
            end = _month_end(start, lunar_year, i)
            if start <= d < end:
                return lunar_year, m, (d - start).days + 1, leap
    raise ValueError(f"无法解析农历日期: {d}")


def chinese_new_year(lunar_year: int) -> date:
    """春节（农历正月初一）。"""
    return lunar_to_solar(lunar_year, 1, 1)


def lunar_new_year_eve(lunar_year: int) -> date:
    """除夕（农历该年腊月最后一天，可能为廿九或三十）。"""
    return lunar_to_solar(lunar_year, 12, lunar_month_days(lunar_year, 12))


# --------------------------------------------------------------------------
# 中文名称
# --------------------------------------------------------------------------
_LUNAR_MONTH_NAMES = {
    1: "正", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六",
    7: "七", 8: "八", 9: "九", 10: "十", 11: "冬", 12: "腊",
}
_DAY_TENS = {1: "十", 2: "二十", 3: "三十"}


def lunar_month_name(month: int, is_leap: bool = False) -> str:
    return ("闰" if is_leap else "") + _LUNAR_MONTH_NAMES[month] + "月"


def lunar_day_name(day: int) -> str:
    if day <= 10:
        return "初" + "一二三四五六七八九十"[day - 1]
    if day < 20:
        return "十" + "一二三四五六七八九"[day - 11]
    if day == 20:
        return "二十"
    if day < 30:
        return "廿" + "一二三四五六七八九"[day - 21]
    return "三十"


def lunar_date_text(lunar_year: int, month: int, day: int, is_leap: bool = False) -> str:
    return f"农历{lunar_month_name(month, is_leap)}{lunar_day_name(day)}"
