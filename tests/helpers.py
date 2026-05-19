import subprocess
import time


def run_in_ns(ns, cmd, timeout=5):
    """Execute a command inside a network namespace."""
    full_cmd = ["ip", "netns", "exec", ns] + cmd
    return subprocess.run(
        full_cmd, capture_output=True, text=True, timeout=timeout
    )


def ping(ns, target, count=1, timeout=3):
    """Ping from a namespace. Returns True if at least one reply."""
    result = run_in_ns(
        ns,
        ["ping", "-c", str(count), "-W", str(timeout), target],
        timeout=timeout + 2,
    )
    return result.returncode == 0


def tcp_connect(ns, host, port, timeout=3):
    """Try a TCP connection from a namespace. Returns True if successful."""
    script = (
        f"import socket; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); "
        f"s.settimeout({timeout}); "
        f"s.connect(('{host}', {port})); s.close(); print('OK')"
    )
    try:
        result = run_in_ns(ns, ["python3", "-c", script], timeout=timeout + 2)
        return "OK" in result.stdout
    except subprocess.TimeoutExpired:
        return False


def udp_send(ns, host, port, message="test", timeout=3):
    """Send a UDP packet and try to get a response. Returns True if response received."""
    script = (
        f"import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
        f"s.settimeout({timeout}); "
        f"s.sendto(b'{message}', ('{host}', {port})); "
        f"data, _ = s.recvfrom(1024); s.close(); print('OK')"
    )
    try:
        result = run_in_ns(ns, ["python3", "-c", script], timeout=timeout + 2)
        return "OK" in result.stdout
    except subprocess.TimeoutExpired:
        return False


def start_tcp_listener(ns, port):
    """Start a TCP listener that echoes back. Returns the Popen object."""
    script = (
        f"import socket\n"
        f"s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        f"s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        f"s.bind(('0.0.0.0', {port}))\n"
        f"s.listen(5)\n"
        f"while True:\n"
        f"    c, _ = s.accept()\n"
        f"    c.sendall(b'OK')\n"
        f"    c.close()\n"
    )
    proc = subprocess.Popen(
        ["ip", "netns", "exec", ns, "python3", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.3)
    return proc


def start_udp_listener(ns, port):
    """Start a UDP listener that echoes back. Returns the Popen object."""
    script = (
        f"import socket\n"
        f"s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n"
        f"s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        f"s.bind(('0.0.0.0', {port}))\n"
        f"while True:\n"
        f"    data, addr = s.recvfrom(1024)\n"
        f"    s.sendto(b'REPLY', addr)\n"
    )
    proc = subprocess.Popen(
        ["ip", "netns", "exec", ns, "python3", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.3)
    return proc


def get_nft_counters(chain_name):
    """Get packet counters from nftables rules in ns-fw."""
    result = run_in_ns("ns-fw", ["nft", "list", "chain", "inet", "firewall", chain_name])
    return result.stdout


def clear_dmesg(ns="ns-fw"):
    """Clear kernel log in a namespace."""
    run_in_ns(ns, ["dmesg", "--clear"])


def get_dmesg(ns="ns-fw", prefix=None):
    """Read kernel log entries, optionally filtering by prefix."""
    result = run_in_ns(ns, ["dmesg", "--notime"])
    lines = result.stdout.strip().splitlines()
    if prefix:
        lines = [l for l in lines if prefix in l]
    return lines


def tcp_connect_get_source(ns, host, port, timeout=3):
    """Connect and return the source IP seen by the server. For NAT testing."""
    script = (
        f"import socket; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); "
        f"s.settimeout({timeout}); "
        f"s.connect(('{host}', {port})); "
        f"data = s.recv(1024); s.close(); print(data.decode())"
    )
    try:
        result = run_in_ns(ns, ["python3", "-c", script], timeout=timeout + 2)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return None


def start_tcp_listener_report_source(ns, port):
    """TCP listener that sends back the client's source IP."""
    script = (
        f"import socket\n"
        f"s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        f"s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        f"s.bind(('0.0.0.0', {port}))\n"
        f"s.listen(5)\n"
        f"while True:\n"
        f"    c, addr = s.accept()\n"
        f"    c.sendall(addr[0].encode())\n"
        f"    c.close()\n"
    )
    proc = subprocess.Popen(
        ["ip", "netns", "exec", ns, "python3", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.3)
    return proc
