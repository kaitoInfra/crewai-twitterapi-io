import json
import os
from typing import Any, Literal

from crewai.tools import BaseTool, EnvVar
from pydantic import BaseModel, Field, PrivateAttr
import requests


TWITTERAPI_IO_BASE_URL = "https://api.twitterapi.io"
_MAX_RESULTS_CAP = 100


def _compact_tweet(tweet: dict[str, Any]) -> dict[str, Any]:
    """Keep the fields an agent usually needs and drop the rest."""
    author = tweet.get("author") or {}
    return {
        "id": tweet.get("id"),
        "url": tweet.get("url"),
        "text": tweet.get("text"),
        "created_at": tweet.get("createdAt"),
        "lang": tweet.get("lang"),
        "like_count": tweet.get("likeCount"),
        "retweet_count": tweet.get("retweetCount"),
        "reply_count": tweet.get("replyCount"),
        "quote_count": tweet.get("quoteCount"),
        "view_count": tweet.get("viewCount"),
        "author": {
            "username": author.get("userName"),
            "name": author.get("name"),
            "followers": author.get("followers"),
            "is_blue_verified": author.get("isBlueVerified"),
        },
    }


class _TwitterApiIoBase(BaseTool):
    """Shared settings for the TwitterAPI.io tools."""

    base_url: str = TWITTERAPI_IO_BASE_URL
    timeout: int = 30
    _api_key: str | None = PrivateAttr(default=None)
    env_vars: list[EnvVar] = Field(
        default_factory=lambda: [
            EnvVar(
                name="TWITTERAPI_IO_API_KEY",
                description="API key for TwitterAPI.io (https://twitterapi.io)",
                required=True,
            ),
        ]
    )

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key or os.getenv("TWITTERAPI_IO_API_KEY")
        if not self._api_key:
            raise ValueError(
                "TWITTERAPI_IO_API_KEY environment variable or api_key argument is "
                f"required for {type(self).__name__}"
            )

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            headers={"X-API-Key": self._api_key, "Accept": "application/json"},
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


class TwitterApiIoSearchToolSchema(BaseModel):
    """Input for TwitterApiIoSearchTool."""

    query: str = Field(
        ...,
        description=(
            "Search query. Supports X advanced search operators, for example "
            "'from:elonmusk', '\"exact phrase\"', 'lang:en', 'since:2025-01-01', "
            "'min_faves:100' or '#hashtag'."
        ),
    )
    query_type: Literal["Latest", "Top"] = Field(
        default="Latest", description="'Latest' for newest first, 'Top' for most relevant."
    )
    max_results: int = Field(
        default=20,
        ge=1,
        le=_MAX_RESULTS_CAP,
        description="Maximum number of tweets to return (1-100).",
    )


class TwitterApiIoSearchTool(_TwitterApiIoBase):
    """Search recent tweets on X (Twitter) through the TwitterAPI.io REST API."""

    name: str = "Search tweets on X (Twitter)"
    description: str = (
        "Searches tweets on X (Twitter) with optional advanced search operators "
        "and returns matching tweets as JSON (text, link, time, engagement and author)."
    )
    args_schema: type[BaseModel] = TwitterApiIoSearchToolSchema

    def _run(
        self, query: str, query_type: str = "Latest", max_results: int = 20, **kwargs: Any
    ) -> str:
        max_results = max(1, min(int(max_results), _MAX_RESULTS_CAP))
        tweets: list[dict[str, Any]] = []
        cursor = ""
        try:
            while len(tweets) < max_results:
                params = {"query": query, "queryType": query_type}
                if cursor:
                    params["cursor"] = cursor
                data = self._get("/twitter/tweet/advanced_search", params)
                page = data.get("tweets") or []
                tweets.extend(_compact_tweet(t) for t in page)
                cursor = data.get("next_cursor") or ""
                if not page or not data.get("has_next_page") or not cursor:
                    break
        except requests.RequestException as e:
            return json.dumps({"success": False, "error": str(e)})
        return json.dumps({"success": True, "tweets": tweets[:max_results]}, ensure_ascii=False)


class TwitterApiIoUserToolSchema(BaseModel):
    """Input for TwitterApiIoUserTool."""

    username: str = Field(
        ..., description="X (Twitter) username without the @, for example 'elonmusk'."
    )
    include_tweets: bool = Field(
        default=True, description="Also return the user's most recent tweets."
    )


class TwitterApiIoUserTool(_TwitterApiIoBase):
    """Look up an X (Twitter) user's profile and recent tweets through TwitterAPI.io."""

    name: str = "Get an X (Twitter) user's profile and recent tweets"
    description: str = (
        "Returns the public profile of an X (Twitter) user (bio, follower counts, "
        "verification) and optionally their most recent tweets, as JSON."
    )
    args_schema: type[BaseModel] = TwitterApiIoUserToolSchema

    def _run(self, username: str, include_tweets: bool = True, **kwargs: Any) -> str:
        username = username.strip().lstrip("@")
        try:
            info = self._get("/twitter/user/info", {"userName": username})
            user = info.get("data") or {}
            if info.get("status") != "success" or not user:
                return json.dumps(
                    {"success": False, "error": info.get("msg") or "user not found"}
                )
            result: dict[str, Any] = {
                "success": True,
                "user": {
                    "id": user.get("id"),
                    "username": user.get("userName"),
                    "name": user.get("name"),
                    "description": user.get("description"),
                    "location": user.get("location"),
                    "followers": user.get("followers"),
                    "following": user.get("following"),
                    "tweet_count": user.get("statusesCount"),
                    "is_blue_verified": user.get("isBlueVerified"),
                    "created_at": user.get("createdAt"),
                    "url": f"https://x.com/{user.get('userName') or username}",
                },
            }
            if include_tweets:
                last = self._get("/twitter/user/last_tweets", {"userName": username})
                tweets = (last.get("data") or {}).get("tweets") or []
                result["recent_tweets"] = [_compact_tweet(t) for t in tweets]
        except requests.RequestException as e:
            return json.dumps({"success": False, "error": str(e)})
        return json.dumps(result, ensure_ascii=False)
