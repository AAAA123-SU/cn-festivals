"""回归测试：python -m unittest discover -s tests -v

其中“已知日期”表为公开日历可查的权威值，用于锁定算法正确性。
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import festivals  # noqa: E402
import ics_builder  # noqa: E402
import lunar  # noqa: E402

ICS_PATH = ROOT / "docs" / "china-festivals.ics"

# 公开权威值：年份 -> 各节日公历日期
KNOWN = {
    2024: {"春节": "2024-02-10", "元宵": "2024-02-24", "清明": "2024-04-04",
           "端午": "2024-06-10", "中秋": "2024-09-17", "冬至": "2024-12-21"},
    2025: {"春节": "2025-01-29", "元宵": "2025-02-12", "清明": "2025-04-04",
           "端午": "2025-05-31", "七夕": "2025-08-29", "中秋": "2025-10-06",
           "重阳": "2025-10-29", "冬至": "2025-12-21"},
    2026: {"春节": "2026-02-17", "元宵": "2026-03-03", "清明": "2026-04-05",
           "端午": "2026-06-19", "七夕": "2026-08-19", "中秋": "2026-09-25",
           "重阳": "2026-10-18", "冬至": "2026-12-22"},
    2027: {"春节": "2027-02-06", "元宵": "2027-02-20", "清明": "2027-04-05",
           "端午": "2027-06-09", "中秋": "2027-09-15", "冬至": "2027-12-22"},
    2028: {"春节": "2028-01-26", "元宵": "2028-02-09", "清明": "2028-04-04",
           "端午": "2028-05-28", "中秋": "2028-10-03", "冬至": "2028-12-21"},
}

SOLAR_TERM_ANGLE = {"清明": 15.0, "冬至": 270.0}
LUNAR_RULE = {
    "春节": (1, 1), "元宵": (1, 15), "端午": (5, 5),
    "七夕": (7, 7), "中秋": (8, 15), "重阳": (9, 9),
}


class TestLunarDates(unittest.TestCase):
    def test_known_festivals(self):
        for year, table in KNOWN.items():
            for name, expect in table.items():
                if name in LUNAR_RULE:
                    m, d = LUNAR_RULE[name]
                    got = lunar.lunar_to_solar(year, m, d)
                else:
                    got = lunar.solar_term_date(year, SOLAR_TERM_ANGLE[name])
                self.assertEqual(got.isoformat(), expect, f"{year} {name}")

    def test_new_year_eve_is_day_before_cny(self):
        for year in range(2024, 2040):
            cny = lunar.chinese_new_year(year)
            eve = lunar.lunar_new_year_eve(year - 1)
            self.assertEqual((cny - eve).days, 1, f"{year} 除夕")

    def test_leap_month_2033(self):
        # 2033 年闰十一月，是农历编排的经典难点
        self.assertEqual(lunar.lunar_month_days(2033, 11, is_leap=True) > 0, True)
        self.assertEqual(lunar.lunar_to_solar(2033, 11, 1, is_leap=False).year, 2033)

    def test_month_lengths(self):
        for year in range(2024, 2040):
            for month in range(1, 13):
                length = lunar.lunar_month_days(year, month)
                self.assertIn(length, (29, 30), f"{year}-{month}")


class TestEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events, cls.meta = festivals.build_events(2024, 2036)

    def test_sorted_and_unique(self):
        uids = [e.uid for e in self.events]
        self.assertEqual(len(uids), len(set(uids)), "UID 重复会导致客户端重复日程")
        keys = [e.start for e in self.events]
        self.assertEqual(keys, sorted(keys), "事件未按时间排序")

    def test_spring_festival_2025_holiday(self):
        ev = [e for e in self.events if e.uid.startswith("holiday-20250128")]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].start, date(2025, 1, 28))
        self.assertEqual(ev[0].days, 8)
        self.assertIn("法定节假日 4 天", ev[0].description)
        self.assertIn("1 月 26 日", ev[0].description)
        self.assertIn("2 月 8 日", ev[0].description)

    def test_national_day_2025_merged_with_midautumn(self):
        ev = [e for e in self.events if e.uid.startswith("holiday-20251001")]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].days, 8)
        self.assertIn("中秋节", ev[0].summary + ev[0].description)

    def test_workdays_match_official(self):
        work = {e.start for e in self.events if e.category == "调休上班"}
        expect_2025 = {date(2025, 1, 26), date(2025, 2, 8), date(2025, 4, 27),
                       date(2025, 9, 28), date(2025, 10, 11)}
        self.assertTrue(expect_2025.issubset(work), sorted(work))

    def test_fallback_year_only_statutory(self):
        # 2027 未收录官方安排：春节只有 4 天法定假日，且不存在该年调休上班日
        ev = [e for e in self.events
              if e.category == "法定假期" and "春节" in e.summary and e.start.year == 2027]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].days, 4)
        self.assertIn("法定假日", ev[0].summary)
        self.assertFalse([e for e in self.events
                          if e.category == "调休上班" and e.start.year == 2027])

    def test_all_day_end_after_start(self):
        for e in self.events:
            self.assertGreater(e.end, e.start, e.uid)


class TestIcsOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events, cls.meta = festivals.build_events(2024, 2036)
        cls.raw = ics_builder.render(cls.events, cls.meta)

    def test_crlf_only(self):
        self.assertEqual(self.raw.count("\n"), self.raw.count("\r\n"))

    def test_no_long_lines(self):
        for line in self.raw.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75, line[:40])

    def test_balanced_blocks(self):
        self.assertTrue(self.raw.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(self.raw.endswith("END:VCALENDAR\r\n"))
        self.assertEqual(self.raw.count("BEGIN:VEVENT"), self.raw.count("END:VEVENT"))
        self.assertEqual(self.raw.count("BEGIN:VALARM"), self.raw.count("END:VALARM"))

    def test_required_properties(self):
        for prop in ("VERSION:2.0", "CALSCALE:GREGORIAN", "X-WR-TIMEZONE:Asia/Shanghai",
                     "REFRESH-INTERVAL", "X-PUBLISHED-TTL"):
            self.assertIn(prop, self.raw)

    def test_parsable_by_icalendar(self):
        try:
            from icalendar import Calendar
        except ImportError:
            self.skipTest("未安装 icalendar")
        cal = Calendar.from_ical(self.raw.encode("utf-8"))
        events = list(cal.walk("VEVENT"))
        self.assertEqual(len(events), len(self.events))

    def test_docs_file_valid(self):
        if not ICS_PATH.exists():
            self.skipTest("尚未生成 docs/china-festivals.ics")
        with ICS_PATH.open("r", encoding="utf-8", newline="") as fh:
            disk = fh.read()
        self.assertTrue(disk.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertGreater(disk.count("BEGIN:VEVENT"), 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
