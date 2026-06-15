# Fork Changes

This fork (`litfinder`) tracks upstream [`calibrain/shelfmark`](https://github.com/calibrain/shelfmark).
Because the fork's git history was rewritten, commit-level provenance against upstream is
unreliable. This file is the source of truth for **what this fork changed and why**, so that
future upstream merges can be reconciled quickly.

> How to use this when pulling upstream later: for each entry below, check whether upstream has
> since changed the same files. If it has, prefer upstream's version and re-confirm the behavior
> described here still holds (the tests listed are the fastest way to confirm).

---

## 2026-06-14 — Ported three upstream changes + dependency refresh

These were merged in upstream after this fork was created (2026-05-29) and ported in manually.
Everything below already existed upstream; we did not invent new behavior, only re-applied it on
top of the fork's customized code.

### 1. IRC: require a search bot, never post bare queries, add per-query cooldown
Upstream PR: **#1065** ("Make IRC less spammy and require a bot name").

Why it matters: previously a search with no configured bot would post a bare book title straight
to the channel. That looks like spam and can get your IRC nick banned. Now a search bot is
required, every query is addressed (`@<bot> <query>`), and an identical query won't be re-posted
within a 24-hour cooldown (so repeated "Refresh" clicks fall back to cache instead of flooding the
channel).

Files:
- `shelfmark/release_sources/irc/source.py` — `is_available()` now requires a bot; in-search
  guard against bare queries; `_query_cooldown_key` / `_query_on_cooldown` / `_record_query_sent`
  helpers + `QUERY_COOLDOWN_SECONDS` / `_recent_query_times` state.
- `shelfmark/release_sources/irc/settings.py` — `IRC_SEARCH_BOT` marked `required=True` with an
  updated description.
- `docs/environment-variables.md` — `IRC_SEARCH_BOT` documented as required.

Tests: `tests/irc/test_source.py`
(`test_search_without_search_bot_never_posts_to_channel`,
`test_search_on_cooldown_returns_cache_without_reposting`, plus the updated no-DCC-offer test).

### 2. Combined search: `?content_type=combined` URL param + `FORCE_COMBINED_SEARCH` setting
Upstream PR: **#1058** ("Add `content_type=combined` URL parameter and `FORCE_COMBINED_SEARCH`").

Why it matters: lets a bookmarkable link force combined (ebook + audiobook) search, and adds a
per-user setting that locks combined mode on whenever it's available (shown by a padlock icon on
the combined toggle).

Backend files:
- `shelfmark/config/settings.py` — `FORCE_COMBINED_SEARCH` checkbox field.
- `shelfmark/config/users_settings.py` — added to the validatable search-preference keys and to the
  boolean-coercion validation branch.
- `shelfmark/main.py` — `force_combined_search` added to the `/api/config` response.

Frontend files:
- `src/frontend/src/types/index.ts` — `force_combined_search` on `AppConfig`.
- `src/frontend/src/utils/parseUrlSearchParams.ts` — parse `content_type=combined`.
- `src/frontend/src/hooks/useUrlSearch.ts` — treat a combined-only URL as a valid bootstrap.
- `src/frontend/src/components/UrlSearchBootstrapMount.tsx` — apply the combined URL override.
- `src/frontend/src/App.tsx` — derive `combinedModeLocked` / `effectiveCombinedMode`; thread props.
- `src/frontend/src/components/{Header,SearchSection,SearchBar}.tsx` — thread `combinedModeLocked`;
  SearchBar shows a lock icon when locked.

Docs:
- `docs/url-search-parameters.md` — documents `content_type=combined`.
- `docs/environment-variables.md` — documents `FORCE_COMBINED_SEARCH`.

Tests: `src/frontend/src/tests/parseUrlSearchParams.test.ts`,
`tests/core/test_admin_users_api.py` (search-preference key order).

### 3. Transmission: mark complete when seed ratio is 0
Upstream PR: **#1023**.

The completion check already accepted the `stopped` state in this fork's code; only the explanatory
comment was stale and was corrected. File: `shelfmark/download/clients/transmission.py`.

### 4. Dependency refresh
Brought locked dependencies up to date with upstream, including `seleniumbase==4.49.9` (which pins
`requests` 2.34.2, `beautifulsoup4` 4.15.0, `selenium` 4.44.0) and security-relevant bumps
(`cryptography` 49, `gunicorn` 26, `certifi`, `idna`). Files: `pyproject.toml`, `uv.lock`.

### Cleanup
Removed `tests/config/test_generate_env_docs.py`, an orphaned test importing the already-deleted
`scripts/generate_env_docs.py`.
