#!/usr/bin/env python3
"""Tests for lib/tariffrate.py: HA rate payload parsing and unit normalisation."""

import datetime, os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.tariffrate import (normalise_rate, parse_rate_payload, apply_rate_message,
                            select_rate, slot_key, SessionCostAccumulator)


def dt(h, m):
    return datetime.datetime(2026, 11, 22, h, m)


class NormaliseRateTests(unittest.TestCase):
    def test_major_units(self):
        self.assertEqual(normalise_rate(0.35894, "GBP/kWh"), 0.35894)
        self.assertEqual(normalise_rate(0.25, "EUR/kWh"), 0.25)

    def test_minor_units(self):
        for u in ["p/kWh", "pence/kWh", "c/kWh", "ct/kWh", "¢/kWh", "öre/kWh"]:
            self.assertAlmostEqual(normalise_rate(28.96, u), 0.2896)

    def test_mwh(self):
        self.assertAlmostEqual(normalise_rate(120.0, "GBP/MWh"), 0.12)

    def test_unit_spaces_and_case(self):
        self.assertAlmostEqual(normalise_rate(28.96, " P / KWH "), 0.2896)
        self.assertEqual(normalise_rate(0.3, "gbp/kwh"), 0.3)

    def test_unknown_or_missing_unit(self):
        self.assertIsNone(normalise_rate(1.0, "kr/kWh"))  # not a 3-letter code
        self.assertIsNone(normalise_rate(1.0, None))
        self.assertIsNone(normalise_rate(1.0, ""))

    def test_negative_kept(self):
        self.assertEqual(normalise_rate(-0.05, "GBP/kWh"), -0.05)


class ParseRatePayloadTests(unittest.TestCase):
    def test_parse_json(self):
        self.assertEqual(parse_rate_payload('{"rate": "0.35894", "unit": "GBP/kWh"}'), (0.35894, "GBP/kWh", "ok"))

    def test_parse_bare_number(self):
        self.assertEqual(parse_rate_payload("0.07"), (0.07, None, "ok"))

    def test_parse_unavailable(self):
        self.assertEqual(parse_rate_payload("unavailable")[2], "unavailable")
        self.assertEqual(parse_rate_payload(" Unknown ")[2], "unavailable")
        self.assertEqual(parse_rate_payload("NONE")[2], "unavailable")
        self.assertEqual(parse_rate_payload('{"rate": "unavailable", "unit": "GBP/kWh"}')[2], "unavailable")

    def test_parse_bad_unit(self):
        self.assertEqual(parse_rate_payload('{"rate": "1", "unit": "kr/kWh"}'), (None, "kr/kWh", "bad_unit"))

    def test_json_missing_or_empty_unit_is_bad_unit(self):
        self.assertEqual(parse_rate_payload('{"rate": "1"}'), (None, None, "bad_unit"))
        self.assertEqual(parse_rate_payload('{"rate": "1", "unit": ""}'), (None, "", "bad_unit"))

    def test_comma_decimal_invalid(self):
        self.assertEqual(parse_rate_payload('{"rate": "0,2896", "unit": "GBP/kWh"}')[2], "invalid")

    def test_non_finite_invalid(self):
        for p in ["nan", "inf", '{"rate": "nan", "unit": "GBP/kWh"}', "{bad json", ""]:
            self.assertEqual(parse_rate_payload(p)[2], "invalid")


class ApplyRateMessageTests(unittest.TestCase):
    def test_apply_warns_once_per_unit(self):
        state, warned, logs = {}, set(), []
        for _ in range(3):
            apply_rate_message('{"rate": "1", "unit": "kr/kWh"}', 100.0, state, warned, lambda l, m: logs.append(m))
        self.assertEqual(len(logs), 1)
        self.assertIn("unrecognised unit 'kr/kWh'", logs[0])
        self.assertEqual(state["eo_ha_rate"], {"value": None, "received_at": 100.0})

    def test_missing_unit_warns_once(self):
        state, warned, logs = {}, set(), []
        for _ in range(2):
            apply_rate_message('{"rate": "1"}', 1.0, state, warned, lambda l, m: logs.append(m))
        self.assertEqual(len(logs), 1)

    def test_apply_ok(self):
        state = {}
        apply_rate_message('{"rate": "28.96", "unit": "p/kWh"}', 5.0, state, set(), lambda l, m: None)
        self.assertAlmostEqual(state["eo_ha_rate"]["value"], 0.2896)

    def test_apply_bare_number(self):
        state = {}
        apply_rate_message("0.07", 5.0, state, set(), lambda l, m: None)
        self.assertEqual(state["eo_ha_rate"], {"value": 0.07, "received_at": 5.0})

    def test_invalid_warns_each_time(self):
        state, logs = {}, []
        for _ in range(2):
            apply_rate_message("{bad", 2.0, state, set(), lambda l, m: logs.append((l, m)))
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0][0], 30)
        self.assertEqual(logs[0][1], "Tariff: invalid HA rate payload '{bad' - using schedule rate")
        self.assertIsNone(state["eo_ha_rate"]["value"])

    def test_unavailable_no_log(self):
        state, logs = {}, []
        apply_rate_message("unavailable", 3.0, state, set(), lambda l, m: logs.append(m))
        self.assertEqual(logs, [])
        self.assertEqual(state["eo_ha_rate"], {"value": None, "received_at": 3.0})


