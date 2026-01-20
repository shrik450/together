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

- **Version**: 2.0+ (sync mode with SQLite)
- **Session management**: Use Litestar's built-in SQLAlchemy plugin
  (`SQLAlchemyPlugin`) which provides automatic session DI via `db_session`
  parameter
- **Models**: Inherit from plugin-provided `Base` class, use `Mapped[]` type
  annotations (SQLAlchemy 2.0 style)
- **Session config**: `expire_on_commit=False` for web apps (objects remain
  usable after commit)

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

**Breadcrumb** - Represents a breadcrumb navigation item:

```python
from framework.ui import Breadcrumb

breadcrumbs = [
    Breadcrumb(label="Home", href="/"),
    Breadcrumb(label="Current Page"),  # No href = current page
]
```

**NavItem** - Represents a sidebar navigation item (defined centrally):

```python
from framework.nav import NAV_ITEMS, NavItem

# NAV_ITEMS is a list of NavItem instances
# Modules don't register nav items; the list is defined in framework/nav.py
```

Handlers pass these to templates via context:

```python
@get("/example")
async def example_page() -> Template:
    return Template(
        template_name="example.html",
        context={
            "breadcrumbs": [Breadcrumb(label="Home", href="/"), Breadcrumb(label="Example")],
            "actions": [PageAction(label="Edit", href="/edit")],
            "page_title": "Example Page",
            "page_subtitle": "A subtitle for the page",
        },
    )
```

---

## Design Principles

1. **Explicit over implicit**: Modules explicitly register themselves, their
   models, and their jobs. No autodiscovery or framework magic. The framework
   helps identify when something wasn't registered or was registered incorrectly.

2. **Modules own their concerns**: Settings, configuration, and module-specific
   logic live in the module, not the framework. The framework provides
   infrastructure (database, auth, scheduling) but not policy.

3. **Simple migrations**: A target `schema.sql` defines the current schema.
   Migration scripts are written manually when needed. No heavy migration
   framework.

## Directory Structure

```
together/
├── app.py                 # Litestar app entry point, explicit module registration
├── schema.sql             # Target database schema (source of truth)
├── together.db            # SQLite database (gitignored)
├── migrations/            # Manual migration scripts (when needed)
├── framework/             # Shared infrastructure
│   ├── __init__.py
│   ├── auth/              # User auth, sessions
│   ├── db/                # Database config, model registration
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

### Database (framework/db/)

Uses Litestar's `SQLAlchemyPlugin` for session management:

- Plugin provides `db_session: Session` dependency automatically
- `Base` class from plugin for models to inherit from
- `register_models(*models)` function for explicit model registration
- Plugin configured with `create_all=False` (we manage schema manually)

Modules define their models in `models.py`, inheriting from the shared `Base`,
and explicitly register them in their `register()` function.

**Schema management:**

- `schema.sql` contains the complete current schema (CREATE TABLE statements)
- To apply schema to a fresh DB: `sqlite3 together.db < schema.sql`
- Migration scripts in `migrations/` for production changes (e.g.,
  `migrations/001_add_quiz_answers.sql`)

### Authentication (framework/auth/)

The framework provides:

- `User` model (id, username, password_hash)
- Login/logout routes
- Session middleware (signed cookies)
- `current_user` dependency for routes
- `require_auth` guard for protected routes

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
- `register()`: Function that registers models and schedules

Each module's `register()` function:

- Calls `register_models()` with all SQLAlchemy models
- Calls `add_schedule()` for any scheduled jobs
- Raises clear errors if misconfigured

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

- **Wide viewports (`min-width: 900px`)**: Persistent left sidebar navigation +
  a right content pane.
- **Narrow viewports**: A top breadcrumb bar + the content pane below.
- **Navigation structure**:
  - Top-level entries are modules.
  - Modules may provide hierarchical navigation for their own content (kept
    bounded; deep browsing lives in module pages, not the global nav).
  - The breadcrumb bar reflects the current hierarchical context without a
    dedicated "Home" crumb.
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
- Model not registered: "Model 'Entry' inherits from Base but was not registered
  via register_models()"
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
