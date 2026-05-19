import subprocess
import os
import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def topology():
    """Set up the entire network topology before tests, tear down after."""
    setup_script = os.path.join(PROJECT_DIR, "setup.sh")
    teardown_script = os.path.join(PROJECT_DIR, "teardown.sh")

    result = subprocess.run(
        ["bash", setup_script], capture_output=True, text=True
    )
    if result.returncode != 0:
        pytest.exit(f"Setup failed:\n{result.stderr}\n{result.stdout}")

    yield

    subprocess.run(["bash", teardown_script], capture_output=True, text=True)
