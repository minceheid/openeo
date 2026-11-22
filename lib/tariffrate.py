"""Pure helpers for the live HA tariff rate: payload parsing and unit normalisation.

No MQTT, sqlite or globalState imports; callers pass state and a log callable.
"""

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
