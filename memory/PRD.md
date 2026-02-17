# eSports Tournament Bracket System - PRD

## Problem Statement
Complete eSports Tournament Bracket System with full access control (admin/player roles), dynamic animated brackets, payment integration (Stripe + PayPal), scheduling system with auto-reminders, pre-built game database, user accounts, team management, score submission, and comprehensive FAQ.

## Latest Update (2026-02-17)

### New Features Implemented
1. **Automatic Scheduling Reminder System**
   - POST `/api/tournaments/{id}/send-scheduling-reminders` - Send reminders to teams with unscheduled matches
   - Email notifications 24h before scheduling window ends
   - In-app notifications for team owners
   - Default time warning in emails (e.g., "Wednesday 19:00 will be used")

2. **PayPal Payment Integration**
   - POST `/api/payments/paypal/create-order` - Create PayPal payment order
   - POST `/api/payments/paypal/capture-order` - Capture approved payment
   - GET `/api/payments/paypal/config` - Frontend configuration
   - Admin Panel: PayPal setup help with developer.paypal.com link

3. **Extended FAQ System (10 Detailed Entries)**
   - How to use the system as new user
   - Team vs Solo tournaments
   - Matchday scheduling process
   - Payment and check-in help
   - Scheduling workflow explanation
   - Sub-teams explanation
   - Check-in process
   - Tournament formats overview
   - Score submission guide
   - Notification system

4. **Admin Panel Improvements**
   - PayPal configuration help section
   - SMTP configuration help (Gmail, Outlook, custom server)
   - Auto-Termine button on tournament detail page
   - Erinnerungen senden button for scheduling reminders

5. **Auto-Scheduling System**
   - Default match day/hour settings per tournament
   - Auto-assign default times when teams don't agree
   - POST `/api/tournaments/{id}/auto-schedule-unscheduled`
   - GET `/api/tournaments/{id}/scheduling-status`

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: React + Tailwind CSS + Shadcn UI + Framer Motion
- **Database**: MongoDB
- **Payment**: Stripe (integrated) + PayPal (integrated)
- **E-Mail**: SMTP (configurable in Admin Panel)

## User Personas
1. **Admin** - Full control over tournaments, settings, payments
2. **Team Owner** - Create teams, manage members, schedule matches
3. **Team Leader** - Submit scores, propose match times
4. **Player** - Join teams, participate in tournaments

## Core Features (Implemented)

### Tournament System
- Multiple bracket types: Single/Double Elimination, Round Robin, League, Group Stage, Swiss, Battle Royale
- Configurable matchday intervals and windows
- Auto-scheduling with default day/hour settings
- Scoring system with customizable points

### Team Management
- Main teams with sub-teams
- Join codes for membership
- Owner/Leader/Member roles

### Match Scheduling System
- Teams propose times via Match Hub
- Accept/counter-propose workflow
- Default time applied if no agreement
- Admin can send reminders and auto-schedule

### Payment System
- **Stripe**: Credit card payments
- **PayPal**: Alternative payment method
- Entry fee management
- Payment status tracking

### Admin Panel
- User/Team/Tournament management
- SMTP configuration with provider guides
- PayPal/Stripe setup with help sections
- FAQ management

## API Endpoints (New)

### Scheduling
- `GET /api/tournaments/{id}/scheduling-status` - Overview of scheduled/unscheduled matches
- `POST /api/tournaments/{id}/auto-schedule-unscheduled` - Auto-assign default times
- `POST /api/tournaments/{id}/send-scheduling-reminders` - Send reminder emails

### PayPal
- `POST /api/payments/paypal/create-order` - Create payment order
- `POST /api/payments/paypal/capture-order` - Capture approved payment
- `GET /api/payments/paypal/config` - Frontend configuration

### Tournament Config
- `default_match_day` - Default day for auto-scheduling
- `default_match_hour` - Default hour (0-23)
- `auto_schedule_on_window_end` - Enable auto-scheduling

## Demo Data
- 13 Tournament Types
- 8 Main Teams with Sub-Teams
- 18 Demo Users
- 14 Games

### Demo Credentials
- `admin@arena.gg / admin123` - Main admin
- `demo.admin@arena.gg / demo123` - Demo admin

## Prioritized Backlog

### P0 (Completed)
- ✅ Auto-Scheduling System
- ✅ Scheduling Reminder Emails
- ✅ PayPal Integration
- ✅ Extended FAQ (10 entries)
- ✅ Admin Panel Improvements

### P1 (High Priority - Next)
- SMTP actual sending (requires user's SMTP credentials)
- PayPal Live Mode (requires user's PayPal credentials)
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
- PayPal sandbox mode by default

## Configuration Required
1. **SMTP**: Set in Admin Panel → Settings → SMTP
2. **PayPal**: Set in Admin Panel → Settings → PayPal (Client ID + Secret from developer.paypal.com)
3. **Stripe**: Already configured via environment variables
