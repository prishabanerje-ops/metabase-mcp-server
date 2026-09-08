"""Metabase REST API client with read-only SQL enforcement."""

import os
import re
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


WRITE_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "TRUNCATE", "GRANT", "REVOKE", "INTO",
)


def _strip_leading_sql_comments(sql: str) -> str:
    """
    Strip leading whitespace and SQL comments (-- line, /* block */) so the
    first real keyword can be found. Used only to locate the first keyword -
    the stacked-statement and write-keyword scans still run on the full,
    comment-inclusive text, so a write keyword or semicolon hidden inside a
    comment still trips validation (over-rejection, not a bypass).
    """
    remainder = sql.lstrip()
    while True:
        if remainder.startswith("--"):
            newline = remainder.find("\n")
            remainder = remainder[newline + 1:].lstrip() if newline != -1 else ""
        elif remainder.startswith("/*"):
            end = remainder.find("*/")
            remainder = remainder[end + 2:].lstrip() if end != -1 else ""
        else:
            return remainder


def validate_readonly_sql(sql: str) -> None:
    """
    Raise MetabaseError unless sql is a single read-only SELECT/CTE statement.

    This is a heuristic, not a full SQL parser or sandbox:
    - A SELECT that calls a function/procedure which itself performs a write
      (e.g. "SELECT delete_all_policies()") is not detectable by keyword
      matching and will pass. The Metabase account should still hold
      read-only DB permissions - this is defense-in-depth, not a substitute
      for least-privilege access.
    - A write keyword inside a quoted string literal or comment can cause a
      false rejection of an otherwise-safe query. Accepted trade-off.
    """
    stripped = sql.strip()
    if not stripped:
        raise MetabaseError("Cannot run an empty SQL query.")

    first_word_match = re.match(r"[A-Za-z]+", _strip_leading_sql_comments(stripped))
    first_word = first_word_match.group(0).upper() if first_word_match else ""

    if first_word not in ("SELECT", "WITH"):
        raise MetabaseError(
            f"Refusing to run non-SELECT statement (starts with '{first_word}'). "
            f"Only SELECT and WITH...SELECT statements are allowed. SQL was: {sql!r}"
        )

    body = stripped.rstrip(";").strip()
    if ";" in body:
        raise MetabaseError(
            f"Refusing to run stacked SQL statements (multiple statements "
            f"separated by ';'). SQL was: {sql!r}"
        )

    upper_body = body.upper()
    for keyword in WRITE_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_body):
            raise MetabaseError(
                f"Refusing to run SQL containing write keyword '{keyword}'. "
                f"SQL was: {sql!r}"
            )


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
        try:
            token = response.json().get("id")
        except ValueError as exc:
            raise MetabaseError(
                f"Metabase login for {self.config.email} succeeded ({response.status_code}) but "
                f"returned a non-JSON body (first 200 chars): {response.text[:200]!r}"
            ) from exc
        if not token:
            raise MetabaseError(
                f"Metabase login for {self.config.email} succeeded but returned no session id."
            )
        self._session_token = token
        return token

    def _headers(self) -> dict[str, str]:
        if self.config.uses_api_key:
            assert self.config.api_key is not None
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

        try:
            return response.json()
        except ValueError as exc:
            raise MetabaseError(
                f"Metabase request succeeded ({method} {path} -> {response.status_code}) but "
                f"returned a non-JSON body (first 200 chars): {response.text[:200]!r}"
            ) from exc

    def search(self, query: str, models: list[str] | None = None) -> Any:
        params: dict[str, Any] = {"q": query}
        if models:
            params["models"] = models
        return self._request("GET", "/api/search", params=params)

    def list_databases(self) -> Any:
        return self._request("GET", "/api/database")

    def list_tables(self, database_id: int) -> Any:
        return self._request("GET", f"/api/database/{database_id}/metadata")

    def list_collections(self) -> Any:
        return self._request("GET", "/api/collection")

    def get_dashboard(self, dashboard_id: int) -> Any:
        return self._request("GET", f"/api/dashboard/{dashboard_id}")

    def get_card(self, card_id: int) -> Any:
        return self._request("GET", f"/api/card/{card_id}")

    def run_card(self, card_id: int, parameters: list[dict[str, Any]] | None = None) -> Any:
        body = {"parameters": parameters or []}
        return self._request("POST", f"/api/card/{card_id}/query", json=body)

    def run_sql(self, database_id: int, sql: str) -> Any:
        validate_readonly_sql(sql)
        body = {
            "type": "native",
            "native": {"query": sql},
            "database": database_id,
        }
        return self._request("POST", "/api/dataset", json=body)
