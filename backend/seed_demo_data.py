#!/usr/bin/env python3
"""Seed deterministic demo data for local/prod previews."""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def demo_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"arena-demo:{name}"))


def hash_password(value: str) -> str:
    return bcrypt.hashpw(value.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def normalize_email(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").lower()


def load_db() -> Tuple[MongoClient, str]:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name = os.environ.get("DB_NAME", "").strip()
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL oder DB_NAME fehlt in backend/.env")
    client = MongoClient(mongo_url)
    return client, db_name


def ensure_fallback_game(db) -> Dict:
    fallback = {
        "id": demo_id("game:demo"),
        "name": "Demo Arena",
        "short_name": "Demo",
        "category": "other",
        "image_url": "",
        "modes": [{"name": "2v2", "team_size": 2, "description": "Demo Mode"}],
        "platforms": ["PC"],
        "is_custom": True,
        "is_demo": True,
        "created_at": now_iso(),
    }
    db.games.update_one({"id": fallback["id"]}, {"$set": fallback}, upsert=True)
    return fallback


def choose_game(games: List[Dict], preferred_names: List[str]) -> Dict:
    for wanted in preferred_names:
        for game in games:
            if game.get("name") == wanted:
                return game
    return games[0] if games else {}


def pick_mode_name(game: Dict, team_size: int) -> str:
    for mode in game.get("modes", []):
        if int(mode.get("team_size", 0) or 0) == team_size:
            return str(mode.get("name", "") or "")
    return f"{team_size}v{team_size}"


def build_members(user_map: Dict[str, Dict], owner_key: str, leaders: List[str], members: List[str]) -> List[Dict]:
    snapshots = []
    for key in members:
        user = user_map[key]
        role = "member"
        if key == owner_key:
            role = "owner"
        elif key in leaders:
            role = "leader"
        snapshots.append(
            {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": role,
            }
        )
    return snapshots


def players_for(team_members: List[Dict], team_size: int = 2) -> List[Dict]:
    picked = []
    for member in team_members[:team_size]:
        picked.append({"name": member["username"], "email": member["email"]})
    while len(picked) < team_size:
        idx = len(picked) + 1
        picked.append({"name": f"Demo Spieler {idx}", "email": f"demo.player{idx}@arena.gg"})
    return picked


def iso_from_now(days: int = 0) -> str:
    return (now_utc() + timedelta(days=days)).isoformat()


def seed_demo_data(reset: bool = False) -> None:
    client, db_name = load_db()
    db = client[db_name]
    ts = now_iso()

    if reset:
        db.registrations.delete_many({"is_demo": True})
        db.tournaments.delete_many({"is_demo": True})
        db.teams.delete_many({"is_demo": True})
        db.users.delete_many({"is_demo": True})

    demo_password = os.environ.get("DEMO_USER_PASSWORD", "demo123")
    common_hash = hash_password(demo_password)

    user_specs = [
        {"key": "admin", "username": "DemoAdmin", "email": "demo.admin@arena.gg", "role": "admin"},
        {"key": "manager", "username": "DemoManager", "email": "demo.manager@arena.gg", "role": "user"},
        {"key": "alpha1", "username": "AlphaOne", "email": "demo.alpha1@arena.gg", "role": "user"},
        {"key": "alpha2", "username": "AlphaTwo", "email": "demo.alpha2@arena.gg", "role": "user"},
        {"key": "bravo1", "username": "BravoOne", "email": "demo.bravo1@arena.gg", "role": "user"},
        {"key": "bravo2", "username": "BravoTwo", "email": "demo.bravo2@arena.gg", "role": "user"},
        {"key": "nova1", "username": "NovaOne", "email": "demo.nova1@arena.gg", "role": "user"},
        {"key": "nova2", "username": "NovaTwo", "email": "demo.nova2@arena.gg", "role": "user"},
        {"key": "charlie1", "username": "CharlieOne", "email": "demo.charlie1@arena.gg", "role": "user"},
        {"key": "charlie2", "username": "CharlieTwo", "email": "demo.charlie2@arena.gg", "role": "user"},
    ]

    users: Dict[str, Dict] = {}
    for spec in user_specs:
        uid = demo_id(f"user:{spec['key']}")
        email = normalize_email(spec["email"])
        payload = {
            "id": uid,
            "username": spec["username"],
            "email": email,
            "role": spec["role"],
            "password_hash": common_hash,
            "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={spec['username']}",
            "banner_url": f"https://images.unsplash.com/photo-1542751110-97427bbecf20?w=1400&seed={spec['key']}",
            "bio": "Demo-Benutzer für Showcase und Tests.",
            "discord_url": "https://discord.gg/demo",
            "website_url": "https://arena.gg",
            "twitter_url": "https://x.com/arena",
            "instagram_url": "https://instagram.com/arena",
            "twitch_url": "https://twitch.tv/arena",
            "youtube_url": "https://youtube.com/@arena",
            "is_demo": True,
            "updated_at": ts,
            "last_login_at": None,
            "last_login_ip": None,
        }
        db.users.update_one(
            {"id": uid},
            {
                "$set": payload,
                "$setOnInsert": {"created_at": ts},
                "$unset": {"password": ""},
            },
            upsert=True,
        )
        users[spec["key"]] = {**payload, "created_at": ts}

    team_specs = [
        {
            "key": "ares_main",
            "name": "ARES Organization",
            "tag": "ARES",
            "owner_key": "manager",
            "leaders": ["manager"],
            "members": ["manager", "alpha1", "alpha2", "bravo1", "bravo2", "charlie1", "charlie2"],
            "parent_key": None,
            "join_code": "ARES01",
            "logo_url": "https://images.unsplash.com/photo-1511884642898-4c92249e20b6?w=300",
            "banner_url": "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=1400",
        },
        {
            "key": "nova_main",
            "name": "NOVA Clan",
            "tag": "NOVA",
            "owner_key": "nova1",
            "leaders": ["nova1"],
            "members": ["nova1", "nova2"],
            "parent_key": None,
            "join_code": "NOVA01",
            "logo_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=300",
            "banner_url": "https://images.unsplash.com/photo-1542751110-97427bbecf20?w=1400",
        },
        {
            "key": "ares_alpha",
            "name": "ARES Alpha",
            "tag": "A-A",
            "owner_key": "alpha1",
            "leaders": ["alpha1"],
            "members": ["alpha1", "alpha2"],
            "parent_key": "ares_main",
            "join_code": "ARSA11",
            "logo_url": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=300",
            "banner_url": "https://images.unsplash.com/photo-1486572788966-cfd3df1f5b42?w=1400",
        },
        {
            "key": "ares_bravo",
            "name": "ARES Bravo",
            "tag": "A-B",
            "owner_key": "bravo1",
            "leaders": ["bravo1"],
            "members": ["bravo1", "bravo2"],
            "parent_key": "ares_main",
            "join_code": "ARSB11",
            "logo_url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=300",
            "banner_url": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=1400",
        },
        {
            "key": "ares_charlie",
            "name": "ARES Charlie",
            "tag": "A-C",
            "owner_key": "charlie1",
            "leaders": ["charlie1"],
            "members": ["charlie1", "charlie2"],
            "parent_key": "ares_main",
            "join_code": "ARSC11",
            "logo_url": "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=300",
            "banner_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1400",
        },
        {
            "key": "nova_prime",
            "name": "NOVA Prime",
            "tag": "N-P",
            "owner_key": "nova1",
            "leaders": ["nova1"],
            "members": ["nova1", "nova2"],
            "parent_key": "nova_main",
            "join_code": "NOVA11",
            "logo_url": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=300",
            "banner_url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085?w=1400",
        },
    ]

    teams: Dict[str, Dict] = {}
    for spec in team_specs:
        team_id = demo_id(f"team:{spec['key']}")
        parent_id = demo_id(f"team:{spec['parent_key']}") if spec.get("parent_key") else None
        owner = users[spec["owner_key"]]
        member_docs = [users[k] for k in spec["members"]]
        member_ids = [m["id"] for m in member_docs]
        leader_ids = [users[k]["id"] for k in spec["leaders"]]
        team_doc = {
            "id": team_id,
            "name": spec["name"],
            "tag": spec["tag"],
            "owner_id": owner["id"],
            "owner_name": owner["username"],
            "join_code": spec["join_code"],
            "member_ids": member_ids,
            "leader_ids": leader_ids,
            "members": build_members(users, spec["owner_key"], spec["leaders"], spec["members"]),
            "parent_team_id": parent_id,
            "bio": f"{spec['name']} ist ein Demo-Team für die Vorschau.",
            "logo_url": spec["logo_url"],
            "banner_url": spec["banner_url"],
            "discord_url": "https://discord.gg/demo",
            "website_url": "https://arena.gg",
            "twitter_url": "https://x.com/arena",
            "instagram_url": "https://instagram.com/arena",
            "twitch_url": "https://twitch.tv/arena",
            "youtube_url": "https://youtube.com/@arena",
            "is_demo": True,
            "updated_at": ts,
        }
        db.teams.update_one(
            {"id": team_id},
            {"$set": team_doc, "$setOnInsert": {"created_at": ts}},
            upsert=True,
        )
        teams[spec["key"]] = team_doc

    games = list(db.games.find({}, {"_id": 0, "id": 1, "name": 1, "modes": 1}))
    if not games:
        games = [ensure_fallback_game(db)]

    game_single = choose_game(games, ["Counter-Strike 2", "Valorant", "Call of Duty"])
    game_league = choose_game(games, ["Call of Duty", "Rocket League", "EA FC (FIFA)"])
    game_groups = choose_game(games, ["Rocket League", "EA FC (FIFA)", "Counter-Strike 2"])

    tournament_specs = [
        {
            "key": "open_single",
            "name": "Demo Open Cup (Single)",
            "status": "registration",
            "bracket_type": "single_elimination",
            "game": game_single,
            "team_size": 2,
            "start_days": 7,
            "checkin_days": 6,
        },
        {
            "key": "checkin_double",
            "name": "Demo Challenger (Double)",
            "status": "checkin",
            "bracket_type": "double_elimination",
            "game": game_single,
            "team_size": 2,
            "start_days": 3,
            "checkin_days": 1,
        },
        {
            "key": "live_single",
            "name": "Demo Live Knockout",
            "status": "live",
            "bracket_type": "single_elimination",
            "game": game_single,
            "team_size": 2,
            "start_days": 0,
            "checkin_days": -1,
        },
        {
            "key": "completed_single",
            "name": "Demo Season Final",
            "status": "completed",
            "bracket_type": "single_elimination",
            "game": game_single,
            "team_size": 2,
            "start_days": -3,
            "checkin_days": -4,
        },
        {
            "key": "live_league",
            "name": "Demo Pro League",
            "status": "live",
            "bracket_type": "league",
            "game": game_league,
            "team_size": 2,
            "start_days": -7,
            "checkin_days": -8,
        },
        {
            "key": "live_groups",
            "name": "Demo Groups Stage",
            "status": "live",
            "bracket_type": "group_stage",
            "group_size": 2,
            "game": game_groups,
            "team_size": 2,
            "start_days": -1,
            "checkin_days": -2,
        },
    ]

    tournaments: Dict[str, Dict] = {}
    for spec in tournament_specs:
        game = spec["game"]
        team_size = int(spec["team_size"])
        mode_name = pick_mode_name(game, team_size)
        tid = demo_id(f"tournament:{spec['key']}")
        doc = {
            "id": tid,
            "name": spec["name"],
            "game_id": game.get("id"),
            "game_name": game.get("name", "Demo Game"),
            "game_mode": mode_name,
            "team_size": team_size,
            "max_participants": 8,
            "bracket_type": spec["bracket_type"],
            "group_size": int(spec.get("group_size", 4)),
            "best_of": 1,
            "entry_fee": 0.0,
            "currency": "usd",
            "prize_pool": "$250",
            "description": "Automatisch erzeugte Demo-Daten",
            "rules": "Demo-Regeln",
            "start_date": iso_from_now(spec["start_days"]),
            "checkin_start": iso_from_now(spec["checkin_days"]),
            "default_match_time": "20:00",
            "status": spec["status"],
            "bracket": None,
            "is_demo": True,
            "updated_at": ts,
        }
        db.tournaments.update_one({"id": tid}, {"$set": doc, "$setOnInsert": {"created_at": ts}}, upsert=True)
        tournaments[spec["key"]] = doc

    registration_specs = [
        {"key": "open_single_alpha", "tournament_key": "open_single", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": False, "seed": 1},
        {"key": "open_single_bravo", "tournament_key": "open_single", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": False, "seed": 2},
        {"key": "checkin_double_alpha", "tournament_key": "checkin_double", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "checkin_double_bravo", "tournament_key": "checkin_double", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 2},
        {"key": "checkin_double_nova", "tournament_key": "checkin_double", "team_key": "nova_prime", "user_key": "nova1", "checked_in": False, "seed": 3},
        {"key": "checkin_double_charlie", "tournament_key": "checkin_double", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": False, "seed": 4},
        {"key": "live_single_alpha", "tournament_key": "live_single", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "live_single_nova", "tournament_key": "live_single", "team_key": "nova_prime", "user_key": "nova1", "checked_in": True, "seed": 2},
        {"key": "completed_single_bravo", "tournament_key": "completed_single", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 1},
        {"key": "completed_single_charlie", "tournament_key": "completed_single", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": True, "seed": 2},
        {"key": "live_league_alpha", "tournament_key": "live_league", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "live_league_bravo", "tournament_key": "live_league", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 2},
        {"key": "live_league_nova", "tournament_key": "live_league", "team_key": "nova_prime", "user_key": "nova1", "checked_in": True, "seed": 3},
        {"key": "live_league_charlie", "tournament_key": "live_league", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": True, "seed": 4},
        {"key": "live_groups_alpha", "tournament_key": "live_groups", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "live_groups_nova", "tournament_key": "live_groups", "team_key": "nova_prime", "user_key": "nova1", "checked_in": True, "seed": 2},
        {"key": "live_groups_bravo", "tournament_key": "live_groups", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 3},
        {"key": "live_groups_charlie", "tournament_key": "live_groups", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": True, "seed": 4},
    ]

    registrations: Dict[str, Dict] = {}
    for spec in registration_specs:
        reg_id = demo_id(f"registration:{spec['key']}")
        team = teams[spec["team_key"]]
        tournament = tournaments[spec["tournament_key"]]
        captain = users[spec["user_key"]]
        parent_name = ""
        parent_id = str(team.get("parent_team_id", "") or "").strip()
        if parent_id:
            parent = next((t for t in teams.values() if t["id"] == parent_id), None)
            parent_name = (parent or {}).get("name", "")
        reg_doc = {
            "id": reg_id,
            "tournament_id": tournament["id"],
            "team_id": team["id"],
            "team_name": team["name"],
            "team_logo_url": team.get("logo_url", ""),
            "team_banner_url": team.get("banner_url", ""),
            "team_tag": team.get("tag", ""),
            "main_team_name": parent_name,
            "players": players_for(team["members"], team_size=int(tournament["team_size"])),
            "user_id": captain["id"],
            "checked_in": bool(spec["checked_in"]),
            "payment_status": "free",
            "payment_session_id": None,
            "seed": int(spec["seed"]),
            "is_demo": True,
            "updated_at": ts,
        }
        db.registrations.update_one({"id": reg_id}, {"$set": reg_doc, "$setOnInsert": {"created_at": ts}}, upsert=True)
        registrations[spec["key"]] = reg_doc

    def match_from_regs(key: str, reg1: str, reg2: str, status: str = "pending", score1: int = 0, score2: int = 0, winner: str = "") -> Dict:
        r1 = registrations[reg1]
        r2 = registrations[reg2]
        return {
            "id": demo_id(f"match:{key}"),
            "round": 1,
            "position": 0,
            "team1_id": r1["id"],
            "team1_name": r1["team_name"],
            "team1_logo_url": r1.get("team_logo_url", ""),
            "team1_tag": r1.get("team_tag", ""),
            "team2_id": r2["id"],
            "team2_name": r2["team_name"],
            "team2_logo_url": r2.get("team_logo_url", ""),
            "team2_tag": r2.get("team_tag", ""),
            "score1": score1,
            "score2": score2,
            "winner_id": winner or None,
            "status": status,
            "best_of": 1,
            "disqualified": None,
        }

    live_single_bracket = {
        "type": "single_elimination",
        "rounds": [{"round": 1, "name": "Final", "matches": [match_from_regs("live-single-final", "live_single_alpha", "live_single_nova")]}],
        "total_rounds": 1,
    }
    completed_single_bracket = {
        "type": "single_elimination",
        "rounds": [
            {
                "round": 1,
                "name": "Final",
                "matches": [
                    match_from_regs(
                        "completed-single-final",
                        "completed_single_bravo",
                        "completed_single_charlie",
                        status="completed",
                        score1=2,
                        score2=1,
                        winner=registrations["completed_single_bravo"]["id"],
                    )
                ],
            }
        ],
        "total_rounds": 1,
    }

    league_rounds = [
        {
            "round": 1,
            "name": "Spieltag 1",
            "matches": [
                match_from_regs(
                    "league-r1-m1",
                    "live_league_alpha",
                    "live_league_bravo",
                    status="completed",
                    score1=2,
                    score2=1,
                    winner=registrations["live_league_alpha"]["id"],
                ),
                match_from_regs(
                    "league-r1-m2",
                    "live_league_nova",
                    "live_league_charlie",
                    status="completed",
                    score1=1,
                    score2=1,
                    winner="",
                ),
            ],
        },
        {
            "round": 2,
            "name": "Spieltag 2",
            "matches": [
                match_from_regs("league-r2-m1", "live_league_alpha", "live_league_nova"),
                match_from_regs(
                    "league-r2-m2",
                    "live_league_bravo",
                    "live_league_charlie",
                    status="completed",
                    score1=0,
                    score2=2,
                    winner=registrations["live_league_charlie"]["id"],
                ),
            ],
        },
        {
            "round": 3,
            "name": "Spieltag 3",
            "matches": [
                match_from_regs("league-r3-m1", "live_league_alpha", "live_league_charlie"),
                match_from_regs("league-r3-m2", "live_league_bravo", "live_league_nova"),
            ],
        },
    ]
    live_league_bracket = {"type": "league", "rounds": league_rounds, "total_rounds": 3}

    groups_bracket = {
        "type": "group_stage",
        "group_size": 2,
        "groups": [
            {
                "id": 1,
                "name": "Gruppe A",
                "rounds": [
                    {
                        "round": 1,
                        "name": "Spieltag 1",
                        "matches": [
                            {
                                **match_from_regs(
                                    "groups-a-r1-m1",
                                    "live_groups_alpha",
                                    "live_groups_nova",
                                    status="completed",
                                    score1=1,
                                    score2=0,
                                    winner=registrations["live_groups_alpha"]["id"],
                                ),
                                "group_id": 1,
                                "group_name": "Gruppe A",
                            }
                        ],
                    }
                ],
                "total_rounds": 1,
            },
            {
                "id": 2,
                "name": "Gruppe B",
                "rounds": [
                    {
                        "round": 1,
                        "name": "Spieltag 1",
                        "matches": [
                            {
                                **match_from_regs("groups-b-r1-m1", "live_groups_bravo", "live_groups_charlie"),
                                "group_id": 2,
                                "group_name": "Gruppe B",
                            }
                        ],
                    }
                ],
                "total_rounds": 1,
            },
        ],
        "total_groups": 2,
    }

    db.tournaments.update_one({"id": tournaments["live_single"]["id"]}, {"$set": {"bracket": live_single_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["completed_single"]["id"]}, {"$set": {"bracket": completed_single_bracket, "status": "completed", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_league"]["id"]}, {"$set": {"bracket": live_league_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_groups"]["id"]}, {"$set": {"bracket": groups_bracket, "status": "live", "updated_at": ts}})

    keep_user_ids = [demo_id(f"user:{u['key']}") for u in user_specs]
    keep_team_ids = [demo_id(f"team:{t['key']}") for t in team_specs]
    keep_tournament_ids = [demo_id(f"tournament:{t['key']}") for t in tournament_specs]
    keep_registration_ids = [demo_id(f"registration:{r['key']}") for r in registration_specs]
    db.users.delete_many({"is_demo": True, "id": {"$nin": keep_user_ids}})
    db.teams.delete_many({"is_demo": True, "id": {"$nin": keep_team_ids}})
    db.tournaments.delete_many({"is_demo": True, "id": {"$nin": keep_tournament_ids}})
    db.registrations.delete_many({"is_demo": True, "id": {"$nin": keep_registration_ids}})

    print("Demo-Daten erfolgreich importiert.")
    print("Demo-Login: demo.admin@arena.gg /", demo_password)
    print("Weitere Nutzer nutzen ebenfalls Passwort:", demo_password)

    client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo users, teams and tournaments.")
    parser.add_argument("--reset", action="store_true", help="Delete existing demo data before seeding.")
    args = parser.parse_args()
    seed_demo_data(reset=args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
