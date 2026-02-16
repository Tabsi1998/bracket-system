from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import logging
import math
import re
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Tuple, Set
import uuid
import secrets
import string
from datetime import datetime, timezone, timedelta
import bcrypt
from jose import jwt as jose_jwt, JWTError
import stripe

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
    modes: List[GameMode] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)

class TournamentCreate(BaseModel):
    name: str
    game_id: str
    game_name: str = ""
    game_mode: str = ""
    participant_mode: str = "team"  # "team" or "solo"
    team_size: int = 1
    max_participants: int = 8
    bracket_type: str = "single_elimination"
    require_admin_score_approval: bool = False
    best_of: int = 1
    entry_fee: float = 0.0
    currency: str = "usd"
    prize_pool: str = ""
    description: str = ""
    rules: str = ""
    start_date: str = ""
    checkin_start: str = ""
    group_size: int = 4
    advance_per_group: int = 2
    swiss_rounds: int = 5
    battle_royale_group_size: int = 4
    battle_royale_advance: int = 2
    default_match_time: str = ""

class TournamentUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    bracket_type: Optional[str] = None
    participant_mode: Optional[str] = None
    team_size: Optional[int] = None
    max_participants: Optional[int] = None
    require_admin_score_approval: Optional[bool] = None
    description: Optional[str] = None
    rules: Optional[str] = None
    start_date: Optional[str] = None
    checkin_start: Optional[str] = None
    group_size: Optional[int] = None
    advance_per_group: Optional[int] = None
    swiss_rounds: Optional[int] = None
    battle_royale_group_size: Optional[int] = None
    battle_royale_advance: Optional[int] = None

class RegistrationCreate(BaseModel):
    team_name: str = ""
    players: List[Dict[str, str]] = Field(default_factory=list)
    team_id: Optional[str] = None

class ScoreUpdate(BaseModel):
    score1: int = Field(ge=0)
    score2: int = Field(ge=0)
    winner_id: Optional[str] = None

class PaymentRequest(BaseModel):
    tournament_id: str
    registration_id: str
    origin_url: str
    provider: Optional[str] = None

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

class AdminEmailTest(BaseModel):
    email: str

class BattleRoyaleResultSubmission(BaseModel):
    placements: List[str]

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

SUPPORTED_BRACKET_TYPES = {
    "single_elimination",
    "double_elimination",
    "round_robin",
    "group_stage",
    "group_playoffs",
    "swiss_system",
    "ladder_system",
    "king_of_the_hill",
    "battle_royale",
    "league",
}

SUPPORTED_PARTICIPANT_MODES = {"team", "solo"}

TEAM_PROFILE_FIELDS = (
    "bio",
    "logo_url",
    "banner_url",
    "discord_url",
    "website_url",
    "twitter_url",
    "instagram_url",
    "twitch_url",
    "youtube_url",
)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def normalize_bracket_type(value: str) -> str:
    bracket_type = str(value or "").strip().lower()
    if bracket_type not in SUPPORTED_BRACKET_TYPES:
        raise HTTPException(400, f"Ungültiger Bracket-Typ: {value}")
    return bracket_type

def normalize_participant_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode not in SUPPORTED_PARTICIPANT_MODES:
        raise HTTPException(400, "participant_mode muss 'team' oder 'solo' sein")
    return mode

def default_admin_approval_for_bracket(bracket_type: str) -> bool:
    return bracket_type == "battle_royale"

def registration_slot(reg: Dict) -> Dict[str, str]:
    return {
        "id": str(reg.get("id", "")).strip(),
        "team_name": str(reg.get("team_name", "")).strip(),
        "team_logo_url": str(reg.get("team_logo_url", "") or ""),
        "team_tag": str(reg.get("team_tag", "") or ""),
    }

def merge_team_with_parent(team: Dict, parent: Optional[Dict]) -> Dict:
    if not team:
        return {}
    merged = dict(team)
    inherited_fields = []
    if parent:
        merged["main_team_name"] = str(parent.get("name", "") or "")
        for field in TEAM_PROFILE_FIELDS:
            if not str(merged.get(field, "") or "").strip():
                parent_value = str(parent.get(field, "") or "").strip()
                if parent_value:
                    merged[field] = parent_value
                    inherited_fields.append(field)
        if not str(merged.get("tag", "") or "").strip():
            parent_tag = str(parent.get("tag", "") or "").strip()
            if parent_tag:
                merged["tag"] = parent_tag
                inherited_fields.append("tag")
    merged["inherited_fields"] = inherited_fields
    merged["inherits_from_parent"] = bool(inherited_fields)
    return merged

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
        from email.utils import formataddr

        smtp_config = await get_smtp_config()
        if not smtp_config:
            logger.info("SMTP config incomplete, skipping email notification")
            return False

        to_email = normalize_email(to_email)
        if not is_valid_email(to_email):
            logger.warning(f"Invalid recipient email: {to_email}")
            return False

        msg = MIMEText(body_text, "plain", "utf-8")
        msg["Subject"] = str(subject or "").strip() or "ARENA Benachrichtigung"
        msg["From"] = formataddr((smtp_config["from_name"], smtp_config["from_email"]))
        msg["To"] = to_email
        if smtp_config["reply_to"]:
            msg["Reply-To"] = smtp_config["reply_to"]

        if smtp_config["use_ssl"]:
            with smtplib.SMTP_SSL(smtp_config["host"], smtp_config["port"], timeout=12) as server:
                if smtp_config["user"]:
                    server.login(smtp_config["user"], smtp_config["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=12) as server:
                if smtp_config["use_starttls"]:
                    server.starttls()
                if smtp_config["user"]:
                    server.login(smtp_config["user"], smtp_config["password"])
                server.send_message(msg)
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.warning(f"Email send failed: {e}")
        return False

def to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default

async def get_admin_setting_value(key: str, default: str = "") -> str:
    row = await db.admin_settings.find_one({"key": key}, {"_id": 0, "value": 1})
    value = str((row or {}).get("value", "")).strip()
    return value if value else default

async def get_smtp_config() -> Optional[Dict[str, Any]]:
    host = await get_admin_setting_value("smtp_host")
    port_raw = await get_admin_setting_value("smtp_port", "587")
    user = await get_admin_setting_value("smtp_user")
    password = await get_admin_setting_value("smtp_password")

    # Optional sender overrides
    from_name = await get_admin_setting_value("smtp_from_name", "ARENA eSports")
    from_email = await get_admin_setting_value("smtp_from_email", user)
    reply_to = await get_admin_setting_value("smtp_reply_to", "")
    use_starttls = to_bool(await get_admin_setting_value("smtp_use_starttls", "true"), default=True)
    use_ssl = to_bool(await get_admin_setting_value("smtp_use_ssl", "false"), default=False)

    if not host or not port_raw:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        logger.warning("SMTP port invalid")
        return None

    if user and not password:
        logger.warning("SMTP user set but password missing")
        return None
    if from_email and not is_valid_email(from_email):
        logger.warning("SMTP from_email invalid")
        return None
    if reply_to and not is_valid_email(reply_to):
        logger.warning("SMTP reply_to invalid")
        reply_to = ""

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_name": from_name,
        "from_email": from_email or user,
        "reply_to": reply_to,
        "use_starttls": use_starttls and not use_ssl,
        "use_ssl": use_ssl,
    }

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

async def get_stripe_webhook_secret() -> Optional[str]:
    env_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if env_secret:
        return env_secret
    setting = await db.admin_settings.find_one({"key": "stripe_webhook_secret"}, {"_id": 0})
    value = str((setting or {}).get("value", "")).strip()
    return value or None

def normalize_payment_provider(value: str) -> str:
    provider = str(value or "").strip().lower()
    if provider in {"", "auto"}:
        return "auto"
    if provider in {"stripe", "paypal"}:
        return provider
    raise HTTPException(400, "Ungültiger Payment-Provider")

async def get_payment_provider(requested_provider: Optional[str] = None) -> str:
    provider = normalize_payment_provider(requested_provider or "")
    if provider in {"stripe", "paypal"}:
        return provider
    setting = await db.admin_settings.find_one({"key": "payment_provider"}, {"_id": 0, "value": 1})
    setting_provider_raw = str((setting or {}).get("value", ""))
    try:
        setting_provider = normalize_payment_provider(setting_provider_raw)
    except HTTPException:
        logger.warning(f"Ignoring invalid payment_provider setting: {setting_provider_raw}")
        setting_provider = "auto"
    if setting_provider in {"stripe", "paypal"}:
        return setting_provider
    paypal_client_id = await get_paypal_client_id()
    paypal_secret = await get_paypal_secret()
    if paypal_client_id and paypal_secret:
        return "paypal"
    return "stripe"

async def get_paypal_client_id() -> Optional[str]:
    env_value = str(os.environ.get("PAYPAL_CLIENT_ID", "") or "").strip()
    if env_value:
        return env_value
    setting = await db.admin_settings.find_one({"key": "paypal_client_id"}, {"_id": 0, "value": 1})
    value = str((setting or {}).get("value", "") or "").strip()
    return value or None

async def get_paypal_secret() -> Optional[str]:
    env_value = str(os.environ.get("PAYPAL_SECRET", "") or "").strip()
    if env_value:
        return env_value
    setting = await db.admin_settings.find_one({"key": "paypal_secret"}, {"_id": 0, "value": 1})
    value = str((setting or {}).get("value", "") or "").strip()
    return value or None

async def get_paypal_base_url() -> str:
    env_mode = str(os.environ.get("PAYPAL_MODE", "") or "").strip().lower()
    if env_mode == "live":
        return "https://api-m.paypal.com"
    if env_mode == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    setting = await db.admin_settings.find_one({"key": "paypal_mode"}, {"_id": 0, "value": 1})
    mode = str((setting or {}).get("value", "") or "").strip().lower()
    if mode == "live":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"

async def paypal_api_request(
    method: str,
    path: str,
    payload: Optional[Dict] = None,
    bearer_token: Optional[str] = None,
    basic_auth: Optional[str] = None,
    raw_body: Optional[bytes] = None,
    content_type: str = "application/json",
) -> Dict:
    base_url = await get_paypal_base_url()
    url = f"{base_url}{path}"
    data = None
    headers = {"Content-Type": content_type, "Accept": "application/json"}
    if raw_body is not None:
        data = raw_body
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    if basic_auth:
        headers["Authorization"] = f"Basic {basic_auth}"

    request_obj = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())

    def _do_request():
        with urllib.request.urlopen(request_obj, timeout=20) as response:
            body = response.read().decode("utf-8") if response else "{}"
            return json.loads(body or "{}")

    try:
        return await asyncio.to_thread(_do_request)
    except urllib.error.HTTPError as http_error:
        body = http_error.read().decode("utf-8", errors="ignore") if http_error else ""
        logger.warning(f"PayPal API error {http_error.code}: {body}")
        detail = "PayPal API Fehler"
        try:
            parsed = json.loads(body or "{}")
            detail = str((parsed.get("message") or detail)).strip() or detail
        except Exception:
            pass
        raise HTTPException(400, detail)
    except Exception as e:
        logger.warning(f"PayPal request failed: {e}")
        raise HTTPException(400, "PayPal Verbindung fehlgeschlagen")

