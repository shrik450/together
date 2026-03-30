# Testing Plan

This document describes the intended pytest suite for the framework scaffold.

The goal is to cover the framework's public boundaries with a small number of
high-value tests, using real integrations where that gives more confidence than
mock-heavy tests.

## Principles

- Test framework boundaries, not implementation trivia.
- Prefer real SQLite, real Litestar wiring, and the real APScheduler lifecycle
  for integration behavior.
- Do not mock logger calls.
- Keep the file layout compact: generally one test file per framework module or
  boundary surface.
- Use classes to organize tests within a file.
- Reuse setup aggressively with fixtures, helper functions, parametrization, and
  class-level setup helpers.

## Async Test Convention

We want pytest asyncio auto mode.

- Configure pytest to use `asyncio_mode = auto`.
- Do not add `@pytest.mark.asyncio` to every async test.
- Future agents should treat per-test asyncio markers as a smell unless there is
  a specific reason to override the default.
- If async tests need special loop behavior, handle it centrally in pytest
  config or shared fixtures instead of decorating lots of tests.

Expected pytest config:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

## Proposed Test Layout

Use a small number of files:

```text
tests/
├── conftest.py
├── helpers.py
├── test_auth.py
├── test_db.py
├── test_scheduler.py
├── test_ui.py
└── test_app.py
```

Guidelines:

- `tests/conftest.py` holds shared fixtures only.
- `tests/helpers.py` holds reusable test-only helper functions and module-level
  scheduler task functions.
- Each test file should contain a few classes grouped by behavior, not one huge
  flat list of tests.
- Prefer shared helper methods on classes when several tests differ only by one
  assertion path.

## Shared Fixtures

These should live in `tests/conftest.py` and be reused across files.

- `tmp_database_path`: temp absolute SQLite path.
- `database_url`: derived `sqlite+aiosqlite` URL.
- `configured_env`: sets `TOGETHER_DATABASE_URL`, `TOGETHER_SECRET_KEY`, and
  any cookie env needed for tests.
- `reset_session_config_cache`: clears `get_session_config()` cache before and
  after tests that vary env.
- `reset_scheduler_registry`: clears `framework.scheduler.service._registry`.
- `reset_nav_registry`: clears `framework.ui._nav_nodes`.
- `migrated_db`: creates schema for integration tests.
- `user_factory`: creates real `User` rows.
- `client`: Litestar test client against the real app.

Notes:

- Global state must be reset centrally. This matters for the auth session cache,
  nav registry, and scheduler registry.
- Prefer fixture composition over custom setup in every test class.

## Reuse Patterns

We should deliberately avoid repetitive tests.

- Use `@pytest.mark.parametrize()` for env validation, redirect safety cases,
  invalid cron cases, invalid timezone cases, and duplicate-path auth behavior.
- Use helper methods for repeated login flows, cookie creation, and schedule
  registration.
- Use fixture factories when the setup varies by a small number of inputs.
- When a test class needs repeated setup steps, use a private helper method on
  the class instead of repeating request/session creation inline.

## Coverage Plan By File

### `tests/test_auth.py`

Organize with classes like:

- `TestSessionConfig`
- `TestSessionCookies`
- `TestRedirectValidation`
- `TestAuthGuard`
- `TestAuthHandlers`
- `TestAuthMiddleware`
- `TestCurrentUserDependency`

High-value cases:

- `get_session_config()` rejects missing or too-short secrets.
- `SESSION_MAX_AGE_DAYS` accepts valid values and rejects invalid/non-positive
  values.
- `TOGETHER_SECURE_COOKIES` parsing is covered parametrically.
- session cookie round-trip succeeds for a valid user id.
- tampered cookies and malformed payloads resolve to anonymous state.
- redirect validation only allows same-site rooted paths.
- `require_auth()` exempts `/auth/...` and `/static/...`.
- unauthenticated protected requests redirect to login with safe `next`.
- HTMX unauthenticated requests get `HX-Redirect`.
- `GET /auth/login` renders for anonymous users and redirects when already
  authenticated.
- `POST /auth/login` succeeds with valid credentials and re-renders with error
  on failure.
- `POST /auth/logout` clears the session cookie.
- middleware populates `request.state.user_id` and lightweight
  `request.state.current_user` for valid cookies.
- `provide_current_user()` returns the real ORM `User` when authenticated.

Implementation notes:

- Use parametrized redirect cases rather than one test per URL.
- Use a shared helper for login requests and cookie extraction.
- Keep handler and middleware tests in the same file because they are one auth
  boundary from the app's perspective.

