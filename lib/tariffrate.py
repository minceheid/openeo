"""Pure helpers for the live HA tariff rate: payload parsing, rate selection and half-hour settlement.

No MQTT, sqlite or globalState imports; callers pass state and a log callable.
"""

import datetime
import json
import logging
import math
import re

_UNAVAILABLE = {"unavailable", "unknown", "none"}
_MINOR_UNITS = {"p", "pence", "c", "ct", "¢", "öre"}
_DENOMINATORS = {"kwh": 1.0, "mwh": 0.001}


def normalise_rate(value, unit):
    """Return the rate as major currency per kWh, or None if the unit is missing/unrecognised."""
    if not isinstance(unit, str):
        return None
    parts = re.sub(r"\s+", "", unit.lower()).split("/")
    if len(parts) != 2:
        return None
    numerator, denominator = parts
    if denominator not in _DENOMINATORS:
        return None
    if re.fullmatch(r"[a-z]{3}", numerator):
        factor = 1.0
    elif numerator in _MINOR_UNITS:
        factor = 0.01
    else:
        return None
    # Skip the multiply for x1 so major-unit rates pass through bit-for-bit.
    factor *= _DENOMINATORS[denominator]
    return value if factor == 1.0 else value * factor


def _to_float(raw):
    """Return a finite float from a number or numeric string, else None."""
    if isinstance(raw, bool):
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_rate_payload(payload):
    """Parse an MQTT rate payload into (rate, unit, status).

    status is one of "ok", "unavailable", "bad_unit", "invalid". A bare number is
    taken as-is (unit None); a JSON object must carry a recognised unit.
    """
    text = payload.strip() if isinstance(payload, str) else ""
    if text.lower() in _UNAVAILABLE:
        return None, None, "unavailable"

    obj = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            obj = parsed
    except ValueError:
        pass

    if obj is None:
        number = _to_float(text)
        if number is None:
            return None, None, "invalid"
        return number, None, "ok"

    raw = obj.get("rate")
    if raw is None or (isinstance(raw, str) and raw.strip().lower() in _UNAVAILABLE):
        return None, None, "unavailable"
    number = _to_float(raw.strip() if isinstance(raw, str) else raw)
    if number is None:
        return None, None, "invalid"
    unit = obj.get("unit")
    rate = normalise_rate(number, unit)
    if rate is None:
        return None, unit, "bad_unit"
    return rate, unit, "ok"


def apply_rate_message(payload, now, state, warned_units, log):
    """Record a rate message in state["eo_ha_rate"], logging bad input.

    Warns once per distinct bad unit (tracked in warned_units) and for every invalid payload.
    """
    rate, unit, status = parse_rate_payload(payload)
    if status == "bad_unit":
        if unit not in warned_units:
            warned_units.add(unit)
            log(logging.WARNING, f"Tariff: unrecognised unit '{unit}' from HA - using schedule rate")
    elif status == "invalid":
        log(logging.WARNING, f"Tariff: invalid HA rate payload '{payload}' - using schedule rate")
    state["eo_ha_rate"] = {"value": rate if status == "ok" else None, "received_at": now}


def select_rate(now, ha_rate, ha_online, mqtt_connected, enabled, stale_minutes, schedule_rate):
    """Choose the rate to cost with; returns (rate, source, reason).

    source is "ha" or "schedule"; reason is "" for ha, else why the schedule was used.
    """
    if not enabled:
        reason = "disabled"
    elif not mqtt_connected:
        reason = "mqtt_disconnected"
    elif ha_online is False:
        reason = "ha_offline"
    elif ha_rate is None:
        reason = "no_data"
    elif ha_rate.get("value") is None:
        reason = "unavailable"
    elif now - ha_rate["received_at"] > stale_minutes * 60:
        reason = "stale"
    else:
        return ha_rate["value"], "ha", ""
    return schedule_rate, "schedule", reason


_FALLBACK_TEXT = {
    "stale": "stale (no update for {stale_minutes}m)",
    "unavailable": "unavailable",
    "ha_offline": "unavailable (Home Assistant offline)",
    "mqtt_disconnected": "unavailable (MQTT disconnected)",
}


def transition_message(prev, new, rate, ever_had_ha, stale_minutes):
    """Return (level, message) to log when the (source, reason) pair changes, else None.

    Silent when nothing changed or the feature is disabled. ever_had_ha means a fresh HA rate
    has been selected at least once before this call.
    """
    if new == prev or new[1] == "disabled":
        return None
    source, reason = new
    if source == "ha":
        if ever_had_ha:
            return logging.WARNING, f"Tariff: HA rate restored {rate:.5f}"
        return logging.INFO, f"Tariff: HA rate received {rate:.5f}"
    if reason == "no_data":
        if ever_had_ha:
            return logging.WARNING, f"Tariff: no HA rate since reconnect - using schedule rate {rate}"
        return logging.INFO, f"Tariff: waiting for first HA rate - using schedule rate {rate}"
    text = _FALLBACK_TEXT[reason].format(stale_minutes=stale_minutes)
    return logging.WARNING, f"Tariff: HA rate {text} - falling back to schedule rate {rate}"


def slot_key(dt):
    """Return the half-hour settlement slot (date, 0-47) for a local datetime."""
    return (dt.date(), dt.hour * 2 + dt.minute // 30)


class SessionCostAccumulator:
    """Costs a session in half-hour settlement slots.

    HA-rate energy is provisional within a slot: the whole slot's HA joules are costed at the
    latest HA rate seen, and settle into the per-tariff totals when the slot ends. Schedule
    (fallback) energy is settled immediately at its own rate.
    """

    def __init__(self):
        self.settled = {}
        self.pending_joules = 0
        self.last_ha_rate = None
        self.fallback_joules = 0
        self._slot = None

    def add(self, dt, joules, rate, source):
        key = slot_key(dt)
        if key != self._slot:
            self.settle()
            self._slot = key
        if source == "ha":
            self.last_ha_rate = round(rate, 5)
            self.pending_joules += joules
        else:
            self.settled[rate] = self.settled.get(rate, 0) + joules
            self.fallback_joules += joules

    def settle(self):
        """Move the pending HA joules into the settled totals at the last HA rate."""
        if self.pending_joules and self.last_ha_rate is not None:
            self.settled[self.last_ha_rate] = self.settled.get(self.last_ha_rate, 0) + self.pending_joules
        self.pending_joules = 0
        self.last_ha_rate = None

    def cost(self):
        """Settled plus provisional cost, unrounded."""
        total = sum(rate * joules for rate, joules in self.settled.items())
        if self.pending_joules and self.last_ha_rate is not None:
            total += self.pending_joules * self.last_ha_rate
        return total / 3_600_000

    def cost_by_tariff(self):
        """Return a new {rate: joules} map including pending HA joules (if any)."""
        result = dict(self.settled)
        if self.pending_joules and self.last_ha_rate is not None:
            result[self.last_ha_rate] = result.get(self.last_ha_rate, 0) + self.pending_joules
        return result
