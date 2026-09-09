"""The one result core, and the proof that both engines agree.

The plan for this step asks for something specific: that the same input produces
the same outcome on both write paths - as a comparison, not as a claim. That is
what the middle section here does. A duel is a ranking of two, so the two ways of
stating an outcome have to be translatable into each other without loss; if they
are, the two engines cannot drift apart on who won.

The rest pins the consequences. Three endpoints used to write a classic result
and they did not agree on what follows from it: staff entry awarded badges and
announced the match, the very same result agreed on by both players did neither.
Those tests would have caught that.
"""
import asyncio
import pathlib
import sys
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import services.classic_result_submission as classic_submission
from services.classic_results import (
    build_classic_result_application,
    duel_from_ranking,
    is_classic_result_replay,
    ranking_from_duel,
)
from services.match_result_errors import MatchResultError
from services.match_results import MatchOutcome, apply_match_result, as_duel, as_ranking
from services.match_v2_results import MatchV2ResultError


def duel_match(**overrides):
    return {
        "id": "m1",
        "tournament_id": "t1",
        "bracket": "wb",
        "round": 1,
        "status": "ready",
        "participant_a_id": "reg-a",
        "participant_b_id": "reg-b",
        **overrides,
    }


def graph_match(**overrides):
    return {
        "id": "g1",
        "tournament_id": "t1",
        "stage_id": "s1",
        "match_key": "A",
        "status": "ready",
        "match_type": "duel",
        "settings": {"min_players": 2, "match_size": 2},
        "slots": [
            {"slot": 1, "registration_id": "reg-a", "user_id": "u-a", "status": "filled"},
            {"slot": 2, "registration_id": "reg-b", "user_id": "u-b", "status": "filled"},
        ],
        "results": [],
        "advancement": [],
        **overrides,
    }


class FakeCollection:
    def __init__(self, rows=()):
        self.rows = [deepcopy(row) for row in rows]

    def _hit(self, row, query):
        return all(row.get(key) == value for key, value in query.items()
                   if not isinstance(value, dict))

    def find(self, query, _projection=None):
        rows = [deepcopy(row) for row in self.rows if self._hit(row, query)]
        return SimpleNamespace(
            to_list=AsyncMock(return_value=rows),
            sort=lambda *_a: SimpleNamespace(to_list=AsyncMock(return_value=rows)),
        )

    async def find_one(self, query, _projection=None):
        return next((deepcopy(row) for row in self.rows if self._hit(row, query)), None)

    async def insert_one(self, document):
        self.rows.append(deepcopy(document))

    async def update_one(self, query, update, upsert=False):
        for row in self.rows:
            if self._hit(row, query):
                row.update(deepcopy(update.get("$set") or {}))
                return
        if upsert:
            self.rows.append({**query, **deepcopy(update.get("$setOnInsert") or {})})


def fake_db(**collections):
    names = ("matches", "matches_v2", "match_reports_v2", "audit_logs",
             "tournaments", "tournament_registrations")
    return SimpleNamespace(**{
        name: FakeCollection(collections.get(name, ())) for name in names
    })


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture(autouse=True)
def quiet_side_effects(monkeypatch):
    """Silence what a decided match triggers; the tests that care patch it again."""
    monkeypatch.setattr(classic_submission, "notify_match_result_confirmed", AsyncMock())
    monkeypatch.setattr(classic_submission, "release_station_for_match", AsyncMock())
    monkeypatch.setattr(classic_submission, "_award_badges", AsyncMock())
    monkeypatch.setattr(classic_submission, "_announce", AsyncMock())


# ------------------------------------------------- Duell und Rangliste ineinander

def test_a_duel_becomes_a_ranking_of_two():
    ranking = ranking_from_duel(duel_match(), "reg-b", score_a=1, score_b=3)

    assert ranking == [
        {"registration_id": "reg-b", "score": 3, "rank": 1},
        {"registration_id": "reg-a", "score": 1, "rank": 2},
    ]


def test_a_draw_becomes_a_shared_first_place():
    """Genau so schreibt die Graph-Engine ein Unentschieden."""
    ranking = ranking_from_duel(duel_match(), None, score_a=2, score_b=2)

    assert [entry["rank"] for entry in ranking] == [1, 1]


def test_the_ranking_reads_back_as_the_same_duel():
    match = duel_match()

    for winner, score_a, score_b in [("reg-a", 3, 0), ("reg-b", 0, 3), (None, 1, 1)]:
        ranking = ranking_from_duel(match, winner, score_a, score_b)
        back = duel_from_ranking(match, ranking)

        assert back["winner_id"] == winner
        assert (back["score_a"], back["score_b"]) == (score_a, score_b)


def test_the_loser_comes_out_of_the_ranking_too():
    ranking = ranking_from_duel(duel_match(), "reg-a", 2, 0)

    assert duel_from_ranking(duel_match(), ranking)["loser_id"] == "reg-b"


