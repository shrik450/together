# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## IMPORTANT - how to work on this project

When working on a request, you must never jump the gun. Instead, confer on the
plan with the user and only start implementing when you have been given an
explicit go-ahead.

When working on a request, always start with exploring the codebase to understand
what is already there.

## Project Overview

"Together" is a personal webapp for relationship activities - tracking current
affairs discussions, restaurant visits, and journaling. It uses a modular
architecture where each feature (current affairs, eats, journal) is a separate
module with sub-routes.

This is a **purely personal** app. While this is in production and actively
used, it is not meant to be sold as a product or used by anyone other than its
creators.

## Tech Stack

- **Framework**: Litestar (Python web framework)
- **Frontend**: HTMX for client-side interactivity
- **Database**: SQLAlchemy with SQLite
- **Scheduling**: APScheduler for periodic tasks
- **Package Manager**: uv
- **Python**: 3.14+

## Commands

```bash
# Install dependencies 
uv sync

# Run the development server 
uv run litestar run --reload

# Run a specific Python file 
uv run python <file.py> 
```

## Coding Guidelines

- Always use `uv` for all Python or python related commands.
- Keep all sensitive information (API keys, secrets) in environment variables or
  `.env` files, never hardcoded or passed as CLI args etc.
- Do not add comments unless they are necessary to understand _why_ something
  is done. Doc comments should be avoided unless they add value over the
  function/class name, argument names and types.
- **Immutable collection types**: When returning collections from functions,
  use `Sequence` or `Mapping` from `collections.abc` instead of `list` or `dict`
  in type hints. This signals to callers that the returned collection should not
  be mutated. Internal storage can still use mutable types, but the public API
  should expose immutable interfaces.

## Architecture

The app is structured as a webapp with sub-routes for each module. Modules are
designed to be self-contained and easy to add. See `docs/architecture.md` for
the full architecture guide (when available).

### Planned Modules

- **Current Affairs**: Daily news briefings and conversation prompts with
discussion notes
- **Eats**: Restaurant tracking (visited/want to visit, favorites, things to
try)
- **Journal**: Relationship journal
