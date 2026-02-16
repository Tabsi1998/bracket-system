#!/usr/bin/env python3
"""Seed deterministic demo data for local/prod previews."""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def choose_game(db) -> Dict:
    games = list(db.games.find({}, {"_id": 0, "id": 1, "name": 1, "modes": 1}))
    preferred = [
        "Rocket League",
        "Counter-Strike 2",
        "Valorant",
        "Call of Duty",
        "EA FC (FIFA)",
    ]
    for wanted in preferred:
        for game in games:
            if game.get("name") == wanted:
                return game
    if games:
        return games[0]

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
            "members": ["manager", "alpha1", "alpha2", "bravo1", "bravo2"],
            "parent_key": None,
            "join_code": "ARES01",
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
            "is_demo": True,
            "updated_at": ts,
        }
        db.teams.update_one(
            {"id": team_id},
            {"$set": team_doc, "$setOnInsert": {"created_at": ts}},
            upsert=True,
        )
        teams[spec["key"]] = team_doc

    game = choose_game(db)
    team_size = 2
    mode_name = ""
    for mode in game.get("modes", []):
        if int(mode.get("team_size", 0) or 0) == team_size:
            mode_name = mode.get("name", "")
            break
    if not mode_name:
        mode_name = "2v2"

    tournament_specs = [
        {
            "key": "registration",
            "name": "Demo Open Cup",
            "status": "registration",
            "start_offset_days": 7,
            "checkin_offset_days": 6,
            "bracket": None,
        },
        {
            "key": "checkin",
            "name": "Demo Check-in Clash",
            "status": "checkin",
            "start_offset_days": 2,
            "checkin_offset_days": 1,
            "bracket": None,
        },
        {
            "key": "live",
            "name": "Demo Live Showdown",
            "status": "live",
            "start_offset_days": 0,
            "checkin_offset_days": 0,
            "bracket": "live",
        },
        {
            "key": "completed",
            "name": "Demo Season Final",
            "status": "completed",
            "start_offset_days": -3,
            "checkin_offset_days": -4,
            "bracket": "completed",
        },
    ]

    tournaments: Dict[str, Dict] = {}
    for spec in tournament_specs:
        tournament_id = demo_id(f"tournament:{spec['key']}")
        tournament_doc = {
            "id": tournament_id,
            "name": spec["name"],
            "game_id": game["id"],
            "game_name": game.get("name", "Demo Game"),
            "game_mode": mode_name,
            "team_size": team_size,
            "max_participants": 8,
            "bracket_type": "single_elimination",
            "best_of": 1,
            "entry_fee": 0.0,
            "currency": "usd",
            "prize_pool": "$250",
            "description": "Automatisch erzeugte Demo-Daten",
            "rules": "Demo-Regeln",
            "start_date": ts,
            "checkin_start": ts,
            "default_match_time": "20:00",
            "status": spec["status"],
            "bracket": None,
            "is_demo": True,
            "updated_at": ts,
        }
        db.tournaments.update_one(
            {"id": tournament_id},
            {"$set": tournament_doc, "$setOnInsert": {"created_at": ts}},
            upsert=True,
        )
        tournaments[spec["key"]] = tournament_doc

    registration_specs = [
        {
            "key": "reg_open_alpha",
            "tournament_key": "registration",
            "team_key": "ares_alpha",
            "user_key": "alpha1",
            "checked_in": False,
        },
        {
            "key": "checkin_bravo",
            "tournament_key": "checkin",
            "team_key": "ares_bravo",
            "user_key": "bravo1",
            "checked_in": False,
        },
        {
            "key": "checkin_nova",
            "tournament_key": "checkin",
            "team_key": "nova_prime",
            "user_key": "nova1",
            "checked_in": True,
        },
        {
            "key": "live_alpha",
            "tournament_key": "live",
            "team_key": "ares_alpha",
            "user_key": "alpha1",
            "checked_in": True,
        },
        {
            "key": "live_nova",
            "tournament_key": "live",
            "team_key": "nova_prime",
            "user_key": "nova1",
            "checked_in": True,
        },
        {
            "key": "completed_bravo",
            "tournament_key": "completed",
            "team_key": "ares_bravo",
            "user_key": "bravo1",
            "checked_in": True,
        },
        {
            "key": "completed_nova",
            "tournament_key": "completed",
            "team_key": "nova_prime",
            "user_key": "nova1",
            "checked_in": True,
        },
    ]

    registrations: Dict[str, Dict] = {}
    for spec in registration_specs:
        reg_id = demo_id(f"registration:{spec['key']}")
        team = teams[spec["team_key"]]
        tournament = tournaments[spec["tournament_key"]]
        captain = users[spec["user_key"]]
        reg_doc = {
            "id": reg_id,
            "tournament_id": tournament["id"],
            "team_id": team["id"],
            "team_name": team["name"],
            "players": players_for(team["members"], team_size=team_size),
            "user_id": captain["id"],
            "checked_in": bool(spec["checked_in"]),
            "payment_status": "free",
            "payment_session_id": None,
            "seed": 1,
            "is_demo": True,
            "updated_at": ts,
        }
        db.registrations.update_one(
            {"id": reg_id},
            {"$set": reg_doc, "$setOnInsert": {"created_at": ts}},
            upsert=True,
        )
        registrations[spec["key"]] = reg_doc

    live_match = {
        "id": demo_id("match:live-final"),
        "round": 1,
        "position": 0,
        "team1_id": registrations["live_alpha"]["id"],
        "team1_name": registrations["live_alpha"]["team_name"],
        "team2_id": registrations["live_nova"]["id"],
        "team2_name": registrations["live_nova"]["team_name"],
        "score1": 0,
        "score2": 0,
        "winner_id": None,
        "status": "pending",
        "best_of": 1,
        "disqualified": None,
    }
    completed_match = {
        "id": demo_id("match:completed-final"),
        "round": 1,
        "position": 0,
        "team1_id": registrations["completed_bravo"]["id"],
        "team1_name": registrations["completed_bravo"]["team_name"],
        "team2_id": registrations["completed_nova"]["id"],
        "team2_name": registrations["completed_nova"]["team_name"],
        "score1": 2,
        "score2": 1,
        "winner_id": registrations["completed_bravo"]["id"],
        "status": "completed",
        "best_of": 1,
        "disqualified": None,
        "completed_at": ts,
    }

    live_bracket = {
        "type": "single_elimination",
        "rounds": [{"round": 1, "name": "Final", "matches": [live_match]}],
        "total_rounds": 1,
    }
    completed_bracket = {
        "type": "single_elimination",
        "rounds": [{"round": 1, "name": "Final", "matches": [completed_match]}],
        "total_rounds": 1,
    }

    db.tournaments.update_one(
        {"id": tournaments["live"]["id"]},
        {"$set": {"bracket": live_bracket, "status": "live", "updated_at": ts}},
    )
    db.tournaments.update_one(
        {"id": tournaments["completed"]["id"]},
        {"$set": {"bracket": completed_bracket, "status": "completed", "updated_at": ts}},
    )

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
