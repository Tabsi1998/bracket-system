from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import math
import re
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
import secrets
import string
from datetime import datetime, timezone, timedelta
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
    username: Optional[str] = ""
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class TeamCreate(BaseModel):
    name: str
    tag: str = ""
    parent_team_id: Optional[str] = None

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    tag: Optional[str] = None
    bio: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    discord_url: Optional[str] = None
    website_url: Optional[str] = None
    twitter_url: Optional[str] = None
    instagram_url: Optional[str] = None
    twitch_url: Optional[str] = None
    youtube_url: Optional[str] = None

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

class AdminUserRoleUpdate(BaseModel):
    role: str

class UserAccountUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    bio: Optional[str] = None
    discord_url: Optional[str] = None
    website_url: Optional[str] = None
    twitter_url: Optional[str] = None
    instagram_url: Optional[str] = None
    twitch_url: Optional[str] = None
    youtube_url: Optional[str] = None

class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str

# ─── JWT Auth ───

JWT_SECRET = os.environ.get("JWT_SECRET", "arena-esports-secret-2026-xk9m2")
JWT_ALGORITHM = "HS256"

def normalize_email(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").lower()

def is_valid_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value or "").strip()))

def normalize_optional_text(value: Optional[str], max_len: int = 1000) -> str:
    cleaned = str(value or "").strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned

def normalize_optional_url(value: Optional[str], *, max_len: int = 500) -> str:
    cleaned = normalize_optional_text(value, max_len=max_len)
    if not cleaned:
        return ""
    if not cleaned.startswith(("http://", "https://")):
        raise HTTPException(400, "URL muss mit http:// oder https:// beginnen")
    return cleaned

def exact_ci_regex(value: str, allow_outer_whitespace: bool = False) -> Dict[str, str]:
    escaped = re.escape(str(value or "").strip())
    if allow_outer_whitespace:
        escaped = rf"\s*{escaped}\s*"
    return {"$regex": f"^{escaped}$", "$options": "i"}

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        logger.warning("Invalid password hash format encountered during login")
        return False

def create_token(user_id: str, email: str, role: str = "user") -> str:
    payload = {"user_id": user_id, "email": email, "role": role, "exp": datetime.now(timezone.utc).timestamp() + 86400 * 7}
    return jose_jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        payload = jose_jwt.decode(auth_header[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0, "password_hash": 0, "password": 0})
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

def get_request_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return str(request.client.host).strip()
    return ""

def is_sub_team(team_doc: Dict) -> bool:
    return bool(str((team_doc or {}).get("parent_team_id") or "").strip())

async def collect_team_hierarchy_ids(root_team_id: str) -> List[str]:
    seen = set()
    ordered = []
    queue = [str(root_team_id or "").strip()]

    while queue:
        current_id = queue.pop(0)
        if not current_id or current_id in seen:
            continue
        seen.add(current_id)
        ordered.append(current_id)
        children = await db.teams.find({"parent_team_id": current_id}, {"_id": 0, "id": 1}).to_list(500)
        for child in children:
            child_id = str(child.get("id", "")).strip()
            if child_id and child_id not in seen:
                queue.append(child_id)

    return ordered

async def delete_teams_and_related(team_ids: List[str]) -> Dict[str, int]:
    valid_ids = [str(tid).strip() for tid in team_ids if str(tid).strip()]
    if not valid_ids:
        return {"deleted_teams": 0, "deleted_registrations": 0}

    reg_result = await db.registrations.delete_many({"team_id": {"$in": valid_ids}})
    team_result = await db.teams.delete_many({"id": {"$in": valid_ids}})
    return {
        "deleted_teams": int(team_result.deleted_count or 0),
        "deleted_registrations": int(reg_result.deleted_count or 0),
    }

async def delete_user_and_related_data(user_id: str) -> Dict[str, int]:
    user_id = str(user_id or "").strip()
    if not user_id:
        return {"deleted_users": 0, "deleted_teams": 0, "deleted_registrations": 0}

    owned = await db.teams.find({"owner_id": user_id}, {"_id": 0, "id": 1}).to_list(500)
    all_team_ids = []
    for team in owned:
        all_team_ids.extend(await collect_team_hierarchy_ids(team.get("id")))
    all_team_ids = list(dict.fromkeys(tid for tid in all_team_ids if tid))

    team_cleanup = await delete_teams_and_related(all_team_ids)

    await db.teams.update_many(
        {"member_ids": user_id},
        {"$pull": {"member_ids": user_id, "leader_ids": user_id, "members": {"id": user_id}}},
    )
    reg_result = await db.registrations.delete_many({"user_id": user_id})
    await db.notifications.delete_many({"user_id": user_id})
    await db.score_submissions.delete_many({"user_id": user_id})
    await db.comments.delete_many({"user_id": user_id})
    await db.payment_transactions.delete_many({"user_id": user_id})
    await db.schedule_proposals.delete_many({"$or": [{"proposed_by": user_id}, {"accepted_by": user_id}]})
    user_result = await db.users.delete_one({"id": user_id})

    return {
        "deleted_users": int(user_result.deleted_count or 0),
        "deleted_teams": int(team_cleanup.get("deleted_teams", 0)),
        "deleted_registrations": int((reg_result.deleted_count or 0) + team_cleanup.get("deleted_registrations", 0)),
    }

async def get_stripe_api_key() -> Optional[str]:
    """Resolve Stripe key from env first, then admin settings."""
    env_key = os.environ.get("STRIPE_API_KEY", "").strip()
    if env_key and env_key.lower() not in {"sk_test_placeholder", "placeholder", "changeme"}:
        return env_key
    setting = await db.admin_settings.find_one({"key": "stripe_secret_key"}, {"_id": 0})
    value = (setting or {}).get("value", "").strip()
    return value or None

