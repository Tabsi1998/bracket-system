"""The measurement that has to survive a migration.

The dry run exists to answer one question with numbers: would anything a member
can see come out differently after the tournaments move to one engine. That only
works if the measurement itself is engine-independent - so the central test here
builds the same tournament twice, once in each store, and requires the same
values to come out. If it ever fails, the fingerprint is measuring the storage
instead of the tournament, and the whole dry run would be worthless.

One field deliberately does not pass that test: placements. They genuinely are
answered differently by the two engines today, which is a finding rather than a
bug in the measurement - and the reason the tool reports it before anything moves.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from services.competition_snapshot import build_structure_snapshot
from services.migration_dryrun import (
    compare_reports,
    fingerprint_differences,
    fingerprint_digest,
    match_identity,
    migration_blockers,
    migration_notices,
    standings_order,
    summarize,
    tournament_fingerprint,
    tournament_report,
)


REGISTRATIONS = [
    {"id": "reg-a", "user_id": "u-a", "display_name": "Anna"},
    {"id": "reg-b", "user_id": "u-b", "display_name": "Bert"},
    {"id": "reg-c", "user_id": "u-c", "display_name": "Cem"},
    {"id": "reg-d", "user_id": "u-d", "display_name": "Dana"},
]

TOURNAMENT = {"id": "t1", "slug": "sommer-cup", "title": "Sommer Cup",
              "format": "single_elim", "status": "completed"}


def legacy_match(match_id, round_number, first, second, winner, *, status="completed", **extra):
    return {
        "id": match_id,
        "tournament_id": "t1",
        "bracket": "wb",
        "round": round_number,
        "match_index": 0,
        "status": status,
        "participant_a_id": first,
        "participant_b_id": second,
        "winner_id": winner,
        "loser_id": (second if winner == first else first) if winner else None,
        "score_a": 2 if winner == first else 0,
        "score_b": 2 if winner == second else 0,
        **extra,
    }


def stage_match(match_id, round_number, first, second, winner, *, status="completed", **extra):
    ranked = [winner, second if winner == first else first] if winner else [first, second]
    return {
        "id": match_id,
        "tournament_id": "t1",
        "stage_id": "s1",
        "stage_number": 1,
        "match_key": match_id,
        "section": "wb",
        "round": round_number,
        "order": 1,
        "status": status,
        "match_type": "duel",
        "settings": {"min_players": 2, "match_size": 2},
        "slots": [
            {"slot": 1, "registration_id": first, "status": "filled"},
            {"slot": 2, "registration_id": second, "status": "filled"},
        ],
        "results": [
            {"registration_id": item, "rank": index + 1,
             "score": 2 if index == 0 else 0}
            for index, item in enumerate(ranked)
        ] if winner else [],
        "advancement": [],
        **extra,
    }


def legacy_snapshot(matches):
    return build_structure_snapshot("t1", legacy_matches=matches)


def stage_snapshot(matches):
    return build_structure_snapshot("t1", stage_matches=matches)


# ------------------------------------------------ Die zentrale Zusage

SAME_TOURNAMENT_CLASSIC = [
    legacy_match("m1", 1, "reg-a", "reg-b", "reg-a"),
    legacy_match("m2", 1, "reg-c", "reg-d", "reg-c"),
    legacy_match("m3", 2, "reg-a", "reg-c", "reg-a"),
]
SAME_TOURNAMENT_GRAPH = [
    stage_match("g1", 1, "reg-a", "reg-b", "reg-a"),
    stage_match("g2", 1, "reg-c", "reg-d", "reg-c"),
    stage_match("g3", 2, "reg-a", "reg-c", "reg-a"),
]


@pytest.mark.parametrize("field", ["participants", "match_count", "decided_count",
                                   "results", "standings"])
def test_the_same_tournament_measures_the_same_in_both_stores(field):
    """Der Kern des Trockenlaufs: die Messung gilt dem Turnier, nicht dem Speicher.

    Wenn das hier fällt, misst der Fingerabdruck den Speicher - und der ganze
    Vergleich vorher/nachher wäre wertlos.
    """
    before = tournament_fingerprint(
        TOURNAMENT, legacy_snapshot(SAME_TOURNAMENT_CLASSIC), REGISTRATIONS)
    after = tournament_fingerprint(
        TOURNAMENT, stage_snapshot(SAME_TOURNAMENT_GRAPH), REGISTRATIONS)

    assert before[field] == after[field]


def test_placements_are_the_one_thing_that_does_not_survive_a_move():
    """Ein bewusst festgehaltener Befund, kein Versehen.

    Klassische Turniere beziehen ihre Platzierungen aus dem historischen Feld
    ``final_position`` - und haben gar keine, wenn es leer ist. Graph-Turniere
    leiten sie immer aus der Tabelle ab. Das hängt an Preisen, Profil-Historie,
    Abzeichen und Saisonpunkten, deshalb meldet der Trockenlauf es als Befund,
    statt es beim Umzug einfach passieren zu lassen.
    """
    classic = legacy_snapshot(SAME_TOURNAMENT_CLASSIC)
    graph = stage_snapshot(SAME_TOURNAMENT_GRAPH)

    before = tournament_fingerprint(TOURNAMENT, classic, REGISTRATIONS)
    after = tournament_fingerprint(TOURNAMENT, graph, REGISTRATIONS)

    assert before["placements"] == {}
    assert after["placements"], "Das Graph-System leitet Platzierungen aus der Tabelle ab"

    codes = [notice["code"] for notice in migration_notices(classic, REGISTRATIONS)]
    assert "placements_would_appear" in codes


def test_a_tournament_with_recorded_placements_is_flagged_separately():
    """Feste Platzierungen sind der gefährlichere Fall: sie gehen beim Umzug verloren."""
    matches = [dict(match) for match in SAME_TOURNAMENT_CLASSIC]
    matches[2]["final_position"] = 1

    codes = [notice["code"] for notice
             in migration_notices(legacy_snapshot(matches), REGISTRATIONS)]

    assert "explicit_placements_would_be_replaced" in codes


def test_a_tournament_already_in_the_graph_has_no_placement_risk():
    assert migration_notices(stage_snapshot(SAME_TOURNAMENT_GRAPH), REGISTRATIONS) == []


def test_the_placement_notice_is_not_counted_as_a_defect():
    """Ein Hinweis, der fast jedes Turnier betrifft, würde drei echte Mängel zudecken."""
    row = tournament_report(
        TOURNAMENT, legacy_snapshot(SAME_TOURNAMENT_CLASSIC), REGISTRATIONS)

    assert row["blockers"] == []
    assert row["notices"]
    assert row["ready"] is True


def test_new_match_ids_alone_do_not_count_as_a_change():
    """Eine Migration vergibt neue IDs - daran darf die Messung nicht hängen."""
    first = legacy_snapshot([legacy_match("alt-1", 1, "reg-a", "reg-b", "reg-a")])
    second = legacy_snapshot([legacy_match("neu-99", 1, "reg-a", "reg-b", "reg-a")])

    assert (fingerprint_digest(tournament_fingerprint(TOURNAMENT, first, REGISTRATIONS))
            == fingerprint_digest(tournament_fingerprint(TOURNAMENT, second, REGISTRATIONS)))


def test_a_different_winner_is_caught():
    before = tournament_fingerprint(
        TOURNAMENT, legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", "reg-a")]), REGISTRATIONS)
    after = tournament_fingerprint(
        TOURNAMENT, legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", "reg-b")]), REGISTRATIONS)

    differences = fingerprint_differences(before, after)

    assert any("Sieger" in text for text in differences)
    assert fingerprint_digest(before) != fingerprint_digest(after)


def test_a_lost_match_is_caught():
    before = tournament_fingerprint(TOURNAMENT, legacy_snapshot([
        legacy_match("m1", 1, "reg-a", "reg-b", "reg-a"),
        legacy_match("m2", 1, "reg-c", "reg-d", "reg-c"),
    ]), REGISTRATIONS)
    after = tournament_fingerprint(TOURNAMENT, legacy_snapshot([
        legacy_match("m1", 1, "reg-a", "reg-b", "reg-a"),
    ]), REGISTRATIONS)

    assert any("Anzahl Spiele" in text for text in fingerprint_differences(before, after))


def test_a_changed_table_order_is_caught():
    before = {"standings": ["reg-a", "reg-b"], "results": {}, "placements": {}}
    after = {"standings": ["reg-b", "reg-a"], "results": {}, "placements": {}}

    assert any("Tabellenreihenfolge" in text for text in fingerprint_differences(before, after))


def test_a_changed_placement_is_named_with_its_rank():
    before = {"standings": [], "results": {}, "placements": {"1": "reg-a"}}
    after = {"standings": [], "results": {}, "placements": {"1": "reg-b"}}

    assert fingerprint_differences(before, after) == [
        "Platz 1: vorher reg-a, jetzt reg-b"]


# ------------------------------------------------ Wie ein Spiel benannt wird

def test_a_match_is_named_by_round_and_participants():
    identity = match_identity({
        "round": 2, "section": "wb",
        "slots": [{"registration_id": "reg-b"}, {"registration_id": "reg-a"}],
    })

    assert identity == "2|wb|reg-a,reg-b"


def test_the_participant_order_does_not_matter():
    first = match_identity({"round": 1, "slots": [
        {"registration_id": "reg-a"}, {"registration_id": "reg-b"}]})
    second = match_identity({"round": 1, "slots": [
        {"registration_id": "reg-b"}, {"registration_id": "reg-a"}]})

    assert first == second


# ------------------------------------------------ Befunde

def test_a_clean_tournament_has_nothing_to_report():
    snapshot = legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", "reg-a")])

    assert migration_blockers(TOURNAMENT, snapshot) == []


def test_a_disputed_match_holds_the_tournament_back():
    snapshot = legacy_snapshot([
        legacy_match("m1", 1, "reg-a", "reg-b", None, status="disputed")])

    codes = [blocker["code"] for blocker in migration_blockers(TOURNAMENT, snapshot)]

    assert "open_matches" in codes


def test_a_knockout_match_decided_without_a_winner_is_reported():
    """Den kann der Turnierbaum nicht weiterleiten - das muss vorher auffallen."""
    snapshot = legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", None)])

    codes = [blocker["code"] for blocker in migration_blockers(TOURNAMENT, snapshot)]

    assert "decided_without_winner" in codes


def test_a_draw_in_a_group_stage_is_not_a_finding():
    snapshot = legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", None)])

    codes = [blocker["code"]
             for blocker in migration_blockers({**TOURNAMENT, "format": "groups"}, snapshot)]

    assert "decided_without_winner" not in codes


def test_a_tournament_living_in_both_stores_is_reported():
    snapshot = build_structure_snapshot(
        "t1",
        legacy_matches=[legacy_match("m1", 1, "reg-a", "reg-b", "reg-a")],
        stage_matches=[stage_match("g1", 1, "reg-c", "reg-d", "reg-c")],
    )

    codes = [blocker["code"] for blocker in migration_blockers(TOURNAMENT, snapshot)]

    assert "mixed_source" in codes


def test_a_format_that_lives_outside_the_engines_is_marked_as_such():
    snapshot = legacy_snapshot([])

    codes = [blocker["code"]
             for blocker in migration_blockers({**TOURNAMENT, "format": "time_trial"}, snapshot)]

    assert "external_format" in codes


def test_a_decided_match_without_participants_is_reported():
    orphan = legacy_match("m1", 1, None, None, None)
    orphan["status"] = "completed"
    snapshot = legacy_snapshot([orphan])

    codes = [blocker["code"]
             for blocker in migration_blockers({**TOURNAMENT, "format": "groups"}, snapshot)]

    assert "result_without_participants" in codes


# ------------------------------------------------ Bericht und Vergleich

def test_a_report_names_the_store_and_whether_it_has_to_move():
    snapshot = legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", "reg-a")])

    row = tournament_report(TOURNAMENT, snapshot, REGISTRATIONS)

    assert row["engine"] == "classic"
    assert row["needs_migration"] is True
    assert row["target_engine"] == "graph"
    assert row["ready"] is True


def test_a_tournament_already_in_the_graph_needs_no_migration():
    snapshot = stage_snapshot([stage_match("g1", 1, "reg-a", "reg-b", "reg-a")])

    row = tournament_report(TOURNAMENT, snapshot, REGISTRATIONS)

    assert row["engine"] == "graph"
    assert row["needs_migration"] is False


def test_the_report_carries_no_member_names():
    """Der Bericht soll teilbar sein, ohne Mitgliederdaten weiterzugeben."""
    snapshot = legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", "reg-a")])

    row = tournament_report(TOURNAMENT, snapshot, REGISTRATIONS)

    import json
    text = json.dumps(row, ensure_ascii=False)
    for name in ("Anna", "Bert", "Cem", "Dana"):
        assert name not in text


def test_an_unchanged_run_compares_as_equivalent():
    snapshot = legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", "reg-a")])
    report = {"tournaments": [tournament_report(TOURNAMENT, snapshot, REGISTRATIONS)]}

    result = compare_reports(report, report)

    assert result["equivalent"] is True
    assert result["unchanged"] == 1


def test_a_changed_run_names_the_tournament_and_the_difference():
    before = {"tournaments": [tournament_report(
        TOURNAMENT, legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", "reg-a")]),
        REGISTRATIONS)]}
    after = {"tournaments": [tournament_report(
        TOURNAMENT, legacy_snapshot([legacy_match("m1", 1, "reg-a", "reg-b", "reg-b")]),
        REGISTRATIONS)]}

    result = compare_reports(before, after)

    assert result["equivalent"] is False
    assert result["changed"][0]["title"] == "Sommer Cup"
    assert result["changed"][0]["differences"]


def test_a_tournament_that_vanished_is_reported_as_missing():
    before = {"tournaments": [tournament_report(
        TOURNAMENT, legacy_snapshot([]), REGISTRATIONS)]}

    result = compare_reports(before, {"tournaments": []})

    assert result["changed"][0]["problem"] == "fehlt jetzt"


def test_the_summary_counts_stores_and_findings():
    rows = [
        tournament_report(TOURNAMENT, legacy_snapshot(
            [legacy_match("m1", 1, "reg-a", "reg-b", "reg-a")]), REGISTRATIONS),
        tournament_report(TOURNAMENT, legacy_snapshot(
            [legacy_match("m2", 1, "reg-a", "reg-b", None, status="disputed")]), REGISTRATIONS),
    ]

    summary = summarize(rows)

    assert summary["tournaments"] == 2
    assert summary["by_engine"]["classic"] == 2
    assert summary["blocked"] == 1
    assert summary["blockers"]["open_matches"] == 1


# ------------------------------------------------ Tabellenformen

def test_a_group_table_is_flattened_in_group_order():
    rows = [
        {"group": {"group_key": "A"}, "standings": [
            {"registration_id": "reg-a"}, {"registration_id": "reg-b"}]},
        {"group": {"group_key": "B"}, "standings": [
            {"registration_id": "reg-c"}]},
    ]

    assert standings_order(rows) == ["reg-a", "reg-b", "reg-c"]


def test_a_flat_table_stays_flat():
    assert standings_order([{"registration_id": "reg-a"}]) == ["reg-a"]


@pytest.mark.parametrize("rows", [None, [], [{}]])
def test_an_empty_table_does_not_crash(rows):
    assert standings_order(rows) == []


# ------------------------------------------------ Das Skript selbst

def load_script():
    import importlib.util
    path = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "tournament-migration-dryrun.py"
    spec = importlib.util.spec_from_file_location("dryrun_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScriptCursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, *_args):
        return self

    async def to_list(self, limit):
        return self.rows[:limit]


class ScriptCollection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.writes = 0

    def find(self, query, _projection=None):
        def hit(row):
            for key, value in query.items():
                if key == "$or":
                    if not any(row.get(k) == v for option in value for k, v in option.items()):
                        return False
                elif row.get(key) != value:
                    return False
            return True
        return ScriptCursor([row for row in self.rows if hit(row)])

    async def insert_one(self, document):
        self.writes += 1


class ScriptDb:
    def __init__(self, **collections):
        self._collections = {
            name: ScriptCollection(collections.get(name, ()))
            for name in ("tournaments", "matches", "matches_v2", "tournament_stages",
                         "tournament_registrations", "tournament_groups")
        }

    def __getattr__(self, name):
        return self._collections[name]


def test_the_script_produces_a_report_for_a_stored_tournament():
    """Bevor das jemand auf echten Daten laufen lässt, muss es hier durchlaufen."""
    import asyncio
    script = load_script()
    db = script.ReadOnlyDb(ScriptDb(
        tournaments=[TOURNAMENT],
        matches=SAME_TOURNAMENT_CLASSIC,
        tournament_registrations=REGISTRATIONS,
    ))

    rows = asyncio.run(script.collect(db, limit=None, only=None))

    assert len(rows) == 1
    assert rows[0]["engine"] == "classic"
    assert rows[0]["needs_migration"] is True
    assert rows[0]["decided_count"] == 3
    assert rows[0]["notices"], "Der Platzierungs-Hinweis muss im Bericht auftauchen"


def test_the_script_cannot_write_even_if_someone_adds_a_write_later():
    """Der Schreibschutz ist eine Eigenschaft des Codes, kein Versprechen im Kommentar."""
    import asyncio
    script = load_script()
    inner = ScriptDb(tournaments=[TOURNAMENT])
    db = script.ReadOnlyDb(inner)

    with pytest.raises(script.ReadOnlyViolation):
        asyncio.run(db.tournaments.insert_one({"id": "x"}))
    assert inner.tournaments.writes == 0


def test_the_script_can_be_pointed_at_a_single_tournament():
    import asyncio
    script = load_script()
    db = script.ReadOnlyDb(ScriptDb(
        tournaments=[TOURNAMENT, {**TOURNAMENT, "id": "t2", "slug": "anderes"}],
        tournament_registrations=REGISTRATIONS,
    ))

    rows = asyncio.run(script.collect(db, limit=None, only="sommer-cup"))

    assert [row["id"] for row in rows] == ["t1"]
