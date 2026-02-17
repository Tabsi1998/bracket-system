# eSports Tournament Bracket System - PRD

## Problem Statement
Complete eSports Tournament Bracket System with full sub-games/maps support, map ban/vote system, team profiles with social media, and comprehensive scheduling.

## Latest Update (2026-02-17)

### Features Implemented in This Session

#### 1. Sub-Games System (Smart Implementation)
- **Only where sensible**: 
  - CoD: Black Ops 6, Modern Warfare 3 (different games with different maps)
  - FIFA: EA FC 24, EA FC 25 (different yearly releases)
- **Direct Maps (no sub-games)**:
  - CS2: 7 Maps directly on game
  - Valorant: 9 Maps directly on game

#### 2. Team Profile Pages
- Complete team detail page with:
  - Banner and Logo display
  - Bio/Description
  - Member list with roles (Owner, Leader, Member)
  - Sub-teams list
  - Tournament participation history
  - Social Media Links (FontAwesome icons)

#### 3. FontAwesome Integration
- CDN loaded in index.html
- Social icons: Discord, Twitter, Instagram, Twitch, YouTube, Website
- Used in TeamDetailPage

#### 4. SMTP Improvements
- New `/api/admin/smtp-config` endpoint for status check
- New `/api/admin/smtp-test` endpoint with detailed diagnostics
- Better error messages showing what's missing
- Test email includes config details for debugging

#### 5. Homepage for Players
- Changed "So funktioniert es" from admin-focused to player-focused:
  - Step 1: Register & Join Team
  - Step 2: Find & Join Tournament
  - Step 3: Check-in & Play

#### 6. Team Tournaments API
- `GET /api/teams/{id}/tournaments` - Public endpoint showing tournament history

## Architecture
- **Backend**: FastAPI + MongoDB
- **Frontend**: React + Tailwind CSS + FontAwesome + Shadcn UI

## API Endpoints (New/Updated)

### SMTP
- `GET /api/admin/smtp-config` - Get SMTP configuration status
- `POST /api/admin/smtp-test` - Send test email with diagnostics

### Teams
- `GET /api/teams/{id}/tournaments` - Get team's tournament participation

### Games & Maps
- CS2 and Valorant have maps directly on game object
- CoD and FIFA have sub_games with maps per sub-game

## Data Models

### Game (Updated)
```json
{
  "id": "...",
  "name": "Counter-Strike 2",
  "maps": [...],  // Direct maps for games without sub-games
  "sub_games": [...] // Only for CoD, FIFA
}
```

### Team (Profile Fields)
```json
{
  "id": "...",
  "name": "Team Name",
  "tag": "TAG",
  "bio": "Team description...",
  "logo_url": "...",
  "banner_url": "...",
  "discord_url": "https://discord.gg/...",
  "twitter_url": "https://twitter.com/...",
  "instagram_url": "https://instagram.com/...",
  "twitch_url": "https://twitch.tv/...",
  "youtube_url": "https://youtube.com/...",
  "website_url": "https://..."
}
```

## Test Results
- Backend: 94%
- Frontend: 100%
- Integration: 100%

## Demo Data
- 14 Tournaments (including CoD BO6 4v4 S&D Liga)
- 8+ Teams with sub-teams
- 14 Games (CoD with 2 sub-games, FIFA with 2 sub-games)

## Configuration Required

### SMTP (for email notifications)
Set in Admin Panel → Settings → SMTP:
- `smtp_host`: SMTP server (e.g., smtp.gmail.com)
- `smtp_port`: Port (587 for STARTTLS, 465 for SSL)
- `smtp_user`: Username/Email
- `smtp_password`: Password (Gmail: App-Password!)
- `smtp_from_email`: Sender address
- `smtp_use_starttls`: true/false
- `smtp_use_ssl`: true/false

### PayPal (optional)
Set in Admin Panel → Settings → PayPal:
- `paypal_client_id`: From developer.paypal.com
- `paypal_secret`: From developer.paypal.com
- `paypal_mode`: sandbox/live

## Backlog

### P0 (Completed)
- ✅ Sub-Games only where sensible
- ✅ Team Profile Pages with Social Icons
- ✅ FontAwesome Integration
- ✅ SMTP Test & Diagnostics
- ✅ Player-focused Homepage

### P1 (Next)
- Actual SMTP configuration (requires credentials)
- Image upload for maps/games (admin)
- Simplified tournament/match creation forms

### P2 (Medium)
- Map images
- Tournament templates
- Automatic reminder cronjob

### P3 (Low)
- i18n / Multiple languages
- Statistics history
