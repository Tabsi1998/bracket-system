# eSports Tournament Bracket System - PRD

## Problem Statement
Complete eSports Tournament Bracket System with full access control (admin/player roles), dynamic animated brackets with Bezier curve connectors, payment integration (Stripe + PayPal prepared), pre-built game database, user accounts, team management with join codes/leaders/sub-teams, score submission by teams with auto-confirm/dispute resolution, comments, notifications, admin panel, profile pages, embeddable widget, markdown-rendered rules, and one-command installer for Ubuntu.

## Latest Update (2026-02-17)
### System Analysis & Improvements
- **Auto-Scheduling System**: New feature where matches get automatic default times (e.g., Wednesday 19:00) if teams don't agree on a time
- **Extended Demo Data**: More realistic tournament descriptions, rules, and team setups
- **SMTP Help Improvements**: Admin panel now shows configuration guides for Gmail, Outlook, custom servers
- **Matchday Overview**: Better structured matchday hierarchy display

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: React + Tailwind CSS + Shadcn UI + Framer Motion
- **Database**: MongoDB (collections: games, tournaments, registrations, payment_transactions, users, teams, comments, notifications, schedule_proposals, admin_settings, score_submissions, match_setups)
- **Payment**: Stripe (integrated), PayPal (prepared in admin settings)
- **E-Mail**: SMTP (configurable in Admin Panel)

## User Personas
1. **Admin** - Full control: Create tournaments, manage games, approve scores, configure settings
2. **Team Owner** - Create teams, manage sub-teams, join codes, promote leaders
3. **Team Leader** - Manage team members, submit scores, propose match times
4. **Player** - Join teams, participate in tournaments, check-in

## Core Features (Implemented)

### Tournament System
- Multiple bracket types: Single/Double Elimination, Round Robin, League, Group Stage, Group+Playoffs, Swiss, Ladder, King of Hill, Battle Royale
- Configurable matchday intervals and windows
- **NEW**: Auto-scheduling with default day/hour settings
- Scoring system with customizable points (win/draw/loss)
- Tiebreaker configuration

### Team Management
- Main teams with sub-teams for tournament participation
- Join codes for team membership
- Owner/Leader/Member roles
- Profile inheritance from parent team

### Match Scheduling System
- Teams propose times via Match Hub
- Other team accepts or counter-proposes
- **NEW**: Default time applied if no agreement (configurable per tournament)
- Window-based scheduling for league formats

### Admin Panel
- Dashboard with statistics
- User/Team/Tournament management
- SMTP configuration with provider guides
- Payment provider setup (Stripe/PayPal)
- FAQ management

## API Endpoints (Key New Additions)

### Scheduling
- `GET /api/tournaments/{id}/scheduling-status` - Overview of scheduled/unscheduled matches
- `POST /api/tournaments/{id}/auto-schedule-unscheduled` - Auto-assign default times to all unscheduled matches

### Tournament Config
- `default_match_day` - Default day for auto-scheduling (monday-sunday)
- `default_match_hour` - Default hour (0-23)
- `auto_schedule_on_window_end` - Enable auto-scheduling

## Demo Data
- **13 Tournament Types**: Various bracket types and statuses
- **8 Main Teams**: ARES, NOVA, PULSE, TITAN, VORTEX, ORBIT
- **14 Sub-Teams**: For tournament participation
- **18 Demo Users**: Including demo admin
- **14 Games**: Call of Duty, FIFA, Rocket League, CS2, Valorant, LoL, etc.

### Demo Credentials
- `admin@arena.gg / admin123` - Main admin
- `demo.admin@arena.gg / demo123` - Demo admin
- `demo.alpha1@arena.gg / demo123` - Demo player

## Prioritized Backlog

### P0 (Completed in this session)
- ✅ Auto-Scheduling System for unscheduled matches
- ✅ Extended Demo Data with realistic rules/descriptions
- ✅ SMTP Configuration Help in Admin Panel
- ✅ Tournament creation with default scheduling options

### P1 (High Priority - Next)
- SMTP actual sending (requires user's SMTP credentials)
- PayPal actual checkout integration
- WebSocket real-time updates

### P2 (Medium)
- Tournament seeding management
- Export bracket as image/PDF
- Tournament templates

### P3 (Low)
- Multiple languages (i18n)
- Player statistics history
- Leaderboards

## Technical Notes
- All timestamps in UTC ISO format
- MongoDB ObjectId exclusion in API responses
- JWT authentication with 7-day expiry
- CORS enabled for frontend integration