async def get_paypal_access_token() -> str:
    client_id = await get_paypal_client_id()
    secret = await get_paypal_secret()
    if not client_id or not secret:
        raise HTTPException(500, "PayPal ist nicht konfiguriert")
    auth_raw = f"{client_id}:{secret}".encode("utf-8")
    basic_auth = base64.b64encode(auth_raw).decode("ascii")
    token_response = await paypal_api_request(
        "POST",
        "/v1/oauth2/token",
        raw_body=b"grant_type=client_credentials",
        content_type="application/x-www-form-urlencoded",
        basic_auth=basic_auth,
    )
    access_token = str((token_response or {}).get("access_token", "")).strip()
    if not access_token:
        raise HTTPException(500, "PayPal Token konnte nicht erzeugt werden")
    return access_token

async def create_paypal_order(amount: float, currency: str, tournament_name: str, return_url: str, cancel_url: str) -> Dict:
    token = await get_paypal_access_token()
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "description": f"Turniergebühr: {tournament_name}",
                "amount": {
                    "currency_code": str(currency or "EUR").upper(),
                    "value": f"{float(amount):.2f}",
                },
            }
        ],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW",
        },
    }
    return await paypal_api_request("POST", "/v2/checkout/orders", payload=payload, bearer_token=token)

async def get_paypal_order(order_id: str) -> Dict:
    token = await get_paypal_access_token()
    return await paypal_api_request("GET", f"/v2/checkout/orders/{order_id}", payload=None, bearer_token=token)

