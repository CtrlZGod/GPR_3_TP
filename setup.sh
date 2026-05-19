#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Clean up any previous topology first
echo "=== Cleaning previous topology (if any) ==="
bash "$SCRIPT_DIR/teardown.sh" 2>/dev/null || true

echo "=== Creating network topology ==="

# Create namespaces
for ns in ns-wan ns-lan ns-lan2 ns-dmz ns-fw; do
    ip netns add "$ns"
    echo "  [+] Namespace $ns"
done

# Enable IP forwarding in firewall namespace
ip netns exec ns-fw sysctl -q -w net.ipv4.ip_forward=1

# Create veth pairs
ip link add veth-wan  type veth peer name veth-fw-wan
ip link add veth-lan  type veth peer name veth-fw-lan
ip link add veth-lan2 type veth peer name veth-fw-lan2
ip link add veth-dmz  type veth peer name veth-fw-dmz
echo "  [+] veth pairs created"

# Move endpoints into namespaces
ip link set veth-wan   netns ns-wan
ip link set veth-lan   netns ns-lan
ip link set veth-lan2  netns ns-lan2
ip link set veth-dmz   netns ns-dmz
ip link set veth-fw-wan  netns ns-fw
ip link set veth-fw-lan  netns ns-fw
ip link set veth-fw-lan2 netns ns-fw
ip link set veth-fw-dmz  netns ns-fw
echo "  [+] Interfaces moved to namespaces"

# Create LAN bridge inside firewall namespace
ip netns exec ns-fw ip link add br-lan type bridge
ip netns exec ns-fw ip link set veth-fw-lan  master br-lan
ip netns exec ns-fw ip link set veth-fw-lan2 master br-lan
echo "  [+] LAN bridge created"

# Assign IP addresses
ip netns exec ns-wan  ip addr add 10.0.1.10/24 dev veth-wan
ip netns exec ns-lan  ip addr add 10.0.2.10/24 dev veth-lan
ip netns exec ns-lan2 ip addr add 10.0.2.20/24 dev veth-lan2
ip netns exec ns-dmz  ip addr add 10.0.3.10/24 dev veth-dmz
ip netns exec ns-fw   ip addr add 10.0.1.1/24  dev veth-fw-wan
ip netns exec ns-fw   ip addr add 10.0.2.1/24  dev br-lan
ip netns exec ns-fw   ip addr add 10.0.3.1/24  dev veth-fw-dmz
echo "  [+] IP addresses assigned"

# Bring up all interfaces
for ns in ns-wan ns-lan ns-lan2 ns-dmz ns-fw; do
    ip netns exec "$ns" ip link set lo up
done

ip netns exec ns-wan  ip link set veth-wan up
ip netns exec ns-lan  ip link set veth-lan up
ip netns exec ns-lan2 ip link set veth-lan2 up
ip netns exec ns-dmz  ip link set veth-dmz up
ip netns exec ns-fw   ip link set veth-fw-wan up
ip netns exec ns-fw   ip link set veth-fw-lan up
ip netns exec ns-fw   ip link set veth-fw-lan2 up
ip netns exec ns-fw   ip link set veth-fw-dmz up
ip netns exec ns-fw   ip link set br-lan up
echo "  [+] All interfaces up"

# Set default routes in endpoint namespaces
ip netns exec ns-wan  ip route add default via 10.0.1.1
ip netns exec ns-lan  ip route add default via 10.0.2.1
ip netns exec ns-lan2 ip route add default via 10.0.2.1
ip netns exec ns-dmz  ip route add default via 10.0.3.1
echo "  [+] Routes configured"

# Apply nftables rules
ip netns exec ns-fw nft -f "$SCRIPT_DIR/nftables/firewall.nft"
ip netns exec ns-fw nft -f "$SCRIPT_DIR/nftables/nat.nft"
echo "  [+] nftables rules applied"

echo ""
echo "=== Topology ready ==="
echo ""
echo "  EXTERNAL (ns-wan)  10.0.1.10"
echo "       |"
echo "       | 10.0.1.1"
echo "  FIREWALL (ns-fw)"
echo "       | 10.0.2.1         | 10.0.3.1"
echo "       |                  |"
echo "  LAN (br-lan)        DMZ (ns-dmz) 10.0.3.10"
echo "   |        |"
echo "  ns-lan   ns-lan2"
echo "  10.0.2.10 10.0.2.20"
