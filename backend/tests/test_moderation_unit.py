import asyncio

from services.moderation import block_between, interaction_is_blocked


class Blocks:
    def __init__(self, row=None):
        self.row = row
        self.query = None

    async def find_one(self, query):
        self.query = query
        return self.row


class Db:
    def __init__(self, row=None):
        self.user_blocks = Blocks(row)


def test_block_lookup_checks_both_directions():
    db = Db({"blocker_id": "b", "blocked_id": "a"})
    row = asyncio.run(block_between(db, "a", "b"))
    assert row["blocker_id"] == "b"
    clauses = db.user_blocks.query["$or"]
    assert {tuple(sorted(clause.items())) for clause in clauses} == {
        tuple(sorted({"blocker_id": "a", "blocked_id": "b"}.items())),
        tuple(sorted({"blocker_id": "b", "blocked_id": "a"}.items())),
    }
    assert asyncio.run(interaction_is_blocked(db, "a", "b")) is True


def test_block_lookup_ignores_incomplete_identity():
    db = Db()
    assert asyncio.run(block_between(db, "a", "")) is None
    assert db.user_blocks.query is None
