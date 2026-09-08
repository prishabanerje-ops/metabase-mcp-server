import pytest
from unittest.mock import MagicMock, patch

from metabase_client import MetabaseConfig, MetabaseError, MetabaseClient, validate_readonly_sql


def test_config_requires_metabase_url(monkeypatch):
    monkeypatch.delenv("METABASE_URL", raising=False)
    with pytest.raises(MetabaseError, match="METABASE_URL"):
        MetabaseConfig()


def test_config_requires_some_auth_method(monkeypatch):
    monkeypatch.setenv("METABASE_URL", "https://metabase.example.com")
    monkeypatch.delenv("METABASE_API_KEY", raising=False)
    monkeypatch.delenv("METABASE_EMAIL", raising=False)
    monkeypatch.delenv("METABASE_PASSWORD", raising=False)
    with pytest.raises(MetabaseError, match="auth"):
        MetabaseConfig()


def test_config_resolves_api_key_mode(monkeypatch):
    monkeypatch.setenv("METABASE_URL", "https://metabase.example.com")
    monkeypatch.setenv("METABASE_API_KEY", "test-key")
    monkeypatch.delenv("METABASE_EMAIL", raising=False)
    monkeypatch.delenv("METABASE_PASSWORD", raising=False)

    config = MetabaseConfig()

    assert config.uses_api_key is True
    assert config.url == "https://metabase.example.com"


def test_config_resolves_session_mode_and_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("METABASE_URL", "https://metabase.example.com/")
    monkeypatch.delenv("METABASE_API_KEY", raising=False)
    monkeypatch.setenv("METABASE_EMAIL", "a@b.com")
    monkeypatch.setenv("METABASE_PASSWORD", "secret")

    config = MetabaseConfig()

    assert config.uses_api_key is False
    assert config.url == "https://metabase.example.com"


def make_config(monkeypatch, *, api_key=None, email=None, password=None):
    monkeypatch.setenv("METABASE_URL", "https://metabase.example.com")
    if api_key:
        monkeypatch.setenv("METABASE_API_KEY", api_key)
    else:
        monkeypatch.delenv("METABASE_API_KEY", raising=False)
    if email:
        monkeypatch.setenv("METABASE_EMAIL", email)
    else:
        monkeypatch.delenv("METABASE_EMAIL", raising=False)
    if password:
        monkeypatch.setenv("METABASE_PASSWORD", password)
    else:
        monkeypatch.delenv("METABASE_PASSWORD", raising=False)
    return MetabaseConfig()


