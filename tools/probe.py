#!/usr/bin/env python3
"""Replay the requests the Kiwee adapter's own web UI sends (stdlib only).

Usage: python3 tools/probe.py 192.168.1.50 [user] [password] > probe.txt

Replays exactly the requests captured from devStatus.html, phyRates.html and index.html
(same paths, same bodies) with Basic auth and a matching csrf_token cookie /
X-CSRF-TOKEN header, and prints every raw response. Redact MAC addresses
before sharing the output.
"""
import base64
import secrets
import sys
import urllib.error
import urllib.request

host = sys.argv[1]
user = sys.argv[2] if len(sys.argv) > 2 else "admin"
pw = sys.argv[3] if len(sys.argv) > 3 else "maxlinear"
AUTH = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
BASE = f"http://{host}"

# pick up a CSRF token from a page load, else invent one
token = None
try:
    req = urllib.request.Request(f"{BASE}/devStatus.html", headers={"Authorization": AUTH})
    with urllib.request.urlopen(req, timeout=10) as r:
        for c in r.headers.get_all("Set-Cookie") or []:
            if c.startswith("csrf_token="):
                token = c.split("=", 1)[1].split(";", 1)[0]
        print(f"devStatus.html: HTTP {r.status}, server csrf cookie: {'yes' if token else 'no'}")
except Exception as e:  # noqa: BLE001
    print(f"devStatus.html: {e}")
token = token or secrets.token_hex(16).upper()


def post(path, body, page):
    headers = {
        "Authorization": AUTH,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html, */*",
        "X-CSRF-TOKEN": token,
        "Cookie": f"csrf_token={token}",
        "Origin": BASE,
        "Referer": f"{BASE}/{page}",
    }
    req = urllib.request.Request(BASE + path, data=body.encode(), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            text = r.read().decode(errors="replace")
            return f"HTTP {r.status} len={len(text)}\n{text.strip()}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return f"ERROR {e}"


E = '{"data":[]}'
# (page, path, body) -- captured from the web UI, in the order the UI sends them
CAPTURED = [
    ("devStatus.html", "/ms/0/0x15", E),
    ("devStatus.html", "/ms/0/0x24", E),
    ("devStatus.html", "/ms/0/0x16", '{"data":[3]}'),
    ("devStatus.html", "/ms/1/0x103/GET", '{"data":[3]}'),
    ("devStatus.html", "/ms/0/0x14", '{"data":[0]}'),
    ("devStatus.html", "/ms/0/0x1003/GET", ""),
    ("devStatus.html", "/ms/1/0x20b/GET", ""),
    ("devStatus.html", "/ms/1/0x303/GET", '{"data":[0]}'),
    ("devStatus.html", "/ms/1/0xb17", '{"data":[0]}'),
    ("devStatus.html", "/ms/0/0x7f", E),
    ("phyRates.html", "/ms/0/0x15", E),
    ("phyRates.html", "/ms/0/0x16", '{"data":[0]}'),
    ("phyRates.html", "/ms/0/0x16", '{"data":[1]}'),
    ("phyRates.html", "/ms/0/0x16", '{"data":[2]}'),
    ("phyRates.html", "/ms/0/0x16", '{"data":[3]}'),
    ("phyRates.html", "/ms/0/0x1D", '{"data":[1,2]}'),
    ("phyRates.html", "/ms/0/0x1D", '{"data":[2,2]}'),
    ("phyRates.html", "/ms/0/0x1D", '{"data":[4,2]}'),
    ("phyRates.html", "/ms/0/0x1D", '{"data":[8,2]}'),
    # index.html (configuration page: Preferred NC, frequencies, ...) -- all POST with an empty data list
    ("index.html", "/ms/0/0x1009/GET", E),
    ("index.html", "/ms/0/0x10a8/GET", E),
    ("index.html", "/ms/0/0x100e/GET", E),
    ("index.html", "/ms/1/0x212/GET", E),
    ("index.html", "/ms/0/0x1001/GET", E),
    ("index.html", "/ms/lastOFrq/GET", E),
    ("index.html", "/ms/0/0x1002/GET", E),
    ("index.html", "/ms/0/0x10f5/GET", E),
    ("index.html", "/ms/0/4195/GET", E),
    ("index.html", "/ms/0/4211/GET", E),
    ("index.html", "/ms/0/4219/GET", E),
    ("index.html", "/ms/0/4203/GET", E),
    ("index.html", "/ms/0/4196/GET", E),
    ("index.html", "/ms/0/4212/GET", E),
    ("index.html", "/ms/0/4220/GET", E),
    ("index.html", "/ms/0/4204/GET", E),
    ("index.html", "/ms/0/4197/GET", E),
    ("index.html", "/ms/0/4213/GET", E),
    ("index.html", "/ms/0/4221/GET", E),
    ("index.html", "/ms/0/4205/GET", E),
]
for page, path, body in CAPTURED:
    print(f"=== [{page}] POST {path}  body={body or '(empty)'}")
    print(post(path, body, page))
    print()
