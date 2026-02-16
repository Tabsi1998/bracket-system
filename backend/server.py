from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import math
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
import secrets
import string
from datetime import datetime, timezone
import bcrypt
from jose import jwt as jose_jwt, JWTError

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── Pydantic Models ───

class GameMode(BaseModel):
    name: str
    team_size: int
    description: str = ""

class GameCreate(BaseModel):
    name: str
    short_name: str = ""
    category: str = "other"
    image_url: str = ""
    modes: List[GameMode] = []
    platforms: List[str] = []

class TournamentCreate(BaseModel):
    name: str
    game_id: str
    game_name: str = ""
    game_mode: str = ""
    team_size: int = 1
    max_participants: int = 8
    bracket_type: str = "single_elimination"
    best_of: int = 1
    entry_fee: float = 0.0
    currency: str = "usd"
    prize_pool: str = ""
    description: str = ""
    rules: str = ""
    start_date: str = ""
    checkin_start: str = ""
    group_size: int = 4
    default_match_time: str = ""

class TournamentUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[str] = None
    start_date: Optional[str] = None
    checkin_start: Optional[str] = None

class RegistrationCreate(BaseModel):
    team_name: str
    players: List[Dict[str, str]]
    team_id: Optional[str] = None

class ScoreUpdate(BaseModel):
    score1: int
    score2: int
    winner_id: Optional[str] = None

class PaymentRequest(BaseModel):
    tournament_id: str
    registration_id: str
    origin_url: str

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class TeamCreate(BaseModel):
    name: str
    tag: str = ""
    parent_team_id: Optional[str] = None

class TeamAddMember(BaseModel):
    email: str

class TeamJoinRequest(BaseModel):
    team_id: str
    join_code: str

class PromoteMember(BaseModel):
    user_id: str

class CommentCreate(BaseModel):
    message: str

class TimeProposal(BaseModel):
    proposed_time: str

class ScoreSubmission(BaseModel):
    score1: int
    score2: int

class AdminScoreResolve(BaseModel):
    score1: int
    score2: int
    winner_id: Optional[str] = None
    disqualify_team_id: Optional[str] = None

class AdminSettingUpdate(BaseModel):
    key: str
    value: str

# ─── JWT Auth ───

JWT_SECRET = os.environ.get("JWT_SECRET", "arena-esports-secret-2026-xk9m2")
JWT_ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str, role: str = "user") -> str:
    payload = {"user_id": user_id, "email": email, "role": role, "exp": datetime.now(timezone.utc).timestamp() + 86400 * 7}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        payload = jose_jwt.decode(auth_header[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0, "password_hash": 0})
        return user
    except (JWTError, Exception):
        return None

async def require_auth(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401, "Nicht eingeloggt")
    return user

async def require_admin(request: Request):
    user = await require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin-Rechte erforderlich")
    return user

# ─── Seed Data ───

