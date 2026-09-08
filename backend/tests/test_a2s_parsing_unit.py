"""What the status query actually delivers - and what used to be thrown away.

The old parser stopped after the player counts. Everything behind it, above all
the version string and the keyword field, was discarded even though it had
already been received. These tests build synthetic answers byte by byte, so the
parsing can be checked without a game server.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from services.game_server_status import (
    GameServerProbeError,
    parse_a2s_info,
    parse_a2s_players,
    parse_a2s_rules,
    suggested_query_port,
)


def _string(value: str) -> bytes:
    return value.encode("utf-8") + b"\x00"


def build_info(
    *,
    name="TLS Server",
    map_name="Navezgane",
    folder="7dtd",
    game="7 Days To Die",
    players=3,
    max_players=8,
    bots=0,
    password=False,
    vac=True,
    version="1.4.2",
    keywords=None,
    truncate_after=None,
) -> bytes:
    payload = b"\xff\xff\xff\xff\x49" + bytes([17])
    payload += _string(name) + _string(map_name) + _string(folder) + _string(game)
    payload += (251).to_bytes(2, "little")
    payload += bytes([players, max_players, bots])
    payload += b"d"  # Servertyp
    payload += b"l"  # Betriebssystem
    payload += bytes([1 if password else 0, 1 if vac else 0])
    payload += _string(version)
    if keywords is not None:
        payload += bytes([0x20]) + _string(keywords)
    else:
        payload += bytes([0x00])
    return payload[:truncate_after] if truncate_after else payload


def test_the_basic_facts_are_read():
    info = parse_a2s_info(build_info())

    assert info["status"] == "online"
    assert info["name"] == "TLS Server"
    assert info["map_name"] == "Navezgane"
    assert info["player_count"] == 3
    assert info["max_players"] == 8


def test_the_version_is_no_longer_discarded():
    """Genau das Feld, das 7 Days To Die bisher fehlte."""
    assert parse_a2s_info(build_info(version="1.4.2"))["version"] == "1.4.2"


def test_server_tags_are_read_and_split():
    """Hier transportieren ARK, Rust und 7DTD ihre Mods und Einstellungen."""
    info = parse_a2s_info(build_info(keywords="pvp,mods=12,build=4711"))

    assert info["server_tags"] == ["pvp", "mods=12", "build=4711"]


def test_password_and_protection_flags_are_read():
    info = parse_a2s_info(build_info(password=True, vac=False, bots=2))

    assert info["password_protected"] is True
    assert info["vac_enabled"] is False
    assert info["bot_count"] == 2


def test_a_server_without_keywords_simply_has_none():
    assert "server_tags" not in parse_a2s_info(build_info(keywords=None))


def test_a_truncated_answer_yields_fewer_fields_instead_of_an_error():
    """Ältere oder sparsame Server antworten kürzer - das darf die Abfrage nicht

    scheitern lassen, solange die Grunddaten gelesen werden konnten.
    """
    full = build_info()
    cut = full.index(_string("1.4.2"))
    info = parse_a2s_info(build_info(truncate_after=cut))

    assert info["player_count"] == 3
    assert "version" not in info


@pytest.mark.parametrize("payload", [b"", b"\xff\xff\xff\xff", b"\xff\xff\xff\xffX"])
def test_a_wrong_answer_is_rejected(payload):
    with pytest.raises(GameServerProbeError):
        parse_a2s_info(payload)


# ---------------------------------------------------------------- Regeln

def test_rules_are_read_as_key_value_pairs():
    payload = b"\xff\xff\xff\xff\x45" + (2).to_bytes(2, "little")
    payload += _string("GameDifficulty") + _string("3")
    payload += _string("DayCount") + _string("42")

    assert parse_a2s_rules(payload) == {"GameDifficulty": "3", "DayCount": "42"}


def test_a_truncated_rule_list_returns_what_was_readable():
    payload = b"\xff\xff\xff\xff\x45" + (5).to_bytes(2, "little")
    payload += _string("Seed") + _string("12345")

    assert parse_a2s_rules(payload) == {"Seed": "12345"}


def test_a_wrong_rules_answer_is_rejected():
    with pytest.raises(GameServerProbeError):
        parse_a2s_rules(b"\xff\xff\xff\xff\x49")


# ---------------------------------------------------------------- Spielerliste

def test_player_names_are_read():
    payload = b"\xff\xff\xff\xff\x44" + bytes([2])
    for name in ("Lion", "Squad"):
        payload += bytes([0]) + _string(name) + b"\x00" * 8

    assert parse_a2s_players(payload) == ["Lion", "Squad"]


def test_an_empty_server_has_no_players():
    assert parse_a2s_players(b"\xff\xff\xff\xff\x44" + bytes([0])) == []


# ---------------------------------------------------------------- Query-Port

@pytest.mark.parametrize("server,expected", [
    ({"query_port": 27020, "game_name": "Rust"}, 27020),
    ({"game_name": "Rust"}, 28016),
    ({"game_name": "ARK Survival Evolved"}, 27015),
    ({"name": "7 Days To Die Mitgliederserver"}, 26900),
    ({"address": "ark.lionsquad.at:7777"}, 27015),
    ({"address": "rust.lionsquad.at:28015"}, 28016),
    ({"game_name": "Windrose"}, None),
])
def test_the_usual_status_port_is_suggested(server, expected):
    assert suggested_query_port(server) == expected


def test_an_explicit_port_always_wins():
    """Der Betreiber kennt sein Setup besser als eine Tabelle."""
    assert suggested_query_port({"query_port": 12345, "game_name": "ARK"}) == 12345