def sanitize_registration(reg: Dict, include_private: bool = False, include_player_emails: bool = False) -> Dict:
    players = []
    for p in reg.get("players", []):
        if isinstance(p, dict):
            item = {"name": str(p.get("name", "")).strip()}
            if include_player_emails and p.get("email"):
                item["email"] = str(p.get("email", "")).strip().lower()
            players.append(item)
        else:
            players.append({"name": str(p).strip()})

    doc = {
        "id": reg.get("id"),
        "tournament_id": reg.get("tournament_id"),
        "team_id": reg.get("team_id"),
        "team_name": reg.get("team_name"),
        "team_logo_url": reg.get("team_logo_url", ""),
        "team_banner_url": reg.get("team_banner_url", ""),
        "team_tag": reg.get("team_tag", ""),
        "main_team_name": reg.get("main_team_name", ""),
        "players": players,
        "checked_in": bool(reg.get("checked_in", False)),
        "payment_status": reg.get("payment_status", "free"),
        "seed": reg.get("seed"),
        "created_at": reg.get("created_at"),
    }

    if include_private:
        doc["user_id"] = reg.get("user_id")
        doc["payment_session_id"] = reg.get("payment_session_id")

    return doc

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
    email = normalize_email(body.email)
    if not email:
        raise HTTPException(400, "E-Mail erforderlich")
    if not is_valid_email(email):
        raise HTTPException(400, "Ungültige E-Mail")
    if await db.users.find_one({"email": exact_ci_regex(email, allow_outer_whitespace=True)}):
        raise HTTPException(400, "E-Mail bereits registriert")

    requested_username = str(body.username or "").strip()
    username = requested_username or (email.split("@")[0] if "@" in email else "user")
    if not username:
        username = f"user_{uuid.uuid4().hex[:6]}"
    if await db.users.find_one({"username": exact_ci_regex(username, allow_outer_whitespace=True)}):
        username = f"{username}_{uuid.uuid4().hex[:6]}"

    user_doc = {
        "id": str(uuid.uuid4()), "username": username, "email": email,
        "password_hash": hash_password(body.password), "role": "user",
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}",
        "banner_url": "",
        "bio": "",
        "discord_url": "",
        "website_url": "",
        "twitter_url": "",
        "instagram_url": "",
        "twitch_url": "",
        "youtube_url": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user_doc)
    token = create_token(user_doc["id"], user_doc["email"], user_doc["role"])
    return {
        "token": token,
        "user": {
            "id": user_doc["id"],
            "username": user_doc["username"],
            "email": user_doc["email"],
            "role": user_doc["role"],
            "avatar_url": user_doc["avatar_url"],
            "banner_url": user_doc["banner_url"],
        },
    }

@api_router.post("/auth/login")
async def login_user(request: Request, body: UserLogin):
    email = normalize_email(body.email)
    if not email:
        raise HTTPException(400, "E-Mail erforderlich")

    user = await db.users.find_one({"email": exact_ci_regex(email, allow_outer_whitespace=True)})
    if not user:
        raise HTTPException(401, "Ungültige Anmeldedaten")

    password_hash = str(user.get("password_hash", "") or "")
    is_authenticated = verify_password(body.password, password_hash)

    if not is_authenticated and password_hash and password_hash == body.password:
        # One-time migration if legacy code stored plaintext in password_hash.
        password_hash = hash_password(body.password)
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"password_hash": password_hash}, "$unset": {"password": ""}},
        )
        is_authenticated = True

    if not is_authenticated and not password_hash and user.get("password"):
        # One-time migration from old plaintext schema.
        if str(user.get("password")) == body.password:
            password_hash = hash_password(body.password)
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"password_hash": password_hash}, "$unset": {"password": ""}},
            )
            is_authenticated = True

    if not is_authenticated:
        raise HTTPException(401, "Ungültige Anmeldedaten")

    user_id = user.get("id")
    if not user_id:
        user_id = str(uuid.uuid4())
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"id": user_id}})

    email = normalize_email(user.get("email", ""))
    username = str(user.get("username", ""))
    role = user.get("role", "user")
    avatar_url = user.get("avatar_url") or f"https://api.dicebear.com/7.x/avataaars/svg?seed={username or user_id}"
    banner_url = user.get("banner_url", "")

    normalize_updates = {}
    if user.get("email") != email:
        normalize_updates["email"] = email
    if username != username.strip():
        normalize_updates["username"] = username.strip()
        username = username.strip()
    normalize_updates["last_login_at"] = datetime.now(timezone.utc).isoformat()
    client_ip = get_request_client_ip(request)
    if client_ip:
        normalize_updates["last_login_ip"] = client_ip
    await db.users.update_one({"_id": user["_id"]}, {"$set": normalize_updates})

    token = create_token(user_id, email, role)
    return {"token": token, "user": {"id": user_id, "username": username, "email": email, "role": role, "avatar_url": avatar_url, "banner_url": banner_url}}

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await require_auth(request)
    return user

