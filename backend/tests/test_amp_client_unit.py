"""Translating AMP answers into the fields the server card shows.

The important rule here is the difference between "no data" and "nobody
online". A missing metric must stay missing, otherwise the page would claim
zero players for a server AMP never reported on.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from services.amp_client import AmpClient, AmpError, instance_matches, status_from_amp


def metrics(**entries):
    return {"Metrics": {name: value for name, value in entries.items()}}


def metric(raw, maximum=None):
    entry = {"RawValue": raw}
    if maximum is not None:
        entry["MaxValue"] = maximum
    return entry


# ---------------------------------------------------------------- Übersetzung

def test_a_running_instance_with_players_is_translated():
    result = status_from_amp(
        {"Running": True},
        metrics(**{"Active Users": metric(4, 16), "CPU Usage": metric(23.4), "Memory Usage": metric(2048, 8192)}),
    )

    assert result["status"] == "online"
    assert result["player_count"] == 4
    assert result["max_players"] == 16
    assert result["cpu_percent"] == 23.4
    assert result["memory_percent"] == 25.0


def test_a_stopped_instance_is_offline():
    assert status_from_amp({"Running": False}, metrics())["status"] == "offline"


def test_a_missing_metric_stays_missing():
    """Sonst stünde bei einem Server ohne Rückmeldung faelschlich "0 online"."""
    result = status_from_amp({"Running": True}, metrics())

    assert result["status"] == "online"
    assert "player_count" not in result
    assert "max_players" not in result
    assert "cpu_percent" not in result


def test_an_empty_server_reports_zero_players():
    """Null gemeldete Spieler ist eine Aussage - im Gegensatz zu keiner Meldung."""
    result = status_from_amp({"Running": True}, metrics(**{"Active Users": metric(0, 10)}))

    assert result["player_count"] == 0
    assert result["max_players"] == 10


def test_metric_names_are_matched_regardless_of_spelling():
    result = status_from_amp({"Running": True}, metrics(**{"active users": metric(2, 8)}))

    assert result["player_count"] == 2


def test_a_broken_answer_does_not_raise():
    assert status_from_amp({"Running": True}, {})["status"] == "online"
    assert status_from_amp({}, {"Metrics": "kaputt"})["status"] == "offline"


def test_memory_without_a_maximum_yields_no_percentage():
    result = status_from_amp({"Running": True}, metrics(**{"Memory Usage": metric(2048)}))

    assert "memory_percent" not in result


# ---------------------------------------------------------------- Zuordnung

@pytest.mark.parametrize("wanted", ["ark-01", "ARK-01", "  ark-01  ", "ARK Mitgliederserver"])
def test_an_instance_is_found_by_name_or_id(wanted):
    instance = {"InstanceID": "ark-01", "FriendlyName": "ARK Mitgliederserver"}

    assert instance_matches(instance, wanted) is True


@pytest.mark.parametrize("wanted", ["", None, "rust-01"])
def test_a_wrong_or_empty_reference_matches_nothing(wanted):
    assert instance_matches({"InstanceID": "ark-01"}, wanted) is False


# ---------------------------------------------------------------- Konfiguration

@pytest.mark.parametrize("args", [
    ("", "user", "pass"),
    ("https://amp.example.test", "", "pass"),
    ("https://amp.example.test", "user", ""),
])
def test_incomplete_configuration_is_rejected_early(args):
    with pytest.raises(AmpError):
        AmpClient(*args)
