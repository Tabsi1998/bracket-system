"""Small, ordered MongoDB migration runner for idempotent schema/data changes."""
from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from models import new_id
from services.secret_migration import migrate_plaintext_secrets

MIGRATIONS = (
    (1, "encrypt_legacy_integration_credentials", migrate_plaintext_secrets),
)


async def run_pending_migrations(db) -> list[dict]:
    """Run each migration once. A short lease avoids startup-worker races."""
    now = datetime.now(timezone.utc)
    owner = f"{socket.gethostname()}:{os.getpid()}:{new_id()}"
    try:
        lease = await db.schema_migration_lock.find_one_and_update(
            {
                "_id": "global",
                "$or": [
                    {"owner": owner},
                    {"locked_until": {"$lt": now}},
                    {"locked_until": {"$exists": False}},
                ],
            },
            {"$set": {"owner": owner, "locked_until": now + timedelta(minutes=10), "updated_at": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        return []
    if not lease or lease.get("owner") != owner:
        return []

    applied: list[dict] = []
    try:
        completed = set(await db.schema_migrations.distinct("version"))
        for version, name, migration in MIGRATIONS:
            if version in completed:
                continue
            result = await migration(db)
            finished_at = datetime.now(timezone.utc)
            record = {"version": version, "name": name, "result": result, "applied_at": finished_at}
            await db.schema_migrations.update_one(
                {"version": version}, {"$setOnInsert": record}, upsert=True,
            )
            applied.append(record)
        return applied
    finally:
        await db.schema_migration_lock.update_one(
            {"_id": "global", "owner": owner},
            {"$set": {"locked_until": datetime.now(timezone.utc)}, "$unset": {"owner": ""}},
        )
