import subprocess
import os
import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMESPACES = ["ns-wan", "ns-lan", "ns-lan2", "ns-dmz", "ns-fw"]


def _topology_up():
    """Return True if all required namespaces exist."""
    r = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True)
    return all(ns in r.stdout for ns in NAMESPACES)


@pytest.fixture(scope="session", autouse=True)
def topology():
    """Set up the topology before tests, tear down after — but only if
    we were the ones to set it up. If topology is already running (e.g.,
    brought up by the web dashboard), leave it alone."""
    setup_script = os.path.join(PROJECT_DIR, "setup.sh")
    teardown_script = os.path.join(PROJECT_DIR, "teardown.sh")

    we_set_it_up = False
    if not _topology_up():
        result = subprocess.run(
            ["bash", setup_script], capture_output=True, text=True
        )
        if result.returncode != 0:
            pytest.exit(f"Setup failed:\n{result.stderr}\n{result.stdout}")
        we_set_it_up = True

    yield

    if we_set_it_up:
        subprocess.run(
            ["bash", teardown_script], capture_output=True, text=True
        )
