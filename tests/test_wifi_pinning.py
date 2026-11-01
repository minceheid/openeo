from conftest import FakeRunner, ok, fail, cp
from wifi_pinning import split_terse, unescape, format_event, make_runner


# =========================
# Parser and helpers
# =========================

def test_split_terse_escaped_bssid():
    assert split_terse(r"AA\:BB\:CC\:DD\:EE\:01:MyMesh:82") == ["AA:BB:CC:DD:EE:01", "MyMesh", "82"]


def test_split_terse_ssid_with_colon_and_backslash():
    assert split_terse(r"AA\:BB\:CC\:DD\:EE\:02:Caf\\e\: Net:40") == ["AA:BB:CC:DD:EE:02", "Caf\\e: Net", "40"]


def test_split_terse_empty_ssid():
    assert split_terse(r"AA\:BB\:CC\:DD\:EE\:03::55") == ["AA:BB:CC:DD:EE:03", "", "55"]


def test_unescape():
    assert unescape(r"AA\:BB\:CC\:DD\:EE\:01") == "AA:BB:CC:DD:EE:01"


def test_format_event_omits_none_and_keeps_order():
    assert format_event("PIN", {"bssid": "AA:BB", "signal": 82, "loss": None, "samples": 3}) == "PIN bssid=AA:BB signal=82 samples=3"


def test_make_runner_missing_binary_returns_127():
    assert make_runner(sudo=False)(["definitely-not-a-binary-xyz"]).returncode == 127


# =========================
# Selection rule and sampling
# =========================

from wifi_pinning import select_bssid, scan_samples, choose_pin

A, B = "AA:AA:AA:AA:AA:01", "BB:BB:BB:BB:BB:02"
SCAN = ("nmcli", "-t", "-f", "BSSID,SSID,SIGNAL", "dev", "wifi", "list", "ifname", "wlan0", "--rescan")


def s(*rows):
    return [(b, "Mesh", sig) for b, sig in rows]


def no_sleep(_):
    pass


def test_select_zero_or_one_bssid_no_pin():
    assert select_bssid([], "Mesh").bssid is None
    assert select_bssid([s((A, 80))] * 3, "Mesh").reason == "single"


def test_select_close_signals_pins_stronger():
    r = select_bssid([s((A, 70), (B, 68))] * 3, "Mesh")
    assert (r.bssid, r.signal, r.runner_up, r.reason) == (A, 70, 68, "pin")


def test_select_min_signal_boundary():
    assert select_bssid([s((A, 29), (B, 10))] * 3, "Mesh").reason == "weak"
    assert select_bssid([s((A, 30), (B, 10))] * 3, "Mesh").bssid == A


def test_select_median_ignores_outlier():
    samples = [s((A, 50), (B, 60)), s((A, 50), (B, 60)), s((A, 95), (B, 60))]
    assert select_bssid(samples, "Mesh").bssid == B


def test_select_drops_bssid_seen_once():
    samples = [s((A, 60), (B, 90)), s((A, 60)), s((A, 60))]
    assert select_bssid(samples, "Mesh").reason == "single"


def test_select_collapses_duplicates_keeping_max():
    samples = [s((A, 40), (A, 70), (B, 50))] * 3
    assert select_bssid(samples, "Mesh").signal == 70


def test_select_exact_ssid_match():
    samples = [[(A, "Mesh ", 90), (B, "mesh", 80), ("CC:CC:CC:CC:CC:03", "Mesh", 50)]] * 3
    assert select_bssid(samples, "Mesh").reason == "single"


def test_select_tie_is_deterministic():
    assert select_bssid([s((B, 70), (A, 70))] * 3, "Mesh").bssid == A


C = "CC:CC:CC:CC:CC:03"


def test_select_excluded_best_picks_next():
    samples = [s((A, 80), (B, 70), (C, 60))] * 3
    sel = select_bssid(samples, "Mesh", exclude={A})
    assert (sel.bssid, sel.signal, sel.runner_up, sel.reason) == (B, 70, 80, "pin")


def test_select_multi_ap_test_uses_full_scan():
    samples = [s((A, 80), (B, 70))] * 3
    assert select_bssid(samples, "Mesh", exclude={A}).bssid == B     # one left, still multi-AP


