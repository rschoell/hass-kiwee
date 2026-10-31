#!/usr/bin/env python3
"""Reboot a Kiwee MoCA adapter from the command line and time how long it takes to come back.

Usage:
    python3 tools/reboot.py <adapter-ip> [user] [password] [--yes] [--allow-controller]

Sends the same request as the Reboot button on the adapter's reboot.html page
(POST /ms/1/0xb00 with {"data":[]}), then polls until the adapter answers again.

Rebooting the network controller interrupts every MoCA link (and anything that uses the
controller as its uplink), so it is refused unless you pass --allow-controller.
Stdlib only. Redact MAC addresses before sharing any output.
"""
import base64
import json
import secrets
import sys
import time
import urllib.error
import urllib.request

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = {a for a in sys.argv[1:] if a.startswith("--")}
if not args:
    sys.exit(__doc__)
host = args[0]
user = args[1] if len(args) > 1 else "admin"
password = args[2] if len(args) > 2 else "maxlinear"

BASE = f"http://{host}"
AUTH = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
token = secrets.token_hex(16).upper()


def get_token():
    global token
    try:
        req = urllib.request.Request(f"{BASE}/devStatus.html", headers={"Authorization": AUTH})
        with urllib.request.urlopen(req, timeout=10) as r:
            for c in r.headers.get_all("Set-Cookie") or []:
                if c.startswith("csrf_token="):
                    token = c.split("=", 1)[1].split(";", 1)[0]
    except Exception:  # noqa: BLE001
        pass


def post(path, page="devStatus.html", timeout=10):
    headers = {
        "Authorization": AUTH,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html, */*",
        "X-CSRF-TOKEN": token,
        "Cookie": f"csrf_token={token}",
        "Origin": BASE,
        "Referer": f"{BASE}/{page}",
    }
    req = urllib.request.Request(BASE + path, data=b'{"data":[]}', method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode(errors="replace")


get_token()
try:
    _, body = post("/ms/0/0x15")
    words = json.loads(body)["data"]
except Exception as e:  # noqa: BLE001
    sys.exit(f"Cannot read the adapter at {host}: {e}")

local_node, nc_node = int(words[0], 16), int(words[1], 16)
is_controller = local_node == nc_node
print(f"Adapter {host}: node {local_node}, controller is node {nc_node} "
      f"-> this adapter {'IS' if is_controller else 'is not'} the network controller")
if is_controller and "--allow-controller" not in flags:
    sys.exit("Refusing to reboot the network controller (it interrupts the whole MoCA network). "
             "Use --allow-controller if you really want that.")
if "--yes" not in flags:
    if input(f"Type the adapter IP ({host}) to confirm the reboot: ").strip() != host:
        sys.exit("Not confirmed, nothing sent.")

started = time.monotonic()
print("Sending reboot request ...")
try:
    status, body = post("/ms/1/0xb00", page="reboot.html")
    print(f"Answer: HTTP {status}, body: {body.strip()[:200]!r}")
except urllib.error.HTTPError as e:
    sys.exit(f"The adapter refused the request: HTTP {e.code}")
except Exception as e:  # noqa: BLE001
    print(f"No answer to the request (the adapter does not reply when it reboots): {type(e).__name__}: {e}")

print("Waiting for the adapter to come back ...")
went_down = None
while time.monotonic() - started < 300:
    time.sleep(3)
    try:
        post("/ms/0/0x15")
        if went_down is not None:
            print(f"Back after {time.monotonic() - started:.0f} s "
                  f"(was unreachable for {time.monotonic() - went_down:.0f} s)")
            break
    except Exception:  # noqa: BLE001
        if went_down is None:
            went_down = time.monotonic()
            print(f"Went down after {went_down - started:.0f} s")
else:
    print("Did not come back within 300 s.")
