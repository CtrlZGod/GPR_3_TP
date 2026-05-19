#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NFT_DIR="$SCRIPT_DIR/../nftables"

echo "Flushing existing rules in ns-fw..."
ip netns exec ns-fw nft flush ruleset

echo "Applying firewall rules..."
ip netns exec ns-fw nft -f "$NFT_DIR/firewall.nft"

echo "Applying NAT rules..."
ip netns exec ns-fw nft -f "$NFT_DIR/nat.nft"

echo "Done. Current ruleset:"
ip netns exec ns-fw nft list ruleset