# ------------------------------------------------- Der geforderte Vergleich

def graph_db_with(match):
    return fake_db(matches_v2=[match])


def test_both_engines_name_the_same_winner_from_the_same_input():
    """Das Abnahmekriterium dieses Blocks, als Vergleich statt als Behauptung."""
    outcome = MatchOutcome(status="completed", winner_id="reg-b", score_a=1, score_b=2)

    classic_db = fake_db(matches=[duel_match()])
    run(apply_match_result(classic_db, duel_match(), "matches", outcome,
                           actor_id="admin", audit_action="test"))
    stored_classic = classic_db.matches.rows[0]

    graph = graph_match()
    graph_db = graph_db_with(graph)
    run(apply_match_result(graph_db, graph, "matches_v2", outcome,
                           actor_id="admin", audit_action="test"))
    stored_graph = graph_db.matches_v2.rows[0]

    assert stored_classic["winner_id"] == "reg-b"
    first = next(entry for entry in stored_graph["results"] if entry["rank"] == 1)
    assert first["registration_id"] == "reg-b"
    assert stored_classic["status"] == stored_graph["status"] == "completed"


def test_a_ranking_decides_the_classic_store_the_same_way():
    """Auch anders herum: eine Rangliste muss im klassischen Speicher ankommen."""
    ranking = [
        {"registration_id": "reg-b", "rank": 1, "score": 5},
        {"registration_id": "reg-a", "rank": 2, "score": 3},
    ]
    db = fake_db(matches=[duel_match()])

    run(apply_match_result(db, duel_match(), "matches",
                           MatchOutcome(status="completed", results=ranking),
                           actor_id="admin", audit_action="test"))

    stored = db.matches.rows[0]
    assert stored["winner_id"] == "reg-b"
    assert stored["loser_id"] == "reg-a"
    assert (stored["score_a"], stored["score_b"]) == (3, 5)


def test_both_engines_refuse_a_winner_who_did_not_play():
    outcome = MatchOutcome(status="completed", winner_id="fremder")

    with pytest.raises(MatchResultError):
        run(apply_match_result(fake_db(matches=[duel_match()]), duel_match(), "matches",
                               outcome, actor_id="admin", audit_action="test"))

    graph = graph_match()
    with pytest.raises(MatchV2ResultError):
        run(apply_match_result(graph_db_with(graph), graph, "matches_v2",
                               outcome, actor_id="admin", audit_action="test"))


def test_an_unknown_store_is_refused_rather_than_guessed():
    with pytest.raises(MatchResultError):
        run(apply_match_result(fake_db(), duel_match(), "matches_v3",
                               MatchOutcome(), actor_id="admin", audit_action="test"))


# ------------------------------------------------- Der klassische Kern

def test_a_decided_match_moves_the_winner_onward():
    follow_up = {"id": "m2", "tournament_id": "t1", "status": "pending",
                 "participant_a_id": None, "participant_b_id": "reg-c"}
    match = duel_match(next_match_id="m2", next_match_slot="a")

    application = build_classic_result_application(
        match, [match, follow_up], status="completed", winner_id="reg-a", now_iso="jetzt")

    assert application["decided"] is True
    assert application["target_sets"]["m2"]["participant_a_id"] == "reg-a"
    assert application["target_sets"]["m2"]["status"] == "ready"


def test_an_undecided_entry_leaves_the_bracket_alone():
    """Ein Einspruch oder ein Termin darf niemanden weiterschicken."""
    match = duel_match(next_match_id="m2", next_match_slot="a")

    application = build_classic_result_application(
        match, [match], status="disputed", winner_id=None, now_iso="jetzt")

    assert application["decided"] is False
    assert application["target_sets"] == {}


def test_a_knockout_match_cannot_end_without_a_winner():
    with pytest.raises(MatchResultError):
        build_classic_result_application(
            duel_match(), [], status="completed", winner_id=None, now_iso="jetzt")


def test_a_group_match_may_end_level():
    application = build_classic_result_application(
        duel_match(bracket="group_A"), [], status="completed", winner_id=None,
        score_a=1, score_b=1, now_iso="jetzt")

    assert application["match_set"]["status"] == "completed"
    assert application["match_set"]["winner_id"] is None


def test_a_missing_score_means_unchanged_not_cleared():
    """Sonst wischt ein Einspruch die bereits gemeldeten Punkte weg."""
    application = build_classic_result_application(
        duel_match(score_a=2, score_b=1), [], status="disputed", winner_id=None,
        now_iso="jetzt")

    assert "score_a" not in application["match_set"]
    assert "score_b" not in application["match_set"]


def test_operational_fields_ride_along_in_the_same_write():
    application = build_classic_result_application(
        duel_match(), [], status="completed", winner_id="reg-a", now_iso="jetzt",
        extra_set={"admin_note": "korrigiert"})

    assert application["match_set"]["admin_note"] == "korrigiert"


