"""Tests for nftables logging/counter of dropped packets.

We verify the rule counters increment instead of parsing dmesg,
because kernel log capture depends on system configuration
(printk levels, journald routing, dmesg_restrict, etc.)
while nftables counters are always available via `nft list chain`."""

import time
import pytest
from helpers import (
    tcp_connect,
    start_tcp_listener,
    get_rule_packets,
)


class TestFirewallLogging:
    """Verify that dropped packets hit the expected counters."""

    def test_wan_to_lan_drop_logged(self):
        """Blocked WAN->LAN traffic increments [FW-WAN2LAN-DROP] counter."""
        listener = start_tcp_listener("ns-lan", 80)
        try:
            before = get_rule_packets("forward", "FW-WAN2LAN-DROP")
            tcp_connect("ns-wan", "10.0.2.10", 80, timeout=2)
            time.sleep(0.3)
            after = get_rule_packets("forward", "FW-WAN2LAN-DROP")
            assert after > before, (
                f"WAN->LAN drop counter should increase, "
                f"before={before}, after={after}"
            )
        finally:
            listener.terminate()
            listener.wait()

    def test_dmz_to_lan_drop_logged(self):
        """Blocked DMZ->LAN traffic increments [FW-DMZ2LAN-DROP] counter."""
        listener = start_tcp_listener("ns-lan", 80)
        try:
            before = get_rule_packets("forward", "FW-DMZ2LAN-DROP")
            tcp_connect("ns-dmz", "10.0.2.10", 80, timeout=2)
            time.sleep(0.3)
            after = get_rule_packets("forward", "FW-DMZ2LAN-DROP")
            assert after > before, (
                f"DMZ->LAN drop counter should increase, "
                f"before={before}, after={after}"
            )
        finally:
            listener.terminate()
            listener.wait()

    def test_forward_drop_generic_logged(self):
        """Traffic on a non-allowed port hits the generic [FW-FORWARD-DROP]."""
        listener = start_tcp_listener("ns-wan", 22)
        try:
            before = get_rule_packets("forward", "FW-FORWARD-DROP")
            tcp_connect("ns-lan", "10.0.1.10", 22, timeout=2)
            time.sleep(0.3)
            after = get_rule_packets("forward", "FW-FORWARD-DROP")
            assert after > before, (
                f"Forward drop counter should increase, "
                f"before={before}, after={after}"
            )
        finally:
            listener.terminate()
            listener.wait()

    def test_input_drop_logged(self):
        """Traffic to the firewall on a non-allowed port hits [FW-INPUT-DROP]."""
        before = get_rule_packets("input", "FW-INPUT-DROP")
        tcp_connect("ns-wan", "10.0.1.1", 8080, timeout=2)
        time.sleep(0.3)
        after = get_rule_packets("input", "FW-INPUT-DROP")
        assert after > before, (
            f"Input drop counter should increase, "
            f"before={before}, after={after}"
        )

    def test_different_drop_chains_distinguished(self):
        """Each drop rule has its own counter — generic forward drops do
        NOT increment the WAN->LAN drop counter."""
        listener = start_tcp_listener("ns-wan", 22)
        try:
            wan2lan_before = get_rule_packets("forward", "FW-WAN2LAN-DROP")
            generic_before = get_rule_packets("forward", "FW-FORWARD-DROP")

            # Trigger a generic forward drop (LAN->WAN port 22, not allowed)
            tcp_connect("ns-lan", "10.0.1.10", 22, timeout=2)
            time.sleep(0.3)

            wan2lan_after = get_rule_packets("forward", "FW-WAN2LAN-DROP")
            generic_after = get_rule_packets("forward", "FW-FORWARD-DROP")

            assert generic_after > generic_before, "Generic drop should fire"
            assert wan2lan_after == wan2lan_before, (
                "WAN->LAN drop must NOT fire for LAN->WAN traffic"
            )
        finally:
            listener.terminate()
            listener.wait()
