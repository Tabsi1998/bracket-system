import asyncio
from types import SimpleNamespace

from services import migrations


class _LockCollection:
    def __init__(self):
        self.owner = None
        self.released = False

    async def find_one_and_update(self, _query, update, **_kwargs):
        self.owner = update["$set"]["owner"]
        return {"_id": "global", "owner": self.owner}

    async def update_one(self, query, _update):
        assert query["owner"] == self.owner
        self.released = True


class _MigrationCollection:
    def __init__(self, completed=None):
        self.completed = list(completed or [])
        self.records = []

    async def distinct(self, _field):
        return list(self.completed)

    async def update_one(self, _query, update, **_kwargs):
        self.records.append(update["$setOnInsert"])


def test_pending_migrations_run_once_and_release_lease(monkeypatch):
    calls = []

    async def migration(_db):
        calls.append("run")
        return {"changed": 2}

    monkeypatch.setattr(migrations, "MIGRATIONS", ((7, "test", migration),))
    lock = _LockCollection()
    records = _MigrationCollection()
    db = SimpleNamespace(schema_migration_lock=lock, schema_migrations=records)

    applied = asyncio.run(migrations.run_pending_migrations(db))

    assert calls == ["run"]
    assert applied[0]["version"] == 7
    assert records.records[0]["result"] == {"changed": 2}
    assert lock.released is True


def test_completed_migration_is_skipped(monkeypatch):
    async def must_not_run(_db):
        raise AssertionError("completed migration ran again")

    monkeypatch.setattr(migrations, "MIGRATIONS", ((7, "test", must_not_run),))
    lock = _LockCollection()
    records = _MigrationCollection(completed=[7])
    db = SimpleNamespace(schema_migration_lock=lock, schema_migrations=records)

    assert asyncio.run(migrations.run_pending_migrations(db)) == []
    assert records.records == []
    assert lock.released is True
