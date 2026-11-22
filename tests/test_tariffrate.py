#!/usr/bin/env python3
"""Tests for lib/tariffrate.py: HA rate payload parsing and unit normalisation."""

import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.tariffrate import normalise_rate, parse_rate_payload, apply_rate_message


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


if __name__ == "__main__":
    unittest.main()
