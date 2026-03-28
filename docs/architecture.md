# Architecture

This document describes the target architecture for the Together app.

## Technology Stack & Conventions

Based on current (2025) best practices for each technology.

### Litestar

- **Version**: 2.x (installed via `litestar[standard]`)
- **Application structure**: Hierarchical - App → Routers → Handlers
- **Modules as Routers**: Each module exports a `Router` that gets mounted on the
  app. Routers contain standalone route handler functions (not Controllers).
- **Why not Controllers?** For a small app, Router + functions is simpler. Routers
  support the same layered config (guards, middleware, dependencies) as Controllers,
  so there's no loss of functionality - just less OOP ceremony.
- **Dependency injection**: Use Litestar's DI system for database sessions, current
  user, etc. Dependencies are declared as function parameters with type hints.
- **Layered config**: Configuration cascades from app → router → handler. Closest
  to handler wins. Set guards/middleware at router level to apply to all handlers.

References:

- [Litestar Applications](https://docs.litestar.dev/latest/usage/applications.html)
- [Litestar Routing Overview](https://docs.litestar.dev/2/usage/routing/overview.html)

### SQLAlchemy

- **Version**: SQLAlchemy 2.0+ via Advanced Alchemy's Litestar integration
- **Session management**: Use `advanced_alchemy.extensions.litestar`
  `SQLAlchemyInitPlugin` with `db_session: AsyncSession` DI
- **Models**: Inherit from `framework.db.Base`, which wraps
  `BigIntAuditBase` and provides integer primary keys plus audit timestamps
- **Session config**: `expire_on_commit=False` with request-scoped async
  autocommit before-send handling
- **SQLite mode**: `TOGETHER_DATABASE_URL` is required and must be an absolute
  `sqlite+aiosqlite` URL, with `connect_args={"autocommit": False}` and
  central PRAGMA setup

References:

- [Litestar SQLAlchemy Plugin](https://docs.litestar.dev/2/usage/databases/sqlalchemy/plugins/sqlalchemy_plugin.html)
- [SQLAlchemy 2.0 Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)

### APScheduler

- **Version**: 4.x (alpha, but async-native design fits Litestar better)
- **Scheduler**: `AsyncScheduler` with AnyIO for native async support
- **Data store**: SQLite for persistence across restarts
- **Registration**: Schedules added via `scheduler.add_schedule()` with explicit
  `id` and `conflict_policy=ConflictPolicy.replace`
- **Lifecycle**: Use as async context manager, integrates with Litestar's lifespan

References:

- [APScheduler 4.x User Guide](https://apscheduler.readthedocs.io/en/master/userguide.html)

### Jinja2 & HTMX

- **Templates**: Configured via `TemplateConfig` with `JinjaTemplateEngine`
- **HTMX**: Use `HTMXPlugin` for HTMX-aware request handling
- **Template responses**: Return `Template(template_name=..., context=...)` from
  handlers
- **Multiple directories**: Template config accepts list of directories (shared
  and module-specific)

References:

- [Litestar Templating](https://docs.litestar.dev/2/usage/templating.html)
- [Litestar HTMX](https://docs.litestar.dev/2/usage/htmx.html)

### UI Framework

The framework provides dataclasses and utilities for consistent UI context:

**PageAction** - Represents a page-level action button:

```python
from framework.ui import PageAction

actions = [
    PageAction(label="Cancel", href="/back", style="secondary"),
    PageAction(label="Save", href="/save", style="primary", method="post"),
]
```

**NavNode** - Represents a navigation node. The app shell uses a unified
navigation model where handlers provide a `nav_stack` (list of levels, where
each level is a list of `NavNode`s). See `docs/ui_design.md` for full details.

```python
from framework.ui import NavNode

@dataclass
class NavNode:
    label: str
    href: str | None = None   # None = current page
    icon: str | None = None   # Optional
```

Handlers pass these to templates via context:

```python
@get("/current-affairs/2026-01-10")
async def entry_page() -> Template:
    return Template(
        template_name="current_affairs/entry.html",
        context={
            "nav_stack": [
                [
                    NavNode(label="Jan 10"),
                    NavNode(label="Jan 9", href="/current-affairs/2026-01-09/"),
                    NavNode(label="Jan 8", href="/current-affairs/2026-01-08/"),
                ],
            ],
            "actions": [PageAction(label="Edit", href="/edit")],
        },
    )
```

The `nav_stack` contains only levels within the module. The shell automatically
prepends the Home level (`/`) and the module's registered `NavNode`.

---

## Design Principles

1. **Explicit over implicit**: Modules explicitly register themselves, their
   models, and their jobs. No autodiscovery or framework magic. The framework
   helps identify when something wasn't registered or was registered incorrectly.

2. **Modules own their concerns**: Settings, configuration, and module-specific
   logic live in the module, not the framework. The framework provides
   infrastructure (database, auth, scheduling) but not policy.

3. **Migration-owned schema**: Alembic migrations are the source of truth for
   database schema changes and fresh database setup.

## Directory Structure

```
together/
├── app.py                 # Litestar app entry point, explicit module registration
├── alembic.ini            # Alembic configuration generated via Litestar CLI
├── together.db            # SQLite database (path configured via env)
├── migrations/            # Alembic environment and revision files
├── framework/             # Shared infrastructure
│   ├── __init__.py
│   ├── auth/              # User auth, sessions
│   ├── db/                # Database config, Base class, async DB helpers
│   ├── ui.py              # PageAction, NavNode, register_nav_node()
│   └── scheduler/         # APScheduler setup
├── modules/               # Feature modules
│   ├── __init__.py
│   ├── current_affairs/
│   ├── eats/
│   └── journal/
├── templates/             # Shared templates (base layout, components)
└── static/                # CSS, JS, images
```

## Module Structure

Each module is a self-contained package:

```
modules/current_affairs/
├── __init__.py            # Exports router and register() function
├── handlers.py            # Route handler functions
├── models.py              # SQLAlchemy models
├── services.py            # Business logic (optional, for complex logic)
├── jobs.py                # Scheduled job functions
└── templates/
    └── current_affairs/   # Module-specific templates
```

---

## Framework Components

### Database (framework/db/__init__.py)

Uses Advanced Alchemy's Litestar integration for async session management:

- `SQLAlchemyInitPlugin` provides `db_session: AsyncSession` automatically
- `Base` is the shared declarative base for app models
- `open_async_session()` and `get_async_engine()` are the sanctioned helpers for
  non-request database access
- SQLite connection behavior is centralized with SQLAlchemy events
- `TOGETHER_DATABASE_URL` is mandatory; there is no implicit local DB path

**Schema management:**

- `migrations/` contains the Alembic environment and revision files
- Fresh databases are created with `uv run litestar database upgrade --no-prompt`
- New schema changes are generated with
  `uv run litestar database make-migrations -m "describe change" --no-prompt`
- `uv run litestar database ...` is the only supported migration interface;
  raw `alembic` commands are intentionally unsupported

### Authentication (framework/auth/)

The framework provides:

- `User` model (id, username, password_hash)
- Login/logout routes
- Session middleware (signed cookies)
- `current_user` dependency for routes
- `require_auth` guard for protected routes

The middleware stores auth state as request metadata, not as a detached ORM
instance. Route dependencies load `User` through the request-scoped session when
needed.

**Known limitations:**

- No CSRF token protection. `SameSite=Lax` cookies and the app's personal
  nature make this acceptable. Cross-site POST attacks could trigger a logout
  but not authenticate or take actions.

**User creation:**

- CLI command: `uv run python -m together create-user <username>`
- No registration UI (just the two of you)

### Scheduler (framework/scheduler/)

Uses APScheduler 4.x `AsyncScheduler` with lifespan integration:

- Scheduler created as async context manager in app lifespan
- SQLite data store for persistence across restarts
- Modules register schedules via `add_schedule()` function during `register()`
- Use `ConflictPolicy.replace` to handle app restarts gracefully

---

## Module Registration

Modules are registered explicitly in `app.py`. Each module exports:

- `router`: A `Router` instance to mount on the app
- `register()`: Function that registers models, schedules, and navigation

Each module's `register()` function:

- Imports any module-specific models before migrations/autogenerate run
- Calls `add_schedule()` for any scheduled jobs
- Calls `register_nav_node()` with the module's top-level `NavNode`
- Raises clear errors if misconfigured

Example:

```python
from framework.scheduler import add_schedule
from framework.ui import NavNode, register_nav_node
from modules.current_affairs.models import Entry, Settings

def register():
    add_schedule("daily-briefing", generate_briefing, cron="0 7 * * *")
    register_nav_node(NavNode(label="Current Affairs", href="/current-affairs/", icon="newspaper"))
```

---

## Templating

- **Shared templates** in `templates/` (base layout, common components)
- **Module templates** in `modules/<name>/templates/<name>/`
- Single Jinja2 environment with search paths for both locations
- Templates use HTMX for interactivity

Template naming convention:

```
{% extends "base.html" %}                        {# shared #}
{% include "current_affairs/entry_card.html" %}  {# module-specific #}
```

## App Shell & Global Navigation

Together uses a shared "app shell" defined by the base template. The shell is
responsible for global navigation and consistent page chrome; modules render
their pages into the main content pane.

> **Note:** This section covers the technical/code aspects of the app shell.
> For UX rationale, visual design, and detailed behavior specifications, see
> `docs/ui_design.md`.

Navigation state is provided via the `nav_stack` context variable. The shell
automatically prepends Home (`/`) and the module's registered `NavNode`. See
`docs/ui_design.md` for the full navigation model specification.

- **Wide viewports (`min-width: 900px`)**: Persistent left sidebar showing all
  modules, with the active module expanded to show the current path and siblings.
- **Narrow viewports**: A breadcrumb bar showing the last two levels, with
  dropdowns for sibling quick-switching.
- **HTMX-friendly shell**: In-app links should be boostable so navigation can
  swap the content pane without re-rendering the whole shell.

---

## Route Conventions

- Auth routes: `/auth/login`, `/auth/logout`
- Module routes: `/<module-name>/...`
  - Current Affairs: `/current-affairs/`, `/current-affairs/<date>/`
  - Eats: `/eats/`, `/eats/<place-id>/`
  - Journal: `/journal/`, `/journal/<entry-id>/`
- Static files: `/static/...`

---

## Error Handling

The framework validates module registration and provides clear errors:

- Missing `register()` function: "Module 'eats' has no register() function"
- Model not inheriting from Base: "Model 'Entry' must inherit from framework Base"
- Schedule registration with invalid trigger: "Schedule 'xyz' has invalid cron
  expression"

---

## Settings

Settings are a module concern, not a framework concern. Each module manages its
own settings:

- Stored in module-specific database tables
- Module provides its own settings UI at `/<module-name>/settings`
- No framework-level settings abstraction

Example for Current Affairs:

- `current_affairs_settings` table with columns like `generation_time`, `user_id`
- Settings page at `/current-affairs/settings`
- Module queries/updates its own settings table
