#!/usr/bin/env python3
"""Read-only check of a BEAAM: shows what the Home Assistant integration will create.

Only sends GET requests. Needs no dependencies.

Usage:
  BEAAM_HOST=192.168.1.28 BEAAM_API_KEY=sk_beaam_... python3 scripts/beaam_check.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

HOST = os.environ.get("BEAAM_HOST", "192.168.1.28")
KEY = os.environ.get("BEAAM_API_KEY", "")


def get(path):
    req = urllib.request.Request(
        f"http://{HOST}{path}",
        headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        return {"_http_error": err.code}


def platform(dp):
    dt, ctrl = dp.get("dataType"), dp.get("controllable", False)
    if dt == "BOOLEAN":
        return "switch" if ctrl else "binary_sensor"
    if dt == "NUMBER" and ctrl:
        return "number"
    return "sensor (disabled)" if dt and dt.endswith("[]") else "sensor"


def main():
    if not KEY:
        sys.exit("Set BEAAM_API_KEY (and BEAAM_HOST if not 192.168.1.28)")
    config = get("/api/v1/site/configuration")
    if "_http_error" in config:
        sys.exit(f"site/configuration -> HTTP {config['_http_error']}")
    print(f"Site {config['siteId']}  (API config version {config.get('versionTimestamp')})\n")

    site = {s["dataPointId"]: s["value"] for s in get("/api/v1/site/state")["energyFlow"]["states"]}
    print("== BEAAM (energy flow)")
    for dp_id, dp in config["energyFlow"]["dataPoints"].items():
        print(f"  {platform(dp):18} {dp['key']:34} {site.get(dp_id)!r} {dp.get('unitOfMeasure')}")

    for thing_id, thing in config["things"].items():
        print(f"\n== {thing.get('name')}  [{thing.get('type')}]  {thing_id}")
        states = get(f"/api/v1/things/{thing_id}/states")
        if "_http_error" in states:
            print(f"  states -> HTTP {states['_http_error']}")
            values = {}
        else:
            values = {s["dataPointId"]: s["value"] for s in states["states"]}
        for dp_id, dp in thing["dataPoints"].items():
            print(f"  {platform(dp):18} {dp['key']:34} {values.get(dp_id)!r} {dp.get('unitOfMeasure')}")
        settings = get(f"/api/v1/things/{thing_id}/settings")
        for s in settings.get("settings", []):
            kind = "switch" if isinstance(s["value"], bool) else "number" if isinstance(s["value"], (int, float)) else "sensor"
            print(f"  {kind + ' (setting)':18} {s['key']:34} {s['value']!r}")


if __name__ == "__main__":
    main()
