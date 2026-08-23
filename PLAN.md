# Hitlist — Steam ingestion → Twitch collection → first creator lists

## Context

You are building a tool that tells indie game devs which content creators to pitch. A dev
supplies either Steam tags or games similar to theirs; the tool returns a ranked list of
streamers who actually play that kind of game, with supporting evidence (which games, when,
how many viewers).

The data pipeline is: **scrape Steam** to learn what games exist and what tags describe them →
**map those games to Twitch categories** → **poll Twitch hourly** to build a time series of who
streams what → **rank** creators by relevance and reach for a given dev's game.

Today the repo is 18 lines: one `requests` + `BeautifulSoup` call that prints the first 50 rows
of a Steam search, plus a 466 KB saved copy of Steam's tag filter sidebar. This plan takes it to
the point where you can hand a real indie dev a CSV they'd find useful, with no API and no
frontend.

---

## 1. Review of the plan

**The core idea is sound and the sequencing is right.** The genuinely hard, genuinely valuable
asset here is the *time series* — a record of who streamed what, when, to how many people.
Nobody can buy that retroactively, and Twitch's `Get Streams` only reports who is live *right
now*, so every hour you don't collect is an hour that is gone forever. That means the single
most important thing in this plan is: **start the hourly poller as early as possible**, well
before the ranking algorithm, the API, or anything else is good. Everything else in this
document is in service of getting a poller running against a decent game list quickly.

**Scraping Steam search and keeping only the top 7 tags is the right call.** Your reasoning about
PEAK is correct and worth restating: Steam's tag *filter* matches all ~20 tags, so it has high
recall and poor precision; the `data-ds-tagids` array is the top 7 by vote weight, so it has
high precision. Using the filter to *discover* games and the top-7 to *describe* them gets you
both. Store the array **in order** — position is a strength signal you'll want later, and it's
free.

**Two things you haven't exploited yet.** First, `store.steampowered.com/search/results/` with
`&infinite=1&start=N&count=100` returns JSON (`success`, `results_html`, `total_count`, `start`)
instead of a full page. `count` caps at 100, deep paging is uncapped (verified `start=21800` on
tag 1667), and `total_count` lets you plan a run before you make it. Second, each result row
already carries release date, price (`data-price-final`, in cents), and a review tooltip
(`"85% of the 789 user reviews for this game are positive."`). Grab all of it — review count is
your best available proxy for "is this game big enough to have been streamed", and you'll use it
to decide which games are worth trying to match to Twitch.

**The biggest unsolved risk is Steam ↔ Twitch identity.** Twitch categories are free-text names
with no Steam appid on them. Exact name matching will fail on editions, subtitles, punctuation,
and non-Latin titles. Plan for a multi-strategy matcher with a recorded `method` and
`confidence` per link, plus a hand-maintained overrides file — and only bother matching games
plausibly big enough to appear on Twitch, not all 32k.

