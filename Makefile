.PHONY: help run sync init-schema status check format typecheck test clean

help:
	@echo "Available commands:"
	@echo "  make run            - Show CLI help"
	@echo "  make sync           - Sync activities from Strava to Notion"
	@echo "  make sync-full      - Sync all activities (not just recent)"
	@echo "  make init-schema    - Initialize Notion database schema"
	@echo "  make status         - Show database status"
	@echo "  make check          - Run linter (ruff)"
	@echo "  make format         - Format code (ruff)"
	@echo "  make typecheck      - Run type checker (ty)"
	@echo "  make test           - Run tests"

# CLI commands
run:
	@uv run strava2notion --help

sync:
	@uv run strava2notion sync

sync-full:
	@uv run strava2notion sync --full

init-schema:
	@uv run strava2notion init-schema

status:
	@uv run strava2notion status

# Development commands
check:
	@uv run ruff check src tests

format:
	@uv run ruff format src tests

typecheck:
	@uvx ty check src

test:
	@uv run pytest

clean:
	rm -rf .ruff_cache .pytest_cache __pycache__ dist build *.egg-info .venv
