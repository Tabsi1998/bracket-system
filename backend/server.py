from fastapi import FastAPI, APIRouter, HTTPException, Request, Body
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure
import os
import asyncio
import logging
import math
import re
import json
import base64
import ssl
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

STRUCTURED_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
STRUCTURED_LOG_MAX_DEPTH = 4
STRUCTURED_LOG_MAX_ITEMS = 20
STRUCTURED_LOG_MAX_STRING_LEN = 600

MATCHDAY_STATUS_LABELS = {
    "pending": "Geplant",
    "in_progress": "Aktiv",
    "completed": "Abgeschlossen",
}

SEASON_STATUS_LABELS = {
    "pending": "Geplant",
    "in_progress": "Aktiv",
    "completed": "Abgeschlossen",
}

TOURNAMENT_TO_MATCHDAY_STATUS = {
    "registration": "pending",
    "checkin": "pending",
    "live": "in_progress",
    "completed": "completed",
}

def _sanitize_log_value(value: Any, depth: int = 0) -> Any:
    if depth >= STRUCTURED_LOG_MAX_DEPTH:
        return "<max-depth>"
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > STRUCTURED_LOG_MAX_STRING_LEN:
            return f"{value[:STRUCTURED_LOG_MAX_STRING_LEN]}...[truncated]"
        return value
    if isinstance(value, dict):
        out = {}
        for idx, (k, v) in enumerate(value.items()):
            if idx >= STRUCTURED_LOG_MAX_ITEMS:
                out["__truncated__"] = True
                break
            out[str(k)] = _sanitize_log_value(v, depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        out_list = []
        for idx, item in enumerate(value):
            if idx >= STRUCTURED_LOG_MAX_ITEMS:
                out_list.append("<truncated>")
                break
            out_list.append(_sanitize_log_value(item, depth + 1))
        return out_list
    return str(value)

def log_structured(level: str, event: str, message: str, context: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
    level_name = str(level or "INFO").strip().upper()
    payload = {
        "event": str(event or "unknown_event").strip() or "unknown_event",
        "message": str(message or "").strip(),
    }
    if context:
        payload["context"] = _sanitize_log_value(context)
    try:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    except Exception:
        line = str(payload)
    logger.log(STRUCTURED_LOG_LEVELS.get(level_name, logging.INFO), line, exc_info=exc_info)

def log_debug(event: str, message: str, **context: Any) -> None:
    log_structured("DEBUG", event, message, context=context or None)

def log_info(event: str, message: str, **context: Any) -> None:
    log_structured("INFO", event, message, context=context or None)

def log_warning(event: str, message: str, **context: Any) -> None:
    log_structured("WARNING", event, message, context=context or None)

def log_error(event: str, message: str, exc_info: bool = False, **context: Any) -> None:
    log_structured("ERROR", event, message, context=context or None, exc_info=exc_info)

def log_critical(event: str, message: str, exc_info: bool = False, **context: Any) -> None:
    log_structured("CRITICAL", event, message, context=context or None, exc_info=exc_info)

# --- Pydantic Models ---

class GameMap(BaseModel):
    id: str = ""
    name: str
    image_url: str = ""
    game_modes: List[str] = Field(default_factory=list)  # Which modes this map supports

class GameMode(BaseModel):
    name: str
    team_size: int
    description: str = ""
    settings_template: Dict[str, Any] = Field(default_factory=dict)
    default_map_pool: List[str] = Field(default_factory=list)  # Default maps for this mode
    best_of_options: List[int] = Field(default_factory=lambda: [1, 3, 5])
    map_ban_enabled: bool = True
    map_vote_enabled: bool = True
    special_rules: str = ""

class SubGame(BaseModel):
    id: str = ""
    name: str  # e.g. "Black Ops 6", "Black Ops Cold War"
    short_name: str = ""
    release_year: int = 0
    maps: List[GameMap] = Field(default_factory=list)
    active: bool = True

class GameCreate(BaseModel):
    name: str
    short_name: str = ""
    category: str = "other"
    image_url: str = ""
    modes: List[GameMode] = Field(default_factory=list)
    sub_games: List[SubGame] = Field(default_factory=list)  # e.g. Black Ops 6, MW3, etc.
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
    default_match_day: str = "wednesday"  # Default day if no team schedules: monday, tuesday, etc.
    default_match_hour: int = 19  # Default hour (0-23) for auto-scheduling
    matchday_interval_days: int = 7
    matchday_window_days: int = 7
    auto_schedule_on_window_end: bool = True  # Auto-assign default time when window ends
    points_win: int = 3
    points_draw: int = 1
    points_loss: int = 0
    tiebreakers: List[str] = Field(default_factory=lambda: ["points", "score_diff", "score_for", "team_name"])

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
    matchday_interval_days: Optional[int] = None
    matchday_window_days: Optional[int] = None
    default_match_day: Optional[str] = None
    default_match_hour: Optional[int] = None
    auto_schedule_on_window_end: Optional[bool] = None
    points_win: Optional[int] = None
    points_draw: Optional[int] = None
    points_loss: Optional[int] = None
    tiebreakers: Optional[List[str]] = None

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

class MatchSetupSubmission(BaseModel):
    settings: Dict[str, Any] = Field(default_factory=dict)
    note: str = ""

class MatchSetupResolve(BaseModel):
    settings: Dict[str, Any] = Field(default_factory=dict)
    note: str = ""

class AdminPayPalValidateRequest(BaseModel):
    force_live: bool = True

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

class FAQEntry(BaseModel):
    id: Optional[str] = None
    question: str
    answer: str

class FAQUpdate(BaseModel):
    items: List[FAQEntry] = Field(default_factory=list)

# --- JWT Auth ---

JWT_SECRET = str(os.environ.get("JWT_SECRET", "") or "").strip()
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET fehlt oder ist zu kurz (min. 32 Zeichen). Bitte backend/.env setzen.")
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

DEFAULT_TIEBREAKERS = ["points", "score_diff", "score_for", "team_name"]
ALLOWED_TIEBREAKERS = {
    "points",
    "score_diff",
    "score_for",
    "wins",
    "draws",
    "losses",
    "played",
    "team_name",
}

try:
    PAYMENT_RESERVATION_MINUTES = max(5, int(str(os.environ.get("PAYMENT_RESERVATION_MINUTES", "30")).strip() or "30"))
except ValueError:
    PAYMENT_RESERVATION_MINUTES = 30

FAQ_SETTINGS_KEY = "faq_items_json"
DEFAULT_FAQ_ITEMS: List[Dict[str, str]] = [
    {
        "id": "faq-overview",
        "question": "Was ist ARENA und wie starte ich?",
        "answer": "ARENA ist ein eSports-Turniersystem für Teams und Solo-Spieler. Starte mit Registrierung/Login, erstelle oder joine ein Team (bei Team-Turnieren ein Sub-Team), wähle ein Turnier und registriere dich.",
    },
    {
        "id": "faq-team-vs-solo",
        "question": "Wann nutze ich Team und wann Solo?",
        "answer": "Bei Turnieren mit participant_mode=team registrierst du ein Sub-Team. Bei participant_mode=solo meldet sich dein Benutzer direkt als Teilnehmer an, ohne Team-Auswahl.",
    },
    {
        "id": "faq-subteams",
        "question": "Warum sind Sub-Teams wichtig?",
        "answer": "Main-Teams sind die organisatorische Basis. Für Turniere werden Sub-Teams verwendet. Sub-Teams erben bei leeren Feldern Logo/Banner/Tag vom Main-Team.",
    },
    {
        "id": "faq-registration",
        "question": "Wie läuft die Turnierregistrierung ab?",
        "answer": "Öffne das Turnier, klicke auf Registrieren und wähle dein passendes Sub-Team (oder solo). Nach erfolgreicher Registrierung siehst du deinen Status in der Teilnehmerliste.",
    },
    {
        "id": "faq-payments",
        "question": "Wie funktionieren Zahlungen und Retry?",
        "answer": "Bei kostenpflichtigen Turnieren wird ein Checkout (Stripe/PayPal) gestartet. Wenn die Zahlung fehlschlägt, bleibt die Registrierung als pending/failed sichtbar und du kannst den Checkout erneut starten (Retry).",
    },
    {
        "id": "faq-checkin",
        "question": "Warum kann ich nicht einchecken?",
        "answer": "Check-in ist nur im Check-in-Zeitfenster möglich. Bei kostenpflichtigen Turnieren muss payment_status=paid sein, sonst wird der Check-in blockiert.",
    },
    {
        "id": "faq-match-hub",
        "question": "Was mache ich im Match-Hub?",
        "answer": "Im Match-Hub kannst du Termine vorschlagen/akzeptieren, Match-Setup bestätigen, Kommentare schreiben und Ergebnisse einreichen. Bei Konflikten kann ein Admin final entscheiden.",
    },
    {
        "id": "faq-admin",
        "question": "Was kann ein Admin verwalten?",
        "answer": "Admins verwalten Benutzerrollen, Teams, Spiele, Turniere, SMTP/Payment-Settings, PayPal-Validierung und können Konflikte bei Setups/Scores auflösen.",
    },
]

CATEGORY_SETTINGS_TEMPLATE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "fps": {
        "maps": [],
        "map_order": "veto",
        "region": "",
        "platform": "",
        "server_notes": "",
        "ruleset": "",
    },
    "sports": {
        "home_away": True,
        "platform": "",
        "match_rules": "",
    },
    "fighting": {
        "stage_rules": "",
        "character_rules": "",
        "bo_default": 3,
    },
    "racing": {
        "tracks": [],
        "race_count": 3,
        "points_table": "",
    },
    "moba": {
        "server": "",
        "patch": "",
        "side_choice": "coin_toss",
    },
    "strategy": {
        "server": "",
        "patch": "",
        "map_pool": [],
        "side_choice": "coin_toss",
    },
    "battle_royale": {
        "lobby_settings": "",
        "scoring_rules": "",
        "admin_review_required": True,
    },
    "other": {
        "ruleset": "",
        "notes": "",
    },
}

GAME_SETTINGS_TEMPLATE_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "call of duty": {
        "maps": [],
        "map_order": "veto",
        "modes": ["S&D", "Hardpoint", "Control"],
        "veto_format": "A-B-B-A",
        "platform_crossplay_required": True,
    },
    "ea fc (fifa)": {
        "home_away": True,
        "halves_minutes": 6,
        "injuries": False,
        "extra_time": True,
        "penalties": True,
    },
    "mario kart": {
        "tracks": [],
        "race_count": 8,
        "items": "standard",
        "cpu": "none",
    },
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def deep_clone_template(value: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(json.dumps(value or {}))
    except Exception:
        return {}

def normalize_tiebreakers(values: Optional[List[str]]) -> List[str]:
    if not values:
        return list(DEFAULT_TIEBREAKERS)
    out: List[str] = []
    for item in values:
        key = str(item or "").strip().lower()
        if key and key in ALLOWED_TIEBREAKERS and key not in out:
            out.append(key)
    return out or list(DEFAULT_TIEBREAKERS)

def parse_int_or_default(value: Any, default: int) -> int:
    if value is None:
        return int(default)
    try:
        text = str(value).strip()
        if text == "":
            return int(default)
        return int(text)
    except Exception:
        return int(default)

def get_tournament_scoring_config(tournament: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "points_win": max(0, parse_int_or_default(tournament.get("points_win"), 3)),
        "points_draw": max(0, parse_int_or_default(tournament.get("points_draw"), 1)),
        "points_loss": max(0, parse_int_or_default(tournament.get("points_loss"), 0)),
        "tiebreakers": normalize_tiebreakers(tournament.get("tiebreakers")),
    }

def get_tournament_matchday_config(tournament: Dict[str, Any]) -> Dict[str, int]:
    return {
        "interval_days": max(1, parse_int_or_default(tournament.get("matchday_interval_days"), 7)),
        "window_days": max(1, parse_int_or_default(tournament.get("matchday_window_days"), 7)),
    }

def hydrate_tournament_defaults(tournament: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(tournament, dict):
        return tournament
    tournament["matchday_interval_days"] = max(1, parse_int_or_default(tournament.get("matchday_interval_days"), 7))
    tournament["matchday_window_days"] = max(1, parse_int_or_default(tournament.get("matchday_window_days"), 7))
    tournament["points_win"] = max(0, parse_int_or_default(tournament.get("points_win"), 3))
    tournament["points_draw"] = max(0, parse_int_or_default(tournament.get("points_draw"), 1))
    tournament["points_loss"] = max(0, parse_int_or_default(tournament.get("points_loss"), 0))
    tournament["tiebreakers"] = normalize_tiebreakers(tournament.get("tiebreakers"))
    return tournament

def build_game_settings_template(category: str, game_name: str) -> Dict[str, Any]:
    category_key = str(category or "other").strip().lower() or "other"
    game_key = str(game_name or "").strip().lower()

    base = deep_clone_template(CATEGORY_SETTINGS_TEMPLATE_DEFAULTS.get(category_key, CATEGORY_SETTINGS_TEMPLATE_DEFAULTS["other"]))
    override = deep_clone_template(GAME_SETTINGS_TEMPLATE_OVERRIDES.get(game_key, {}))
    base.update(override)
    return base

def apply_mode_templates_to_game(game_doc: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    if not isinstance(game_doc, dict):
        return game_doc, False
    changed = False
    modes_out = []
    category = str(game_doc.get("category", "other") or "other")
    game_name = str(game_doc.get("name", "") or "")
    for mode in game_doc.get("modes", []) or []:
        mode_doc = dict(mode or {})
        if not isinstance(mode_doc.get("settings_template"), dict) or not mode_doc.get("settings_template"):
            mode_doc["settings_template"] = build_game_settings_template(category, game_name)
            changed = True
        modes_out.append(mode_doc)
    if modes_out != (game_doc.get("modes") or []):
        game_doc["modes"] = modes_out
    return game_doc, changed

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
        log_warning(
            "auth.required.denied",
            "Request blocked because user is not authenticated",
            path=str(request.url.path),
            client_ip=get_request_client_ip(request),
        )
        raise HTTPException(401, "Nicht eingeloggt")
    return user

async def require_admin(request: Request):
    user = await require_auth(request)
    if user.get("role") != "admin":
        log_warning(
            "auth.admin.denied",
            "Admin endpoint access denied",
            path=str(request.url.path),
            user_id=str(user.get("id", "") or ""),
            role=str(user.get("role", "") or ""),
        )
        raise HTTPException(403, "Admin-Rechte erforderlich")
    return user

def generate_join_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

async def send_email_notification(to_email: str, subject: str, body_text: str):
    ok, _detail = await send_email_notification_detailed(to_email, subject, body_text)
    return ok

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

async def get_setting_value_with_env_fallback(
    setting_key: str,
    default: str = "",
    env_keys: Optional[List[str]] = None,
) -> str:
    for env_key in (env_keys or []):
        env_value = str(os.environ.get(env_key, "") or "").strip()
        if env_value:
            return env_value
    return await get_admin_setting_value(setting_key, default)

async def get_smtp_config_detailed() -> Tuple[Optional[Dict[str, Any]], str]:
    host = await get_setting_value_with_env_fallback("smtp_host", env_keys=["SMTP_HOST"])
    port_raw = await get_setting_value_with_env_fallback("smtp_port", "587", env_keys=["SMTP_PORT"])
    user = await get_setting_value_with_env_fallback("smtp_user", env_keys=["SMTP_USER", "SMTP_USERNAME"])
    password = await get_setting_value_with_env_fallback("smtp_password", env_keys=["SMTP_PASSWORD"])

    from_name = await get_setting_value_with_env_fallback("smtp_from_name", "ARENA eSports", env_keys=["SMTP_FROM_NAME"])
    default_from_email = user if is_valid_email(user) else ""
    from_email = await get_setting_value_with_env_fallback("smtp_from_email", default_from_email, env_keys=["SMTP_FROM_EMAIL"])
    reply_to = await get_setting_value_with_env_fallback("smtp_reply_to", "", env_keys=["SMTP_REPLY_TO"])
    use_starttls = to_bool(
        await get_setting_value_with_env_fallback("smtp_use_starttls", "true", env_keys=["SMTP_USE_STARTTLS"]),
        default=True,
    )
    use_ssl = to_bool(
        await get_setting_value_with_env_fallback("smtp_use_ssl", "false", env_keys=["SMTP_USE_SSL"]),
        default=False,
    )

    if not host:
        return None, "SMTP Host fehlt (smtp_host oder SMTP_HOST)."
    if not port_raw:
        return None, "SMTP Port fehlt (smtp_port oder SMTP_PORT)."
    try:
        port = int(str(port_raw).strip())
    except ValueError:
        return None, f"SMTP Port ist ungültig: {port_raw}"
    if port < 1 or port > 65535:
        return None, f"SMTP Port außerhalb des gültigen Bereichs: {port}"
    if user and not password:
        return None, "SMTP Benutzer ist gesetzt, aber smtp_password fehlt."

    from_email = normalize_email(from_email)
    if not from_email:
        return None, "SMTP Absender-Adresse fehlt (smtp_from_email oder SMTP_FROM_EMAIL)."
    if not is_valid_email(from_email):
        return None, f"SMTP Absender-Adresse ungültig: {from_email}"

    reply_to = normalize_email(reply_to)
    if reply_to and not is_valid_email(reply_to):
        return None, f"SMTP Reply-To ungültig: {reply_to}"

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_name": str(from_name or "ARENA eSports").strip() or "ARENA eSports",
        "from_email": from_email,
        "reply_to": reply_to,
        "use_starttls": use_starttls and not use_ssl,
        "use_ssl": use_ssl,
    }, ""

async def get_smtp_config() -> Optional[Dict[str, Any]]:
    config, _detail = await get_smtp_config_detailed()
    return config

async def send_email_notification_detailed(to_email: str, subject: str, body_text: str) -> Tuple[bool, str]:
    """Send email with detailed error message for diagnostics/admin test endpoint."""
    import smtplib
    from email.mime.text import MIMEText
    from email.utils import formataddr

    smtp_config, config_error = await get_smtp_config_detailed()
    if not smtp_config:
        detail = config_error or "SMTP Konfiguration unvollständig."
        log_warning("smtp.send.skipped", "Skipping email send due to invalid SMTP config", detail=detail)
        return False, detail

    normalized_to = normalize_email(to_email)
    if not is_valid_email(normalized_to):
        return False, f"Empfänger-Adresse ungültig: {normalized_to}"

    msg = MIMEText(body_text, "plain", "utf-8")
    msg["Subject"] = str(subject or "").strip() or "ARENA Benachrichtigung"
    msg["From"] = formataddr((smtp_config["from_name"], smtp_config["from_email"]))
    msg["To"] = normalized_to
    if smtp_config["reply_to"]:
        msg["Reply-To"] = smtp_config["reply_to"]

    try:
        if smtp_config["use_ssl"]:
            with smtplib.SMTP_SSL(smtp_config["host"], smtp_config["port"], timeout=15) as server:
                server.ehlo()
                if smtp_config["user"]:
                    server.login(smtp_config["user"], smtp_config["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=15) as server:
                server.ehlo()
                if smtp_config["use_starttls"]:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                if smtp_config["user"]:
                    server.login(smtp_config["user"], smtp_config["password"])
                server.send_message(msg)
        log_info(
            "smtp.send.success",
            "Email sent successfully",
            to=normalized_to,
            host=smtp_config["host"],
            port=smtp_config["port"],
            ssl=bool(smtp_config["use_ssl"]),
            starttls=bool(smtp_config["use_starttls"]),
        )
        return True, "E-Mail erfolgreich versendet."
    except smtplib.SMTPAuthenticationError as e:
        decoded = ""
        try:
            decoded = (e.smtp_error or b"").decode("utf-8", errors="ignore").strip()
        except Exception:
            decoded = ""
        detail = f"SMTP Auth fehlgeschlagen ({e.smtp_code}). {decoded}".strip()
    except smtplib.SMTPConnectError as e:
        detail = f"SMTP Verbindung fehlgeschlagen ({e.smtp_code}): {e.smtp_error}"
    except smtplib.SMTPServerDisconnected:
        detail = "SMTP Server hat die Verbindung unerwartet geschlossen."
    except smtplib.SMTPException as e:
        detail = f"SMTP Fehler: {e}"
    except Exception as e:
        detail = f"SMTP Fehler: {e}"

    log_warning(
        "smtp.send.failed",
        "Email send failed",
        to=normalized_to,
        host=smtp_config.get("host", ""),
        port=smtp_config.get("port", 0),
        detail=detail,
    )
    return False, detail

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
        log_debug("payments.provider.resolve.explicit", "Using explicitly requested payment provider", provider=provider)
        return provider
    setting = await db.admin_settings.find_one({"key": "payment_provider"}, {"_id": 0, "value": 1})
    setting_provider_raw = str((setting or {}).get("value", ""))
    try:
        setting_provider = normalize_payment_provider(setting_provider_raw)
    except HTTPException:
        logger.warning(f"Ignoring invalid payment_provider setting: {setting_provider_raw}")
        log_warning("payments.provider.resolve.invalid_setting", "Ignoring invalid payment provider setting", value=setting_provider_raw)
        setting_provider = "auto"
    if setting_provider in {"stripe", "paypal"}:
        log_debug("payments.provider.resolve.setting", "Using payment provider from admin settings", provider=setting_provider)
        return setting_provider
    paypal_client_id = await get_paypal_client_id()
    paypal_secret = await get_paypal_secret()
    if paypal_client_id and paypal_secret:
        log_debug("payments.provider.resolve.auto", "Auto-selected PayPal because credentials are configured")
        return "paypal"
    log_debug("payments.provider.resolve.auto", "Auto-selected Stripe because no PayPal credentials were found")
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

async def save_admin_setting_value(key: str, value: str) -> None:
    await db.admin_settings.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value, "updated_at": now_iso()}},
        upsert=True,
    )

def normalize_faq_items(items_raw: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen_questions: Set[str] = set()
    if not isinstance(items_raw, list):
        return out

    for item in items_raw:
        if not isinstance(item, dict):
            continue
        question = normalize_optional_text(item.get("question"), max_len=260)
        answer = normalize_optional_text(item.get("answer"), max_len=7000)
        if not question or not answer:
            continue
        key = question.lower()
        if key in seen_questions:
            continue
        seen_questions.add(key)
        item_id = normalize_optional_text(item.get("id"), max_len=100) or str(uuid.uuid4())
        out.append({"id": item_id, "question": question, "answer": answer})
        if len(out) >= 120:
            break
    return out

def clone_default_faq_items() -> List[Dict[str, str]]:
    return [dict(item) for item in DEFAULT_FAQ_ITEMS]

async def get_faq_payload() -> Dict[str, Any]:
    setting = await db.admin_settings.find_one({"key": FAQ_SETTINGS_KEY}, {"_id": 0, "value": 1, "updated_at": 1})
    updated_at = str((setting or {}).get("updated_at", "") or "")
    raw_value = str((setting or {}).get("value", "") or "").strip()

    custom_items: List[Dict[str, str]] = []
    if raw_value:
        try:
            parsed = json.loads(raw_value)
        except Exception:
            parsed = []
        custom_items = normalize_faq_items(parsed)

    if custom_items:
        return {"items": custom_items, "source": "custom", "updated_at": updated_at}
    return {"items": clone_default_faq_items(), "source": "default", "updated_at": updated_at}

async def validate_paypal_configuration(force_live: bool = True, persist_result: bool = True) -> Dict[str, Any]:
    client_id = await get_paypal_client_id()
    secret = await get_paypal_secret()
    base_url = await get_paypal_base_url()
    mode = "live" if "api-m.paypal.com" in base_url and "sandbox" not in base_url else "sandbox"
    log_info(
        "paypal.validate.start",
        "Validating PayPal configuration",
        force_live=bool(force_live),
        persist_result=bool(persist_result),
        mode=mode,
        configured=bool(client_id and secret),
    )
    result = {
        "configured": bool(client_id and secret),
        "valid": False,
        "mode": mode,
        "base_url": base_url,
        "checked_at": now_iso(),
        "detail": "",
    }

    if not client_id or not secret:
        result["detail"] = "PayPal Credentials fehlen (Client ID / Secret)."
    else:
        try:
            if force_live:
                await get_paypal_access_token()
            result["valid"] = True
            result["detail"] = "PayPal Credentials sind gültig."
        except HTTPException as e:
            result["detail"] = str(e.detail or "PayPal Validierung fehlgeschlagen")
            log_warning("paypal.validate.http_error", "PayPal validation returned an HTTP exception", detail=result["detail"], mode=mode)
        except Exception as e:
            result["detail"] = f"PayPal Validierung fehlgeschlagen: {e}"
            log_critical(
                "paypal.validate.unexpected_exception",
                "Unexpected exception during PayPal validation",
                exc_info=True,
                error=str(e),
                mode=mode,
            )

    if persist_result:
        await save_admin_setting_value("paypal_last_validation_status", "valid" if result["valid"] else "invalid")
        await save_admin_setting_value("paypal_last_validation_detail", result["detail"])
        await save_admin_setting_value("paypal_last_validation_mode", result["mode"])
        await save_admin_setting_value("paypal_last_validation_checked_at", result["checked_at"])
    if result["valid"]:
        log_info("paypal.validate.success", "PayPal configuration validation succeeded", mode=result["mode"])
    else:
        log_warning("paypal.validate.failed", "PayPal configuration validation failed", mode=result["mode"], detail=result["detail"])
    return result

async def get_payment_provider_status(force_paypal_check: bool = False) -> Dict[str, Any]:
    stripe_key = await get_stripe_api_key()
    paypal_client_id = await get_paypal_client_id()
    paypal_secret = await get_paypal_secret()
    paypal_base_url = await get_paypal_base_url()
    paypal_mode = "live" if "api-m.paypal.com" in paypal_base_url and "sandbox" not in paypal_base_url else "sandbox"
    paypal_status = {
        "configured": bool(paypal_client_id and paypal_secret),
        "mode": paypal_mode,
        "valid": False,
        "last_status": await get_admin_setting_value("paypal_last_validation_status", ""),
        "last_detail": await get_admin_setting_value("paypal_last_validation_detail", ""),
        "last_checked_at": await get_admin_setting_value("paypal_last_validation_checked_at", ""),
    }
    if force_paypal_check and paypal_status["configured"]:
        live = await validate_paypal_configuration(force_live=True, persist_result=True)
        paypal_status["valid"] = bool(live.get("valid"))
        paypal_status["last_status"] = "valid" if live.get("valid") else "invalid"
        paypal_status["last_detail"] = str(live.get("detail", "") or "")
        paypal_status["last_checked_at"] = str(live.get("checked_at", "") or "")
    else:
        paypal_status["valid"] = str(paypal_status["last_status"]).lower() == "valid"
    return {
        "stripe": {"configured": bool(stripe_key)},
        "paypal": paypal_status,
    }

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
    log_debug("paypal.api.request.start", "Calling PayPal API", method=method.upper(), path=path)
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
        response = await asyncio.to_thread(_do_request)
        log_debug("paypal.api.request.success", "PayPal API call succeeded", method=method.upper(), path=path)
        return response
    except urllib.error.HTTPError as http_error:
        body = http_error.read().decode("utf-8", errors="ignore") if http_error else ""
        logger.warning(f"PayPal API error {http_error.code}: {body}")
        log_warning(
            "paypal.api.request.http_error",
            "PayPal API returned an HTTP error",
            method=method.upper(),
            path=path,
            status_code=int(http_error.code),
            response_body=body[:500],
        )
        detail = "PayPal API Fehler"
        try:
            parsed = json.loads(body or "{}")
            err_code = str((parsed or {}).get("error", "") or "").strip()
            err_message = str((parsed or {}).get("message", "") or "").strip()
            err_description = str((parsed or {}).get("error_description", "") or "").strip()
            if err_code == "invalid_client":
                detail = "PayPal Credentials ungültig oder Sandbox/Live Modus passt nicht."
            elif err_message:
                detail = err_message
            if err_description:
                detail = f"{detail} ({err_description})"
        except Exception:
            pass
        raise HTTPException(400, detail)
    except Exception as e:
        logger.warning(f"PayPal request failed: {e}")
        log_error("paypal.api.request.error", "PayPal API call failed due to connection or parsing error", method=method.upper(), path=path, error=str(e))
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
        log_error("paypal.token.missing", "PayPal access token response did not include access_token")
        raise HTTPException(500, "PayPal Token konnte nicht erzeugt werden")
    log_debug("paypal.token.success", "PayPal access token retrieved successfully")
    return access_token

async def create_paypal_order(amount: float, currency: str, tournament_name: str, return_url: str, cancel_url: str) -> Dict:
    log_info(
        "paypal.order.create.start",
        "Creating PayPal order",
        amount=float(amount or 0),
        currency=str(currency or "").upper(),
        tournament_name=str(tournament_name or ""),
    )
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
    order = await paypal_api_request("POST", "/v2/checkout/orders", payload=payload, bearer_token=token)
    log_info(
        "paypal.order.create.success",
        "PayPal order created",
        order_id=str((order or {}).get("id", "") or ""),
        status=str((order or {}).get("status", "") or ""),
    )
    return order

async def get_paypal_order(order_id: str) -> Dict:
    log_debug("paypal.order.fetch.start", "Fetching PayPal order", order_id=str(order_id or ""))
    token = await get_paypal_access_token()
    order = await paypal_api_request("GET", f"/v2/checkout/orders/{order_id}", payload=None, bearer_token=token)
    log_debug("paypal.order.fetch.success", "Fetched PayPal order", order_id=str(order_id or ""), status=str((order or {}).get("status", "") or ""))
    return order

async def capture_paypal_order(order_id: str) -> Dict:
    log_info("paypal.order.capture.start", "Capturing PayPal order", order_id=str(order_id or ""))
    token = await get_paypal_access_token()
    capture = await paypal_api_request("POST", f"/v2/checkout/orders/{order_id}/capture", payload={}, bearer_token=token)
    log_info(
        "paypal.order.capture.success",
        "PayPal order capture completed",
        order_id=str(order_id or ""),
        status=str((capture or {}).get("status", "") or ""),
    )
    return capture

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
        doc["payment_expires_at"] = reg.get("payment_expires_at", "")

    return doc

# --- Seed Data ---

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
            game_payload, _ = apply_mode_templates_to_game(dict(game_data))
            doc = {
                "id": str(uuid.uuid4()),
                "is_custom": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **game_payload,
            }
            await db.games.insert_one(doc)
        logger.info(f"Seeded {len(SEED_GAMES)} games")

# --- Auth Endpoints ---

@api_router.post("/auth/register")
async def register_user(body: UserRegister):
    email = normalize_email(body.email)
    log_info("auth.register.start", "User registration requested", email=email)
    if not email:
        log_warning("auth.register.invalid_email", "Registration blocked because email is missing")
        raise HTTPException(400, "E-Mail erforderlich")
    if not is_valid_email(email):
        log_warning("auth.register.invalid_email", "Registration blocked because email format is invalid", email=email)
        raise HTTPException(400, "Ungültige E-Mail")
    if await db.users.find_one({"email": exact_ci_regex(email, allow_outer_whitespace=True)}):
        log_warning("auth.register.duplicate_email", "Registration blocked because email already exists", email=email)
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
    log_info("auth.register.success", "User registration succeeded", user_id=user_doc["id"], email=email)
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
    log_info("auth.login.start", "Login requested", email=email, client_ip=get_request_client_ip(request))
    if not email:
        log_warning("auth.login.invalid_email", "Login blocked because email is missing")
        raise HTTPException(400, "E-Mail erforderlich")

    user = await db.users.find_one({"email": exact_ci_regex(email, allow_outer_whitespace=True)})
    if not user:
        log_warning("auth.login.unknown_user", "Login failed because user was not found", email=email)
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
        log_warning(
            "auth.login.invalid_credentials",
            "Login failed because credentials are invalid",
            email=email,
            user_id=str(user.get("id", "") or ""),
        )
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
    log_info(
        "auth.login.success",
        "Login succeeded",
        user_id=str(user_id or ""),
        email=email,
        role=str(role or ""),
        client_ip=client_ip,
    )
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

    admin_password = str(os.environ.get("ADMIN_PASSWORD", "") or "").strip()
    if not admin_password:
        logger.warning("ADMIN_PASSWORD is empty; startup will not create/reset admin passwords without explicit value.")

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
            if not admin_password:
                raise RuntimeError("ADMIN_FORCE_PASSWORD_RESET=true benötigt ein gesetztes ADMIN_PASSWORD.")
            update_doc["password_hash"] = hash_password(admin_password)
        elif not existing_hash:
            if legacy_password:
                update_doc["password_hash"] = hash_password(legacy_password)
            elif admin_password:
                update_doc["password_hash"] = hash_password(admin_password)
            else:
                raise RuntimeError(
                    "Admin-User ohne Passwort-Hash erkannt. Setze ADMIN_PASSWORD oder führe ./update.sh --admin-reset aus."
                )
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

    if not admin_password:
        raise RuntimeError(
            "ADMIN_PASSWORD fehlt für die initiale Admin-Erstellung. Setze ADMIN_PASSWORD in backend/.env."
        )

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

# --- Team Endpoints ---

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

# --- Game Endpoints ---

@api_router.get("/games")
async def list_games(category: Optional[str] = None):
    query = {}
    if category:
        query["category"] = category
    games = await db.games.find(query, {"_id": 0}).to_list(100)
    for game in games:
        patched, changed = apply_mode_templates_to_game(game)
        if changed:
            await db.games.update_one({"id": game.get("id")}, {"$set": {"modes": patched.get("modes", []), "updated_at": now_iso()}})
    return games

@api_router.post("/games")
async def create_game(request: Request, body: GameCreate):
    await require_admin(request)
    payload = body.model_dump()
    payload, _ = apply_mode_templates_to_game(payload)
    doc = {
        "id": str(uuid.uuid4()),
        "is_custom": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    await db.games.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/games/{game_id}")
async def get_game(game_id: str):
    game = await db.games.find_one({"id": game_id}, {"_id": 0})
    if not game:
        raise HTTPException(404, "Game not found")
    game, changed = apply_mode_templates_to_game(game)
    if changed:
        await db.games.update_one({"id": game_id}, {"$set": {"modes": game.get("modes", []), "updated_at": now_iso()}})
    return game

@api_router.put("/games/{game_id}")
async def update_game(request: Request, game_id: str, body: GameCreate):
    await require_admin(request)
    payload = body.model_dump()
    payload, _ = apply_mode_templates_to_game(payload)
    payload["updated_at"] = now_iso()
    result = await db.games.update_one({"id": game_id}, {"$set": payload})
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

# --- Tournament Endpoints ---

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
        hydrate_tournament_defaults(t)
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
        "matchday_interval_days": max(1, int(body.matchday_interval_days or 7)),
        "matchday_window_days": max(1, int(body.matchday_window_days or 7)),
        "points_win": max(0, int(body.points_win if body.points_win is not None else 3)),
        "points_draw": max(0, int(body.points_draw if body.points_draw is not None else 1)),
        "points_loss": max(0, int(body.points_loss if body.points_loss is not None else 0)),
        "tiebreakers": normalize_tiebreakers(body.tiebreakers),
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
    hydrate_tournament_defaults(t)
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
    if "matchday_interval_days" in update_data:
        update_data["matchday_interval_days"] = max(1, int(update_data["matchday_interval_days"] or 7))
    if "matchday_window_days" in update_data:
        update_data["matchday_window_days"] = max(1, int(update_data["matchday_window_days"] or 7))
    if "points_win" in update_data:
        update_data["points_win"] = max(0, int(update_data["points_win"] or 0))
    if "points_draw" in update_data:
        update_data["points_draw"] = max(0, int(update_data["points_draw"] or 0))
    if "points_loss" in update_data:
        update_data["points_loss"] = max(0, int(update_data["points_loss"] or 0))
    if "tiebreakers" in update_data:
        update_data["tiebreakers"] = normalize_tiebreakers(update_data["tiebreakers"])

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

# --- Registration Endpoints ---

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

@api_router.get("/tournaments/{tournament_id}/my-registrations")
async def list_my_registrations(request: Request, tournament_id: str):
    user = await require_auth(request)
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0, "id": 1, "entry_fee": 1, "currency": 1})
    if not tournament:
        raise HTTPException(404, "Tournament not found")

    regs = await db.registrations.find({"tournament_id": tournament_id, "user_id": user["id"]}, {"_id": 0}).to_list(200)
    payload = []
    for reg in regs:
        row = sanitize_registration(reg, include_private=True, include_player_emails=False)
        payment_status = str(reg.get("payment_status", "free") or "free").strip().lower()
        row["entry_fee"] = float(tournament.get("entry_fee", 0) or 0)
        row["currency"] = str(tournament.get("currency", "usd") or "usd").lower()
        row["can_retry_payment"] = row["entry_fee"] > 0 and payment_status != "paid"
        payload.append(row)
    return payload

@api_router.post("/tournaments/{tournament_id}/register")
async def register_for_tournament(request: Request, tournament_id: str, body: RegistrationCreate):
    user = await require_auth(request)
    log_info(
        "tournament.registration.start",
        "Tournament registration requested",
        tournament_id=tournament_id,
        user_id=str(user.get("id", "") or ""),
    )
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        log_warning("tournament.registration.not_found", "Registration blocked because tournament does not exist", tournament_id=tournament_id)
        raise HTTPException(404, "Tournament not found")
    if t["status"] not in ("registration", "checkin"):
        log_warning(
            "tournament.registration.closed",
            "Registration blocked because tournament is closed",
            tournament_id=tournament_id,
            status=str(t.get("status", "") or ""),
        )
        raise HTTPException(400, "Registration is closed")
    now_dt = datetime.now(timezone.utc)
    entry_fee = float(t.get("entry_fee", 0) or 0)
    paid_tournament = entry_fee > 0
    capacity_regs = []
    capacity_cursor = db.registrations.find(
        {"tournament_id": tournament_id},
        {"_id": 0, "id": 1, "payment_status": 1, "payment_expires_at": 1, "created_at": 1},
    )
    async for row in capacity_cursor:
        capacity_regs.append(row)

    if paid_tournament:
        expired_pending_ids = []
        for existing_reg in capacity_regs:
            if str(existing_reg.get("payment_status", "")).strip().lower() != "pending":
                continue
            if is_pending_registration_active(existing_reg, reference_time=now_dt):
                continue
            reg_id = str(existing_reg.get("id", "") or "").strip()
            if reg_id:
                expired_pending_ids.append(reg_id)
        if expired_pending_ids:
            expired_pending_set = set(expired_pending_ids)
            await db.registrations.update_many(
                {"id": {"$in": expired_pending_ids}},
                {"$set": {"payment_status": "failed", "updated_at": now_iso()}},
            )
            capacity_regs = [r for r in capacity_regs if str(r.get("id", "") or "").strip() not in expired_pending_set]

    active_reg_count = sum(
        1
        for existing_reg in capacity_regs
        if registration_counts_against_capacity(existing_reg, paid_tournament=paid_tournament, reference_time=now_dt)
    )
    if active_reg_count >= t["max_participants"]:
        log_warning(
            "tournament.registration.full",
            "Registration blocked because participant limit is reached",
            tournament_id=tournament_id,
            registered_count=active_reg_count,
            max_participants=int(t.get("max_participants", 0) or 0),
        )
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

    payment_status = "free" if entry_fee <= 0 else "pending"
    next_seed = 1
    latest_seed_row = await db.registrations.find(
        {"tournament_id": tournament_id},
        {"_id": 0, "seed": 1},
    ).sort("seed", -1).to_list(1)
    if latest_seed_row:
        next_seed = parse_int_or_default(latest_seed_row[0].get("seed"), 0) + 1
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
        "payment_expires_at": compute_payment_reservation_expiry_iso(now_dt) if payment_status == "pending" else "",
        "payment_session_id": None,
        "seed": next_seed,
        "created_at": now_iso(),
    }
    await db.registrations.insert_one(doc)
    log_info(
        "tournament.registration.success",
        "Tournament registration created",
        tournament_id=tournament_id,
        registration_id=str(doc.get("id", "") or ""),
        user_id=str(user.get("id", "") or ""),
        team_id=str(doc.get("team_id", "") or ""),
        participant_mode=participant_mode,
        payment_status=str(doc.get("payment_status", "") or ""),
    )
    doc.pop("_id", None)
    return doc

@api_router.get("/tournaments/{tournament_id}/standings")
async def get_tournament_standings(tournament_id: str):
    tournament = await db.tournaments.find_one(
        {"id": tournament_id},
        {
            "_id": 0,
            "id": 1,
            "bracket": 1,
            "bracket_type": 1,
            "updated_at": 1,
            "points_win": 1,
            "points_draw": 1,
            "points_loss": 1,
            "tiebreakers": 1,
        },
    )
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
    scoring = get_tournament_scoring_config(tournament)

    bracket_type = bracket.get("type", tournament.get("bracket_type", "single_elimination"))
    if bracket_type in ("round_robin", "league", "ladder_system", "king_of_the_hill"):
        matches = [m for rd in bracket.get("rounds", []) for m in rd.get("matches", [])]
        standings = compute_standings_for_registrations(
            regs,
            matches,
            team_map,
            points_win=scoring["points_win"],
            points_draw=scoring["points_draw"],
            points_loss=scoring["points_loss"],
            tiebreakers=scoring["tiebreakers"],
        )
        return {
            "type": bracket_type,
            "standings": standings,
            "updated_at": tournament.get("updated_at"),
            "scoring": scoring,
        }

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
            standings = compute_standings_for_registrations(
                group_regs,
                matches,
                team_map,
                points_win=scoring["points_win"],
                points_draw=scoring["points_draw"],
                points_loss=scoring["points_loss"],
                tiebreakers=scoring["tiebreakers"],
            )
            groups_payload.append({"id": group.get("id"), "name": group.get("name", ""), "standings": standings})
        return {"type": bracket_type, "groups": groups_payload, "updated_at": tournament.get("updated_at"), "scoring": scoring}

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
            standings = compute_standings_for_registrations(
                group_regs,
                matches,
                team_map,
                points_win=scoring["points_win"],
                points_draw=scoring["points_draw"],
                points_loss=scoring["points_loss"],
                tiebreakers=scoring["tiebreakers"],
            )
            groups_payload.append({"id": group.get("id"), "name": group.get("name", ""), "standings": standings})
        playoffs = bracket.get("playoffs") or {}
        return {
            "type": bracket_type,
            "groups": groups_payload,
            "playoffs_generated": bool(bracket.get("playoffs_generated")),
            "playoffs": {"total_rounds": playoffs.get("total_rounds", 0)},
            "updated_at": tournament.get("updated_at"),
            "scoring": scoring,
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

def normalize_matchday_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in MATCHDAY_STATUS_LABELS:
        return status
    return "pending"

def matchday_status_label(value: Any) -> str:
    status = normalize_matchday_status(value)
    return MATCHDAY_STATUS_LABELS.get(status, MATCHDAY_STATUS_LABELS["pending"])

def aggregate_progress_status(values: List[str]) -> str:
    normalized = [normalize_matchday_status(v) for v in values if str(v or "").strip()]
    if normalized and all(v == "completed" for v in normalized):
        return "completed"
    if any(v in {"in_progress", "completed"} for v in normalized):
        return "in_progress"
    return "pending"

def format_date_range_label(start_iso: str, end_iso: str) -> str:
    start_dt = parse_optional_datetime(str(start_iso or ""))
    end_dt = parse_optional_datetime(str(end_iso or ""))
    if not start_dt or not end_dt:
        return ""
    return f"{start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')}"

def resolve_matchday_anchor(
    day_doc: Dict[str, Any],
    *,
    fallback_start: Optional[datetime],
    interval_days: int,
) -> datetime:
    window_start = parse_optional_datetime(str(day_doc.get("window_start", "") or ""))
    if window_start:
        return window_start
    for match in day_doc.get("matches", []) or []:
        scheduled = parse_optional_datetime(str(match.get("scheduled_for", "") or ""))
        if scheduled:
            return scheduled
    day_index = max(1, int(day_doc.get("matchday", 1) or 1))
    anchor = fallback_start or datetime(2000, 1, 1, tzinfo=timezone.utc)
    return anchor + timedelta(days=max(1, int(interval_days or 1)) * (day_index - 1))

def enrich_matchdays_with_calendar(
    tournament: Dict[str, Any],
    matchdays: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not matchdays:
        return []
    cfg = get_tournament_matchday_config(tournament or {})
    tournament_start = parse_optional_datetime(str((tournament or {}).get("start_date", "") or ""))
    fallback_start = tournament_start
    if fallback_start is None:
        anchors: List[datetime] = []
        for day in matchdays:
            window_start = parse_optional_datetime(str(day.get("window_start", "") or ""))
            if window_start:
                anchors.append(window_start)
                continue
            for match in day.get("matches", []) or []:
                scheduled = parse_optional_datetime(str(match.get("scheduled_for", "") or ""))
                if scheduled:
                    anchors.append(scheduled)
                    break
        if anchors:
            fallback_start = min(anchors)
        else:
            fallback_start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    out = []
    for day in sorted(matchdays, key=lambda x: int(x.get("matchday", 0) or 0)):
        doc = dict(day or {})
        status = normalize_matchday_status(doc.get("status"))
        anchor = resolve_matchday_anchor(
            doc,
            fallback_start=fallback_start,
            interval_days=cfg["interval_days"],
        )
        iso = anchor.isocalendar()
        week_start = anchor - timedelta(days=iso.weekday - 1)
        week_end = week_start + timedelta(days=6)
        week_id = f"{iso.year}-KW{iso.week:02d}"
        week_name = f"KW {iso.week:02d}"
        week_range_label = f"{week_start.strftime('%d.%m.%Y')} - {week_end.strftime('%d.%m.%Y')}"
        doc["status"] = status
        doc["status_label"] = matchday_status_label(status)
        doc["window_label"] = format_date_range_label(doc.get("window_start", ""), doc.get("window_end", ""))
        doc["iso_year"] = int(iso.year)
        doc["iso_week"] = int(iso.week)
        doc["week_id"] = week_id
        doc["week_name"] = week_name
        doc["week_range_start"] = week_start.isoformat()
        doc["week_range_end"] = week_end.isoformat()
        doc["week_range_label"] = week_range_label
        doc["week_label"] = f"{week_name} ({week_range_label})"
        out.append(doc)
    return out

def build_matchday_hierarchy(tournament: Dict[str, Any], matchdays: List[Dict[str, Any]]) -> Dict[str, Any]:
    enriched_days = enrich_matchdays_with_calendar(tournament, matchdays)
    if not enriched_days:
        tournament_status = TOURNAMENT_TO_MATCHDAY_STATUS.get(str((tournament or {}).get("status", "")).strip().lower(), "pending")
        empty_season = {
            "name": "Saison",
            "status": tournament_status,
            "status_label": SEASON_STATUS_LABELS.get(tournament_status, "Geplant"),
            "start": "",
            "end": "",
            "weeks": [],
        }
        return {
            "season": empty_season,
            "weeks": [],
            "summary": {"week_count": 0, "matchday_count": 0, "match_count": 0},
            "matchdays": [],
        }

    week_map: Dict[str, Dict[str, Any]] = {}
    for day in enriched_days:
        week_id = str(day.get("week_id", "") or "")
        if week_id not in week_map:
            week_map[week_id] = {
                "id": week_id,
                "name": day.get("week_name", ""),
                "iso_year": int(day.get("iso_year", 0) or 0),
                "iso_week": int(day.get("iso_week", 0) or 0),
                "range_start": str(day.get("week_range_start", "") or ""),
                "range_end": str(day.get("week_range_end", "") or ""),
                "range_label": str(day.get("week_range_label", "") or ""),
                "label": str(day.get("week_label", "") or ""),
                "status": "pending",
                "status_label": MATCHDAY_STATUS_LABELS["pending"],
                "matchdays": [],
                "matchday_count": 0,
                "total_matches": 0,
                "completed_matches": 0,
                "disputed_matches": 0,
                "scheduled_matches": 0,
            }
        week_doc = week_map[week_id]
        day_entry = dict(day)
        week_doc["matchdays"].append(day_entry)
        week_doc["matchday_count"] += 1
        week_doc["total_matches"] += int(day_entry.get("total_matches", 0) or 0)
        week_doc["completed_matches"] += int(day_entry.get("completed_matches", 0) or 0)
        week_doc["disputed_matches"] += int(day_entry.get("disputed_matches", 0) or 0)
        week_doc["scheduled_matches"] += int(day_entry.get("scheduled_matches", 0) or 0)

    weeks = sorted(week_map.values(), key=lambda x: (int(x.get("iso_year", 0) or 0), int(x.get("iso_week", 0) or 0)))
    for week in weeks:
        week_status = aggregate_progress_status([str(day.get("status", "")) for day in week["matchdays"]])
        week["status"] = week_status
        week["status_label"] = matchday_status_label(week_status)
        week["matchdays"] = sorted(week["matchdays"], key=lambda x: int(x.get("matchday", 0) or 0))

    season_start = weeks[0].get("range_start", "")
    season_end = weeks[-1].get("range_end", "")
    season_start_dt = parse_optional_datetime(str(season_start or ""))
    season_end_dt = parse_optional_datetime(str(season_end or ""))
    season_name = "Saison"
    if season_start_dt and season_end_dt:
        if season_start_dt.year == season_end_dt.year:
            season_name = f"Saison {season_start_dt.year}"
        else:
            season_name = f"Saison {season_start_dt.year}/{season_end_dt.year}"
    season_status = aggregate_progress_status([str(week.get("status", "")) for week in weeks])
    season_doc = {
        "name": season_name,
        "status": season_status,
        "status_label": SEASON_STATUS_LABELS.get(season_status, "Geplant"),
        "start": season_start,
        "end": season_end,
        "weeks": weeks,
    }
    total_matches = sum(int(week.get("total_matches", 0) or 0) for week in weeks)
    summary = {
        "week_count": len(weeks),
        "matchday_count": len(enriched_days),
        "match_count": total_matches,
    }
    return {
        "season": season_doc,
        "weeks": weeks,
        "summary": summary,
        "matchdays": enriched_days,
    }

def summarize_matchday(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(matches)
    completed = sum(1 for m in matches if str(m.get("status", "")).strip().lower() == "completed")
    disputed = sum(
        1
        for m in matches
        if str(m.get("status", "")).strip().lower() in {"disputed", "pending_admin_approval"}
    )
    scheduled = sum(1 for m in matches if str(m.get("scheduled_for", "")).strip())
    if total and completed == total:
        status = "completed"
    elif completed > 0:
        status = "in_progress"
    else:
        status = "pending"
    return {
        "status": status,
        "total_matches": total,
        "completed_matches": completed,
        "disputed_matches": disputed,
        "scheduled_matches": scheduled,
    }

def build_tournament_matchdays(tournament: Dict[str, Any]) -> List[Dict[str, Any]]:
    bracket = (tournament or {}).get("bracket") or {}
    bracket_type = str((bracket or {}).get("type", "")).strip().lower()
    if bracket_type not in {"round_robin", "league", "group_stage", "group_playoffs"}:
        return []

    matchday_map: Dict[int, Dict[str, Any]] = {}
    matchday_cfg = get_tournament_matchday_config(tournament or {})
    start_dt = parse_optional_datetime(str((tournament or {}).get("start_date", "") or ""))

    def ensure_matchday(day_index: int) -> Dict[str, Any]:
        day_key = max(1, int(day_index or 1))
        if day_key not in matchday_map:
            window_start = ""
            window_end = ""
            if start_dt:
                day_start = start_dt + timedelta(days=matchday_cfg["interval_days"] * (day_key - 1))
                day_end = day_start + timedelta(days=matchday_cfg["window_days"])
                window_start = day_start.isoformat()
                window_end = day_end.isoformat()
            matchday_map[day_key] = {
                "matchday": day_key,
                "name": f"Spieltag {day_key}",
                "window_start": window_start,
                "window_end": window_end,
                "matches": [],
            }
        return matchday_map[day_key]

    def append_round_matches(
        round_doc: Dict[str, Any],
        group_doc: Optional[Dict[str, Any]] = None,
        *,
        day_offset: int = 0,
    ):
        round_index = int(round_doc.get("round") or round_doc.get("matchday") or 1)
        base_matchday_index = int(round_doc.get("matchday") or round_index or 1)
        matchday_index = max(1, base_matchday_index + max(0, int(day_offset or 0)))
        target = ensure_matchday(matchday_index)
        target["name"] = str(round_doc.get("name", f"Spieltag {matchday_index}") or f"Spieltag {matchday_index}")
        if round_doc.get("window_start"):
            target["window_start"] = str(round_doc.get("window_start", "") or "")
        if round_doc.get("window_end"):
            target["window_end"] = str(round_doc.get("window_end", "") or "")
        for match in round_doc.get("matches", []) or []:
            item_matchday = int(match.get("matchday") or base_matchday_index or 1)
            item = {
                "id": match.get("id"),
                "round": match.get("round", round_index),
                "matchday": max(1, item_matchday + max(0, int(day_offset or 0))),
                "position": int(match.get("position", 0) or 0),
                "team1_id": match.get("team1_id"),
                "team1_name": match.get("team1_name", ""),
                "team1_logo_url": match.get("team1_logo_url", ""),
                "team1_tag": match.get("team1_tag", ""),
                "team2_id": match.get("team2_id"),
                "team2_name": match.get("team2_name", ""),
                "team2_logo_url": match.get("team2_logo_url", ""),
                "team2_tag": match.get("team2_tag", ""),
                "score1": int(match.get("score1", 0) or 0),
                "score2": int(match.get("score2", 0) or 0),
                "winner_id": match.get("winner_id"),
                "status": str(match.get("status", "pending") or "pending"),
                "scheduled_for": str(match.get("scheduled_for", "") or ""),
            }
            if group_doc:
                item["group_id"] = group_doc.get("id")
                item["group_name"] = group_doc.get("name", "")
            target["matches"].append(item)

    if bracket_type in {"round_robin", "league"}:
        for round_doc in (bracket.get("rounds", []) or []):
            append_round_matches(round_doc)
    elif bracket_type in {"group_stage", "group_playoffs"}:
        playoffs_matchday_offset = 0
        for group_doc in (bracket.get("groups", []) or []):
            for round_doc in (group_doc.get("rounds", []) or []):
                append_round_matches(round_doc, group_doc=group_doc)
                playoffs_matchday_offset = max(
                    playoffs_matchday_offset,
                    int(round_doc.get("matchday") or round_doc.get("round") or 1),
                )
        if bracket_type == "group_playoffs":
            playoffs = (bracket.get("playoffs") or {}).get("rounds", []) or []
            for round_doc in playoffs:
                append_round_matches(
                    round_doc,
                    group_doc={"id": "playoffs", "name": "Playoffs"},
                    day_offset=playoffs_matchday_offset,
                )

    result = []
    for day in sorted(matchday_map):
        doc = matchday_map[day]
        doc["matches"].sort(key=lambda x: (int(x.get("position", 0) or 0), str(x.get("id", ""))))
        doc.update(summarize_matchday(doc["matches"]))
        doc["status"] = normalize_matchday_status(doc.get("status"))
        doc["status_label"] = matchday_status_label(doc.get("status"))
        doc["window_label"] = format_date_range_label(doc.get("window_start", ""), doc.get("window_end", ""))
        result.append(doc)
    return enrich_matchdays_with_calendar(tournament, result)

@api_router.get("/tournaments/{tournament_id}/matchdays")
async def get_tournament_matchdays(tournament_id: str):
    log_info("matchdays.fetch.start", "Loading tournament matchdays", tournament_id=tournament_id)
    tournament = await db.tournaments.find_one(
        {"id": tournament_id},
        {
            "_id": 0,
            "id": 1,
            "name": 1,
            "status": 1,
            "bracket": 1,
            "bracket_type": 1,
            "start_date": 1,
            "matchday_interval_days": 1,
            "matchday_window_days": 1,
        },
    )
    if not tournament:
        log_warning("matchdays.fetch.not_found", "Tournament not found while loading matchdays", tournament_id=tournament_id)
        raise HTTPException(404, "Tournament not found")
    if not tournament.get("bracket"):
        log_warning("matchdays.fetch.no_bracket", "Matchdays requested before bracket generation", tournament_id=tournament_id)
        raise HTTPException(400, "Bracket wurde noch nicht generiert")

    days = build_tournament_matchdays(tournament)
    hierarchy = build_matchday_hierarchy(tournament, days)
    enriched_days = hierarchy.get("matchdays", days)
    log_info(
        "matchdays.fetch.success",
        "Tournament matchdays loaded",
        tournament_id=tournament_id,
        matchday_count=len(enriched_days),
        week_count=int((hierarchy.get("summary") or {}).get("week_count", 0) or 0),
    )
    return {
        "tournament_id": tournament_id,
        "type": str((tournament.get("bracket") or {}).get("type", tournament.get("bracket_type", ""))),
        "matchdays": enriched_days,
        "count": len(enriched_days),
        "hierarchy": hierarchy,
        "season": hierarchy.get("season"),
        "weeks": hierarchy.get("weeks", []),
        "summary": hierarchy.get("summary", {}),
    }

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
    entry_fee = float(t.get("entry_fee", 0) or 0)
    if entry_fee > 0 and str(reg.get("payment_status", "")).strip().lower() != "paid":
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

# --- Bracket Generation ---

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

def compute_payment_reservation_expiry_iso(reference_time: Optional[datetime] = None) -> str:
    base = reference_time or datetime.now(timezone.utc)
    return (base + timedelta(minutes=PAYMENT_RESERVATION_MINUTES)).isoformat()

def get_registration_payment_expiry(registration: Dict[str, Any]) -> Optional[datetime]:
    direct_expiry = parse_optional_datetime(str((registration or {}).get("payment_expires_at", "") or ""))
    if direct_expiry:
        return direct_expiry
    created_at = parse_optional_datetime(str((registration or {}).get("created_at", "") or ""))
    if created_at:
        return created_at + timedelta(minutes=PAYMENT_RESERVATION_MINUTES)
    return None

def is_pending_registration_active(registration: Dict[str, Any], *, reference_time: Optional[datetime] = None) -> bool:
    if str((registration or {}).get("payment_status", "") or "").strip().lower() != "pending":
        return False
    expires_at = get_registration_payment_expiry(registration)
    if not expires_at:
        return False
    now_ref = reference_time or datetime.now(timezone.utc)
    return expires_at > now_ref

def registration_counts_against_capacity(
    registration: Dict[str, Any],
    *,
    paid_tournament: bool,
    reference_time: Optional[datetime] = None,
) -> bool:
    if not paid_tournament:
        return True
    status = str((registration or {}).get("payment_status", "") or "").strip().lower()
    if status in {"paid", "free"}:
        return True
    if status == "pending":
        return is_pending_registration_active(registration, reference_time=reference_time)
    return False

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

def generate_group_playoffs(
    registrations: List[Dict],
    group_size: int = 4,
    advance_per_group: int = 2,
    start_date: str = "",
    interval_days: int = 7,
    window_days: int = 7,
):
    groups = generate_group_stage(
        registrations,
        group_size=group_size,
        start_date=start_date,
        interval_days=interval_days,
        window_days=window_days,
    )
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

def generate_round_robin(
    registrations,
    start_date: str = "",
    bracket_type: str = "round_robin",
    interval_days: int = 7,
    window_days: int = 7,
):
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
            window_start = None
            if base_start:
                window_start = base_start + timedelta(days=interval_days * round_idx)
                scheduled_for = window_start.isoformat()

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

        round_window_start = ""
        round_window_end = ""
        if base_start:
            start_doc = base_start + timedelta(days=interval_days * round_idx)
            end_doc = start_doc + timedelta(days=max(1, int(window_days or 7)))
            round_window_start = start_doc.isoformat()
            round_window_end = end_doc.isoformat()
        rounds.append(
            {
                "round": round_idx + 1,
                "matchday": round_idx + 1,
                "name": f"Spieltag {round_idx + 1}",
                "window_start": round_window_start,
                "window_end": round_window_end,
                "matches": round_matches,
            }
        )

        fixed = participants[0]
        rotating = participants[1:]
        rotating = [rotating[-1]] + rotating[:-1]
        participants = [fixed] + rotating

    return {"type": bracket_type, "rounds": rounds, "total_rounds": len(rounds)}

def generate_group_stage(
    registrations,
    group_size: int = 4,
    start_date: str = "",
    interval_days: int = 7,
    window_days: int = 7,
):
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
        rr = generate_round_robin(
            group_regs,
            start_date=start_date,
            bracket_type="round_robin",
            interval_days=interval_days,
            window_days=window_days,
        )
        for rd in rr.get("rounds", []):
            for match in rd.get("matches", []):
                match["group_id"] = idx + 1
                match["group_name"] = group_name
        group_docs.append({"id": idx + 1, "name": group_name, "rounds": rr.get("rounds", []), "total_rounds": rr.get("total_rounds", 0)})

    return {"type": "group_stage", "groups": group_docs, "group_size": size, "total_groups": len(group_docs)}

def sort_standings_rows(rows: List[Dict[str, Any]], tiebreakers: List[str]) -> List[Dict[str, Any]]:
    ordered_rules = normalize_tiebreakers(tiebreakers)

    def numeric_value(row: Dict[str, Any], key: str) -> float:
        try:
            return float(row.get(key, 0) or 0)
        except Exception:
            return 0.0

    def key_fn(row: Dict[str, Any]):
        parts = []
        for rule in ordered_rules:
            if rule == "team_name":
                parts.append(str(row.get("team_name", "")).lower())
            else:
                parts.append(-numeric_value(row, rule))
        parts.append(str(row.get("team_name", "")).lower())
        return tuple(parts)

    return sorted(rows, key=key_fn)

def compute_standings_for_registrations(
    registrations: List[Dict],
    matches: List[Dict],
    team_map: Dict[str, Dict],
    *,
    points_win: int = 3,
    points_draw: int = 1,
    points_loss: int = 0,
    tiebreakers: Optional[List[str]] = None,
) -> List[Dict]:
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
            st1["points"] += int(points_win)
            st2["losses"] += 1
            st2["points"] += int(points_loss)
        elif score2 > score1:
            st2["wins"] += 1
            st2["points"] += int(points_win)
            st1["losses"] += 1
            st1["points"] += int(points_loss)
        else:
            st1["draws"] += 1
            st2["draws"] += 1
            st1["points"] += int(points_draw)
            st2["points"] += int(points_draw)

    rows = list(standings.values())
    for row in rows:
        row["score_diff"] = row["score_for"] - row["score_against"]
    rows = sort_standings_rows(rows, tiebreakers or DEFAULT_TIEBREAKERS)
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

def find_match_round_context(bracket: Dict[str, Any], match_id: str) -> Dict[str, Any]:
    if not bracket or not match_id:
        return {}

    def _extract(round_doc: Dict[str, Any], match_doc: Dict[str, Any], group_doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "round": int(round_doc.get("round") or match_doc.get("round") or 1),
            "matchday": int(match_doc.get("matchday") or round_doc.get("matchday") or round_doc.get("round") or 1),
            "round_name": str(round_doc.get("name", "") or ""),
            "window_start": str(round_doc.get("window_start", "") or ""),
            "window_end": str(round_doc.get("window_end", "") or ""),
            "group_id": str((group_doc or {}).get("id", "") or ""),
            "group_name": str((group_doc or {}).get("name", "") or ""),
        }

    def _scan_rounds(rounds: List[Dict[str, Any]], group_doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        for round_doc in rounds or []:
            for match_doc in round_doc.get("matches", []) or []:
                if str(match_doc.get("id", "")).strip() == match_id:
                    return _extract(round_doc, match_doc, group_doc=group_doc)
        return {}

    bracket_type = str((bracket or {}).get("type", "")).strip().lower()
    if bracket_type in {"single_elimination", "round_robin", "league", "swiss_system", "ladder_system", "king_of_the_hill", "battle_royale"}:
        return _scan_rounds((bracket or {}).get("rounds", []) or [])
    if bracket_type == "double_elimination":
        for section_name in ("winners_bracket", "losers_bracket"):
            section_ctx = _scan_rounds(((bracket or {}).get(section_name) or {}).get("rounds", []) or [])
            if section_ctx:
                section_ctx["bracket_section"] = section_name
                return section_ctx
        gf = (bracket or {}).get("grand_final")
        if gf and str(gf.get("id", "")).strip() == match_id:
            return {
                "round": int(gf.get("round", 0) or 0),
                "matchday": int(gf.get("matchday", 0) or 0),
                "round_name": "Grand Final",
                "window_start": "",
                "window_end": "",
                "group_id": "",
                "group_name": "",
                "bracket_section": "grand_final",
            }
        return {}
    if bracket_type == "group_stage":
        for group_doc in (bracket or {}).get("groups", []) or []:
            ctx = _scan_rounds((group_doc or {}).get("rounds", []) or [], group_doc=group_doc)
            if ctx:
                return ctx
        return {}
    if bracket_type == "group_playoffs":
        for group_doc in (bracket or {}).get("groups", []) or []:
            ctx = _scan_rounds((group_doc or {}).get("rounds", []) or [], group_doc=group_doc)
            if ctx:
                return ctx
        playoffs_ctx = _scan_rounds(((bracket or {}).get("playoffs") or {}).get("rounds", []) or [], group_doc={"id": "playoffs", "name": "Playoffs"})
        if playoffs_ctx:
            return playoffs_ctx
    return {}

def build_match_lookup_query(match_id: str) -> Dict[str, Any]:
    target = str(match_id or "").strip()
    if not target:
        return {"_id": {"$exists": False}}
    return {
        "$or": [
            {"bracket.rounds.matches.id": target},
            {"bracket.winners_bracket.rounds.matches.id": target},
            {"bracket.losers_bracket.rounds.matches.id": target},
            {"bracket.grand_final.id": target},
            {"bracket.groups.rounds.matches.id": target},
            {"bracket.playoffs.rounds.matches.id": target},
        ]
    }

async def find_tournament_and_match_by_match_id(match_id: str):
    projection = {
        "_id": 0,
        "id": 1,
        "name": 1,
        "status": 1,
        "game_id": 1,
        "game_name": 1,
        "game_mode": 1,
        "participant_mode": 1,
        "start_date": 1,
        "matchday_interval_days": 1,
        "matchday_window_days": 1,
        "bracket": 1,
    }

    targeted = await db.tournaments.find_one(build_match_lookup_query(match_id), projection)
    if targeted:
        targeted_match = find_match_in_bracket(targeted.get("bracket"), match_id)
        if targeted_match:
            return targeted, targeted_match

    cursor = db.tournaments.find({"bracket": {"$ne": None}}, projection)
    async for tournament in cursor:
        match = find_match_in_bracket(tournament.get("bracket"), match_id)
        if match:
            return tournament, match
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

async def get_tournament_mode_settings_template(tournament: Dict[str, Any]) -> Dict[str, Any]:
    game_id = str((tournament or {}).get("game_id", "") or "").strip()
    game_mode = str((tournament or {}).get("game_mode", "") or "").strip().lower()
    if not game_id or not game_mode:
        return {}
    game = await db.games.find_one({"id": game_id}, {"_id": 0, "category": 1, "name": 1, "modes": 1})
    if not game:
        return {}
    _, changed = apply_mode_templates_to_game(game)
    if changed:
        await db.games.update_one({"id": game_id}, {"$set": {"modes": game.get("modes", []), "updated_at": now_iso()}})
    for mode in game.get("modes", []) or []:
        if str(mode.get("name", "")).strip().lower() == game_mode:
            tpl = mode.get("settings_template", {})
            if isinstance(tpl, dict):
                return deep_clone_template(tpl)
    return {}

async def resolve_user_match_side(user: Dict[str, Any], team1_reg: Optional[Dict], team2_reg: Optional[Dict]) -> Optional[str]:
    if not user:
        return None
    if user.get("role") == "admin":
        return "admin"

    async def _belongs(reg: Optional[Dict]) -> bool:
        if not reg:
            return False
        if reg.get("user_id") == user.get("id"):
            return True
        team_id = str(reg.get("team_id", "") or "").strip()
        if team_id:
            team_role = await get_user_team_role(user["id"], team_id)
            if team_role in {"owner", "leader"}:
                return True
        return False

    if await _belongs(team1_reg):
        return "team1"
    if await _belongs(team2_reg):
        return "team2"
    return None

def prepare_match_setup_response(doc: Optional[Dict[str, Any]], *, match_id: str, tournament_id: str) -> Dict[str, Any]:
    if not doc:
        return {
            "id": None,
            "tournament_id": tournament_id,
            "match_id": match_id,
            "status": "pending",
            "submission_team1": None,
            "submission_team2": None,
            "final_setup": {},
            "final_note": "",
            "updated_at": None,
            "created_at": None,
            "resolved_by": None,
            "resolved_at": None,
        }
    clean = {k: v for k, v in doc.items() if k != "_id"}
    clean.setdefault("status", "pending")
    clean.setdefault("submission_team1", None)
    clean.setdefault("submission_team2", None)
    clean.setdefault("final_setup", {})
    clean.setdefault("final_note", "")
    return clean

@api_router.get("/matches/{match_id}")
async def get_match_detail(request: Request, match_id: str):
    user = await require_auth(request)
    tournament, match = await find_tournament_and_match_by_match_id(match_id)
    if not tournament or not match:
        raise HTTPException(404, "Match nicht gefunden")
    if not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")

    team_reg_ids = [rid for rid in [match.get("team1_id"), match.get("team2_id")] if rid]
    regs = await db.registrations.find({"id": {"$in": team_reg_ids}}, {"_id": 0}).to_list(10)
    reg_by_id = {str(r.get("id", "")).strip(): r for r in regs if str(r.get("id", "")).strip()}
    team1_reg = reg_by_id.get(str(match.get("team1_id", "")).strip())
    team2_reg = reg_by_id.get(str(match.get("team2_id", "")).strip())

    side = await resolve_user_match_side(user, team1_reg, team2_reg)
    setup_doc = await db.match_setups.find_one({"tournament_id": tournament["id"], "match_id": match_id}, {"_id": 0})
    accepted_schedule = await db.schedule_proposals.find_one(
        {
            "match_id": match_id,
            "status": "accepted",
            "$or": [{"tournament_id": tournament["id"]}, {"tournament_id": {"$exists": False}}],
        },
        {"_id": 0},
    )
    schedule_count = await db.schedule_proposals.count_documents(
        {"match_id": match_id, "$or": [{"tournament_id": tournament["id"]}, {"tournament_id": {"$exists": False}}]}
    )

    mode_template = await get_tournament_mode_settings_template(tournament)
    round_context = find_match_round_context(tournament.get("bracket") or {}, match_id)
    match_payload = dict(match or {})
    if not match_payload.get("matchday") and round_context.get("matchday"):
        match_payload["matchday"] = int(round_context.get("matchday") or 0)
    if round_context.get("round_name") and not match_payload.get("round_name"):
        match_payload["round_name"] = str(round_context.get("round_name", "") or "")

    return {
        "tournament": {
            "id": tournament.get("id"),
            "name": tournament.get("name", ""),
            "status": tournament.get("status", ""),
            "game_name": tournament.get("game_name", ""),
            "game_mode": tournament.get("game_mode", ""),
            "participant_mode": tournament.get("participant_mode", "team"),
        },
        "match": match_payload,
        "team1_registration": sanitize_registration(team1_reg) if team1_reg else None,
        "team2_registration": sanitize_registration(team2_reg) if team2_reg else None,
        "setup": prepare_match_setup_response(setup_doc, match_id=match_id, tournament_id=tournament["id"]),
        "setup_template": mode_template,
        "context": round_context,
        "schedule": {
            "scheduled_for": str(match.get("scheduled_for", "") or ""),
            "window_start": str(round_context.get("window_start", "") or ""),
            "window_end": str(round_context.get("window_end", "") or ""),
            "accepted": accepted_schedule,
            "proposal_count": int(schedule_count or 0),
        },
        "viewer": {
            "is_admin": bool(user.get("role") == "admin"),
            "side": side,
            "can_manage_match": True,
        },
    }

@api_router.get("/matches/{match_id}/setup")
async def get_match_setup(request: Request, match_id: str):
    user = await require_auth(request)
    tournament, match = await find_tournament_and_match_by_match_id(match_id)
    if not tournament or not match:
        raise HTTPException(404, "Match nicht gefunden")
    if not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")

    setup_doc = await db.match_setups.find_one({"tournament_id": tournament["id"], "match_id": match_id}, {"_id": 0})
    mode_template = await get_tournament_mode_settings_template(tournament)

    regs = await db.registrations.find(
        {"id": {"$in": [match.get("team1_id"), match.get("team2_id")] if match.get("team1_id") or match.get("team2_id") else []}},
        {"_id": 0},
    ).to_list(10)
    reg_by_id = {str(r.get("id", "")).strip(): r for r in regs if str(r.get("id", "")).strip()}
    side = await resolve_user_match_side(
        user,
        reg_by_id.get(str(match.get("team1_id", "")).strip()),
        reg_by_id.get(str(match.get("team2_id", "")).strip()),
    )

    return {
        "setup": prepare_match_setup_response(setup_doc, match_id=match_id, tournament_id=tournament["id"]),
        "template": mode_template,
        "viewer_side": side,
    }

@api_router.post("/matches/{match_id}/setup")
async def submit_match_setup(request: Request, match_id: str, body: MatchSetupSubmission):
    user = await require_auth(request)
    tournament, match = await find_tournament_and_match_by_match_id(match_id)
    if not tournament or not match:
        raise HTTPException(404, "Match nicht gefunden")
    if match.get("status") == "completed":
        raise HTTPException(400, "Match ist bereits abgeschlossen")
    if match.get("type") == "battle_royale_heat" or match.get("participants"):
        raise HTTPException(400, "Für dieses Match ist Team-Setup nicht verfügbar")
    if not await can_user_manage_match(user, match):
        raise HTTPException(403, "Keine Berechtigung")

    regs = await db.registrations.find(
        {"id": {"$in": [match.get("team1_id"), match.get("team2_id")] if match.get("team1_id") or match.get("team2_id") else []}},
        {"_id": 0},
    ).to_list(10)
    reg_by_id = {str(r.get("id", "")).strip(): r for r in regs if str(r.get("id", "")).strip()}
    team1_reg = reg_by_id.get(str(match.get("team1_id", "")).strip())
    team2_reg = reg_by_id.get(str(match.get("team2_id", "")).strip())
    side = await resolve_user_match_side(user, team1_reg, team2_reg)
    if side not in {"team1", "team2"}:
        raise HTTPException(403, "Nur Team-Verantwortliche können Setup einreichen")

    settings = body.settings if isinstance(body.settings, dict) else {}
    if not settings:
        raise HTTPException(400, "Setup darf nicht leer sein")

    now = now_iso()
    submission = {
        "by": user["id"],
        "by_name": user.get("username", ""),
        "settings": settings,
        "note": normalize_optional_text(body.note, max_len=1000),
        "submitted_at": now,
    }

    query = {"tournament_id": tournament["id"], "match_id": match_id}
    existing = await db.match_setups.find_one(query, {"_id": 0})
    doc = existing or {
        "id": str(uuid.uuid4()),
        "tournament_id": tournament["id"],
        "match_id": match_id,
        "status": "pending",
        "submission_team1": None,
        "submission_team2": None,
        "final_setup": {},
        "final_note": "",
        "created_at": now,
    }
    key = "submission_team1" if side == "team1" else "submission_team2"
    doc[key] = submission
    doc["updated_at"] = now

    left = doc.get("submission_team1")
    right = doc.get("submission_team2")
    if left and right:
        left_norm = json.dumps(left.get("settings", {}), sort_keys=True)
        right_norm = json.dumps(right.get("settings", {}), sort_keys=True)
        if left_norm == right_norm:
            doc["status"] = "confirmed"
            doc["final_setup"] = left.get("settings", {})
            doc["final_note"] = left.get("note", "") or right.get("note", "")
            doc["confirmed_at"] = now
        else:
            doc["status"] = "disputed"
            doc["final_setup"] = {}
    else:
        doc["status"] = "pending"

    await db.match_setups.update_one(query, {"$set": doc}, upsert=True)
    return prepare_match_setup_response(doc, match_id=match_id, tournament_id=tournament["id"])

@api_router.put("/matches/{match_id}/setup/resolve")
async def resolve_match_setup(request: Request, match_id: str, body: MatchSetupResolve):
    admin = await require_admin(request)
    tournament, match = await find_tournament_and_match_by_match_id(match_id)
    if not tournament or not match:
        raise HTTPException(404, "Match nicht gefunden")
    if match.get("type") == "battle_royale_heat" or match.get("participants"):
        raise HTTPException(400, "Für dieses Match ist Team-Setup nicht verfügbar")
    settings = body.settings if isinstance(body.settings, dict) else {}
    if not settings:
        raise HTTPException(400, "Setup darf nicht leer sein")

    now = now_iso()
    query = {"tournament_id": tournament["id"], "match_id": match_id}
    existing = await db.match_setups.find_one(query, {"_id": 0}) or {
        "id": str(uuid.uuid4()),
        "tournament_id": tournament["id"],
        "match_id": match_id,
        "submission_team1": None,
        "submission_team2": None,
        "created_at": now,
    }
    existing["status"] = "resolved_by_admin"
    existing["final_setup"] = settings
    existing["final_note"] = normalize_optional_text(body.note, max_len=1000)
    existing["resolved_by"] = admin["id"]
    existing["resolved_by_name"] = admin.get("username", "")
    existing["resolved_at"] = now
    existing["updated_at"] = now
    await db.match_setups.update_one(query, {"$set": existing}, upsert=True)
    return prepare_match_setup_response(existing, match_id=match_id, tournament_id=tournament["id"])

@api_router.post("/tournaments/{tournament_id}/generate-bracket")
async def generate_bracket(request: Request, tournament_id: str):
    admin_user = await require_admin(request)
    log_info(
        "tournament.bracket.generate.start",
        "Bracket generation requested",
        tournament_id=tournament_id,
        admin_id=str(admin_user.get("id", "") or ""),
    )
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        log_warning("tournament.bracket.generate.not_found", "Bracket generation failed because tournament was not found", tournament_id=tournament_id)
        raise HTTPException(404, "Tournament not found")
    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).sort("seed", 1).to_list(200)
    if len(regs) < 2:
        log_warning(
            "tournament.bracket.generate.not_enough_participants",
            "Bracket generation failed because not enough registrations are present",
            tournament_id=tournament_id,
            registration_count=len(regs),
        )
        raise HTTPException(400, "Need at least 2 registrations to generate bracket")
    bracket_type = normalize_bracket_type(t.get("bracket_type", "single_elimination"))
    matchday_cfg = get_tournament_matchday_config(t)
    if bracket_type == "single_elimination":
        bracket = generate_single_elimination(regs)
    elif bracket_type == "double_elimination":
        bracket = generate_double_elimination(regs)
    elif bracket_type == "round_robin":
        bracket = generate_round_robin(
            regs,
            start_date=t.get("start_date", ""),
            bracket_type="round_robin",
            interval_days=matchday_cfg["interval_days"],
            window_days=matchday_cfg["window_days"],
        )
    elif bracket_type == "league":
        bracket = generate_round_robin(
            regs,
            start_date=t.get("start_date", ""),
            bracket_type="league",
            interval_days=matchday_cfg["interval_days"],
            window_days=matchday_cfg["window_days"],
        )
    elif bracket_type == "group_stage":
        bracket = generate_group_stage(
            regs,
            group_size=int(t.get("group_size", 4) or 4),
            start_date=t.get("start_date", ""),
            interval_days=matchday_cfg["interval_days"],
            window_days=matchday_cfg["window_days"],
        )
    elif bracket_type == "group_playoffs":
        bracket = generate_group_playoffs(
            regs,
            group_size=int(t.get("group_size", 4) or 4),
            advance_per_group=int(t.get("advance_per_group", 2) or 2),
            start_date=t.get("start_date", ""),
            interval_days=matchday_cfg["interval_days"],
            window_days=matchday_cfg["window_days"],
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
    log_info(
        "tournament.bracket.generate.success",
        "Bracket generation completed",
        tournament_id=tournament_id,
        bracket_type=bracket_type,
        registration_count=len(regs),
    )
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    return t

# --- Score Submission System ---

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
            # Scores differ -> disputed
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

# --- Payment Endpoints ---

@api_router.post("/payments/create-checkout")
async def create_checkout(request: Request, body: PaymentRequest):
    log_info(
        "payments.checkout.start",
        "Checkout creation requested",
        tournament_id=body.tournament_id,
        registration_id=body.registration_id,
        requested_provider=str(body.provider or ""),
    )
    t = await db.tournaments.find_one({"id": body.tournament_id}, {"_id": 0})
    if not t:
        log_warning("payments.checkout.tournament_not_found", "Checkout failed because tournament was not found", tournament_id=body.tournament_id)
        raise HTTPException(404, "Tournament not found")
    entry_fee = t.get("entry_fee", 0)
    if entry_fee <= 0:
        log_warning("payments.checkout.free_tournament", "Checkout blocked because tournament has no entry fee", tournament_id=body.tournament_id)
        raise HTTPException(400, "This tournament is free")
    reg = await db.registrations.find_one({"id": body.registration_id, "tournament_id": body.tournament_id}, {"_id": 0})
    if not reg:
        log_warning(
            "payments.checkout.registration_not_found",
            "Checkout failed because registration was not found",
            tournament_id=body.tournament_id,
            registration_id=body.registration_id,
        )
        raise HTTPException(404, "Registration not found")
    if reg.get("payment_status") == "paid":
        log_warning(
            "payments.checkout.already_paid",
            "Checkout blocked because registration is already paid",
            tournament_id=body.tournament_id,
            registration_id=body.registration_id,
        )
        raise HTTPException(400, "Registration is already paid")

    user = await get_current_user(request)
    if reg.get("user_id") and (not user or (user["id"] != reg["user_id"] and user.get("role") != "admin")):
        log_warning(
            "payments.checkout.forbidden",
            "Checkout blocked because requester has no permission for this registration",
            tournament_id=body.tournament_id,
            registration_id=body.registration_id,
            requester_id=str((user or {}).get("id", "") or ""),
        )
        raise HTTPException(403, "Keine Berechtigung für diese Zahlung")

    payment_provider = await get_payment_provider(body.provider)
    host_url = body.origin_url.rstrip("/")
    if not (host_url.startswith("http://") or host_url.startswith("https://")):
        log_warning("payments.checkout.invalid_origin", "Checkout blocked because origin URL is invalid", origin_url=body.origin_url)
        raise HTTPException(400, "Invalid origin URL")

    currency = str(t.get("currency", "usd") or "usd").lower()
    unit_amount = int(round(float(entry_fee) * 100))
    reservation_expires_at = compute_payment_reservation_expiry_iso()
    if unit_amount <= 0:
        log_warning("payments.checkout.invalid_amount", "Checkout blocked because computed amount is invalid", tournament_id=body.tournament_id, entry_fee=float(entry_fee or 0))
        raise HTTPException(400, "Invalid entry fee")
    if payment_provider == "paypal":
        validation = await validate_paypal_configuration(force_live=True, persist_result=True)
        if not validation.get("configured"):
            log_warning("payments.checkout.paypal_not_configured", "Checkout blocked because PayPal is not fully configured")
            raise HTTPException(400, "PayPal ist nicht vollständig konfiguriert")
        if not validation.get("valid"):
            log_warning("payments.checkout.paypal_invalid", "Checkout blocked because PayPal validation failed", detail=str(validation.get("detail", "") or ""))
            raise HTTPException(400, str(validation.get("detail") or "PayPal Validierung fehlgeschlagen"))
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
        await db.registrations.update_one(
            {"id": body.registration_id},
            {
                "$set": {
                    "payment_session_id": order_id,
                    "payment_status": "pending",
                    "payment_expires_at": reservation_expires_at,
                    "updated_at": now_iso(),
                }
            },
        )
        log_info(
            "payments.checkout.paypal.success",
            "PayPal checkout created",
            tournament_id=body.tournament_id,
            registration_id=body.registration_id,
            session_id=order_id,
        )
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
        log_error(
            "payments.checkout.stripe.error",
            "Stripe checkout creation failed",
            tournament_id=body.tournament_id,
            registration_id=body.registration_id,
            error=str(e),
        )
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
    await db.registrations.update_one(
        {"id": body.registration_id},
        {
            "$set": {
                "payment_session_id": session.id,
                "payment_status": "pending",
                "payment_expires_at": reservation_expires_at,
                "updated_at": now_iso(),
            }
        },
    )
    log_info(
        "payments.checkout.stripe.success",
        "Stripe checkout created",
        tournament_id=body.tournament_id,
        registration_id=body.registration_id,
        session_id=str(session.id),
    )
    return {"url": session.url, "session_id": session.id, "provider": "stripe"}

@api_router.get("/payments/status/{session_id}")
async def check_payment_status(request: Request, session_id: str):
    user = await require_auth(request)
    log_debug("payments.status.start", "Payment status requested", session_id=session_id, user_id=str(user.get("id", "") or ""))
    existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not existing:
        log_warning("payments.status.not_found", "Payment status requested for unknown session", session_id=session_id)
        raise HTTPException(404, "Payment session not found")

    registration = await db.registrations.find_one({"id": existing.get("registration_id")}, {"_id": 0, "user_id": 1})
    if registration and registration.get("user_id") and registration.get("user_id") != user.get("id") and user.get("role") != "admin":
        log_warning(
            "payments.status.forbidden",
            "Payment status denied because requester has no permission",
            session_id=session_id,
            requester_id=str(user.get("id", "") or ""),
        )
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
                log_warning("payments.status.paypal_capture_retry", "PayPal order capture failed during polling, refetching order status", session_id=session_id)
                refreshed = await get_paypal_order(session_id)
                order = refreshed or order
                order_status = str((refreshed or {}).get("status", order_status) or order_status).strip().upper()

        if order_status == "COMPLETED":
            payment_status = "paid"
        elif order_status in {"VOIDED", "CANCELLED", "DECLINED", "FAILED", "EXPIRED"}:
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
            await db.registrations.update_one(
                {"id": existing["registration_id"]},
                {"$set": {"payment_status": "paid", "payment_expires_at": "", "updated_at": now_iso()}},
            )
        elif payment_status == "failed":
            await db.registrations.update_one(
                {"id": existing["registration_id"]},
                {"$set": {"payment_status": "failed", "payment_expires_at": "", "updated_at": now_iso()}},
            )

        log_info(
            "payments.status.paypal.result",
            "Resolved PayPal payment status",
            session_id=session_id,
            payment_status=payment_status,
            status=order_status,
        )
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
        log_error("payments.status.stripe.error", "Stripe status request failed", session_id=session_id, error=str(e))
        raise HTTPException(404, "Payment session not found")

    stripe_payment_status_raw = str(getattr(session, "payment_status", "") or "").strip().lower()
    session_status = str(getattr(session, "status", "") or "").strip().lower()
    payment_status = "pending"
    if stripe_payment_status_raw == "paid":
        payment_status = "paid"
    elif session_status in {"expired"} or stripe_payment_status_raw in {"unpaid", "canceled", "cancelled"}:
        payment_status = "failed"

    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "payment_status": payment_status,
                "status": session_status,
                "provider_payment_status": stripe_payment_status_raw,
                "updated_at": now_iso(),
            }
        },
    )
    if payment_status == "paid":
        await db.registrations.update_one(
            {"id": existing["registration_id"]},
            {"$set": {"payment_status": "paid", "payment_expires_at": "", "updated_at": now_iso()}},
        )
    elif payment_status == "failed":
        await db.registrations.update_one(
            {"id": existing["registration_id"]},
            {"$set": {"payment_status": "failed", "payment_expires_at": "", "updated_at": now_iso()}},
        )
    log_info(
        "payments.status.stripe.result",
        "Resolved Stripe payment status",
        session_id=session_id,
        payment_status=payment_status,
        status=session_status,
        provider_payment_status=stripe_payment_status_raw,
    )
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
                    {"$set": {"payment_status": "paid", "payment_expires_at": "", "updated_at": now_iso()}},
                )
        return {"status": "processed"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

# --- Profile Endpoint ---

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

# --- Widget Endpoint ---

@api_router.get("/widget/tournament/{tournament_id}")
async def get_widget_data(tournament_id: str, view: Optional[str] = None, matchday: Optional[int] = None):
    log_debug("widget.fetch.start", "Widget payload requested", tournament_id=tournament_id, view=view, matchday=matchday)
    t = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not t:
        log_warning("widget.fetch.not_found", "Widget requested for missing tournament", tournament_id=tournament_id)
        raise HTTPException(404, "Tournament not found")
    hydrate_tournament_defaults(t)
    regs = await db.registrations.find({"tournament_id": tournament_id}, {"_id": 0}).to_list(200)
    requested_view = str(view or "bracket").strip().lower()
    if requested_view not in {"bracket", "standings", "matchdays"}:
        requested_view = "bracket"

    payload: Dict[str, Any] = {
        "tournament": t,
        "registrations": [sanitize_registration(r) for r in regs],
        "embed_version": "1.1",
        "view": requested_view,
    }

    if requested_view == "standings" and t.get("bracket"):
        try:
            payload["standings"] = await get_tournament_standings(tournament_id)
        except HTTPException as e:
            payload["standings_error"] = str(e.detail)
    elif requested_view == "matchdays" and t.get("bracket"):
        all_days = build_tournament_matchdays(t)
        hierarchy = build_matchday_hierarchy(t, all_days)
        all_days = hierarchy.get("matchdays", all_days)
        payload["matchdays"] = all_days
        payload["matchday_hierarchy"] = hierarchy
        payload["season"] = hierarchy.get("season")
        payload["weeks"] = hierarchy.get("weeks", [])
        payload["matchday_summary"] = hierarchy.get("summary", {})
        if isinstance(matchday, int) and matchday > 0:
            payload["selected_matchday"] = next((d for d in all_days if int(d.get("matchday", 0) or 0) == matchday), None)

    log_debug(
        "widget.fetch.success",
        "Widget payload built",
        tournament_id=tournament_id,
        view=requested_view,
        registration_count=len(payload.get("registrations", [])),
        matchday_count=len(payload.get("matchdays", [])) if isinstance(payload.get("matchdays"), list) else 0,
    )
    return payload

@api_router.get("/faq")
async def get_faq():
    return await get_faq_payload()

# --- Comment Endpoints ---

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

# --- Notification Endpoints ---

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

# --- Match Scheduling ---

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

    parsed_time = parse_optional_datetime(body.proposed_time)
    if not parsed_time:
        raise HTTPException(400, "Ungültiges Datum/Zeitformat")

    doc = {
        "id": str(uuid.uuid4()),
        "tournament_id": tournament["id"],
        "match_id": match_id,
        "proposed_by": user["id"],
        "proposed_by_name": user["username"],
        "proposed_time": parsed_time.isoformat(),
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

    accepted_time = str((proposal or {}).get("proposed_time", "") or "").strip()
    bracket = tournament.get("bracket") or {}
    target_match = find_match_in_bracket(bracket, match_id)
    if target_match and accepted_time:
        target_match["scheduled_for"] = accepted_time
        await db.tournaments.update_one(
            {"id": tournament["id"]},
            {"$set": {"bracket": bracket, "updated_at": now_iso()}},
        )

    if proposal and proposal.get("proposed_by") != user["id"]:
        notif = {
            "id": str(uuid.uuid4()),
            "user_id": proposal["proposed_by"],
            "type": "schedule",
            "message": f"{user['username']} hat deinen Zeitvorschlag akzeptiert",
            "link": f"/tournaments/{tournament['id']}/matches/{match_id}",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.notifications.insert_one(notif)
    return {"status": "accepted"}

# --- Auto-Scheduling System ---

WEEKDAY_MAP = {
    "monday": 0, "montag": 0,
    "tuesday": 1, "dienstag": 1,
    "wednesday": 2, "mittwoch": 2,
    "thursday": 3, "donnerstag": 3,
    "friday": 4, "freitag": 4,
    "saturday": 5, "samstag": 5,
    "sunday": 6, "sonntag": 6,
}

def get_default_match_datetime(tournament: Dict, window_start: Optional[datetime], window_end: Optional[datetime]) -> Optional[datetime]:
    """Calculate default match datetime based on tournament settings."""
    default_day = str(tournament.get("default_match_day", "wednesday") or "wednesday").strip().lower()
    default_hour = max(0, min(23, int(tournament.get("default_match_hour", 19) or 19)))
    
    target_weekday = WEEKDAY_MAP.get(default_day, 2)  # Wednesday as fallback
    
    if window_start:
        base_date = window_start
    elif window_end:
        base_date = window_end - timedelta(days=3)
    else:
        base_date = datetime.now(timezone.utc)
    
    # Find the target weekday within the window
    days_until_target = (target_weekday - base_date.weekday()) % 7
    if days_until_target == 0 and base_date.hour > default_hour:
        days_until_target = 7
    
    target_date = base_date + timedelta(days=days_until_target)
    result = target_date.replace(hour=default_hour, minute=0, second=0, microsecond=0)
    
    # Ensure it's within the window
    if window_end and result > window_end:
        result = window_end.replace(hour=default_hour, minute=0, second=0, microsecond=0)
    
    return result

@api_router.post("/tournaments/{tournament_id}/auto-schedule-unscheduled")
async def auto_schedule_unscheduled_matches(request: Request, tournament_id: str):
    """Admin endpoint to auto-schedule all unscheduled matches with default time."""
    await require_admin(request)
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not tournament:
        raise HTTPException(404, "Turnier nicht gefunden")
    if not tournament.get("bracket"):
        raise HTTPException(400, "Bracket noch nicht generiert")
    
    bracket = tournament["bracket"]
    bracket_type = bracket.get("type", "")
    scheduled_count = 0
    
    def schedule_match(match: Dict, window_start: Optional[datetime], window_end: Optional[datetime]) -> bool:
        nonlocal scheduled_count
        if match.get("scheduled_for"):
            return False
        if match.get("status") == "completed":
            return False
        if not match.get("team1_id") or not match.get("team2_id"):
            return False
        
        default_time = get_default_match_datetime(tournament, window_start, window_end)
        if default_time:
            match["scheduled_for"] = default_time.isoformat()
            match["auto_scheduled"] = True
            scheduled_count += 1
            return True
        return False
    
    # Process based on bracket type
    if bracket_type in ("league", "round_robin"):
        for round_doc in bracket.get("rounds", []):
            window_start = parse_optional_datetime(str(round_doc.get("window_start", "") or ""))
            window_end = parse_optional_datetime(str(round_doc.get("window_end", "") or ""))
            for match in round_doc.get("matches", []):
                schedule_match(match, window_start, window_end)
    
    elif bracket_type in ("group_stage", "group_playoffs"):
        for group in bracket.get("groups", []):
            for round_doc in group.get("rounds", []):
                window_start = parse_optional_datetime(str(round_doc.get("window_start", "") or ""))
                window_end = parse_optional_datetime(str(round_doc.get("window_end", "") or ""))
                for match in round_doc.get("matches", []):
                    schedule_match(match, window_start, window_end)
        if bracket_type == "group_playoffs" and bracket.get("playoffs"):
            for round_doc in bracket["playoffs"].get("rounds", []):
                for match in round_doc.get("matches", []):
                    schedule_match(match, None, None)
    
    elif bracket_type in ("single_elimination", "double_elimination", "swiss_system", "ladder_system", "king_of_the_hill"):
        for round_doc in bracket.get("rounds", []):
            for match in round_doc.get("matches", []):
                schedule_match(match, None, None)
    
    if scheduled_count > 0:
        await db.tournaments.update_one(
            {"id": tournament_id},
            {"$set": {"bracket": bracket, "updated_at": now_iso()}}
        )
    
    return {
        "status": "ok",
        "scheduled_count": scheduled_count,
        "message": f"{scheduled_count} Matches wurden automatisch terminiert"
    }

@api_router.get("/tournaments/{tournament_id}/scheduling-status")
async def get_scheduling_status(request: Request, tournament_id: str):
    """Get overview of scheduled vs unscheduled matches."""
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not tournament:
        raise HTTPException(404, "Turnier nicht gefunden")
    if not tournament.get("bracket"):
        return {"total": 0, "scheduled": 0, "unscheduled": 0, "completed": 0, "pending": 0}
    
    bracket = tournament["bracket"]
    bracket_type = bracket.get("type", "")
    
    stats = {"total": 0, "scheduled": 0, "unscheduled": 0, "completed": 0, "pending": 0, "auto_scheduled": 0}
    
    def count_match(match: Dict):
        stats["total"] += 1
        if match.get("status") == "completed":
            stats["completed"] += 1
        else:
            stats["pending"] += 1
        if match.get("scheduled_for"):
            stats["scheduled"] += 1
        else:
            stats["unscheduled"] += 1
        if match.get("auto_scheduled"):
            stats["auto_scheduled"] += 1
    
    if bracket_type in ("league", "round_robin", "swiss_system", "ladder_system", "king_of_the_hill"):
        for round_doc in bracket.get("rounds", []):
            for match in round_doc.get("matches", []):
                count_match(match)
    elif bracket_type in ("group_stage", "group_playoffs"):
        for group in bracket.get("groups", []):
            for round_doc in group.get("rounds", []):
                for match in round_doc.get("matches", []):
                    count_match(match)
        if bracket_type == "group_playoffs" and bracket.get("playoffs"):
            for round_doc in bracket["playoffs"].get("rounds", []):
                for match in round_doc.get("matches", []):
                    count_match(match)
    elif bracket_type == "single_elimination":
        for round_doc in bracket.get("rounds", []):
            for match in round_doc.get("matches", []):
                count_match(match)
    elif bracket_type == "double_elimination":
        for round_doc in bracket.get("winners_bracket", {}).get("rounds", []):
            for match in round_doc.get("matches", []):
                count_match(match)
        for round_doc in bracket.get("losers_bracket", {}).get("rounds", []):
            for match in round_doc.get("matches", []):
                count_match(match)
        if bracket.get("grand_final"):
            count_match(bracket["grand_final"])
    
    stats["default_day"] = tournament.get("default_match_day", "wednesday")
    stats["default_hour"] = tournament.get("default_match_hour", 19)
    stats["auto_schedule_enabled"] = tournament.get("auto_schedule_on_window_end", True)
    
    return stats

# --- Scheduling Reminder System ---

@api_router.post("/tournaments/{tournament_id}/send-scheduling-reminders")
async def send_scheduling_reminders(request: Request, tournament_id: str, hours_before_window_end: int = 24):
    """Send reminder emails to teams with unscheduled matches."""
    await require_admin(request)
    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not tournament:
        raise HTTPException(404, "Turnier nicht gefunden")
    if not tournament.get("bracket"):
        raise HTTPException(400, "Bracket noch nicht generiert")
    
    bracket = tournament["bracket"]
    bracket_type = bracket.get("type", "")
    now = datetime.now(timezone.utc)
    reminder_threshold = timedelta(hours=hours_before_window_end)
    reminders_sent = 0
    teams_notified = set()
    
    async def process_match_for_reminder(match: Dict, window_end: Optional[datetime]):
        nonlocal reminders_sent
        # Skip if already scheduled or completed
        if match.get("scheduled_for") or match.get("status") == "completed":
            return
        if not match.get("team1_id") or not match.get("team2_id"):
            return
        
        # Check if we're within the reminder threshold
        should_send = False
        if window_end:
            time_until_end = window_end - now
            if timedelta(0) < time_until_end <= reminder_threshold:
                should_send = True
        else:
            # For KO-style, send reminders for any unscheduled match
            should_send = True
        
        if not should_send:
            return
        
        # Get team details and notify
        for team_id in [match.get("team1_id"), match.get("team2_id")]:
            if team_id and team_id not in teams_notified:
                team = await db.teams.find_one({"id": team_id}, {"_id": 0, "name": 1, "owner_id": 1})
                if team and team.get("owner_id"):
                    owner = await db.users.find_one({"id": team["owner_id"]}, {"_id": 0, "email": 1, "username": 1})
                    if owner and owner.get("email"):
                        # Create notification
                        notif = {
                            "id": str(uuid.uuid4()),
                            "user_id": team["owner_id"],
                            "type": "scheduling_reminder",
                            "title": "Termin-Erinnerung",
                            "message": f"Das Match für Team '{team.get('name', 'Unbekannt')}' im Turnier '{tournament.get('name', '')}' hat noch keinen Termin. Bitte stimmt euch im Match-Hub ab!",
                            "read": False,
                            "created_at": now_iso(),
                            "tournament_id": tournament_id,
                            "match_id": match.get("id", ""),
                        }
                        await db.notifications.insert_one(notif)
                        
                        # Send email
                        default_day = tournament.get("default_match_day", "Mittwoch")
                        default_hour = tournament.get("default_match_hour", 19)
                        day_map = {"monday": "Montag", "tuesday": "Dienstag", "wednesday": "Mittwoch", "thursday": "Donnerstag", "friday": "Freitag", "saturday": "Samstag", "sunday": "Sonntag"}
                        day_display = day_map.get(str(default_day).lower(), default_day)
                        
                        email_body = f"""Hallo {owner.get('username', 'Team-Owner')},

dies ist eine freundliche Erinnerung: Das Match für Team "{team.get('name', 'Unbekannt')}" im Turnier "{tournament.get('name', '')}" hat noch keinen Termin!

Bitte einigt euch mit eurem Gegner im Match-Hub auf einen Termin.

⚠️ Wichtig: Falls keine Einigung erfolgt, wird automatisch der Standard-Termin verwendet:
   📅 {day_display}, {default_hour}:00 Uhr

Mit sportlichen Grüßen,
Das ARENA eSports Team
"""
                        await send_email_notification(
                            owner["email"],
                            f"[{tournament.get('name', 'Turnier')}] Termin-Erinnerung für {team.get('name', 'dein Team')}",
                            email_body
                        )
                        teams_notified.add(team_id)
                        reminders_sent += 1
    
    # Process all matches based on bracket type
    if bracket_type in ("league", "round_robin"):
        for round_doc in bracket.get("rounds", []):
            window_end = parse_optional_datetime(str(round_doc.get("window_end", "") or ""))
            for match in round_doc.get("matches", []):
                await process_match_for_reminder(match, window_end)
    elif bracket_type in ("group_stage", "group_playoffs"):
        for group in bracket.get("groups", []):
            for round_doc in group.get("rounds", []):
                window_end = parse_optional_datetime(str(round_doc.get("window_end", "") or ""))
                for match in round_doc.get("matches", []):
                    await process_match_for_reminder(match, window_end)
    elif bracket_type in ("single_elimination", "double_elimination", "swiss_system"):
        for round_doc in bracket.get("rounds", []):
            for match in round_doc.get("matches", []):
                await process_match_for_reminder(match, None)
    
    return {
        "status": "ok",
        "reminders_sent": reminders_sent,
        "teams_notified": len(teams_notified),
        "message": f"{reminders_sent} Erinnerungen an {len(teams_notified)} Teams gesendet"
    }

# --- PayPal Payment Integration ---

class PayPalOrderCreate(BaseModel):
    registration_id: str

@api_router.post("/payments/paypal/create-order")
async def create_paypal_order_v2(request: Request, body: PayPalOrderCreate):
    """Create a PayPal order for tournament entry fee."""
    user = await require_auth(request)
    
    reg = await db.registrations.find_one({"id": body.registration_id}, {"_id": 0})
    if not reg:
        raise HTTPException(404, "Registrierung nicht gefunden")
    
    tournament = await db.tournaments.find_one({"id": reg["tournament_id"]}, {"_id": 0})
    if not tournament:
        raise HTTPException(404, "Turnier nicht gefunden")
    
    entry_fee = float(tournament.get("entry_fee", 0))
    if entry_fee <= 0:
        raise HTTPException(400, "Turnier ist kostenlos, keine Zahlung erforderlich")
    
    # Check if already paid
    if reg.get("payment_status") == "paid":
        raise HTTPException(400, "Bereits bezahlt")
    
    # Get PayPal config from admin settings
    paypal_mode = await get_setting_value_with_env_fallback("paypal_mode", "sandbox")
    paypal_client_id = await get_setting_value_with_env_fallback("paypal_client_id", env_keys=["PAYPAL_CLIENT_ID"])
    paypal_secret = await get_setting_value_with_env_fallback("paypal_secret", env_keys=["PAYPAL_SECRET"])
    
    if not paypal_client_id or not paypal_secret:
        raise HTTPException(500, "PayPal ist nicht konfiguriert. Bitte Admin kontaktieren.")
    
    # Create order record
    order_id = f"PAYPAL-{uuid.uuid4()}"
    currency = str(tournament.get("currency", "USD")).upper()
    if currency not in ("USD", "EUR", "GBP"):
        currency = "USD"
    
    order = {
        "id": order_id,
        "registration_id": body.registration_id,
        "tournament_id": tournament["id"],
        "user_id": user["id"],
        "amount": entry_fee,
        "currency": currency,
        "provider": "paypal",
        "status": "pending",
        "created_at": now_iso(),
    }
    await db.payment_transactions.insert_one(order)
    
    # Return data for frontend to create PayPal order
    return {
        "order_id": order_id,
        "client_id": paypal_client_id,
        "amount": str(entry_fee),
        "currency": currency,
        "mode": paypal_mode,
        "tournament_name": tournament.get("name", ""),
        "description": f"Startgebühr: {tournament.get('name', 'Turnier')}",
    }

@api_router.post("/payments/paypal/capture-order")
async def capture_paypal_order_v2(request: Request, order_id: str = Body(...), paypal_order_id: str = Body(...)):
    """Capture a PayPal order after approval."""
    user = await require_auth(request)
    
    # Find our order
    order = await db.payment_transactions.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order nicht gefunden")
    if order.get("user_id") != user["id"]:
        raise HTTPException(403, "Keine Berechtigung")
    if order.get("status") == "completed":
        raise HTTPException(400, "Bereits abgeschlossen")
    
    # Update order with PayPal transaction ID and mark as completed
    await db.payment_transactions.update_one(
        {"id": order_id},
        {"$set": {
            "status": "completed",
            "paypal_order_id": paypal_order_id,
            "completed_at": now_iso(),
        }}
    )
    
    # Update registration as paid
    await db.registrations.update_one(
        {"id": order["registration_id"]},
        {"$set": {
            "payment_status": "paid",
            "payment_method": "paypal",
            "payment_completed_at": now_iso(),
        }}
    )
    
    return {"status": "success", "message": "Zahlung erfolgreich!"}

@api_router.get("/payments/paypal/config")
async def get_paypal_config():
    """Get PayPal client config for frontend."""
    paypal_mode = await get_setting_value_with_env_fallback("paypal_mode", "sandbox")
    paypal_client_id = await get_setting_value_with_env_fallback("paypal_client_id", env_keys=["PAYPAL_CLIENT_ID"])
    
    if not paypal_client_id:
        return {"enabled": False}
    
    return {
        "enabled": True,
        "client_id": paypal_client_id,
        "mode": paypal_mode,
    }

# --- Admin Endpoints ---

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

@api_router.get("/admin/faq")
async def admin_get_faq(request: Request):
    await require_admin(request)
    return await get_faq_payload()

@api_router.put("/admin/faq")
async def admin_update_faq(request: Request, body: FAQUpdate):
    await require_admin(request)
    raw_items = [item.model_dump() for item in (body.items or [])]
    normalized_items = normalize_faq_items(raw_items)
    await save_admin_setting_value(FAQ_SETTINGS_KEY, json.dumps(normalized_items, ensure_ascii=False))
    payload = await get_faq_payload()
    return {"status": "ok", **payload}

@api_router.get("/admin/payments/providers/status")
async def admin_get_payment_provider_status(request: Request):
    await require_admin(request)
    provider = await get_payment_provider()
    status = await get_payment_provider_status(force_paypal_check=False)
    return {"selected_provider": provider, **status}

@api_router.post("/admin/payments/paypal/validate")
async def admin_validate_paypal(request: Request, body: Optional[AdminPayPalValidateRequest] = None):
    admin_user = await require_admin(request)
    force_live = True if body is None else bool(body.force_live)
    log_info(
        "paypal.validate.admin.start",
        "Admin triggered PayPal validation",
        admin_id=str(admin_user.get("id", "") or ""),
        force_live=force_live,
    )
    result = await validate_paypal_configuration(force_live=force_live, persist_result=True)
    log_info(
        "paypal.validate.admin.result",
        "Admin PayPal validation completed",
        admin_id=str(admin_user.get("id", "") or ""),
        valid=bool(result.get("valid")),
        mode=str(result.get("mode", "") or ""),
    )
    return result

@api_router.post("/admin/email/test")
async def admin_send_test_email(request: Request, body: AdminEmailTest):
    await require_admin(request)
    to_email = normalize_email(body.email)
    if not to_email or not is_valid_email(to_email):
        raise HTTPException(400, "Ungültige E-Mail-Adresse")
    ok, detail = await send_email_notification_detailed(
        to_email,
        "ARENA SMTP Test",
        "Dies ist eine Testnachricht aus dem ARENA Adminbereich.",
    )
    if not ok:
        raise HTTPException(400, detail or "SMTP Versand fehlgeschlagen. Bitte SMTP Einstellungen prüfen.")
    return {"status": "sent", "email": to_email, "detail": detail}

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

# --- Stats ---

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

async def _safe_create_index(collection_name: str, keys: List[Tuple[str, int]], **options: Any) -> None:
    index_name = str(options.get("name", "") or "")
    try:
        await db[collection_name].create_index(keys, **options)
    except (OperationFailure, DuplicateKeyError) as e:
        log_warning(
            "db.index.ensure.failed",
            "Index creation skipped",
            collection=collection_name,
            index=index_name,
            error=str(e),
        )
    except Exception as e:
        log_error(
            "db.index.ensure.error",
            "Unexpected error during index creation",
            collection=collection_name,
            index=index_name,
            error=str(e),
            exc_info=True,
        )

async def ensure_indexes() -> None:
    log_info("db.index.ensure.start", "Ensuring MongoDB indexes")

    index_specs: List[Tuple[str, List[Tuple[List[Tuple[str, int]], Dict[str, Any]]]]] = [
        (
            "users",
            [
                ([("id", ASCENDING)], {"name": "users_id_unique", "unique": True}),
                ([("email", ASCENDING)], {"name": "users_email_unique", "unique": True}),
                ([("role", ASCENDING)], {"name": "users_role_idx"}),
            ],
        ),
        (
            "teams",
            [
                ([("id", ASCENDING)], {"name": "teams_id_unique", "unique": True}),
                ([("owner_id", ASCENDING)], {"name": "teams_owner_idx"}),
                ([("parent_team_id", ASCENDING)], {"name": "teams_parent_idx"}),
                ([("member_ids", ASCENDING)], {"name": "teams_members_idx"}),
            ],
        ),
        (
            "games",
            [
                ([("id", ASCENDING)], {"name": "games_id_unique", "unique": True}),
                ([("name", ASCENDING)], {"name": "games_name_idx"}),
            ],
        ),
        (
            "tournaments",
            [
                ([("id", ASCENDING)], {"name": "tournaments_id_unique", "unique": True}),
                ([("status", ASCENDING)], {"name": "tournaments_status_idx"}),
                ([("bracket.rounds.matches.id", ASCENDING)], {"name": "tournaments_round_matches_idx"}),
                ([("bracket.winners_bracket.rounds.matches.id", ASCENDING)], {"name": "tournaments_wb_matches_idx"}),
                ([("bracket.losers_bracket.rounds.matches.id", ASCENDING)], {"name": "tournaments_lb_matches_idx"}),
                ([("bracket.groups.rounds.matches.id", ASCENDING)], {"name": "tournaments_group_matches_idx"}),
                ([("bracket.playoffs.rounds.matches.id", ASCENDING)], {"name": "tournaments_playoff_matches_idx"}),
                ([("bracket.grand_final.id", ASCENDING)], {"name": "tournaments_gf_match_idx"}),
            ],
        ),
        (
            "registrations",
            [
                ([("id", ASCENDING)], {"name": "registrations_id_unique", "unique": True}),
                ([("tournament_id", ASCENDING)], {"name": "registrations_tournament_idx"}),
                (
                    [("tournament_id", ASCENDING), ("team_id", ASCENDING)],
                    {
                        "name": "registrations_tournament_team_unique",
                        "unique": True,
                        "partialFilterExpression": {"team_id": {"$exists": True, "$type": "string", "$ne": ""}},
                    },
                ),
                (
                    [("tournament_id", ASCENDING), ("payment_status", ASCENDING), ("payment_expires_at", ASCENDING)],
                    {"name": "registrations_payment_reservation_idx"},
                ),
            ],
        ),
        (
            "payment_transactions",
            [
                ([("id", ASCENDING)], {"name": "payments_id_unique", "unique": True}),
                ([("session_id", ASCENDING)], {"name": "payments_session_unique", "unique": True}),
                ([("registration_id", ASCENDING)], {"name": "payments_registration_idx"}),
            ],
        ),
        (
            "schedule_proposals",
            [
                ([("id", ASCENDING)], {"name": "schedule_id_unique", "unique": True}),
                ([("match_id", ASCENDING)], {"name": "schedule_match_idx"}),
            ],
        ),
        (
            "match_setups",
            [
                ([("id", ASCENDING)], {"name": "match_setups_id_unique", "unique": True}),
                ([("tournament_id", ASCENDING), ("match_id", ASCENDING)], {"name": "match_setups_tournament_match_unique", "unique": True}),
            ],
        ),
        (
            "admin_settings",
            [
                ([("key", ASCENDING)], {"name": "admin_settings_key_unique", "unique": True}),
            ],
        ),
        (
            "notifications",
            [
                ([("id", ASCENDING)], {"name": "notifications_id_unique", "unique": True}),
                ([("user_id", ASCENDING), ("read", ASCENDING)], {"name": "notifications_user_read_idx"}),
            ],
        ),
        (
            "comments",
            [
                ([("id", ASCENDING)], {"name": "comments_id_unique", "unique": True}),
                ([("target_type", ASCENDING), ("target_id", ASCENDING), ("created_at", ASCENDING)], {"name": "comments_target_created_idx"}),
            ],
        ),
    ]

    for collection_name, indexes in index_specs:
        for keys, options in indexes:
            await _safe_create_index(collection_name, keys, **options)

    log_info("db.index.ensure.done", "MongoDB index ensure finished")

# --- App Setup ---

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
    await ensure_indexes()
    await seed_games()
    await seed_admin()
    logger.info("eSports Tournament System started")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