def make_response(status_code, json_body=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body if json_body is not None else {}
    response.text = text
    return response


@patch("metabase_client.requests.request")
def test_api_key_mode_never_calls_session_endpoint(mock_request, monkeypatch):
    config = make_config(monkeypatch, api_key="test-key")
    client = MetabaseClient(config)
    mock_request.return_value = make_response(200, {"ok": True})

    with patch("metabase_client.requests.post") as mock_post:
        result = client._request("GET", "/api/database")

    mock_post.assert_not_called()
    assert result == {"ok": True}
    assert mock_request.call_args.kwargs["headers"] == {"x-api-key": "test-key"}


@patch("metabase_client.requests.post")
@patch("metabase_client.requests.request")
def test_session_mode_authenticates_lazily_then_reuses_token(mock_request, mock_post, monkeypatch):
    config = make_config(monkeypatch, email="a@b.com", password="secret")
    client = MetabaseClient(config)
    mock_post.return_value = make_response(200, {"id": "session-token-1"})
    mock_request.return_value = make_response(200, {"ok": True})

    client._request("GET", "/api/database")
    client._request("GET", "/api/collection")

    assert mock_post.call_count == 1
    for call in mock_request.call_args_list:
        assert call.kwargs["headers"] == {"X-Metabase-Session": "session-token-1"}


@patch("metabase_client.requests.post")
@patch("metabase_client.requests.request")
def test_401_triggers_one_reauth_and_retry(mock_request, mock_post, monkeypatch):
    config = make_config(monkeypatch, email="a@b.com", password="secret")
    client = MetabaseClient(config)
    mock_post.side_effect = [make_response(200, {"id": "token-1"}), make_response(200, {"id": "token-2"})]
    mock_request.side_effect = [make_response(401, text="expired"), make_response(200, {"ok": True})]

    result = client._request("GET", "/api/database")

    assert result == {"ok": True}
    assert mock_post.call_count == 2
    assert mock_request.call_count == 2


@patch("metabase_client.requests.post")
@patch("metabase_client.requests.request")
def test_second_401_after_retry_raises(mock_request, mock_post, monkeypatch):
    config = make_config(monkeypatch, email="a@b.com", password="secret")
    client = MetabaseClient(config)
    mock_post.side_effect = [make_response(200, {"id": "token-1"}), make_response(200, {"id": "token-2"})]
    mock_request.side_effect = [make_response(401, text="expired"), make_response(401, text="still expired")]

    with pytest.raises(MetabaseError, match="401"):
        client._request("GET", "/api/database")


@patch("metabase_client.requests.request")
def test_error_response_raises_with_context(mock_request, monkeypatch):
    config = make_config(monkeypatch, api_key="test-key")
    client = MetabaseClient(config)
    mock_request.return_value = make_response(500, text="internal error")

    with pytest.raises(MetabaseError, match=r"GET /api/database"):
        client._request("GET", "/api/database")


def test_validate_accepts_select():
    validate_readonly_sql("SELECT * FROM policies LIMIT 10")  # must not raise


def test_validate_accepts_cte_with_select():
    validate_readonly_sql("WITH recent AS (SELECT * FROM policies) SELECT * FROM recent")  # must not raise


def test_validate_rejects_empty_sql():
    with pytest.raises(MetabaseError, match="empty"):
        validate_readonly_sql("   ")


def test_validate_rejects_delete():
    with pytest.raises(MetabaseError, match="DELETE"):
        validate_readonly_sql("DELETE FROM policies")


def test_validate_rejects_stacked_statements():
    with pytest.raises(MetabaseError, match="stacked"):
        validate_readonly_sql("SELECT 1; DROP TABLE policies")


def test_validate_rejects_write_keyword_inside_cte():
    with pytest.raises(MetabaseError, match="GRANT"):
        validate_readonly_sql("WITH x AS (SELECT 1) SELECT * FROM x WHERE 1=1 GRANT ALL")


def test_validate_rejects_select_into():
    with pytest.raises(MetabaseError, match="INTO"):
        validate_readonly_sql("SELECT * INTO evil_table FROM policies")


def test_validate_rejects_select_into_outfile():
    with pytest.raises(MetabaseError, match="INTO"):
        validate_readonly_sql("SELECT * FROM t INTO OUTFILE '/tmp/out.csv'")


@patch.object(MetabaseClient, "_request")
def test_search_sends_query_param(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"data": []}

    result = client.search("premium")

    mock_request.assert_called_once_with("GET", "/api/search", params={"q": "premium"})
    assert result == {"data": []}


@patch.object(MetabaseClient, "_request")
def test_search_with_models_filter(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"data": []}

    client.search("premium", models=["dashboard", "card"])

    mock_request.assert_called_once_with(
        "GET", "/api/search", params={"q": "premium", "models": ["dashboard", "card"]}
    )


@patch.object(MetabaseClient, "_request")
def test_list_databases(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"data": [{"id": 1}]}

    result = client.list_databases()

    mock_request.assert_called_once_with("GET", "/api/database")
    assert result == {"data": [{"id": 1}]}


@patch.object(MetabaseClient, "_request")
def test_list_tables(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"tables": []}

    client.list_tables(7)

    mock_request.assert_called_once_with("GET", "/api/database/7/metadata")


@patch.object(MetabaseClient, "_request")
def test_list_collections(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = []

    client.list_collections()

    mock_request.assert_called_once_with("GET", "/api/collection")


@patch.object(MetabaseClient, "_request")
def test_get_dashboard(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"id": 3}

    client.get_dashboard(3)

    mock_request.assert_called_once_with("GET", "/api/dashboard/3")


@patch.object(MetabaseClient, "_request")
def test_get_card(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"id": 9}

    client.get_card(9)

    mock_request.assert_called_once_with("GET", "/api/card/9")


@patch.object(MetabaseClient, "_request")
def test_run_card_posts_query_with_parameters(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"data": {"rows": []}}

    client.run_card(12, parameters=[{"id": "p1", "value": "x"}])

    mock_request.assert_called_once_with(
        "POST", "/api/card/12/query", json={"parameters": [{"id": "p1", "value": "x"}]}
    )


@patch.object(MetabaseClient, "_request")
def test_run_card_defaults_to_empty_parameters(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"data": {"rows": []}}

    client.run_card(12)

    mock_request.assert_called_once_with("POST", "/api/card/12/query", json={"parameters": []})


@patch.object(MetabaseClient, "_request")
def test_run_sql_sends_native_query(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"data": {"rows": []}}

    client.run_sql(5, "SELECT * FROM policies LIMIT 10")

    mock_request.assert_called_once_with(
        "POST",
        "/api/dataset",
        json={"type": "native", "native": {"query": "SELECT * FROM policies LIMIT 10"}, "database": 5},
    )


@patch.object(MetabaseClient, "_request")
def test_run_sql_rejects_delete_without_http_call(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))

    with pytest.raises(MetabaseError, match="DELETE"):
        client.run_sql(5, "DELETE FROM policies")

    mock_request.assert_not_called()


@patch.object(MetabaseClient, "_request")
def test_run_sql_rejects_stacked_statements(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))

    with pytest.raises(MetabaseError, match="stacked"):
        client.run_sql(5, "SELECT 1; DROP TABLE policies")

    mock_request.assert_not_called()


@patch.object(MetabaseClient, "_request")
def test_run_sql_accepts_cte(mock_request, monkeypatch):
    client = MetabaseClient(make_config(monkeypatch, api_key="test-key"))
    mock_request.return_value = {"data": {"rows": []}}

    client.run_sql(5, "WITH recent AS (SELECT * FROM policies) SELECT * FROM recent")

    mock_request.assert_called_once()
