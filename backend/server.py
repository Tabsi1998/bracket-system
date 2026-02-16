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
    score1: int = Field(ge=0)
    score2: int = Field(ge=0)
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
    score1: int = Field(ge=0)
    score2: int = Field(ge=0)

class AdminScoreResolve(BaseModel):
    score1: int = Field(ge=0)
    score2: int = Field(ge=0)
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

def generate_join_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

async def send_email_notification(to_email: str, subject: str, body_text: str):
    """Send email if SMTP is configured in admin settings."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        smtp_host = await db.admin_settings.find_one({"key": "smtp_host"}, {"_id": 0})
        smtp_port = await db.admin_settings.find_one({"key": "smtp_port"}, {"_id": 0})
        smtp_user = await db.admin_settings.find_one({"key": "smtp_user"}, {"_id": 0})
        smtp_pass = await db.admin_settings.find_one({"key": "smtp_password"}, {"_id": 0})
        if not all([smtp_host, smtp_port, smtp_user, smtp_pass]):
            return
        msg = MIMEText(body_text, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = smtp_user["value"]
        msg["To"] = to_email
        with smtplib.SMTP(smtp_host["value"], int(smtp_port["value"]), timeout=10) as server:
            server.starttls()
            server.login(smtp_user["value"], smtp_pass["value"])
            server.send_message(msg)
        logger.info(f"Email sent to {to_email}")
    except Exception as e:
        logger.warning(f"Email send failed: {e}")

async def get_user_team_role(user_id: str, team_id: str):
    """Returns 'owner', 'leader', 'member', or None."""
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        return None
    if team.get("owner_id") == user_id:
        return "owner"
    if user_id in team.get("leader_ids", []):
        return "leader"
    if user_id in team.get("member_ids", []):
        return "member"
    return None

async def get_stripe_api_key() -> Optional[str]:
    """Resolve Stripe key from env first, then admin settings."""
    env_key = os.environ.get("STRIPE_API_KEY", "").strip()
    if env_key:
        return env_key
    setting = await db.admin_settings.find_one({"key": "stripe_secret_key"}, {"_id": 0})
    value = (setting or {}).get("value", "").strip()
    return value or None

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
    email = body.email.strip().lower()
    username = body.username.strip()
    if not username:
        raise HTTPException(400, "Benutzername erforderlich")
    if not email:
        raise HTTPException(400, "E-Mail erforderlich")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "E-Mail bereits registriert")
    if await db.users.find_one({"username": username}):
        raise HTTPException(400, "Benutzername bereits vergeben")
    user_doc = {
        "id": str(uuid.uuid4()), "username": username, "email": email,
        "password_hash": hash_password(body.password), "role": "user",
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)
    token = create_token(user_doc["id"], user_doc["email"], user_doc["role"])
    return {"token": token, "user": {"id": user_doc["id"], "username": user_doc["username"], "email": user_doc["email"], "role": user_doc["role"], "avatar_url": user_doc["avatar_url"]}}

@api_router.post("/auth/login")
async def login_user(body: UserLogin):
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Ungültige Anmeldedaten")
    token = create_token(user["id"], user["email"], user.get("role", "user"))
    return {"token": token, "user": {"id": user["id"], "username": user["username"], "email": user["email"], "role": user.get("role", "user"), "avatar_url": user.get("avatar_url", "")}}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await require_auth(request)
    return user

async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@arena.gg").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    default_username = os.environ.get("ADMIN_USERNAME", admin_email.split("@")[0] or "admin").strip()
    username = default_username or "admin"

    existing_with_email = await db.users.find_one({"email": admin_email}, {"_id": 0})
    if existing_with_email:
        update_doc = {
            "role": "admin",
            "password_hash": hash_password(admin_password),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if not existing_with_email.get("username"):
            update_doc["username"] = username
        await db.users.update_one(
            {"id": existing_with_email["id"]},
            {
                "$set": update_doc
            },
        )
        logger.info(f"Promoted existing user to admin: {admin_email}")
        return

    existing_admin = await db.users.find_one({"role": "admin"}, {"_id": 0})
    if existing_admin:
        logger.info(f"Admin already exists ({existing_admin.get('email', 'unknown')}); configured admin user not created")
        return

    if await db.users.find_one({"username": username}, {"_id": 0}):
        username = f"{username}_{uuid.uuid4().hex[:6]}"

    admin_doc = {
        "id": str(uuid.uuid4()), "username": username, "email": admin_email,
        "password_hash": hash_password(admin_password), "role": "admin",
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(admin_doc)
    logger.info(f"Admin user seeded: {admin_email}")

# ─── Team Endpoints ───

@api_router.get("/teams")
async def list_teams(request: Request):
    user = await require_auth(request)
    teams = await db.teams.find({"$or": [{"owner_id": user["id"]}, {"member_ids": user["id"]}], "parent_team_id": {"$in": [None, ""]}}, {"_id": 0}).to_list(100)
    # Strip join_code for non-owners
    result = []
    for t in teams:
        if t.get("owner_id") != user["id"]:
            t.pop("join_code", None)
        result.append(t)
    return result

@api_router.post("/teams")
async def create_team(request: Request, body: TeamCreate):
    user = await require_auth(request)
    doc = {
        "id": str(uuid.uuid4()), "name": body.name, "tag": body.tag,
        "owner_id": user["id"], "owner_name": user["username"],
        "join_code": generate_join_code(),
        "member_ids": [user["id"]],
        "leader_ids": [user["id"]],
        "members": [{"id": user["id"], "username": user["username"], "email": user["email"], "role": "owner"}],
        "parent_team_id": body.parent_team_id or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.teams.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/teams/{team_id}")
async def get_team(request: Request, team_id: str):
    user = await get_current_user(request)
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")
    # Hide join_code for non-owners
    if not user or team.get("owner_id") != user.get("id"):
        team.pop("join_code", None)
    return team

@api_router.delete("/teams/{team_id}")
async def delete_team(request: Request, team_id: str):
    user = await require_auth(request)
    result = await db.teams.delete_one({"id": team_id, "owner_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Team nicht gefunden")
    # Also delete sub-teams
    await db.teams.delete_many({"parent_team_id": team_id})
    return {"status": "deleted"}

@api_router.post("/teams/join")
async def join_team(request: Request, body: TeamJoinRequest):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": body.team_id}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")
    if team.get("join_code") != body.join_code:
        raise HTTPException(403, "Falscher Beitrittscode")
    if user["id"] in team.get("member_ids", []):
        raise HTTPException(400, "Bereits Teammitglied")
    await db.teams.update_one({"id": body.team_id}, {
        "$push": {"member_ids": user["id"], "members": {"id": user["id"], "username": user["username"], "email": user["email"], "role": "member"}}
    })
    updated = await db.teams.find_one({"id": body.team_id}, {"_id": 0})
    updated.pop("join_code", None)
    return updated

@api_router.put("/teams/{team_id}/regenerate-code")
async def regenerate_join_code(request: Request, team_id: str):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id, "owner_id": user["id"]}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden oder keine Berechtigung")
    new_code = generate_join_code()
    await db.teams.update_one({"id": team_id}, {"$set": {"join_code": new_code}})
    return {"join_code": new_code}

@api_router.post("/teams/{team_id}/members")
async def add_team_member(request: Request, team_id: str, body: TeamAddMember):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")
    if team.get("owner_id") != user["id"] and user["id"] not in team.get("leader_ids", []):
        raise HTTPException(403, "Nur Owner oder Leader können Mitglieder hinzufügen")
    member = await db.users.find_one({"email": body.email}, {"_id": 0, "password_hash": 0})
    if not member:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if member["id"] in team.get("member_ids", []):
        raise HTTPException(400, "Bereits Teammitglied")
    await db.teams.update_one({"id": team_id}, {"$push": {"member_ids": member["id"], "members": {"id": member["id"], "username": member["username"], "email": member["email"], "role": "member"}}})
    return await db.teams.find_one({"id": team_id}, {"_id": 0})

@api_router.delete("/teams/{team_id}/members/{member_id}")
async def remove_team_member(request: Request, team_id: str, member_id: str):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")
    if team.get("owner_id") != user["id"] and user["id"] not in team.get("leader_ids", []):
        raise HTTPException(403, "Keine Berechtigung")
    await db.teams.update_one({"id": team_id}, {"$pull": {"member_ids": member_id, "members": {"id": member_id}, "leader_ids": member_id}})
    return await db.teams.find_one({"id": team_id}, {"_id": 0})

@api_router.put("/teams/{team_id}/leaders/{user_id}")
async def promote_to_leader(request: Request, team_id: str, user_id: str):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id, "owner_id": user["id"]}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Nur der Team-Owner kann Leader ernennen")
    if user_id not in team.get("member_ids", []):
        raise HTTPException(400, "Benutzer ist kein Teammitglied")
    if user_id in team.get("leader_ids", []):
        raise HTTPException(400, "Bereits Leader")
    await db.teams.update_one({"id": team_id}, {"$push": {"leader_ids": user_id}})
    await db.teams.update_one({"id": team_id, "members.id": user_id}, {"$set": {"members.$.role": "leader"}})
    return await db.teams.find_one({"id": team_id}, {"_id": 0})

@api_router.delete("/teams/{team_id}/leaders/{user_id}")
async def demote_leader(request: Request, team_id: str, user_id: str):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id, "owner_id": user["id"]}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Nur der Team-Owner kann Leader entfernen")
    await db.teams.update_one({"id": team_id}, {"$pull": {"leader_ids": user_id}})
    await db.teams.update_one({"id": team_id, "members.id": user_id}, {"$set": {"members.$.role": "member"}})
    return await db.teams.find_one({"id": team_id}, {"_id": 0})

@api_router.get("/teams/{team_id}/sub-teams")
async def list_sub_teams(request: Request, team_id: str):
    user = await require_auth(request)
    subs = await db.teams.find({"parent_team_id": team_id}, {"_id": 0}).to_list(50)
    for s in subs:
        if s.get("owner_id") != user["id"]:
            s.pop("join_code", None)
    return subs

# ─── Game Endpoints ───

@api_router.get("/games")
async def list_games(category: Optional[str] = None):
    query = {}
    if category:
        query["category"] = category
    games = await db.games.find(query, {"_id": 0}).to_list(100)
    return games

@api_router.post("/games")
async def create_game(request: Request, body: GameCreate):
    await require_admin(request)
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
async def update_game(request: Request, game_id: str, body: GameCreate):
    await require_admin(request)
    result = await db.games.update_one({"id": game_id}, {"$set": body.model_dump()})
    if result.matched_count == 0:
        raise HTTPException(404, "Game not found")
    game = await db.games.find_one({"id": game_id}, {"_id": 0})
    return game

@api_router.delete("/games/{game_id}")
async def delete_game(request: Request, game_id: str):
    await require_admin(request)
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
async def create_tournament(request: Request, body: TournamentCreate):
    await require_admin(request)
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
async def update_tournament(request: Request, tournament_id: str, body: TournamentUpdate):
    await require_admin(request)
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.tournaments.update_one({"id": tournament_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(404, "Tournament not found")
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    return t

@api_router.delete("/tournaments/{tournament_id}")
async def delete_tournament(request: Request, tournament_id: str):
    await require_admin(request)
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
    team_name = body.team_name.strip()
    if not team_name:
        raise HTTPException(400, "Team-Name ist erforderlich")

    expected_team_size = max(1, int(t.get("team_size", 1)))
    if len(body.players) != expected_team_size:
        raise HTTPException(400, f"Es werden genau {expected_team_size} Spieler benötigt")

    normalized_players = []
    seen_emails = set()
    for p in body.players:
        name = str(p.get("name", "")).strip() if isinstance(p, dict) else ""
        email = str(p.get("email", "")).strip().lower() if isinstance(p, dict) else ""
        if not name or not email:
            raise HTTPException(400, "Alle Spieler benötigen Name und E-Mail")
        if email in seen_emails:
            raise HTTPException(400, "Spieler-E-Mails dürfen nicht doppelt sein")
        seen_emails.add(email)
        normalized_players.append({"name": name, "email": email})

    user = await get_current_user(request)
    team_id = body.team_id.strip() if isinstance(body.team_id, str) and body.team_id.strip() else None
    if team_id:
        team = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not team:
            raise HTTPException(404, "Team nicht gefunden")
        if not user:
            raise HTTPException(401, "Ein Login ist für Team-Registrierungen erforderlich")
        team_role = await get_user_team_role(user["id"], team_id)
        if team_role not in ("owner", "leader", "member"):
            raise HTTPException(403, "Du bist kein Mitglied dieses Teams")
        if await db.registrations.find_one({"tournament_id": tournament_id, "team_id": team_id}, {"_id": 0}):
            raise HTTPException(400, "Dieses Team ist bereits registriert")

    if user and not team_id and await db.registrations.find_one({"tournament_id": tournament_id, "user_id": user["id"]}, {"_id": 0}):
        raise HTTPException(400, "Du bist bereits für dieses Turnier registriert")

    payment_status = "free" if t["entry_fee"] <= 0 else "pending"
    doc = {
        "id": str(uuid.uuid4()),
        "tournament_id": tournament_id,
        "team_name": team_name,
        "players": normalized_players,
        "team_id": team_id,
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
async def checkin(request: Request, tournament_id: str, registration_id: str):
    user = await require_auth(request)
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    if t.get("status") != "checkin":
        raise HTTPException(400, "Check-in ist aktuell nicht aktiv")

    reg = await db.registrations.find_one({"id": registration_id, "tournament_id": tournament_id}, {"_id": 0})
    if not reg:
        raise HTTPException(404, "Registration not found")
    if reg.get("checked_in"):
        return reg
    if reg["payment_status"] == "pending":
        raise HTTPException(400, "Payment required before check-in")

    can_checkin = user.get("role") == "admin"
    if not can_checkin and reg.get("user_id") == user["id"]:
        can_checkin = True
    if not can_checkin and reg.get("team_id"):
        team_role = await get_user_team_role(user["id"], reg["team_id"])
        if team_role in ("owner", "leader"):
            can_checkin = True
    if not can_checkin:
        raise HTTPException(403, "Keine Berechtigung für diesen Check-in")

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
async def generate_bracket(request: Request, tournament_id: str):
    await require_admin(request)
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

# ─── Score Submission System ───

@api_router.post("/tournaments/{tournament_id}/matches/{match_id}/submit-score")
async def submit_match_score(request: Request, tournament_id: str, match_id: str, body: ScoreSubmission):
    """Teams/leaders submit their score. If both agree, auto-confirm."""
    user = await require_auth(request)
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t or not t.get("bracket"):
        raise HTTPException(404, "Turnier oder Bracket nicht gefunden")

    # Find the match in bracket to get team IDs
    match_data = None
    bracket = t["bracket"]
    all_rounds = []
    if bracket["type"] in ("single_elimination", "round_robin"):
        all_rounds = bracket.get("rounds", [])
    elif bracket["type"] == "double_elimination":
        all_rounds = bracket.get("winners_bracket", {}).get("rounds", [])
        all_rounds += bracket.get("losers_bracket", {}).get("rounds", [])
    for rd in all_rounds:
        for m in rd["matches"]:
            if m["id"] == match_id:
                match_data = m
                break
        if match_data:
            break
    if not match_data and bracket["type"] == "double_elimination":
        gf = bracket.get("grand_final")
        if gf and gf["id"] == match_id:
            match_data = gf
    if not match_data:
        raise HTTPException(404, "Match nicht gefunden")
    if match_data.get("status") == "completed":
        raise HTTPException(400, "Match ist bereits abgeschlossen")

    # Determine which team the user belongs to
    team1_reg = await db.registrations.find_one({"id": match_data["team1_id"]}, {"_id": 0})
    team2_reg = await db.registrations.find_one({"id": match_data["team2_id"]}, {"_id": 0})
    submitting_for = None
    if team1_reg:
        tid = team1_reg.get("team_id")
        if tid:
            role = await get_user_team_role(user["id"], tid)
            if role in ("owner", "leader"):
                submitting_for = "team1"
        if not submitting_for and team1_reg.get("user_id") == user["id"]:
            submitting_for = "team1"
    if not submitting_for and team2_reg:
        tid = team2_reg.get("team_id")
        if tid:
            role = await get_user_team_role(user["id"], tid)
            if role in ("owner", "leader"):
                submitting_for = "team2"
        if not submitting_for and team2_reg.get("user_id") == user["id"]:
            submitting_for = "team2"
    if not submitting_for:
        raise HTTPException(403, "Du bist kein Leader/Owner eines beteiligten Teams")

    # Store submission
    submission_filter = {"tournament_id": tournament_id, "match_id": match_id, "side": submitting_for}
    existing = await db.score_submissions.find_one(submission_filter, {"_id": 0})
    if existing:
        await db.score_submissions.update_one(submission_filter, {
            "$set": {"score1": body.score1, "score2": body.score2, "submitted_by": user["id"], "submitted_by_name": user["username"], "updated_at": datetime.now(timezone.utc).isoformat()}
        })
    else:
        await db.score_submissions.insert_one({
            "id": str(uuid.uuid4()), "tournament_id": tournament_id, "match_id": match_id,
            "side": submitting_for, "score1": body.score1, "score2": body.score2,
            "submitted_by": user["id"], "submitted_by_name": user["username"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Check if both sides submitted
    subs = await db.score_submissions.find({"tournament_id": tournament_id, "match_id": match_id}, {"_id": 0}).to_list(2)
    sides = {s["side"]: s for s in subs}
    if "team1" in sides and "team2" in sides:
        s1, s2 = sides["team1"], sides["team2"]
        if s1["score1"] == s2["score1"] and s1["score2"] == s2["score2"]:
            # Scores agree → auto-confirm
            await _apply_score_to_bracket(tournament_id, match_id, s1["score1"], s1["score2"])
            await db.score_submissions.update_many({"tournament_id": tournament_id, "match_id": match_id}, {"$set": {"status": "confirmed"}})
            return {"status": "confirmed", "message": "Ergebnisse stimmen überein - automatisch bestätigt!"}
        else:
            # Scores differ → disputed
            await db.score_submissions.update_many({"tournament_id": tournament_id, "match_id": match_id}, {"$set": {"status": "disputed"}})
            # Notify admins
            admins = await db.users.find({"role": "admin"}, {"_id": 0}).to_list(10)
            for admin in admins:
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()), "user_id": admin["id"], "type": "dispute",
                    "message": f"Ergebnis-Streit im Match: {match_data.get('team1_name')} vs {match_data.get('team2_name')}",
                    "link": f"/tournaments/{tournament_id}", "read": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            return {"status": "disputed", "message": "Ergebnisse stimmen nicht überein - Admin muss prüfen!"}

    return {"status": "submitted", "message": f"Ergebnis von {submitting_for} eingereicht. Warte auf die andere Seite."}

@api_router.get("/tournaments/{tournament_id}/matches/{match_id}/submissions")
async def get_score_submissions(tournament_id: str, match_id: str):
    subs = await db.score_submissions.find({"tournament_id": tournament_id, "match_id": match_id}, {"_id": 0}).to_list(10)
    return subs

async def _apply_score_to_bracket(tournament_id: str, match_id: str, score1: int, score2: int, winner_id: str = None, disqualify_id: str = None):
    """Internal: apply finalized score to bracket and propagate."""
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    bracket = t["bracket"]
    bracket_type = bracket.get("type", "single_elimination")
    rounds = []
    if bracket_type in ("single_elimination", "round_robin"):
        rounds = bracket["rounds"]
    elif bracket_type == "double_elimination":
        rounds = bracket.get("winners_bracket", {}).get("rounds", [])

    match_found = False
    match_round_idx = -1
    match_pos = -1
    for r_idx, rd in enumerate(rounds):
        for m_idx, m in enumerate(rd["matches"]):
            if m["id"] == match_id:
                m["score1"] = score1
                m["score2"] = score2
                if disqualify_id:
                    m["winner_id"] = m["team2_id"] if m["team1_id"] == disqualify_id else m["team1_id"]
                    m["disqualified"] = disqualify_id
                elif winner_id:
                    m["winner_id"] = winner_id
                elif score1 > score2:
                    m["winner_id"] = m["team1_id"]
                elif score2 > score1:
                    m["winner_id"] = m["team2_id"]
                m["status"] = "completed"
                match_found = True
                match_round_idx = r_idx
                match_pos = m_idx
                break
        if match_found:
            break

    if not match_found and bracket_type == "double_elimination":
        gf = bracket.get("grand_final")
        if gf and gf["id"] == match_id:
            gf["score1"] = score1
            gf["score2"] = score2
            if winner_id:
                gf["winner_id"] = winner_id
            elif score1 > score2:
                gf["winner_id"] = gf["team1_id"]
            else:
                gf["winner_id"] = gf["team2_id"]
            gf["status"] = "completed"
            match_found = True

    # Propagate winner (single elimination)
    if bracket_type == "single_elimination" and match_round_idx >= 0 and match_round_idx < len(rounds) - 1:
        cm = rounds[match_round_idx]["matches"][match_pos]
        if cm["winner_id"]:
            nm = rounds[match_round_idx + 1]["matches"][match_pos // 2]
            slot = "team1" if match_pos % 2 == 0 else "team2"
            wn = cm["team1_name"] if cm["winner_id"] == cm["team1_id"] else cm["team2_name"]
            nm[f"{slot}_id"] = cm["winner_id"]
            nm[f"{slot}_name"] = wn

    # Check completion
    if bracket_type == "single_elimination" and rounds:
        final = rounds[-1]["matches"][0]
        if final.get("winner_id"):
            await db.tournaments.update_one({"id": tournament_id}, {"$set": {"status": "completed"}})

    await db.tournaments.update_one({"id": tournament_id}, {"$set": {"bracket": bracket, "updated_at": datetime.now(timezone.utc).isoformat()}})

# Admin-only: resolve disputed scores or force-set scores
@api_router.put("/tournaments/{tournament_id}/matches/{match_id}/resolve")
async def admin_resolve_score(request: Request, tournament_id: str, match_id: str, body: AdminScoreResolve):
    await require_admin(request)
    await _apply_score_to_bracket(tournament_id, match_id, body.score1, body.score2, body.winner_id, body.disqualify_team_id)
    await db.score_submissions.update_many({"tournament_id": tournament_id, "match_id": match_id}, {"$set": {"status": "resolved_by_admin"}})
    return await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})

# Keep legacy admin score update for backwards compat
@api_router.put("/tournaments/{tournament_id}/matches/{match_id}/score")
async def update_match_score(request: Request, tournament_id: str, match_id: str, body: ScoreUpdate):
    await require_admin(request)
    await _apply_score_to_bracket(tournament_id, match_id, body.score1, body.score2, body.winner_id)
    return await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})

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
    reg = await db.registrations.find_one({"id": body.registration_id, "tournament_id": body.tournament_id}, {"_id": 0})
    if not reg:
        raise HTTPException(404, "Registration not found")
    if reg.get("payment_status") == "paid":
        raise HTTPException(400, "Registration is already paid")

    user = await get_current_user(request)
    if reg.get("user_id") and (not user or (user["id"] != reg["user_id"] and user.get("role") != "admin")):
        raise HTTPException(403, "Keine Berechtigung für diese Zahlung")

    stripe_api_key = await get_stripe_api_key()
    if not stripe_api_key:
        raise HTTPException(500, "Payment system not configured")
    host_url = body.origin_url.rstrip("/")
    if not (host_url.startswith("http://") or host_url.startswith("https://")):
        raise HTTPException(400, "Invalid origin URL")
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
    stripe_api_key = await get_stripe_api_key()
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
    stripe_api_key = await get_stripe_api_key()
    if not stripe_api_key:
        raise HTTPException(500, "Payment system not configured")
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

# ─── Profile Endpoint ───

@api_router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    teams = await db.teams.find({"member_ids": user_id, "parent_team_id": {"$in": [None, ""]}}, {"_id": 0, "join_code": 0}).to_list(50)
    regs = await db.registrations.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    tournament_ids = list(set(r["tournament_id"] for r in regs))
    tournaments = []
    for tid in tournament_ids[:20]:
        t = await db.tournaments.find_one({"id": tid}, {"_id": 0, "bracket": 0})
        if t:
            tournaments.append(t)
    wins = 0
    losses = 0
    for reg in regs:
        t = await db.tournaments.find_one({"id": reg["tournament_id"]}, {"_id": 0})
        if t and t.get("bracket"):
            all_matches = []
            b = t["bracket"]
            if b["type"] in ("single_elimination", "round_robin"):
                for rd in b.get("rounds", []):
                    all_matches.extend(rd["matches"])
            elif b["type"] == "double_elimination":
                for rd in b.get("winners_bracket", {}).get("rounds", []):
                    all_matches.extend(rd["matches"])
            for m in all_matches:
                if m.get("status") == "completed":
                    if m.get("team1_id") == reg["id"] or m.get("team2_id") == reg["id"]:
                        if m.get("winner_id") == reg["id"]:
                            wins += 1
                        else:
                            losses += 1
    return {
        **user,
        "teams": teams,
        "tournaments": tournaments,
        "stats": {"tournaments_played": len(regs), "wins": wins, "losses": losses},
    }

# ─── Widget Endpoint ───

@api_router.get("/widget/tournament/{tournament_id}")
async def get_widget_data(tournament_id: str):
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(200)
    return {"tournament": t, "registrations": regs, "embed_version": "1.0"}

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
