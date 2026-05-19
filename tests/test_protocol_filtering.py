"""Tests for protocol-specific filtering (TCP, UDP, ICMP)."""

import pytest
from helpers import (
    tcp_connect,
    udp_send,
    ping,
    start_tcp_listener,
    start_udp_listener,
)


class TestTCPFiltering:
    """Verify TCP-specific filtering rules."""

    def test_tcp_allowed_port_works(self):
        """TCP on an allowed port (LAN -> DMZ:80) succeeds."""
        listener = start_tcp_listener("ns-dmz", 80)
        try:
            assert tcp_connect("ns-lan", "10.0.3.10", 80)
        finally:
            listener.terminate()
            listener.wait()

    def test_tcp_blocked_port_dropped(self):
        """TCP on a blocked port (WAN -> DMZ:3306) is dropped."""
        listener = start_tcp_listener("ns-dmz", 3306)
        try:
            assert not tcp_connect("ns-wan", "10.0.3.10", 3306, timeout=2)
        finally:
            listener.terminate()
            listener.wait()

    def test_tcp_high_port_blocked(self):
        """TCP on a random high port is blocked."""
        listener = start_tcp_listener("ns-dmz", 9999)
        try:
            assert not tcp_connect("ns-wan", "10.0.3.10", 9999, timeout=2)
        finally:
            listener.terminate()
            listener.wait()


class TestUDPFiltering:
    """Verify UDP-specific filtering rules."""

    def test_udp_dns_lan_to_dmz(self):
        """UDP DNS (port 53) from LAN to DMZ is allowed."""
        listener = start_udp_listener("ns-dmz", 53)
        try:
            assert udp_send("ns-lan", "10.0.3.10", 53)
        finally:
            listener.terminate()
            listener.wait()

    def test_udp_dns_dmz_to_wan(self):
        """UDP DNS (port 53) from DMZ to WAN is allowed."""
        listener = start_udp_listener("ns-wan", 53)
        try:
            assert udp_send("ns-dmz", "10.0.1.10", 53)
        finally:
            listener.terminate()
            listener.wait()

    def test_udp_random_port_blocked(self):
        """UDP on a non-DNS port from WAN to DMZ is blocked."""
        listener = start_udp_listener("ns-dmz", 9999)
        try:
            assert not udp_send("ns-wan", "10.0.3.10", 9999, timeout=2)
        finally:
            listener.terminate()
            listener.wait()


class TestICMPFiltering:
    """Verify ICMP filtering between zones."""

    def test_ping_lan_to_firewall(self):
        """LAN can ping the firewall."""
        assert ping("ns-lan", "10.0.2.1")

    def test_ping_wan_to_firewall(self):
        """WAN can ping the firewall (rate-limited but allowed)."""
        assert ping("ns-wan", "10.0.1.1")

    def test_ping_lan_to_dmz(self):
        """LAN can ping DMZ through the firewall."""
        assert ping("ns-lan", "10.0.3.10")

    def test_ping_dmz_to_wan(self):
        """DMZ can ping WAN through the firewall."""
        assert ping("ns-dmz", "10.0.1.10")

    def test_ping_lan_to_wan(self):
        """LAN can ping WAN through the firewall."""
        assert ping("ns-lan", "10.0.1.10")

    def test_ping_between_lan_hosts(self):
        """LAN hosts can ping each other via the bridge."""
        assert ping("ns-lan", "10.0.2.20")
