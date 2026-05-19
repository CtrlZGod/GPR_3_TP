"""Tests for nftables logging of dropped packets."""

import time
import pytest
from helpers import run_in_ns, tcp_connect, ping, start_tcp_listener, clear_dmesg, get_dmesg


class TestFirewallLogging:
    """Verify that dropped packets generate log entries with the correct prefix."""

    @pytest.fixture(autouse=True)
    def _clear_logs(self):
        """Clear dmesg before each test to isolate log entries."""
        clear_dmesg("ns-fw")
        yield

    def test_wan_to_lan_drop_logged(self):
        """Blocked WAN->LAN traffic generates a log with [FW-WAN2LAN-DROP]."""
        listener = start_tcp_listener("ns-lan", 80)
        try:
            tcp_connect("ns-wan", "10.0.2.10", 80, timeout=2)
            time.sleep(0.5)
            logs = get_dmesg("ns-fw", prefix="FW-WAN2LAN-DROP")
            assert len(logs) > 0, "Expected WAN->LAN drop to be logged"
        finally:
            listener.terminate()
            listener.wait()

    def test_dmz_to_lan_drop_logged(self):
        """Blocked DMZ->LAN traffic generates a log with [FW-DMZ2LAN-DROP]."""
        listener = start_tcp_listener("ns-lan", 80)
        try:
            tcp_connect("ns-dmz", "10.0.2.10", 80, timeout=2)
            time.sleep(0.5)
            logs = get_dmesg("ns-fw", prefix="FW-DMZ2LAN-DROP")
            assert len(logs) > 0, "Expected DMZ->LAN drop to be logged"
        finally:
            listener.terminate()
            listener.wait()

    def test_forward_drop_generic_logged(self):
        """Traffic on a non-allowed port generates [FW-FORWARD-DROP]."""
        listener = start_tcp_listener("ns-wan", 22)
        try:
            tcp_connect("ns-lan", "10.0.1.10", 22, timeout=2)
            time.sleep(0.5)
            logs = get_dmesg("ns-fw", prefix="FW-FORWARD-DROP")
            assert len(logs) > 0, "Expected generic forward drop to be logged"
        finally:
            listener.terminate()
            listener.wait()

    def test_input_drop_logged(self):
        """Traffic to the firewall on a non-allowed port generates
        [FW-INPUT-DROP]."""
        tcp_connect("ns-wan", "10.0.1.1", 8080, timeout=2)
        time.sleep(0.5)
        logs = get_dmesg("ns-fw", prefix="FW-INPUT-DROP")
        assert len(logs) > 0, "Expected input drop to be logged"

    def test_log_contains_source_info(self):
        """Log entries should contain source IP information."""
        tcp_connect("ns-wan", "10.0.2.10", 80, timeout=2)
        time.sleep(0.5)
        logs = get_dmesg("ns-fw", prefix="FW-WAN2LAN-DROP")
        if logs:
            log_text = "\n".join(logs)
            assert "SRC=10.0.1.10" in log_text, (
                f"Expected SRC=10.0.1.10 in log, got:\n{log_text}"
            )
