.PHONY: all setup test teardown clean report check

all: setup test teardown

setup:
	sudo bash setup.sh

test:
	sudo python3 -m pytest tests/ -v --tb=short

teardown:
	sudo bash teardown.sh

report:
	sudo python3 -m pytest tests/ -v --tb=short --html=report.html --self-contained-html
	@echo ""
	@echo "Report saved to report.html"

clean: teardown
	rm -f report.html

check:
	@echo "=== Checking prerequisites ==="
	@which nft >/dev/null 2>&1 && echo "[OK] nft found" || echo "[MISSING] nft (install nftables)"
	@which python3 >/dev/null 2>&1 && echo "[OK] python3 found" || echo "[MISSING] python3"
	@python3 -c "import pytest" 2>/dev/null && echo "[OK] pytest installed" || echo "[MISSING] pytest (pip install -r requirements.txt)"
	@ip netns list >/dev/null 2>&1 && echo "[OK] ip netns available" || echo "[MISSING] iproute2"
	@echo ""
	@echo "Run with: make all"