async def capture_paypal_order(order_id: str) -> Dict:
    token = await get_paypal_access_token()
    return await paypal_api_request("POST", f"/v2/checkout/orders/{order_id}/capture", payload={}, bearer_token=token)

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
    force_password_reset = to_bool(os.environ.get("ADMIN_FORCE_PASSWORD_RESET", "false"), default=False)

    existing_with_email = await db.users.find_one(
        {"email": exact_ci_regex(admin_email, allow_outer_whitespace=True)},
    )
    if existing_with_email:
        update_doc = {
            "role": "admin",
            "email": admin_email,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        existing_hash = str(existing_with_email.get("password_hash", "") or "").strip()
        legacy_password = str(existing_with_email.get("password", "") or "").strip()
        if force_password_reset:
            update_doc["password_hash"] = hash_password(admin_password)
        elif not existing_hash:
            if legacy_password:
                update_doc["password_hash"] = hash_password(legacy_password)
            else:
                update_doc["password_hash"] = hash_password(admin_password)
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
        if force_password_reset:
            logger.info(f"Promoted existing user to admin and force-reset password via ADMIN_FORCE_PASSWORD_RESET: {admin_email}")
        else:
            logger.info(f"Promoted/ensured existing admin user: {admin_email}")
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
    result = []
    for t in teams:
        t = merge_team_with_parent(t, None)
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
        parent_docs = await db.teams.find(
            {"id": {"$in": parent_ids}},
            {"_id": 0, "id": 1, "name": 1, "tag": 1, "logo_url": 1, "banner_url": 1, "discord_url": 1, "website_url": 1, "twitter_url": 1, "instagram_url": 1, "twitch_url": 1, "youtube_url": 1, "bio": 1},
        ).to_list(300)
    parent_map = {p["id"]: p.get("name", "") for p in parent_docs}
    parent_doc_map = {p["id"]: p for p in parent_docs}

    result = []
    for t in sub_teams:
        parent_id = str(t.get("parent_team_id", "")).strip()
        t = merge_team_with_parent(t, parent_doc_map.get(parent_id))
        if t.get("owner_id") != user["id"]:
            t.pop("join_code", None)
        t["parent_team_name"] = parent_map.get(parent_id, "")
        t["is_sub_team"] = True
        result.append(t)
    result.sort(key=lambda item: (str(item.get("parent_team_name", "")).lower(), str(item.get("name", "")).lower()))
    return result

@api_router.get("/teams/public")
async def list_public_teams(q: Optional[str] = None):
    term = normalize_optional_text(q, max_len=80) if q else ""
    query = {"parent_team_id": {"$in": [None, ""]}}
    if term:
        query["$or"] = [
            {"name": {"$regex": re.escape(term), "$options": "i"}},
            {"tag": {"$regex": re.escape(term), "$options": "i"}},
            {"bio": {"$regex": re.escape(term), "$options": "i"}},
        ]

    team_projection = {
        "_id": 0,
        "id": 1,
        "name": 1,
        "tag": 1,
        "bio": 1,
        "logo_url": 1,
        "banner_url": 1,
        "discord_url": 1,
        "website_url": 1,
        "twitter_url": 1,
        "instagram_url": 1,
        "twitch_url": 1,
        "youtube_url": 1,
        "parent_team_id": 1,
        "member_ids": 1,
        "created_at": 1,
    }
    main_teams = await db.teams.find(query, team_projection).sort("created_at", -1).to_list(500)
    main_team_map = {str(t.get("id", "")).strip(): t for t in main_teams if str(t.get("id", "")).strip()}

    # If a sub-team matches the search term, include its parent main team as well.
    if term:
        sub_parent_rows = await db.teams.find(
            {
                "parent_team_id": {"$nin": [None, ""]},
                "$or": [
                    {"name": {"$regex": re.escape(term), "$options": "i"}},
                    {"tag": {"$regex": re.escape(term), "$options": "i"}},
                    {"bio": {"$regex": re.escape(term), "$options": "i"}},
                ],
            },
            {"_id": 0, "parent_team_id": 1},
        ).to_list(2000)
        missing_parent_ids = [
            parent_id
            for parent_id in {
                str(row.get("parent_team_id", "")).strip()
                for row in sub_parent_rows
                if str(row.get("parent_team_id", "")).strip()
            }
            if parent_id not in main_team_map
        ]
        if missing_parent_ids:
            extra_main_teams = await db.teams.find({"id": {"$in": missing_parent_ids}}, team_projection).to_list(500)
            for extra in extra_main_teams:
                extra_id = str(extra.get("id", "")).strip()
                if extra_id:
                    main_team_map[extra_id] = extra

    main_teams = list(main_team_map.values())
    main_teams.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    main_team_ids = [str(t.get("id", "")).strip() for t in main_teams if str(t.get("id", "")).strip()]

    subs = []
    if main_team_ids:
        subs = await db.teams.find(
            {"parent_team_id": {"$in": main_team_ids}},
            team_projection,
        ).sort("created_at", -1).to_list(2000)

    sub_map: Dict[str, List[Dict]] = {}
    for sub in subs:
        parent_id = str(sub.get("parent_team_id", "")).strip()
        if not parent_id:
            continue
        sub_map.setdefault(parent_id, []).append(sub)

    payload = []
    for team in main_teams:
        team_id = str(team.get("id", "")).strip()
        merged_main = merge_team_with_parent(team, None)
        merged_main["is_sub_team"] = False
        merged_main["member_count"] = len(merged_main.pop("member_ids", []) or [])
        for private_field in ("members", "leader_ids", "owner_id", "owner_name", "join_code"):
            merged_main.pop(private_field, None)

        children = []
        for sub in sub_map.get(team_id, []):
            merged_sub = merge_team_with_parent(sub, team)
            merged_sub["is_sub_team"] = True
            merged_sub["parent_team_name"] = team.get("name", "")
            merged_sub["member_count"] = len(merged_sub.pop("member_ids", []) or [])
            for private_field in ("members", "leader_ids", "owner_id", "owner_name", "join_code"):
                merged_sub.pop(private_field, None)
            children.append(merged_sub)
        children.sort(key=lambda item: str(item.get("name", "")).lower())

        merged_main["sub_teams"] = children
        merged_main["sub_team_count"] = len(children)
        payload.append(merged_main)

    return payload

@api_router.post("/teams")
async def create_team(request: Request, body: TeamCreate):
    user = await require_auth(request)
    name = normalize_optional_text(body.name, max_len=80)
    if not name:
        raise HTTPException(400, "Team-Name ist erforderlich")
    tag = normalize_optional_text(body.tag, max_len=20)

    parent_team_id = str(body.parent_team_id or "").strip() or None
    parent_profile = None
    if parent_team_id:
        parent = await db.teams.find_one(
            {"id": parent_team_id},
            {"_id": 0, "id": 1, "owner_id": 1, "parent_team_id": 1, "bio": 1, "logo_url": 1, "banner_url": 1, "discord_url": 1, "website_url": 1, "twitter_url": 1, "instagram_url": 1, "twitch_url": 1, "youtube_url": 1},
        )
        if not parent:
            raise HTTPException(404, "Hauptteam nicht gefunden")
        if is_sub_team(parent):
            raise HTTPException(400, "Sub-Teams können nicht unter weiteren Sub-Teams erstellt werden")
        if parent.get("owner_id") != user["id"] and user.get("role") != "admin":
            raise HTTPException(403, "Nur der Owner des Hauptteams kann Sub-Teams erstellen")
        parent_profile = parent

    doc = {
        "id": str(uuid.uuid4()), "name": name, "tag": tag,
        "owner_id": user["id"], "owner_name": user["username"],
        "join_code": generate_join_code(),
        "member_ids": [user["id"]],
        "leader_ids": [user["id"]],
        "members": [{"id": user["id"], "username": user["username"], "email": user["email"], "role": "owner"}],
        "parent_team_id": parent_team_id,
        "bio": str((parent_profile or {}).get("bio", "") or ""),
        "logo_url": str((parent_profile or {}).get("logo_url", "") or ""),
        "banner_url": str((parent_profile or {}).get("banner_url", "") or ""),
        "discord_url": str((parent_profile or {}).get("discord_url", "") or ""),
        "website_url": str((parent_profile or {}).get("website_url", "") or ""),
        "twitter_url": str((parent_profile or {}).get("twitter_url", "") or ""),
        "instagram_url": str((parent_profile or {}).get("instagram_url", "") or ""),
        "twitch_url": str((parent_profile or {}).get("twitch_url", "") or ""),
        "youtube_url": str((parent_profile or {}).get("youtube_url", "") or ""),
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
    parent_doc = None
    parent_id = str(team.get("parent_team_id", "") or "").strip()
    if parent_id:
        parent_doc = await db.teams.find_one({"id": parent_id}, {"_id": 0, "join_code": 0})
    team = merge_team_with_parent(team, parent_doc)
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

    # Main-team branding fallback for sub-teams: only fill empty child fields.
    if not is_sub_team(team):
        child_teams = await db.teams.find({"parent_team_id": team_id}, {"_id": 0, "id": 1, "logo_url": 1, "banner_url": 1, "tag": 1}).to_list(500)
        for child in child_teams:
            child_updates = {}
            if "logo_url" in updates and not str(child.get("logo_url", "") or "").strip():
                child_updates["logo_url"] = updates["logo_url"]
            if "banner_url" in updates and not str(child.get("banner_url", "") or "").strip():
                child_updates["banner_url"] = updates["banner_url"]
            if "tag" in updates and not str(child.get("tag", "") or "").strip():
                child_updates["tag"] = updates["tag"]

            if child_updates:
                child_updates["updated_at"] = datetime.now(timezone.utc).isoformat()
                await db.teams.update_one({"id": child["id"]}, {"$set": child_updates})

                reg_child_updates = {}
                if "logo_url" in child_updates:
                    reg_child_updates["team_logo_url"] = child_updates["logo_url"]
                if "banner_url" in child_updates:
                    reg_child_updates["team_banner_url"] = child_updates["banner_url"]
                if "tag" in child_updates:
                    reg_child_updates["team_tag"] = child_updates["tag"]
                if reg_child_updates:
                    await db.registrations.update_many({"team_id": child["id"]}, {"$set": reg_child_updates})

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
    parent = await db.teams.find_one(
        {"id": team_id},
        {"_id": 0, "id": 1, "name": 1, "owner_id": 1, "member_ids": 1, "tag": 1, "bio": 1, "logo_url": 1, "banner_url": 1, "discord_url": 1, "website_url": 1, "twitter_url": 1, "instagram_url": 1, "twitch_url": 1, "youtube_url": 1},
    )
    if not parent:
        raise HTTPException(404, "Team nicht gefunden")
    can_view = user.get("role") == "admin" or parent.get("owner_id") == user["id"] or user["id"] in parent.get("member_ids", [])
    if not can_view:
        raise HTTPException(403, "Keine Berechtigung")
    subs = await db.teams.find({"parent_team_id": team_id}, {"_id": 0}).to_list(50)
    merged_subs = []
    for s in subs:
        s = merge_team_with_parent(s, parent)
        if user.get("role") != "admin" and s.get("owner_id") != user["id"]:
            s.pop("join_code", None)
        merged_subs.append(s)
    return merged_subs

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

    bracket_type = normalize_bracket_type(body.bracket_type)
    participant_mode = normalize_participant_mode(body.participant_mode)
    team_size = max(1, int(body.team_size or 1))
    if participant_mode == "solo":
        team_size = 1

    require_admin_score_approval = bool(body.require_admin_score_approval)
    if bracket_type == "battle_royale" and not body.require_admin_score_approval:
        require_admin_score_approval = True

    doc = {
        "id": str(uuid.uuid4()),
        "status": "registration",
        "bracket": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
        "bracket_type": bracket_type,
        "participant_mode": participant_mode,
        "team_size": team_size,
        "require_admin_score_approval": require_admin_score_approval,
        "group_size": max(2, int(body.group_size or 4)),
        "advance_per_group": max(1, int(body.advance_per_group or 2)),
        "swiss_rounds": max(1, int(body.swiss_rounds or 5)),
        "battle_royale_group_size": max(2, int(body.battle_royale_group_size or body.group_size or 4)),
        "battle_royale_advance": max(1, int(body.battle_royale_advance or body.advance_per_group or 2)),
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
    if "bracket_type" in update_data:
        update_data["bracket_type"] = normalize_bracket_type(update_data["bracket_type"])
    if "participant_mode" in update_data:
        update_data["participant_mode"] = normalize_participant_mode(update_data["participant_mode"])
    if "team_size" in update_data:
        update_data["team_size"] = max(1, int(update_data["team_size"] or 1))
    if "max_participants" in update_data:
        update_data["max_participants"] = max(2, int(update_data["max_participants"] or 2))
    if "group_size" in update_data:
        update_data["group_size"] = max(2, int(update_data["group_size"] or 4))
    if "advance_per_group" in update_data:
        update_data["advance_per_group"] = max(1, int(update_data["advance_per_group"] or 2))
    if "swiss_rounds" in update_data:
        update_data["swiss_rounds"] = max(1, int(update_data["swiss_rounds"] or 5))
    if "battle_royale_group_size" in update_data:
        update_data["battle_royale_group_size"] = max(2, int(update_data["battle_royale_group_size"] or 4))
    if "battle_royale_advance" in update_data:
        update_data["battle_royale_advance"] = max(1, int(update_data["battle_royale_advance"] or 2))

    if update_data.get("participant_mode") == "solo":
        update_data["team_size"] = 1
    effective_bracket_type = update_data.get("bracket_type")
    if not effective_bracket_type:
        existing_tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0, "bracket_type": 1})
        effective_bracket_type = str((existing_tournament or {}).get("bracket_type", "")).strip().lower()
    if effective_bracket_type == "battle_royale":
        update_data["require_admin_score_approval"] = True

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
        parent_docs = await db.teams.find({"id": {"$in": parent_ids}}, {"_id": 0, "id": 1, "name": 1, "tag": 1, "logo_url": 1, "banner_url": 1}).to_list(500)
    parent_map = {p["id"]: p.get("name", "") for p in parent_docs}
    parent_doc_map = {p["id"]: p for p in parent_docs}

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
        parent_doc = parent_doc_map.get(parent_id, {})
        if not reg.get("team_logo_url"):
            reg["team_logo_url"] = parent_doc.get("logo_url", "")
        if not reg.get("team_banner_url"):
            reg["team_banner_url"] = parent_doc.get("banner_url", "")
        if not reg.get("team_tag"):
            reg["team_tag"] = parent_doc.get("tag", "")

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

    participant_mode = normalize_participant_mode(t.get("participant_mode", "team"))
    requested_team_name = normalize_optional_text(body.team_name, max_len=120)
    team_name = requested_team_name
    team_logo_url = ""
    team_banner_url = ""
    team_tag = ""
    main_team_name = ""
    team_id = None
    normalized_players = []

    expected_team_size = max(1, int(t.get("team_size", 1)))

    if participant_mode == "solo":
        if await db.registrations.find_one({"tournament_id": tournament_id, "user_id": user["id"]}, {"_id": 0}):
            raise HTTPException(400, "Du bist bereits für dieses Turnier registriert")
        team_name = team_name or str(user.get("username", "")).strip() or str(user.get("email", "")).strip()
        team_logo_url = str(user.get("avatar_url", "") or "")
        team_banner_url = str(user.get("banner_url", "") or "")
        player_name = str(user.get("username", "")).strip() or team_name
        player_email = normalize_email(user.get("email", ""))
        normalized_players = [{"name": player_name, "email": player_email}]
    else:
        if not team_name:
            raise HTTPException(400, "Team-Name ist erforderlich")
        if len(body.players) != expected_team_size:
            raise HTTPException(400, f"Es werden genau {expected_team_size} Spieler benötigt")

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
            parent = await db.teams.find_one({"id": parent_team_id}, {"_id": 0, "name": 1, "tag": 1, "logo_url": 1, "banner_url": 1})
            main_team_name = str((parent or {}).get("name", "") or "")
            if not team_logo_url:
                team_logo_url = str((parent or {}).get("logo_url", "") or "")
            if not team_banner_url:
                team_banner_url = str((parent or {}).get("banner_url", "") or "")
            if not team_tag:
                team_tag = str((parent or {}).get("tag", "") or "")

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
        "participant_mode": participant_mode,
        "checked_in": False,
        "payment_status": payment_status,
        "payment_session_id": None,
        "seed": reg_count + 1,
        "created_at": now_iso(),
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
    if bracket_type in ("round_robin", "league", "ladder_system", "king_of_the_hill"):
        matches = [m for rd in bracket.get("rounds", []) for m in rd.get("matches", [])]
        standings = compute_standings_for_registrations(regs, matches, team_map)
        return {"type": bracket_type, "standings": standings, "updated_at": tournament.get("updated_at")}

    if bracket_type == "swiss_system":
        swiss_table = compute_swiss_points(regs, bracket.get("rounds", []))
        rows = []
        for row in swiss_table.values():
            reg = row["registration"]
            rows.append(
                {
                    "registration_id": str(reg.get("id", "")).strip(),
                    "team_id": str(reg.get("team_id", "")).strip(),
                    "team_name": reg.get("team_name", ""),
                    "team_tag": reg.get("team_tag", ""),
                    "team_logo_url": reg.get("team_logo_url", ""),
                    "main_team_name": reg.get("main_team_name", ""),
                    "played": row["wins"] + row["losses"] + row["draws"],
                    "wins": row["wins"],
                    "draws": row["draws"],
                    "losses": row["losses"],
                    "score_for": 0,
                    "score_against": 0,
                    "score_diff": row["score_diff"],
                    "points": row["points"],
                }
            )
        rows.sort(key=lambda r: (-r["points"], -r["score_diff"], str(r.get("team_name", "")).lower()))
        for idx, row in enumerate(rows, start=1):
            row["rank"] = idx
        return {"type": bracket_type, "standings": rows, "updated_at": tournament.get("updated_at")}

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

    if bracket_type == "group_playoffs":
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
        playoffs = bracket.get("playoffs") or {}
        return {
            "type": bracket_type,
            "groups": groups_payload,
            "playoffs_generated": bool(bracket.get("playoffs_generated")),
            "playoffs": {"total_rounds": playoffs.get("total_rounds", 0)},
            "updated_at": tournament.get("updated_at"),
        }

    if bracket_type == "battle_royale":
        table = {}
        reg_map = {str(r.get("id", "")).strip(): r for r in regs if str(r.get("id", "")).strip()}
        for reg_id, reg in reg_map.items():
            table[reg_id] = {
                "registration_id": reg_id,
                "team_id": str(reg.get("team_id", "")).strip(),
                "team_name": reg.get("team_name", ""),
                "team_tag": reg.get("team_tag", ""),
                "team_logo_url": reg.get("team_logo_url", ""),
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
        for rd in bracket.get("rounds", []):
            for heat in rd.get("matches", []):
                if heat.get("status") != "completed":
                    continue
                placements = [str(x).strip() for x in heat.get("placements", []) if str(x).strip()]
                points_map = heat.get("points_map", {}) or {}
                if placements:
                    winner_id = placements[0]
                    if winner_id in table:
                        table[winner_id]["wins"] += 1
                for rid in placements:
                    if rid in table:
                        table[rid]["played"] += 1
                        table[rid]["points"] += int(points_map.get(rid, 0) or 0)
                for idx, rid in enumerate(placements):
                    if rid in table and idx > 0:
                        table[rid]["losses"] += 1
        rows = list(table.values())
        rows.sort(key=lambda r: (-r["points"], -r["wins"], str(r.get("team_name", "")).lower()))
        for idx, row in enumerate(rows, start=1):
            row["rank"] = idx
        return {"type": bracket_type, "standings": rows, "updated_at": tournament.get("updated_at")}

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

def chunked(items: List[Any], size: int) -> List[List[Any]]:
    size = max(1, int(size or 1))
    return [items[i : i + size] for i in range(0, len(items), size)]

def pair_key(reg_id_1: str, reg_id_2: str) -> str:
    a = str(reg_id_1 or "").strip()
    b = str(reg_id_2 or "").strip()
    if not a or not b:
        return ""
    return "|".join(sorted([a, b]))

def build_duel_match(round_num: int, position: int, p1: Optional[Dict], p2: Optional[Dict], *, scheduled_for: str = "", name: str = "") -> Dict[str, Any]:
    match = {
        "id": str(uuid.uuid4()),
        "round": int(round_num),
        "position": int(position),
        "name": name or "",
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
        "scheduled_for": scheduled_for,
    }
    if p1:
        match["team1_id"] = p1.get("id")
        match["team1_name"] = p1.get("team_name", "TBD")
        match["team1_logo_url"] = p1.get("team_logo_url", "")
        match["team1_tag"] = p1.get("team_tag", "")
    if p2:
        match["team2_id"] = p2.get("id")
        match["team2_name"] = p2.get("team_name", "TBD")
        match["team2_logo_url"] = p2.get("team_logo_url", "")
        match["team2_tag"] = p2.get("team_tag", "")
    elif p1:
        match["team2_name"] = "BYE"
        match["winner_id"] = match["team1_id"]
        match["status"] = "completed"
    return match

def round_container(round_num: int, name: str, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"round": int(round_num), "name": name, "matches": matches}

def generate_group_playoffs(registrations: List[Dict], group_size: int = 4, advance_per_group: int = 2, start_date: str = ""):
    groups = generate_group_stage(registrations, group_size=group_size, start_date=start_date)
    adv = max(1, int(advance_per_group or 2))
    return {
        "type": "group_playoffs",
        "groups": groups.get("groups", []),
        "group_size": groups.get("group_size", max(2, int(group_size or 4))),
        "total_groups": groups.get("total_groups", 0),
        "advance_per_group": adv,
        "playoffs": None,
        "playoffs_generated": False,
    }

def compute_swiss_points(registrations: List[Dict], rounds: List[Dict]) -> Dict[str, Dict[str, Any]]:
    table = {}
    for idx, reg in enumerate(registrations):
        reg_id = str(reg.get("id", "")).strip()
        if not reg_id:
            continue
        table[reg_id] = {
            "registration": reg,
            "points": 0.0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "score_diff": 0,
            "seed": int(reg.get("seed", idx + 1) or idx + 1),
        }

    for rd in rounds:
        for match in rd.get("matches", []):
            if match.get("status") != "completed":
                continue
            t1 = str(match.get("team1_id", "")).strip()
            t2 = str(match.get("team2_id", "")).strip()
            if not t1 or t1 not in table:
                continue
            score1 = int(match.get("score1", 0) or 0)
            score2 = int(match.get("score2", 0) or 0)
            table[t1]["score_diff"] += score1 - score2

            if not t2:
                table[t1]["points"] += 1.0
                table[t1]["wins"] += 1
                continue
            if t2 not in table:
                continue

            table[t2]["score_diff"] += score2 - score1
            if score1 > score2:
                table[t1]["points"] += 1.0
                table[t1]["wins"] += 1
                table[t2]["losses"] += 1
            elif score2 > score1:
                table[t2]["points"] += 1.0
                table[t2]["wins"] += 1
                table[t1]["losses"] += 1
            else:
                table[t1]["points"] += 0.5
                table[t2]["points"] += 0.5
                table[t1]["draws"] += 1
                table[t2]["draws"] += 1
    return table

def create_swiss_round_matches(
    ordered_regs: List[Dict],
    used_pairs: Set[str],
    bye_history: Set[str],
    round_num: int,
    start_date: str = "",
):
    base_start = parse_optional_datetime(start_date)
    scheduled_for = ""
    if base_start:
        scheduled_for = (base_start + timedelta(days=7 * (round_num - 1))).isoformat()

    available = list(ordered_regs)
    bye_reg = None
    if len(available) % 2 == 1:
        for candidate in reversed(available):
            cid = str(candidate.get("id", "")).strip()
            if cid and cid not in bye_history:
                bye_reg = candidate
                break
        if bye_reg is None:
            bye_reg = available[-1]
        available = [r for r in available if str(r.get("id", "")).strip() != str(bye_reg.get("id", "")).strip()]

    matches = []
    pos = 0
    while available:
        p1 = available.pop(0)
        match_idx = 0
        p1_id = str(p1.get("id", "")).strip()
        for idx, candidate in enumerate(available):
            candidate_id = str(candidate.get("id", "")).strip()
            pk = pair_key(p1_id, candidate_id)
            if pk and pk not in used_pairs:
                match_idx = idx
                break
        p2 = available.pop(match_idx)
        pk = pair_key(p1_id, str(p2.get("id", "")).strip())
        if pk:
            used_pairs.add(pk)
        matches.append(build_duel_match(round_num, pos, registration_slot(p1), registration_slot(p2), scheduled_for=scheduled_for))
        pos += 1

    if bye_reg:
        bye_id = str(bye_reg.get("id", "")).strip()
        if bye_id:
            bye_history.add(bye_id)
        matches.append(build_duel_match(round_num, pos, registration_slot(bye_reg), None, scheduled_for=scheduled_for, name="BYE"))

    return matches

def generate_swiss_system(registrations: List[Dict], rounds_count: int = 5, start_date: str = ""):
    regs = list(registrations)
    if len(regs) < 2:
        return {"type": "swiss_system", "rounds": [], "current_round": 0, "max_rounds": max(1, int(rounds_count or 5))}
    regs.sort(key=lambda r: int(r.get("seed", 999999) or 999999))
    max_rounds = max(1, int(rounds_count or 5))
    used_pairs: Set[str] = set()
    bye_history: Set[str] = set()
    first_round = create_swiss_round_matches(regs, used_pairs, bye_history, 1, start_date=start_date)
    return {
        "type": "swiss_system",
        "rounds": [round_container(1, "Swiss Runde 1", first_round)],
        "current_round": 1,
        "max_rounds": max_rounds,
        "total_rounds": max_rounds,
        "used_pairs": sorted(list(used_pairs)),
        "bye_reg_ids": sorted(list(bye_history)),
    }

def generate_ladder_system(registrations: List[Dict], start_date: str = ""):
    regs = list(registrations)
    if len(regs) < 2:
        return {"type": "ladder_system", "rounds": [], "ladder_cycle_count": 0, "ladder_max_cycles": 0}
    regs.sort(key=lambda r: int(r.get("seed", 999999) or 999999))
    champion = registration_slot(regs[0])
    queue = [registration_slot(r) for r in regs[1:]]
    first_match = build_duel_match(1, 0, champion, queue[0], scheduled_for=(parse_optional_datetime(start_date) or datetime.now(timezone.utc)).isoformat())
    return {
        "type": "ladder_system",
        "rounds": [round_container(1, "Ladder Match 1", [first_match])],
        "champion_id": champion.get("id"),
        "challenger_queue": [q.get("id") for q in queue],
        "ladder_cycle_count": 0,
        "ladder_max_cycles": max(1, len(regs) * 2),
        "total_rounds": max(1, len(regs) * 2),
    }

def generate_king_of_the_hill(registrations: List[Dict], start_date: str = ""):
    regs = list(registrations)
    if len(regs) < 2:
        return {"type": "king_of_the_hill", "rounds": [], "koth_queue": []}
    regs.sort(key=lambda r: int(r.get("seed", 999999) or 999999))
    champion = registration_slot(regs[0])
    queue = [registration_slot(r) for r in regs[1:]]
    first_match = build_duel_match(1, 0, champion, queue[0], scheduled_for=(parse_optional_datetime(start_date) or datetime.now(timezone.utc)).isoformat())
    return {
        "type": "king_of_the_hill",
        "rounds": [round_container(1, "KOTH Runde 1", [first_match])],
        "champion_id": champion.get("id"),
        "koth_queue": [q.get("id") for q in queue],
        "total_rounds": len(queue),
    }

def build_battle_royale_heat(round_num: int, pos: int, regs: List[Dict], scheduled_for: str = "") -> Dict[str, Any]:
    participants = []
    for reg in regs:
        participants.append(
            {
                "registration_id": str(reg.get("id", "")).strip(),
                "name": reg.get("team_name", ""),
                "logo_url": reg.get("team_logo_url", ""),
                "tag": reg.get("team_tag", ""),
            }
        )
    return {
        "id": str(uuid.uuid4()),
        "round": round_num,
        "position": pos,
        "type": "battle_royale_heat",
        "participants": participants,
        "placements": [],
        "points_map": {},
        "status": "pending",
        "approved": False,
        "scheduled_for": scheduled_for,
    }

def generate_battle_royale(registrations: List[Dict], group_size: int = 4, advance_per_heat: int = 2, start_date: str = ""):
    regs = list(registrations)
    if len(regs) < 2:
        return {"type": "battle_royale", "rounds": [], "group_size": max(2, int(group_size or 4)), "advance_per_heat": max(1, int(advance_per_heat or 2))}
    size = max(2, int(group_size or 4))
    adv = max(1, int(advance_per_heat or 2))
    if adv >= size:
        adv = max(1, size - 1)
    base_start = parse_optional_datetime(start_date)
    scheduled_for = base_start.isoformat() if base_start else ""
    heats = []
    for pos, group_regs in enumerate(chunked(regs, size)):
        if len(group_regs) < 2:
            continue
        heats.append(build_battle_royale_heat(1, pos, group_regs, scheduled_for=scheduled_for))
    return {
        "type": "battle_royale",
        "rounds": [round_container(1, "Battle Royale Runde 1", heats)] if heats else [],
        "group_size": size,
        "advance_per_heat": adv,
        "current_round": 1,
        "total_rounds": 1,
    }

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
    if bracket_type in ("single_elimination", "round_robin", "league", "swiss_system", "ladder_system", "king_of_the_hill", "battle_royale"):
        all_rounds = bracket.get("rounds", [])
    elif bracket_type == "double_elimination":
        all_rounds = bracket.get("winners_bracket", {}).get("rounds", []) + bracket.get("losers_bracket", {}).get("rounds", [])
    elif bracket_type == "group_stage":
        for group in bracket.get("groups", []):
            all_rounds.extend(group.get("rounds", []))
    elif bracket_type == "group_playoffs":
        for group in bracket.get("groups", []):
            all_rounds.extend(group.get("rounds", []))
        playoffs = bracket.get("playoffs") or {}
        all_rounds.extend(playoffs.get("rounds", []))

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
    for participant in match_data.get("participants", []):
        rid = str((participant or {}).get("registration_id", "")).strip()
        if rid:
            reg_ids.append(rid)
    reg_ids = list(dict.fromkeys(reg_ids))
    if not reg_ids:
        return False

    regs = await db.registrations.find({"id": {"$in": reg_ids}}, {"_id": 0}).to_list(100)
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
    bracket_type = normalize_bracket_type(t.get("bracket_type", "single_elimination"))
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
    elif bracket_type == "group_playoffs":
        bracket = generate_group_playoffs(
            regs,
            group_size=int(t.get("group_size", 4) or 4),
            advance_per_group=int(t.get("advance_per_group", 2) or 2),
            start_date=t.get("start_date", ""),
        )
    elif bracket_type == "swiss_system":
        bracket = generate_swiss_system(regs, rounds_count=int(t.get("swiss_rounds", 5) or 5), start_date=t.get("start_date", ""))
    elif bracket_type == "ladder_system":
        bracket = generate_ladder_system(regs, start_date=t.get("start_date", ""))
    elif bracket_type == "king_of_the_hill":
        bracket = generate_king_of_the_hill(regs, start_date=t.get("start_date", ""))
    elif bracket_type == "battle_royale":
        bracket = generate_battle_royale(
            regs,
            group_size=int(t.get("battle_royale_group_size", t.get("group_size", 4)) or 4),
            advance_per_heat=int(t.get("battle_royale_advance", t.get("advance_per_group", 2)) or 2),
            start_date=t.get("start_date", ""),
        )
    else:
        bracket = generate_single_elimination(regs)
    await db.tournaments.update_one(
        {"id": tournament_id},
        {"$set": {"bracket": bracket, "status": "live", "updated_at": now_iso()}}
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
    if match_data.get("type") == "battle_royale_heat" or match_data.get("participants"):
        raise HTTPException(400, "Für Battle Royale bitte das BR-Ergebnis-System verwenden")
    if not match_data.get("team1_id") or not match_data.get("team2_id"):
        raise HTTPException(400, "Dieses Match kann nicht per Team-Score gemeldet werden")

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
            if t.get("require_admin_score_approval"):
                await db.score_submissions.update_many(
                    {"tournament_id": tournament_id, "match_id": match_id},
                    {"$set": {"status": "pending_admin_approval", "updated_at": now_iso()}},
                )
                admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1, "email": 1}).to_list(20)
                for admin in admins:
                    await db.notifications.insert_one(
                        {
                            "id": str(uuid.uuid4()),
                            "user_id": admin["id"],
                            "type": "score_approval",
                            "message": f"Ergebnis wartet auf Admin-Freigabe: {match_data.get('team1_name')} vs {match_data.get('team2_name')}",
                            "link": f"/tournaments/{tournament_id}",
                            "read": False,
                            "created_at": now_iso(),
                        }
                    )
                    if admin.get("email"):
                        await send_email_notification(
                            admin["email"],
                            "ARENA: Ergebnis-Freigabe erforderlich",
                            f"Ein Ergebnis wartet auf Freigabe: {match_data.get('team1_name')} vs {match_data.get('team2_name')}.",
                        )
                return {"status": "pending_admin_approval", "message": "Ergebnis eingereicht und wartet auf Admin-Freigabe."}
            # Scores agree -> auto-confirm
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

def normalize_battle_royale_placements(match_doc: Dict, placements: List[str]) -> List[str]:
    participant_ids = [str((p or {}).get("registration_id", "")).strip() for p in match_doc.get("participants", []) if str((p or {}).get("registration_id", "")).strip()]
    participant_set = set(participant_ids)
    ordered = []
    seen = set()
    for reg_id in placements:
        rid = str(reg_id or "").strip()
        if not rid or rid in seen or rid not in participant_set:
            continue
        ordered.append(rid)
        seen.add(rid)
    for rid in participant_ids:
        if rid not in seen:
            ordered.append(rid)
    if len(ordered) != len(participant_ids):
        raise HTTPException(400, "Ungültige Platzierungen")
    return ordered

async def _apply_battle_royale_result(tournament_id: str, match_id: str, placements: List[str]):
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not tournament or not tournament.get("bracket"):
        raise HTTPException(404, "Turnier oder Bracket nicht gefunden")
    bracket = tournament["bracket"]
    if bracket.get("type") != "battle_royale":
        raise HTTPException(400, "Kein Battle Royale Bracket")

    rounds = bracket.get("rounds", [])
    match_doc = None
    round_idx = -1
    for r_idx, rd in enumerate(rounds):
        for m in rd.get("matches", []):
            if m.get("id") == match_id:
                match_doc = m
                round_idx = r_idx
                break
        if match_doc:
            break
    if not match_doc:
        raise HTTPException(404, "BR-Heat nicht gefunden")
    if match_doc.get("status") == "completed":
        raise HTTPException(400, "BR-Heat ist bereits abgeschlossen")

    ordered = normalize_battle_royale_placements(match_doc, placements)
    total_players = len(ordered)
    points_map = {}
    for idx, reg_id in enumerate(ordered):
        points_map[reg_id] = max(0, total_players - idx)
    match_doc["placements"] = ordered
    match_doc["points_map"] = points_map
    match_doc["status"] = "completed"
    match_doc["approved"] = True
    match_doc["resolved_at"] = now_iso()

    # Generate next round once all heats in the current round are completed.
    current_round_matches = rounds[round_idx].get("matches", [])
    current_round_done = bool(current_round_matches) and all(m.get("status") == "completed" for m in current_round_matches)
    if current_round_done and round_idx == len(rounds) - 1:
        advance_per_heat = max(1, int(bracket.get("advance_per_heat", 2) or 2))
        next_reg_ids = []
        for heat in current_round_matches:
            heat_placements = [str(rid).strip() for rid in heat.get("placements", []) if str(rid).strip()]
            next_reg_ids.extend(heat_placements[:advance_per_heat])
        next_reg_ids = list(dict.fromkeys(next_reg_ids))

        if len(next_reg_ids) >= 2:
            reg_docs = await db.registrations.find({"tournament_id": tournament_id, "id": {"$in": next_reg_ids}}, {"_id": 0}).to_list(800)
            reg_map = {str(r.get("id", "")).strip(): r for r in reg_docs if str(r.get("id", "")).strip()}
            next_regs = [reg_map[rid] for rid in next_reg_ids if rid in reg_map]
            group_size = max(2, int(bracket.get("group_size", 4) or 4))
            new_round_no = len(rounds) + 1
            base_start = parse_optional_datetime(tournament.get("start_date", ""))
            scheduled_for = ""
            if base_start:
                scheduled_for = (base_start + timedelta(days=7 * (new_round_no - 1))).isoformat()
            new_heats = []
            for pos, group_regs in enumerate(chunked(next_regs, group_size)):
                if len(group_regs) < 2:
                    continue
                new_heats.append(build_battle_royale_heat(new_round_no, pos, group_regs, scheduled_for=scheduled_for))
            if new_heats:
                rounds.append(round_container(new_round_no, f"Battle Royale Runde {new_round_no}", new_heats))
                bracket["current_round"] = new_round_no
                bracket["total_rounds"] = len(rounds)

    update_status = None
    last_round_matches = rounds[-1].get("matches", []) if rounds else []
    if last_round_matches and len(last_round_matches) == 1 and last_round_matches[0].get("status") == "completed":
        update_status = "completed"

    update_doc = {"bracket": bracket, "updated_at": now_iso()}
    if update_status:
        update_doc["status"] = update_status
    await db.tournaments.update_one({"id": tournament_id}, {"$set": update_doc})

@api_router.post("/tournaments/{tournament_id}/matches/{match_id}/submit-battle-royale")
async def submit_battle_royale_result(request: Request, tournament_id: str, match_id: str, body: BattleRoyaleResultSubmission):
    user = await require_auth(request)
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0, "bracket": 1})
    match = find_match_in_bracket((tournament or {}).get("bracket"), match_id)
    if not tournament or not match:
        raise HTTPException(404, "Turnier oder Heat nicht gefunden")
    if (tournament.get("bracket") or {}).get("type") != "battle_royale":
        raise HTTPException(400, "Kein Battle Royale Turnier")
    if match.get("status") == "completed":
        raise HTTPException(400, "Heat bereits abgeschlossen")
    if user.get("role") != "admin" and not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")

    placements = normalize_battle_royale_placements(match, body.placements)
    await db.battle_royale_submissions.update_one(
        {"tournament_id": tournament_id, "match_id": match_id, "submitted_by": user["id"]},
        {
            "$set": {
                "tournament_id": tournament_id,
                "match_id": match_id,
                "submitted_by": user["id"],
                "submitted_by_name": user.get("username", ""),
                "placements": placements,
                "status": "pending_admin_approval",
                "updated_at": now_iso(),
            },
            "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now_iso()},
        },
        upsert=True,
    )

    if user.get("role") == "admin":
        await _apply_battle_royale_result(tournament_id, match_id, placements)
        await db.battle_royale_submissions.update_many(
            {"tournament_id": tournament_id, "match_id": match_id},
            {"$set": {"status": "resolved_by_admin", "resolved_at": now_iso(), "resolved_by": user["id"]}},
        )
        return {"status": "resolved", "message": "BR-Ergebnis sofort als Admin übernommen."}

    admins = await db.users.find({"role": "admin"}, {"_id": 0, "id": 1, "email": 1}).to_list(25)
    for admin in admins:
        await db.notifications.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": admin["id"],
                "type": "battle_royale_approval",
                "message": "Battle-Royale-Ergebnis wartet auf Freigabe",
                "link": f"/tournaments/{tournament_id}",
                "read": False,
                "created_at": now_iso(),
            }
        )
        if admin.get("email"):
            await send_email_notification(
                admin["email"],
                "ARENA: Battle Royale Ergebnis-Freigabe",
                "Ein Battle-Royale-Ergebnis wartet auf deine Freigabe.",
            )
    return {"status": "pending_admin_approval", "message": "Ergebnis eingereicht. Admin-Freigabe erforderlich."}

