"""The operator inventory is read-only and never presents unknown state as a go-live."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location("staging_preflight", Path(__file__).resolve().parents[2] / "scripts" / "staging-preflight.py")
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def test_memory_reports_available_not_just_unused_pages():
    assert preflight.memory_mib("MemTotal: 8388608 kB\nMemFree: 100 kB\nMemAvailable: 4194304 kB") == {
        "total_mib": 8192, "available_mib": 4096
    }


@pytest.mark.parametrize("output", [None, "unexpected ss output", "LISTEN 0 128 localhost:invalid *:*"])
def test_unknown_ports_are_never_reported_as_free(output):
    assert set(preflight.port_status(output).values()) == {"unknown"}


def test_ipv4_and_ipv6_listeners_are_both_detected():
    output = "LISTEN 0 128 127.0.0.1:13000 0.0.0.0:*\nLISTEN 0 128 [::]:18001 [::]:*"
    assert preflight.port_status(output) == {"13000": "occupied", "18001": "occupied"}


def test_empty_socket_table_is_distinct_from_command_failure():
    assert preflight.port_status("") == {"13000": "free_at_check_time", "18001": "free_at_check_time"}


def test_failed_commands_do_not_leak_stderr(monkeypatch):
    monkeypatch.setattr(preflight.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, "sensitive-output", "sensitive-error"))
    assert preflight.read_command("docker", "version") is None


def test_timeout_is_reported_as_unknown(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 5)
    monkeypatch.setattr(preflight.subprocess, "run", timeout)
    assert preflight.read_command("docker", "version") is None


def test_windows_report_cannot_be_confused_with_server_acceptance(monkeypatch):
    monkeypatch.setattr(preflight.platform, "system", lambda: "Windows")
    monkeypatch.setattr(preflight, "read_command", lambda *args: pytest.fail("No host commands expected on Windows"))
    report = preflight.collect_report()
    assert report["decision"] == "manual_review_required"
    assert report["read_only"] is True
    assert "run_on_the_linux_server" in report["host_checks"]


@pytest.mark.parametrize("override", ["DOCKER_HOST", "DOCKER_CONTEXT", None])
def test_remote_docker_is_not_inspected_or_disclosed(monkeypatch, override):
    monkeypatch.setattr(preflight.platform, "system", lambda: "Linux")
    monkeypatch.setattr(preflight.os, "getloadavg", lambda: (0.1, 0.2, 0.3), raising=False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    if override:
        monkeypatch.setenv(override, "private-remote-canary")
    calls = []
    def read(*args):
        calls.append(args)
        return "ssh://private-remote-canary" if args[:3] == ("docker", "context", "inspect") else None
    monkeypatch.setattr(preflight, "read_command", read)
    report = preflight.collect_report()
    assert report["decision"] == "manual_review_required"
    assert "private-remote-canary" not in str(report)
    assert "containers" not in report
    assert not any(args[:2] in (("docker", "inspect"), ("docker", "info"), ("docker", "version")) for args in calls)


def test_local_docker_only_uses_read_only_commands(monkeypatch):
    monkeypatch.setattr(preflight.platform, "system", lambda: "Linux")
    monkeypatch.setattr(preflight.os, "getloadavg", lambda: (0.1, 0.2, 0.3), raising=False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    calls = []
    def read(*args):
        calls.append(args)
        if args[:3] == ("docker", "context", "inspect"):
            return "unix:///var/run/docker.sock"
        if args[:2] == ("docker", "inspect"):
            return "running/healthy"
        return "" if args[:1] == ("ss",) else None
    monkeypatch.setattr(preflight, "read_command", read)
    report = preflight.collect_report()
    assert report["decision"] == "manual_review_required"
    assert report["docker_target"] == "local_unix_socket"
    assert set(report["containers"]) == set(preflight.CONTAINERS)
    assert set(report["containers"].values()) == {"running/healthy"}
    allowed_prefixes = {
        ("ss", "-H"), ("git", "status"), ("git", "rev-parse"),
        ("docker", "compose"), ("docker", "context"), ("docker", "version"),
        ("docker", "info"), ("docker", "inspect"),
    }
    assert all(args[:2] in allowed_prefixes for args in calls)
    assert ("docker", "compose", "version", "--short") in calls
