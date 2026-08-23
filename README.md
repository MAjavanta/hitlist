# hitlist

Finds content creators for indie game developers to pitch.

A dev supplies Steam tags (or games similar to theirs) and hitlist returns a ranked list of
streamers who actually play that kind of game, with evidence: which games, when, how many
viewers.

The pipeline is:

1. Scrape Steam search to learn what games exist and which tags describe them.
2. Map those games to Twitch categories.
3. Poll Twitch hourly to build a time series of who streams what.
4. Rank creators by relevance and reach for a given game.

See [PLAN.md](PLAN.md) for the full plan and the reasoning behind it.

## Setup

This project uses [uv](https://docs.astral.sh/uv/). It is not pip — use the project commands
below rather than `pip install` or `uv pip install`, so `pyproject.toml` and `uv.lock` stay in
sync with what's actually installed.

```sh
uv sync
```

## Commands

Everything runs through `uv run hitlist`. Commands are added here as they're built.

| Command | What it does |
| --- | --- |
| `uv run hitlist` | Prints the first page of a Steam search (the original spike; will be replaced) |

## Layout

```
src/hitlist/     application code
data/            SQLite database and scraped data (gitignored)
PLAN.md          the plan, including schema and build order
```
