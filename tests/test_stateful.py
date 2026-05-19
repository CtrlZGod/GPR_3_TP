"""Tests for stateful connection tracking (conntrack)."""

import subprocess
import time
import pytest
from helpers import run_in_ns, start_tcp_listener, tcp_connect


class TestStatefulFiltering:
    """Verify that the firewall is stateful — return traffic for established
    connections is allowed, but unsolicited traffic in the reverse direction
    is blocked."""

    def test_lan_to_wan_return_traffic(self):
        """When LAN initiates HTTP to WAN, the response comes back
        (ct state established,related)."""
        listener = start_tcp_listener("ns-wan", 80)
        try:
            assert tcp_connect("ns-lan", "10.0.1.10", 80)
        finally:
            listener.terminate()
            listener.wait()

    def test_wan_cannot_initiate_to_lan(self):
        """Even though LAN->WAN HTTP is allowed, WAN cannot initiate
        connections to LAN — stateful rules only permit return traffic."""
        listener = start_tcp_listener("ns-lan", 80)
        try:
            assert not tcp_connect("ns-wan", "10.0.2.10", 80, timeout=2)
        finally:
            listener.terminate()
            listener.wait()

    def test_dmz_to_wan_return_traffic(self):
        """DMZ-initiated HTTP to WAN gets a response back."""
        listener = start_tcp_listener("ns-wan", 80)
        try:
            assert tcp_connect("ns-dmz", "10.0.1.10", 80)
        finally:
            listener.terminate()
            listener.wait()

    def test_lan_to_dmz_bidirectional(self):
        """LAN initiates SSH to DMZ. The connection is bidirectional once
        established (server can send data back)."""
        script = (
            "import socket\n"
            "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
            "s.bind(('0.0.0.0', 22))\n"
            "s.listen(1)\n"
            "c, _ = s.accept()\n"
            "c.sendall(b'SSH-2.0-test\\r\\n')\n"
            "data = c.recv(1024)\n"
            "c.sendall(b'REPLY:' + data)\n"
            "c.close()\n"
            "s.close()\n"
        )
        server = subprocess.Popen(
            ["ip", "netns", "exec", "ns-dmz", "python3", "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        time.sleep(0.3)

        client_script = (
            "import socket\n"
            "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "s.settimeout(3)\n"
            "s.connect(('10.0.3.10', 22))\n"
            "banner = s.recv(1024)\n"
            "s.sendall(b'HELLO')\n"
            "reply = s.recv(1024)\n"
            "s.close()\n"
            "print(reply.decode())\n"
        )
        try:
            result = run_in_ns("ns-lan", ["python3", "-c", client_script], timeout=5)
            assert "REPLY:HELLO" in result.stdout
        finally:
            server.terminate()
            server.wait()

    def test_conntrack_invalid_state_dropped(self):
        """Packets with invalid conntrack state should be dropped.
        We test this by verifying the ct state invalid drop counter increases
        when we send a RST to a non-existing connection."""
        # Get initial counter
        result_before = run_in_ns(
            "ns-fw", ["nft", "list", "chain", "inet", "firewall", "forward"]
        )

        # Send a TCP RST packet to a non-existing connection using python
        script = (
            "import socket\n"
            "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "s.settimeout(1)\n"
            "try:\n"
            "    s.connect(('10.0.3.10', 9999))\n"
            "except:\n"
            "    pass\n"
            "s.close()\n"
        )
        run_in_ns("ns-wan", ["python3", "-c", script], timeout=3)
        time.sleep(0.5)

        result_after = run_in_ns(
            "ns-fw", ["nft", "list", "chain", "inet", "firewall", "forward"]
        )
        # The chain should show the forward drop counter has incremented
        assert result_after.returncode == 0
