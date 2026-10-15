# crewai-twitterapi-io

[CrewAI](https://crewai.com) tools for reading X (Twitter) data through the [TwitterAPI.io](https://twitterapi.io) REST API. No X developer account is needed, only a TwitterAPI.io API key.

| Tool | What it does |
|---|---|
| `TwitterApiIoSearchTool` | Searches tweets, with X advanced search operators (`from:`, `"exact phrase"`, `lang:`, `since:`, `min_faves:`, `#hashtag` ...). Paginates up to 100 results. |
| `TwitterApiIoUserTool` | Returns a user's public profile (bio, followers, verification) and, optionally, their most recent tweets. |

Both tools are read-only and return compact JSON (text, link, time, engagement counts and author for each tweet), which keeps agent context small.

## Install

```shell
pip install crewai-twitterapi-io
```

Get an API key at [twitterapi.io](https://twitterapi.io) and set it as an environment variable:

```shell
export TWITTERAPI_IO_API_KEY="your_key"
```

You can also pass it directly: `TwitterApiIoSearchTool(api_key="your_key")`.

## Example

```python
from crewai import Agent, Crew, Task
from crewai_twitterapi_io import TwitterApiIoSearchTool, TwitterApiIoUserTool

researcher = Agent(
    role="Social media researcher",
    goal="Summarize what people on X are saying about a topic",
    backstory="You track conversations on X and report the key points with links.",
    tools=[TwitterApiIoSearchTool(), TwitterApiIoUserTool()],
)

task = Task(
    description="Find the 30 most recent English tweets about 'crewAI' and summarize the main themes, citing tweet links.",
    expected_output="A short summary with 3-5 themes and example tweet links.",
    agent=researcher,
)

print(Crew(agents=[researcher], tasks=[task]).kickoff())
```

Calling a tool directly:

```python
from crewai_twitterapi_io import TwitterApiIoSearchTool, TwitterApiIoUserTool

print(TwitterApiIoSearchTool().run(query="from:OpenAI", query_type="Latest", max_results=10))
print(TwitterApiIoUserTool().run(username="OpenAI", include_tweets=True))
```

## Parameters

`TwitterApiIoSearchTool.run(query, query_type="Latest", max_results=20)`
- `query`: search text, X advanced search operators supported.
- `query_type`: `"Latest"` (newest first) or `"Top"` (most relevant).
- `max_results`: 1-100.

`TwitterApiIoUserTool.run(username, include_tweets=True)`
- `username`: X username, with or without `@`.
- `include_tweets`: also return the most recent tweets.

On a network or API error the tools return `{"success": false, "error": "..."}` instead of raising, so the agent can decide what to do.

## Pricing

Requests are billed to your TwitterAPI.io account. See [twitterapi.io/pricing](https://twitterapi.io/pricing).

## License

MIT
