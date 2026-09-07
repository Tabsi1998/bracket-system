from services.team_levels import top_team_id


def test_top_team_id_requires_positive_points():
    assert top_team_id({}) is None
    assert top_team_id({"zero": {"team_id": "zero", "points": 0}}) is None


def test_top_team_id_uses_stable_ranking_and_tie_breakers():
    teams = {
        "lower": {"team_id": "lower", "points": 99, "level": 10, "name": "A"},
        "zeta": {"team_id": "zeta", "points": 100, "level": 10, "name": "Beta"},
        "beta": {"team_id": "beta", "points": 100, "level": 10, "name": "Alpha"},
        "alpha": {"team_id": "alpha", "points": 100, "level": 10, "name": "Alpha"},
    }

    assert top_team_id(teams) == "alpha"
