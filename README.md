# Together

This is an app for Samhita and Me ❤️

## Intro

This is a webapp for us to keep track of what we do together *and* enable us to
do more things together. It is being built around modules like:

1. A "current affairs" module, which helps us talk about current affairs on a
   regular basis and keep track of what we've discussed.

2. A "eats" module, where we keep track of places we've been to or want to go,
   what we like about them or want to try there.

3. A relationship journal

It is structured as a webapp with sub-routes for each module.

Current status: the scaffolded app shell, auth flow, database integration, and
scheduler infrastructure are in place. Feature modules beyond the placeholder
home route have not been built yet.

The webapp is built on the following stack:

1. Litestar as the server
2. HTMX for client-side interactivity
3. Advanced Alchemy + SQLAlchemy with async SQLite for the database
4. APScheduler 4.x for scheduling periodic tasks
5. uv as the package manager
6. uv + SQLite for a simple server deployment

The architecture is designed to make adding modules easy and provide a simple
framework for building them; see `docs/architecture.md`.

For setup and deployment, see `docs/getting_started.md`.

Note: this project intentionally targets APScheduler 4.x even though that line
is still alpha, because its async-native design fits the rest of the stack.

## Environment

Copy `.env.example` and fill in values as needed.

Required:

- `TOGETHER_DATABASE_URL` - absolute SQLite URL for the app database, for example:
  `sqlite+aiosqlite:////absolute/path/to/together.db`
- `TOGETHER_SECRET_KEY` - secret for signing session cookies. Generate one with:
  `python -c "import secrets; print(secrets.token_hex(32))"`

Optional:

- `SESSION_MAX_AGE_DAYS` - session expiry in days (default: 30)
- `TOGETHER_SECURE_COOKIES` - set `false` for local HTTP (default: true)

## Local setup

```bash
uv sync
uv run litestar database upgrade --no-prompt
uv run python -m together create-user <username>
uv run litestar run --reload
```

Use Litestar's database CLI only:

```bash
uv run litestar database --help
```

Raw `alembic` commands are intentionally unsupported in this project.

Schema changes are migration-driven:

```bash
uv run litestar database make-migrations -m "describe change" --no-prompt
uv run litestar database upgrade --no-prompt
```
