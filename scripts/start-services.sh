#!/usr/bin/env bash
set -euo pipefail

echo "Starting dummy services..."

# DMZ: HTTP server (port 80)
ip netns exec ns-dmz bash -c '
    while true; do
        echo -e "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK" | nc -l -p 80 -q 1 2>/dev/null || true
    done &
'
echo "  [+] DMZ HTTP server on port 80"

# DMZ: HTTPS server (port 443)
ip netns exec ns-dmz bash -c '
    while true; do
        echo -e "HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK" | nc -l -p 443 -q 1 2>/dev/null || true
    done &
'
echo "  [+] DMZ HTTPS server on port 443"

# DMZ: DNS server (UDP port 53)
ip netns exec ns-dmz bash -c '
    while true; do
        echo "DNS-REPLY" | nc -l -u -p 53 -q 1 2>/dev/null || true
    done &
'
echo "  [+] DMZ DNS server on port 53 (UDP)"

# WAN: HTTP server (port 80) - simulates internet
ip netns exec ns-wan bash -c '
    while true; do
        echo -e "HTTP/1.1 200 OK\r\nContent-Length: 8\r\n\r\nINTERNET" | nc -l -p 80 -q 1 2>/dev/null || true
    done &
'
echo "  [+] WAN HTTP server on port 80"

echo ""
echo "Services running. Use 'scripts/stop-services.sh' or teardown.sh to stop."
