"""Shared helpers for building MongoDB filters from user input."""
import re


def safe_regex(value: str | None, max_len: int = 80) -> str:
    """Escape a search term so it matches literally and cannot blow up the regex engine.

    Every search route needs the same two guarantees: a user typing ``a.*b`` looks
    for that exact text, and an overlong term cannot turn into a pathological
    pattern. Keeping one implementation means a fix here reaches all of them.
    """
    return re.escape((value or "").strip()[:max_len])