SEED_GAMES = [
    {
        "name": "Call of Duty",
        "short_name": "CoD",
        "category": "fps",
        "image_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=600",
        "modes": [
            {"name": "1v1", "team_size": 1, "description": "1v1 Gunfight"},
            {"name": "2v2", "team_size": 2, "description": "2v2 Gunfight"},
            {"name": "3v3", "team_size": 3, "description": "3v3 Search & Destroy"},
            {"name": "4v4", "team_size": 4, "description": "4v4 Hardpoint"},
            {"name": "5v5", "team_size": 5, "description": "5v5 Competitive"},
        ],
        "platforms": ["PC", "PS5", "Xbox"],
    },
    {
        "name": "EA FC (FIFA)",
        "short_name": "FIFA",
        "category": "sports",
        "image_url": "https://images.unsplash.com/photo-1493711662062-fa541adb3fc8?w=600",
        "modes": [
            {"name": "1v1", "team_size": 1, "description": "1v1 Seasons"},
            {"name": "2v2", "team_size": 2, "description": "2v2 Co-Op"},
        ],
        "platforms": ["PC", "PS5", "Xbox"],
    },
    {
        "name": "Rocket League",
        "short_name": "RL",
        "category": "sports",
        "image_url": "https://images.unsplash.com/photo-1612287230202-1ff1d85d1bdf?w=600",
        "modes": [
            {"name": "1v1", "team_size": 1, "description": "1v1 Duel"},
            {"name": "2v2", "team_size": 2, "description": "2v2 Doubles"},
            {"name": "3v3", "team_size": 3, "description": "3v3 Standard"},
        ],
        "platforms": ["PC", "PS5", "Xbox", "Switch"],
    },
    {
        "name": "Counter-Strike 2",
        "short_name": "CS2",
        "category": "fps",
        "image_url": "https://images.unsplash.com/photo-1552820728-8b83bb6b2b28?w=600",
        "modes": [
            {"name": "5v5", "team_size": 5, "description": "5v5 Competitive"},
        ],
        "platforms": ["PC"],
    },
    {
        "name": "Valorant",
        "short_name": "VAL",
        "category": "fps",
        "image_url": "https://images.unsplash.com/photo-1558008258-ec20a83db196?w=600",
        "modes": [
            {"name": "5v5", "team_size": 5, "description": "5v5 Competitive"},
        ],
        "platforms": ["PC"],
    },
    {
        "name": "League of Legends",
        "short_name": "LoL",
        "category": "moba",
        "image_url": "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=600",
        "modes": [
            {"name": "5v5", "team_size": 5, "description": "5v5 Summoner's Rift"},
        ],
        "platforms": ["PC"],
    },
    {
        "name": "Dota 2",
        "short_name": "DOTA",
        "category": "moba",
        "image_url": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600",
        "modes": [
            {"name": "5v5", "team_size": 5, "description": "5v5 Standard"},
        ],
        "platforms": ["PC"],
    },
    {
        "name": "Mario Kart",
        "short_name": "MK",
        "category": "racing",
        "image_url": "https://images.unsplash.com/photo-1712522134057-174c7358ca01?w=600",
        "modes": [
            {"name": "1v1", "team_size": 1, "description": "1v1 Race"},
            {"name": "2v2", "team_size": 2, "description": "2v2 Team Race"},
        ],
        "platforms": ["Switch"],
    },
    {
        "name": "Super Smash Bros",
        "short_name": "SSB",
        "category": "fighting",
        "image_url": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=600",
        "modes": [
            {"name": "1v1", "team_size": 1, "description": "1v1 Stock Battle"},
            {"name": "2v2", "team_size": 2, "description": "2v2 Team Battle"},
        ],
        "platforms": ["Switch"],
    },
    {
        "name": "Fortnite",
        "short_name": "FN",
        "category": "battle_royale",
        "image_url": "https://images.unsplash.com/photo-1589241062272-c0a000072dfa?w=600",
        "modes": [
            {"name": "Solo", "team_size": 1, "description": "Solo Battle Royale"},
            {"name": "Duo", "team_size": 2, "description": "Duo Battle Royale"},
            {"name": "Squad", "team_size": 4, "description": "Squad Battle Royale"},
        ],
        "platforms": ["PC", "PS5", "Xbox", "Switch"],
    },
    {
        "name": "Apex Legends",
        "short_name": "APEX",
        "category": "battle_royale",
        "image_url": "https://images.unsplash.com/photo-1560419015-7c427e8ae5ba?w=600",
        "modes": [
            {"name": "Trio", "team_size": 3, "description": "3-Player Squad"},
        ],
        "platforms": ["PC", "PS5", "Xbox"],
    },
    {
        "name": "Overwatch 2",
        "short_name": "OW2",
        "category": "fps",
        "image_url": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=600",
        "modes": [
            {"name": "5v5", "team_size": 5, "description": "5v5 Competitive"},
        ],
        "platforms": ["PC", "PS5", "Xbox"],
    },
    {
        "name": "Street Fighter 6",
        "short_name": "SF6",
        "category": "fighting",
        "image_url": "https://images.unsplash.com/photo-1612287230202-1ff1d85d1bdf?w=600",
        "modes": [
            {"name": "1v1", "team_size": 1, "description": "1v1 Ranked"},
        ],
        "platforms": ["PC", "PS5"],
    },
    {
        "name": "Tekken 8",
        "short_name": "T8",
        "category": "fighting",
        "image_url": "https://images.unsplash.com/photo-1542751110-97427bbecf20?w=600",
        "modes": [
            {"name": "1v1", "team_size": 1, "description": "1v1 Ranked"},
        ],
        "platforms": ["PC", "PS5", "Xbox"],
    },
]

