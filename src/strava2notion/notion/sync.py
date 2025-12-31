"""Sync logic for upserting activities to Notion."""

import asyncio
from collections.abc import Callable
from datetime import datetime

from strava2notion.models import Activity
from strava2notion.notion.client import NotionClient


class ActivitySyncer:
    """Handles syncing activities to Notion with upsert logic."""

    def __init__(self, client: NotionClient, database_id: str):
        self.client = client
        self.database_id = database_id
        self._strava_id_to_page_id: dict[str, str] = {}
        self._most_recent_date: datetime | None = None

    async def initialize(self) -> None:
        """Initialize sync state by loading existing pages."""
        await self._build_lookup_index()

    async def _build_lookup_index(self) -> None:
        """Load all existing pages and build lookup index."""
        self._strava_id_to_page_id = {}
        self._most_recent_date = None

        async for page in self.client.query_database_all(self.database_id):
            props = page.get("properties", {})
            page_id = page["id"]

            # Index by Strava ID
            strava_id_prop = props.get("Strava ID", {})
            rich_text = strava_id_prop.get("rich_text", [])
            if rich_text:
                strava_id = rich_text[0].get("plain_text", "")
                if strava_id:
                    self._strava_id_to_page_id[strava_id] = page_id

            # Track most recent date
            date_prop = props.get("Date", {})
            date_val = date_prop.get("date")
            if date_val and date_val.get("start"):
                try:
                    date_str = date_val["start"]
                    # Handle both datetime and date-only formats
                    if "T" in date_str:
                        activity_date = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                    else:
                        activity_date = datetime.fromisoformat(date_str)

                    if self._most_recent_date is None or activity_date > self._most_recent_date:
                        self._most_recent_date = activity_date
                except ValueError:
                    pass

    def _find_existing_page(self, activity: Activity) -> str | None:
        """Find existing page ID for an activity."""
        return self._strava_id_to_page_id.get(str(activity.strava_id))

    async def sync_activity(self, activity: Activity) -> tuple[str, str]:
        """
        Sync a single activity to Notion.

        Returns:
            Tuple of (page_id, action) where action is "created" or "updated"
        """
        properties = activity.to_notion_properties()
        existing_page_id = self._find_existing_page(activity)

        if existing_page_id:
            await self.client.update_page(existing_page_id, properties)
            return existing_page_id, "updated"
        else:
            result = await self.client.create_page(self.database_id, properties)
            new_id = result["id"]
            self._strava_id_to_page_id[str(activity.strava_id)] = new_id
            return new_id, "created"

    async def sync_activities(
        self,
        activities: list[Activity],
        on_progress: Callable[[Activity, str], None] | None = None,
    ) -> dict[str, int]:
        """
        Sync multiple activities.

        Args:
            activities: List of activities to sync
            on_progress: Optional callback called with (activity, action)

        Returns:
            Dict with counts: {"created": N, "updated": N}
        """
        counts = {"created": 0, "updated": 0}

        for activity in activities:
            _, action = await self.sync_activity(activity)
            counts[action] += 1

            if on_progress:
                on_progress(activity, action)

        return counts

    @property
    def existing_count(self) -> int:
        """Number of existing activities loaded."""
        return len(self._strava_id_to_page_id)

    @property
    def most_recent_activity_date(self) -> datetime | None:
        """Most recent activity date in the database."""
        return self._most_recent_date
