set shell := ["bash", "-cu"]

# Show available recipes.
default:
    @just --list

# Install Python dependencies.
setup:
    uv sync --dev

# Fix Python lint issues and format repo-owned source files.
lint:
    ruff check --fix .
    ruff format .
    prettier --write templates modules static

# Check lint, formatting and types, then run the tests, without modifying files.
check:
    ruff check .
    ruff format --check .
    prettier --check templates modules static
    basedpyright
    uv run pytest

# Type-check the project.
typecheck:
    basedpyright

# Run the test suite.
test:
    uv run pytest

# Run the app in reload mode.
dev:
    uv run litestar run --reload
