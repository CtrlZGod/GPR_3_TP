#!/usr/bin/env bash
set -uo pipefail

echo "=== Tearing down network topology ==="

# Delete namespaces (this also removes any veth inside them)
for ns in ns-wan ns-lan ns-lan2 ns-dmz ns-fw; do
    if ip netns list | grep -qw "$ns"; then
        ip netns del "$ns"
        echo "  [-] Deleted namespace $ns"
    fi
done

# Delete any dangling veth interfaces in the host namespace
# (left behind if a previous setup failed mid-way)
for veth in veth-wan veth-lan veth-lan2 veth-dmz \
            veth-fw-wan veth-fw-lan veth-fw-lan2 veth-fw-dmz; do
    if ip link show "$veth" >/dev/null 2>&1; then
        ip link delete "$veth"
        echo "  [-] Deleted dangling veth $veth"
    fi
done

echo "=== Topology cleaned up ==="
