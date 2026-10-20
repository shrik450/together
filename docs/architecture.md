# Architecture

This document describes the current architecture of the Together scaffold and
the extension points future modules are expected to use.

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

### Pydantic AI

- **Version**: 2.x via `pydantic-ai-slim` with the Anthropic, OpenAI and Google
  extras
- **Agents**: Plain Pydantic AI `Agent`s, defined at module level with a `name`
  and no model; `framework.llm.run_agent` supplies the model for a role
- **Output**: Use dataclasses as `output_type`, like the rest of the codebase
- **Web access**: Use `framework.llm.web_toolset`, not provider-hosted web
  tools, so agents behave the same whichever provider runs them

References:

- [Pydantic AI](https://pydantic.dev/docs/ai/)

### Zendriver

- **Purpose**: Drives a real Chromium for `framework.browser`, talking to it
  directly over the DevTools protocol rather than through Playwright or
  webdriver, which many sites detect and block
- **Browser**: Chromium from the flake (nixpkgs); Zendriver itself is pure
  Python and installed by uv

References:

- [Zendriver](https://github.com/cdpdriver/zendriver)

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
    href: str | None = None  # None = current page
    icon: str | None = None  # Optional
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

Handlers currently provide the page's `nav_stack` directly. The shell always
ensures Home (`/`) appears in breadcrumb rendering, while registered module
`NavNode`s populate the sidebar when modules add them.

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
│   ├── browser/           # Chromium for reading web pages
│   ├── db/                # Database config, Base class, async DB helpers
│   ├── llm/               # Model roles, agent runs, web tools
│   ├── ui.py              # PageAction, NavNode, register_nav_node()
│   └── scheduler/         # APScheduler setup, queued jobs
├── modules/               # Feature modules
│   ├── __init__.py
│   └── home/
├── templates/             # Shared templates (base layout, components)
└── static/                # CSS, JS, images
```

## Module Structure

Feature modules are expected to be self-contained packages like:

```
modules/current_affairs/
├── __init__.py            # Exports router and register() function
├── handlers.py            # Route handler functions
├── models.py              # SQLAlchemy models
├── services.py            # Business logic (optional, for complex logic)
├── jobs.py                # Scheduled and queued job functions
├── llm.py                 # Agents and their output types
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
- The scaffold provides the scheduler boundary and registration API; no
  application schedules are registered yet

**Queued jobs:** `SchedulerService.enqueue(func, *args, **kwargs)` queues a
one-off job and returns without waiting. Use it for work that must outlive a
request, such as an LLM run whose result is saved.

- `func` must be an importable module-level function, as for schedules
- Pass ids and plain values, not ORM objects; arguments are serialized into
  APScheduler's tables
- The job's return value is discarded. The job records its own outcome on the
  module's records (e.g. a proposal's status)
- A job queued while the app is down runs when it starts. A job interrupted by
  a restart is **not** rerun, so modules must be able to tell that work was
  left unfinished (e.g. a proposal still "in progress" long after it was
  queued) and offer a retry

### Browser (framework/browser/)

A single Chromium, shared by the whole app, for reading web pages:

- `get_browser_service()` returns the app's `BrowserService`;
  `browser_lifespan` owns it
- `fetch(url)` returns a `Page`: the final URL after redirects, title, main
  text as Markdown (via trafilatura), JSON-LD structured data, and links
- `search(query)` runs a Google search and returns the results page's text and
  result links. Google's own panels, such as a place's address and hours, are
  part of the text. A blocked search raises `SearchBlockedError`
- The browser starts on first use and closes after a few idle minutes. It keeps
  a persistent profile in `browser-profile/` next to the database, so cookies
  and consent choices survive
- Every request a tab makes (the page, its redirects, and its images, scripts
  and frames) is paused through the DevTools `Fetch` domain and only continues
  if its host resolves to public addresses (`network.py`). Callers, including
  LLMs, choose the URLs, and the app runs on a home server. Known limits: a
  host that resolves differently for Chromium than for us (DNS rebinding), and
  requests from web workers and WebSockets, are not checked
- `chromium.py` is the only module that touches Zendriver. It runs the
  Chromium process itself (Zendriver's launcher leaks pipes), parses every
  value read from a page into a declared type, and raises every failure as a
  `BrowserError`
- Headless Chromium's user agent is replaced with a regular desktop one

### LLM (framework/llm/)

Modules define Pydantic AI agents and run them with `run_agent`:

```python
from pydantic_ai import Agent

from framework.llm import ModelRole, run_agent, web_toolset

capture_agent = Agent(
    name="eats.capture",
    output_type=CaptureProposal,
    instructions=CAPTURE_INSTRUCTIONS,
    toolsets=[web_toolset],
)

result = await run_agent(capture_agent, [text, receipt], deps=None)
result.output  # CaptureProposal
result.run_id  # the run's LlmRun row
```

- **Model roles:** `ModelRole.default` and `ModelRole.fast` map to models in
  code, and `TOGETHER_LLM_MODEL_<ROLE>` overrides either. Feature code names a
  role, never a provider or model. API keys come from each provider's own
  environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `GOOGLE_API_KEY`)
- **Run records:** every run writes an `LlmRun` row: agent, model, status,
  requests, tokens, best-effort cost, error, and messages. Runs can be long, so
  records use their own sessions. Images and other files in the prompt are
  replaced with a note before the messages are stored
- **Failures:** a failed run is recorded and raised as `AgentRunFailed`, which
  carries its `run_id`. The module decides what failure means for its records
- **Limits:** runs default to at most 30 model requests; pass `usage_limits`
  to change that
- **Where runs happen:** run an agent in a queued job when its result is saved
  (capture, briefings), and inside the request when someone is waiting on an
  answer that isn't saved
- **Web tools:** `web_toolset` gives agents `search_web` and `fetch_page`,
  backed by `framework.browser`. Its instructions tell the model page content
  is untrusted

---

## Module Registration

Modules are registered explicitly in `app.py`. Full feature modules are
expected to export:

- `router`: A `Router` instance to mount on the app
- `register()`: Function that registers models, schedules, and navigation

Each feature module's `register()` function should:

- Imports any module-specific models before migrations/autogenerate run
- Calls `add_schedule()` for any scheduled jobs
- Calls `register_nav_node()` with the module's top-level `NavNode`
- Raise clear errors if misconfigured

The current `home` scaffold is intentionally lighter-weight and only registers
its template directory.

Example:

```python
from framework.scheduler import ScheduleDefinition, ScheduleRef, add_schedule
from framework.ui import NavNode, register_nav_node
from modules.current_affairs.models import Entry, Settings

DAILY_BRIEFING = ScheduleRef("current-affairs-daily-briefing")


def register():
    add_schedule(
        ScheduleDefinition(
            ref=DAILY_BRIEFING,
            func=generate_briefing,
            cron="0 7 * * *",
            timezone="America/New_York",
        )
    )
    register_nav_node(
        NavNode(label="Current Affairs", href="/current-affairs/", icon="newspaper")
    )
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

Navigation state is provided via the `nav_stack` context variable. The current
shell uses that stack directly, ensures Home appears in breadcrumb rendering,
and lists registered module nodes in the sidebar when present. See
`docs/ui_design.md` for the navigation model and current scaffold notes.

- **Wide viewports (`min-width: 900px`)**: Persistent left sidebar showing all
  modules, with the active module expanded to show the current path and siblings.
- **Narrow viewports**: A breadcrumb bar showing the last two levels, with
  dropdowns for sibling quick-switching.
- **HTMX-friendly shell**: HTMX is installed and available for progressive
  enhancement; boosted partial navigation has not been implemented yet.

---

## Route Conventions

- Home route: `/`
- Auth routes: `/auth/login`, `/auth/logout`
- Module routes: `/<module-name>/...`
  - Current Affairs: `/current-affairs/`, `/current-affairs/<date>/`
  - Eats: `/eats/`, `/eats/<place-id>/`
  - Journal: `/journal/`, `/journal/<entry-id>/`
- Static files: `/static/...`

Only `/`, `/auth/...`, and `/static/...` exist in the current scaffold.

---

## Error Handling

The current scaffold already provides explicit validation in a few shared
surfaces:

- Invalid or duplicate schedule registration raises clear errors from
  `framework/scheduler/service.py`
- Missing auth secrets or invalid database configuration fail fast during app
  setup
- More module-registration validation can be added once feature modules exist

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
