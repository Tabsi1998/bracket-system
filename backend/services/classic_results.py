"""Result application for classic duel matches.

The graph engine has had exactly one place that decides what a result changes
(``build_v2_result_application``). The classic engine had none - the same
sequence of "write the result, look up the follow-up match, move the winner
there" was written out three times, in the staff entry, in the player report and
in the walkover. Three copies of a rule are three chances for them to drift, and
they had already drifted: only one of them awarded badges or announced anything.

This module is the missing counterpart. It decides, without touching the
database, what one result changes - and returns it in the same shape the graph
engine returns, so the layer above can stop caring which engine it is talking to.
"""
from __future__ import annotations

from bracket_engine import advance_match_winner
from match_rules import match_allows_draw, participant_ids
from services.match_result_errors import MatchResultError


TERMINAL_STATUSES = {"completed", "forfeit"}
RESULT_FIELDS = ("status", "winner_id", "score_a", "score_b")


def result_signature(match: dict) -> tuple:
    """The part of a match that says how it ended."""
    return tuple(match.get(field) for field in RESULT_FIELDS)


def duel_sides(match: dict) -> tuple[str | None, str | None]:
    """The two sides of a duel, whichever shape the match is stored in.

    The classic store names them in two fixed fields, the graph store lists them
    as slots. A translator that only understood one of the two would be no
    translator at all.
    """
    first, second = match.get("participant_a_id"), match.get("participant_b_id")
    if first or second:
        return first, second
    filled = [
        slot.get("registration_id")
        for slot in match.get("slots") or []
        if slot.get("registration_id")
    ]
    return (
        filled[0] if filled else None,
        filled[1] if len(filled) > 1 else None,
    )


def loser_for(match: dict, winner_id: str | None) -> str | None:
    if not winner_id:
        return None
    first, second = duel_sides(match)
    if winner_id == first:
        return second
    if winner_id == second:
        return first
    return None


def ranking_from_duel(match: dict, winner_id: str | None,
                      score_a: int | None = None, score_b: int | None = None) -> list[dict]:
    """Express a duel outcome as the ranking the graph engine speaks.

    A duel is a ranking of two - that is the whole reason the two engines can be
    merged at all. Without a winner both sides share rank 1, which is exactly how
    the graph engine records a draw.
    """
    first, second = duel_sides(match)
    if len(match.get("slots") or []) > 2:
        raise MatchResultError(
            "Für ein Match mit mehr als zwei Teilnehmern wird eine Platzierungsliste "
            "gemeldet, kein Sieger."
        )
    if winner_id and winner_id not in {first, second}:
        # Ohne diese Pruefung wuerde ein fremder Sieger hier lautlos verschwinden
        # und die Rangliste den ersten Teilnehmer zum Gewinner machen.
        raise MatchResultError("Gewinner ist kein Teilnehmer dieses Matches")
    scores = {first: score_a, second: score_b}
    entries = [
        {"registration_id": item, "score": scores.get(item)}
        for item in (first, second) if item
    ]
    for entry in entries:
        if not winner_id:
            entry["rank"] = 1
        else:
            entry["rank"] = 1 if entry["registration_id"] == winner_id else 2
    return sorted(entries, key=lambda entry: entry["rank"])


def duel_from_ranking(match: dict, results: list[dict]) -> dict:
    """Read a duel outcome back out of a ranking.

    The inverse of :func:`ranking_from_duel`, and the reason a comparison test
    can show that both engines decide the same thing from the same input.
    """
    by_registration = {
        entry.get("registration_id"): entry
        for entry in results or []
        if entry.get("registration_id")
    }
    first, second = duel_sides(match)
    ranks = {item: (by_registration.get(item) or {}).get("rank") for item in (first, second)}
    ranked = [item for item in (first, second) if ranks.get(item) is not None]
    winner = None
    if len(ranked) == 2 and ranks[first] != ranks[second]:
        winner = first if ranks[first] < ranks[second] else second
    elif len(ranked) == 1:
        winner = ranked[0]
    return {
        "winner_id": winner,
        "loser_id": loser_for(match, winner),
        "score_a": (by_registration.get(first) or {}).get("score"),
        "score_b": (by_registration.get(second) or {}).get("score"),
    }


def validate_outcome(match: dict, status: str | None, winner_id: str | None) -> None:
    """Refuse an outcome the bracket cannot carry.

    Both checks protect the advancement: a winner who never played this match
    would be moved into the next round, and a decided knockout match without a
    winner would leave the follow-up slot empty forever.
    """
    if winner_id and winner_id not in participant_ids(match):
        raise MatchResultError("Gewinner ist kein Teilnehmer dieses Matches")
    if status == "completed" and not winner_id and not match_allows_draw(match):
        raise MatchResultError("Dieses Match braucht einen Gewinner")


def is_classic_result_replay(match: dict, *, status: str | None, winner_id: str | None,
                             score_a: int | None, score_b: int | None,
                             note: str | None = None) -> bool:
    """Whether the match already says exactly this.

    An exact retry must not advance anyone a second time, write another audit
    entry or send the announcement again - the same promise the graph engine
    makes for its own replays.
    """
    if match.get("status") not in TERMINAL_STATUSES:
        return False
    if note is not None and (match.get("admin_decision_note") or None) != (note or None):
        return False
    return result_signature(match) == (status, winner_id, score_a, score_b)


def build_classic_result_application(
    match: dict,
    tournament_matches: list[dict],
    *,
    status: str | None,
    winner_id: str | None,
    score_a: int | None = None,
    score_b: int | None = None,
    now_iso: str,
    extra_set: dict | None = None,
) -> dict:
    """Decide what this result changes, without writing any of it.

    Mirrors ``build_v2_result_application``: ``match_set`` is what the match
    itself becomes, ``target_sets`` is what the follow-up matches become. Only a
    decided match moves anyone onward - an entry that merely schedules or
    disputes a match leaves the bracket untouched.
    """
    validate_outcome(match, status, winner_id)

    match_set: dict = dict(extra_set or {})
    # Ein nicht angegebener Punktstand heisst "unveraendert", nicht "geloescht" -
    # sonst wuerde ein Einspruch die bereits gemeldeten Punkte wegwischen.
    for key, value in (("score_a", score_a), ("score_b", score_b)):
        if value is not None:
            match_set[key] = value
    if status:
        match_set["status"] = status
    match_set["winner_id"] = winner_id
    match_set["loser_id"] = loser_for(match, winner_id)
    match_set["updated_at"] = now_iso

    decided = status in TERMINAL_STATUSES and bool(winner_id)
    target_sets: dict[str, dict] = {}
    if decided:
        decided_match = {**match, **match_set}
        for target in advance_match_winner(decided_match, tournament_matches):
            target_sets[target["id"]] = {
                key: value for key, value in target.items() if key != "_id"
            }

    return {
        "match_set": match_set,
        "target_sets": target_sets,
        "decided": decided,
        "results": ranking_from_duel(match, winner_id, score_a, score_b) if decided else [],
    }
