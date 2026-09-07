"""Backup/restore targets must not cross production and staging projects."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "compose_backup_target", Path(__file__).resolve().parents[2] / "scripts" / "compose-backup-target.py"
)
target_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target_module)


def compose_config(project="tls-staging", database="tls_arena_staging"):
    return {
        "services": {"backend": {
            "environment": {"DB_NAME": database, "UPLOAD_DIR": "/app/backend/uploads"},
            "volumes": [{"type": "volume", "source": "uploads_data", "target": "/app/backend/uploads"}],
        }},
        "volumes": {"uploads_data": {"name": f"{project}_uploads_data"}},
    }


@pytest.mark.parametrize("project,database", [("tls-staging", "tls_arena_staging"), ("production", "tls_arena")])
def test_resolves_only_the_selected_project(project, database):
    assert target_module.resolve_target(compose_config(project, database)) == (database, f"{project}_uploads_data")


def test_explicit_matching_targets_are_allowed():
    assert target_module.resolve_target(compose_config(), "tls_arena_staging", "tls-staging_uploads_data") == (
        "tls_arena_staging", "tls-staging_uploads_data"
    )


@pytest.mark.parametrize("database,volume", [("tls_arena", ""), ("", "production_uploads_data")])
def test_rejects_cross_project_overrides(database, volume):
    with pytest.raises(ValueError):
        target_module.resolve_target(compose_config(), database, volume)


@pytest.mark.parametrize("change", ["bind", "external", "duplicate", "missing", "wrong_path", "unsafe_db", "unsafe_volume"])
def test_rejects_unsafe_or_ambiguous_targets(change):
    config = compose_config()
    backend = config["services"]["backend"]
    if change == "bind":
        backend["volumes"][0]["type"] = "bind"
    elif change == "external":
        config["volumes"]["uploads_data"]["external"] = True
    elif change == "duplicate":
        backend["volumes"].append(dict(backend["volumes"][0]))
    elif change == "missing":
        backend["volumes"] = []
    elif change == "wrong_path":
        backend["environment"]["UPLOAD_DIR"] = "/different/path"
    elif change == "unsafe_db":
        backend["environment"]["DB_NAME"] = "name\ninjected"
    elif change == "unsafe_volume":
        config["volumes"]["uploads_data"]["name"] = "/host/path"
    with pytest.raises(ValueError):
        target_module.resolve_target(config)


def test_custom_upload_destination_is_resolved():
    config = compose_config()
    config["services"]["backend"]["environment"]["UPLOAD_DIR"] = "/data/uploads"
    config["services"]["backend"]["volumes"][0]["target"] = "/data/uploads"
    assert target_module.resolve_target(config)[1] == "tls-staging_uploads_data"


@pytest.mark.parametrize("payload", ["not-json-sensitive-canary", '{"password":"sensitive-canary"}', "[]"])
def test_cli_rejects_malformed_config_without_leaking_input(payload):
    result = subprocess.run(
        [sys.executable, str(spec.origin)], input=payload, text=True, capture_output=True, check=False
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "sensitive-canary" not in result.stderr
    assert "Backup target rejected" in result.stderr


def test_cli_outputs_only_validated_targets():
    result = subprocess.run(
        [sys.executable, str(spec.origin), "--db", "tls_arena_staging", "--volume", "tls-staging_uploads_data"],
        input=json.dumps(compose_config()), text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["tls_arena_staging", "tls-staging_uploads_data"]
    assert result.stderr == ""