@api_router.get("/tournaments/{tournament_id}/matches/{match_id}/battle-royale-submissions")
async def get_battle_royale_submissions(request: Request, tournament_id: str, match_id: str):
    user = await require_auth(request)
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0, "bracket": 1})
    match = find_match_in_bracket((tournament or {}).get("bracket"), match_id)
    if user.get("role") != "admin" and not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")
    subs = await db.battle_royale_submissions.find({"tournament_id": tournament_id, "match_id": match_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return subs

@api_router.put("/tournaments/{tournament_id}/matches/{match_id}/battle-royale-resolve")
async def resolve_battle_royale_result(request: Request, tournament_id: str, match_id: str, body: BattleRoyaleResultSubmission):
    admin = await require_admin(request)
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0, "bracket": 1})
    match = find_match_in_bracket((tournament or {}).get("bracket"), match_id)
    if not tournament or not match:
        raise HTTPException(404, "Turnier oder Heat nicht gefunden")
    placements = normalize_battle_royale_placements(match, body.placements)
    await _apply_battle_royale_result(tournament_id, match_id, placements)
    await db.battle_royale_submissions.update_many(
        {"tournament_id": tournament_id, "match_id": match_id},
        {"$set": {"status": "resolved_by_admin", "resolved_at": now_iso(), "resolved_by": admin["id"]}},
    )
    return await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})

