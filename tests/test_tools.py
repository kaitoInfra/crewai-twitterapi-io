import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from crewai_twitterapi_io import TwitterApiIoSearchTool, TwitterApiIoUserTool


def _resp(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


def _tweet(i):
    return {
        "id": str(i),
        "url": f"https://x.com/a/status/{i}",
        "text": f"tweet {i}",
        "createdAt": "Tue Oct 14 10:00:00 +0000 2026",
        "lang": "en",
        "likeCount": i,
        "retweetCount": 0,
        "replyCount": 0,
        "quoteCount": 0,
        "viewCount": 10,
        "author": {"userName": "a", "name": "A", "followers": 5, "isBlueVerified": False},
        "extraField": "dropped",
    }


@pytest.fixture(autouse=True)
def api_key():
    with patch.dict(os.environ, {"TWITTERAPI_IO_API_KEY": "test_key"}):
        yield


def test_requires_api_key():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError):
            TwitterApiIoSearchTool()


def test_api_key_argument_overrides_env():
    with patch.dict(os.environ, {}, clear=True):
        tool = TwitterApiIoSearchTool(api_key="k")
        with patch("requests.get", return_value=_resp({"tweets": [], "has_next_page": False})) as g:
            tool.run(query="x")
        assert g.call_args.kwargs["headers"]["X-API-Key"] == "k"


@patch("requests.get")
def test_search_paginates_and_compacts(mock_get):
    mock_get.side_effect = [
        _resp({"tweets": [_tweet(i) for i in range(20)], "has_next_page": True, "next_cursor": "c1"}),
        _resp({"tweets": [_tweet(i) for i in range(20, 40)], "has_next_page": True, "next_cursor": "c2"}),
    ]
    out = json.loads(TwitterApiIoSearchTool().run(query="from:a", max_results=25))
    assert out["success"] is True
    assert len(out["tweets"]) == 25
    assert "extraField" not in out["tweets"][0]
    assert out["tweets"][0]["author"]["username"] == "a"
    assert mock_get.call_count == 2
    first, second = (c.kwargs["params"] for c in mock_get.call_args_list)
    assert first == {"query": "from:a", "queryType": "Latest"}
    assert second["cursor"] == "c1"


@patch("requests.get")
def test_search_stops_when_no_next_page(mock_get):
    mock_get.return_value = _resp({"tweets": [_tweet(1)], "has_next_page": False, "next_cursor": ""})
    out = json.loads(TwitterApiIoSearchTool().run(query="q", max_results=50))
    assert len(out["tweets"]) == 1
    assert mock_get.call_count == 1


@patch("requests.get", side_effect=requests.ConnectionError("boom"))
def test_search_returns_error_instead_of_raising(_):
    out = json.loads(TwitterApiIoSearchTool().run(query="q"))
    assert out == {"success": False, "error": "boom"}


@patch("requests.get")
def test_user_profile_and_tweets(mock_get):
    mock_get.side_effect = [
        _resp({"status": "success", "data": {"id": "1", "userName": "OpenAI", "name": "OpenAI", "followers": 10, "statusesCount": 3}}),
        _resp({"status": "success", "data": {"tweets": [_tweet(1), _tweet(2)]}}),
    ]
    out = json.loads(TwitterApiIoUserTool().run(username="@OpenAI"))
    assert out["success"] is True
    assert out["user"]["username"] == "OpenAI"
    assert out["user"]["tweet_count"] == 3
    assert out["user"]["url"] == "https://x.com/OpenAI"
    assert len(out["recent_tweets"]) == 2
    assert mock_get.call_args_list[0].kwargs["params"] == {"userName": "OpenAI"}


@patch("requests.get")
def test_user_without_tweets_makes_one_call(mock_get):
    mock_get.return_value = _resp({"status": "success", "data": {"userName": "a"}})
    out = json.loads(TwitterApiIoUserTool().run(username="a", include_tweets=False))
    assert "recent_tweets" not in out
    assert mock_get.call_count == 1


@patch("requests.get")
def test_user_not_found(mock_get):
    mock_get.return_value = _resp({"status": "error", "msg": "user not found", "data": None})
    out = json.loads(TwitterApiIoUserTool().run(username="nobody"))
    assert out == {"success": False, "error": "user not found"}
