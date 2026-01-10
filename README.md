# Together

This is an app for Samhita and Me ❤️

## Intro

This is a webapp for us to keep track of what we do together *and* enable us to
do more things together. It has features like:

1. A "current affairs" module, which helps us talk about current affairs on a
   regular basis and keep track of what we've discussed.

2. A "eats" module, where we keep track of places we've been to or want to go,
   what we like about them or want to try there.

3. A relationship journal

It is structured as a webapp with sub-routes for each module.

The webapp is built on the following stack:

1. Litestar as the server
2. HTMX for client-side interactivity
3. SQLAlchemy with SQLite for the database
4. APScheduler for scheduling periodic tasks
5. uv as the package manager
6. Docker for deployment

The architecture is designed to make adding modules easy and provide a simple
framework for building them; see `docs/architecture.md`.
