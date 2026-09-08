"""Production backups must not silently stay on the same host they protect."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
POLICY = REPO / "scripts" / "backup-offsite-policy.sh"
BASH = shutil.which("bash") if os.name != "nt" else r"C:\Program Files\Git\bin\bash.exe"
pytestmark = pytest.mark.skipif(not BASH or not Path(BASH).exists(), reason="Bash required")


def run_policy(snippet, cwd=None, env=None):
    script = f'set -eu; source "{POLICY.as_posix()}"; {snippet}'
    return subprocess.run(
        [BASH, "-c", script],
        cwd=cwd or REPO,
        env={**os.environ, **(env or {})},
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )


@pytest.mark.parametrize("remote,app_env,optional", [
    ("gdrive:tls-backups", "production", "false"),
    ("gdrive:tls-backups", "staging", "false"),
    ("", "staging", "false"),
    ("", "", "false"),
    ("", "production", "true"),
])
def test_allowed_combinations_continue(remote, app_env, optional):
    result = run_policy(f'offsite_backup_allowed "{remote}" "{app_env}" "{optional}"')
    assert result.returncode == 0, result.stderr


def test_production_without_remote_stops_the_run():
    result = run_policy('offsite_backup_allowed "" "production" "false"')
    assert result.returncode == 1
    assert "BACKUP_REMOTE" in result.stdout
    assert "BACKUP_REMOTE_OPTIONAL=true" in result.stdout


def test_explicit_opt_out_is_reported_but_allowed():
    result = run_policy('offsite_backup_allowed "" "production" "true"; echo "continued"')
    assert result.returncode == 0
    assert "continued" in result.stdout


def test_app_env_is_read_from_env_file(tmp_path):
    (tmp_path / ".env").write_text('APP_ENV="production"\nJWT_SECRET=irrelevant\n', encoding="utf8", newline="\n")
    result = run_policy('printf "%s" "$(resolve_app_env .env)"', cwd=tmp_path, env={"APP_ENV": ""})
    assert result.stdout == "production"


def test_environment_wins_over_env_file(tmp_path):
    (tmp_path / ".env").write_text("APP_ENV=production\n", encoding="utf8", newline="\n")
    result = run_policy('printf "%s" "$(resolve_app_env .env)"', cwd=tmp_path, env={"APP_ENV": "staging"})
    assert result.stdout == "staging"


def test_missing_env_file_resolves_empty(tmp_path):
    result = run_policy('printf "%s" "$(resolve_app_env .env)"', cwd=tmp_path, env={"APP_ENV": ""})
    assert result.stdout == ""


def test_env_file_secrets_do_not_leak_into_the_shell(tmp_path):
    """resolve_app_env must read the file, never source it."""
    (tmp_path / ".env").write_text("APP_ENV=production\nJWT_SECRET=super-secret-value\n", encoding="utf8", newline="\n")
    result = run_policy('resolve_app_env .env >/dev/null; printf "%s" "${JWT_SECRET:-unset}"', cwd=tmp_path, env={"APP_ENV": ""})
    assert result.stdout == "unset"
