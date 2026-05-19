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
        We send 20 pings as fast as possible and expect some loss."""
        result = run_in_ns(
            "ns-lan",
            ["ping", "-c", "20", "-i", "0.05", "-W", "1", "10.0.2.1"],
            timeout=10,
        )
        output = result.stdout
        # Parse packet loss percentage
        for line in output.splitlines():
            if "packet loss" in line:
                # Extract percentage, e.g., "60% packet loss"
                parts = line.split(",")
                for part in parts:
                    if "packet loss" in part:
                        pct = part.strip().split("%")[0].strip()
                        # Remove any leading text before the number
                        pct = "".join(c for c in pct if c.isdigit() or c == ".")
                        loss = float(pct)
                        assert loss > 0, (
                            "Expected some packet loss from rate limiting, "
                            "but all pings succeeded"
                        )
                        return

        # If we couldn't parse loss but some pings failed, that's also valid
        if result.returncode != 0:
            return
        pytest.fail("Could not parse ping output for packet loss")


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
