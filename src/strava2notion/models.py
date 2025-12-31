"""Data models for strava2notion."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field


class Activity(BaseModel):
    """Represents a Strava activity."""

    # Core identifiers
    strava_id: int = Field(description="Strava activity ID")

    # Activity metadata
    name: str
    activity_type: str = Field(description="e.g., Run, Ride, Swim")
    start_date_local: datetime

    # Metrics
    distance_meters: float = Field(default=0.0)
    moving_time_seconds: int = Field(default=0)
    total_elevation_gain: float = Field(default=0.0)
    weighted_average_watts: int | None = Field(default=None)

    @computed_field
    @property
    def distance_km(self) -> float:
        """Distance in kilometers, rounded to 2 decimals."""
        return round(self.distance_meters / 1000, 2)

    @computed_field
    @property
    def time_hours(self) -> float:
        """Moving time in hours, rounded to 2 decimals."""
        return round(self.moving_time_seconds / 3600, 2)

    @computed_field
    @property
    def strava_url(self) -> str:
        """URL to the activity on Strava."""
        return f"https://strava.com/activities/{self.strava_id}"

    @property
    def power(self) -> int:
        """Weighted average power, defaulting to 0 if not available."""
        return self.weighted_average_watts or 0

    def to_notion_properties(self) -> dict[str, Any]:
        """Convert to Notion API property format."""
        return {
            "Name": {"title": [{"text": {"content": self.name}}]},
            "Type": {"select": {"name": self.activity_type}},
            "Length": {"number": self.distance_km},
            "Time": {"number": self.time_hours},
            "Power": {"number": self.power},
            "Elevation": {"number": self.total_elevation_gain},
            "Date": {"date": {"start": str(self.start_date_local)}},
            "Strava Link": {"url": self.strava_url},
            "Strava ID": {"rich_text": [{"text": {"content": str(self.strava_id)}}]},
        }

    @classmethod
    def from_strava_api(cls, data: dict[str, Any]) -> "Activity":
        """Create Activity from Strava API response."""
        return cls(
            strava_id=data["id"],
            name=data["name"],
            activity_type=data["type"],
            start_date_local=datetime.fromisoformat(data["start_date_local"].replace("Z", "")),
            distance_meters=data.get("distance", 0.0),
            moving_time_seconds=data.get("moving_time", 0),
            total_elevation_gain=data.get("total_elevation_gain", 0.0),
            weighted_average_watts=data.get("weighted_average_watts"),
        )
