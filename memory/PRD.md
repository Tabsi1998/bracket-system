# eSports Tournament Bracket System - PRD

## Problem Statement
Complete eSports Tournament Bracket System with full access control (admin/player roles), dynamic animated brackets with Bezier curve connectors, payment integration (Stripe + PayPal prepared), pre-built game database, user accounts, team management with join codes/leaders/sub-teams, score submission by teams with auto-confirm/dispute resolution, comments, notifications, admin panel, profile pages, embeddable widget, markdown-rendered rules, and one-command installer for Ubuntu.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: React + Tailwind CSS + Shadcn UI + Framer Motion
- **Database**: MongoDB (collections: games, tournaments, registrations, payment_transactions, users, teams, comments, notifications, schedule_proposals, admin_settings, score_submissions)
- **Payment**: Stripe (integrated), PayPal (prepared in admin settings)
- **Auth**: JWT (python-jose + bcrypt)
- **Email**: SMTP (prepared in admin settings)
- **Deployment**: Nginx reverse proxy + systemd service + one-command installer

## User Roles
- **Admin** (role: "admin"): Full access
- **Spieler** (role: "user"): Participate, create teams, submit scores, comment

## What's Implemented

### Phase 0 - MVP (2026-02-16)
- Full backend API, 14 pre-seeded games, tournament CRUD, brackets, Stripe

### Phase 1 - User System (2026-02-17)
- JWT Auth, Teams, Comments, Notifications, Match scheduling, Admin Panel

### Phase 1.5 - Access Control & Advanced (2026-02-17)
- Admin-only access, Score submission/dispute system, Team join codes/leaders/sub-teams
- Profile page, Widget, Bezier brackets, Markdown rules, PayPal/SMTP prepared

### Phase 2 - Deployment & Polish (2026-02-17)
- One-command Ubuntu installer (install.sh)
- Clean requirements.prod.txt with minimal dependencies
- Professional README.md with full API docs, architecture, role matrix
- Nginx config, systemd service, SSL instructions
- Full system smoke test (13/13 passed)

## Prioritized Backlog

### P1 (High)
- PayPal actual checkout (needs PayPal sandbox keys)
- E-Mail notifications (needs SMTP credentials in Admin Panel)

### P2 (Medium)
- WebSocket real-time updates
- Swiss bracket type
- Tournament seeding & participant management

### P3 (Low)
- Export bracket as image/PDF
- Tournament templates, recurring tournaments
- Leaderboards, player statistics history
- Multiple languages
