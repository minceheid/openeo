#!/usr/bin/env python3
"""Tests for lib/tariffrate.py: HA rate payload parsing and unit normalisation."""

import datetime, logging, os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.tariffrate import (normalise_rate, parse_rate_payload, apply_rate_message,
                            select_rate, slot_key, SessionCostAccumulator,
                            transition_message)


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

    def test_invalid_payload_truncated(self):
        logs = []
        apply_rate_message("x" * 500, 2.0, {}, set(), lambda l, m: logs.append(m))
        self.assertEqual(logs[0], "Tariff: invalid HA rate payload " + repr("x" * 64) + " - using schedule rate")

    def test_unit_truncated(self):
        logs = []
        apply_rate_message('{"rate": "1", "unit": "%s"}' % ("u" * 200), 2.0, {}, set(), lambda l, m: logs.append(m))
        self.assertEqual(len(logs), 1)
        self.assertIn("'" + "u" * 32 + "'", logs[0])
        self.assertNotIn("u" * 33, logs[0])

    def test_warned_units_capped(self):
        warned, logs = set(), []
        for i in range(30):
            apply_rate_message('{"rate": "1", "unit": "bad%d"}' % i, 1.0, {}, warned, lambda l, m: logs.append(m))
        self.assertEqual(len(logs), 20)
        self.assertEqual(len(warned), 20)

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
        self.assertEqual(select_rate(10, None, None, True, True, 15, 0.27)[2], "no_data")
        self.assertEqual(select_rate(10, {"value": None, "received_at": 0}, True, True, True, 15, 0.27)[2], "unavailable")

    def test_disconnected_uses_fresh_rate(self):
        # A held rate stays in use while MQTT is down, until the stale timer expires.
        r = {"value": 0.07, "received_at": 0}
        self.assertEqual(select_rate(900, r, None, False, True, 15, 0.27), (0.07, "ha", ""))

    def test_disconnected_and_stale_reports_disconnected(self):
        r = {"value": 0.07, "received_at": 0}
        self.assertEqual(select_rate(901, r, None, False, True, 15, 0.27), (0.27, "schedule", "mqtt_disconnected"))

    def test_disconnected_without_rate_reports_disconnected(self):
        self.assertEqual(select_rate(10, None, None, False, True, 15, 0.27), (0.27, "schedule", "mqtt_disconnected"))

    def test_disconnected_with_unavailable_rate(self):
        r = {"value": None, "received_at": 5}
        self.assertEqual(select_rate(10, r, None, False, True, 15, 0.27)[2], "unavailable")

    def test_ha_offline_uses_fresh_rate(self):
        # An HA restart reports offline; the held rate stays in use until the stale timer expires.
        r = {"value": 0.07, "received_at": 0}
        self.assertEqual(select_rate(900, r, False, True, True, 15, 0.27), (0.07, "ha", ""))

    def test_ha_offline_and_stale_reports_offline(self):
        r = {"value": 0.07, "received_at": 0}
        self.assertEqual(select_rate(901, r, False, True, True, 15, 0.27), (0.27, "schedule", "ha_offline"))

    def test_ha_offline_without_rate_reports_offline(self):
        self.assertEqual(select_rate(10, None, False, True, True, 15, 0.27), (0.27, "schedule", "ha_offline"))

    def test_ha_offline_with_unavailable_rate(self):
        r = {"value": None, "received_at": 5}
        self.assertEqual(select_rate(10, r, False, True, True, 15, 0.27)[2], "unavailable")

    def test_mqtt_disconnected_reported_over_ha_offline(self):
        self.assertEqual(select_rate(10, None, False, False, True, 15, 0.27)[2], "mqtt_disconnected")

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

    def test_negative_zero_rate_normalised(self):
        a = SessionCostAccumulator()
        a.add(dt(5, 0), 10, -0.000001, "ha")
        self.assertEqual(str(a.last_ha_rate), "0.0")
        a.settle()
        self.assertEqual([str(k) for k in a.cost_by_tariff()], ["0.0"])

    def test_ha_rate_rounded_schedule_not(self):
        a = SessionCostAccumulator()
        a.add(dt(5, 0), 1, 0.1234567, "ha")
        a.add(dt(5, 0), 1, 0.2704812345, "schedule")
        a.settle()
        self.assertEqual(set(a.cost_by_tariff()), {0.12346, 0.2704812345})

