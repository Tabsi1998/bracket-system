"""Check repository-local Markdown link targets; remote URLs need separate review."""
import os
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {".git", "node_modules", ".pytest_cache", "dist", "test-results", "playwright-report", ".venv", "__pycache__"}


def main():
    checked = 0
    broken = []
    for directory, children, filenames in os.walk(ROOT):
        children[:] = [name for name in children if name not in IGNORED]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            source = Path(directory) / name
            checked += 1
            content = re.sub(r"```[\s\S]*?```", "", source.read_text(encoding="utf-8"))
            for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", content):
                target = match.group(1).strip().split(' "', 1)[0].strip("<>")
                if target.startswith(("#", "http://", "https://", "mailto:", "app://")):
                    continue
                path = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if path and not (source.parent / path).exists():
                    broken.append(f"{source.relative_to(ROOT)}: {target}")
    for entry in broken:
        print(entry)
    print(f"Checked {checked} Markdown files; {len(broken)} missing local link targets.")
    return int(bool(broken))


if __name__ == "__main__":
    raise SystemExit(main())
