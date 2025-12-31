"""CLI commands using click."""

import asyncio
from typing import Any

import click

from strava2notion import __version__
from strava2notion.config import Settings, get_settings


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Sync Strava activities to Notion database."""
    ctx.ensure_object(dict)
    try:
        ctx.obj["settings"] = get_settings()
    except Exception as e:
        ctx.obj["settings"] = None
        ctx.obj["settings_error"] = str(e)


@main.command()
@click.option("--full", is_flag=True, help="Full sync (all activities, not just recent)")
@click.option("--dry-run", is_flag=True, help="Show what would be synced without syncing")
@click.pass_context
def sync(ctx: click.Context, full: bool, dry_run: bool) -> None:
    """Sync activities from Strava to Notion.

    By default, performs incremental sync (only new activities since last sync).
    Use --full to sync all activities.
    """
    settings: Settings | None = ctx.obj.get("settings")
    if settings is None:
        click.echo(f"Error loading settings: {ctx.obj.get('settings_error')}", err=True)
        ctx.exit(1)

    asyncio.run(_sync(settings, full=full, dry_run=dry_run))


async def _sync(settings: Settings, full: bool, dry_run: bool) -> None:
    """Async sync implementation."""
    from strava2notion.notion.client import NotionClient
    from strava2notion.notion.sync import ActivitySyncer
    from strava2notion.strava.client import StravaClient

    # Initialize clients
    notion = NotionClient(settings.notion_token, settings.rate_limit_delay)
    strava = StravaClient(settings)

    try:
        # Initialize syncer and load existing activities
        syncer = ActivitySyncer(notion, settings.notion_database_id)
        await syncer.initialize()
        click.echo(f"Found {syncer.existing_count} existing activities in Notion")

        # Determine sync start date
        after_date = None
        if not full and syncer.most_recent_activity_date:
            after_date = syncer.most_recent_activity_date
            click.echo(f"Incremental sync: fetching activities after {after_date.date()}")
        else:
            click.echo("Full sync: fetching all activities")

        # Fetch from Strava
        click.echo("\nFetching activities from Strava...")
        activities = await strava.get_activities(after=after_date)
        click.echo(f"Found {len(activities)} activities from Strava")

        if not activities:
            click.echo("No new activities to sync.")
            return

        if dry_run:
            click.echo("\nDry run - would sync:")
            for activity in activities:
                click.echo(
                    f"  {activity.name} ({activity.activity_type}) - "
                    f"{activity.distance_km}km, {activity.start_date_local.date()}"
                )
            return

        # Sync to Notion
        click.echo("\nSyncing to Notion...")

        def on_progress(activity: Any, action: str) -> None:
            symbol = "+" if action == "created" else "~"
            click.echo(f"  [{symbol}] {activity.name}")

        counts = await syncer.sync_activities(activities, on_progress=on_progress)
        click.echo(f"\nSync complete: {counts['created']} created, {counts['updated']} updated")

    finally:
        await notion.close()
        await strava.close()


@main.command()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Authorize with Strava to get a refresh token.

    Opens a browser for Strava authorization, then displays
    the refresh token to add to your .env file.
    """
    settings: Settings | None = ctx.obj.get("settings")
    if settings is None:
        click.echo(f"Error loading settings: {ctx.obj.get('settings_error')}", err=True)
        ctx.exit(1)

    from strava2notion.strava.client import StravaClient

    click.echo("Opening browser for Strava authorization...")
    click.echo("(Make sure 'localhost' is set as your Authorization Callback Domain in Strava)")
    click.echo()

    strava = StravaClient(settings)
    try:
        tokens = strava.authorize()
        click.echo()
        click.echo("Authorization successful!")
        click.echo()
        click.echo("Add this to your .env file:")
        click.echo(f'STRAVA_REFRESH_TOKEN="{tokens["refresh_token"]}"')
        click.echo()
        click.echo(f"Access token (expires): {tokens['access_token'][:20]}...")
        click.echo(f"Token type: {tokens.get('token_type', 'Bearer')}")
        click.echo(f"Expires at: {tokens.get('expires_at', 'unknown')}")
    except Exception as e:
        click.echo(f"Authorization failed: {e}", err=True)
        ctx.exit(1)


@main.command("init-schema")
@click.pass_context
def init_schema(ctx: click.Context) -> None:
    """Initialize Notion database with required properties."""
    settings: Settings | None = ctx.obj.get("settings")
    if settings is None:
        click.echo(f"Error loading settings: {ctx.obj.get('settings_error')}", err=True)
        ctx.exit(1)

    asyncio.run(_init_schema(settings))


async def _init_schema(settings: Settings) -> None:
    """Initialize database schema."""
    from strava2notion.notion.client import NotionClient
    from strava2notion.notion.schema import SCHEMA

    click.echo("Updating Notion database schema...")

    client = NotionClient(settings.notion_token)
    try:
        db = await client.get_database(settings.notion_database_id)
        title_list = db.get("title", [])
        db_name = title_list[0].get("plain_text", "Unknown") if title_list else "Unknown"
        click.echo(f"Database: {db_name}")

        await client.update_database(settings.notion_database_id, SCHEMA)

        click.echo("\nSchema updated! Properties:")
        for name, config in SCHEMA.items():
            prop_type = list(config.keys())[0]
            click.echo(f"  + {name}: {prop_type}")

        click.echo("\nDone! Your database now has all required properties.")
    finally:
        await client.close()


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current sync status and database statistics."""
    settings: Settings | None = ctx.obj.get("settings")
    if settings is None:
        click.echo(f"Error loading settings: {ctx.obj.get('settings_error')}", err=True)
        ctx.exit(1)

    asyncio.run(_status(settings))


async def _status(settings: Settings) -> None:
    """Show database status."""
    from strava2notion.notion.client import NotionClient

    client = NotionClient(settings.notion_token)
    try:
        # Get database info
        db = await client.get_database(settings.notion_database_id)
        title_list = db.get("title", [])
        db_name = title_list[0].get("plain_text", "Unknown") if title_list else "Unknown"

        # Count activities by type
        type_counts: dict[str, int] = {}
        total = 0
        most_recent = None

        async for page in client.query_database_all(settings.notion_database_id):
            total += 1
            props = page.get("properties", {})

            # Count by type
            type_prop = props.get("Type", {})
            type_select = type_prop.get("select")
            type_name = type_select.get("name", "Unknown") if type_select else "Unknown"
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

            # Track most recent
            date_prop = props.get("Date", {})
            date_val = date_prop.get("date")
            if date_val and date_val.get("start"):
                if most_recent is None or date_val["start"] > most_recent:
                    most_recent = date_val["start"]

        click.echo(f"\nNotion Database: {db_name}")
        click.echo(f"Total activities: {total}")
        if most_recent:
            click.echo(f"Most recent: {most_recent[:10]}")
        click.echo("\nActivities by type:")
        for type_name, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {type_name}: {count}")
    finally:
        await client.close()


if __name__ == "__main__":
    main()