def test_select_all_excluded():
    samples = [s((A, 80), (B, 70))] * 3
    sel = select_bssid(samples, "Mesh", exclude={A, B})
    assert (sel.bssid, sel.samples, sel.reason) == (None, 3, "excluded")


def test_select_exclude_is_case_insensitive():
    samples = [s(("AA:BB:CC:DD:EE:01", 80), ("AA:BB:CC:DD:EE:02", 70))] * 3
    assert select_bssid(samples, "Mesh", exclude={"aa:bb:cc:dd:ee:01"}).bssid == "AA:BB:CC:DD:EE:02"


def test_select_weak_test_applies_to_remaining_best():
    samples = [s((A, 80), (B, 20))] * 3
    sel = select_bssid(samples, "Mesh", exclude={A})
    assert (sel.reason, sel.signal, sel.runner_up) == ("weak", 20, 80)


def test_scan_skips_failed_samples_and_falls_back_to_cache():
    line = "AA\\:AA\\:AA\\:AA\\:AA\\:01:Mesh:70\nBB\\:BB\\:BB\\:BB\\:BB\\:02:Mesh:40\nbad line\n"
    run = FakeRunner([(SCAN + ("yes",), fail()), (SCAN + ("no",), ok(line))])
    samples = scan_samples(run, sleep=no_sleep)
    assert len(samples) == 1 and len(samples[0]) == 2
    assert choose_pin(run, "Mesh", sleep=no_sleep).bssid == A


def test_scan_all_failed_including_cache_is_noscan():
    run = FakeRunner([(("nmcli",), fail())])
    assert choose_pin(run, "Mesh", sleep=no_sleep).reason == "noscan"


# =========================
# Health check, station dump, nmcli wrappers
# =========================

from wifi_pinning import health_check, station_info, get_pin, link_up

GW = ("nmcli", "-g", "IP4.GATEWAY", "device", "show", "wlan0")
GW_OK = (GW, ok("192.168.1.1\n"))


def ping_out(loss):
    return ok(f"10 packets transmitted, {10 - loss // 10} received, {loss}% packet loss, time 1803ms\n")


def test_health_pass_fail_boundaries():
    for loss, passed in [(0, True), (20, True), (30, False)]:
        r = health_check(FakeRunner([GW_OK, (("ping",), ping_out(loss))]))
        assert (r.passed, r.loss, r.skipped) == (passed, loss, False)


def test_health_100_percent_loss_fails_even_with_rc_1():
    out = "10 packets transmitted, 0 received, 100% packet loss, time 9ms\n"
    r = health_check(FakeRunner([GW_OK, (("ping",), cp(1, out))]))
    assert (r.passed, r.loss) == (False, 100)


def test_health_pings_gateway_on_wlan0():
    run = FakeRunner([GW_OK, (("ping",), ping_out(0))])
    health_check(run)
    assert run.calls[-1] == ["ping", "-c", "10", "-i", "0.2", "-W", "1", "-I", "wlan0", "192.168.1.1"]


def test_health_skipped_cases_count_as_pass():
    for runner in [FakeRunner([(GW, ok("\n"))]),
                   FakeRunner([GW_OK, (("ping",), fail(127))]),
                   FakeRunner([GW_OK, (("ping",), ok("garbage"))])]:
        r = health_check(runner)
        assert (r.passed, r.skipped, r.loss) == (True, True, None)


def test_station_info_parses_real_output():
    dump = ("Station aa:bb:cc:dd:ee:01 (on wlan0)\n\tinactive time:\t120 ms\n\ttx retries:\t3\n\ttx failed:\t0\n"
            "\tsignal:  \t-52 [-52] dBm\n\ttx bitrate:\t65.0 MBit/s MCS 7\n")
    assert station_info(FakeRunner([(("iw",), ok(dump))])) == {"rssi": -52, "tx_bitrate": 65.0, "tx_retries": 3, "tx_failed": 0}


def test_station_info_missing_fields_and_failure():
    assert station_info(FakeRunner([(("iw",), ok("Station x (on wlan0)\n\tsignal:\t-60 dBm\n"))])) == {"rssi": -60}
    assert station_info(FakeRunner([(("iw",), fail(127))])) == {}


def test_get_pin_unescapes_colons():
    run = FakeRunner([(("nmcli", "-g", "802-11-wireless.bssid"), ok("AA\\:BB\\:CC\\:DD\\:EE\\:01\n"))])
    assert get_pin(run) == "AA:BB:CC:DD:EE:01"


