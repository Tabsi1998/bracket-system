# eSports Tournament Bracket System - PRD

## Problem Statement
Complete eSports Tournament Bracket System with Sub-Games (e.g., Black Ops 6, MW3), Maps, Map Ban/Vote System, full scheduling with matchday windows, and comprehensive demo data.

## Latest Update (2026-02-17)

### Major Features Implemented

#### 1. Sub-Games System
Games can now have sub-games (versions) with their own maps:
- **Call of Duty**: Black Ops 6 (8 maps), Modern Warfare 3 (6 maps)
- **CS2**: Premier (7 maps)
- **Valorant**: Ranked Competitive (9 maps)

#### 2. Map System
- Maps belong to Sub-Games
- Maps have game_mode restrictions (e.g., Nuketown supports S&D, Hardpoint, Control)
- Map pool selection when creating tournaments
- Map IDs: `bo6-nuketown`, `cs2-mirage`, `val-ascent`, etc.

#### 3. Map Ban/Vote System
Complete veto system for match setup:
- Teams take turns banning/picking maps
- Configurable pick order: `ban_ban_pick`, `ban_pick_ban`, `alternate`
- Configurable ban count per team
- Full history tracking
- UI in Match Detail Page

#### 4. CoD BO6 4v4 S&D Liga Demo
Complete demonstration tournament:
- 8 Teams: ARES Alpha, NOVA Prime, ARES Bravo, ARES Charlie, PULSE Shadow, TITAN Core, VORTEX Prime, ORBIT Omega
- 7 Spieltage (Matchdays) with weekly windows
- 5 Maps in Pool: Nuketown, Hacienda, Vault, Skyline, Red Card
- Detailed rules and description

## Architecture
- **Backend**: FastAPI + MongoDB
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Database**: MongoDB with collections: games, tournaments, registrations, teams, users, map_vetos, etc.

## API Endpoints (New)

### Sub-Games & Maps
- `GET /api/games/{game_id}/sub-games` - Get all sub-games for a game
- `GET /api/games/{game_id}/sub-games/{sub_game_id}/maps` - Get maps for specific sub-game

### Map Veto
- `GET /api/matches/{match_id}/map-veto` - Get veto state
- `POST /api/matches/{match_id}/map-veto` - Submit ban/pick action
- `POST /api/matches/{match_id}/map-veto/reset` - Admin reset

### Tournament Config (New Fields)
- `sub_game_id` - Which sub-game version
- `sub_game_name` - Display name
- `map_pool` - List of map IDs for this tournament
- `map_ban_enabled` - Enable map banning
- `map_ban_count` - How many maps each team can ban
- `map_vote_enabled` - Enable map voting
- `map_pick_order` - Order of ban/pick actions

## Data Models

### SubGame
```json
{
  "id": "cod-bo6",
  "name": "Black Ops 6",
  "short_name": "BO6",
  "release_year": 2024,
  "active": true,
  "maps": [GameMap]
}
```

### GameMap
```json
{
  "id": "bo6-nuketown",
  "name": "Nuketown",
  "image_url": "",
  "game_modes": ["S&D", "Hardpoint", "Control"]
}
```

### MapVeto
```json
{
  "tournament_id": "...",
  "match_id": "...",
  "map_pool": ["bo6-nuketown", ...],
  "banned_maps": ["bo6-hacienda"],
  "picked_maps": ["bo6-nuketown"],
  "current_turn": "team1",
  "current_action": "pick",
  "action_sequence": [...],
  "action_index": 3,
  "status": "in_progress",
  "history": [...]
}
```

## Demo Data

### Games with Sub-Games
| Game | Sub-Games | Maps |
|------|-----------|------|
| Call of Duty | Black Ops 6, MW3 | 14 total |
| CS2 | Premier | 7 |
| Valorant | Ranked | 9 |

### CoD BO6 4v4 S&D Liga
- **Status**: Live
- **Teams**: 8
- **Spieltage**: 7
- **Map Pool**: Nuketown, Hacienda, Vault, Skyline, Red Card
- **Current Round**: 4 (Feb 17-22)

### Demo Credentials
- `admin@arena.gg / admin123`
- `demo.admin@arena.gg / demo123`

## Test Results
- Backend: 91.7% (11/12 tests)
- Frontend: 85% (core features verified)

## Backlog

### P0 (Completed)
- ✅ Sub-Games System
- ✅ Maps per Sub-Game
- ✅ Map Ban/Vote System
- ✅ CoD Liga Demo with 8 teams and 7 Spieltage

### P1 (High Priority)
- SMTP email sending (requires credentials)
- PayPal live mode (requires credentials)
- Automatic reminder cronjob

### P2 (Medium)
- Map images
- Map statistics
- Tournament templates

### P3 (Low)
- Multiple languages
- Player statistics history