**On whether clips imply an audience — yes, mostly, with a caveat worth knowing.** A clip only
exists because someone was watching and pressed the button, so *the existence of clips is a real
audience signal* and a good filter against dead channels. But `view_count` on a clip counts views
of the clip page — including embeds, Reddit, and Twitter — so a tiny streamer can have one viral
clip. Treat clips as a **recall/bootstrap signal** ("this person has streamed this game and
someone cared") and let the accumulating stream snapshots be the **authority on reach**. Also
note `creator_id` is whoever made the clip and `broadcaster_id` is the streamer — you want
`broadcaster_id`.

**Two design notes.** `Get Streams` accepts up to **100 `game_id` values per request**, so polling
1,000 games costs ~10 requests plus cursor pages, not 1,000 — hourly polling is effectively free
and you should build the poller around batched game ids from the start. And when you get to
ranking, weight tags by inverse document frequency: this is the precise, standard fix for your
"every game is Action" objection — a tag on 90,000 games carries almost no information, a tag on
1,600 carries a lot, and IDF computes that weighting from data you'll already have.

---

## 2. Overarching roadmap

Each stage should produce something you could show someone. Expect to divert on feedback.

| # | Stage | Outcome |
|---|---|---|
| 0 | Repo hygiene + Steam tag lookup table | Tag id → name in SQLite |
| 1 | Steam game + tag ingestion for 5 seed tags | ~32k games with ordered top-7 tags |
| 2 | Twitch app credentials + Steam→Twitch category matching | Linked game list, coverage measured |
| 3 | **Hourly stream poller running** | Time series starts accumulating — do this early |
| 4 | Clip backfill (12 months) + weekly incremental | Usable creator data on day one |
| 5 | Hand-written SQL queries → CSV, given to devs manually | **First thing a real dev sees** |
| 6 | Feedback loop: 3–5 devs, learn how they want lists ranked | Validated output, and a spec for ranking |
| 7 | Add VOD collection; add streamer enrichment (followers, socials) | Better coverage and contactability |
| 8 | Widen tag coverage beyond the 5 seeds | More niches served |
| 9 | Postgres migration | Multi-reader, ready for an API |
| 10 | C#/.NET API over the DB, **with the ranking algorithm in it** | Programmatic access, paid lists |
| 11 | React UI | Self-serve product |

The commercial logic behind stages 5–10: if devs find the manual, hand-queried lists useful, that
is the evidence that a properly ranked version is worth paying for. Build the algorithm after
that's proven and after devs have told you what "good" means to them — not before.

**Stages 0–5 are this plan.** Stage 3 can and should start before 5 is finished — the moment you
have *any* linked game list, turn the poller on and let it run while you build the ranking.

Postgres (stage 9) is deliberately late: SQLite is genuinely fine for a single-writer hourly
collector, and moving is cheap if you keep raw responses on disk and only use portable SQLModel
column types.

---

## 3. Detailed plan to the first user-facing output

### 3.0 Seed tags

Five tags, chosen so that one is your horror anchor, all are indie-dominated, and the set spans
enough tag-space to actually exercise a similarity algorithm (Cozy and Colony Sim should score
near zero against Horror; Metroidvania and Roguelike Deckbuilder should partially overlap through
Roguelike / 2D / Pixel Graphics):

| Tag | ID | Games | Why |
|---|---|---|---|
| Horror | 1667 | 21,838 | Your target niche; broad anchor |
| Metroidvania | 1628 | 3,321 | Indie-defining, specific, real Twitch presence |
| Cozy | 97376 | 4,130 | Deliberate opposite pole — negative control for matching |
| Colony Sim | 220585 | 2,120 | Specific, distinctive creator scene |
| Roguelike Deckbuilder | 1091588 | 1,644 | Your own example; maximally informative tag |

~33,000 rows before dedup ≈ **330 requests** at `count=100`. At a 1.5 s delay that's about eight
minutes. Add Survival Horror (3978, 8,330 games) or Boomer Shooter (1023537, 1,285 games) later
if you want; the code takes a list, so widening is a config change.

Note a sweep of tag 1667 will *also* record sub-tags like Survival Horror inside those games'
top-7, so you get sub-genre resolution without sweeping the sub-tags separately.

Other verified counts for reference: Psychological Horror (1721) 14,760 · Action Roguelike
(42804) 10,674 · Immersive Sim (9204) 9,912 · Souls-like (29482) 3,233 · Extraction Shooter
(1199779) 253.

### 3.1 Repo hygiene — DONE

- Root `.gitignore` covering `__pycache__/`, `*.py[cod]`, `.venv/`, `data/`, `.env`, and
  `tag_filter_container.html`.
- `git rm --cached src/hitlist/__pycache__/__init__.cpython-312.pyc` — it was **tracked**.
- `.venv` was never tracked: uv writes a `.venv/.gitignore` containing `*`, so it excludes itself.
- `tag_filter_container.html` is gitignored rather than committed. It stays on disk as an offline
  reference for checking parser selectors; delete it whenever you like.
- Dependencies added with **uv, not pip**: `uv add sqlmodel typer`. Deliberately *not* added yet —
  `tenacity` (retries aren't a problem yet) and `pydantic-settings` (a plain `config.py` of module
  constants is centralised and needs no dependency; add settings-from-env when Twitch secrets
  arrive). Run everything with `uv run`; never `uv pip install` for project deps.
- `README.md` now lists the commands, and gains a row each time we build one.

### 3.2 On when and how to structure

Your instinct is right: people don't design the final tree up front. The rule that works is
**structure follows a second caller.** Extract a module the moment two things need the same code,
or the moment one file mixes network I/O, parsing, and database writes and passes ~200 lines.
Three beats:

**Beat 1 — now, minimal.** `src/hitlist/__init__.py` becomes empty (just `__version__`). Create
`cli.py`, `db.py`, `models.py`, `config.py`, and a `steam.py`. That's it — you already have three
concerns (fetching, parsing, storing) crammed into one function, which is the trigger.

`config.py` is the one place every knob lives: database path, seed tag ids, base URLs, any delay.
Adding a tag should mean editing one list in one file, and nothing else.

**Beat 2 — as soon as you touch Twitch.** Split by *external system*, not by architectural layer.
Layers ("services", "repositories") are a Java habit that adds indirection without adding
clarity at this size; systems have genuinely different auth, rate limits, and failure modes. At
that point `models.py` also becomes a `models/` package so Steam and Twitch tables don't share a
file:

```
src/hitlist/
  __init__.py        # __version__ only
  config.py          # every knob: db path, seed tags, URLs, creds
  db.py              # engine, get_session(), init_db()
  models/
    steam.py         # Tag, Game, GameTag
    twitch.py        # TwitchGame, GameTwitchLink, Streamer, StreamSnapshot, Clip
  cli.py             # typer app; thin — arg parsing and calls only
  steam/
    client.py        # fetching
    parse.py         # PURE: html string -> dataclasses. No network, no DB.
    ingest.py        # dataclasses -> DB upserts
  twitch/
    client.py        # token management + helix wrappers + pagination
    ingest.py
data/                # gitignored
  hitlist.db
```

**No beat 3.** Ranking is going to live in the C#/.NET API, not here. Python's job ends at "there
is a good database". The first lists for devs come out of hand-written SQL queries — if devs like
those, that's the signal that a properly ranked version is worth building, and it gets built in
C# with input from the devs themselves on how they want it ranked.

**The one split that matters most** is `parse.py` being pure functions taking an HTML/JSON string
and returning dataclasses, with no network and no database. That's what makes the parsing testable
without hitting Steam, and what keeps a parser change from being tangled up with a fetching
change.

**The trigger for all of this, worth restating:** refactor when a file starts mixing network I/O,
parsing, and database writes — or when it simply gets too long. Not before.

### 3.3 Database schema

**Build the Steam tables first and only those.** The Twitch tables below are here so the shape is
visible, not because they should be written now — they get added when Twitch does, at which point
`models.py` splits into `models/steam.py` and `models/twitch.py`.

Answering "how do I make a lookup table": in SQLModel a lookup table is just a table whose
primary key you supply yourself instead of letting SQLite autoincrement. `Field(primary_key=True)`
on an `int` without a default means "I provide this" — which is exactly right for Steam tag ids
and appids, because they're stable natural keys and using them saves you a join everywhere.

Start with, in `models.py`:

```python
class Tag(SQLModel, table=True):
    """Lookup: Steam tag id -> name. id is Steam's, not ours."""
    id: int = Field(primary_key=True)
    name: str = Field(index=True)

class Game(SQLModel, table=True):
    appid: int = Field(primary_key=True)
    title: str
    released_on: date | None = None
    release_text: str | None = None      # raw: "Coming soon", "Q3 2026"
    review_summary: str | None = None    # "Very Positive"
    review_pct: int | None = None
    review_count: int | None = None      # best proxy for "is this streamable"
    price_final: int | None = None       # cents
    first_seen_at: datetime
    last_seen_at: datetime

class GameTag(SQLModel, table=True):
    """Junction: 7 rows per game. Composite PK = two primary_key=True fields."""
    appid: int = Field(foreign_key="game.appid", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)
    rank: int                            # 0-6, position in data-ds-tagids
```

Twitch side — **later, when you get to step 3**, in `models/twitch.py`:

```python
class TwitchGame(SQLModel, table=True):
    id: str = Field(primary_key=True)    # Twitch category id is a STRING
    name: str = Field(index=True)
    igdb_id: str | None = None

class GameTwitchLink(SQLModel, table=True):
    appid: int = Field(foreign_key="game.appid", primary_key=True)
    twitch_game_id: str = Field(foreign_key="twitchgame.id", primary_key=True)
    method: str                          # exact_name | search | igdb | manual
    confidence: float
    linked_at: datetime

class Streamer(SQLModel, table=True):
    id: str = Field(primary_key=True)    # twitch user_id
    login: str = Field(index=True)
    display_name: str
    # enriched later: follower count, description, socials

class StreamSnapshot(SQLModel, table=True):
    """One row per (live stream, poll). The asset."""
    id: int | None = Field(default=None, primary_key=True)
    captured_at: datetime = Field(index=True)
    stream_id: str = Field(index=True)   # stable for one broadcast
    streamer_id: str = Field(foreign_key="streamer.id", index=True)
    twitch_game_id: str = Field(index=True)
    viewer_count: int
    started_at: datetime
    language: str
    title: str

class Clip(SQLModel, table=True):
    id: str = Field(primary_key=True)
    broadcaster_id: str = Field(index=True)
    twitch_game_id: str = Field(index=True)
    view_count: int
    created_at: datetime = Field(index=True)
    title: str
    url: str
    fetched_at: datetime

class CollectionRun(SQLModel, table=True):
    """Provenance. Makes gaps in the time series visible instead of invisible."""
    id: int | None = Field(default=None, primary_key=True)
    command: str
    started_at: datetime
    finished_at: datetime | None = None
    rows_written: int = 0
    ok: bool = False
    error: str | None = None
```

Two notes. `stream_id` is what lets you later collapse hourly snapshots into *broadcasts* with a
duration, peak, and average — that rollup is the real analytical unit. And `CollectionRun` is
not optional bookkeeping: without it you cannot tell "nobody streamed horror at 4am" from "the
poller was down at 4am", and those mean opposite things.

Use `SQLModel.metadata.create_all()` for now. Add Alembic at stage 9, not before.

### 3.4 Build order

Each step is the simplest thing that works. Retries, resumability, rate limiting, and raw-response
archiving are all explicitly **not** in scope until their absence causes an actual problem.

**Step 1 — DB + tag lookup.** `hitlist db init` creates `data/hitlist.db`. Then
`hitlist steam sync-tags` **fetches the tag sidebar live from Steam** — no local file, no
`--from-file` flag. Any search page carries the full sidebar. Select
`div.tab_filter_control_row`, read `data-value` and `data-loc`, `.strip()` the names (some have
trailing spaces), skip anything where `data-param != "tags"`. That yields 430 rows with no dedup
needed — the outer div fully describes each tag, and the inner spans only repeat it. Ignore
`tab_filter_control_count`; only ~25 are populated and they're relative to the current query.

**Step 2 — Steam game sweep.** `hitlist steam sync-games`, reading the seed tag list from
`config.py`. Loop `start=0, 100, 200…` against
`https://store.steampowered.com/search/results/?query&start={n}&count=100&infinite=1&hwtype=0&category1=998&ndl=1&tags={id}`,
stop when `start >= total_count`. Parse `results_html` with BeautifulSoup + lxml, extract per row:
`data-ds-appid`, `data-ds-tagids` (JSON array, keep order), `span.title`, `div.search_released`,
`data-price-final`, and the `data-tooltip-html` review string (regex out percent and count; it's
HTML-escaped). Upsert games, replace that game's `GameTag` rows wholesale. Single-threaded with a
small sleep between requests, because it costs nothing and keeps the sweep obviously polite.
**On `ndl=1`:** keep it — it drops the English-only default, and a Japanese horror game with no
English store page can still be streamed. `hwtype=0` is a Steam Deck filter parameter in its
neutral state; harmless, keep it for fidelity with the real page.

**Step 3 — Twitch credentials.** Register an app at dev.twitch.tv, get client id + secret into
`.env` (gitignored), read via pydantic-settings. Fetch an app access token from
`POST https://id.twitch.tv/oauth2/token?grant_type=client_credentials`, cache it with its expiry,
refresh on 401. App tokens get 800 rate-limit points/min, which you will not come close to.

**Step 4 — Steam ↔ Twitch matching.** `hitlist twitch resolve-games`. This is the risky step, so
attack it in order of cost, and **only for games worth matching** — order by `review_count desc`
and take the top ~2,000; the long tail of zero-review horror shovelware has no Twitch presence
and matching it is wasted effort.

1. Normalise names (casefold, strip ™ ® and punctuation, drop leading "the", strip
   "Definitive/GOTY/Deluxe Edition" suffixes) and batch against `helix/games?name=` — **100 names
   per request**.
2. For misses, try `helix/search/categories?query=` and accept only a high-similarity match.
3. **Spike, then decide:** IGDB is owned by Twitch and takes the *same* client credentials, and
   its `external_games` data maps Steam appids to IGDB ids; `helix/games?igdb_id=` then maps IGDB
   ids to Twitch categories. If it works this is an exact join rather than fuzzy matching. Verify
   on 50 games you know before building on it — don't assume.
4. Record `method` and `confidence`; keep `data/manual_overrides.csv` for hand fixes and apply it
   last so it always wins.

Then **measure and print coverage** — what fraction of your top-2,000 matched, and what the
biggest unmatched games are. That number tells you whether to invest more here.

**Step 5 — turn the poller on.** `hitlist twitch poll-streams`. Take every distinct
`twitch_game_id` in `GameTwitchLink`, chunk into 100s, and for each chunk call
`helix/streams?game_id=…&game_id=…&first=100`, following the `pagination.cursor` until exhausted.
Upsert `Streamer`, insert one `StreamSnapshot` per live stream with a single `captured_at` for
the whole run. Wrap it in a `CollectionRun`. Get this running before you build anything else —
every hour it isn't running is data that cannot be recovered.

**Step 6 — clip backfill.** `hitlist twitch backfill-clips --since 2025-08-23`. Per
`twitch_game_id`, call `helix/clips?game_id=…&started_at=…&ended_at=…&first=100` and page. Clips
come back ordered by view count, and a single query realistically surfaces up to ~1,000 per
window, so **window it monthly** rather than asking for a whole year at once — otherwise you only
ever see the same top clips and miss the mid-tail creators who are exactly your target. Then run
a weekly incremental over the last 7 days.

**Step 7 — the first lists, by hand.** No ranking code in Python. Once the database has a couple
of weeks of snapshots plus clips, write SQL queries by hand, export the results, and give them to
devs. That's the cheapest possible test of whether the output is worth anything, and it's the
thing that tells you what devs actually want ranked before you commit to an algorithm.

The queries want, per streamer, over the Twitch categories linked to games similar to the dev's:
hours observed, median and peak viewers, distinct matching games played, most recent stream, and
clip count. Emit `login, display_name, twitch_url, median_viewers, peak_viewers, hours_observed,
matching_games_played, top_matching_games, last_seen, clip_count, language`. The evidence columns
matter as much as the order — a dev needs to see *why* someone is on the list before they'll
trust it.

When ranking does get built, it goes in the C#/.NET API, informed by what the devs say. Two ideas
worth carrying over when you get there:

- **Weight tags by IDF** — `log(total_games / games_with_tag)` over your own `GameTag` table.
  This is the fix for the "every game is Action" problem: Singleplayer sits on ~116k games and
  gets a near-zero weight automatically, while Roguelike Deckbuilder gets a large one. No
  hand-tuning, and it improves as tag coverage widens.
- **Down-weight the very largest channels.** A 40k-viewer streamer will not answer an indie dev's
  email; the useful band is roughly 50–2,000 concurrent. Relevance × reach alone will sort the
  unreachable people straight to the top, which makes the list feel useless.

### 3.5 Testing — deferred

Worth doing, not worth doing yet. When it's time, the three that pay for themselves are: parse
tests against saved real responses (possible because `parse.py` is pure), one round-trip test
asserting 7 correctly-ordered `GameTag` rows for a known appid, and one test that ingesting twice
is idempotent.

---

## 4. Operating it

### What you actually run

Everything is one CLI, every command idempotent and resumable:

```
uv run hitlist db init
uv run hitlist steam sync-tags             # fetches the tag sidebar from Steam
uv run hitlist steam sync-games            # uses seed tags from config.py
uv run hitlist twitch resolve-games
uv run hitlist twitch poll-streams         # <- hourly
uv run hitlist twitch backfill-clips
```

Lists for devs come out of hand-written SQL against `data/hitlist.db`, not a command.

### Scheduling

**Do not reach for Airflow, Celery, or Prefect.** A cron entry calling an idempotent CLI command
is the correct amount of machinery here, and will remain correct for years. The `CollectionRun`
table is your monitoring.

**Now — your laptop.** Windows Task Scheduler, hourly:

```
schtasks /create /tn "hitlist-poll" /sc hourly ^
  /tr "cmd /c cd /d C:\Users\mahma\CodeProjects\hitlist && uv run hitlist twitch poll-streams >> data\poll.log 2>&1"
```

**Then — move it off the laptop, sooner than you'd think.** The reason isn't data loss, it's
**sampling bias**, and this is the part that's easy to underestimate. If your laptop is closed
every night from 01:00 to 09:00, you don't lose a random 33% of your data — you systematically
lose *European morning and Asian prime-time streamers entirely*, and your rankings become
confidently wrong in a way nothing in the data will reveal. Random gaps are survivable;
correlated gaps corrupt the dataset.

So: run on the laptop for the first week or two while you're still changing the schema and
throwing data away anyway. The moment you start collecting data you intend to *keep*, move to a
~€4/month Hetzner CX22 or equivalent. Deployment is `git pull`, `uv sync`, and one systemd timer;
SQLite lives on the box, and a nightly `sqlite3 data/hitlist.db ".backup"` into a dated file
(plus an rsync home) is sufficient backup at this scale.

### "Hetzner vs. deploying onto something" — what the options are

Two different kinds of thing:

- **A VPS** (Hetzner, DigitalOcean, Vultr, Linode) is a whole Linux machine you rent and manage.
  You SSH in, install things, and it has a real disk that persists. ~€4/month.
- **A PaaS** (Railway, Render, Fly.io, Heroku) runs your code for you from a Git push. No server
  to manage — but the filesystem is usually **ephemeral**, wiped on every deploy and restart.

That last point is the whole answer for you: **an ephemeral filesystem destroys a SQLite
database.** Render's cron jobs, for example, have no persistent disk at all, so you'd be forced
onto their managed Postgres at ~$7/month — more expensive *and* a bigger change than the VPS,
just to run an hourly script. Fly.io can attach a persistent volume and would work, but you're
then managing volumes and machine configs, which is more moving parts than a cron line.

So while you're on SQLite, a VPS is both the cheapest and the simplest option, and it isn't close.
PaaS only becomes attractive at stage 9, once you've moved to Postgres and the database lives
somewhere other than the filesystem — which is also roughly when the C# API needs hosting anyway.

### Refresh cadences

| Data | Cadence | Why |
|---|---|---|
| Twitch streams | **Hourly** | Live-only; unrecoverable. 24×14 = 336 samples/game in a fortnight |
| Twitch clips | Monthly-windowed backfill once, then **weekly** | Retrospective, so no urgency |
| Twitch VODs | Later (stage 7) | Third signal; noisier and slower to page |
| Steam games | **Weekly**, full re-sweep | Only ~330 requests. Tags drift, reviews accumulate, new games ship |
| Steam tag lookup | **Monthly**, plus auto-flag on unknown ids | New tags appear rarely |
| Twitch game matching | **Weekly**, after the Steam sweep | Picks up new releases and newly-created categories |

Re-sweeping Steam in full weekly rather than doing incremental cleverness is the right trade:
330 requests is nothing, and it keeps `review_count` and tag drift current for free. If you ever
want a cheap daily check for brand-new releases, add `&sort_by=Released_DESC` and stop after a
few pages.

### Etiquette and limits

Steam: single-threaded, 1.5 s between requests, identifying User-Agent, exponential backoff via
`tenacity` on 429/5xx, and archive raw responses so a parser bug never costs you a re-crawl.
Your steady-state load is a few hundred requests a week — invisible. Twitch: app tokens allow 800
points/min and your hourly poll costs on the order of 20 requests; you have enormous headroom.

---

## Verification

1. `uv run hitlist db init` then inspect: `sqlite3 data/hitlist.db ".tables"` shows all tables.
2. `uv run hitlist steam sync-tags --from-file ...` → `SELECT COUNT(*) FROM tag` returns **430**,
   and `SELECT name FROM tag WHERE id IN (1667, 1091588)` returns `Horror`,
   `Roguelike Deckbuilder` with no trailing whitespace.
3. `uv run hitlist steam sync-games --tag 1091588` (smallest tag, 1,644 games, ~17 requests) →
   `SELECT COUNT(*) FROM game` ≈ 1,644; every game has exactly 7 `GameTag` rows with `rank` 0–6;
   spot-check a game you know against its Steam page.
4. Re-run the same command → counts unchanged. Idempotency confirmed.
5. `pytest` — parse tests pass offline with the network disconnected.
6. `uv run hitlist twitch resolve-games` → prints match coverage; manually verify 10 links point
   at the right Twitch category.
7. `uv run hitlist twitch poll-streams` → `SELECT COUNT(*) FROM streamsnapshot` is non-zero;
   cross-check two rows against twitch.tv live right now. Run twice an hour apart and confirm two
   distinct `captured_at` values and a shared `stream_id` for a still-live stream.
8. After ~3 days of polling: `uv run hitlist export creators --tags 1667 --out horror.csv`, then
   open the CSV and sanity-check the top 20 against Twitch by hand. This is the real test — if
   the names look wrong to you, they'll look wrong to a dev.