class SelectRateTests(unittest.TestCase):
    def test_select_fresh(self):
        self.assertEqual(select_rate(1000, {"value": 0.07, "received_at": 900}, True, True, True, 15, 0.27), (0.07, "ha", ""))

    def test_select_reasons_in_order(self):
        r = {"value": 0.07, "received_at": 0}
        self.assertEqual(select_rate(10, r, True, True, False, 15, 0.27)[2], "disabled")
        self.assertEqual(select_rate(10, r, False, False, True, 15, 0.27)[2], "mqtt_disconnected")
        self.assertEqual(select_rate(10, r, False, True, True, 15, 0.27)[2], "ha_offline")
        self.assertEqual(select_rate(10, None, None, True, True, 15, 0.27)[2], "no_data")
        self.assertEqual(select_rate(10, {"value": None, "received_at": 0}, True, True, True, 15, 0.27)[2], "unavailable")

    def test_stale_boundary(self):
        r = {"value": 0.07, "received_at": 0}
        self.assertEqual(select_rate(900, r, True, True, True, 15, 0.27)[1], "ha")
        self.assertEqual(select_rate(901, r, True, True, True, 15, 0.27), (0.27, "schedule", "stale"))


class SessionCostAccumulatorTests(unittest.TestCase):
    def test_slot_key(self):
        self.assertEqual(slot_key(dt(1, 29)), (datetime.date(2026, 11, 22), 2))
        self.assertEqual(slot_key(dt(1, 30)), (datetime.date(2026, 11, 22), 3))

    def test_midslot_drop_recosts_slot(self):
        a = SessionCostAccumulator()
        a.add(dt(1, 0), 3_600_000, 0.27, "ha")
        a.add(dt(1, 10), 3_600_000, 0.07, "ha")
        self.assertAlmostEqual(a.cost(), 0.14)
        self.assertEqual(a.cost_by_tariff(), {0.07: 7_200_000})
        a.add(dt(1, 30), 0, 0.07, "ha")
        self.assertEqual(a.cost_by_tariff(), {0.07: 7_200_000})

    def test_cost_by_tariff_returns_copy_and_no_zero_keys(self):
        a = SessionCostAccumulator()
        a.add(dt(1, 0), 0, 0.07, "ha")
        self.assertEqual(a.cost_by_tariff(), {})
        a.add(dt(1, 1), 10, 0.07, "ha")
        a.cost_by_tariff()[0.07] = 99
        self.assertEqual(a.cost_by_tariff(), {0.07: 10})

    def test_mixed_ha_and_fallback_slot(self):
        a = SessionCostAccumulator()
        a.add(dt(2, 0), 3_600_000, 0.07, "ha")
        a.add(dt(2, 5), 3_600_000, 0.27048, "schedule")
        a.settle()
        self.assertAlmostEqual(a.cost(), 0.07 + 0.27048)
        self.assertEqual(a.fallback_joules, 3_600_000)

    def test_stale_gap_within_slot(self):
        a = SessionCostAccumulator()
        a.add(dt(3, 0), 3_600_000, 0.27, "ha")
        a.add(dt(3, 5), 3_600_000, 0.30, "schedule")
        a.add(dt(3, 10), 3_600_000, 0.07, "ha")
        a.settle()
        self.assertEqual(a.cost_by_tariff(), {0.07: 7_200_000, 0.30: 3_600_000})

    def test_slot_boundary(self):
        a = SessionCostAccumulator()
        a.add(dt(4, 29), 3_600_000, 0.27, "ha")
        a.add(dt(4, 30), 3_600_000, 0.07, "ha")
        a.settle()
        self.assertEqual(a.cost_by_tariff(), {0.27: 3_600_000, 0.07: 3_600_000})

    def test_ha_rate_rounded_schedule_not(self):
        a = SessionCostAccumulator()
        a.add(dt(5, 0), 1, 0.1234567, "ha")
        a.add(dt(5, 0), 1, 0.2704812345, "schedule")
        a.settle()
        self.assertEqual(set(a.cost_by_tariff()), {0.12346, 0.2704812345})

if __name__ == "__main__":
    unittest.main()