### `tests/test_db.py`

Organize with classes like:

- `TestDatabaseUrl`
- `TestSQLiteConnectionConfiguration`

High-value cases:

- `get_database_url()` rejects missing env.
- rejects non-SQLite driver names.
- rejects relative paths and `:memory:`.
- accepts absolute SQLite URLs.
- SQLite PRAGMA setup is applied on a real connection.

Implementation notes:

- Parametrize invalid URL cases.
- Use a small helper to inspect PRAGMA values from a real sqlite connection.

### `tests/test_scheduler.py`

This file should be more integration-heavy than the others.

Organize with classes like:

- `TestScheduleDefinitionValidation`
- `TestScheduleRegistration`
- `TestSchedulerLifespan`
- `TestSchedulerRuntime`
- `TestSchedulerPersistence`
- `TestSchedulerService`

High-value cases:

- `ScheduleRef` rejects blank ids.
- `ScheduleDefinition` rejects blank cron, blank timezone, and non-positive
  misfire grace time.
- callable validation rejects lambda, bound methods, and nested functions.
- invalid cron and invalid timezone are covered parametrically.
- `add_schedule()` rejects duplicate ids.
- scheduler lifespan attaches `scheduler_service` to app state and removes it on
  shutdown.
- real registered schedules are reconciled into the persistent datastore on
  startup.
- restarting the lifespan does not duplicate schedules.
- changed definitions are replaced on startup.
- stale app-managed schedules are removed on startup.
- `SchedulerService.run_now()` executes a real module-level test function and
  returns its result.
- `run_now()` supports overriding args and kwargs.
- `run_now()` raises on unknown schedule refs.
- `list_schedules()` returns framework definitions in sorted order with expected
  surfaced state.

APScheduler-specific guidance:

- Use the real `AsyncScheduler` path through `scheduler_lifespan()`.
- Use a real persistent SQLite datastore for persistence and reconciliation
  tests.
- Prefer explicit schedule ids and real startup/shutdown cycles over mocking
  scheduler internals.
- Do not assert logger calls.
- Do not exhaustively test APScheduler cron semantics; test our boundary and one
  or two representative real schedules.

Implementation notes:

- Keep module-level test task functions in `tests/helpers.py` so they are valid
  importable callables for scheduler registration.
- Use helper functions to register schedules and to start the scheduler within a
  lifespan context.
- Reset the scheduler registry before each test to avoid global leakage.

### `tests/test_ui.py`

Organize with classes like:

- `TestNavRegistry`
- `TestUiDataclasses`

High-value cases:

- `register_nav_node()` adds a node once.
- duplicate registration is idempotent.
- `get_nav_nodes()` returns a copy.
- `NavNode` and `PageAction` basic construction expectations are covered where
  useful.

This file should stay small.

### `tests/test_app.py`

Organize with classes like:

- `TestAppWiring`
- `TestProtectedHome`
- `TestShellRendering`

High-value cases:

- app imports successfully with required env.
- expected routes exist: `/`, `/auth/login`, `/auth/logout`, `/static/...`.
- app has auth guard, auth exception handler, session middleware, security
  middleware, HTMX plugin, and scheduler lifespan.
- unauthenticated `/` redirects to login.
- authenticated `/` renders the shell and home content.
- shell rendering includes expected chrome markers such as breadcrumb/sidebar
  structure and current username.

Implementation notes:

- Keep this file focused on app composition and a few smoke tests.
- Do not duplicate auth behavior already tested in `tests/test_auth.py`.

## What We Intentionally Do Not Test Yet

- Deep CSS behavior beyond a few shell render markers.
- Exhaustive APScheduler internals or cron semantics.
- Module feature behavior beyond the placeholder home route.
- Log output as part of the test contract.

## Recommended Implementation Order

1. `tests/conftest.py` and `tests/helpers.py`
2. `tests/test_auth.py`
3. `tests/test_scheduler.py`
4. `tests/test_db.py`
5. `tests/test_app.py`
6. `tests/test_ui.py`

## Guidance For Future Agents

When adding or updating tests in this repository:

- Default to `asyncio_mode = auto`.
- Do not scatter `@pytest.mark.asyncio` across the suite.
- Prefer one test file per framework surface, using classes inside the file for
  structure.
- Prefer parametrized tests over repeated near-duplicate functions.
- Prefer fixtures and helper factories over ad hoc local setup.
- Prefer real integrations for auth, app wiring, and scheduler lifecycle tests.
- Only mock when crossing a boundary that is expensive, flaky, or not owned by
  this repository.