@pytest.mark.parametrize("status", ["completed", "forfeit"])
def test_the_same_result_twice_is_recognised(status):
    match = duel_match(status=status, winner_id="reg-a", loser_id="reg-b",
                       score_a=2, score_b=0)

    assert is_classic_result_replay(match, status=status, winner_id="reg-a",
                                    score_a=2, score_b=0) is True
    assert is_classic_result_replay(match, status=status, winner_id="reg-b",
                                    score_a=0, score_b=2) is False


def test_an_open_match_is_never_a_replay():
    match = duel_match(status="ready", winner_id=None)

    assert is_classic_result_replay(match, status="completed", winner_id="reg-a",
                                    score_a=None, score_b=None) is False


def test_a_replay_writes_nothing_and_says_so():
    match = duel_match(status="completed", winner_id="reg-a", loser_id="reg-b",
                       score_a=2, score_b=0)
    db = fake_db(matches=[match])

    result = run(apply_match_result(
        db, match, "matches",
        MatchOutcome(status="completed", winner_id="reg-a", score_a=2, score_b=0),
        actor_id="admin", audit_action="test"))

    assert result["idempotent_replay"] is True
    assert db.audit_logs.rows == []


# ------------------------------------------------- Gleiche Folgen für jeden Weg

def side_effect_spies(monkeypatch):
    spies = {
        "notify": AsyncMock(),
        "release": AsyncMock(),
        "badges": AsyncMock(),
        "announce": AsyncMock(),
    }
    monkeypatch.setattr(classic_submission, "notify_match_result_confirmed", spies["notify"])
    monkeypatch.setattr(classic_submission, "release_station_for_match", spies["release"])
    monkeypatch.setattr(classic_submission, "_award_badges", spies["badges"])
    monkeypatch.setattr(classic_submission, "_announce", spies["announce"])
    return spies


@pytest.mark.parametrize("audit_action", [
    "match.result.update",
    "match.result.auto_resolution",
    "match.forfeit",
])
def test_every_way_of_deciding_a_match_has_the_same_consequences(monkeypatch, audit_action):
    """Vorher entschied der Weg, ob es Abzeichen und eine Ankündigung gab."""
    spies = side_effect_spies(monkeypatch)
    match = duel_match()
    status = "forfeit" if audit_action == "match.forfeit" else "completed"

    run(apply_match_result(
        fake_db(matches=[match]), match, "matches",
        MatchOutcome(status=status, winner_id="reg-a", score_a=2, score_b=0),
        actor_id="admin", audit_action=audit_action))

    for name, spy in spies.items():
        assert spy.await_count == 1, f"{name} fehlt bei {audit_action}"


def test_an_undecided_result_triggers_nothing(monkeypatch):
    spies = side_effect_spies(monkeypatch)
    match = duel_match()

    run(apply_match_result(
        fake_db(matches=[match]), match, "matches",
        MatchOutcome(status="disputed", winner_id=None),
        actor_id="admin", audit_action="match.result.update"))

    for spy in spies.values():
        spy.assert_not_awaited()


def test_a_failing_announcement_does_not_undo_the_result(monkeypatch):
    """Discord ist nicht Teil des Ergebnisses - ein Ausfall darf es nicht kippen."""
    side_effect_spies(monkeypatch)
    monkeypatch.setattr(classic_submission, "_announce",
                        AsyncMock(side_effect=RuntimeError("Discord weg")))
    match = duel_match()
    db = fake_db(matches=[match])

    result = run(apply_match_result(
        db, match, "matches",
        MatchOutcome(status="completed", winner_id="reg-a", score_a=2, score_b=0),
        actor_id="admin", audit_action="match.result.update"))

    assert result["match"]["winner_id"] == "reg-a"
    assert db.matches.rows[0]["status"] == "completed"


def test_the_write_is_recorded_for_the_classic_engine():
    match = duel_match()
    db = fake_db(matches=[match])

    run(apply_match_result(db, match, "matches",
                           MatchOutcome(status="completed", winner_id="reg-a"),
                           actor_id="admin", audit_action="match.result.update"))

    entry = db.audit_logs.rows[0]
    assert entry["action"] == "match.result.update"
    assert entry["data"]["match_id"] == "m1"


# ------------------------------------------------- Übersetzung im Einstieg

def test_the_entry_point_hands_each_store_the_form_it_needs():
    match = duel_match()
    only_duel = MatchOutcome(winner_id="reg-a", score_a=2, score_b=1)
    only_ranking = MatchOutcome(results=[
        {"registration_id": "reg-a", "rank": 1},
        {"registration_id": "reg-b", "rank": 2},
    ])

    assert as_ranking(match, only_duel)[0]["registration_id"] == "reg-a"
    assert as_duel(match, only_ranking)["winner_id"] == "reg-a"
    assert as_duel(match, only_duel)["score_a"] == 2
    assert as_ranking(match, only_ranking) is only_ranking.results
