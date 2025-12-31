# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

strava2notion syncs Strava activity data to a Notion database. It uses token-based authentication with Strava (refresh token flow) and the Notion API.

## Commands

```bash
make sync           # Incremental sync (new activities only)
make sync-full      # Full sync (all activities)
make init-schema    # Initialize Notion database schema
make status         # Show database statistics

make check          # Lint with ruff
make format         # Auto-format with ruff
make typecheck      # Type check with ty
make test           # Run tests
```

Or use the CLI directly:
```bash
uv run strava2notion sync [--full] [--dry-run]
uv run strava2notion init-schema
uv run strava2notion status
```

## Environment Setup

Requires Python 3.12 and uv. Copy `.env.example` to `.env` and configure:
- `CLIENT_ID`, `CLIENT_SECRET` - Strava API credentials
- `STRAVA_REFRESH_TOKEN` - Strava refresh token for automated auth
- `TOKEN_V3` - Notion API integration secret
- `DATABASE_ID` - Target Notion database ID

## Architecture

```
src/strava2notion/
├── cli.py              # Click CLI commands
├── config.py           # pydantic-settings configuration
├── models.py           # Pydantic Activity model
├── exceptions.py       # Custom exception hierarchy
├── strava/
│   └── client.py       # Async Strava client with token refresh
└── notion/
    ├── client.py       # Async Notion API client
    ├── schema.py       # Database schema definition
    └── sync.py         # ActivitySyncer with upsert logic
```

**Data Flow:**
1. `StravaClient` refreshes access token using refresh token (no browser needed)
2. Fetches activities from Strava API
3. Converts to `Activity` Pydantic models
4. `ActivitySyncer` loads existing Notion pages, builds dedup index by Strava ID
5. Upserts activities (creates new, updates existing)

## Notion Database Schema

Required fields: Name (title), Type (select), Length (number, km), Time (number, hours), Date (date), Power (number, watts), Elevation (number), Strava Link (URL), Strava ID (rich_text for deduplication).

Run `make init-schema` to add missing properties to an existing database.

## GitHub Actions

Automated sync runs every 6 hours via `.github/workflows/sync.yml`. Required secrets:
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`
- `NOTION_TOKEN`, `NOTION_DATABASE_ID`
