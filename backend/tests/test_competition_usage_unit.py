"""The measurement must never cost a tournament operation.

Recording which engine wrote is useful, but it is bookkeeping. If the bookkeeping
fails, the result entry it accompanies still has to succeed - otherwise a
monitoring feature would become an outage. These tests pin that guarantee.
"""
import asyncio
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from services import competition_usage
from services.competition_usage import CLASSIC, GRAPH, engine_for_match


class _ExplodingCollection:
    async def insert_one(self, _document):
        raise RuntimeError("Datenbank nicht erreichbar")


class _ExplodingDb:
    def __getitem__(self, _name):
        return _ExplodingCollection()


class _RecordingCollection:
    def __init__(self):
        self.documents = []

    async def insert_one(self, document):
        self.documents.append(document)


class _RecordingDb:
    def __init__(self):
        self.collection = _RecordingCollection()

    def __getitem__(self, _name):
        return self.collection


# ---------------------------------------------------------------- Engine-Erkennung

@pytest.mark.parametrize("match,expected", [
    ({"stage_id": "s1"}, GRAPH),
    ({"slots": []}, GRAPH),
    ({"participant_a_id": "r1", "participant_b_id": "r2"}, CLASSIC),
    ({"score_a": 3, "score_b": 1}, CLASSIC),
    ({"id": "m1"}, "unknown"),
    (None, "unknown"),
])
def test_engine_is_derived_from_the_match_shape(match, expected):
    assert engine_for_match(match) == expected


def test_a_graph_match_is_not_mistaken_for_a_classic_one():
    """Graph matches may still carry legacy-looking fields; the stage decides."""
    mixed = {"stage_id": "s1", "score_a": 2}
    assert engine_for_match(mixed) == GRAPH


# ---------------------------------------------------------------- Ausfallsicherheit

def test_a_failing_database_does_not_raise(monkeypatch):
    monkeypatch.setattr(competition_usage, "get_db", lambda: _ExplodingDb())

    asyncio.run(competition_usage.record_write(CLASSIC, "match.result.update", tournament_id="t1"))


def test_a_missing_database_does_not_raise(monkeypatch):
    def boom():
        raise RuntimeError("keine Verbindung")

    monkeypatch.setattr(competition_usage, "get_db", boom)

    asyncio.run(competition_usage.record_write(GRAPH, "match.result.update"))


# ---------------------------------------------------------------- Inhalt

def test_the_recorded_entry_carries_what_the_decision_needs(monkeypatch):
    db = _RecordingDb()
    monkeypatch.setattr(competition_usage, "get_db", lambda: db)

    asyncio.run(competition_usage.record_write(
        CLASSIC, "match.forfeit", tournament_id="t1", format_key="single_elim", detail="force",
    ))

    assert len(db.collection.documents) == 1
    entry = db.collection.documents[0]
    assert entry["engine"] == CLASSIC
    assert entry["capability"] == "match.forfeit"
    assert entry["tournament_id"] == "t1"
    assert entry["format"] == "single_elim"
    assert entry["created_at"] is not None
