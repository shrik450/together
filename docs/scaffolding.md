# Scaffolding Plan

This document outlines the scaffolding layers needed to build the app.

## Layer 1: Core App Structure

The foundation that everything else builds on:

- Litestar app entry point with explicit module registration pattern
- Database setup (SQLAlchemy + SQLite, session factory, Base class)
- Templating (Jinja2 with shared + module template paths)
- Static file serving

## Layer 2: Framework Features (Implemented)

Shared infrastructure that modules depend on:

- **User auth**: User model, login/logout routes, session middleware,
  `current_user` dependency, `require_auth` guard
  - Session storage via signed cookies (itsdangerous)
  - Password hashing via Argon2
  - CLI command for user creation: `uv run python cli.py create-user <username>`
- **Scheduler**: APScheduler 4.x AsyncScheduler with SQLite data store
  - Lifespan integration for automatic start/stop
  - `add_schedule()` function for modules to register cron jobs
- **App Shell**: Responsive layout with sidebar (wide) and breadcrumb bar (narrow)
  - CSS framework with design tokens, dark mode, and component styles
  - NavItem registration via central NAV_ITEMS list
  - PageAction and Breadcrumb dataclasses for UI context

Note: Settings is a module concern, not framework. Each module manages its own
settings table and UI.

### Layer 2 File Structure

```
framework/
├── __init__.py
├── ui.py                   # PageAction, Breadcrumb dataclasses
├── nav.py                  # NavItem, NAV_ITEMS list
├── auth/
│   ├── __init__.py         # Module exports
│   ├── models.py           # User model
│   ├── handlers.py         # Login/logout routes
│   ├── middleware.py       # Session middleware
│   ├── dependencies.py     # current_user provider
│   └── guards.py           # require_auth guard
└── scheduler/
    ├── __init__.py         # Module exports
    └── setup.py            # AsyncScheduler setup

templates/
├── base.html               # Full app shell
└── auth/
    └── login.html          # Login form

static/
└── style.css               # Full CSS framework
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
   - Has a placeholder module mounted at `/example/`

2. **Layer 2** - Add framework features:
   - Auth (can log in, protected routes work)
   - Scheduler (can register and run a test job)

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
├── schema.sql
├── framework/
│   ├── __init__.py
│   └── db/
│       └── __init__.py
├── modules/
│   └── __init__.py
├── templates/
│   └── base.html
└── static/
    └── style.css
```