class TransitionMessageTests(unittest.TestCase):
    HA = ("ha", "")

    def test_ha_first_received(self):
        self.assertEqual(transition_message(None, self.HA, 0.358941, False, 15),
                         (logging.INFO, "Tariff: HA rate received 0.35894"))

    def test_ha_restored(self):
        self.assertEqual(transition_message(("schedule", "stale"), self.HA, 0.25, True, 15),
                         (logging.WARNING, "Tariff: HA rate restored 0.25000"))

    def test_waiting_for_first(self):
        self.assertEqual(transition_message(None, ("schedule", "no_data"), 0.27048, False, 15),
                         (logging.INFO, "Tariff: waiting for first HA rate - using schedule rate 0.27048"))

    def test_startup_mqtt_disconnected_is_waiting(self):
        for reason in ("mqtt_disconnected", "ha_offline", "no_data"):
            self.assertEqual(transition_message(None, ("schedule", reason), 0.27048, False, 15),
                             (logging.INFO, "Tariff: waiting for first HA rate - using schedule rate 0.27048"))

    def test_moving_between_waiting_reasons_is_silent(self):
        self.assertIsNone(transition_message(("schedule", "mqtt_disconnected"), ("schedule", "no_data"), 0.27, False, 15))
        self.assertIsNone(transition_message(("schedule", "ha_offline"), ("schedule", "mqtt_disconnected"), 0.27, False, 15))

    def test_entering_waiting_from_other_reason_logs_info(self):
        self.assertEqual(transition_message(("schedule", "unavailable"), ("schedule", "no_data"), 0.27, False, 15)[0],
                         logging.INFO)

    def test_stale_and_unavailable_still_warn_before_first_ha(self):
        for reason in ("stale", "unavailable"):
            self.assertEqual(transition_message(None, ("schedule", reason), 0.27, False, 15)[0], logging.WARNING)

    def test_mqtt_disconnected_warns_after_having_ha(self):
        self.assertEqual(transition_message(None, ("schedule", "mqtt_disconnected"), 0.27, True, 15)[0], logging.WARNING)

    def test_unknown_reason_does_not_crash(self):
        level, msg = transition_message(self.HA, ("schedule", "brand_new"), 0.27, True, 15)
        self.assertEqual(level, logging.WARNING)
        self.assertIn("brand_new", msg)

    def test_fallback_reasons(self):
        texts = {"stale": "stale (no update for 15m)",
                 "unavailable": "unavailable",
                 "ha_offline": "stale (no update for 15m, Home Assistant offline)",
                 "mqtt_disconnected": "stale (no update for 15m, MQTT disconnected)"}
        for reason, text in texts.items():
            self.assertEqual(transition_message(self.HA, ("schedule", reason), 0.27048, True, 15),
                             (logging.WARNING,
                              f"Tariff: HA rate {text} - falling back to schedule rate 0.27048"))

    def test_no_change_returns_none(self):
        self.assertIsNone(transition_message(self.HA, self.HA, 0.3, True, 15))
        self.assertIsNone(transition_message(("schedule", "stale"), ("schedule", "stale"), 0.3, True, 15))

    def test_disabled_silent(self):
        self.assertIsNone(transition_message(self.HA, ("schedule", "disabled"), 0.3, True, 15))
        self.assertIsNone(transition_message(None, ("schedule", "disabled"), 0.3, False, 15))


if __name__ == "__main__":
    unittest.main()