async def _apply_score_to_bracket(tournament_id: str, match_id: str, score1: int, score2: int, winner_id: str = None, disqualify_id: str = None):
    """Internal: apply finalized score to bracket and propagate."""
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    bracket = t["bracket"]
    bracket_type = bracket.get("type", "single_elimination")
    match_found = False
    match_round_idx = -1
    match_pos = -1
    target_rounds = None
    match_scope = ""

    def apply_to_match(match_doc: Dict, *, knockout: bool):
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
        elif knockout:
            raise HTTPException(400, "Unentschieden ist im K.o.-Modus nicht erlaubt")
        else:
            match_doc["winner_id"] = None
        match_doc["status"] = "completed"

    def propagate_within_rounds(rounds_ref: List[Dict], r_idx: int, m_idx: int):
        if r_idx < 0 or r_idx >= len(rounds_ref) - 1:
            return
        cm = rounds_ref[r_idx]["matches"][m_idx]
        if not cm.get("winner_id"):
            return
        nm = rounds_ref[r_idx + 1]["matches"][m_idx // 2]
        slot = "team1" if m_idx % 2 == 0 else "team2"
        winner_is_team1 = cm["winner_id"] == cm.get("team1_id")
        nm[f"{slot}_id"] = cm["winner_id"]
        nm[f"{slot}_name"] = cm.get("team1_name", "TBD") if winner_is_team1 else cm.get("team2_name", "TBD")
        nm[f"{slot}_logo_url"] = cm.get("team1_logo_url", "") if winner_is_team1 else cm.get("team2_logo_url", "")
        nm[f"{slot}_tag"] = cm.get("team1_tag", "") if winner_is_team1 else cm.get("team2_tag", "")

    # locate and apply
    if bracket_type in ("single_elimination", "round_robin", "league", "swiss_system", "ladder_system", "king_of_the_hill"):
        rounds = bracket.get("rounds", [])
        for r_idx, rd in enumerate(rounds):
            for m_idx, m in enumerate(rd.get("matches", [])):
                if m.get("id") == match_id:
                    apply_to_match(m, knockout=bracket_type in ("single_elimination", "ladder_system", "king_of_the_hill"))
                    match_found = True
                    match_round_idx = r_idx
                    match_pos = m_idx
                    target_rounds = rounds
                    match_scope = "main"
                    break
            if match_found:
                break
    elif bracket_type == "double_elimination":
        rounds = bracket.get("winners_bracket", {}).get("rounds", []) + bracket.get("losers_bracket", {}).get("rounds", [])
        for rd in rounds:
            for m in rd.get("matches", []):
                if m.get("id") == match_id:
                    apply_to_match(m, knockout=True)
                    match_found = True
                    break
            if match_found:
                break
        if not match_found:
            gf = bracket.get("grand_final")
            if gf and gf.get("id") == match_id:
                apply_to_match(gf, knockout=True)
                match_found = True
                match_scope = "grand_final"
    elif bracket_type in ("group_stage", "group_playoffs"):
        for group in bracket.get("groups", []):
            rounds = group.get("rounds", [])
            for rd in rounds:
                for m in rd.get("matches", []):
                    if m.get("id") == match_id:
                        apply_to_match(m, knockout=False)
                        match_found = True
                        match_scope = "group"
                        break
                if match_found:
                    break
            if match_found:
                break
        if not match_found and bracket_type == "group_playoffs" and bracket.get("playoffs"):
            playoffs_rounds = bracket.get("playoffs", {}).get("rounds", [])
            for r_idx, rd in enumerate(playoffs_rounds):
                for m_idx, m in enumerate(rd.get("matches", [])):
                    if m.get("id") == match_id:
                        apply_to_match(m, knockout=True)
                        match_found = True
                        match_round_idx = r_idx
                        match_pos = m_idx
                        target_rounds = playoffs_rounds
                        match_scope = "playoff"
                        break
                if match_found:
                    break
    else:
        raise HTTPException(400, f"Score-Update für Bracket-Typ '{bracket_type}' nicht unterstützt")

    if not match_found:
        raise HTTPException(404, "Match nicht gefunden")

    # propagate knockouts
    if bracket_type == "single_elimination" and target_rounds is not None:
        propagate_within_rounds(target_rounds, match_round_idx, match_pos)
    if bracket_type == "group_playoffs" and match_scope == "playoff" and target_rounds is not None:
        propagate_within_rounds(target_rounds, match_round_idx, match_pos)

    # dynamic progression
    if bracket_type == "group_playoffs" and not bracket.get("playoffs_generated"):
        all_group_matches = []
        for group in bracket.get("groups", []):
            for rd in group.get("rounds", []):
                all_group_matches.extend([m for m in rd.get("matches", []) if m.get("team1_id") and m.get("team2_id")])
        groups_done = bool(all_group_matches) and all(m.get("status") == "completed" for m in all_group_matches)
        if groups_done:
            regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(600)
            reg_map = {str(r.get("id", "")).strip(): r for r in regs if str(r.get("id", "")).strip()}
            team_ids = [str(r.get("team_id", "")).strip() for r in regs if str(r.get("team_id", "")).strip()]
            team_docs = await db.teams.find({"id": {"$in": team_ids}}, {"_id": 0, "id": 1, "tag": 1, "logo_url": 1}).to_list(1000) if team_ids else []
            team_map = {t.get("id"): t for t in team_docs}
            qualifiers = []
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
                adv = max(1, int(bracket.get("advance_per_group", 2) or 2))
                for row in standings[:adv]:
                    reg = reg_map.get(str(row.get("registration_id", "")).strip())
                    if reg:
                        qualifiers.append(reg)
            if len(qualifiers) >= 2:
                bracket["playoffs"] = generate_single_elimination(qualifiers)
            else:
                bracket["playoffs"] = {"type": "single_elimination", "rounds": [], "total_rounds": 0}
            bracket["playoffs_generated"] = True

    if bracket_type == "swiss_system":
        rounds = bracket.get("rounds", [])
        current_round = int(bracket.get("current_round", len(rounds) or 1) or 1)
        max_rounds = int(bracket.get("max_rounds", current_round) or current_round)
        if match_round_idx >= 0 and match_round_idx < len(rounds):
            current_round_matches = rounds[match_round_idx].get("matches", [])
            if current_round_matches and all(m.get("status") == "completed" for m in current_round_matches):
                if current_round < max_rounds:
                    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(600)
                    swiss_table = compute_swiss_points(regs, rounds)
                    ordered_regs = [
                        row["registration"]
                        for row in sorted(
                            swiss_table.values(),
                            key=lambda row: (-row["points"], -row["score_diff"], -row["wins"], row["seed"]),
                        )
                    ]
                    used_pairs = set(bracket.get("used_pairs", []))
                    bye_history = set(bracket.get("bye_reg_ids", []))
                    next_round_no = current_round + 1
                    next_matches = create_swiss_round_matches(
                        ordered_regs,
                        used_pairs,
                        bye_history,
                        next_round_no,
                        start_date=t.get("start_date", ""),
                    )
                    rounds.append(round_container(next_round_no, f"Swiss Runde {next_round_no}", next_matches))
                    bracket["current_round"] = next_round_no
                    bracket["used_pairs"] = sorted(list(used_pairs))
                    bracket["bye_reg_ids"] = sorted(list(bye_history))

    if bracket_type in ("ladder_system", "king_of_the_hill") and match_scope == "main":
        rounds = bracket.get("rounds", [])
        current_match = rounds[match_round_idx]["matches"][match_pos]
        champion_id = str(bracket.get("champion_id", current_match.get("team1_id"))).strip()
        winner_reg_id = str(current_match.get("winner_id", "")).strip()
        challenger_id = str(current_match.get("team2_id", "")).strip()

        if bracket_type == "ladder_system":
            queue = [str(x).strip() for x in bracket.get("challenger_queue", []) if str(x).strip()]
            if queue and queue[0] == challenger_id:
                queue.pop(0)
            elif challenger_id in queue:
                queue.remove(challenger_id)

            if winner_reg_id and winner_reg_id == challenger_id:
                old_champion = champion_id
                champion_id = challenger_id
                if old_champion:
                    queue.append(old_champion)
            else:
                if challenger_id:
                    queue.append(challenger_id)

            bracket["champion_id"] = champion_id
            bracket["challenger_queue"] = queue
            bracket["ladder_cycle_count"] = int(bracket.get("ladder_cycle_count", 0) or 0) + 1

            can_continue = bool(queue) and int(bracket.get("ladder_cycle_count", 0) or 0) < int(bracket.get("ladder_max_cycles", 1) or 1)
            if can_continue:
                reg_docs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(600)
                reg_map = {str(r.get("id", "")).strip(): r for r in reg_docs}
                champion_reg = reg_map.get(champion_id)
                next_challenger_reg = reg_map.get(queue[0]) if queue else None
                if champion_reg and next_challenger_reg:
                    new_round_no = len(rounds) + 1
                    next_match = build_duel_match(new_round_no, 0, registration_slot(champion_reg), registration_slot(next_challenger_reg))
                    rounds.append(round_container(new_round_no, f"Ladder Match {new_round_no}", [next_match]))

        if bracket_type == "king_of_the_hill":
            queue = [str(x).strip() for x in bracket.get("koth_queue", []) if str(x).strip()]
            if queue and queue[0] == challenger_id:
                queue.pop(0)
            elif challenger_id in queue:
                queue.remove(challenger_id)

            if winner_reg_id and winner_reg_id == challenger_id:
                champion_id = challenger_id
            bracket["champion_id"] = champion_id
            bracket["koth_queue"] = queue

            if queue:
                reg_docs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(600)
                reg_map = {str(r.get("id", "")).strip(): r for r in reg_docs}
                champion_reg = reg_map.get(champion_id)
                next_challenger_reg = reg_map.get(queue[0])
                if champion_reg and next_challenger_reg:
                    new_round_no = len(rounds) + 1
                    next_match = build_duel_match(new_round_no, 0, registration_slot(champion_reg), registration_slot(next_challenger_reg))
                    rounds.append(round_container(new_round_no, f"KOTH Runde {new_round_no}", [next_match]))

    update_status = None
    if bracket_type == "single_elimination":
        rounds = bracket.get("rounds", [])
        if rounds and rounds[-1].get("matches") and rounds[-1]["matches"][0].get("winner_id"):
            update_status = "completed"
    elif bracket_type in ("round_robin", "league"):
        rounds = bracket.get("rounds", [])
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
    elif bracket_type == "group_playoffs":
        playoffs = bracket.get("playoffs") or {}
        playoffs_rounds = playoffs.get("rounds", [])
        if playoffs_rounds and playoffs_rounds[-1].get("matches") and playoffs_rounds[-1]["matches"][0].get("winner_id"):
            update_status = "completed"
    elif bracket_type == "double_elimination":
        gf = bracket.get("grand_final")
        if gf and gf.get("winner_id"):
            update_status = "completed"
    elif bracket_type == "swiss_system":
        rounds = bracket.get("rounds", [])
        max_rounds = int(bracket.get("max_rounds", len(rounds) or 1) or 1)
        if len(rounds) >= max_rounds and rounds and all(m.get("status") == "completed" for rd in rounds for m in rd.get("matches", [])):
            update_status = "completed"
    elif bracket_type == "ladder_system":
        if int(bracket.get("ladder_cycle_count", 0) or 0) >= int(bracket.get("ladder_max_cycles", 1) or 1):
            update_status = "completed"
    elif bracket_type == "king_of_the_hill":
        if not bracket.get("koth_queue"):
            update_status = "completed"

    update_doc = {"bracket": bracket, "updated_at": now_iso()}
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

# ─── Payment Endpoints ───

@api_router.post("/payments/create-checkout")
async def create_checkout(request: Request, body: PaymentRequest):
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

    payment_provider = await get_payment_provider(body.provider)
    host_url = body.origin_url.rstrip("/")
    if not (host_url.startswith("http://") or host_url.startswith("https://")):
        raise HTTPException(400, "Invalid origin URL")

    currency = str(t.get("currency", "usd") or "usd").lower()
    unit_amount = int(round(float(entry_fee) * 100))
    if unit_amount <= 0:
        raise HTTPException(400, "Invalid entry fee")
    if payment_provider == "paypal":
        return_url = f"{host_url}/tournaments/{body.tournament_id}?payment_provider=paypal"
        cancel_url = f"{host_url}/tournaments/{body.tournament_id}?payment_cancelled=1"
        order = await create_paypal_order(
            amount=float(entry_fee),
            currency=currency,
            tournament_name=str(t.get("name", "Tournament") or "Tournament"),
            return_url=return_url,
            cancel_url=cancel_url,
        )
        order_id = str((order or {}).get("id", "")).strip()
        if not order_id:
            raise HTTPException(500, "PayPal Order konnte nicht erstellt werden")
        approve_url = ""
        for link in (order or {}).get("links", []):
            if str((link or {}).get("rel", "")).strip().lower() == "approve":
                approve_url = str((link or {}).get("href", "")).strip()
                break
        if not approve_url:
            raise HTTPException(500, "PayPal Freigabe-URL fehlt")

        payment_doc = {
            "id": str(uuid.uuid4()),
            "provider": "paypal",
            "session_id": order_id,
            "tournament_id": body.tournament_id,
            "registration_id": body.registration_id,
            "amount": float(entry_fee),
            "currency": currency,
            "payment_status": "pending",
            "status": str((order or {}).get("status", "CREATED") or "CREATED"),
            "metadata": {"tournament_id": body.tournament_id, "registration_id": body.registration_id},
            "created_at": now_iso(),
        }
        await db.payment_transactions.insert_one(payment_doc)
        await db.registrations.update_one({"id": body.registration_id}, {"$set": {"payment_session_id": order_id}})
        return {"url": approve_url, "session_id": order_id, "provider": "paypal"}

    stripe_api_key = await get_stripe_api_key()
    if not stripe_api_key:
        raise HTTPException(500, "Stripe ist nicht konfiguriert")
    stripe.api_key = stripe_api_key
    success_url = f"{host_url}/tournaments/{body.tournament_id}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/tournaments/{body.tournament_id}?payment_cancelled=1"
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"tournament_id": body.tournament_id, "registration_id": body.registration_id},
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "product_data": {"name": f"Turniergebühr: {t.get('name', 'Tournament')}"},
                        "unit_amount": unit_amount,
                    },
                    "quantity": 1,
                }
            ],
        )
    except Exception as e:
        logger.error(f"Stripe checkout create error: {e}")
        raise HTTPException(500, "Stripe checkout konnte nicht erstellt werden")

    payment_doc = {
        "id": str(uuid.uuid4()),
        "provider": "stripe",
        "session_id": session.id,
        "tournament_id": body.tournament_id,
        "registration_id": body.registration_id,
        "amount": float(entry_fee),
        "currency": currency,
        "payment_status": "pending",
        "status": "initiated",
        "metadata": {"tournament_id": body.tournament_id, "registration_id": body.registration_id},
        "created_at": now_iso(),
    }
    await db.payment_transactions.insert_one(payment_doc)
    await db.registrations.update_one({"id": body.registration_id}, {"$set": {"payment_session_id": session.id}})
    return {"url": session.url, "session_id": session.id, "provider": "stripe"}

