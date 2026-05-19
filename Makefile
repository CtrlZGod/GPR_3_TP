ifdef VIRTUAL_ENV
    PYTHON := $(VIRTUAL_ENV)/bin/python3
else
    PYTHON := $(shell which python3)
endif

.PHONY: all setup test teardown clean report check

all: setup test teardown

setup:
	sudo bash setup.sh

test:
	sudo $(PYTHON) -m pytest tests/ -v --tb=short

teardown:
	sudo bash teardown.sh

report:
	sudo $(PYTHON) -m pytest tests/ -v --tb=short --html=report.html --self-contained-html
	@echo ""
	@echo "Report saved to report.html"

clean: teardown
	rm -f report.html

check:
	@echo "=== Checking prerequisites ==="
	@which nft >/dev/null 2>&1 && echo "[OK] nft found" || echo "[MISSING] nft (install nftables)"
	@echo "[INFO] Python: $(PYTHON)"
	@$(PYTHON) -c "import pytest" 2>/dev/null && echo "[OK] pytest installed" || echo "[MISSING] pytest (pip install -r requirements.txt)"
	@ip netns list >/dev/null 2>&1 && echo "[OK] ip netns available" || echo "[MISSING] iproute2"
	@echo ""
	@echo "Run with: make all"
