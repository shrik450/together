set shell := ["bash", "-cu"]

# Show available recipes.
default:
    @just --list

# Install Python and frontend tooling.
setup:
    uv sync --dev
    npm install

# Fix Python lint issues and format repo-owned source files.
lint:
    uv run ruff check --fix .
    uv run ruff format .
    npm exec -- prettier --write templates modules static

# Check Python lint and formatting without modifying files.
check:
    uv run ruff check .
    uv run ruff format --check .
    npm exec -- prettier --check templates modules static
    uv run pytest

# Run the test suite.
test:
    uv run pytest

# Run the app in reload mode.
dev:
    uv run litestar run --reload
