"""Custom exceptions for strava2notion."""


class StravaNotionError(Exception):
    """Base exception for strava2notion."""


class ConfigurationError(StravaNotionError):
    """Missing or invalid configuration."""


class StravaAPIError(StravaNotionError):
    """Error from Strava API."""


class StravaAuthError(StravaAPIError):
    """Authentication error with Strava."""


class NotionAPIError(StravaNotionError):
    """Error from Notion API."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Notion API error ({status_code}): {message}")


class RateLimitError(NotionAPIError):
    """Notion API rate limit exceeded."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(429, f"Rate limited. Retry after {retry_after}s")


class SyncError(StravaNotionError):
    """Error during sync operation."""

    def __init__(self, activity_id: int, name: str, original_error: Exception):
        self.activity_id = activity_id
        self.name = name
        self.original_error = original_error
        super().__init__(f"Failed to sync '{name}' (ID: {activity_id}): {original_error}")
