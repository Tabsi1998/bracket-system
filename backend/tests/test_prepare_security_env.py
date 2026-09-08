import os
import shutil
import subprocess
import sys
import shlex
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") if os.name != "nt" else r"C:\Program Files\Git\bin\bash.exe"
pytestmark = pytest.mark.skipif(not BASH or not Path(BASH).exists(), reason="Bash required")


@pytest.mark.parametrize("scenario,success,created", [
    ("authenticated", True, False),
    ("legacy_empty", True, True),
    ("bad_password", False, False),
    ("existing_other_admin", False, False),
    ("unreachable", False, False),
    ("create_denied", False, True),
])
def test_repeated_updates_authenticate_before_bootstrap(tmp_path, scenario, success, created):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "bin").mkdir()
    shutil.copyfile(REPO / "scripts/prepare-security-env.sh", tmp_path / "scripts/prepare-security-env.sh")
    original = "SETTINGS_ENCRYPTION_KEY=test-key\nMONGO_USERNAME=test-admin\nMONGO_PASSWORD=test-password\n"
    (tmp_path / ".env").write_text(original, encoding="utf8")
    docker = tmp_path / "bin/docker"
    docker.write_text('''#!/usr/bin/env bash
case "$*" in
  inspect*) printf 'true\\n'; exit 0 ;;
  *admin.auth*) [ "$SCENARIO" = authenticated ]; exit $? ;;
  *usersInfo*)
    case "$SCENARIO" in
      legacy_empty|create_denied) exit 0 ;;
      existing_other_admin) exit 14 ;;
      *) exit 13 ;;
    esac ;;
  *createUser*) touch created; [ "$SCENARIO" != create_denied ]; exit $? ;;
esac
exit 99
''', encoding="utf8", newline="\n")
    docker.chmod(0o755)
    if os.name == "nt":
        python_shim = tmp_path / "bin/python3"
        python_shim.write_text(f'#!/usr/bin/env bash\nexec {shlex.quote(Path(sys.executable).as_posix())} "$@"\n', encoding="utf8", newline="\n")
        python_shim.chmod(0o755)
    # stdin must be detached: a lingering grandchild otherwise keeps the captured
    # pipes open on Windows, so communicate() waits past the timeout even though
    # the script itself already exited.
    result = subprocess.run([BASH, "-c", 'export PATH="$PWD/bin:$PATH"; bash scripts/prepare-security-env.sh </dev/null'],
                            cwd=tmp_path, env={**os.environ, "SCENARIO": scenario},
                            text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=30)
    assert (result.returncode == 0) is success, result.stderr
    assert (tmp_path / "created").exists() is created
    assert "test-password" not in result.stdout + result.stderr
    if not success:
        assert (tmp_path / ".env").read_text(encoding="utf8") == original
