#!/usr/bin/env python3
"""Tibo's Codex 28-day ship tracker — daily scraper.

Sources (all free, no keys):
  1. twiscan.com profile page  -> discovers new tweet ids (+ relative time)
  2. api.fxtwitter.com /status  -> canonical full text, timestamp, engagement

Output:
  data/days.json  (append-only log of Day N entries)
  index.html        (static page rendered from the log; no JS needed to read)

Fail-soft: if the timeline source is unreachable, existing data is kept and the
script exits 0 so the scheduled run never wipes the site.
"""
import datetime
import html as htmlmod
import json
import os
import re
import sys
import urllib.request

HANDLE = "thsottiaux"
ANNOUNCEMENT_ID = "2106845241357824205"  # Oct 5: "Over the next 28 days..."
TOTAL_DAYS = 28

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "days.json")
INDEX_PATH = os.path.join(ROOT, "index.html")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse_twiscan(page_html):
    """Extract (tweet_id, relative_time, preview_text) from the profile page."""
    tweets, seen = [], set()
    for m in re.finditer(
        r'href="https://twiscan\.com/en/x/thsottiaux/(\d{10,})">([^<]+)</a>', page_html
    ):
        tid, rel = m.group(1), m.group(2).strip()
        if tid in seen:
            continue
        seen.add(tid)
        tail = page_html[m.end() : m.end() + 8000]
        tm = re.search(r'id="clamp-%s-0">\s*(.*?)\s*</div>' % tid, tail, re.S)
        text = ""
        if tm:
            text = htmlmod.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        tweets.append({"id": tid, "relative": rel, "preview": text})
    return tweets


def rel_to_dt(rel, now):
    m = re.match(r"(\d+)\s*(second|minute|hour|day|week|month|year)", rel, re.I)
    if not m:
        return now
    n, unit = int(m.group(1)), m.group(2).lower()
    secs = {
        "second": 1, "minute": 60, "hour": 3600, "day": 86400,
        "week": 604800, "month": 2592000, "year": 31536000,
    }[unit]
    return now - datetime.timedelta(seconds=n * secs)


def fx_status(tid):
    """Canonical tweet data from the fxtwitter API."""
    d = json.loads(fetch(f"https://api.fxtwitter.com/{HANDLE}/status/{tid}"))
    t = d.get("tweet") or {}
    return {
        "id": str(t.get("id") or tid),
        "text": (t.get("text") or "").strip(),
        "posted_at": t.get("created_at") or "",
        "url": t.get("url") or f"https://x.com/{HANDLE}/status/{tid}",
        "likes": t.get("likes") or 0,
        "reposts": t.get("retweets") or 0,
        "replies": t.get("replies") or 0,
        "views": t.get("views") or 0,
    }


def day_number(text):
    m = re.match(r"\s*Day\s*(\d{1,2})\s*/", text, re.I)
    return int(m.group(1)) if m else None


def load_log():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"handle": HANDLE, "total_days": TOTAL_DAYS,
            "announcement_id": ANNOUNCEMENT_ID, "entries": []}


