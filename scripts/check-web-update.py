"""Read-only checks for release consistency and browser update headers."""
import json
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def fetch(base, path):
    request = Request(base + path, headers={"Cache-Control": "no-cache", "User-Agent": "TLS-Release-Check/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.headers, response.read(2_000_000).decode("utf-8")


def check(base):
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("Expected a website origin without credentials, path or query")
    base = base.rstrip("/")
    manifest_headers, manifest = fetch(base, "/version.json")
    version = json.loads(manifest)["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[a-f0-9]{20}", version):
        raise ValueError("Invalid release version")
    worker_headers, worker = fetch(base, "/service-worker.js")
    for headers in (manifest_headers, worker_headers):
        cache = headers.get("Cache-Control", "").lower()
        if "no-store" not in cache or "immutable" in cache:
            raise ValueError("Service worker/version manifest must use Cache-Control: no-store")
    if version not in worker or "javascript" not in worker_headers.get("Content-Type", ""):
        raise ValueError("Service worker does not match release manifest")
    root_assets = None
    for path in ("/", "/login", "/verify-email", "/dashboard"):
        headers, html = fetch(base, path)
        if "text/html" not in headers.get("Content-Type", "") or "no-store" not in headers.get("Cache-Control", "").lower():
            raise ValueError(f"{path}: HTML content or cache policy incorrect")
        assets = sorted(set(re.findall(r'assets/[^"\s<>]+\.(?:js|css)', html)))
        if not assets or (root_assets is not None and assets != root_assets):
            raise ValueError(f"{path}: stale or missing application assets")
        root_assets = assets
    for asset in root_assets:
        headers, _body = fetch(base, "/" + asset)
        if "text/html" in headers.get("Content-Type", ""):
            raise ValueError("Missing application asset returned HTML")
    return {"origin": base, "version": version, "ok": True}


def main():
    if len(sys.argv) not in {2, 3}:
        print("Usage: python scripts/check-web-update.py ORIGIN [PUBLIC_ORIGIN]")
        return 2
    try:
        reports = [check(origin) for origin in sys.argv[1:]]
        if len({report["version"] for report in reports}) != 1:
            raise ValueError("Public proxy serves a different release than the local frontend")
        print(json.dumps({"read_only": True, "checks": reports}, indent=2))
        return 0
    except Exception as error:
        print(f"Web release check failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