def test_get_pin_failure_is_empty():
    assert get_pin(FakeRunner([(("nmcli",), fail(10))])) == ""


def test_link_up():
    q = ("nmcli", "-g", "GENERAL.STATE,GENERAL.CONNECTION")
    assert link_up(FakeRunner([(q, ok("100 (connected)\ncustom-wifi\n"))]))
    assert not link_up(FakeRunner([(q, ok("60 (need-auth)\ncustom-wifi\n"))]))
    assert not link_up(FakeRunner([(q, ok("100 (connected)\nother\n"))]))


# =========================
# Portal setup flow
# =========================

import portal

NM_UP = ("nmcli", "connection", "up", "custom-wifi")
TOUCH = ("touch", "/run/openeo-wifi-setup.lock")
RMLOCK = ("rm", "-f", "/run/openeo-wifi-setup.lock")
PIN_A = "AA:BB:CC:DD:EE:01"


def pick(monkeypatch, bssid, signal=80):
    sel = portal.wifi_pinning.Selection(bssid, signal if bssid else None, 60, 3, "pin" if bssid else "single")
    monkeypatch.setattr(portal.wifi_pinning, "choose_pin", lambda run, ssid, sleep=None: sel)


def health(monkeypatch, passed, loss):
    monkeypatch.setattr(portal.wifi_pinning, "health_check", lambda run: portal.wifi_pinning.HealthResult(passed, loss, False))


def has(run, *prefix):
    return any(tuple(c[:len(prefix)]) == prefix for c in run.calls)


def test_setup_pins_and_keeps_healthy_pin(monkeypatch):
    pick(monkeypatch, PIN_A); health(monkeypatch, True, 0)
    run = FakeRunner([])
    assert portal.setup_wifi_connection("Mesh", "password1", run=run, sleep=no_sleep) == (True, "", PIN_A, 80)
    assert has(run, "nmcli", "connection", "modify", "custom-wifi", "802-11-wireless.bssid", PIN_A)
    assert any("wifi-sec.psk-flags" in c and "0" in c for c in run.calls)
    assert run.calls[0] == list(TOUCH) and run.calls[-1] == list(RMLOCK)


def test_setup_pinned_connect_failure_unpins_and_retries(monkeypatch):
    pick(monkeypatch, PIN_A)
    run = FakeRunner([(NM_UP, [fail(4, "assoc rejected"), ok("Connection successfully activated")])])
    success, msg, bssid, sig = portal.setup_wifi_connection("Mesh", "password1", run=run, sleep=no_sleep)
    assert (success, msg, bssid, sig) == (True, "Connection successfully activated", None, None)
    assert has(run, "nmcli", "connection", "modify", "custom-wifi", "802-11-wireless.bssid", "")


def test_setup_failed_health_unpins_but_reports_success(monkeypatch):
    pick(monkeypatch, PIN_A); health(monkeypatch, False, 60)
    run = FakeRunner([])
    success, _, bssid, _ = portal.setup_wifi_connection("Mesh", "password1", run=run, sleep=no_sleep)
    assert (success, bssid) == (True, None)
    assert has(run, "nmcli", "connection", "modify", "custom-wifi", "802-11-wireless.bssid", "")
    assert len([c for c in run.calls if tuple(c[:4]) == NM_UP]) == 2


def test_setup_no_pin_connects_unpinned(monkeypatch):
    pick(monkeypatch, None)
    run = FakeRunner([])
    assert portal.setup_wifi_connection("Mesh", "password1", run=run, sleep=no_sleep)[2:] == (None, None)
    assert not has(run, "nmcli", "connection", "modify", "custom-wifi", "802-11-wireless.bssid")


def test_setup_wrong_password_reports_failure_unpinned(monkeypatch):
    pick(monkeypatch, PIN_A)
    run = FakeRunner([(NM_UP, fail(4, "Secrets were required"))])
    assert portal.setup_wifi_connection("Mesh", "password1", run=run, sleep=no_sleep) == (False, "Secrets were required", None, None)


