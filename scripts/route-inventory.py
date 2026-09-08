"""Dump the application's HTTP route table for before/after comparison.

A refactor that only moves code must not change a single route. Proving that by
reading a diff of two thousand moved lines is hopeless; comparing two sorted
route tables takes a second:

    python scripts/route-inventory.py > before.txt
    # ... refactor ...
    python scripts/route-inventory.py > after.txt
    diff before.txt after.txt

Empty output from diff is the proof. This was used for the extras_routes split
and is kept because the tournament consolidation will need it repeatedly.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"

# Import-time configuration only; nothing here reaches a real database.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("JWT_SECRET", "route-inventory-secret-with-at-least-32-chars")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("SETTINGS_ENCRYPTION_KEY", "NQBHeGtQg5HYMo1HzvJtSQPN7X8YpJrZDvw-XMz0Bm8=")

sys.path.insert(0, str(BACKEND))


def main() -> int:
    try:
        from server import app
    except Exception as exc:  # pragma: no cover - depends on local environment
        print(f"# Anwendung nicht ladbar: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    rows: list[str] = []
    collect(app.routes, rows)

    for row in sorted(rows):
        print(row)
    print(f"# {len(rows)} Routen")
    return 0


def collect(routes, rows: list[str]) -> None:
    """Walk the route tree.

    Included routers are not flattened into the application in this FastAPI
    version - they stay as wrapper objects that carry the original router. A
    flat scan therefore finds only the routes defined in server.py itself, so
    the wrappers have to be followed explicitly.
    """
    for route in routes or []:
        original = getattr(route, "original_router", None)
        if original is not None:
            collect(getattr(original, "routes", []), rows)
            continue
        nested = getattr(route, "routes", None)
        if nested and not getattr(route, "methods", None):
            collect(nested, rows)
            continue
        for method in sorted(getattr(route, "methods", []) or []):
            if method in {"HEAD", "OPTIONS"}:
                continue
            rows.append(f"{method:7} {route.path} -> {getattr(route, 'name', '')}")


if __name__ == "__main__":
    raise SystemExit(main())
