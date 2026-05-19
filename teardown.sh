#!/usr/bin/env bash
set -euo pipefail

echo "=== Tearing down network topology ==="

for ns in ns-wan ns-lan ns-lan2 ns-dmz ns-fw; do
    if ip netns list | grep -qw "$ns"; then
        ip netns del "$ns"
        echo "  [-] Deleted $ns"
    fi
done

echo "=== Topology cleaned up ==="
