# Codex: 28 Days of Shipping

Unofficial daily tracker of Tibo ([@thsottiaux](https://x.com/thsottiaux), OpenAI Codex lead)'s 28-day Codex improvement sprint (Oct 5 – Nov 1, 2026). One card per ship, newest first.

**Live site:** https://codexy.fyi/

## How it works (total cost: $0)

| Piece | Choice | Cost |
|---|---|---|
| Hosting | GitHub Pages (public repo) | $0 |
| Daily scrape | GitHub Actions, 2×/day (~1 min each) | $0 (free tier: 2000 min/mo) |
| Timeline discovery | twiscan.com + site.twstalker.com public profiles (no key) | $0 |
| Tweet text + engagement | api.fxtwitter.com per-status API (no key) | $0 |
| Domain | username.github.io subdomain | $0 |

Pipeline: `scripts/scrape.py` unions status IDs from two independent public timeline mirrors, then verifies each exact ID, author, full text and timestamp via the fxtwitter API. Only the author's own line-start `Day N/` text creates a day entry. Direct author replies to an archived Day post are stored in that entry's `followups` array, with exact reply/quote relationships and English/Chinese text; they do not increase the day count. Standalone announcements and replies to other threads are not assigned an invented day. The script re-renders the static `index.html` and `llms.txt`; GitHub Pages rebuilds on push.

Fail-soft by design: unavailable, empty, or archive-lagging discovery sources emit visible workflow warnings. Existing data is preserved and another source can continue. Mirrors can still lag or omit posts, so a successful run is not a guarantee of complete X coverage. Mirror previews are never used to classify posts, because a preview can belong to a neighboring card.

## Run locally

```bash
python3 scripts/scrape.py   # updates data/days.json + index.html
python3 -B -m unittest discover -v  # isolated regression suite (no network)
```

## Reuse as a template

Fork this repo to track any other account's daily series: change `HANDLE`, `ANNOUNCEMENT_ID`, the `day_number()` pattern, and the copy in `render()`. Same $0 stack.

