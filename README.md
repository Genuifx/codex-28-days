# Codex: 28 Days of Shipping

Unofficial daily tracker of Tibo ([@thsottiaux](https://x.com/thsottiaux), OpenAI Codex lead)'s 28-day Codex improvement sprint (Oct 5 – Nov 1, 2026). One card per ship, newest first.

**Live site:** https://codexy.fyi/

## How it works (total cost: $0)

| Piece | Choice | Cost |
|---|---|---|
| Hosting | GitHub Pages (public repo) | $0 |
| Daily scrape | GitHub Actions, 2×/day (~1 min each) | $0 (free tier: 2000 min/mo) |
| Timeline discovery | twiscan.com public profile mirror (no key) | $0 |
| Tweet text + engagement | api.fxtwitter.com per-status API (no key) | $0 |
| Domain | username.github.io subdomain | $0 |

Pipeline: `scripts/scrape.py` discovers new `Day N/` tweets from the public timeline mirror, fetches canonical text/engagement via the fxtwitter API, appends to `data/days.json`, and re-renders the fully static `index.html` (no JS needed to read; good for SEO). The scheduled workflow commits only when something changed; GitHub Pages rebuilds on push.

Fail-soft by design: if a source is unreachable the script keeps existing data and exits 0 — the site never gets wiped by a bad scrape.

## Run locally

```bash
python3 scripts/scrape.py   # updates data/days.json + index.html
```

## Reuse as a template

Fork this repo to track any other account's daily series: change `HANDLE`, `ANNOUNCEMENT_ID`, the `day_number()` pattern, and the copy in `render()`. Same $0 stack.
