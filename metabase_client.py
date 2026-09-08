"""Metabase REST API client with read-only SQL enforcement."""

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class MetabaseError(Exception):
    """Raised when a Metabase API call fails or a query is rejected."""


class MetabaseConfig:
    def __init__(self) -> None:
        url = os.environ.get("METABASE_URL")
        if not url:
            raise MetabaseError(
                "METABASE_URL is not set. Set it in your environment or .env file."
            )
        self.url = url.rstrip("/")

        self.api_key = os.environ.get("METABASE_API_KEY")
        self.email = os.environ.get("METABASE_EMAIL")
        self.password = os.environ.get("METABASE_PASSWORD")

        if not self.api_key and not (self.email and self.password):
            raise MetabaseError(
                "No Metabase auth configured. Set METABASE_API_KEY, or both "
                "METABASE_EMAIL and METABASE_PASSWORD."
            )

    @property
    def uses_api_key(self) -> bool:
        return bool(self.api_key)


class MetabaseClient:
    def __init__(self, config: MetabaseConfig | None = None) -> None:
        self.config = config or MetabaseConfig()
        self._session_token: str | None = None

    def _authenticate(self) -> str:
        response = requests.post(
            f"{self.config.url}/api/session",
            json={"username": self.config.email, "password": self.config.password},
            timeout=30,
        )
        if response.status_code != 200:
            raise MetabaseError(
                f"Failed to authenticate to Metabase as {self.config.email}: "
                f"{response.status_code} {response.text}"
            )
        token = response.json().get("id")
        if not token:
            raise MetabaseError(
                f"Metabase login for {self.config.email} succeeded but returned no session id."
            )
        self._session_token = token
        return token

    def _headers(self) -> dict[str, str]:
        if self.config.uses_api_key:
            return {"x-api-key": self.config.api_key}
        token = self._session_token or self._authenticate()
        return {"X-Metabase-Session": token}

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.config.url}{path}"
        response = requests.request(method, url, headers=self._headers(), json=json, params=params, timeout=60)

        if response.status_code == 401 and not self.config.uses_api_key:
            self._session_token = None
            response = requests.request(method, url, headers=self._headers(), json=json, params=params, timeout=60)

        if response.status_code >= 400:
            raise MetabaseError(
                f"Metabase request failed: {method} {path} -> {response.status_code} {response.text}"
            )

        return response.json()