async def seed_games():
    count = await db.games.count_documents({})
    if count == 0:
        for game_data in SEED_GAMES:
            doc = {
                "id": str(uuid.uuid4()),
                "is_custom": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **game_data,
            }
            await db.games.insert_one(doc)
        logger.info(f"Seeded {len(SEED_GAMES)} games")

# ─── Auth Endpoints ───

@api_router.post("/auth/register")
async def register_user(body: UserRegister):
    if await db.users.find_one({"email": body.email}):
        raise HTTPException(400, "E-Mail bereits registriert")
    if await db.users.find_one({"username": body.username}):
        raise HTTPException(400, "Benutzername bereits vergeben")
    user_doc = {
        "id": str(uuid.uuid4()), "username": body.username, "email": body.email,
        "password_hash": hash_password(body.password), "role": "user",
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={body.username}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)
    token = create_token(user_doc["id"], user_doc["email"], user_doc["role"])
    return {"token": token, "user": {"id": user_doc["id"], "username": user_doc["username"], "email": user_doc["email"], "role": user_doc["role"], "avatar_url": user_doc["avatar_url"]}}

@api_router.post("/auth/login")
async def login_user(body: UserLogin):
    user = await db.users.find_one({"email": body.email}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Ungültige Anmeldedaten")
    token = create_token(user["id"], user["email"], user.get("role", "user"))
    return {"token": token, "user": {"id": user["id"], "username": user["username"], "email": user["email"], "role": user.get("role", "user"), "avatar_url": user.get("avatar_url", "")}}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await require_auth(request)
    return user

async def seed_admin():
    if not await db.users.find_one({"role": "admin"}):
        admin_doc = {
            "id": str(uuid.uuid4()), "username": "admin", "email": "admin@arena.gg",
            "password_hash": hash_password("admin123"), "role": "admin",
            "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(admin_doc)
        logger.info("Admin user seeded: admin@arena.gg / admin123")

# ─── Team Endpoints ───

@api_router.get("/teams")
async def list_teams(request: Request):
    user = await require_auth(request)
    teams = await db.teams.find({"$or": [{"owner_id": user["id"]}, {"member_ids": user["id"]}]}, {"_id": 0}).to_list(100)
    return teams

@api_router.post("/teams")
async def create_team(request: Request, body: TeamCreate):
    user = await require_auth(request)
    doc = {
        "id": str(uuid.uuid4()), "name": body.name, "tag": body.tag,
        "owner_id": user["id"], "owner_name": user["username"],
        "member_ids": [user["id"]],
        "members": [{"id": user["id"], "username": user["username"], "email": user["email"]}],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.teams.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/teams/{team_id}")
async def get_team(team_id: str):
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")
    return team

@api_router.delete("/teams/{team_id}")
async def delete_team(request: Request, team_id: str):
    user = await require_auth(request)
    result = await db.teams.delete_one({"id": team_id, "owner_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Team nicht gefunden")
    return {"status": "deleted"}

@api_router.post("/teams/{team_id}/members")
async def add_team_member(request: Request, team_id: str, body: TeamAddMember):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id, "owner_id": user["id"]}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")
    member = await db.users.find_one({"email": body.email}, {"_id": 0, "password_hash": 0})
    if not member:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if member["id"] in team.get("member_ids", []):
        raise HTTPException(400, "Bereits Teammitglied")
    await db.teams.update_one({"id": team_id}, {"$push": {"member_ids": member["id"], "members": {"id": member["id"], "username": member["username"], "email": member["email"]}}})
    return await db.teams.find_one({"id": team_id}, {"_id": 0})

@api_router.delete("/teams/{team_id}/members/{member_id}")
async def remove_team_member(request: Request, team_id: str, member_id: str):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id, "owner_id": user["id"]}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")
    await db.teams.update_one({"id": team_id}, {"$pull": {"member_ids": member_id, "members": {"id": member_id}}})
    return await db.teams.find_one({"id": team_id}, {"_id": 0})

# ─── Game Endpoints ───

@api_router.get("/games")
async def list_games(category: Optional[str] = None):
    query = {}
    if category:
        query["category"] = category
    games = await db.games.find(query, {"_id": 0}).to_list(100)
    return games

@api_router.post("/games")
async def create_game(body: GameCreate):
    doc = {
        "id": str(uuid.uuid4()),
        "is_custom": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(),
    }
    await db.games.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/games/{game_id}")
async def get_game(game_id: str):
    game = await db.games.find_one({"id": game_id}, {"_id": 0})
    if not game:
        raise HTTPException(404, "Game not found")
    return game

@api_router.put("/games/{game_id}")
async def update_game(game_id: str, body: GameCreate):
    result = await db.games.update_one({"id": game_id}, {"$set": body.model_dump()})
    if result.matched_count == 0:
        raise HTTPException(404, "Game not found")
    game = await db.games.find_one({"id": game_id}, {"_id": 0})
    return game

@api_router.delete("/games/{game_id}")
async def delete_game(game_id: str):
    result = await db.games.delete_one({"id": game_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Game not found")
    return {"status": "deleted"}

# ─── Tournament Endpoints ───

@api_router.get("/tournaments")
async def list_tournaments(status: Optional[str] = None, game_id: Optional[str] = None):
    query = {}
    if status:
        query["status"] = status
    if game_id:
        query["game_id"] = game_id
    tournaments = await db.tournaments.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    for t in tournaments:
        reg_count = await db.registrations.count_documents({"tournament_id": t["id"]})
        t["registered_count"] = reg_count
    return tournaments

@api_router.post("/tournaments")
async def create_tournament(body: TournamentCreate):
    game = await db.games.find_one({"id": body.game_id}, {"_id": 0})
    if not game:
        raise HTTPException(404, "Game not found")
    doc = {
        "id": str(uuid.uuid4()),
        "status": "registration",
        "bracket": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **body.model_dump(),
        "game_name": game["name"],
    }
    await db.tournaments.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/tournaments/{tournament_id}")
async def get_tournament(tournament_id: str):
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    reg_count = await db.registrations.count_documents({"tournament_id": tournament_id})
    t["registered_count"] = reg_count
    return t

@api_router.put("/tournaments/{tournament_id}")
async def update_tournament(tournament_id: str, body: TournamentUpdate):
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.tournaments.update_one({"id": tournament_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Tournament not found")
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    return t

@api_router.delete("/tournaments/{tournament_id}")
async def delete_tournament(tournament_id: str):
    await db.tournaments.delete_one({"id": tournament_id})
    await db.registrations.delete_many({"tournament_id": tournament_id})
    return {"status": "deleted"}

# ─── Registration Endpoints ───

@api_router.get("/tournaments/{tournament_id}/registrations")
async def list_registrations(tournament_id: str):
    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(200)
    return regs

@api_router.post("/tournaments/{tournament_id}/register")
async def register_for_tournament(request: Request, tournament_id: str, body: RegistrationCreate):
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    if t["status"] not in ("registration", "checkin"):
        raise HTTPException(400, "Registration is closed")
    reg_count = await db.registrations.count_documents({"tournament_id": tournament_id})
    if reg_count >= t["max_participants"]:
        raise HTTPException(400, "Tournament is full")
    user = await get_current_user(request)
    payment_status = "free" if t["entry_fee"] <= 0 else "pending"
    doc = {
        "id": str(uuid.uuid4()),
        "tournament_id": tournament_id,
        "team_name": body.team_name,
        "players": body.players,
        "team_id": body.team_id,
        "user_id": user["id"] if user else None,
        "checked_in": False,
        "payment_status": payment_status,
        "payment_session_id": None,
        "seed": reg_count + 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.registrations.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.post("/tournaments/{tournament_id}/checkin/{registration_id}")
async def checkin(tournament_id: str, registration_id: str):
    reg = await db.registrations.find_one({"id": registration_id, "tournament_id": tournament_id}, {"_id": 0})
    if not reg:
        raise HTTPException(404, "Registration not found")
    if reg["payment_status"] == "pending":
        raise HTTPException(400, "Payment required before check-in")
    await db.registrations.update_one({"id": registration_id}, {"$set": {"checked_in": True}})
    reg["checked_in"] = True
    return reg

# ─── Bracket Generation ───

def get_round_name(round_num, total_rounds):
    remaining = total_rounds - round_num
    if remaining == 0:
        return "Grand Final"
    if remaining == 1:
        return "Semi-Final"
    if remaining == 2:
        return "Quarter-Final"
    return f"Round {round_num}"

def generate_single_elimination(registrations):
    n = len(registrations)
    if n < 2:
        return {"type": "single_elimination", "rounds": [], "total_rounds": 0}
    num_rounds = math.ceil(math.log2(n))
    total_slots = 2 ** num_rounds
    participants = list(registrations)
    while len(participants) < total_slots:
        participants.append(None)
    rounds = []
    matches_per_round = total_slots // 2
    for r in range(1, num_rounds + 1):
        round_matches = []
        for m in range(matches_per_round):
            round_matches.append({
                "id": str(uuid.uuid4()),
                "round": r,
                "position": m,
                "team1_id": None,
                "team1_name": "TBD",
                "team2_id": None,
                "team2_name": "TBD",
                "score1": 0,
                "score2": 0,
                "winner_id": None,
                "status": "pending",
            })
        rounds.append({
            "round": r,
            "name": get_round_name(r, num_rounds),
            "matches": round_matches,
        })
        matches_per_round //= 2

    # Fill round 1
    for i, match in enumerate(rounds[0]["matches"]):
        p1 = participants[i * 2]
        p2 = participants[i * 2 + 1]
        if p1:
            match["team1_id"] = p1["id"]
            match["team1_name"] = p1["team_name"]
        else:
            match["team1_name"] = "BYE"
        if p2:
            match["team2_id"] = p2["id"]
            match["team2_name"] = p2["team_name"]
        else:
            match["team2_name"] = "BYE"
        # Auto-advance byes
        if p1 and not p2:
            match["winner_id"] = p1["id"]
            match["status"] = "completed"
        elif p2 and not p1:
            match["winner_id"] = p2["id"]
            match["status"] = "completed"
        elif not p1 and not p2:
            match["status"] = "completed"

    # Propagate byes
    for r_idx in range(len(rounds) - 1):
        for m_idx, match in enumerate(rounds[r_idx]["matches"]):
            if match["winner_id"]:
                next_match = rounds[r_idx + 1]["matches"][m_idx // 2]
                slot = "team1" if m_idx % 2 == 0 else "team2"
                winner_name = match["team1_name"] if match["winner_id"] == match["team1_id"] else match["team2_name"]
                next_match[f"{slot}_id"] = match["winner_id"]
                next_match[f"{slot}_name"] = winner_name

    return {"type": "single_elimination", "rounds": rounds, "total_rounds": num_rounds}

def generate_double_elimination(registrations):
    # Generate winners bracket as single elimination
    wb = generate_single_elimination(registrations)
    wb_rounds = wb["rounds"]
    # Create losers bracket skeleton
    n = len(registrations)
    if n < 2:
        return {"type": "double_elimination", "winners_bracket": wb, "losers_bracket": {"rounds": []}, "grand_final": None}
    num_lb_rounds = (len(wb_rounds) - 1) * 2
    lb_rounds = []
    for r in range(1, num_lb_rounds + 1):
        num_matches = max(1, n // (2 ** (r // 2 + 1)))
        round_matches = []
        for m in range(num_matches):
            round_matches.append({
                "id": str(uuid.uuid4()),
                "round": r,
                "position": m,
                "team1_id": None,
                "team1_name": "TBD",
                "team2_id": None,
                "team2_name": "TBD",
                "score1": 0,
                "score2": 0,
                "winner_id": None,
                "status": "pending",
            })
        lb_rounds.append({
            "round": r,
            "name": f"Losers Round {r}",
            "matches": round_matches,
        })
    grand_final = {
        "id": str(uuid.uuid4()),
        "round": 1,
        "position": 0,
        "team1_id": None,
        "team1_name": "Winners Bracket Champion",
        "team2_id": None,
        "team2_name": "Losers Bracket Champion",
        "score1": 0,
        "score2": 0,
        "winner_id": None,
        "status": "pending",
    }
    return {
        "type": "double_elimination",
        "winners_bracket": {"rounds": wb_rounds, "total_rounds": wb.get("total_rounds", 0)},
        "losers_bracket": {"rounds": lb_rounds},
        "grand_final": grand_final,
    }

def generate_round_robin(registrations):
    n = len(registrations)
    rounds = []
    round_num = 1
    for i in range(n):
        for j in range(i + 1, n):
            match = {
                "id": str(uuid.uuid4()),
                "round": round_num,
                "position": 0,
                "team1_id": registrations[i]["id"],
                "team1_name": registrations[i]["team_name"],
                "team2_id": registrations[j]["id"],
                "team2_name": registrations[j]["team_name"],
                "score1": 0,
                "score2": 0,
                "winner_id": None,
                "status": "pending",
            }
            found = False
            for rd in rounds:
                if rd["round"] == round_num:
                    rd["matches"].append(match)
                    found = True
                    break
            if not found:
                rounds.append({"round": round_num, "name": f"Round {round_num}", "matches": [match]})
            round_num += 1
    return {"type": "round_robin", "rounds": rounds, "total_rounds": len(rounds)}

@api_router.post("/tournaments/{tournament_id}/generate-bracket")
async def generate_bracket(tournament_id: str):
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).sort("seed", 1).to_list(200)
    if len(regs) < 2:
        raise HTTPException(400, "Need at least 2 registrations to generate bracket")
    bracket_type = t.get("bracket_type", "single_elimination")
    if bracket_type == "single_elimination":
        bracket = generate_single_elimination(regs)
    elif bracket_type == "double_elimination":
        bracket = generate_double_elimination(regs)
    elif bracket_type == "round_robin":
        bracket = generate_round_robin(regs)
    else:
        bracket = generate_single_elimination(regs)
    await db.tournaments.update_one(
        {"id": tournament_id},
        {"$set": {"bracket": bracket, "status": "live", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    return t

# ─── Match Score Updates ───

@api_router.put("/tournaments/{tournament_id}/matches/{match_id}/score")
async def update_match_score(tournament_id: str, match_id: str, body: ScoreUpdate):
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t or not t.get("bracket"):
        raise HTTPException(404, "Tournament or bracket not found")
    bracket = t["bracket"]
    bracket_type = bracket.get("type", "single_elimination")

    if bracket_type == "single_elimination":
        rounds = bracket["rounds"]
    elif bracket_type == "double_elimination":
        # Check all sub-brackets
        rounds = bracket.get("winners_bracket", {}).get("rounds", [])
        # Also check losers bracket and grand final
    elif bracket_type == "round_robin":
        rounds = bracket["rounds"]
    else:
        rounds = bracket.get("rounds", [])

    match_found = False
    match_round_idx = -1
    match_pos = -1

    for r_idx, rd in enumerate(rounds):
        for m_idx, m in enumerate(rd["matches"]):
            if m["id"] == match_id:
                m["score1"] = body.score1
                m["score2"] = body.score2
                if body.winner_id:
                    m["winner_id"] = body.winner_id
                elif body.score1 > body.score2:
                    m["winner_id"] = m["team1_id"]
                elif body.score2 > body.score1:
                    m["winner_id"] = m["team2_id"]
                m["status"] = "completed"
                match_found = True
                match_round_idx = r_idx
                match_pos = m_idx
                break
        if match_found:
            break

    if not match_found:
        # Check double elimination sub-brackets
        if bracket_type == "double_elimination":
            gf = bracket.get("grand_final")
            if gf and gf["id"] == match_id:
                gf["score1"] = body.score1
                gf["score2"] = body.score2
                if body.winner_id:
                    gf["winner_id"] = body.winner_id
                elif body.score1 > body.score2:
                    gf["winner_id"] = gf["team1_id"]
                else:
                    gf["winner_id"] = gf["team2_id"]
                gf["status"] = "completed"
                match_found = True
        if not match_found:
            raise HTTPException(404, "Match not found")

    # Propagate winner to next round (single elimination)
    if bracket_type == "single_elimination" and match_round_idx >= 0 and match_round_idx < len(rounds) - 1:
        current_match = rounds[match_round_idx]["matches"][match_pos]
        if current_match["winner_id"]:
            next_match = rounds[match_round_idx + 1]["matches"][match_pos // 2]
            slot = "team1" if match_pos % 2 == 0 else "team2"
            winner_name = current_match["team1_name"] if current_match["winner_id"] == current_match["team1_id"] else current_match["team2_name"]
            next_match[f"{slot}_id"] = current_match["winner_id"]
            next_match[f"{slot}_name"] = winner_name

    # Check if tournament is completed
    if bracket_type == "single_elimination":
        final_match = rounds[-1]["matches"][0]
        if final_match.get("winner_id"):
            await db.tournaments.update_one({"id": tournament_id}, {"$set": {"status": "completed"}})

    await db.tournaments.update_one(
        {"id": tournament_id},
        {"$set": {"bracket": bracket, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    return updated

# ─── Payment Endpoints (Stripe) ───

@api_router.post("/payments/create-checkout")
async def create_checkout(request: Request, body: PaymentRequest):
    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    t = await db.tournaments.find_one({"id": body.tournament_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    entry_fee = t.get("entry_fee", 0)
    if entry_fee <= 0:
        raise HTTPException(400, "This tournament is free")
    reg = await db.registrations.find_one({"id": body.registration_id}, {"_id": 0})
    if not reg:
        raise HTTPException(404, "Registration not found")
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(500, "Payment system not configured")
    host_url = body.origin_url.rstrip("/")
    success_url = f"{host_url}/tournaments/{body.tournament_id}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/tournaments/{body.tournament_id}"
    webhook_url = f"{str(request.base_url).rstrip('/')}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    checkout_request = CheckoutSessionRequest(
        amount=float(entry_fee),
        currency=t.get("currency", "usd"),
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"tournament_id": body.tournament_id, "registration_id": body.registration_id},
    )
    session = await stripe_checkout.create_checkout_session(checkout_request)
    payment_doc = {
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "tournament_id": body.tournament_id,
        "registration_id": body.registration_id,
        "amount": float(entry_fee),
        "currency": t.get("currency", "usd"),
        "payment_status": "pending",
        "status": "initiated",
        "metadata": {"tournament_id": body.tournament_id, "registration_id": body.registration_id},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(payment_doc)
    await db.registrations.update_one({"id": body.registration_id}, {"$set": {"payment_session_id": session.session_id}})
    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/payments/status/{session_id}")
async def check_payment_status(request: Request, session_id: str):
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(500, "Payment system not configured")
    webhook_url = f"{str(request.base_url).rstrip('/')}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    try:
        checkout_status = await stripe_checkout.get_checkout_status(session_id)
    except Exception as e:
        logger.error(f"Stripe checkout status error: {e}")
        raise HTTPException(404, "Payment session not found")
    # Update payment transaction
    existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if existing and existing.get("payment_status") != "paid":
        new_status = checkout_status.payment_status
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": new_status, "status": checkout_status.status}}
        )
        if new_status == "paid":
            await db.registrations.update_one(
                {"id": existing["registration_id"]},
                {"$set": {"payment_status": "paid"}}
            )
    return {
        "status": checkout_status.status,
        "payment_status": checkout_status.payment_status,
        "amount_total": checkout_status.amount_total,
        "currency": checkout_status.currency,
    }

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    webhook_url = f"{str(request.base_url).rstrip('/')}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    try:
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        if webhook_response.payment_status == "paid":
            session_id = webhook_response.session_id
            existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            if existing and existing.get("payment_status") != "paid":
                await db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": {"payment_status": "paid", "status": "complete"}}
                )
                await db.registrations.update_one(
                    {"id": existing["registration_id"]},
                    {"$set": {"payment_status": "paid"}}
                )
        return {"status": "processed"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

# ─── Comment Endpoints ───

@api_router.get("/tournaments/{tournament_id}/comments")
async def list_tournament_comments(tournament_id: str):
    comments = await db.comments.find({"target_type": "tournament", "target_id": tournament_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return comments

@api_router.post("/tournaments/{tournament_id}/comments")
async def create_tournament_comment(request: Request, tournament_id: str, body: CommentCreate):
    user = await require_auth(request)
    doc = {
        "id": str(uuid.uuid4()),
        "target_type": "tournament",
        "target_id": tournament_id,
        "author_id": user["id"],
        "author_name": user["username"],
        "author_avatar": user.get("avatar_url", ""),
        "message": body.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.comments.insert_one(doc)
    doc.pop("_id", None)
    # Create notifications for tournament participants
    regs = await db.registrations.find({"tournament_id": tournament_id, "user_id": {"$nin": [None, user["id"]]}}, {"_id": 0}).to_list(200)
    for reg in regs:
        if reg.get("user_id") and reg["user_id"] != user["id"]:
            notif = {
                "id": str(uuid.uuid4()),
                "user_id": reg["user_id"],
                "type": "comment",
                "message": f"{user['username']} hat einen Kommentar im Turnier geschrieben",
                "link": f"/tournaments/{tournament_id}",
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.notifications.insert_one(notif)
    return doc

@api_router.get("/matches/{match_id}/comments")
async def list_match_comments(match_id: str):
    comments = await db.comments.find({"target_type": "match", "target_id": match_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return comments

@api_router.post("/matches/{match_id}/comments")
async def create_match_comment(request: Request, match_id: str, body: CommentCreate):
    user = await require_auth(request)
    doc = {
        "id": str(uuid.uuid4()),
        "target_type": "match",
        "target_id": match_id,
        "author_id": user["id"],
        "author_name": user["username"],
        "author_avatar": user.get("avatar_url", ""),
        "message": body.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.comments.insert_one(doc)
    doc.pop("_id", None)
    return doc

# ─── Notification Endpoints ───

@api_router.get("/notifications")
async def list_notifications(request: Request):
    user = await require_auth(request)
    notifications = await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return notifications

@api_router.get("/notifications/unread-count")
async def unread_count(request: Request):
    user = await require_auth(request)
    count = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"count": count}

@api_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(request: Request, notification_id: str):
    user = await require_auth(request)
    await db.notifications.update_one({"id": notification_id, "user_id": user["id"]}, {"$set": {"read": True}})
    return {"status": "ok"}

@api_router.put("/notifications/read-all")
async def mark_all_read(request: Request):
    user = await require_auth(request)
    await db.notifications.update_many({"user_id": user["id"], "read": False}, {"$set": {"read": True}})
    return {"status": "ok"}

# ─── Match Scheduling ───

@api_router.get("/matches/{match_id}/schedule")
async def get_match_schedule(match_id: str):
    proposals = await db.schedule_proposals.find({"match_id": match_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return proposals

@api_router.post("/matches/{match_id}/schedule")
async def propose_match_time(request: Request, match_id: str, body: TimeProposal):
    user = await require_auth(request)
    doc = {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "proposed_by": user["id"],
        "proposed_by_name": user["username"],
        "proposed_time": body.proposed_time,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.schedule_proposals.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/matches/{match_id}/schedule/{proposal_id}/accept")
async def accept_schedule(request: Request, match_id: str, proposal_id: str):
    user = await require_auth(request)
    await db.schedule_proposals.update_many({"match_id": match_id}, {"$set": {"status": "rejected"}})
    await db.schedule_proposals.update_one({"id": proposal_id}, {"$set": {"status": "accepted"}})
    proposal = await db.schedule_proposals.find_one({"id": proposal_id}, {"_id": 0})
    if proposal and proposal.get("proposed_by") != user["id"]:
        notif = {
            "id": str(uuid.uuid4()),
            "user_id": proposal["proposed_by"],
            "type": "schedule",
            "message": f"{user['username']} hat deinen Zeitvorschlag akzeptiert",
            "link": "",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.notifications.insert_one(notif)
    return {"status": "accepted"}

# ─── Admin Endpoints ───

@api_router.get("/admin/settings")
async def get_admin_settings(request: Request):
    await require_admin(request)
    settings = await db.admin_settings.find({}, {"_id": 0}).to_list(50)
    return settings

@api_router.put("/admin/settings")
async def update_admin_setting(request: Request, body: AdminSettingUpdate):
    await require_admin(request)
    await db.admin_settings.update_one(
        {"key": body.key},
        {"$set": {"key": body.key, "value": body.value, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"status": "ok"}

@api_router.get("/admin/users")
async def list_admin_users(request: Request):
    await require_admin(request)
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(200)
    return users

@api_router.get("/admin/dashboard")
async def admin_dashboard(request: Request):
    await require_admin(request)
    total_users = await db.users.count_documents({})
    total_teams = await db.teams.count_documents({})
    total_tournaments = await db.tournaments.count_documents({})
    total_registrations = await db.registrations.count_documents({})
    live_tournaments = await db.tournaments.count_documents({"status": "live"})
    total_payments = await db.payment_transactions.count_documents({"payment_status": "paid"})
    return {
        "total_users": total_users,
        "total_teams": total_teams,
        "total_tournaments": total_tournaments,
        "total_registrations": total_registrations,
        "live_tournaments": live_tournaments,
        "total_payments": total_payments,
    }

# ─── Stats ───

@api_router.get("/stats")
async def get_stats():
    total_tournaments = await db.tournaments.count_documents({})
    live_tournaments = await db.tournaments.count_documents({"status": "live"})
    total_registrations = await db.registrations.count_documents({})
    total_games = await db.games.count_documents({})
    return {
        "total_tournaments": total_tournaments,
        "live_tournaments": live_tournaments,
        "total_registrations": total_registrations,
        "total_games": total_games,
    }

# ─── App Setup ───

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await seed_games()
    await seed_admin()
    logger.info("eSports Tournament System started")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
