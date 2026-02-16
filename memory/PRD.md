# eSports Tournament Bracket System - PRD

## Problem Statement
Complete eSports Tournament Bracket System with full access control (admin/player roles), dynamic animated brackets with Bezier curve connectors, payment integration (Stripe + PayPal prepared), pre-built game database, user accounts, team management with join codes/leaders/sub-teams, score submission by teams with auto-confirm/dispute resolution, comments, notifications, admin panel, profile pages, embeddable widget, and markdown-rendered rules.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: React + Tailwind CSS + Shadcn UI + Framer Motion
- **Database**: MongoDB (collections: games, tournaments, registrations, payment_transactions, users, teams, comments, notifications, schedule_proposals, admin_settings, score_submissions)
- **Payment**: Stripe (integrated), PayPal (prepared in admin settings)
- **Auth**: JWT (python-jose + bcrypt)
- **Email**: SMTP (prepared in admin settings)

## User Roles
- **Admin** (role: "admin"): Full access — create/edit/delete tournaments & games, generate brackets, resolve score disputes, manage users/settings
- **Spieler** (role: "user"): Register for tournaments, create/manage teams, submit scores, comment, receive notifications

## Core Requirements (All Implemented)
- Tournament CRUD (admin-only)
- 14+ pre-built games with modes and platforms
- Single/Double Elimination, Round Robin bracket types with Bezier curve SVG connectors
- Player/Team registration
- Check-in system
- Score submission system (both teams submit, auto-confirm if matching, admin resolves disputes)
- Disqualification support
- Stripe payment integration
- JWT authentication with admin seed
- Team management (join codes, leaders, sub-teams)
- Comments on tournaments and matches
- In-app notifications (bell icon with unread count)
- Match scheduling (time proposals)
- Admin panel with dashboard, user/tournament/game management, payment & SMTP settings
- Profile pages with stats, teams, tournament history
- Embeddable widget (iframe) for external sites
- Markdown-rendered tournament rules
- German UI

## What's Implemented

### Phase 0 - MVP (Completed 2026-02-16)
- Full backend API, 14 pre-seeded games, tournament CRUD, anonymous registration
- Bracket visualization, Stripe payment, dark gaming UI

### Phase 1 - User System & Community (Completed 2026-02-17)
- JWT Auth, Admin seed, Team management, Comments, Notifications, Match scheduling
- Admin Panel, Auth-aware UI, Protected routes

### Phase 1.5 - Access Control & Advanced Features (Completed 2026-02-17)
- **Admin-only access control**: Tournaments, games, brackets, status changes → admin only
- **Score submission system**: Both teams submit scores, auto-confirm if matching, admin resolves disputes with disqualification option
- **Team enhancements**: Join codes (6-char), leaders, sub-teams, owner-only code visibility
- **Profile page**: User stats (wins/losses/winrate), teams, tournament history
- **Widget**: Standalone iframe-embeddable tournament view
- **Bracket improvements**: Bezier curve SVG connecting lines between rounds
- **Markdown rules**: Rich text rendering for tournament rules
- **PayPal prepared**: Admin settings fields for PayPal Client ID & Secret
- **SMTP prepared**: Admin settings fields for SMTP host/port/user/password
- **Email sending**: Backend function sends email when SMTP configured

## Prioritized Backlog

### P1 (High)
- PayPal actual checkout flow (needs user to provide PayPal sandbox keys)
- E-Mail notifications triggering (needs SMTP credentials configured)

### P2 (Medium)
- Real-time updates (WebSocket for live bracket changes)
- Swiss bracket type
- Tournament seeding control
- Participant management (kick, reorder seeds)

### P3 (Low)
- Export bracket as image/PDF
- Tournament templates & recurring tournaments
- Player statistics history & leaderboards
- Multiple languages
