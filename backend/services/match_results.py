"""One entry point for writing a match result, whichever store holds it.

Until now every endpoint that wrote a result had to know which engine it was
talking to, and say so in its own words: the classic store wants a winner and
two scores, the graph store wants a ranking. That knowledge was copied into
every caller, which is why the two sides kept drifting apart.

The knowledge lives here now. A caller states what happened - as a winner, as a
ranking, or as both - and this module translates it into whatever the holding
store needs. A duel is a ranking of two, so the translation is total in both
directions; that is also what lets a test prove both engines decide the same
thing from the same input, instead of it being asserted in a comment.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from services.classic_result_submission import submit_classic_result
from services.classic_results import duel_from_ranking, ranking_from_duel
from services.match_result_errors import MatchResultError
from services.v2_result_submission import submit_v2_result


CLASSIC_COLLECTION = "matches"
GRAPH_COLLECTION = "matches_v2"


@dataclass(frozen=True)
class MatchOutcome:
    """What happened in a match, in whichever way the caller knows it.

    ``results`` is the canonical form - a ranking, one entry per participant.
    ``winner_id`` with the two scores is the duel shorthand. Giving either is
    enough; the missing one is derived from the other.
    """

    status: str = "completed"
    results: list[dict] | None = None
    winner_id: str | None = None
    score_a: int | None = None
    score_b: int | None = None
    note: str | None = None
    proof_url: str | None = None
    extra_set: dict = field(default_factory=dict)


def as_ranking(match: dict, outcome: MatchOutcome) -> list[dict]:
    """The outcome as a ranking, deriving it from the duel form if needed."""
    if outcome.results:
        return outcome.results
    return ranking_from_duel(match, outcome.winner_id, outcome.score_a, outcome.score_b)


def as_duel(match: dict, outcome: MatchOutcome) -> dict:
    """The outcome as winner and scores, deriving it from a ranking if needed."""
    if outcome.results and not outcome.winner_id:
        return duel_from_ranking(match, outcome.results)
    return {
        "winner_id": outcome.winner_id,
        "score_a": outcome.score_a,
        "score_b": outcome.score_b,
    }


async def apply_match_result(
    db,
    match: dict,
    collection: str,
    outcome: MatchOutcome,
    *,
    actor_id: str | None,
    audit_action: str,
    force: bool = False,
    audit_data: dict | None = None,
) -> dict:
    """Write one result into whichever store holds the match.

    Both branches return the same shape, so a caller never has to unpack two
    different answers: the stored match, which follow-up matches changed, and
    whether this call was an exact repeat of one already applied.
    """
    if collection == GRAPH_COLLECTION:
        return await submit_v2_result(
            db,
            match,
            as_ranking(match, outcome),
            actor_id=actor_id,
            proof_url=outcome.proof_url,
            note=outcome.note,
            force=force,
            audit_action=audit_action,
        )
    if collection == CLASSIC_COLLECTION:
        duel = as_duel(match, outcome)
        return await submit_classic_result(
            db,
            match,
            status=outcome.status,
            winner_id=duel["winner_id"],
            score_a=duel["score_a"],
            score_b=duel["score_b"],
            actor_id=actor_id,
            audit_action=audit_action,
            note=outcome.note,
            extra_set=outcome.extra_set or None,
            audit_data=audit_data,
        )
    raise MatchResultError(f"Unbekannter Match-Speicher: {collection}")