async def seed_admin():
    admin_email = normalize_email(os.environ.get("ADMIN_EMAIL", "admin@arena.gg"))
    if not admin_email or "@" not in admin_email:
        logger.warning("Invalid ADMIN_EMAIL in environment, falling back to admin@arena.gg")
        admin_email = "admin@arena.gg"

    admin_password = str(os.environ.get("ADMIN_PASSWORD", "admin123") or "").strip()
    if not admin_password:
        logger.warning("Empty ADMIN_PASSWORD in environment, falling back to admin123")
        admin_password = "admin123"

    default_username = os.environ.get("ADMIN_USERNAME", admin_email.split("@")[0] or "admin").strip()
    username = default_username or "admin"

    existing_with_email = await db.users.find_one(
        {"email": exact_ci_regex(admin_email, allow_outer_whitespace=True)},
    )
    if existing_with_email:
        update_doc = {
            "role": "admin",
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if not existing_with_email.get("id"):
            update_doc["id"] = str(uuid.uuid4())
        if not existing_with_email.get("username"):
            update_doc["username"] = username
        if not existing_with_email.get("avatar_url"):
            update_doc["avatar_url"] = f"https://api.dicebear.com/7.x/avataaars/svg?seed={update_doc.get('username', existing_with_email.get('username', username))}"
        if "banner_url" not in existing_with_email:
            update_doc["banner_url"] = ""
        update_filter = {"_id": existing_with_email["_id"]}
        await db.users.update_one(
            update_filter,
            {
                "$set": update_doc,
                "$unset": {"password": ""},
            },
        )
        logger.info(f"Promoted existing user to admin: {admin_email}")
        return

    if await db.users.find_one({"username": exact_ci_regex(username, allow_outer_whitespace=True)}, {"_id": 0}):
        username = f"{username}_{uuid.uuid4().hex[:6]}"

    admin_doc = {
        "id": str(uuid.uuid4()), "username": username, "email": admin_email,
        "password_hash": hash_password(admin_password), "role": "admin",
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={username}",
        "banner_url": "",
        "bio": "",
        "discord_url": "",
        "website_url": "",
        "twitter_url": "",
        "instagram_url": "",
        "twitch_url": "",
        "youtube_url": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(admin_doc)
    logger.info(f"Admin user seeded/ensured: {admin_email}")

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

@api_router.get("/teams/registerable-sub-teams")
async def list_registerable_sub_teams(request: Request):
    user = await require_auth(request)
    query = {
        "$or": [{"owner_id": user["id"]}, {"member_ids": user["id"]}],
        "parent_team_id": {"$nin": [None, ""]},
    }
    sub_teams = await db.teams.find(query, {"_id": 0}).to_list(300)

    parent_ids = list(dict.fromkeys(str(t.get("parent_team_id", "")).strip() for t in sub_teams if str(t.get("parent_team_id", "")).strip()))
    parent_docs = []
    if parent_ids:
        parent_docs = await db.teams.find({"id": {"$in": parent_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(300)
    parent_map = {p["id"]: p.get("name", "") for p in parent_docs}

    result = []
    for t in sub_teams:
        if t.get("owner_id") != user["id"]:
            t.pop("join_code", None)
        parent_id = str(t.get("parent_team_id", "")).strip()
        t["parent_team_name"] = parent_map.get(parent_id, "")
        t["is_sub_team"] = True
        result.append(t)
    result.sort(key=lambda item: (str(item.get("parent_team_name", "")).lower(), str(item.get("name", "")).lower()))
    return result

@api_router.post("/teams")
async def create_team(request: Request, body: TeamCreate):
    user = await require_auth(request)
    name = normalize_optional_text(body.name, max_len=80)
    if not name:
        raise HTTPException(400, "Team-Name ist erforderlich")
    tag = normalize_optional_text(body.tag, max_len=20)

    parent_team_id = str(body.parent_team_id or "").strip() or None
    if parent_team_id:
        parent = await db.teams.find_one({"id": parent_team_id}, {"_id": 0, "id": 1, "owner_id": 1, "parent_team_id": 1})
        if not parent:
            raise HTTPException(404, "Hauptteam nicht gefunden")
        if is_sub_team(parent):
            raise HTTPException(400, "Sub-Teams können nicht unter weiteren Sub-Teams erstellt werden")
        if parent.get("owner_id") != user["id"] and user.get("role") != "admin":
            raise HTTPException(403, "Nur der Owner des Hauptteams kann Sub-Teams erstellen")

    doc = {
        "id": str(uuid.uuid4()), "name": name, "tag": tag,
        "owner_id": user["id"], "owner_name": user["username"],
        "join_code": generate_join_code(),
        "member_ids": [user["id"]],
        "leader_ids": [user["id"]],
        "members": [{"id": user["id"], "username": user["username"], "email": user["email"], "role": "owner"}],
        "parent_team_id": parent_team_id,
        "bio": "",
        "logo_url": "",
        "banner_url": "",
        "discord_url": "",
        "website_url": "",
        "twitter_url": "",
        "instagram_url": "",
        "twitch_url": "",
        "youtube_url": "",
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

@api_router.put("/teams/{team_id}")
async def update_team(request: Request, team_id: str, body: TeamUpdate):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")

    is_owner = team.get("owner_id") == user["id"]
    is_leader = user["id"] in team.get("leader_ids", [])
    if not is_owner and not is_leader and user.get("role") != "admin":
        raise HTTPException(403, "Keine Berechtigung")

    updates = {}
    if body.name is not None:
        name = normalize_optional_text(body.name, max_len=80)
        if not name:
            raise HTTPException(400, "Team-Name darf nicht leer sein")
        updates["name"] = name
    if body.tag is not None:
        updates["tag"] = normalize_optional_text(body.tag, max_len=20)
    if body.bio is not None:
        updates["bio"] = normalize_optional_text(body.bio, max_len=1000)
    if body.logo_url is not None:
        updates["logo_url"] = normalize_optional_url(body.logo_url)
    if body.banner_url is not None:
        updates["banner_url"] = normalize_optional_url(body.banner_url)
    if body.discord_url is not None:
        updates["discord_url"] = normalize_optional_url(body.discord_url)
    if body.website_url is not None:
        updates["website_url"] = normalize_optional_url(body.website_url)
    if body.twitter_url is not None:
        updates["twitter_url"] = normalize_optional_url(body.twitter_url)
    if body.instagram_url is not None:
        updates["instagram_url"] = normalize_optional_url(body.instagram_url)
    if body.twitch_url is not None:
        updates["twitch_url"] = normalize_optional_url(body.twitch_url)
    if body.youtube_url is not None:
        updates["youtube_url"] = normalize_optional_url(body.youtube_url)

    if not updates:
        raise HTTPException(400, "Keine Änderungen übergeben")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.teams.update_one({"id": team_id}, {"$set": updates})

    # Keep registrations visually in sync for logo/name/tag.
    reg_updates = {}
    if "name" in updates:
        reg_updates["team_name"] = updates["name"]
    if "logo_url" in updates:
        reg_updates["team_logo_url"] = updates["logo_url"]
    if "banner_url" in updates:
        reg_updates["team_banner_url"] = updates["banner_url"]
    if "tag" in updates:
        reg_updates["team_tag"] = updates["tag"]
    if reg_updates:
        await db.registrations.update_many({"team_id": team_id}, {"$set": reg_updates})

    updated = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if updated and user.get("role") != "admin" and updated.get("owner_id") != user["id"]:
        updated.pop("join_code", None)
    return updated

@api_router.delete("/teams/{team_id}")
async def delete_team(request: Request, team_id: str):
    user = await require_auth(request)
    team = await db.teams.find_one({"id": team_id}, {"_id": 0, "id": 1, "owner_id": 1})
    if not team or team.get("owner_id") != user["id"]:
        raise HTTPException(404, "Team nicht gefunden")
    hierarchy_ids = await collect_team_hierarchy_ids(team_id)
    cleanup = await delete_teams_and_related(hierarchy_ids)
    return {"status": "deleted", **cleanup}

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
    member_email = normalize_email(body.email)
    if not member_email:
        raise HTTPException(400, "E-Mail erforderlich")
    if not is_valid_email(member_email):
        raise HTTPException(400, "Ungültige E-Mail")
    member = await db.users.find_one(
        {"email": exact_ci_regex(member_email, allow_outer_whitespace=True)},
        {"_id": 0, "password_hash": 0, "password": 0},
    )
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
    parent = await db.teams.find_one({"id": team_id}, {"_id": 0, "owner_id": 1, "member_ids": 1})
    if not parent:
        raise HTTPException(404, "Team nicht gefunden")
    can_view = user.get("role") == "admin" or parent.get("owner_id") == user["id"] or user["id"] in parent.get("member_ids", [])
    if not can_view:
        raise HTTPException(403, "Keine Berechtigung")
    subs = await db.teams.find({"parent_team_id": team_id}, {"_id": 0}).to_list(50)
    for s in subs:
        if user.get("role") != "admin" and s.get("owner_id") != user["id"]:
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
    tournament_ids = [t["id"] for t in tournaments]
    reg_counts = {}
    if tournament_ids:
        grouped = await db.registrations.aggregate([
            {"$match": {"tournament_id": {"$in": tournament_ids}}},
            {"$group": {"_id": "$tournament_id", "count": {"$sum": 1}}},
        ]).to_list(200)
        reg_counts = {g["_id"]: g["count"] for g in grouped}
    for t in tournaments:
        t["registered_count"] = reg_counts.get(t["id"], 0)
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
async def list_registrations(request: Request, tournament_id: str):
    user = await get_current_user(request)
    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(200)
    team_ids = list(dict.fromkeys(str(r.get("team_id", "")).strip() for r in regs if str(r.get("team_id", "")).strip()))
    teams = []
    if team_ids:
        teams = await db.teams.find(
            {"id": {"$in": team_ids}},
            {"_id": 0, "id": 1, "name": 1, "tag": 1, "logo_url": 1, "banner_url": 1, "parent_team_id": 1},
        ).to_list(500)
    team_map = {t["id"]: t for t in teams}
    parent_ids = list(dict.fromkeys(str(t.get("parent_team_id", "")).strip() for t in teams if str(t.get("parent_team_id", "")).strip()))
    parent_docs = []
    if parent_ids:
        parent_docs = await db.teams.find({"id": {"$in": parent_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    parent_map = {p["id"]: p.get("name", "") for p in parent_docs}

    for reg in regs:
        team_id = str(reg.get("team_id", "")).strip()
        team = team_map.get(team_id)
        if not team:
            continue
        reg["team_logo_url"] = team.get("logo_url", "")
        reg["team_banner_url"] = team.get("banner_url", "")
        reg["team_tag"] = team.get("tag", "")
        parent_id = str(team.get("parent_team_id", "")).strip()
        reg["main_team_name"] = parent_map.get(parent_id, "")

    is_admin = bool(user and user.get("role") == "admin")
    return [sanitize_registration(r, include_private=is_admin, include_player_emails=is_admin) for r in regs]

@api_router.post("/tournaments/{tournament_id}/register")
async def register_for_tournament(request: Request, tournament_id: str, body: RegistrationCreate):
    user = await require_auth(request)
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    if t["status"] not in ("registration", "checkin"):
        raise HTTPException(400, "Registration is closed")
    reg_count = await db.registrations.count_documents({"tournament_id": tournament_id})
    if reg_count >= t["max_participants"]:
        raise HTTPException(400, "Tournament is full")
    requested_team_name = body.team_name.strip()
    if not requested_team_name:
        raise HTTPException(400, "Team-Name ist erforderlich")
    team_name = requested_team_name
    team_logo_url = ""
    team_banner_url = ""
    team_tag = ""
    main_team_name = ""

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

    team_id = body.team_id.strip() if isinstance(body.team_id, str) and body.team_id.strip() else None
    if not team_id:
        raise HTTPException(400, "Registrierung ist nur mit einem Sub-Team möglich")
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Team nicht gefunden")
    if not is_sub_team(team):
        raise HTTPException(400, "Nur Sub-Teams können für Turniere registriert werden")
    team_role = await get_user_team_role(user["id"], team_id)
    if team_role not in ("owner", "leader", "member"):
        raise HTTPException(403, "Du bist kein Mitglied dieses Teams")
    if await db.registrations.find_one({"tournament_id": tournament_id, "team_id": team_id}, {"_id": 0}):
        raise HTTPException(400, "Dieses Team ist bereits registriert")
    canonical_team_name = str(team.get("name", "")).strip()
    if canonical_team_name:
        team_name = canonical_team_name
    team_logo_url = str(team.get("logo_url", "") or "")
    team_banner_url = str(team.get("banner_url", "") or "")
    team_tag = str(team.get("tag", "") or "")
    parent_team_id = str(team.get("parent_team_id", "") or "").strip()
    if parent_team_id:
        parent = await db.teams.find_one({"id": parent_team_id}, {"_id": 0, "name": 1})
        main_team_name = str((parent or {}).get("name", "") or "")

    payment_status = "free" if t["entry_fee"] <= 0 else "pending"
    doc = {
        "id": str(uuid.uuid4()),
        "tournament_id": tournament_id,
        "team_name": team_name,
        "team_logo_url": team_logo_url,
        "team_banner_url": team_banner_url,
        "team_tag": team_tag,
        "main_team_name": main_team_name,
        "players": normalized_players,
        "team_id": team_id,
        "user_id": user["id"],
        "checked_in": False,
        "payment_status": payment_status,
        "payment_session_id": None,
        "seed": reg_count + 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.registrations.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/tournaments/{tournament_id}/standings")
async def get_tournament_standings(tournament_id: str):
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0, "id": 1, "bracket": 1, "bracket_type": 1, "updated_at": 1})
    if not tournament:
        raise HTTPException(404, "Tournament not found")
    bracket = tournament.get("bracket")
    if not bracket:
        raise HTTPException(400, "Bracket wurde noch nicht generiert")

    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(400)
    team_ids = list(dict.fromkeys(str(r.get("team_id", "")).strip() for r in regs if str(r.get("team_id", "")).strip()))
    teams = []
    if team_ids:
        teams = await db.teams.find({"id": {"$in": team_ids}}, {"_id": 0, "id": 1, "tag": 1, "logo_url": 1}).to_list(800)
    team_map = {t.get("id"): t for t in teams}

    bracket_type = bracket.get("type", tournament.get("bracket_type", "single_elimination"))
    if bracket_type in ("round_robin", "league"):
        matches = [m for rd in bracket.get("rounds", []) for m in rd.get("matches", [])]
        standings = compute_standings_for_registrations(regs, matches, team_map)
        return {"type": bracket_type, "standings": standings, "updated_at": tournament.get("updated_at")}

    if bracket_type == "group_stage":
        reg_map = {str(r.get("id", "")).strip(): r for r in regs if str(r.get("id", "")).strip()}
        groups_payload = []
        for group in bracket.get("groups", []):
            matches = [m for rd in group.get("rounds", []) for m in rd.get("matches", [])]
            group_reg_ids = set()
            for match in matches:
                if match.get("team1_id"):
                    group_reg_ids.add(str(match.get("team1_id")))
                if match.get("team2_id"):
                    group_reg_ids.add(str(match.get("team2_id")))
            group_regs = [reg_map[rid] for rid in group_reg_ids if rid in reg_map]
            standings = compute_standings_for_registrations(group_regs, matches, team_map)
            groups_payload.append({"id": group.get("id"), "name": group.get("name", ""), "standings": standings})
        return {"type": bracket_type, "groups": groups_payload, "updated_at": tournament.get("updated_at")}

    raise HTTPException(400, "Für diesen Bracket-Typ ist keine Tabelle verfügbar")

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
                "team1_logo_url": "",
                "team1_tag": "",
                "team2_id": None,
                "team2_name": "TBD",
                "team2_logo_url": "",
                "team2_tag": "",
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
            match["team1_logo_url"] = str(p1.get("team_logo_url", "") or "")
            match["team1_tag"] = str(p1.get("team_tag", "") or "")
        else:
            match["team1_name"] = "BYE"
        if p2:
            match["team2_id"] = p2["id"]
            match["team2_name"] = p2["team_name"]
            match["team2_logo_url"] = str(p2.get("team_logo_url", "") or "")
            match["team2_tag"] = str(p2.get("team_tag", "") or "")
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
                winner_logo = match["team1_logo_url"] if match["winner_id"] == match["team1_id"] else match["team2_logo_url"]
                winner_tag = match["team1_tag"] if match["winner_id"] == match["team1_id"] else match["team2_tag"]
                next_match[f"{slot}_id"] = match["winner_id"]
                next_match[f"{slot}_name"] = winner_name
                next_match[f"{slot}_logo_url"] = winner_logo
                next_match[f"{slot}_tag"] = winner_tag

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
                "team1_logo_url": "",
                "team1_tag": "",
                "team2_id": None,
                "team2_name": "TBD",
                "team2_logo_url": "",
                "team2_tag": "",
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
        "team1_logo_url": "",
        "team1_tag": "",
        "team2_id": None,
        "team2_name": "Losers Bracket Champion",
        "team2_logo_url": "",
        "team2_tag": "",
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

def parse_optional_datetime(value: str) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

def generate_round_robin(registrations, start_date: str = "", bracket_type: str = "round_robin", interval_days: int = 7):
    participants = list(registrations)
    if len(participants) < 2:
        return {"type": bracket_type, "rounds": [], "total_rounds": 0}

    # Circle method (one matchday per round, every team plays at most once per matchday).
    if len(participants) % 2 == 1:
        participants.append(None)
    total_slots = len(participants)
    total_rounds = total_slots - 1
    matches_per_round = total_slots // 2
    base_start = parse_optional_datetime(start_date)
    rounds = []

    for round_idx in range(total_rounds):
        round_matches = []
        for pos in range(matches_per_round):
            p1 = participants[pos]
            p2 = participants[total_slots - 1 - pos]
            if p1 is None or p2 is None:
                continue

            # Alternate first pairing for better home/away balance.
            if pos == 0 and round_idx % 2 == 1:
                p1, p2 = p2, p1

            scheduled_for = ""
            if base_start:
                scheduled_for = (base_start + timedelta(days=interval_days * round_idx)).isoformat()

            round_matches.append(
                {
                    "id": str(uuid.uuid4()),
                    "round": round_idx + 1,
                    "matchday": round_idx + 1,
                    "position": pos,
                    "team1_id": p1["id"],
                    "team1_name": p1["team_name"],
                    "team1_logo_url": str(p1.get("team_logo_url", "") or ""),
                    "team1_tag": str(p1.get("team_tag", "") or ""),
                    "team2_id": p2["id"],
                    "team2_name": p2["team_name"],
                    "team2_logo_url": str(p2.get("team_logo_url", "") or ""),
                    "team2_tag": str(p2.get("team_tag", "") or ""),
                    "score1": 0,
                    "score2": 0,
                    "winner_id": None,
                    "status": "pending",
                    "scheduled_for": scheduled_for,
                }
            )

        rounds.append({"round": round_idx + 1, "name": f"Spieltag {round_idx + 1}", "matches": round_matches})

        fixed = participants[0]
        rotating = participants[1:]
        rotating = [rotating[-1]] + rotating[:-1]
        participants = [fixed] + rotating

    return {"type": bracket_type, "rounds": rounds, "total_rounds": len(rounds)}

def generate_group_stage(registrations, group_size: int = 4, start_date: str = ""):
    regs = list(registrations)
    if len(regs) < 2:
        return {"type": "group_stage", "groups": [], "group_size": max(2, int(group_size or 4)), "total_groups": 0}

    size = max(2, int(group_size or 4))
    groups = []
    for i in range(0, len(regs), size):
        groups.append(regs[i : i + size])

    group_docs = []
    for idx, group_regs in enumerate(groups):
        if len(group_regs) < 2:
            continue
        group_name = f"Gruppe {chr(65 + idx)}"
        rr = generate_round_robin(group_regs, start_date=start_date, bracket_type="round_robin")
        for rd in rr.get("rounds", []):
            for match in rd.get("matches", []):
                match["group_id"] = idx + 1
                match["group_name"] = group_name
        group_docs.append({"id": idx + 1, "name": group_name, "rounds": rr.get("rounds", []), "total_rounds": rr.get("total_rounds", 0)})

    return {"type": "group_stage", "groups": group_docs, "group_size": size, "total_groups": len(group_docs)}

def compute_standings_for_registrations(registrations: List[Dict], matches: List[Dict], team_map: Dict[str, Dict]) -> List[Dict]:
    standings = {}
    for reg in registrations:
        reg_id = str(reg.get("id", "")).strip()
        if not reg_id:
            continue
        team_id = str(reg.get("team_id", "")).strip()
        team_doc = team_map.get(team_id, {})
        standings[reg_id] = {
            "registration_id": reg_id,
            "team_id": team_id,
            "team_name": reg.get("team_name", ""),
            "team_tag": reg.get("team_tag", "") or team_doc.get("tag", ""),
            "team_logo_url": reg.get("team_logo_url", "") or team_doc.get("logo_url", ""),
            "main_team_name": reg.get("main_team_name", ""),
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "score_for": 0,
            "score_against": 0,
            "score_diff": 0,
            "points": 0,
        }

    for match in matches:
        if match.get("status") != "completed":
            continue
        team1_id = str(match.get("team1_id", "")).strip()
        team2_id = str(match.get("team2_id", "")).strip()
        if not team1_id or not team2_id:
            continue
        if team1_id not in standings or team2_id not in standings:
            continue
        score1 = int(match.get("score1", 0) or 0)
        score2 = int(match.get("score2", 0) or 0)
        st1 = standings[team1_id]
        st2 = standings[team2_id]

        st1["played"] += 1
        st2["played"] += 1
        st1["score_for"] += score1
        st1["score_against"] += score2
        st2["score_for"] += score2
        st2["score_against"] += score1

        if score1 > score2:
            st1["wins"] += 1
            st1["points"] += 3
            st2["losses"] += 1
        elif score2 > score1:
            st2["wins"] += 1
            st2["points"] += 3
            st1["losses"] += 1
        else:
            st1["draws"] += 1
            st2["draws"] += 1
            st1["points"] += 1
            st2["points"] += 1

    rows = list(standings.values())
    for row in rows:
        row["score_diff"] = row["score_for"] - row["score_against"]
    rows.sort(key=lambda r: (-r["points"], -r["score_diff"], -r["score_for"], str(r.get("team_name", "")).lower()))
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows

def find_match_in_bracket(bracket: Dict, match_id: str):
    if not bracket:
        return None
    bracket_type = bracket.get("type")
    all_rounds = []
    if bracket_type in ("single_elimination", "round_robin", "league"):
        all_rounds = bracket.get("rounds", [])
    elif bracket_type == "double_elimination":
        all_rounds = bracket.get("winners_bracket", {}).get("rounds", []) + bracket.get("losers_bracket", {}).get("rounds", [])
    elif bracket_type == "group_stage":
        for group in bracket.get("groups", []):
            all_rounds.extend(group.get("rounds", []))

    for rd in all_rounds:
        for m in rd.get("matches", []):
            if m.get("id") == match_id:
                return m

    if bracket_type == "double_elimination":
        gf = bracket.get("grand_final")
        if gf and gf.get("id") == match_id:
            return gf
    return None

async def find_tournament_and_match_by_match_id(match_id: str):
    tournaments = await db.tournaments.find({"bracket": {"$ne": None}}, {"_id": 0, "id": 1, "bracket": 1}).to_list(300)
    for t in tournaments:
        match = find_match_in_bracket(t.get("bracket"), match_id)
        if match:
            return t, match
    return None, None

async def can_user_manage_match(user: Dict, match_data: Dict) -> bool:
    if not user or not match_data:
        return False
    if user.get("role") == "admin":
        return True

    reg_ids = [rid for rid in [match_data.get("team1_id"), match_data.get("team2_id")] if rid]
    if not reg_ids:
        return False

    regs = await db.registrations.find({"id": {"$in": reg_ids}}, {"_id": 0}).to_list(2)
    for reg in regs:
        if reg.get("user_id") == user["id"]:
            return True
        team_id = reg.get("team_id")
        if team_id:
            role = await get_user_team_role(user["id"], team_id)
            if role in ("owner", "leader"):
                return True
    return False

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
        bracket = generate_round_robin(regs, start_date=t.get("start_date", ""), bracket_type="round_robin")
    elif bracket_type == "league":
        bracket = generate_round_robin(regs, start_date=t.get("start_date", ""), bracket_type="league")
    elif bracket_type == "group_stage":
        bracket = generate_group_stage(regs, group_size=int(t.get("group_size", 4) or 4), start_date=t.get("start_date", ""))
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
    bracket = t["bracket"]
    match_data = find_match_in_bracket(bracket, match_id)
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
                if admin.get("email"):
                    await send_email_notification(
                        admin["email"],
                        "ARENA: Ergebnis-Streitfall",
                        f"Es gibt einen Streitfall im Match {match_data.get('team1_name')} vs {match_data.get('team2_name')}."
                    )
            return {"status": "disputed", "message": "Ergebnisse stimmen nicht überein - Admin muss prüfen!"}

    return {"status": "submitted", "message": f"Ergebnis von {submitting_for} eingereicht. Warte auf die andere Seite."}

@api_router.get("/tournaments/{tournament_id}/matches/{match_id}/submissions")
async def get_score_submissions(request: Request, tournament_id: str, match_id: str):
    user = await require_auth(request)
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0, "bracket": 1})
    match = find_match_in_bracket((t or {}).get("bracket"), match_id)
    if user.get("role") != "admin" and not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")
    subs = await db.score_submissions.find({"tournament_id": tournament_id, "match_id": match_id}, {"_id": 0}).to_list(10)
    return subs

async def _apply_score_to_bracket(tournament_id: str, match_id: str, score1: int, score2: int, winner_id: str = None, disqualify_id: str = None):
    """Internal: apply finalized score to bracket and propagate."""
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    bracket = t["bracket"]
    bracket_type = bracket.get("type", "single_elimination")
    rounds = []
    if bracket_type in ("single_elimination", "round_robin", "league"):
        rounds = bracket.get("rounds", [])
    elif bracket_type == "double_elimination":
        rounds = bracket.get("winners_bracket", {}).get("rounds", []) + bracket.get("losers_bracket", {}).get("rounds", [])

    match_found = False
    match_round_idx = -1
    match_pos = -1

    def apply_to_match(match_doc: Dict):
        team1_id = match_doc.get("team1_id")
        team2_id = match_doc.get("team2_id")
        match_team_ids = {tid for tid in [team1_id, team2_id] if tid}
        if len(match_team_ids) < 2:
            raise HTTPException(400, "Match ist nicht vollständig belegt")

        match_doc["score1"] = score1
        match_doc["score2"] = score2
        if disqualify_id:
            if disqualify_id not in match_team_ids:
                raise HTTPException(400, "Ungültiges disqualify_team_id für dieses Match")
            match_doc["winner_id"] = team2_id if team1_id == disqualify_id else team1_id
            match_doc["disqualified"] = disqualify_id
        elif winner_id:
            if winner_id not in match_team_ids:
                raise HTTPException(400, "Ungültige winner_id für dieses Match")
            match_doc["winner_id"] = winner_id
        elif score1 > score2:
            match_doc["winner_id"] = team1_id
        elif score2 > score1:
            match_doc["winner_id"] = team2_id
        elif bracket_type in ("single_elimination", "double_elimination"):
            raise HTTPException(400, "Unentschieden ist im K.o.-Modus nicht erlaubt")
        else:
            match_doc["winner_id"] = None
        match_doc["status"] = "completed"

    if bracket_type == "group_stage":
        for group in bracket.get("groups", []):
            for rd in group.get("rounds", []):
                for m in rd.get("matches", []):
                    if m.get("id") == match_id:
                        apply_to_match(m)
                        match_found = True
                        break
                if match_found:
                    break
            if match_found:
                break
    else:
        for r_idx, rd in enumerate(rounds):
            for m_idx, m in enumerate(rd.get("matches", [])):
                if m.get("id") == match_id:
                    apply_to_match(m)
                    match_found = True
                    match_round_idx = r_idx
                    match_pos = m_idx
                    break
            if match_found:
                break

    if not match_found and bracket_type == "double_elimination":
        gf = bracket.get("grand_final")
        if gf and gf.get("id") == match_id:
            gf["score1"] = score1
            gf["score2"] = score2
            if winner_id:
                gf["winner_id"] = winner_id
            elif score1 > score2:
                gf["winner_id"] = gf.get("team1_id")
            elif score2 > score1:
                gf["winner_id"] = gf.get("team2_id")
            else:
                raise HTTPException(400, "Unentschieden ist im K.o.-Modus nicht erlaubt")
            gf["status"] = "completed"
            match_found = True

    if not match_found:
        raise HTTPException(404, "Match nicht gefunden")

    # Propagate winner (single elimination)
    if bracket_type == "single_elimination" and match_round_idx >= 0 and match_round_idx < len(rounds) - 1:
        cm = rounds[match_round_idx]["matches"][match_pos]
        if cm.get("winner_id"):
            nm = rounds[match_round_idx + 1]["matches"][match_pos // 2]
            slot = "team1" if match_pos % 2 == 0 else "team2"
            wn = cm["team1_name"] if cm["winner_id"] == cm.get("team1_id") else cm["team2_name"]
            wl = cm.get("team1_logo_url", "") if cm["winner_id"] == cm.get("team1_id") else cm.get("team2_logo_url", "")
            wt = cm.get("team1_tag", "") if cm["winner_id"] == cm.get("team1_id") else cm.get("team2_tag", "")
            nm[f"{slot}_id"] = cm["winner_id"]
            nm[f"{slot}_name"] = wn
            nm[f"{slot}_logo_url"] = wl
            nm[f"{slot}_tag"] = wt

    update_status = None
    if bracket_type == "single_elimination" and rounds:
        final = rounds[-1]["matches"][0]
        if final.get("winner_id"):
            update_status = "completed"
    elif bracket_type in ("round_robin", "league"):
        all_matches = [m for rd in rounds for m in rd.get("matches", []) if m.get("team1_id") and m.get("team2_id")]
        if all_matches and all(m.get("status") == "completed" for m in all_matches):
            update_status = "completed"
    elif bracket_type == "group_stage":
        all_matches = []
        for group in bracket.get("groups", []):
            for rd in group.get("rounds", []):
                all_matches.extend([m for m in rd.get("matches", []) if m.get("team1_id") and m.get("team2_id")])
        if all_matches and all(m.get("status") == "completed" for m in all_matches):
            update_status = "completed"

    update_doc = {"bracket": bracket, "updated_at": datetime.now(timezone.utc).isoformat()}
    if update_status:
        update_doc["status"] = update_status
    await db.tournaments.update_one({"id": tournament_id}, {"$set": update_doc})

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

@api_router.put("/users/me/account")
async def update_my_account(request: Request, body: UserAccountUpdate):
    user = await require_auth(request)
    existing_user = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not existing_user:
        raise HTTPException(404, "Benutzer nicht gefunden")

    updates = {}

    if body.username is not None:
        username = str(body.username).strip()
        if not username:
            raise HTTPException(400, "Benutzername darf nicht leer sein")
        username_exists = await db.users.find_one(
            {
                "id": {"$ne": user["id"]},
                "username": exact_ci_regex(username, allow_outer_whitespace=True),
            },
            {"_id": 0, "id": 1},
        )
        if username_exists:
            raise HTTPException(400, "Benutzername bereits vergeben")
        updates["username"] = username

    if body.email is not None:
        email = normalize_email(body.email)
        if not email:
            raise HTTPException(400, "E-Mail erforderlich")
        if not is_valid_email(email):
            raise HTTPException(400, "Ungültige E-Mail")
        email_exists = await db.users.find_one(
            {
                "id": {"$ne": user["id"]},
                "email": exact_ci_regex(email, allow_outer_whitespace=True),
            },
            {"_id": 0, "id": 1},
        )
        if email_exists:
            raise HTTPException(400, "E-Mail bereits registriert")
        updates["email"] = email

    if body.avatar_url is not None:
        updates["avatar_url"] = normalize_optional_url(body.avatar_url)
    if body.banner_url is not None:
        updates["banner_url"] = normalize_optional_url(body.banner_url)
    if body.bio is not None:
        updates["bio"] = normalize_optional_text(body.bio, max_len=1200)
    if body.discord_url is not None:
        updates["discord_url"] = normalize_optional_url(body.discord_url)
    if body.website_url is not None:
        updates["website_url"] = normalize_optional_url(body.website_url)
    if body.twitter_url is not None:
        updates["twitter_url"] = normalize_optional_url(body.twitter_url)
    if body.instagram_url is not None:
        updates["instagram_url"] = normalize_optional_url(body.instagram_url)
    if body.twitch_url is not None:
        updates["twitch_url"] = normalize_optional_url(body.twitch_url)
    if body.youtube_url is not None:
        updates["youtube_url"] = normalize_optional_url(body.youtube_url)

    if not updates:
        raise HTTPException(400, "Keine Änderungen übergeben")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": user["id"]}, {"$set": updates})

    # Keep team member snapshots in sync.
    member_updates = {}
    if "username" in updates:
        member_updates["members.$[member].username"] = updates["username"]
        await db.teams.update_many({"owner_id": user["id"]}, {"$set": {"owner_name": updates["username"]}})
    if "email" in updates:
        member_updates["members.$[member].email"] = updates["email"]
    if member_updates:
        await db.teams.update_many(
            {"members.id": user["id"]},
            {"$set": member_updates},
            array_filters=[{"member.id": user["id"]}],
        )

    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0, "password": 0})
    if not updated:
        raise HTTPException(404, "Benutzer nicht gefunden")
    return updated

@api_router.put("/users/me/password")
async def update_my_password(request: Request, body: UserPasswordUpdate):
    user = await require_auth(request)
    current_password = str(body.current_password or "")
    new_password = str(body.new_password or "")

    if not current_password or not new_password:
        raise HTTPException(400, "Aktuelles und neues Passwort sind erforderlich")
    if len(new_password) < 6:
        raise HTTPException(400, "Neues Passwort muss mindestens 6 Zeichen haben")

    user_doc = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(404, "Benutzer nicht gefunden")

    password_hash = str(user_doc.get("password_hash", "") or "")
    legacy_password = str(user_doc.get("password", "") or "")

    is_authenticated = verify_password(current_password, password_hash)
    if not is_authenticated and password_hash and password_hash == current_password:
        is_authenticated = True
    if not is_authenticated and not password_hash and legacy_password:
        is_authenticated = legacy_password == current_password
    if not is_authenticated:
        raise HTTPException(401, "Aktuelles Passwort ist falsch")

    old_password_matches_new = verify_password(new_password, password_hash) if password_hash else False
    if old_password_matches_new or (password_hash and password_hash == new_password) or (legacy_password and legacy_password == new_password):
        raise HTTPException(400, "Neues Passwort muss sich vom aktuellen unterscheiden")

    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {
                "password_hash": hash_password(new_password),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$unset": {"password": ""},
        },
    )
    return {"message": "Passwort geändert"}

@api_router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password": 0})
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    teams = await db.teams.find({"member_ids": user_id, "parent_team_id": {"$in": [None, ""]}}, {"_id": 0, "join_code": 0}).to_list(50)
    regs = await db.registrations.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    tournament_ids = list(dict.fromkeys(r["tournament_id"] for r in regs if r.get("tournament_id")))
    tournament_docs = []
    if tournament_ids:
        tournament_docs = await db.tournaments.find({"id": {"$in": tournament_ids}}, {"_id": 0}).to_list(300)
    tournament_map = {t["id"]: t for t in tournament_docs}
    tournaments = [{k: v for k, v in tournament_map[tid].items() if k != "bracket"} for tid in tournament_ids[:20] if tid in tournament_map]
    wins = 0
    draws = 0
    losses = 0
    for reg in regs:
        t = tournament_map.get(reg.get("tournament_id"))
        if t and t.get("bracket"):
            all_matches = []
            b = t["bracket"]
            if b["type"] in ("single_elimination", "round_robin", "league"):
                for rd in b.get("rounds", []):
                    all_matches.extend(rd["matches"])
            elif b["type"] == "double_elimination":
                for rd in b.get("winners_bracket", {}).get("rounds", []):
                    all_matches.extend(rd["matches"])
            elif b["type"] == "group_stage":
                for group in b.get("groups", []):
                    for rd in group.get("rounds", []):
                        all_matches.extend(rd.get("matches", []))
            for m in all_matches:
                if m.get("status") == "completed":
                    if m.get("team1_id") == reg["id"] or m.get("team2_id") == reg["id"]:
                        winner = m.get("winner_id")
                        if winner == reg["id"]:
                            wins += 1
                        elif winner in (m.get("team1_id"), m.get("team2_id")):
                            losses += 1
                        else:
                            draws += 1
    return {
        **user,
        "teams": teams,
        "tournaments": tournaments,
        "stats": {"tournaments_played": len(regs), "wins": wins, "draws": draws, "losses": losses},
    }

# ─── Widget Endpoint ───

@api_router.get("/widget/tournament/{tournament_id}")
async def get_widget_data(tournament_id: str):
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(200)
    return {"tournament": t, "registrations": [sanitize_registration(r) for r in regs], "embed_version": "1.0"}

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
async def get_match_schedule(request: Request, match_id: str):
    user = await require_auth(request)
    tournament, match = await find_tournament_and_match_by_match_id(match_id)
    if not tournament or not match:
        raise HTTPException(404, "Match nicht gefunden")
    if not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")

    q = {
        "match_id": match_id,
        "$or": [{"tournament_id": tournament["id"]}, {"tournament_id": {"$exists": False}}],
    }
    proposals = await db.schedule_proposals.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
    return proposals

@api_router.post("/matches/{match_id}/schedule")
async def propose_match_time(request: Request, match_id: str, body: TimeProposal):
    user = await require_auth(request)
    tournament, match = await find_tournament_and_match_by_match_id(match_id)
    if not tournament or not match:
        raise HTTPException(404, "Match nicht gefunden")
    if not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")

    doc = {
        "id": str(uuid.uuid4()),
        "tournament_id": tournament["id"],
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
    tournament, match = await find_tournament_and_match_by_match_id(match_id)
    if not tournament or not match:
        raise HTTPException(404, "Match nicht gefunden")
    if not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")

    proposal_query = {
        "id": proposal_id,
        "match_id": match_id,
        "$or": [{"tournament_id": tournament["id"]}, {"tournament_id": {"$exists": False}}],
    }
    proposal = await db.schedule_proposals.find_one(proposal_query, {"_id": 0})
    if not proposal:
        raise HTTPException(404, "Zeitvorschlag nicht gefunden")

    match_query = {
        "match_id": match_id,
        "$or": [{"tournament_id": tournament["id"]}, {"tournament_id": {"$exists": False}}],
    }
    await db.schedule_proposals.update_many(match_query, {"$set": {"status": "rejected"}})
    await db.schedule_proposals.update_one(proposal_query, {"$set": {"status": "accepted", "accepted_by": user["id"], "accepted_at": datetime.now(timezone.utc).isoformat(), "tournament_id": tournament["id"]}})
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
    users = await db.users.find({}, {"_id": 0, "password_hash": 0, "password": 0}).sort("created_at", -1).to_list(500)
    user_ids = [str(u.get("id", "")).strip() for u in users if str(u.get("id", "")).strip()]
    if not user_ids:
        return users

    user_id_set = set(user_ids)
    teams = await db.teams.find(
        {"member_ids": {"$in": user_ids}},
        {"_id": 0, "id": 1, "name": 1, "tag": 1, "owner_id": 1, "parent_team_id": 1, "member_ids": 1},
    ).to_list(3000)
    teams_by_user = {uid: [] for uid in user_ids}
    for team in teams:
        summary = {
            "id": team.get("id"),
            "name": team.get("name", ""),
            "tag": team.get("tag", ""),
            "owner_id": team.get("owner_id"),
            "parent_team_id": team.get("parent_team_id"),
            "is_sub_team": is_sub_team(team),
        }
        for member_id in team.get("member_ids", []):
            if member_id in user_id_set:
                teams_by_user[member_id].append(summary)

    regs = await db.registrations.find(
        {"user_id": {"$in": user_ids}},
        {"_id": 0, "user_id": 1, "tournament_id": 1, "team_id": 1, "team_name": 1, "created_at": 1},
    ).to_list(6000)
    tournament_ids = list(dict.fromkeys(str(r.get("tournament_id", "")).strip() for r in regs if str(r.get("tournament_id", "")).strip()))
    tournament_docs = []
    if tournament_ids:
        tournament_docs = await db.tournaments.find(
            {"id": {"$in": tournament_ids}},
            {"_id": 0, "id": 1, "name": 1, "status": 1},
        ).to_list(1200)
    tournament_map = {t["id"]: t for t in tournament_docs}
    tournaments_by_user = {uid: [] for uid in user_ids}
    seen_user_tournaments = {uid: set() for uid in user_ids}
    for reg in regs:
        uid = reg.get("user_id")
        tid = str(reg.get("tournament_id", "")).strip()
        if uid not in tournaments_by_user or not tid or tid in seen_user_tournaments[uid]:
            continue
        seen_user_tournaments[uid].add(tid)
        t_doc = tournament_map.get(tid, {})
        tournaments_by_user[uid].append(
            {
                "id": tid,
                "name": t_doc.get("name", ""),
                "status": t_doc.get("status", ""),
                "team_id": reg.get("team_id"),
                "team_name": reg.get("team_name", ""),
                "registered_at": reg.get("created_at"),
            }
        )

    for user in users:
        uid = str(user.get("id", "")).strip()
        team_list = teams_by_user.get(uid, [])
        tournament_list = tournaments_by_user.get(uid, [])
        user["teams"] = team_list[:50]
        user["team_count"] = len(team_list)
        user["tournaments"] = tournament_list[:50]
        user["tournament_count"] = len(tournament_list)
    return users

@api_router.put("/admin/users/{user_id}/role")
async def admin_set_user_role(request: Request, user_id: str, body: AdminUserRoleUpdate):
    admin_user = await require_admin(request)
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Benutzer nicht gefunden")

    new_role = str(body.role or "").strip().lower()
    if new_role not in {"user", "admin"}:
        raise HTTPException(400, "Ungültige Rolle")

    current_role = str(target.get("role", "user")).strip().lower()
    if current_role == new_role:
        return {"status": "ok", "user_id": user_id, "role": new_role}

    if target.get("id") == admin_user.get("id") and new_role != "admin":
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(400, "Der letzte Admin kann nicht degradiert werden")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": new_role, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"status": "ok", "user_id": user_id, "role": new_role}

@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(request: Request, user_id: str):
    admin_user = await require_admin(request)
    target = await db.users.find_one({"id": user_id}, {"_id": 0, "id": 1, "role": 1})
    if not target:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if target.get("id") == admin_user.get("id"):
        raise HTTPException(400, "Du kannst deinen eigenen Admin-Account nicht löschen")
    if target.get("role") == "admin":
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(400, "Der letzte Admin kann nicht gelöscht werden")

    cleanup = await delete_user_and_related_data(user_id)
    return {"status": "deleted", **cleanup}

@api_router.get("/admin/teams")
async def admin_list_teams(request: Request):
    await require_admin(request)
    teams = await db.teams.find({}, {"_id": 0}).sort("created_at", -1).to_list(3000)
    team_ids = [str(t.get("id", "")).strip() for t in teams if str(t.get("id", "")).strip()]
    reg_counts = {}
    if team_ids:
        grouped = await db.registrations.aggregate(
            [
                {"$match": {"team_id": {"$in": team_ids}}},
                {"$group": {"_id": "$team_id", "count": {"$sum": 1}}},
            ]
        ).to_list(4000)
        reg_counts = {g["_id"]: int(g.get("count", 0)) for g in grouped}

    team_map = {t.get("id"): t for t in teams}
    for team in teams:
        team.pop("join_code", None)
        parent_id = str(team.get("parent_team_id") or "").strip()
        team["is_sub_team"] = bool(parent_id)
        team["parent_team_name"] = (team_map.get(parent_id) or {}).get("name", "")
        team["member_count"] = len(team.get("member_ids", []))
        team["registration_count"] = reg_counts.get(team.get("id"), 0)
    return teams

@api_router.delete("/admin/teams/{team_id}")
async def admin_delete_team(request: Request, team_id: str):
    await require_admin(request)
    existing = await db.teams.find_one({"id": team_id}, {"_id": 0, "id": 1})
    if not existing:
        raise HTTPException(404, "Team nicht gefunden")
    hierarchy_ids = await collect_team_hierarchy_ids(team_id)
    cleanup = await delete_teams_and_related(hierarchy_ids)
    return {"status": "deleted", **cleanup}

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

cors_origins_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
if not cors_origins:
    cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
cors_allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_credentials=cors_allow_credentials,
    allow_origins=cors_origins,
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
