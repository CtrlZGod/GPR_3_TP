#!/usr/bin/env bash
set -euo pipefail

echo "=== nftables ruleset in ns-fw ==="
echo ""
ip netns exec ns-fw nft list ruleset
