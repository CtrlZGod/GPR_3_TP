"""Tests for basic port/zone filtering rules."""

import pytest
from helpers import tcp_connect, ping, start_tcp_listener, start_udp_listener, udp_send


# =============================================
#  WAN -> DMZ (allowed services only)
# =============================================

class TestWanToDmz:
    """WAN should reach DMZ on public service ports only."""

    @pytest.fixture(autouse=True)
    def _listeners(self):
        procs = [
            start_tcp_listener("ns-dmz", 80),
            start_tcp_listener("ns-dmz", 443),
            start_tcp_listener("ns-dmz", 22),
            start_udp_listener("ns-dmz", 53),
        ]
        yield
        for p in procs:
            p.terminate()
            p.wait()

    def test_wan_to_dmz_http(self):
        """WAN can reach DMZ HTTP (port 80) via DNAT."""
        assert tcp_connect("ns-wan", "10.0.1.1", 80)

    def test_wan_to_dmz_https(self):
        """WAN can reach DMZ HTTPS (port 443) via DNAT."""
        assert tcp_connect("ns-wan", "10.0.1.1", 443)

    def test_wan_to_dmz_dns_udp(self):
        """WAN can reach DMZ DNS (UDP 53) via DNAT."""
        assert udp_send("ns-wan", "10.0.1.1", 53)

    def test_wan_to_dmz_ssh_blocked(self):
        """WAN cannot reach DMZ SSH (port 22) — not in allowed set."""
        assert not tcp_connect("ns-wan", "10.0.3.10", 22, timeout=2)

    def test_wan_to_dmz_random_port_blocked(self):
        """WAN cannot reach DMZ on arbitrary port (e.g., 8080)."""
        assert not tcp_connect("ns-wan", "10.0.3.10", 8080, timeout=2)


# =============================================
#  WAN -> LAN (always blocked)
# =============================================

class TestWanToLan:
    """WAN must never reach the internal LAN — critical security boundary."""

    @pytest.fixture(autouse=True)
    def _listeners(self):
        procs = [
            start_tcp_listener("ns-lan", 80),
            start_tcp_listener("ns-lan", 22),
        ]
        yield
        for p in procs:
            p.terminate()
            p.wait()

    def test_wan_to_lan_http_blocked(self):
        """WAN cannot reach LAN on port 80."""
        assert not tcp_connect("ns-wan", "10.0.2.10", 80, timeout=2)

    def test_wan_to_lan_ssh_blocked(self):
        """WAN cannot reach LAN on port 22."""
        assert not tcp_connect("ns-wan", "10.0.2.10", 22, timeout=2)

    def test_wan_to_lan_ping_blocked(self):
        """WAN cannot ping LAN hosts (ICMP is allowed between zones,
        but forwarding WAN->LAN should be dropped before ICMP rule)."""
        # The forward chain drops WAN->LAN before reaching the ICMP accept rule
        assert not ping("ns-wan", "10.0.2.10", timeout=2)


# =============================================
#  LAN -> WAN (internet access)
# =============================================

class TestLanToWan:
    """LAN users should be able to access internet services."""

    @pytest.fixture(autouse=True)
    def _listeners(self):
        procs = [
            start_tcp_listener("ns-wan", 80),
            start_tcp_listener("ns-wan", 443),
            start_tcp_listener("ns-wan", 22),
            start_udp_listener("ns-wan", 53),
        ]
        yield
        for p in procs:
            p.terminate()
            p.wait()

    def test_lan_to_wan_http(self):
        """LAN can access WAN HTTP (port 80)."""
        assert tcp_connect("ns-lan", "10.0.1.10", 80)

    def test_lan_to_wan_https(self):
        """LAN can access WAN HTTPS (port 443)."""
        assert tcp_connect("ns-lan", "10.0.1.10", 443)

    def test_lan_to_wan_dns_udp(self):
        """LAN can access WAN DNS (UDP 53)."""
        assert udp_send("ns-lan", "10.0.1.10", 53)

    def test_lan_to_wan_ssh_blocked(self):
        """LAN cannot SSH to WAN — only HTTP/HTTPS/DNS allowed."""
        assert not tcp_connect("ns-lan", "10.0.1.10", 22, timeout=2)


