#################################################################################
"""
OpenEO Module: Wi-Fi status helpers
Helpers for the wifi_health plugin: read the status file written by the root
Wi-Fi watchdog and turn it into state fields and App Events log lines. Kept free
of globalState imports so that they can be unit tested off-device.
"""
#################################################################################

import json
import math

# A copy of the constant in portal/wifi_pinning.py: lib/ doesn't import portal/.
STATUS_FILE = "/run/openeo-wifi-watchdog/status.json"
STALE_AFTER = 300  # seconds; the watchdog rewrites the file every 60 s
LEVELS = ("ok", "warning", "problem", "unknown")

_UNKNOWN = {"level": "unknown", "code": "", "message": ""}


def read_status(path, now_wall):
    """Return the watchdog's status dict, or an "unknown" status if it is missing, bad or stale."""
    try:
        with open(path, "r") as f:
            status = json.load(f)
        if not isinstance(status, dict) or status.get("level") not in LEVELS:
            return dict(_UNKNOWN)
        updated = status.get("updated")
        if isinstance(updated, bool) or not isinstance(updated, (int, float)) or not math.isfinite(updated):
            return dict(_UNKNOWN)
        # abs(): also rejects a future-dated file after a clock jump
        if abs(now_wall - updated) > STALE_AFTER:
            return dict(_UNKNOWN)
        return status
    except (OSError, ValueError):
        return dict(_UNKNOWN)


def state_fields(status):
    """The stateDict entries published for a status dict."""
    return {
        "eo_wifi_health": status.get("level", "unknown"),
        "eo_wifi_health_code": status.get("code") or "",
        "eo_wifi_health_message": status.get("message") or "",
        "eo_wifi_health_since": status.get("since"),
        "eo_wifi_pinned_bssid": status.get("pinned_bssid") or "",
        "eo_wifi_current_bssid": status.get("current_bssid") or "",
        "eo_wifi_rssi": status.get("rssi"),
        "eo_wifi_drops_1h": status.get("drops_1h") or 0,
    }


def log_lines(prev, cur):
    """
    App Events lines for what changed between two status dicts. prev is the last known
    (not unknown) status, or None before the first one: an unknown status logs nothing,
    and the caller keeps comparing with the last known one, so a gap replays nothing.
    """
    lines = []
    level, code = cur.get("level"), cur.get("code")
    if level == "unknown":
        return lines
    if prev is None or (prev.get("level"), prev.get("code")) != (level, code):
        lines.append(f"wifi: {level} {code} - {cur.get('message')}")
    # Don't replay an old event on the first poll after an app restart.
    if prev is not None and cur.get("last_event"):
        if (prev.get("last_event"), prev.get("last_event_at")) != (cur["last_event"], cur.get("last_event_at")):
            lines.append(f"wifi: {cur['last_event']}")
    return lines


def ha_payload(state):
    """Wi-Fi fields for the Home Assistant state topic, read from the eo_wifi_* state keys."""
    return {
        "wifi_health": state.get("eo_wifi_health", "unknown"),
        "wifi_health_code": state.get("eo_wifi_health_code", ""),
        "wifi_health_message": state.get("eo_wifi_health_message", ""),
        "wifi_health_since": state.get("eo_wifi_health_since"),
        "wifi_pinned_bssid": state.get("eo_wifi_pinned_bssid", ""),
        "wifi_rssi": state.get("eo_wifi_rssi"),
    }


def ha_entities(state_topic):
    """Discovery entries (in homeassistant.py's `sensors` shape) for the Wi-Fi health and pinned-AP sensors."""
    return [
        {
            "component": "sensor",
            "object_id": "wifi_health",
            "name": "Wi-Fi Health",
            "state_topic": state_topic,
            "value_template": "{{ value_json.wifi_health }}",
            # enum: HA offers these values in automation editors; states stay lowercase machine values
            "device_class": "enum",
            "options": list(LEVELS),
            "json_attributes_topic": state_topic,
            "json_attributes_template": "{{ {'code': value_json.wifi_health_code, 'message': value_json.wifi_health_message, 'since': value_json.wifi_health_since} | tojson }}",
            "icon": "mdi:wifi-alert",
        },
        {
            "component": "sensor",
            "object_id": "wifi_pinned_ap",
            "name": "Wi-Fi Pinned AP",
            "state_topic": state_topic,
            "value_template": "{{ value_json.wifi_pinned_bssid if value_json.wifi_pinned_bssid else 'none' }}",
            "icon": "mdi:access-point",
        },
    ]
