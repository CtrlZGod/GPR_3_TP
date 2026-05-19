"""Tests for NAT rules (DNAT and masquerade/SNAT)."""

import pytest
from helpers import (
    tcp_connect,
    start_tcp_listener,
    start_tcp_listener_report_source,
    tcp_connect_get_source,
)


class TestDNAT:
    """Verify DNAT redirects WAN traffic to DMZ servers."""

    def test_dnat_http_to_dmz(self):
        """WAN connects to firewall WAN IP (10.0.1.1:80), traffic is
        DNATed to DMZ (10.0.3.10:80)."""
        listener = start_tcp_listener("ns-dmz", 80)
        try:
            assert tcp_connect("ns-wan", "10.0.1.1", 80)
        finally:
            listener.terminate()
            listener.wait()

    def test_dnat_https_to_dmz(self):
        """WAN connects to firewall WAN IP (10.0.1.1:443), traffic is
        DNATed to DMZ (10.0.3.10:443)."""
        listener = start_tcp_listener("ns-dmz", 443)
        try:
            assert tcp_connect("ns-wan", "10.0.1.1", 443)
        finally:
            listener.terminate()
            listener.wait()

    def test_dnat_only_on_wan_interface(self):
        """DNAT should only apply on the WAN interface. LAN connecting
        directly to DMZ IP should work without DNAT."""
        listener = start_tcp_listener("ns-dmz", 80)
        try:
            assert tcp_connect("ns-lan", "10.0.3.10", 80)
        finally:
            listener.terminate()
            listener.wait()


class TestMasquerade:
    """Verify masquerade/SNAT for outbound traffic."""

    def test_lan_to_wan_masquerade(self):
        """LAN traffic reaching WAN should appear to come from the
        firewall's WAN IP (10.0.1.1), not the LAN IP."""
        listener = start_tcp_listener_report_source("ns-wan", 80)
        try:
            source_ip = tcp_connect_get_source("ns-lan", "10.0.1.10", 80)
            assert source_ip == "10.0.1.1", (
                f"Expected source 10.0.1.1 (masqueraded), got {source_ip}"
            )
        finally:
            listener.terminate()
            listener.wait()

    def test_dmz_to_wan_masquerade(self):
        """DMZ traffic to WAN should also be masqueraded."""
        listener = start_tcp_listener_report_source("ns-wan", 80)
        try:
            source_ip = tcp_connect_get_source("ns-dmz", "10.0.1.10", 80)
            assert source_ip == "10.0.1.1", (
                f"Expected source 10.0.1.1 (masqueraded), got {source_ip}"
            )
        finally:
            listener.terminate()
            listener.wait()

    def test_lan_to_dmz_no_masquerade(self):
        """LAN to DMZ traffic should NOT be masqueraded — it stays on
        internal networks and the DMZ sees the real LAN IP."""
        listener = start_tcp_listener_report_source("ns-dmz", 80)
        try:
            source_ip = tcp_connect_get_source("ns-lan", "10.0.3.10", 80)
            assert source_ip == "10.0.2.10", (
                f"Expected source 10.0.2.10 (no masquerade), got {source_ip}"
            )
        finally:
            listener.terminate()
            listener.wait()
