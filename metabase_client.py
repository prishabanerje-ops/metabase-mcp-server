"""Metabase REST API client with read-only SQL enforcement."""

import os

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
