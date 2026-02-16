# eSports Tournament Bracket System - PRD

## Problem Statement
Complete eSports Tournament Bracket System with tournament creation, dynamic animated brackets, payment integration, pre-built game database, registration/check-in, and live bracket display.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: React + Tailwind CSS + Shadcn UI + Framer Motion
- **Database**: MongoDB (collections: games, tournaments, registrations, payment_transactions)
- **Payment**: Stripe (test key integrated)

## User Personas
- **Tournament Organizers**: Create & manage tournaments, set parameters, enter scores
- **Players/Teams**: Register with name/email, check-in, view brackets
- **Spectators**: View live bracket updates

## Core Requirements
- Tournament CRUD with full parametrization
- 14 pre-built games (CoD, FIFA, RL, CS2, Valorant, LoL, Dota 2, Mario Kart, SSB, Fortnite, Apex, OW2, SF6, Tekken 8)
- Game management (add/edit/delete custom games)
- Single Elimination, Double Elimination, Round Robin bracket types
- Player/Team registration (name + email, no auth required)
- Check-in system
- Score entry with winner propagation
- Stripe payment for paid tournaments
- German UI language

## What's Implemented (2026-02-16)
- Full backend API with 15+ endpoints
- 14 pre-seeded games with modes and platforms
- Tournament creation with all parameters (game, mode, team size, max participants, bracket type, best of, entry fee, prize pool, rules)
- Registration system (name + email)
- Check-in system
- Single Elimination bracket generation with auto-bye handling
- Double Elimination bracket generation
- Round Robin bracket generation
- Score updates with winner propagation to next rounds
- Stripe payment integration for paid tournaments
- Homepage with hero, stats, featured tournaments
- Tournaments list with search and filters
- Tournament detail page with Bracket/Participants/Info tabs
- Bracket visualization component
- Games page with category filters and poster-style cards
- Create Tournament form with game/mode selection
- Full German UI
- Dark gaming theme (Obsidian + Neon Yellow)

## Prioritized Backlog
### P0 (Critical)
- None remaining for MVP

### P1 (High)
- PayPal integration (requires user's PayPal API keys)
- Bracket connecting lines (SVG curves between rounds)
- Real-time updates (WebSocket for live bracket changes)
- Embeddable widget/iframe support

### P2 (Medium)
- Swiss bracket type
- Tournament seeding control
- Participant management (kick, reorder seeds)
- Match scheduling with times
- Export bracket as image/PDF
- Email notifications for participants

### P3 (Low)
- Tournament templates
- Recurring tournaments
- Player statistics & history
- Leaderboards
- Admin authentication
- Multiple languages
