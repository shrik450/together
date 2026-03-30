# Getting Started

This app can be deployed without Docker. A simple setup is:

- a Linux server or VM
- Python 3.14+
- `uv`
- a persistent directory for the SQLite database
- a reverse proxy such as Caddy or Nginx in front of the app

## 1. Install the app

```bash
git clone <your-repo-url>
cd together
uv sync --frozen --dev
npm install
```

## 2. Configure the environment

Copy `.env.example` and fill in production values:

```bash
cp .env.example .env
```

Required:

- `TOGETHER_DATABASE_URL` - must be an absolute SQLite URL, for example:
  `sqlite+aiosqlite:////srv/together/data/together.db`
- `TOGETHER_SECRET_KEY` - session signing key. Generate one with:
  `uv run python -c "import secrets; print(secrets.token_hex(32))"`

Optional:

- `SESSION_MAX_AGE_DAYS` - session expiry in days (default: 30)
- `TOGETHER_SECURE_COOKIES` - keep this as `true` in production and set it to
  `false` only for local HTTP development

## 3. Create the database and first user

```bash
uv run litestar database upgrade --no-prompt
uv run python -m together create-user <username>
```

Use Litestar's database CLI only:

```bash
uv run litestar database --help
```

Raw `alembic` commands are intentionally unsupported in this project.

## 4. Run the app

For a first deployment, bind the app to localhost and put a reverse proxy in
front of it:

```bash
uv run litestar run --host 127.0.0.1 --port 8000
```

Then proxy traffic from your domain to `127.0.0.1:8000` using Caddy or Nginx.

## 5. Run tests

Install the dev dependencies and run pytest:

```bash
uv run pytest
```

For formatter and lint checks:

```bash
just test
just check
```

## 6. Run it as a service

A minimal `systemd` unit might look like this:

```ini
[Unit]
Description=Together app
After=network.target

[Service]
User=together
WorkingDirectory=/srv/together/app
EnvironmentFile=/srv/together/app/.env
ExecStart=/home/together/.local/bin/uv run litestar run --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now together
```

## Notes

- SQLite is supported here, but keep the database on persistent storage and back
  it up regularly.
- `TOGETHER_DATABASE_URL` must point to an absolute path.
- Keep `TOGETHER_SECURE_COOKIES=true` when serving the app over HTTPS.
- Schema changes are migration-driven:

```bash
uv run litestar database make-migrations -m "describe change" --no-prompt
uv run litestar database upgrade --no-prompt
```