def save_log(log):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fmt_int(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "–"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def esc(s):
    return htmlmod.escape(s or "")


def render(log):
    entries = sorted(log["entries"], key=lambda e: e["day"])
    latest_day = max([e["day"] for e in entries if e["day"] > 0], default=0)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    cards = []
    for e in sorted(entries, key=lambda e: e["day"], reverse=True):
        label = "Announcement" if e["day"] == 0 else f"Day {e['day']}"
        paras = "".join(f"<p>{esc(p)}</p>" for p in e["text"].split("\n") if p.strip())
        cards.append(f"""<article class="card">
  <div class="card-head"><span class="day-badge">{esc(label)}</span>
  <span class="date">{esc(e.get('posted_at', ''))}</span></div>
  <div class="text">{paras}</div>
  <div class="meta"><span>♥ {fmt_int(e.get('likes'))}</span><span>↻ {fmt_int(e.get('reposts'))}</span><span>💬 {fmt_int(e.get('replies'))}</span><span>👁 {fmt_int(e.get('views'))}</span>
  <a class="orig" href="{esc(e['url'])}" target="_blank" rel="noopener">View on X →</a></div>
</article>""")
    cards_html = "\n".join(cards) if cards else "<p>No entries yet — check back soon.</p>"
    pct = round(latest_day / TOTAL_DAYS * 100)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex: 28 Days of Shipping — tracking @{HANDLE}</title>
<meta name="description" content="Unofficial daily tracker of Tibo (@{HANDLE}, OpenAI Codex lead)'s 28-day shipping sprint: every Codex improvement, day by day, Oct 5 – Nov 1 2026.">
<meta property="og:title" content="Codex: 28 Days of Shipping">
<meta property="og:description" content="Every daily Codex ship from Tibo's 28-day sprint, tracked day by day.">
<meta property="og:type" content="website">
<style>
:root{{--bg:#0b0e14;--card:#141a26;--ink:#e8ecf4;--mut:#8b94a7;--acc:#4da3ff;--line:#232c40}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:720px;margin:0 auto;padding:32px 20px 64px}}
.hero{{border:1px solid var(--line);border-radius:16px;padding:28px;background:linear-gradient(180deg,#131a2a,#0e1420);margin-bottom:8px}}
.hero h1{{margin:0 0 8px;font-size:28px;letter-spacing:-.5px}}
.hero p{{margin:6px 0;color:var(--mut)}}
.hero a{{color:var(--acc);text-decoration:none}}
.bar{{height:10px;background:#1c2436;border-radius:99px;margin:18px 0 6px;overflow:hidden}}
.bar i{{display:block;height:100%;width:{pct}%;background:linear-gradient(90deg,#2f7de1,#4da3ff);border-radius:99px}}
.prog{{font-size:13px;color:var(--mut)}}
.card{{border:1px solid var(--line);border-radius:14px;background:var(--card);padding:20px 22px;margin:18px 0}}
.card-head{{display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap}}
.day-badge{{background:#1d2b45;color:var(--acc);font-weight:700;font-size:13px;padding:4px 12px;border-radius:99px;letter-spacing:.3px}}
.date{{color:var(--mut);font-size:13px}}
.text p{{margin:0 0 12px;white-space:pre-wrap}}
.meta{{display:flex;gap:16px;align-items:center;color:var(--mut);font-size:13px;border-top:1px solid var(--line);padding-top:12px;flex-wrap:wrap}}
.orig{{margin-left:auto;color:var(--acc);text-decoration:none;font-weight:600}}
footer{{margin-top:40px;color:var(--mut);font-size:13px;border-top:1px solid var(--line);padding-top:16px}}
footer a{{color:var(--acc);text-decoration:none}}
</style>
</head>
<body>
<div class="wrap">
<div class="hero">
<h1>Codex: 28 Days of Shipping 🚢</h1>
<p>Unofficial daily tracker of <a href="https://x.com/{HANDLE}" target="_blank" rel="noopener">Tibo (@{HANDLE})</a>'s
28-day Codex improvement sprint (Oct 5 – Nov 1, 2026). One card per ship, newest first.</p>
<div class="bar"><i></i></div>
<div class="prog">Day {latest_day} of {TOTAL_DAYS} tracked · updated {esc(now)}</div>
</div>
{cards_html}
<footer>
<p>Unofficial fan tracker. All posts belong to <a href="https://x.com/{HANDLE}" target="_blank" rel="noopener">@{HANDLE}</a> on X.
Source: public posts, refreshed twice daily. Not affiliated with OpenAI. ·
<a href="data/days.json">raw JSON</a> · <a href="https://github.com/Genuifx/codex-28-days">GitHub</a></p>
</footer>
</div>
</body>
</html>
"""


def main():
    log = load_log()
    known_ids = {e["id"] for e in log["entries"]}
    now = datetime.datetime.now(datetime.timezone.utc)

    # Seed the announcement once.
    if ANNOUNCEMENT_ID not in known_ids:
        try:
            t = fx_status(ANNOUNCEMENT_ID)
            t["day"] = 0
            log["entries"].append(t)
            known_ids.add(ANNOUNCEMENT_ID)
            print(f"seeded announcement {ANNOUNCEMENT_ID}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"announcement fetch failed: {e}", file=sys.stderr, flush=True)

    # Discover new Day N tweets from the public timeline mirror.
    try:
        page = fetch(f"https://twiscan.com/en/x/{HANDLE}")
    except Exception as e:  # noqa: BLE001
        print(f"timeline unreachable, keeping existing data: {e}", file=sys.stderr, flush=True)
        page = ""

    added = 0
    if page:
        for tw in parse_twiscan(page):
            if tw["id"] in known_ids:
                continue
            n = day_number(tw["preview"]) or day_number(tw["preview"].lstrip())
            if n is None or not (1 <= n <= TOTAL_DAYS):
                continue
            try:
                t = fx_status(tw["id"])
            except Exception as e:  # noqa: BLE001
                print(f"status fetch failed for {tw['id']}: {e}", file=sys.stderr, flush=True)
                continue
            if not t["text"]:
                t["text"] = tw["preview"]
            if not t["posted_at"]:
                t["posted_at"] = rel_to_dt(tw["relative"], now).strftime("%a %b %d %H:%M:%S %z %Y")
            t["day"] = day_number(t["text"]) or n
            log["entries"].append(t)
            known_ids.add(tw["id"])
            added += 1
            print(f"added Day {t['day']}: {tw['id']}", flush=True)

    save_log(log)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(render(log))
    print(f"done: {added} new, {len(log['entries'])} total entries", flush=True)


if __name__ == "__main__":
    main()
