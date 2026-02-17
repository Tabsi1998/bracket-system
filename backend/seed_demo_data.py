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


def players_for_user(user: Dict) -> List[Dict]:
    return [{"name": user.get("username", "Player"), "email": user.get("email", "")}]


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
        {"key": "delta1", "username": "DeltaOne", "email": "demo.delta1@arena.gg", "role": "user"},
        {"key": "delta2", "username": "DeltaTwo", "email": "demo.delta2@arena.gg", "role": "user"},
        {"key": "echo1", "username": "EchoOne", "email": "demo.echo1@arena.gg", "role": "user"},
        {"key": "echo2", "username": "EchoTwo", "email": "demo.echo2@arena.gg", "role": "user"},
        {"key": "foxtrot1", "username": "FoxtrotOne", "email": "demo.foxtrot1@arena.gg", "role": "user"},
        {"key": "foxtrot2", "username": "FoxtrotTwo", "email": "demo.foxtrot2@arena.gg", "role": "user"},
        {"key": "gamma1", "username": "GammaOne", "email": "demo.gamma1@arena.gg", "role": "user"},
        {"key": "gamma2", "username": "GammaTwo", "email": "demo.gamma2@arena.gg", "role": "user"},
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
        {
            "key": "pulse_main",
            "name": "PULSE Collective",
            "tag": "PULSE",
            "owner_key": "delta1",
            "leaders": ["delta1"],
            "members": ["delta1", "delta2"],
            "parent_key": None,
            "join_code": "PULS01",
            "logo_url": "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=300",
            "banner_url": "https://images.unsplash.com/photo-1466604332514-9f74e9f16f1c?w=1400",
        },
        {
            "key": "pulse_shadow",
            "name": "PULSE Shadow",
            "tag": "P-S",
            "owner_key": "delta1",
            "leaders": ["delta1"],
            "members": ["delta1", "delta2"],
            "parent_key": "pulse_main",
            "join_code": "PULS11",
            "logo_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=300",
            "banner_url": "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=1400",
        },
        {
            "key": "titan_main",
            "name": "TITAN Command",
            "tag": "TITAN",
            "owner_key": "echo1",
            "leaders": ["echo1"],
            "members": ["echo1", "echo2"],
            "parent_key": None,
            "join_code": "TITA01",
            "logo_url": "https://images.unsplash.com/photo-1484417894907-623942c8ee29?w=300",
            "banner_url": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=1400",
        },
        {
            "key": "titan_core",
            "name": "TITAN Core",
            "tag": "T-C",
            "owner_key": "echo1",
            "leaders": ["echo1"],
            "members": ["echo1", "echo2"],
            "parent_key": "titan_main",
            "join_code": "TITA11",
            "logo_url": "https://images.unsplash.com/photo-1507146426996-ef05306b995a?w=300",
            "banner_url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1400",
        },
        {
            "key": "vortex_main",
            "name": "VORTEX Syndicate",
            "tag": "VRTX",
            "owner_key": "foxtrot1",
            "leaders": ["foxtrot1"],
            "members": ["foxtrot1", "foxtrot2"],
            "parent_key": None,
            "join_code": "VRTX01",
            "logo_url": "https://images.unsplash.com/photo-1518773553398-650c184e0bb3?w=300",
            "banner_url": "https://images.unsplash.com/photo-1516117172878-fd2c41f4a759?w=1400",
        },
        {
            "key": "vortex_prime",
            "name": "VORTEX Prime",
            "tag": "V-P",
            "owner_key": "foxtrot1",
            "leaders": ["foxtrot1"],
            "members": ["foxtrot1", "foxtrot2"],
            "parent_key": "vortex_main",
            "join_code": "VRTX11",
            "logo_url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=300",
            "banner_url": "https://images.unsplash.com/photo-1522252234503-e356532cafd5?w=1400",
        },
        {
            "key": "orbit_main",
            "name": "ORBIT Network",
            "tag": "ORBIT",
            "owner_key": "gamma1",
            "leaders": ["gamma1"],
            "members": ["gamma1", "gamma2"],
            "parent_key": None,
            "join_code": "ORBT01",
            "logo_url": "https://images.unsplash.com/photo-1461749280684-dccba630e2f6?w=300",
            "banner_url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=1400",
        },
        {
            "key": "orbit_omega",
            "name": "ORBIT Omega",
            "tag": "O-O",
            "owner_key": "gamma1",
            "leaders": ["gamma1"],
            "members": ["gamma1", "gamma2"],
            "parent_key": "orbit_main",
            "join_code": "ORBT11",
            "logo_url": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=300",
            "banner_url": "https://images.unsplash.com/photo-1517180102446-f3ece451e9d8?w=1400",
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
    game_fighting = choose_game(games, ["Street Fighter 6", "Tekken 8", "Super Smash Bros", "Mario Kart"])
    game_battle_royale = choose_game(games, ["Fortnite", "Apex Legends", "Call of Duty"])

    tournament_specs = [
        {
            "key": "open_single",
            "name": "Demo Open Cup (Single)",
            "status": "registration",
            "bracket_type": "single_elimination",
            "participant_mode": "team",
            "game": game_single,
            "team_size": 2,
            "max_participants": 8,
            "start_days": 7,
            "checkin_days": 6,
        },
        {
            "key": "checkin_double",
            "name": "Demo Challenger (Double)",
            "status": "checkin",
            "bracket_type": "double_elimination",
            "participant_mode": "team",
            "game": game_single,
            "team_size": 2,
            "max_participants": 8,
            "start_days": 3,
            "checkin_days": 1,
        },
        {
            "key": "live_single",
            "name": "Demo Live Knockout",
            "status": "live",
            "bracket_type": "single_elimination",
            "participant_mode": "team",
            "game": game_single,
            "team_size": 2,
            "max_participants": 8,
            "start_days": 0,
            "checkin_days": -1,
        },
        {
            "key": "completed_single",
            "name": "Demo Season Final",
            "status": "completed",
            "bracket_type": "single_elimination",
            "participant_mode": "team",
            "game": game_single,
            "team_size": 2,
            "max_participants": 8,
            "start_days": -3,
            "checkin_days": -4,
        },
        # === HAUPTTURNIER: CoD Black Ops 6 - 4v4 S&D Liga ===
        {
            "key": "cod_snd_league",
            "name": "CoD BO6 4v4 S&D Liga - Season 1",
            "status": "live",
            "bracket_type": "league",
            "participant_mode": "team",
            "game": game_league,  # Will be replaced with CoD
            "game_mode_override": "S&D",
            "team_size": 4,
            "max_participants": 8,
            "start_days": -21,  # Started 3 weeks ago
            "checkin_days": -22,
            "matchday_interval_days": 7,
            "matchday_window_days": 5,
            "default_match_day": "wednesday",
            "default_match_hour": 20,
            "best_of": 3,
            "map_pool": ["bo6-nuketown", "bo6-hacienda", "bo6-vault", "bo6-skyline", "bo6-red-card"],
            "map_ban_enabled": True,
            "map_ban_count": 2,
            "description": """# CoD BO6 4v4 S&D Liga - Season 1

## Übersicht
Willkommen zur ersten Season der ARENA 4v4 Search & Destroy Liga für Call of Duty: Black Ops 6!

## Format
- **Liga-System**: Jeder gegen jeden
- **Spieltage**: Wöchentlich (7 Tage Intervall)
- **Zeitfenster**: 5 Tage pro Spieltag für Terminabsprache
- **Matches**: Best of 3

## Punkte
- Sieg: 3 Punkte
- Unentschieden: 1 Punkt
- Niederlage: 0 Punkte

## Map-Veto Prozess
1. Team A bannt eine Map
2. Team B bannt eine Map
3. Team A pickt Map 1
4. Team B pickt Map 2
5. Team A bannt eine Map
6. Team B bannt eine Map
7. Verbleibende Map = Map 3 (Decider)
""",
            "rules": """# Turnier-Regeln

## Spieleranzahl
- 4 Spieler pro Team (keine Wechselspieler erlaubt im Match)

## Map-Pool
- Nuketown
- Hacienda
- Vault
- Skyline
- Red Card

## Match-Setup
- Modus: Search & Destroy
- Rundenlimit: 11 (First to 6)
- Zeitlimit pro Runde: 1:30
- Bomben-Timer: 45 Sekunden

## Terminabstimmung
1. Teams schlagen Termine im Match-Hub vor
2. Der andere Team-Leader bestätigt oder macht Gegenvorschlag
3. Bei keiner Einigung innerhalb von 5 Tagen: Standard-Termin (Mittwoch 20:00)

## Ergebnismeldung
- Beide Teams melden das Ergebnis
- Screenshots als Beweis empfohlen
- Bei Streit: Admin entscheidet

## Code of Conduct
- Fair Play ist Pflicht
- Kein Cheating, kein Glitching
- Respektvolles Verhalten gegenüber Gegnern
- Beleidigungen führen zu Verwarnungen/Disqualifikation
""",
        },
        {
            "key": "live_league",
            "name": "Demo Pro League",
            "status": "live",
            "bracket_type": "league",
            "participant_mode": "team",
            "game": game_league,
            "team_size": 2,
            "max_participants": 8,
            "start_days": -14,
            "checkin_days": -15,
        },
        {
            "key": "live_groups",
            "name": "Demo Groups Stage",
            "status": "live",
            "bracket_type": "group_stage",
            "participant_mode": "team",
            "group_size": 2,
            "game": game_groups,
            "team_size": 2,
            "max_participants": 8,
            "start_days": -1,
            "checkin_days": -2,
        },
        {
            "key": "live_group_playoffs",
            "name": "Demo Groups + Playoffs",
            "status": "live",
            "bracket_type": "group_playoffs",
            "participant_mode": "team",
            "group_size": 2,
            "advance_per_group": 1,
            "game": game_groups,
            "team_size": 2,
            "max_participants": 8,
            "start_days": -2,
            "checkin_days": -3,
        },
        {
            "key": "live_swiss",
            "name": "Demo Swiss Open",
            "status": "live",
            "bracket_type": "swiss_system",
            "participant_mode": "team",
            "swiss_rounds": 3,
            "game": game_single,
            "team_size": 2,
            "max_participants": 8,
            "start_days": -2,
            "checkin_days": -3,
        },
        {
            "key": "live_ladder",
            "name": "Demo Ladder Sprint",
            "status": "live",
            "bracket_type": "ladder_system",
            "participant_mode": "team",
            "game": game_single,
            "team_size": 2,
            "max_participants": 8,
            "start_days": -4,
            "checkin_days": -5,
        },
        {
            "key": "live_koth",
            "name": "Demo King of the Hill",
            "status": "live",
            "bracket_type": "king_of_the_hill",
            "participant_mode": "team",
            "game": game_single,
            "team_size": 2,
            "max_participants": 8,
            "start_days": -4,
            "checkin_days": -5,
        },
        {
            "key": "live_battle_royale",
            "name": "Demo Battle Royale Series",
            "status": "live",
            "bracket_type": "battle_royale",
            "participant_mode": "solo",
            "game": game_battle_royale,
            "team_size": 1,
            "max_participants": 12,
            "battle_royale_group_size": 3,
            "battle_royale_advance": 2,
            "require_admin_score_approval": True,
            "start_days": -1,
            "checkin_days": -2,
        },
        {
            "key": "open_solo_single",
            "name": "Demo Solo Cup (MK)",
            "status": "registration",
            "bracket_type": "single_elimination",
            "participant_mode": "solo",
            "game": game_fighting,
            "team_size": 1,
            "max_participants": 16,
            "start_days": 8,
            "checkin_days": 7,
        },
        {
            "key": "checkin_solo_double",
            "name": "Demo Solo Double (Fighters)",
            "status": "checkin",
            "bracket_type": "double_elimination",
            "participant_mode": "solo",
            "game": game_fighting,
            "team_size": 1,
            "max_participants": 16,
            "start_days": 2,
            "checkin_days": 1,
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
            "participant_mode": spec.get("participant_mode", "team"),
            "team_size": team_size,
            "max_participants": int(spec.get("max_participants", 8)),
            "bracket_type": spec["bracket_type"],
            "group_size": int(spec.get("group_size", 4)),
            "advance_per_group": int(spec.get("advance_per_group", 2)),
            "swiss_rounds": int(spec.get("swiss_rounds", 5)),
            "battle_royale_group_size": int(spec.get("battle_royale_group_size", spec.get("group_size", 4))),
            "battle_royale_advance": int(spec.get("battle_royale_advance", spec.get("advance_per_group", 2))),
            "matchday_interval_days": int(spec.get("matchday_interval_days", 7)),
            "matchday_window_days": int(spec.get("matchday_window_days", 7)),
            "points_win": int(spec.get("points_win", 3)),
            "points_draw": int(spec.get("points_draw", 1)),
            "points_loss": int(spec.get("points_loss", 0)),
            "tiebreakers": list(spec.get("tiebreakers", ["points", "score_diff", "score_for", "team_name"])),
            "require_admin_score_approval": bool(spec.get("require_admin_score_approval", spec["bracket_type"] == "battle_royale")),
            "best_of": 1,
            "entry_fee": 0.0,
            "currency": "usd",
            "prize_pool": "$250",
            "description": "Automatisch erzeugte Demo-Daten für die Systemvorschau. Dieses Turnier zeigt die wichtigsten Funktionen der Plattform.",
            "rules": """# Turnier-Regeln

## Allgemein
- Fair Play ist Pflicht
- Cheating führt zur Disqualifikation
- Admin-Entscheidungen sind endgültig

## Terminabstimmung
1. Teams schlagen Termine im Match-Hub vor
2. Gegner bestätigt oder macht Gegenvorschlag
3. Bei keiner Einigung: Default-Zeit gilt (Mittwoch 19:00 Uhr)

## Ergebnismeldung
- Beide Teams melden das Ergebnis
- Bei Übereinstimmung: automatische Bestätigung
- Bei Unstimmigkeit: Admin entscheidet
""",
            "start_date": iso_from_now(spec["start_days"]),
            "checkin_start": iso_from_now(spec["checkin_days"]),
            "default_match_time": "20:00",
            "default_match_day": "wednesday",
            "default_match_hour": 19,
            "auto_schedule_on_window_end": True,
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
        {"key": "live_league_pulse", "tournament_key": "live_league", "team_key": "pulse_shadow", "user_key": "delta1", "checked_in": True, "seed": 5},
        {"key": "live_league_titan", "tournament_key": "live_league", "team_key": "titan_core", "user_key": "echo1", "checked_in": True, "seed": 6},
        {"key": "live_league_vortex", "tournament_key": "live_league", "team_key": "vortex_prime", "user_key": "foxtrot1", "checked_in": True, "seed": 7},
        {"key": "live_league_orbit", "tournament_key": "live_league", "team_key": "orbit_omega", "user_key": "gamma1", "checked_in": True, "seed": 8},
        {"key": "live_groups_alpha", "tournament_key": "live_groups", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "live_groups_nova", "tournament_key": "live_groups", "team_key": "nova_prime", "user_key": "nova1", "checked_in": True, "seed": 2},
        {"key": "live_groups_bravo", "tournament_key": "live_groups", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 3},
        {"key": "live_groups_charlie", "tournament_key": "live_groups", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": True, "seed": 4},
        {"key": "live_group_playoffs_alpha", "tournament_key": "live_group_playoffs", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "live_group_playoffs_nova", "tournament_key": "live_group_playoffs", "team_key": "nova_prime", "user_key": "nova1", "checked_in": True, "seed": 2},
        {"key": "live_group_playoffs_bravo", "tournament_key": "live_group_playoffs", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 3},
        {"key": "live_group_playoffs_charlie", "tournament_key": "live_group_playoffs", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": True, "seed": 4},
        {"key": "live_swiss_alpha", "tournament_key": "live_swiss", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "live_swiss_bravo", "tournament_key": "live_swiss", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 2},
        {"key": "live_swiss_nova", "tournament_key": "live_swiss", "team_key": "nova_prime", "user_key": "nova1", "checked_in": True, "seed": 3},
        {"key": "live_swiss_charlie", "tournament_key": "live_swiss", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": True, "seed": 4},
        {"key": "live_ladder_alpha", "tournament_key": "live_ladder", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "live_ladder_bravo", "tournament_key": "live_ladder", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 2},
        {"key": "live_ladder_nova", "tournament_key": "live_ladder", "team_key": "nova_prime", "user_key": "nova1", "checked_in": True, "seed": 3},
        {"key": "live_ladder_charlie", "tournament_key": "live_ladder", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": True, "seed": 4},
        {"key": "live_koth_alpha", "tournament_key": "live_koth", "team_key": "ares_alpha", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "live_koth_bravo", "tournament_key": "live_koth", "team_key": "ares_bravo", "user_key": "bravo1", "checked_in": True, "seed": 2},
        {"key": "live_koth_nova", "tournament_key": "live_koth", "team_key": "nova_prime", "user_key": "nova1", "checked_in": True, "seed": 3},
        {"key": "live_koth_charlie", "tournament_key": "live_koth", "team_key": "ares_charlie", "user_key": "charlie1", "checked_in": True, "seed": 4},
        {"key": "solo_br_alpha1", "tournament_key": "live_battle_royale", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "solo_br_bravo1", "tournament_key": "live_battle_royale", "user_key": "bravo1", "checked_in": True, "seed": 2},
        {"key": "solo_br_nova1", "tournament_key": "live_battle_royale", "user_key": "nova1", "checked_in": True, "seed": 3},
        {"key": "solo_br_charlie1", "tournament_key": "live_battle_royale", "user_key": "charlie1", "checked_in": True, "seed": 4},
        {"key": "solo_br_alpha2", "tournament_key": "live_battle_royale", "user_key": "alpha2", "checked_in": True, "seed": 5},
        {"key": "solo_br_bravo2", "tournament_key": "live_battle_royale", "user_key": "bravo2", "checked_in": True, "seed": 6},
        {"key": "open_solo_alpha1", "tournament_key": "open_solo_single", "user_key": "alpha1", "checked_in": False, "seed": 1},
        {"key": "open_solo_bravo1", "tournament_key": "open_solo_single", "user_key": "bravo1", "checked_in": False, "seed": 2},
        {"key": "open_solo_nova1", "tournament_key": "open_solo_single", "user_key": "nova1", "checked_in": False, "seed": 3},
        {"key": "open_solo_charlie1", "tournament_key": "open_solo_single", "user_key": "charlie1", "checked_in": False, "seed": 4},
        {"key": "checkin_solo_alpha1", "tournament_key": "checkin_solo_double", "user_key": "alpha1", "checked_in": True, "seed": 1},
        {"key": "checkin_solo_bravo1", "tournament_key": "checkin_solo_double", "user_key": "bravo1", "checked_in": True, "seed": 2},
        {"key": "checkin_solo_nova1", "tournament_key": "checkin_solo_double", "user_key": "nova1", "checked_in": False, "seed": 3},
        {"key": "checkin_solo_charlie1", "tournament_key": "checkin_solo_double", "user_key": "charlie1", "checked_in": False, "seed": 4},
    ]

    registrations: Dict[str, Dict] = {}
    for spec in registration_specs:
        reg_id = demo_id(f"registration:{spec['key']}")
        tournament = tournaments[spec["tournament_key"]]
        captain = users[spec["user_key"]]

        team_key = spec.get("team_key")
        if team_key:
            team = teams[team_key]
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
                "participant_mode": tournament.get("participant_mode", "team"),
                "checked_in": bool(spec["checked_in"]),
                "payment_status": "free",
                "payment_session_id": None,
                "seed": int(spec["seed"]),
                "is_demo": True,
                "updated_at": ts,
            }
        else:
            reg_doc = {
                "id": reg_id,
                "tournament_id": tournament["id"],
                "team_id": None,
                "team_name": captain["username"],
                "team_logo_url": captain.get("avatar_url", ""),
                "team_banner_url": captain.get("banner_url", ""),
                "team_tag": "",
                "main_team_name": "",
                "players": players_for_user(captain),
                "user_id": captain["id"],
                "participant_mode": "solo",
                "checked_in": bool(spec["checked_in"]),
                "payment_status": "free",
                "payment_session_id": None,
                "seed": int(spec["seed"]),
                "is_demo": True,
                "updated_at": ts,
            }
        db.registrations.update_one({"id": reg_id}, {"$set": reg_doc, "$setOnInsert": {"created_at": ts}}, upsert=True)
        registrations[spec["key"]] = reg_doc

    def match_from_regs(
        key: str,
        reg1: str,
        reg2: str,
        status: str = "pending",
        score1: int = 0,
        score2: int = 0,
        winner: str = "",
        round_num: int = 1,
        position: int = 0,
        matchday: int | None = None,
        scheduled_for: str = "",
    ) -> Dict:
        r1 = registrations[reg1]
        r2 = registrations[reg2]
        return {
            "id": demo_id(f"match:{key}"),
            "round": round_num,
            "matchday": int(matchday if matchday is not None else round_num),
            "position": position,
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
            "scheduled_for": scheduled_for,
            "disqualified": None,
        }

    def reg_pair_key(reg_a: str, reg_b: str) -> str:
        a = registrations[reg_a]["id"]
        b = registrations[reg_b]["id"]
        return "|".join(sorted([a, b]))

    def br_heat(
        key: str,
        round_num: int,
        position: int,
        reg_keys: List[str],
        status: str = "pending",
        placements: List[str] | None = None,
    ) -> Dict:
        participants = []
        for reg_key in reg_keys:
            reg = registrations[reg_key]
            participants.append(
                {
                    "registration_id": reg["id"],
                    "name": reg["team_name"],
                    "logo_url": reg.get("team_logo_url", ""),
                    "tag": reg.get("team_tag", ""),
                }
            )
        ordered = [registrations[key]["id"] for key in (placements or [])]
        points_map = {}
        if ordered:
            total = len(ordered)
            for idx, reg_id in enumerate(ordered):
                points_map[reg_id] = max(0, total - idx)
        return {
            "id": demo_id(f"match:{key}"),
            "round": round_num,
            "position": position,
            "type": "battle_royale_heat",
            "participants": participants,
            "placements": ordered,
            "points_map": points_map,
            "status": status,
            "approved": status == "completed",
            "scheduled_for": iso_from_now(round_num - 1),
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

    def build_league_rounds(
        reg_keys: List[str],
        *,
        start_dt: datetime,
        interval_days: int = 7,
        window_days: int = 7,
    ) -> List[Dict]:
        rotation = list(reg_keys)
        if len(rotation) % 2 != 0:
            rotation.append(None)
        if len(rotation) < 2:
            return []

        rounds: List[Dict] = []
        total_rounds = len(rotation) - 1
        for round_idx in range(total_rounds):
            day_index = round_idx + 1
            window_start_dt = start_dt + timedelta(days=interval_days * round_idx)
            window_end_dt = window_start_dt + timedelta(days=max(1, int(window_days)) - 1, hours=23, minutes=59)
            matches: List[Dict] = []

            for position in range(len(rotation) // 2):
                home_key = rotation[position]
                away_key = rotation[-(position + 1)]
                if not home_key or not away_key:
                    continue

                status = "pending"
                score1 = 0
                score2 = 0
                winner = ""
                scheduled_for = ""

                # Demo flow: Spieltag 1 vollständig gespielt, Spieltag 2 teils gespielt,
                # danach gemischt aus terminierten/offenen Matches.
                if round_idx == 0:
                    score1 = 2 if position % 2 == 0 else 1
                    score2 = 1 if position % 2 == 0 else 2
                    status = "completed"
                    winner = registrations[home_key]["id"] if score1 > score2 else registrations[away_key]["id"]
                    scheduled_for = (window_start_dt + timedelta(days=1, hours=19 + position)).isoformat()
                elif round_idx == 1:
                    if position in {0, 1}:
                        score1 = 2
                        score2 = 0 if position == 0 else 1
                        status = "completed"
                        winner = registrations[home_key]["id"]
                        scheduled_for = (window_start_dt + timedelta(days=2, hours=19 + position)).isoformat()
                    else:
                        scheduled_for = (window_start_dt + timedelta(days=3 + position, hours=20)).isoformat()
                elif round_idx == 2 and position < 2:
                    scheduled_for = (window_start_dt + timedelta(days=4 + position, hours=20)).isoformat()

                matches.append(
                    match_from_regs(
                        f"league-r{day_index}-m{position + 1}",
                        home_key,
                        away_key,
                        status=status,
                        score1=score1,
                        score2=score2,
                        winner=winner,
                        round_num=day_index,
                        position=position,
                        matchday=day_index,
                        scheduled_for=scheduled_for,
                    )
                )

            rounds.append(
                {
                    "round": day_index,
                    "matchday": day_index,
                    "name": f"Spieltag {day_index}",
                    "window_start": window_start_dt.isoformat(),
                    "window_end": window_end_dt.isoformat(),
                    "matches": matches,
                }
            )

            fixed = rotation[0]
            rest = rotation[1:]
            rest = [rest[-1]] + rest[:-1]
            rotation = [fixed] + rest

        return rounds

    league_reg_keys = [
        "live_league_alpha",
        "live_league_bravo",
        "live_league_nova",
        "live_league_charlie",
        "live_league_pulse",
        "live_league_titan",
        "live_league_vortex",
        "live_league_orbit",
    ]
    try:
        league_start_dt = datetime.fromisoformat(str(tournaments["live_league"]["start_date"]))
    except Exception:
        league_start_dt = now_utc() - timedelta(days=14)
    league_rounds = build_league_rounds(
        league_reg_keys,
        start_dt=league_start_dt,
        interval_days=int(tournaments["live_league"].get("matchday_interval_days", 7)),
        window_days=int(tournaments["live_league"].get("matchday_window_days", 7)),
    )
    live_league_bracket = {"type": "league", "rounds": league_rounds, "total_rounds": len(league_rounds)}

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

    group_playoffs_bracket = {
        "type": "group_playoffs",
        "group_size": 2,
        "total_groups": 2,
        "advance_per_group": 1,
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
                                    "group-playoffs-a-r1",
                                    "live_group_playoffs_alpha",
                                    "live_group_playoffs_nova",
                                    status="completed",
                                    score1=2,
                                    score2=1,
                                    winner=registrations["live_group_playoffs_alpha"]["id"],
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
                                **match_from_regs(
                                    "group-playoffs-b-r1",
                                    "live_group_playoffs_bravo",
                                    "live_group_playoffs_charlie",
                                    status="completed",
                                    score1=0,
                                    score2=2,
                                    winner=registrations["live_group_playoffs_charlie"]["id"],
                                ),
                                "group_id": 2,
                                "group_name": "Gruppe B",
                            }
                        ],
                    }
                ],
                "total_rounds": 1,
            },
        ],
        "playoffs_generated": True,
        "playoffs": {
            "type": "single_elimination",
            "rounds": [
                {
                    "round": 1,
                    "name": "Finale",
                    "matches": [match_from_regs("group-playoffs-final", "live_group_playoffs_alpha", "live_group_playoffs_charlie")],
                }
            ],
            "total_rounds": 1,
        },
    }

    swiss_bracket = {
        "type": "swiss_system",
        "rounds": [
            {
                "round": 1,
                "name": "Swiss Runde 1",
                "matches": [
                    match_from_regs(
                        "swiss-r1-m1",
                        "live_swiss_alpha",
                        "live_swiss_bravo",
                        status="completed",
                        score1=2,
                        score2=1,
                        winner=registrations["live_swiss_alpha"]["id"],
                        round_num=1,
                        position=0,
                    ),
                    match_from_regs(
                        "swiss-r1-m2",
                        "live_swiss_nova",
                        "live_swiss_charlie",
                        status="completed",
                        score1=0,
                        score2=2,
                        winner=registrations["live_swiss_charlie"]["id"],
                        round_num=1,
                        position=1,
                    ),
                ],
            },
            {
                "round": 2,
                "name": "Swiss Runde 2",
                "matches": [
                    match_from_regs("swiss-r2-m1", "live_swiss_alpha", "live_swiss_charlie", round_num=2, position=0),
                    match_from_regs("swiss-r2-m2", "live_swiss_nova", "live_swiss_bravo", round_num=2, position=1),
                ],
            },
        ],
        "current_round": 2,
        "max_rounds": 3,
        "total_rounds": 3,
        "used_pairs": [
            reg_pair_key("live_swiss_alpha", "live_swiss_bravo"),
            reg_pair_key("live_swiss_nova", "live_swiss_charlie"),
        ],
        "bye_reg_ids": [],
    }

    ladder_bracket = {
        "type": "ladder_system",
        "rounds": [
            {
                "round": 1,
                "name": "Ladder Match 1",
                "matches": [
                    match_from_regs(
                        "ladder-r1",
                        "live_ladder_alpha",
                        "live_ladder_bravo",
                        status="completed",
                        score1=2,
                        score2=0,
                        winner=registrations["live_ladder_alpha"]["id"],
                        round_num=1,
                        position=0,
                    )
                ],
            },
            {
                "round": 2,
                "name": "Ladder Match 2",
                "matches": [match_from_regs("ladder-r2", "live_ladder_alpha", "live_ladder_nova", round_num=2, position=0)],
            },
        ],
        "champion_id": registrations["live_ladder_alpha"]["id"],
        "challenger_queue": [registrations["live_ladder_nova"]["id"], registrations["live_ladder_charlie"]["id"]],
        "ladder_cycle_count": 1,
        "ladder_max_cycles": 8,
        "total_rounds": 8,
    }

    koth_bracket = {
        "type": "king_of_the_hill",
        "rounds": [
            {
                "round": 1,
                "name": "KOTH Runde 1",
                "matches": [
                    match_from_regs(
                        "koth-r1",
                        "live_koth_alpha",
                        "live_koth_bravo",
                        status="completed",
                        score1=0,
                        score2=2,
                        winner=registrations["live_koth_bravo"]["id"],
                        round_num=1,
                        position=0,
                    )
                ],
            },
            {
                "round": 2,
                "name": "KOTH Runde 2",
                "matches": [match_from_regs("koth-r2", "live_koth_bravo", "live_koth_nova", round_num=2, position=0)],
            },
        ],
        "champion_id": registrations["live_koth_bravo"]["id"],
        "koth_queue": [registrations["live_koth_nova"]["id"], registrations["live_koth_charlie"]["id"]],
        "total_rounds": 3,
    }

    battle_royale_bracket = {
        "type": "battle_royale",
        "group_size": 3,
        "advance_per_heat": 2,
        "rounds": [
            {
                "round": 1,
                "name": "Battle Royale Runde 1",
                "matches": [
                    br_heat(
                        "br-r1-h1",
                        round_num=1,
                        position=0,
                        reg_keys=["solo_br_alpha1", "solo_br_bravo1", "solo_br_nova1"],
                        status="completed",
                        placements=["solo_br_alpha1", "solo_br_nova1", "solo_br_bravo1"],
                    ),
                    br_heat(
                        "br-r1-h2",
                        round_num=1,
                        position=1,
                        reg_keys=["solo_br_charlie1", "solo_br_alpha2", "solo_br_bravo2"],
                        status="completed",
                        placements=["solo_br_charlie1", "solo_br_alpha2", "solo_br_bravo2"],
                    ),
                ],
            },
            {
                "round": 2,
                "name": "Battle Royale Runde 2",
                "matches": [
                    br_heat(
                        "br-r2-h1",
                        round_num=2,
                        position=0,
                        reg_keys=["solo_br_alpha1", "solo_br_nova1", "solo_br_charlie1", "solo_br_alpha2"],
                    )
                ],
            },
        ],
        "current_round": 2,
        "total_rounds": 2,
    }

    db.tournaments.update_one({"id": tournaments["live_single"]["id"]}, {"$set": {"bracket": live_single_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["completed_single"]["id"]}, {"$set": {"bracket": completed_single_bracket, "status": "completed", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_league"]["id"]}, {"$set": {"bracket": live_league_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_groups"]["id"]}, {"$set": {"bracket": groups_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_group_playoffs"]["id"]}, {"$set": {"bracket": group_playoffs_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_swiss"]["id"]}, {"$set": {"bracket": swiss_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_ladder"]["id"]}, {"$set": {"bracket": ladder_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_koth"]["id"]}, {"$set": {"bracket": koth_bracket, "status": "live", "updated_at": ts}})
    db.tournaments.update_one({"id": tournaments["live_battle_royale"]["id"]}, {"$set": {"bracket": battle_royale_bracket, "status": "live", "updated_at": ts}})

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
