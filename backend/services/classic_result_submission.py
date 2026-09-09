"""The single place a classic match result is persisted.

Counterpart to ``v2_result_submission`` for the ``matches`` store. Before this
existed, three endpoints each wrote the result, reloaded the match, advanced the
bracket and fired notifications on their own. They did not agree: a result
entered by staff awarded badges and announced itself on Discord, while the very
same result agreed on by both players did neither, and a walkover did neither
either. The outcome was identical, the consequences were not.

Everything that follows from "this match is decided" now happens here, once.
"""
from __future__ import annotations

import logging

from models import new_id, now_utc
from services.classic_results import (
    build_classic_result_application,
    is_classic_result_replay,
)
from services.competition_usage import CLASSIC, record_write
from services.match_notifications import notify_match_result_confirmed
from services.station_runtime import release_station_for_match


logger = logging.getLogger("tls.match_results")


async def _record_audit(db, *, audit_action: str, match: dict, actor_id: str | None,
                        data: dict, advanced_match_ids: list[str]) -> None:
    await record_write(CLASSIC, audit_action, tournament_id=match.get("tournament_id"))
    await db.audit_logs.insert_one({
        "id": new_id(),
        "action": audit_action,
        "target_id": match.get("tournament_id") or match.get("id"),
        "actor_id": actor_id,
        "data": {
            "match_id": match.get("id"),
            "advanced_matches": advanced_match_ids,
            **data,
        },
        "created_at": now_utc().isoformat(),
    })


async def _award_badges(db, match: dict) -> None:
    from badges import on_match_completed

    registrations = {
        row["id"]: row.get("user_id")
        for row in await db.tournament_registrations.find(
            {"tournament_id": match["tournament_id"]}, {"_id": 0}).to_list(500)
    }
    winner_user = registrations.get(match.get("winner_id"))
    if winner_user:
        await on_match_completed(
            winner_user,
            registrations.get(match.get("loser_id")),
            match["tournament_id"],
            match["id"],
        )


async def _announce(db, match: dict) -> None:
    from discord_service import send_public_discord

    registrations = {
        row["id"]: row
        for row in await db.tournament_registrations.find(
            {"tournament_id": match["tournament_id"]}, {"_id": 0}).to_list(500)
    }
    tournament = await db.tournaments.find_one({"id": match["tournament_id"]}, {"_id": 0}) or {}
    first = registrations.get(match.get("participant_a_id"), {})
    second = registrations.get(match.get("participant_b_id"), {})
    winner = registrations.get(match.get("winner_id"), {})
    walkover = match.get("status") == "forfeit"
    score = f"({match.get('score_a', 0)}:{match.get('score_b', 0)})"
    await send_public_discord(
        tournament,
        f"🎮 Match beendet · {tournament.get('title') or 'Turnier'}",
        f"**{first.get('display_name') or '?'}** vs **{second.get('display_name') or '?'}**\n"
        f"Gewinner: **{winner.get('display_name') or '?'}** "
        f"{'(kampflos)' if walkover else score}",
        color=0x29B6E8,
        url=f"/tournaments/{tournament.get('slug') or tournament.get('id')}/bracket",
        fields=[{
            "name": "Runde",
            "value": match.get("round_name") or f"Runde {match.get('round', '?')}",
            "inline": True,
        }],
        event_key="match.completed",
    )


async def _finish_result_side_effects(db, match: dict) -> None:
    """Everything that follows a decided match, in one place and never fatal.

    A failing announcement must not undo a result that is already written, so
    each step is isolated - but it is logged rather than swallowed silently,
    because a permanently broken notification should be visible somewhere.
    """
    for label, action in (
        ("notification", notify_match_result_confirmed(db, match, "matches")),
        ("station release", release_station_for_match(db, match, "matches")),
        ("badges", _award_badges(db, match)),
        ("announcement", _announce(db, match)),
    ):
        try:
            await action
        except Exception as exc:
            logger.warning(
                "Classic result %s failed for match=%s type=%s",
                label, match.get("id"), type(exc).__name__,
            )


async def submit_classic_result(
    db,
    match: dict,
    *,
    status: str | None,
    winner_id: str | None,
    score_a: int | None = None,
    score_b: int | None = None,
    actor_id: str | None,
    audit_action: str,
    note: str | None = None,
    extra_set: dict | None = None,
    audit_data: dict | None = None,
) -> dict:
    """Persist one classic result while the caller owns the write lease."""
    match_id = match["id"]
    if is_classic_result_replay(
        match, status=status, winner_id=winner_id,
        score_a=score_a, score_b=score_b, note=note,
    ):
        stored = await db.matches.find_one({"id": match_id}, {"_id": 0}) or match
        return {"ok": True, "match": stored, "advanced_match_ids": [], "idempotent_replay": True}

    tournament_matches = await db.matches.find(
        {"tournament_id": match["tournament_id"]}, {"_id": 0}).to_list(2000)
    application = build_classic_result_application(
        match,
        tournament_matches,
        status=status,
        winner_id=winner_id,
        score_a=score_a,
        score_b=score_b,
        now_iso=now_utc().isoformat(),
        extra_set=extra_set,
    )
    advanced_match_ids = list(application["target_sets"])

    # Erst die Folgematches, dann das Quellmatch - so führt ein Abbruch
    # dazwischen zu einer Wiederholung und nicht zu einem Match, das als
    # entschieden gilt, ohne jemanden weitergeschickt zu haben.
    for target_id, update in application["target_sets"].items():
        await db.matches.update_one({"id": target_id}, {"$set": update})
    await db.matches.update_one({"id": match_id}, {"$set": application["match_set"]})

    updated = await db.matches.find_one({"id": match_id}, {"_id": 0}) or match
    await _record_audit(
        db,
        audit_action=audit_action,
        match=updated,
        actor_id=actor_id,
        data=audit_data or {},
        advanced_match_ids=advanced_match_ids,
    )
    if application["decided"]:
        await _finish_result_side_effects(db, updated)
    return {
        "ok": True,
        "match": updated,
        "advanced_match_ids": advanced_match_ids,
        "idempotent_replay": False,
    }
