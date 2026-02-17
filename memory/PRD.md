# eSports Tournament Bracket System - PRD

## Original Problem Statement
Comprehensive eSports tournament platform with bracket management, team features, and admin tools.

## Core Requirements
- Tournament creation with various bracket types (League, Swiss, Single/Double Elimination, Battle Royale)
- Team management with sub-teams, member roles, and social profiles
- Match scheduling with proposal system and auto-scheduling defaults
- Map veto/ban system for competitive matches
- Games with Sub-Games (Versionen) and Maps hierarchy
- Admin panel for managing games, users, SMTP, PayPal, FAQ
- Public access for guests to view matches and tournaments

## Architecture
- **Frontend**: React + TailwindCSS + Shadcn/UI, served on port 3000
- **Backend**: FastAPI + MongoDB (motor async driver), served on port 8001
- **Auth**: JWT-based authentication
- **Cron**: APScheduler for daily reminder jobs
- **Routing**: All API routes prefixed with /api

## What's Been Implemented

### Phase 1 - Core Platform (Complete)
- User auth (register, login, JWT)
- Tournament CRUD with bracket generation
- Match scheduling with proposals and auto-scheduling
- Score submission and admin approval system
- Team creation and management with sub-teams

### Phase 2 - Games/Sub-Games/Maps System (Complete - Feb 2026)
- Full game hierarchy: Game → Sub-Game (Version) → Maps
- CRUD endpoints for sub-games: POST/PUT/DELETE /api/games/{id}/sub-games
- CRUD endpoints for maps: POST/PUT/DELETE /api/games/{id}/sub-games/{sg_id}/maps
- GamesPage completely overhauled with expandable cards showing modes, sub-games, maps
- Admin can add/edit/delete sub-games and maps through intuitive UI
- Map pool selection in tournament creation based on selected sub-game
- Map veto system shows proper map names (not IDs)

### Phase 3 - Admin & UX Improvements (Complete - Feb 2026)
- Image upload: POST /api/upload/image + GET /api/uploads/{filename}
- Image upload UI in map management dialogs
- SMTP improvements: async sending, 30s timeout, thread-based execution
- Improved SMTP test endpoint with detailed config diagnosis
- Structured logging added to critical operations (auth, tournament creation, score submission)
- Cron job: Daily automated reminders via APScheduler at 10:00 UTC
- Public match endpoint: GET /api/matches/{id}/public for guest access
- Guest-friendly MatchDetailPage with fallback to public endpoint

### Phase 4 - Team & Content (Complete)
- Team detail page with biography, members, social links (FontAwesome icons)
- Tournament history tab on team profile
- Homepage updated for players and guests
- FAQ system in admin panel

## Data Models
- `games`: id, name, short_name, category, modes[], sub_games[{id, name, maps[]}], platforms[]
- `tournaments`: id, name, game_id, sub_game_id, bracket_type, bracket{}, map_pool[], status
- `users`: id, email, username, password_hash, role
- `teams`: id, name, tag, owner_id, members[], social links
- `map_vetos`: match_id, map_pool[], banned_maps[], picked_maps[], status, history[]
- `score_submissions`: tournament_id, match_id, side, score1, score2

## Key API Endpoints
- POST /api/auth/register, /api/auth/login
- GET/POST /api/games, GET/PUT/DELETE /api/games/{id}
- POST/PUT/DELETE /api/games/{id}/sub-games/{sg_id}
- POST/PUT/DELETE /api/games/{id}/sub-games/{sg_id}/maps/{map_id}
- POST /api/upload/image, GET /api/uploads/{filename}
- GET/POST /api/tournaments, GET /api/tournaments/{id}
- POST /api/tournaments/{id}/generate-bracket
- GET /api/matches/{id}/public (no auth)
- GET /api/matches/{id}/map-veto
- POST /api/admin/smtp-test
- GET /api/teams/{id}, GET /api/teams/{id}/tournaments

## Backlog
### P1
- None currently

### P2
- Map images in veto UI (show uploaded images during ban/pick)

### P3
- PayPal live integration (currently MOCKED)
- i18n / multi-language support
- Statistics/leaderboard history

## Test Reports
- /app/test_reports/iteration_8.json - Sub-games/Maps CRUD: 100% pass
- /app/test_reports/iteration_9.json - Guest access, image upload, cron, SMTP: 100% pass
