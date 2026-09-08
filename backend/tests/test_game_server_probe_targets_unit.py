"""Game-server probes must not be pointed at the platform itself or at metadata endpoints."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from services import game_server_status
from services.game_server_status import (
    GameServerProbeError,
    ensure_probe_target_allowed,
    probe_target_block_reason,
)


@pytest.mark.parametrize("host", [
    "127.0.0.1",
    "127.0.0.53",
    "::1",
    "::ffff:127.0.0.1",
    "169.254.169.254",
    "169.254.1.1",
    "fe80::1",
    "0.0.0.0",
    "224.0.0.1",
    "",
])
def test_blocked_targets_are_refused(host):
    assert probe_target_block_reason(host) is not None


@pytest.mark.parametrize("host", [
    "192.168.2.106",
    "10.10.0.5",
    "172.20.1.9",
    "fd00::5",
    "45.83.104.10",
])
def test_lan_and_public_targets_stay_allowed(host):
    """Internal sync addresses are a documented setup and must keep working."""
    assert probe_target_block_reason(host) is None


def test_hostname_resolving_to_loopback_is_blocked(monkeypatch):
    monkeypatch.setattr(game_server_status, "_resolve_host_sync", lambda host: ["127.0.0.1"])
    assert probe_target_block_reason("sneaky.example.com") is not None


def test_hostname_resolving_to_lan_is_allowed(monkeypatch):
    monkeypatch.setattr(game_server_status, "_resolve_host_sync", lambda host: ["192.168.2.106"])
    assert probe_target_block_reason("mc.lan.example.com") is None


def test_unresolvable_hostname_is_left_to_the_probe(monkeypatch):
    """A DNS failure should surface as the probe's own DNS error, not as a block."""
    def boom(host):
        raise OSError("name or service not known")

    monkeypatch.setattr(game_server_status, "_resolve_host_sync", boom)
    assert probe_target_block_reason("does-not-exist.example.com") is None


def test_ensure_raises_for_blocked_target():
    with pytest.raises(GameServerProbeError):
        ensure_probe_target_allowed("169.254.169.254")


def test_tcp_probe_refuses_loopback_without_opening_a_socket(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("probe must not open a connection to a blocked target")

    monkeypatch.setattr(game_server_status.socket, "create_connection", fail_if_called)
    with pytest.raises(GameServerProbeError):
        game_server_status._tcp_reachable_sync("127.0.0.1", 8001, 1.0)


def test_minecraft_probe_refuses_metadata_address(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("probe must not open a connection to a blocked target")

    monkeypatch.setattr(game_server_status.socket, "create_connection", fail_if_called)
    with pytest.raises(GameServerProbeError):
        game_server_status._minecraft_status_sync("169.254.169.254", 25565, 1.0)
