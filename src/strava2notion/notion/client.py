"""Async Notion API client."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from strava2notion.exceptions import NotionAPIError, RateLimitError

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"


class NotionClient:
    """Async client for Notion API."""

    def __init__(self, token: str, rate_limit_delay: float = 0.35):
        self.token = token
        self.rate_limit_delay = rate_limit_delay
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=NOTION_BASE_URL,
                headers=self._get_headers(),
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        import time

        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | None = None,
        retries: int = 3,
    ) -> dict[str, Any]:
        """Make an API request with retry logic."""
        client = await self._get_client()
        await self._rate_limit()

        for attempt in range(retries):
            try:
                response = await client.request(method, endpoint, json=json)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("retry-after", "1"))
                    if attempt < retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    raise RateLimitError(retry_after)

                if response.status_code >= 400:
                    error_body = response.json()
                    raise NotionAPIError(
                        response.status_code,
                        error_body.get("message", "Unknown error"),
                    )

                return response.json()

            except httpx.HTTPError as e:
                if attempt < retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise NotionAPIError(0, str(e)) from e

        raise NotionAPIError(0, "Max retries exceeded")

    async def query_database(
        self,
        database_id: str,
        start_cursor: str | None = None,
        page_size: int = 100,
        sorts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Query a database with pagination."""
        payload: dict[str, Any] = {"page_size": page_size}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        if sorts:
            payload["sorts"] = sorts

        return await self._request("POST", f"/databases/{database_id}/query", json=payload)

    async def query_database_all(self, database_id: str) -> AsyncIterator[dict[str, Any]]:
        """Query all pages from a database, handling pagination."""
        start_cursor = None
        while True:
            result = await self.query_database(database_id, start_cursor)
            for page in result.get("results", []):
                yield page

            if not result.get("has_more"):
                break
            start_cursor = result.get("next_cursor")

    async def create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new page in a database."""
        payload = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        return await self._request("POST", "/pages", json=payload)

    async def update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing page's properties."""
        return await self._request("PATCH", f"/pages/{page_id}", json={"properties": properties})

    async def update_database(
        self,
        database_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Update database schema (add properties)."""
        return await self._request(
            "PATCH", f"/databases/{database_id}", json={"properties": properties}
        )

    async def get_database(self, database_id: str) -> dict[str, Any]:
        """Get database metadata including schema."""
        return await self._request("GET", f"/databases/{database_id}")
