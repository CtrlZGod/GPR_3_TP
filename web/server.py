#!/usr/bin/env python3
"""Firewall Test Dashboard — HTTP API + UI for running tests in the browser."""

import os
import json
import subprocess
from flask import Flask, jsonify, request, send_from_directory

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(WEB_DIR)
TESTS_DIR = os.path.join(PROJECT_DIR, "tests")
SETUP_SCRIPT = os.path.join(PROJECT_DIR, "setup.sh")
TEARDOWN_SCRIPT = os.path.join(PROJECT_DIR, "teardown.sh")
JSON_REPORT = "/tmp/firewall-test-report.json"

NAMESPACES = ["ns-wan", "ns-lan", "ns-lan2", "ns-dmz", "ns-fw"]

app = Flask(__name__, static_folder=WEB_DIR)


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/api/status")
def status():
    result = subprocess.run(
        ["ip", "netns", "list"], capture_output=True, text=True
    )
    present = [ns for ns in NAMESPACES if ns in result.stdout]
    return jsonify({
        "up": len(present) == len(NAMESPACES),
        "namespaces": present,
        "expected": NAMESPACES,
    })


@app.route("/api/setup", methods=["POST"])
def setup():
    result = subprocess.run(
        ["bash", SETUP_SCRIPT],
        capture_output=True, text=True, timeout=30,
        cwd=PROJECT_DIR,
    )
    return jsonify({
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    })


@app.route("/api/teardown", methods=["POST"])
def teardown():
    result = subprocess.run(
        ["bash", TEARDOWN_SCRIPT],
        capture_output=True, text=True, timeout=15,
        cwd=PROJECT_DIR,
    )
    return jsonify({
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    })


@app.route("/api/tests")
def list_tests():
    result = subprocess.run(
        ["python3", "-m", "pytest", "tests/", "--collect-only", "-q",
         "--no-header"],
        capture_output=True, text=True, cwd=PROJECT_DIR,
    )
    organized = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if "::" not in line or line.startswith("="):
            continue
        parts = line.split("::")
        file_ = parts[0]
        if len(parts) == 3:
            cls, test_name = parts[1], parts[2]
        else:
            cls, test_name = "_module", parts[1]
        organized.setdefault(file_, {}).setdefault(cls, []).append({
            "name": test_name, "id": line,
        })
    return jsonify(organized)


@app.route("/api/run", methods=["POST"])
def run_tests():
    data = request.get_json() or {}
    test_ids = data.get("tests", [])
    if not test_ids:
        return jsonify({"error": "No tests selected"}), 400

    if os.path.exists(JSON_REPORT):
        os.remove(JSON_REPORT)

    cmd = [
        "python3", "-m", "pytest", "-v", "--tb=short",
        "--json-report", f"--json-report-file={JSON_REPORT}",
        "--no-header",
    ] + test_ids

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=PROJECT_DIR, timeout=600,
    )

    report = None
    if os.path.exists(JSON_REPORT):
        try:
            with open(JSON_REPORT) as f:
                report = json.load(f)
        except Exception as e:
            report = {"error": f"Failed to read report: {e}"}

    return jsonify({
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "report": report,
    })


@app.route("/api/rules")
def rules():
    result = subprocess.run(
        ["ip", "netns", "exec", "ns-fw", "nft", "list", "ruleset"],
        capture_output=True, text=True,
    )
    return jsonify({
        "ruleset": result.stdout,
        "error": result.stderr if result.returncode != 0 else None,
    })


@app.route("/api/counters")
def counters():
    """Return counter values from all chains in the firewall table."""
    out = {}
    for chain in ["input", "forward"]:
        r = subprocess.run(
            ["ip", "netns", "exec", "ns-fw", "nft", "list", "chain",
             "inet", "firewall", chain],
            capture_output=True, text=True,
        )
        out[chain] = r.stdout
    return jsonify(out)


if __name__ == "__main__":
    print("=" * 60)
    print(" Firewall Test Dashboard")
    print(" Open: http://localhost:8080")
    print(" (or http://<raspberry-ip>:8080 from another machine)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8080, debug=False)
