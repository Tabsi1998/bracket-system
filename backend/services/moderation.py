"""Shared block-list checks for community interactions."""
from __future__ import annotations


async def block_between(db, first_user_id: str, second_user_id: str) -> dict | None:
    if not first_user_id or not second_user_id:
        return None
    return await db.user_blocks.find_one({
        "$or": [
            {"blocker_id": first_user_id, "blocked_id": second_user_id},
            {"blocker_id": second_user_id, "blocked_id": first_user_id},
        ],
    })


async def interaction_is_blocked(db, first_user_id: str, second_user_id: str) -> bool:
    return bool(await block_between(db, first_user_id, second_user_id))