# =============================================
#  LAN -> DMZ (admin access)
# =============================================

class TestLanToDmz:
    """LAN admins should access DMZ services plus SSH for management."""

    @pytest.fixture(autouse=True)
    def _listeners(self):
        procs = [
            start_tcp_listener("ns-dmz", 80),
            start_tcp_listener("ns-dmz", 443),
            start_tcp_listener("ns-dmz", 22),
            start_udp_listener("ns-dmz", 53),
        ]
        yield
        for p in procs:
            p.terminate()
            p.wait()

    def test_lan_to_dmz_http(self):
        """LAN can reach DMZ HTTP (port 80)."""
        assert tcp_connect("ns-lan", "10.0.3.10", 80)

    def test_lan_to_dmz_https(self):
        """LAN can reach DMZ HTTPS (port 443)."""
        assert tcp_connect("ns-lan", "10.0.3.10", 443)

    def test_lan_to_dmz_ssh(self):
        """LAN can SSH to DMZ servers (admin access)."""
        assert tcp_connect("ns-lan", "10.0.3.10", 22)

    def test_lan_to_dmz_dns(self):
        """LAN can query DMZ DNS (UDP 53)."""
        assert udp_send("ns-lan", "10.0.3.10", 53)

    def test_lan_to_dmz_random_port_blocked(self):
        """LAN cannot reach DMZ on arbitrary ports."""
        assert not tcp_connect("ns-lan", "10.0.3.10", 3306, timeout=2)


# =============================================
#  DMZ -> LAN (always blocked — DMZ isolation)
# =============================================

class TestDmzToLan:
    """A compromised DMZ server must NOT be able to reach the internal LAN."""

    @pytest.fixture(autouse=True)
    def _listeners(self):
        procs = [
            start_tcp_listener("ns-lan", 80),
            start_tcp_listener("ns-lan", 22),
        ]
        yield
        for p in procs:
            p.terminate()
            p.wait()

    def test_dmz_to_lan_http_blocked(self):
        """DMZ cannot reach LAN HTTP."""
        assert not tcp_connect("ns-dmz", "10.0.2.10", 80, timeout=2)

    def test_dmz_to_lan_ssh_blocked(self):
        """DMZ cannot reach LAN SSH."""
        assert not tcp_connect("ns-dmz", "10.0.2.10", 22, timeout=2)

    def test_dmz_to_lan_ping_blocked(self):
        """DMZ cannot ping LAN (dropped before ICMP rule)."""
        assert not ping("ns-dmz", "10.0.2.10", timeout=2)


# =============================================
#  DMZ -> WAN (limited internet access)
# =============================================

class TestDmzToWan:
    """DMZ servers need limited internet access for updates."""

    @pytest.fixture(autouse=True)
    def _listeners(self):
        procs = [
            start_tcp_listener("ns-wan", 80),
            start_tcp_listener("ns-wan", 443),
            start_tcp_listener("ns-wan", 22),
            start_udp_listener("ns-wan", 53),
        ]
        yield
        for p in procs:
            p.terminate()
            p.wait()

    def test_dmz_to_wan_http(self):
        """DMZ can reach WAN HTTP for updates."""
        assert tcp_connect("ns-dmz", "10.0.1.10", 80)

    def test_dmz_to_wan_https(self):
        """DMZ can reach WAN HTTPS for updates."""
        assert tcp_connect("ns-dmz", "10.0.1.10", 443)

    def test_dmz_to_wan_dns(self):
        """DMZ can query WAN DNS."""
        assert udp_send("ns-dmz", "10.0.1.10", 53)

    def test_dmz_to_wan_ssh_blocked(self):
        """DMZ cannot SSH to WAN."""
        assert not tcp_connect("ns-dmz", "10.0.1.10", 22, timeout=2)