def test_setup_add_failure_returns_nmcli_error(monkeypatch):
    pick(monkeypatch, None)
    run = FakeRunner([(("nmcli", "connection", "add"), fail(2, "bad ssid"))])
    assert portal.setup_wifi_connection("Mesh", "password1", run=run, sleep=no_sleep) == (False, "nmcli error: bad ssid", None, None)
    assert run.calls[-1] == list(RMLOCK)


def test_setup_removes_lock_on_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(portal.wifi_pinning, "choose_pin", boom)
    run = FakeRunner([])
    assert portal.setup_wifi_connection("Mesh", "password1", run=run, sleep=no_sleep)[0] is False
    assert run.calls[-1] == list(RMLOCK)


def test_dryrun_returns_tuple(monkeypatch):
    monkeypatch.setattr(portal, "DRYRUN", True)
    assert portal.setup_wifi_connection("Mesh", "password1") == (False, "dryrun - not executed", None, None)


def test_api_set_wifi_reports_pin(monkeypatch):
    monkeypatch.setattr(portal, "setup_wifi_connection", lambda ssid, pw: (True, "ok", PIN_A, 80))
    monkeypatch.setattr(portal, "can_access_internet", lambda: True)
    r = portal.api_set_wifi({"ssid": "Mesh", "password": "password1"})
    assert (r["pinned_bssid"], r["pinned_signal"], r["connected_to_wifi"]) == (PIN_A, 80, True)


def test_api_get_wifi_reports_pinned(monkeypatch):
    monkeypatch.setattr(portal, "get_wifi_data", lambda: {"SSID": [], "CONNECTED": ""})
    monkeypatch.setattr(portal, "can_access_internet", lambda: False)
    monkeypatch.setattr(portal, "get_ssh_public_key", lambda: "")
    monkeypatch.setattr(portal, "get_ip_address", lambda ifname: None)
    monkeypatch.setattr(portal.wifi_pinning, "get_pin", lambda run: PIN_A)
    assert portal.api_get_wifi({})["PINNED"] == PIN_A


def test_setup_refreshes_lock_before_every_connect(monkeypatch):
    # A slow setup must not let the lock go stale (LOCK_STALE) while it connects
    pick(monkeypatch, PIN_A); health(monkeypatch, False, 60)
    run = FakeRunner([])
    portal.setup_wifi_connection("Mesh", "password1", run=run, sleep=no_sleep)
    ups = [i for i, c in enumerate(run.calls) if tuple(c[:4]) == NM_UP]
    assert len(ups) == 2
    assert all(run.calls[i - 1] == list(TOUCH) for i in ups)


# =========================
# Link state (iw + NM)
# =========================

from wifi_pinning import link_state, LinkState, norm_bssid

NMQ = ("nmcli", "-g", "GENERAL.STATE,GENERAL.CONNECTION")
IWQ = ("iw", "dev", "wlan0", "link")
NM_UP_OUT = ok("100 (connected)\ncustom-wifi\n")
IW_CONNECTED = ok("Connected to 02:ec:da:fd:20:a6 (on wlan0)\n\tSSID: Home\n\tsignal: -64 dBm\n")


def test_link_state_nm_up_and_iw_connected():
    s = link_state(FakeRunner([(NMQ, NM_UP_OUT), (IWQ, IW_CONNECTED)]))
    assert s == LinkState(True, "02:EC:DA:FD:20:A6", -64)


def test_link_state_iw_not_connected_is_down():
    assert not link_state(FakeRunner([(NMQ, NM_UP_OUT), (IWQ, ok("Not connected.\n"))])).up


def test_link_state_iw_missing_is_nm_only():
    assert link_state(FakeRunner([(NMQ, NM_UP_OUT), (IWQ, fail(127))])) == LinkState(True, None, None)


def test_link_state_unrecognised_iw_output_is_nm_only():
    assert link_state(FakeRunner([(NMQ, NM_UP_OUT), (IWQ, ok(""))])).up
    assert link_state(FakeRunner([(NMQ, NM_UP_OUT), (IWQ, ok("command failed: No such device (-19)\n"))])).up


def test_link_state_nm_down_wins():
    assert not link_state(FakeRunner([(NMQ, ok("30 (disconnected)\n\n")), (IWQ, IW_CONNECTED)])).up


def test_norm_bssid():
    assert norm_bssid(" 02:ec:da:fd:20:a6\n") == "02:EC:DA:FD:20:A6" and norm_bssid(None) == ""


