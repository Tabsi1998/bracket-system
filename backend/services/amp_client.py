"""Read-only client for a CubeCoders AMP panel.

Why this exists: the public status query only works for games that speak a
public protocol. Palworld and Windrose do not, ARK and Rust only on a port that
is often closed - so those servers show nothing useful no matter how good the
parser is.

AMP knows all of them, because it runs them. Its own interface reports the same
figures for every instance regardless of the game: running or not, players
current and maximum, and the real CPU and memory load. That is exactly what the
public query cannot deliver.

Deliberately read-only. Starting or stopping a server from the website is not a
feature anybody asked for, and a panel session that can only look is a much
smaller risk if it ever leaks.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("tls.amp")

REQUEST_TIMEOUT = 8.0


class AmpError(RuntimeError):
    """The panel could not be reached or refused the request."""


def _endpoint(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/API/{path.lstrip('/')}"


def _metric_value(metrics: dict, name: str) -> tuple[float | None, float | None]:
    """Pull one metric out of AMP's status answer.

    The panel reports metrics as a mapping of display name to a small object
    with the current and maximum value. Names differ slightly between AMP
    versions, so the lookup is case-insensitive and tolerant of absence.
    """
    if not isinstance(metrics, dict):
        return None, None
    wanted = name.strip().lower()
    for key, entry in metrics.items():
        if str(key).strip().lower() != wanted or not isinstance(entry, dict):
            continue
        raw = entry.get("RawValue")
        maximum = entry.get("MaxValue")
        return (
            float(raw) if isinstance(raw, (int, float)) else None,
            float(maximum) if isinstance(maximum, (int, float)) else None,
        )
    return None, None


class AmpClient:
    """One panel session, used for a single sync run."""

    def __init__(self, base_url: str, username: str, password: str):
        if not base_url or not username or not password:
            raise AmpError("AMP-Zugang ist unvollständig konfiguriert.")
        self.base_url = base_url
        self.username = username
        self.password = password
        self.session_id: str | None = None

    async def __aenter__(self) -> "AmpClient":
        self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        await self.login()
        return self

    async def __aexit__(self, *_exc_info) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            response = await self._client.post(_endpoint(self.base_url, path), json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise AmpError(f"AMP nicht erreichbar: {type(exc).__name__}") from exc
        except ValueError as exc:
            raise AmpError("AMP hat keine verwertbare Antwort geliefert.") from exc

    async def login(self) -> str:
        data = await self._post("Core/Login", {
            "username": self.username,
            "password": self.password,
            "token": "",
            "rememberMe": False,
        })
        session_id = (data or {}).get("sessionID")
        if not session_id or (data or {}).get("success") is False:
            raise AmpError("AMP-Anmeldung abgelehnt.")
        self.session_id = session_id
        return session_id

    async def instances(self) -> list[dict]:
        """All instances the panel knows, flattened across its targets."""
        data = await self._post("ADSModule/GetInstances", {"SESSIONID": self.session_id})
        targets = data if isinstance(data, list) else (data or {}).get("result") or []
        found: list[dict] = []
        for target in targets:
            for instance in (target or {}).get("AvailableInstances") or []:
                if isinstance(instance, dict):
                    found.append(instance)
        return found

    async def instance_status(self, instance_id: str) -> dict:
        data = await self._post(
            f"ADSModule/Servers/{instance_id}/API/Core/GetStatus",
            {"SESSIONID": self.session_id},
        )
        return data if isinstance(data, dict) else {}


def instance_matches(instance: dict, wanted: str) -> bool:
    """Find the panel instance an entry on the website refers to.

    Matching is by name or id and case-insensitive, so an operator can enter
    whichever of the two they see in front of them in AMP.
    """
    needle = str(wanted or "").strip().lower()
    if not needle:
        return False
    for field in ("InstanceID", "InstanceName", "FriendlyName"):
        if str(instance.get(field) or "").strip().lower() == needle:
            return True
    return False


def status_from_amp(instance: dict, status: dict) -> dict:
    """Translate one AMP answer into the fields the server card shows.

    Only what AMP genuinely knows is returned. A missing metric stays absent
    rather than being reported as zero - "no data" and "nobody online" must not
    look the same on the page.
    """
    running = bool(instance.get("Running"))
    metrics = (status or {}).get("Metrics") or {}
    players, max_players = _metric_value(metrics, "Active Users")
    cpu, _cpu_max = _metric_value(metrics, "CPU Usage")
    memory, memory_max = _metric_value(metrics, "Memory Usage")

    result: dict[str, Any] = {
        "status": "online" if running else "offline",
        "sync_note": "Werte aus AMP.",
    }
    if players is not None:
        result["player_count"] = int(players)
    if max_players:
        result["max_players"] = int(max_players)
    if cpu is not None:
        result["cpu_percent"] = round(cpu, 1)
    if memory is not None and memory_max:
        result["memory_percent"] = round(memory / memory_max * 100, 1)
    return result
