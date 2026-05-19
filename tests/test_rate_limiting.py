"""Tests for rate limiting rules."""

import time
import pytest
from helpers import ping, run_in_ns


class TestICMPRateLimit:
    """ICMP to the firewall itself is rate-limited to 5/second."""

    def test_single_ping_allowed(self):
        """A single ping to the firewall succeeds."""
        assert ping("ns-lan", "10.0.2.1", count=1)

    def test_moderate_ping_allowed(self):
        """A few pings at normal rate succeed."""
        assert ping("ns-lan", "10.0.2.1", count=3, timeout=5)

    def test_ping_flood_partially_dropped(self):
        """A flood of pings should have some dropped due to rate limiting.
        Rule is `limit rate 5/second` (default burst 5) so out of 50 pings
        sent in under a second, most should be dropped."""
        result = run_in_ns(
            "ns-lan",
            ["ping", "-c", "50", "-i", "0.01", "-W", "1", "10.0.2.1"],
            timeout=15,
        )
        # Parse "N packets transmitted, M received" line
        transmitted = received = None
        for line in result.stdout.splitlines():
            if "transmitted" in line and "received" in line:
                parts = [p.strip() for p in line.split(",")]
                for p in parts:
                    if "transmitted" in p:
                        transmitted = int(p.split()[0])
                    elif "received" in p:
                        received = int(p.split()[0])
                break

        assert transmitted is not None, (
            f"Could not parse ping output:\n{result.stdout}"
        )
        assert received < transmitted, (
            f"Expected some packets to be dropped by rate limiter, "
            f"but {received}/{transmitted} got through. "
            f"Rule may not be applying limit correctly."
        )


class TestICMPBetweenZones:
    """ICMP between zones (through forward chain) should work without
    rate limiting — rate limit only applies to traffic TO the firewall."""

    def test_lan_to_dmz_ping(self):
        """LAN can ping DMZ."""
        assert ping("ns-lan", "10.0.3.10")

    def test_dmz_to_wan_ping(self):
        """DMZ can ping WAN."""
        assert ping("ns-dmz", "10.0.1.10")

    def test_lan_to_wan_ping(self):
        """LAN can ping WAN."""
        assert ping("ns-lan", "10.0.1.10")
