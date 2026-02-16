# eSports Tournament Bracket System - PRD

## Problem Statement
Complete eSports Tournament Bracket System with tournament creation, dynamic animated brackets, payment integration, pre-built game database, registration/check-in, user accounts, team management, comments, notifications, admin panel, and live bracket display.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: React + Tailwind CSS + Shadcn UI + Framer Motion
- **Database**: MongoDB (collections: games, tournaments, registrations, payment_transactions, users, teams, comments, notifications, schedule_proposals, admin_settings)
- **Payment**: Stripe (test key integrated)
- **Auth**: JWT (python-jose + bcrypt)

## User Personas
- **Admin**: Manages tournaments, games, users, payment settings (admin@arena.gg / admin123)
- **Tournament Organizers**: Create & manage tournaments, set parameters, enter scores
- **Players/Teams**: Register with accounts, create teams, join tournaments, comment
- **Spectators**: View live bracket updates

## Core Requirements
- Tournament CRUD with full parametrization
- 14 pre-built games (CoD, FIFA, RL, CS2, Valorant, LoL, Dota 2, Mario Kart, SSB, Fortnite, Apex, OW2, SF6, Tekken 8)
- Game management (add/edit/delete custom games)
- Single Elimination, Double Elimination, Round Robin bracket types
- Player/Team registration with user accounts
- Check-in system
- Score entry with winner propagation
- Stripe payment for paid tournaments
- User authentication (JWT)
- Team management (create/delete teams, invite/remove members)
- Comments on tournaments and matches
- In-app notifications (bell icon with unread count)
- Match scheduling (time proposals)
- Admin panel with dashboard, user management, payment/SMTP settings
- German UI language

## What's Implemented (2026-02-17)

### Phase 0 - MVP (Completed 2026-02-16)
- Full backend API with 15+ endpoints
- 14 pre-seeded games with modes and platforms
- Tournament creation with all parameters
- Anonymous registration system
- Check-in system
- Single/Double Elimination & Round Robin brackets
- Score updates with winner propagation
- Stripe payment integration
- Full German UI with dark gaming theme

### Phase 1 - User System & Community (Completed 2026-02-17)
- **Auth System**: JWT-based login/register with bcrypt password hashing
- **Admin Seed**: Admin user auto-created on startup (admin@arena.gg / admin123)
- **Team Management**: Create/delete teams, invite/remove members by email
- **Comment System**: Comments on tournaments with author info & timestamps
- **Notification System**: In-app bell with unread count, auto-notifications on comments/scheduling
- **Match Scheduling**: Time proposals with accept/reject workflow
- **Admin Panel**: Dashboard stats, tournament/game/user management, payment & SMTP settings
- **Auth-aware UI**: Navbar shows login state, Teams/Admin links, notification bell
- **Protected Routes**: Teams & Admin pages require authentication

## Prioritized Backlog

### P1 (High)
- PayPal integration (prepared in Admin Panel settings)
- E-Mail notifications via SMTP (prepared in Admin Panel settings)
- Regelwerk-Einbettung verbessern

### P2 (Medium)
- Bracket SVG connecting lines improvement
- Real-time updates (WebSocket for live bracket changes)
- Embeddable widget/iframe support
- Profile page for users

### P3 (Low)
- Swiss bracket type
- Tournament seeding control
- Participant management (kick, reorder seeds)
- Export bracket as image/PDF
- Tournament templates
- Recurring tournaments
- Player statistics & history
- Leaderboards
- Multiple languages