# =========================
# wpa_supplicant journal
# =========================

import json
from wifi_pinning import parse_wpa_journal, read_wpa_events, WpaEvent


def jline(mono_s, msg, boot="b1", cursor="c"):
    return json.dumps({"__CURSOR": cursor, "__MONOTONIC_TIMESTAMP": str(int(mono_s * 1e6)),
                       "_BOOT_ID": boot, "MESSAGE": msg})


def test_parse_wpa_journal_drops_auth_and_cursor():
    out = "\n".join([
        jline(100, "wlan0: CTRL-EVENT-DISCONNECTED bssid=02:ec:da:fd:20:a6 reason=0 locally_generated=1", cursor="c1"),
        jline(101, "wlan0: CTRL-EVENT-ASSOC-REJECT bssid=02:ec:da:fd:20:a6 status_code=16", cursor="c2"),
        jline(102, 'wlan0: CTRL-EVENT-SSID-TEMP-DISABLED id=0 ssid="x" auth_failures=1 reason=WRONG_KEY', cursor="c3"),
        jline(103, "wlan0: CTRL-EVENT-DISCONNECTED bssid=aa:aa:aa:aa:aa:aa reason=3", boot="old", cursor="c4"),
        "{not json"])
    events, cursor = parse_wpa_journal(out, boot_id="b1")
    assert events == [WpaEvent("drop", 100.0, "02:EC:DA:FD:20:A6"), WpaEvent("auth_fail", 102.0)]
    assert cursor == "c4"


def test_parse_wpa_journal_skips_byte_array_message():
    assert parse_wpa_journal(json.dumps({"__CURSOR": "c", "__MONOTONIC_TIMESTAMP": "1", "MESSAGE": [104, 105]}))[0] == []


def test_parse_wpa_journal_skips_missing_timestamp_and_no_lines_gives_no_cursor():
    line = json.dumps({"__CURSOR": "c", "MESSAGE": "wlan0: CTRL-EVENT-DISCONNECTED bssid=02:ec:da:fd:20:a6"})
    assert parse_wpa_journal(line) == ([], "c")
    assert parse_wpa_journal("") == ([], None)


DISC = "wlan0: CTRL-EVENT-DISCONNECTED bssid=02:ec:da:fd:20:a6 reason=3"
JQ = ("journalctl",)


def test_read_wpa_events_uses_cursor():
    run = FakeRunner([(JQ, ok(jline(5, DISC, cursor="c2")))])
    events, cursor = read_wpa_events(run, "c1", "b1")
    assert len(run.calls) == 1 and "--after-cursor" in run.calls[0] and "c1" in run.calls[0]
    assert events == [WpaEvent("drop", 5.0, "02:EC:DA:FD:20:A6")] and cursor == "c2"


def test_read_wpa_events_no_cursor_reads_window():
    run = FakeRunner([(JQ, ok(jline(5, DISC, cursor="c2")))])
    events, cursor = read_wpa_events(run, None, "b1")
    assert "--since" in run.calls[0] and "-600s" in run.calls[0] and "--after-cursor" not in run.calls[0]
    assert cursor == "c2" and len(events) == 1


def test_read_wpa_events_bad_cursor_falls_back_to_window():
    run = FakeRunner([(JQ, [fail(1), ok(jline(5, DISC, cursor="c2"))])])
    events, cursor = read_wpa_events(run, "stale", "b1")
    assert "--after-cursor" in run.calls[0] and "--since" in run.calls[1]
    assert len(events) == 1 and cursor == "c2"


def test_read_wpa_events_empty_keeps_cursor():
    assert read_wpa_events(FakeRunner([(JQ, ok(""))]), "c1", "b1") == ([], "c1")


def test_make_runner_skips_sudo_when_root(monkeypatch):
    """sudo logs the full command line, which for nmcli modify includes the Wi-Fi PSK."""
    import subprocess
    import wifi_pinning as wpm
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
    monkeypatch.setattr(wpm.os, "geteuid", lambda: 0)
    wpm.make_runner(sudo=True)(["nmcli", "x"])
    monkeypatch.setattr(wpm.os, "geteuid", lambda: 1000)
    wpm.make_runner(sudo=True)(["nmcli", "x"])
    assert seen == [["nmcli", "x"], ["sudo", "nmcli", "x"]]
