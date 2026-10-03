#!/usr/bin/env python3
"""Fetch files from a GitHub repo via the REST contents API (proxy-friendly).
Usage: ghget.py <owner/repo> <outdir> <path> [<path> ...]
"""
import base64
import json
import os
import subprocess
import sys
import time

CURL = r"C:\Windows\System32\curl.exe"


def api(url):
    for attempt in range(6):
        p = subprocess.run(
            [CURL, "-s", "-m", "30", "-H", "Accept: application/vnd.github+json", url],
            capture_output=True,
        )
        raw = p.stdout
        if raw and len(raw) > 20:
            try:
                return json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                pass
        time.sleep(1.5)
    return None


def main():
    repo, outdir = sys.argv[1], sys.argv[2]
    paths = sys.argv[3:]
    for path in paths:
        url = f"https://api.github.com/repos/{repo}/contents/{path}?ref=HEAD"
        d = api(url)
        if not d or "content" not in d:
            print(f"FAIL  {path}  {str(d)[:120] if d else 'no-response'}")
            continue
        blob = base64.b64decode(d["content"])
        dest = os.path.join(outdir, path.replace("/", "__"))
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "wb") as f:
            f.write(blob)
        print(f"OK    {len(blob):>8}  {path}")


if __name__ == "__main__":
    main()
