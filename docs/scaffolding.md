# Scaffolding Plan

This document outlines the scaffolding layers needed to build the app.

## Progress

Last updated: 2026-03-29

| Layer | Status | Summary |
| --- | --- | --- |
| Layer 1: Core App Structure | ✅ Complete | All components implemented |
| Layer 2: Framework Features | ✅ Complete | Auth, scheduler scaffolding, and app shell implemented |
| Layer 3: First Module | ❌ Not Started | — |

### Layer 1 Details

| Component | Status |
| --- | --- |
| Litestar app entry point | ✅ |
| Module registration pattern | ✅ |
| Database setup (SQLAlchemy + SQLite) | ✅ |
| Templating (Jinja2) | ✅ |
| Static file serving | ✅ |

### Layer 2 Details

| Component | Status | Notes |
| --- | --- | --- |
| **User Auth** | ✅ | Implemented in `framework/auth/` and `together/__main__.py` |
| ↳ User model | ✅ | `framework/auth/models.py`; schema now comes from Alembic migrations |
| ↳ Login/logout routes | ✅ | `framework/auth/handlers.py` |
| ↳ Session middleware | ✅ | `framework/auth/middleware.py` |
| ↳ `current_user` dependency | ✅ | `framework/auth/dependencies.py` |
| ↳ `require_auth` guard | ✅ | `framework/auth/guards.py` |
| ↳ CLI user creation | ✅ | `uv run python -m together create-user <username>` |
| **Scheduler** | ✅ | Implemented in `framework/scheduler/` and wired into `app.py` |
| ↳ AsyncScheduler setup | ✅ | APScheduler 4.x remains an intentional choice despite still being alpha |
| ↳ Lifespan integration | ✅ | `scheduler_lifespan()` registered on the app |
| ↳ `add_schedule()` function | ✅ | `framework.scheduler.add_schedule()` available for module registration |
| **App Shell** | ✅ | |
| ↳ `NavNode` / `PageAction` dataclasses | ✅ | `framework/ui.py` |
| ↳ `register_nav_node()` | ✅ | `framework/ui.py` |
| ↳ Responsive layout (sidebar/breadcrumb) | ✅ | `templates/base.html` |
| ↳ CSS framework | ✅ | `static/style.css` |

## Layer 1: Core App Structure ✅

The foundation that everything else builds on:

- Litestar app entry point with explicit module registration pattern
- Database setup (Advanced Alchemy + async SQLite, session factory, Base class)
- Templating (Jinja2 with shared + module template paths)
- Static file serving

## Layer 2: Framework Features ✅

Shared infrastructure that modules depend on:

- **User auth**: User model, login/logout routes, session middleware,
  `current_user` dependency, `require_auth` guard
  - Session storage via signed cookies (itsdangerous)
  - Password hashing via Argon2
  - CLI command for user creation: `uv run python -m together create-user <username>`
- **Scheduler**: APScheduler 4.x AsyncScheduler with SQLite data store
  - Lifespan integration for automatic start/stop
  - `add_schedule()` function for modules to register cron jobs
  - Scheduler infrastructure is scaffolded; concrete schedules are expected to be
    registered by modules in later layers
  - APScheduler 4.x is intentional even though it is still alpha; we prefer its
    async-native design over the stable 3.x line for this app
- **App Shell**: Responsive layout with sidebar (wide) and breadcrumb bar (narrow)
  - CSS framework with design tokens, dark mode, and component styles
  - `NavNode` registration via `register_nav_node()` during module registration
  - `PageAction` and `NavNode` dataclasses for UI context (see `docs/ui_design.md`)

Note: Settings is a module concern, not framework. Each module manages its own
settings table and UI.

### Layer 2 File Structure

```
framework/
├── __init__.py
├── db/
│   ├── __init__.py         # Database config, Base class, async DB helpers
│   └── engine.py           # Shared SQLite engine / PRAGMA wiring
├── ui.py                   # PageAction, NavNode dataclasses, register_nav_node()
├── auth/
│   ├── __init__.py         # Module exports
│   ├── models.py           # User model
│   ├── handlers.py         # Login/logout routes
│   ├── middleware.py       # Session middleware
│   ├── dependencies.py     # current_user provider
│   ├── guards.py           # require_auth guard
│   └── session.py          # Session config and cookie signing helpers
└── scheduler/
    ├── __init__.py         # Module exports
    └── service.py          # AsyncScheduler setup and lifecycle

templates/
├── base.html               # Full app shell
└── auth/
    ├── base.html           # Auth-specific base template
    └── login.html          # Login form

static/
├── style.css               # Full CSS framework
└── js/
    └── shell.js            # Shell dropdown behavior
```

## Layer 3: First Module

Build Current Affairs using the patterns established:

- Module structure (`__init__.py`, routes, models, jobs, templates)
- Registration with app
- Module-specific settings table and UI

## Build Order

1. **Layer 1** - Get a working Litestar app that:
   - Serves a "hello world" template
   - Connects to SQLite
   - Has a placeholder home module mounted at `/`

2. **Layer 2** - Add framework features:
   - Auth (can log in, protected routes work)
   - Scheduler infrastructure (modules can register jobs in later layers)

3. **Layer 3** - Build Current Affairs module incrementally:
   - Static entry display (hardcoded data)
   - Database models and real data
   - Entry generation job
   - Quiz and reflection features
   - Settings page

## Files to Create (Layer 1)

```
together/
├── app.py
├── alembic.ini
├── migrations/
├── framework/
│   ├── __init__.py
│   └── db/
│       ├── __init__.py
│       └── engine.py
├── modules/
│   ├── __init__.py
│   └── home/
├── templates/
│   ├── base.html
│   └── auth/
└── static/
    ├── style.css
    └── js/
```