@api_router.get("/payments/status/{session_id}")
async def check_payment_status(request: Request, session_id: str):
    user = await require_auth(request)
    existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Payment session not found")

    registration = await db.registrations.find_one({"id": existing.get("registration_id")}, {"_id": 0, "user_id": 1})
    if registration and registration.get("user_id") and registration.get("user_id") != user.get("id") and user.get("role") != "admin":
        raise HTTPException(403, "Keine Berechtigung")

    provider = str(existing.get("provider", "stripe") or "stripe").strip().lower()
    if provider == "paypal":
        order = await get_paypal_order(session_id)
        order_status = str((order or {}).get("status", "") or "").strip().upper()
        payment_status = "pending"

        if order_status == "APPROVED":
            try:
                capture = await capture_paypal_order(session_id)
                capture_status = str((capture or {}).get("status", "") or "").strip().upper()
                if capture_status:
                    order_status = capture_status
            except HTTPException:
                refreshed = await get_paypal_order(session_id)
                order = refreshed or order
                order_status = str((refreshed or {}).get("status", order_status) or order_status).strip().upper()

        if order_status == "COMPLETED":
            payment_status = "paid"
        elif order_status in {"VOIDED", "CANCELLED", "DECLINED", "FAILED"}:
            payment_status = "failed"

        amount_total = 0
        currency_code = str(existing.get("currency", "") or "").upper()
        try:
            purchase_units = (order or {}).get("purchase_units", []) or []
            amount_obj = ((purchase_units[0] if purchase_units else {}) or {}).get("amount", {}) or {}
            if amount_obj.get("value"):
                amount_total = int(round(float(amount_obj.get("value")) * 100))
            if amount_obj.get("currency_code"):
                currency_code = str(amount_obj.get("currency_code") or "").upper()
        except Exception:
            pass

        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": payment_status, "status": order_status, "updated_at": now_iso()}},
        )
        if payment_status == "paid":
            await db.registrations.update_one({"id": existing["registration_id"]}, {"$set": {"payment_status": "paid"}})

        return {
            "provider": "paypal",
            "status": order_status,
            "payment_status": payment_status,
            "amount_total": amount_total,
            "currency": currency_code.lower(),
        }

    stripe_api_key = await get_stripe_api_key()
    if not stripe_api_key:
        raise HTTPException(500, "Stripe ist nicht konfiguriert")
    stripe.api_key = stripe_api_key
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        logger.error(f"Stripe checkout status error: {e}")
        raise HTTPException(404, "Payment session not found")

    payment_status = str(getattr(session, "payment_status", "") or "")
    session_status = str(getattr(session, "status", "") or "")
    if existing.get("payment_status") != "paid":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": payment_status, "status": session_status, "updated_at": now_iso()}},
        )
        if payment_status == "paid":
            await db.registrations.update_one({"id": existing["registration_id"]}, {"$set": {"payment_status": "paid"}})
    return {
        "provider": "stripe",
        "status": session_status,
        "payment_status": payment_status,
        "amount_total": int(getattr(session, "amount_total", 0) or 0),
        "currency": str(getattr(session, "currency", "") or ""),
    }

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    stripe_api_key = await get_stripe_api_key()
    if not stripe_api_key:
        raise HTTPException(500, "Payment system not configured")
    stripe.api_key = stripe_api_key
    webhook_secret = await get_stripe_webhook_secret()
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    try:
        if webhook_secret and signature:
            event = stripe.Webhook.construct_event(body, signature, webhook_secret)
        else:
            event = json.loads(body.decode("utf-8"))

        event_type = str((event or {}).get("type", ""))
        session_obj = (event or {}).get("data", {}).get("object", {}) if isinstance(event, dict) else {}
        session_id = str(session_obj.get("id", "")).strip()
        payment_status = str(session_obj.get("payment_status", "")).strip()

        if session_id and event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"} and payment_status == "paid":
            existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0, "registration_id": 1})
            if existing:
                await db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": {"payment_status": "paid", "status": "complete", "updated_at": now_iso()}},
                )
                await db.registrations.update_one(
                    {"id": existing["registration_id"]},
                    {"$set": {"payment_status": "paid"}},
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
            if b["type"] in ("single_elimination", "round_robin", "league", "swiss_system", "ladder_system", "king_of_the_hill"):
                for rd in b.get("rounds", []):
                    all_matches.extend(rd["matches"])
            elif b["type"] == "double_elimination":
                for rd in b.get("winners_bracket", {}).get("rounds", []):
                    all_matches.extend(rd["matches"])
            elif b["type"] == "group_stage":
                for group in b.get("groups", []):
                    for rd in group.get("rounds", []):
                        all_matches.extend(rd.get("matches", []))
            elif b["type"] == "group_playoffs":
                for group in b.get("groups", []):
                    for rd in group.get("rounds", []):
                        all_matches.extend(rd.get("matches", []))
                for rd in (b.get("playoffs") or {}).get("rounds", []):
                    all_matches.extend(rd.get("matches", []))
            elif b["type"] == "battle_royale":
                for rd in b.get("rounds", []):
                    all_matches.extend(rd.get("matches", []))
            for m in all_matches:
                if m.get("status") == "completed":
                    if m.get("type") == "battle_royale_heat" or m.get("participants"):
                        placements = [str(x).strip() for x in m.get("placements", []) if str(x).strip()]
                        if reg["id"] in placements:
                            if placements and placements[0] == reg["id"]:
                                wins += 1
                            else:
                                losses += 1
                    elif m.get("team1_id") == reg["id"] or m.get("team2_id") == reg["id"]:
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

@api_router.post("/admin/email/test")
async def admin_send_test_email(request: Request, body: AdminEmailTest):
    await require_admin(request)
    to_email = normalize_email(body.email)
    if not to_email or not is_valid_email(to_email):
        raise HTTPException(400, "Ungültige E-Mail-Adresse")
    ok = await send_email_notification(
        to_email,
        "ARENA SMTP Test",
        "Dies ist eine Testnachricht aus dem ARENA Adminbereich.",
    )
    if not ok:
        raise HTTPException(400, "SMTP Versand fehlgeschlagen. Bitte SMTP Einstellungen prüfen.")
    return {"status": "sent", "email": to_email}

@api_router.post("/admin/reminders/checkin/{tournament_id}")
async def admin_send_checkin_reminders(request: Request, tournament_id: str):
    await require_admin(request)
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0, "id": 1, "name": 1, "status": 1})
    if not tournament:
        raise HTTPException(404, "Turnier nicht gefunden")
    regs = await db.registrations.find({"tournament_id": tournament_id, "checked_in": False}, {"_id": 0}).to_list(800)
    sent = 0
    failed = 0
    for reg in regs:
        user_id = str(reg.get("user_id", "")).strip()
        if not user_id:
            continue
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "username": 1})
        email = normalize_email((user_doc or {}).get("email", ""))
        if not email:
            continue
        ok = await send_email_notification(
            email,
            f"ARENA Erinnerung: Check-in für {tournament.get('name', 'Turnier')}",
            f"Hallo {(user_doc or {}).get('username', 'Spieler')}, bitte checke für das Turnier '{tournament.get('name', 'Turnier')}' ein.",
        )
        if ok:
            sent += 1
        else:
            failed += 1
    return {"status": "ok", "tournament_id": tournament_id, "sent": sent, "failed": failed}

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
