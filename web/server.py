#!/usr/bin/env python3
"""Firewall Test Dashboard — HTTP API + UI for running tests in the browser."""

import ast
import os
import re
import sys
import json
import subprocess
from datetime import datetime
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

# Use the SAME interpreter the server is running with — otherwise sudo
# falls back to /usr/bin/python3 which doesn't have pytest installed.
PY = sys.executable

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


def _extract_docstrings(filepath):
    """Parse a Python file with ast and return {func_name: first_line_of_docstring}."""
    docs = {}
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read(), filename=filepath)
    except Exception:
        return docs

    for node in ast.walk(tree):
        # Top-level functions: tests/test_foo.py::test_bar
        if isinstance(node, ast.FunctionDef):
            ds = ast.get_docstring(node)
            if ds:
                docs[node.name] = ds.strip().split("\n")[0]
        # Methods inside classes: tests/test_foo.py::TestClass::test_bar
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    ds = ast.get_docstring(item)
                    if ds:
                        docs[f"{node.name}::{item.name}"] = ds.strip().split("\n")[0]
    return docs


@app.route("/api/tests")
def list_tests():
    """Collect tests via pytest and extract docstrings via ast."""
    result = subprocess.run(
        [PY, "-m", "pytest", "tests/", "--collect-only", "-q", "--no-header"],
        capture_output=True, text=True, cwd=PROJECT_DIR,
    )

    # Cache of docstrings per file
    docstring_cache = {}

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

        # Extract docstrings from this file (once per file)
        if file_ not in docstring_cache:
            full_path = os.path.join(PROJECT_DIR, file_)
            docstring_cache[file_] = _extract_docstrings(full_path)
        file_docs = docstring_cache[file_]

        # Look up: first try "Class::method", then just "method"
        desc = ""
        if cls != "_module":
            desc = file_docs.get(f"{cls}::{test_name}", "")
        if not desc:
            desc = file_docs.get(test_name, "")

        organized.setdefault(file_, {}).setdefault(cls, []).append({
            "name": test_name, "id": line, "desc": desc,
        })

    if not organized:
        return jsonify({
            "_error": {
                "message": "Test collection failed",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "python": PY,
            }
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
        PY, "-m", "pytest", "-v", "--tb=short",
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


_RESULT_RE = re.compile(
    r'^(tests/\S+(?:::\S+)+)\s+(PASSED|FAILED|SKIPPED|ERROR|XPASS|XFAIL)\b'
)


def _sse(payload):
    return f"data: {json.dumps(payload)}\n\n"


@app.route("/api/run-stream", methods=["POST"])
def run_tests_stream():
    """Run tests and stream progress as Server-Sent Events.
    Each test result is emitted as it happens, plus a final 'done' event
    with the full JSON report."""
    data = request.get_json() or {}
    test_ids = data.get("tests", [])
    if not test_ids:
        return jsonify({"error": "No tests selected"}), 400

    def generate():
        if os.path.exists(JSON_REPORT):
            os.remove(JSON_REPORT)

        cmd = [
            PY, "-u", "-m", "pytest", "-v", "--tb=short", "--color=no",
            "--no-header",
            "--json-report", f"--json-report-file={JSON_REPORT}",
        ] + test_ids

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=PROJECT_DIR, bufsize=1, text=True, env=env,
        )

        total = len(test_ids)
        completed = 0

        yield _sse({"type": "start", "total": total})

        try:
            for line in proc.stdout:
                line = line.rstrip("\n")
                m = _RESULT_RE.match(line)
                if m:
                    test_id = m.group(1)
                    outcome = m.group(2).lower()
                    completed += 1
                    yield _sse({
                        "type": "result",
                        "test_id": test_id,
                        "outcome": outcome,
                        "completed": completed,
                        "total": total,
                    })
                else:
                    yield _sse({"type": "output", "line": line})
        finally:
            proc.wait()

        report = None
        if os.path.exists(JSON_REPORT):
            try:
                with open(JSON_REPORT) as f:
                    report = json.load(f)
            except Exception as e:
                report = {"error": str(e)}

        yield _sse({
            "type": "done",
            "returncode": proc.returncode,
            "report": report,
        })

    response = Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response


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


@app.route("/api/benchmark", methods=["POST"])
def benchmark():
    """Run ping benchmarks between zone pairs and return individual RTTs."""
    pairs = [
        {"label": "LAN → Firewall",   "ns": "ns-lan", "target": "10.0.2.1",  "hops": "direto"},
        {"label": "LAN → WAN",        "ns": "ns-lan", "target": "10.0.1.10", "hops": "via FW + masquerade"},
        {"label": "LAN → DMZ",        "ns": "ns-lan", "target": "10.0.3.10", "hops": "via FW"},
        {"label": "WAN → DMZ (DNAT)", "ns": "ns-wan", "target": "10.0.1.1",  "hops": "via FW + DNAT"},
        {"label": "DMZ → WAN",        "ns": "ns-dmz", "target": "10.0.1.10", "hops": "via FW + masquerade"},
    ]
    results = []
    for pair in pairs:
        r = subprocess.run(
            ["ip", "netns", "exec", pair["ns"],
             "ping", "-c", "50", "-i", "0.02", pair["target"]],
            capture_output=True, text=True, timeout=30,
        )
        rtts = []
        for line in r.stdout.splitlines():
            m = re.search(r"time[=<]([\d.]+)", line)
            if m:
                rtts.append(float(m.group(1)))

        stats = {
            "label": pair["label"],
            "hops": pair["hops"],
            "rtts": rtts,
            "count": len(rtts),
        }
        if rtts:
            stats["min"] = round(min(rtts), 3)
            stats["avg"] = round(sum(rtts) / len(rtts), 3)
            stats["max"] = round(max(rtts), 3)
        results.append(stats)

    return jsonify(results)


@app.route("/api/export-pdf")
def export_pdf():
    """Generate a PDF test report from the last test run."""
    try:
        from fpdf import FPDF
    except ImportError:
        return jsonify({"error": "fpdf2 not installed. Run: pip install fpdf2"}), 500

    if not os.path.exists(JSON_REPORT):
        return jsonify({"error": "No test results. Run tests first."}), 400

    with open(JSON_REPORT) as f:
        report = json.load(f)

    tests = report.get("tests", [])
    if not tests:
        return jsonify({"error": "No test results in report."}), 400

    s = report.get("summary", {})
    passed = [t for t in tests if t["outcome"] == "passed"]
    failed = [t for t in tests if t["outcome"] != "passed"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # --- Title ---
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 14, "Firewall Test Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 7, f"Tema 18 - Firewall por Regras + Testes Automatizados", ln=True, align="C")
    pdf.cell(0, 7, f"Generated: {now}", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # --- Summary box ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "  Summary", ln=True, fill=True)
    pdf.set_font("Helvetica", "", 11)
    total = s.get("total", len(tests))
    dur = report.get("duration", 0)
    pdf.cell(47, 8, f"Total: {total}", border=1, align="C")
    pdf.set_text_color(40, 160, 40)
    pdf.cell(47, 8, f"Passed: {s.get('passed', len(passed))}", border=1, align="C")
    pdf.set_text_color(220, 50, 50)
    pdf.cell(47, 8, f"Failed: {s.get('failed', len(failed))}", border=1, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.cell(47, 8, f"Duration: {dur:.1f}s", border=1, align="C", ln=True)
    pdf.ln(8)

    # --- Failed tests ---
    if failed:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(220, 50, 50)
        pdf.cell(0, 10, f"Failed ({len(failed)})", ln=True)
        pdf.set_text_color(60, 60, 60)
        pdf.set_font("Helvetica", "", 9)
        for t in failed:
            parts = t["nodeid"].split("::")
            name = parts[-1]
            cls = parts[-2] if len(parts) >= 3 else ""
            pdf.cell(0, 5, f"  FAIL   {cls}::{name}", ln=True)
            longrepr = ""
            if isinstance(t.get("call"), dict):
                longrepr = t["call"].get("longrepr", "")
            elif isinstance(t.get("longrepr"), str):
                longrepr = t["longrepr"]
            if longrepr:
                pdf.set_font("Courier", "", 7)
                for lr_line in str(longrepr).splitlines()[:6]:
                    pdf.cell(0, 4, f"         {lr_line[:100]}", ln=True)
                pdf.set_font("Helvetica", "", 9)
        pdf.ln(4)

    # --- Passed tests ---
    if passed:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(40, 160, 40)
        pdf.cell(0, 10, f"Passed ({len(passed)})", ln=True)
        pdf.set_text_color(60, 60, 60)
        pdf.set_font("Helvetica", "", 9)
        for t in passed:
            parts = t["nodeid"].split("::")
            name = parts[-1]
            cls = parts[-2] if len(parts) >= 3 else ""
            dur_t = t.get("duration", 0)
            pdf.cell(0, 5, f"  PASS   {cls}::{name}  ({dur_t:.2f}s)", ln=True)

    # --- Footer ---
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "Generated by Firewall Test Dashboard", ln=True, align="C")

    content = pdf.output()
    return Response(
        content,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="firewall-report-{datetime.now():%Y%m%d-%H%M}.pdf"',
        },
    )


if __name__ == "__main__":
    print("=" * 60)
    print(" Firewall Test Dashboard")
    print(" Open: http://localhost:8080")
    print(" (or http://<raspberry-ip>:8080 from another machine)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8080, debug=False)
