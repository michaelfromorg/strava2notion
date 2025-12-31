"""Strava API client with token refresh."""

import http.server
import threading
import urllib.parse
import webbrowser
from datetime import datetime

import httpx

from strava2notion.config import Settings
from strava2notion.exceptions import StravaAPIError, StravaAuthError
from strava2notion.models import Activity

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaClient:
    """Async client for Strava API using token refresh."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._access_token: str | None = None
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _refresh_token(self) -> str:
        """Refresh access token using refresh token."""
        if not self.settings.strava_refresh_token:
            raise StravaAuthError(
                "No refresh token configured. Run 'strava2notion auth' first."
            )

        client = await self._get_client()

        try:
            response = await client.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": self.settings.strava_client_id,
                    "client_secret": self.settings.strava_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.settings.strava_refresh_token,
                },
            )

            if response.status_code != 200:
                raise StravaAuthError(
                    f"Token refresh failed ({response.status_code}): {response.text}"
                )

            data = response.json()
            self._access_token = data["access_token"]
            return self._access_token

        except httpx.HTTPError as e:
            raise StravaAuthError(f"Token refresh request failed: {e}") from e

    async def _get_access_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        if self._access_token is None:
            return await self._refresh_token()
        return self._access_token

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
    ) -> dict | list:
        """Make authenticated API request."""
        client = await self._get_client()
        token = await self._get_access_token()

        try:
            response = await client.request(
                method,
                f"{STRAVA_API_BASE}{endpoint}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )

            if response.status_code == 401:
                # Token expired, refresh and retry
                token = await self._refresh_token()
                response = await client.request(
                    method,
                    f"{STRAVA_API_BASE}{endpoint}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )

            if response.status_code >= 400:
                raise StravaAPIError(
                    f"Strava API error ({response.status_code}): {response.text}"
                )

            return response.json()

        except httpx.HTTPError as e:
            raise StravaAPIError(f"Strava API request failed: {e}") from e

    def authorize(self, port: int = 8000) -> dict:
        """
        Run OAuth flow to get new tokens with proper scopes.

        Opens browser for user authorization, then exchanges code for tokens.
        Returns dict with access_token and refresh_token.
        """
        auth_code: str | None = None
        error: str | None = None

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal auth_code, error
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)

                if "code" in params:
                    auth_code = params["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<h1>Authorization successful!</h1>")
                    self.wfile.write(b"<p>You can close this window.</p>")
                elif "error" in params:
                    error = params.get("error_description", params["error"])[0]
                    self.send_response(400)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(f"<h1>Error: {error}</h1>".encode())
                else:
                    self.send_response(400)
                    self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress logging

        # Build authorization URL
        auth_params = {
            "client_id": self.settings.strava_client_id,
            "redirect_uri": f"http://localhost:{port}/callback",
            "response_type": "code",
            "scope": "activity:read_all",
        }
        auth_url = f"{STRAVA_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

        # Start local server
        server = http.server.HTTPServer(("localhost", port), CallbackHandler)
        server.timeout = 120  # 2 minute timeout

        # Open browser
        webbrowser.open(auth_url)

        # Wait for callback
        server.handle_request()
        server.server_close()

        if error:
            raise StravaAuthError(f"Authorization failed: {error}")
        if not auth_code:
            raise StravaAuthError("No authorization code received")

        # Exchange code for tokens
        with httpx.Client() as client:
            response = client.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": self.settings.strava_client_id,
                    "client_secret": self.settings.strava_client_secret,
                    "code": auth_code,
                    "grant_type": "authorization_code",
                },
            )

            if response.status_code != 200:
                raise StravaAuthError(f"Token exchange failed: {response.text}")

            return response.json()

    async def get_activities(
        self,
        after: datetime | None = None,
        before: datetime | None = None,
        per_page: int = 100,
    ) -> list[Activity]:
        """
        Fetch activities from Strava.

        Args:
            after: Only fetch activities after this date
            before: Only fetch activities before this date
            per_page: Number of activities per page (max 200)

        Returns:
            List of Activity models
        """
        params: dict = {"per_page": per_page}

        if after:
            params["after"] = int(after.timestamp())
        if before:
            params["before"] = int(before.timestamp())

        activities = []
        page = 1

        while True:
            params["page"] = page
            data = await self._request("GET", "/athlete/activities", params=params)

            if not data:
                break

            for item in data:
                activities.append(Activity.from_strava_api(item))

            if len(data) < per_page:
                break

            page += 1

        return activities
