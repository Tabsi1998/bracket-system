#!/usr/bin/env python3
"""Resolve backup targets from this Compose project, never from global volume names."""
from __future__ import annotations

import argparse
import json
import re
import sys


def resolve_target(config: dict, expected_db: str = "", expected_volume: str = "") -> tuple[str, str]:
    backend = config["services"]["backend"]
    environment = backend["environment"]
    database = environment["DB_NAME"]
    if not isinstance(database, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", database):
        raise ValueError("Invalid Compose DB_NAME")
    upload_path = environment.get("UPLOAD_DIR", "/app/backend/uploads")
    mounts = [mount for mount in backend["volumes"] if mount.get("target") == upload_path]
    if len(mounts) != 1 or mounts[0].get("type") != "volume" or mounts[0].get("source") != "uploads_data":
        raise ValueError("Expected exactly one named uploads_data mount at UPLOAD_DIR")
    volume_config = config["volumes"]["uploads_data"]
    volume = volume_config["name"]
    if volume_config.get("external") or not isinstance(volume, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]+", volume):
        raise ValueError("Expected a project-owned uploads volume with a resolved name")
    if expected_db and expected_db != database:
        raise ValueError("DB_NAME does not match the selected Compose project")
    if expected_volume and expected_volume != volume:
        raise ValueError("UPLOADS_VOLUME does not match the selected Compose project")
    return database, volume


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="")
    parser.add_argument("--volume", default="")
    args = parser.parse_args()
    try:
        database, volume = resolve_target(json.load(sys.stdin), args.db, args.volume)
    except (ValueError, KeyError, TypeError, AttributeError):
        # Compose input contains secrets: never print it or exception values.
        print("Backup target rejected: check Compose DB_NAME, UPLOAD_DIR and project-owned uploads_data; explicit overrides must match.", file=sys.stderr)
        return 1
    print(database)
    print(volume)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
