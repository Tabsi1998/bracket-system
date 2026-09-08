"""The safety net for the competition consolidation.

Two write models are being merged into one. After every step of that work the
question is the same: can a user still do everything they could do before? These
tests answer it mechanically instead of by inspection.

They fail when an endpoint disappears, when a new competition endpoint is added
without being classified, and when a known gap is closed without recording it.
The last one is deliberate - closing a gap is progress and should be written
down, not slip through silently.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from routes.match_routes import router as match_router
from routes.tournament_routes import router as tournament_router
from services.competition_capabilities import (
    CAPABILITIES,
    CAPABILITIES_BY_KEY,
    CLASSIC,
    GRAPH,
    declared_endpoints,
    open_gaps,
)
from services.competition_formats import FORMAT_CAPABILITIES


COMPETITION_ROUTERS = (tournament_router, match_router)


def live_endpoints(*routers) -> set[str]:
    found = set()
    for router in routers:
        for route in router.routes:
            for method in sorted(getattr(route, "methods", []) or []):
                if method in {"HEAD", "OPTIONS"}:
                    continue
                found.add(f"{method} {route.path}")
    return found


# ---------------------------------------------------------------- Vollständigkeit

def test_every_declared_endpoint_exists():
    """Nothing in the inventory may vanish unnoticed - this is the core promise."""
    missing = sorted(declared_endpoints() - live_endpoints(*COMPETITION_ROUTERS))
    assert missing == [], (
        "Diese Fähigkeiten sind im Inventar beschrieben, aber im Code nicht mehr vorhanden. "
        "Entweder wurde eine Funktion entfernt, oder das Inventar muss angepasst werden."
    )


def test_every_competition_endpoint_is_classified():
    """A new endpoint has to be classified, otherwise the inventory rots."""
    unclassified = sorted(live_endpoints(*COMPETITION_ROUTERS) - declared_endpoints())
    assert unclassified == [], (
        "Diese Endpunkte gehören zu keiner Fähigkeit im Inventar. "
        "Bitte in services/competition_capabilities.py einordnen."
    )


def test_capability_keys_are_unique():
    keys = [capability.key for capability in CAPABILITIES]
    assert len(keys) == len(set(keys))


def test_every_capability_has_a_german_label_and_engines():
    for capability in CAPABILITIES:
        assert capability.label.strip(), capability.key
        assert capability.endpoints, capability.key
        assert capability.engines, capability.key


# ---------------------------------------------------------------- Bekannte Lücken

EXPECTED_GAPS = {
    "structure.swiss",
    "structure.groups",
}


def test_known_gaps_are_exactly_the_recorded_ones():
    """Block 3 closes these. When one is closed, this set has to shrink with it."""
    assert {capability.key for capability in open_gaps()} == EXPECTED_GAPS


@pytest.mark.parametrize("key", sorted(EXPECTED_GAPS))
def test_each_gap_is_classic_only_today(key):
    capability = CAPABILITIES_BY_KEY[key]
    assert capability.engines == (CLASSIC,), (
        f"{key} gilt als Lücke, ist aber nicht mehr nur klassisch verfuegbar. "
        "Wenn die Lücke geschlossen wurde: Engines hier und EXPECTED_GAPS anpassen."
    )


# ---------------------------------------------------------------- Der entfernte Zwilling

def test_the_duplicated_match_router_stays_gone():
    """In Block 1 entfernt: ein 618-Zeilen-Zwilling von match_routes, der unter
    /api/matches-v2/* dieselben Pfade anbot und von keinem Client aufgerufen
    wurde. Ein zweiter Match-Router waere genau der Zustand, den die
    Vereinheitlichung beseitigen soll - deshalb bleibt die Abwesenheit geprueft.
    """
    routes_dir = pathlib.Path(__file__).resolve().parents[1] / "routes"
    assert not (routes_dir / "match_v2_routes.py").exists(), (
        "Der doppelte Match-Router ist zurueck. Ergebnis-Endpunkte gehoeren in match_routes."
    )

    paths = {path.split(" ", 1)[1] for path in live_endpoints(*COMPETITION_ROUTERS)}
    duplicated = sorted(path for path in paths if path.startswith("/api/matches-v2/"))
    assert duplicated == [], (
        f"Diese Pfade duplizieren den Match-Router erneut: {duplicated}. "
        "Der Leseendpunkt unter /api/tournaments ist davon nicht betroffen."
    )


# ---------------------------------------------------------------- Format-Abgleich

def test_no_format_claims_to_be_write_ready_yet():
    """Guards the migration order: a format may only be marked ready once its

    gaps are closed. If this fails, somebody flipped the flag ahead of the work.
    """
    premature = [key for key, cap in FORMAT_CAPABILITIES.items() if cap.canonical_write_ready]
    assert premature == [], (
        "Diese Formate sind als schreibfertig markiert, obwohl die Vereinheitlichung laeuft: "
        f"{premature}. Vor dem Setzen müssen die Lücken aus EXPECTED_GAPS geschlossen sein."
    )


def test_formats_that_switch_engine_on_rebuild_are_visible():
    """Single/Double start classic and silently move to the graph store on rebuild.

    Block 4 stops that. Until then the behaviour must at least be declared.
    """
    switching = [
        key for key, cap in FORMAT_CAPABILITIES.items()
        if cap.initial_preview_engine == "legacy" and cap.rebuild_engine == "stage"
    ]
    assert sorted(switching) == ["double_elim", "single_elim"], (
        "Die Liste der Formate mit stillem Speicherwechsel hat sich geändert - "
        "das ist genau der Punkt, den Block 4 abstellt."
    )
