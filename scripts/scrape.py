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
import urllib.parse
import urllib.request

HANDLE = "thsottiaux"
ANNOUNCEMENT_ID = "2106845241357824205"  # Oct 5: "Over the next 28 days..."
TOTAL_DAYS = 28
SITE_URL = "https://genuifx.github.io/codex-28-days/"
SITE_SHARE_TEXT = "Tracking Tibo's 28-day Codex shipping sprint"

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


LEAF_PATH = ("M50 2 58 20 66 15 63 38 78 26 82 34 96 30 88 48 95 52 72 68 75 76 54 73 "
             "53 98 47 98 46 73 25 76 28 68 5 52 12 48 4 30 18 34 22 26 37 38 34 15 42 20Z")

CSS = """
:root{--paper:#faf8f3;--card:#fff;--ink:#2b1712;--mut:#6f564d;--line:#e7ddd0;--red:#d23b2e;--red-ink:#a92d1f;--red-soft:#fbe9e5;
--px:"Press Start 2P",ui-monospace,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
*{box-sizing:border-box}
html{background:var(--paper)}
body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.75 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--red-ink)}
a:focus-visible{outline:2px solid var(--red);outline-offset:3px}
.wrap{max-width:760px;margin:0 auto;padding:0 24px}
.px{font-family:var(--px);font-weight:400;letter-spacing:.5px;line-height:1.6}

/* HUD */
.hud{background:var(--card);border-bottom:1px solid var(--line)}
.hud .wrap{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding-top:14px;padding-bottom:14px}
.hud-title{font-size:10px;color:var(--ink);margin:0}
.hud-title b{color:var(--red);font-weight:400}
.hud-lv{font-size:10px;color:var(--mut)}
.hud-lv strong{color:var(--red);font-weight:400}

/* Hero */
.hero{position:relative;overflow:hidden;padding:72px 0 40px}
.hero-inner{position:relative;z-index:1}
.kicker{font-size:9px;color:var(--red-ink);margin:0 0 20px}
.hero h1{margin:0 0 20px;font-size:clamp(34px,7vw,52px);line-height:1.08;letter-spacing:-1.5px;font-weight:800}
.hero h1 span{color:var(--red)}
.lede{margin:0;max-width:560px;color:var(--mut);font-size:17px}
.lede a{text-decoration:none;border-bottom:1px solid currentColor}
.leaves{position:absolute;inset:0;pointer-events:none;z-index:0}
.leaf{position:absolute;top:-40px;fill:var(--red);opacity:0;animation:fall linear infinite}
.leaf.l1{left:68%;width:26px;animation-duration:14s}
.leaf.l2{left:84%;width:18px;fill:#e98b7d;animation-duration:17s;animation-delay:-6s}
.leaf.l3{left:92%;width:30px;animation-duration:20s;animation-delay:-11s}
.leaf.l4{left:76%;width:14px;fill:#e98b7d;animation-duration:12s;animation-delay:-3s}
@keyframes fall{
0%{transform:translate(0,0) rotate(0deg);opacity:0}
10%{opacity:.85}
50%{transform:translate(-30px,190px) rotate(160deg)}
85%{opacity:.6}
100%{transform:translate(10px,400px) rotate(330deg);opacity:0}}

/* XP bar */
.xp{margin-top:40px}
.xp-row{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.xp-label{font-size:9px;color:var(--ink)}
.xp-count{font-size:9px;color:var(--red-ink)}
.xp-bar{display:grid;grid-template-columns:repeat(28,1fr);gap:3px;padding:4px;background:var(--card);border:1px solid var(--line)}
.xp-bar i{display:block;height:14px;background:var(--paper);border:1px solid var(--line)}
.xp-bar i.on{background:var(--red);border-color:var(--red)}
.xp-bar i.cur{background:var(--red);border-color:var(--ink);animation:blink 1.6s steps(2,start) infinite}
@keyframes blink{50%{background:#f2a497}}
.prog{margin:10px 0 0;color:var(--mut);font-size:13px}

/* Quest log */
.log-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:56px 0 20px;padding-bottom:12px;border-bottom:1px solid var(--ink)}
.log-head h2{margin:0;font-size:11px;color:var(--ink)}
.log-head span{font-size:9px;color:var(--mut)}
.quest{position:relative;background:var(--card);border:1px solid var(--line);padding:24px 28px 18px;margin:0 0 24px}
.quest.is-new{border-color:var(--red)}
.quest-head{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:16px}
.badge{display:inline-block;font-size:9px;color:#fff;background:var(--red);padding:5px 8px 4px;margin:2px;
box-shadow:0 -2px 0 0 var(--red),0 2px 0 0 var(--red),-2px 0 0 0 var(--red),2px 0 0 0 var(--red)}
.quest-head time{color:var(--mut);font-size:13px}
.status{margin-left:auto;font-size:8px;color:var(--mut)}
.new-ship{position:absolute;top:-9px;right:20px;font-size:8px;color:var(--red-ink);background:var(--card);border:1px solid var(--red);padding:3px 7px 2px}
.text p{margin:0 0 14px;white-space:pre-wrap;overflow-wrap:anywhere}
.meta{display:flex;gap:18px;align-items:center;flex-wrap:wrap;color:var(--mut);font-size:13px;border-top:1px dashed var(--line);padding-top:14px;margin-top:6px}
.meta span{white-space:nowrap}
.orig{margin-left:auto;font-weight:600;text-decoration:none}
.orig:hover{text-decoration:underline}
.empty{color:var(--mut)}
.quest{scroll-margin-top:20px}
.quest:target,.quest.is-hit{border-color:var(--red);animation:hit 1.2s steps(4,end) 2}
@keyframes hit{0%,100%{box-shadow:0 0 0 0 var(--red-soft)}50%{box-shadow:0 0 0 6px var(--red-soft)}}

/* Share tags */
[hidden]{display:none!important}
.share{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:14px}
.share-label{font-size:8px;color:var(--mut);margin-right:2px}
.tag{display:inline-flex;align-items:center;font:400 8px/1.6 var(--px);letter-spacing:.5px;color:var(--red-ink);background:var(--card);
border:1px solid var(--red);padding:6px 9px 5px;text-decoration:none;cursor:pointer;-webkit-appearance:none;appearance:none;border-radius:0}
.tag:hover{background:var(--red);color:#fff}
.tag:focus-visible{outline:2px solid var(--red);outline-offset:2px}
.tag:disabled{cursor:default;background:var(--red);color:#fff}
.hud-share{font-size:8px;color:var(--red-ink);text-decoration:none;border:1px solid var(--red);padding:5px 8px 4px}
.hud-share:hover{background:var(--red);color:#fff}
.hud-right{display:flex;align-items:center;gap:14px}
.share-site{background:var(--card);border:1px solid var(--line);padding:20px 24px;margin:0 0 28px;scroll-margin-top:20px}
.share-site h2{margin:0 0 6px;font-size:10px;color:var(--ink)}
.share-site p{margin:0;color:var(--mut);font-size:14px}

/* Footer */
.site-foot{margin:56px 0 0;padding:24px 0 56px;border-top:1px solid var(--line);color:var(--mut);font-size:13px}
.site-foot p{margin:0}
.site-foot .px{font-size:8px;color:var(--red-ink);margin-bottom:10px}

@media (max-width:560px){
body{font-size:16px}
.wrap{padding:0 18px}
.hero{padding:52px 0 32px}
.quest{padding:20px 18px 16px}
.xp-bar{gap:2px;padding:3px}
.xp-bar i{height:12px}
.orig{margin-left:0;flex-basis:100%}
.share-site{padding:18px}
.tag{padding:8px 10px 7px}
.leaf.l1,.leaf.l4{display:none}
}
@media (prefers-reduced-motion:reduce){
.leaf{animation:none;opacity:.5}
.leaf.l1{top:40px}.leaf.l2{top:110px}.leaf.l3{top:18px}.leaf.l4{top:170px}
.xp-bar i.cur{animation:none}
.quest:target,.quest.is-hit{animation:none;box-shadow:0 0 0 4px var(--red-soft)}
}
"""


def fmt_date(s):
    """'Mon Oct 05 17:20:29 +0000 2026' -> (iso, 'Oct 05, 2026 · 17:20 UTC'); raw on failure."""
    try:
        dt = datetime.datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").astimezone(datetime.timezone.utc)
        return dt.isoformat(), dt.strftime("%b %d, %Y · %H:%M UTC")
    except (TypeError, ValueError):
        return "", s or ""


def day_url(day):
    return f"{SITE_URL}#day-{day}"


def tweet_intent(text, url):
    q = urllib.parse.urlencode({"text": text, "url": url}, quote_via=urllib.parse.quote)
    return f"https://twitter.com/intent/tweet?{q}"


def share_blurb(e, limit=80):
    """'Codex Day N: <first ~80 chars of the post>…' for the X intent."""
    body = re.sub(r"^\s*Day\s*\d{1,2}\s*/\s*", "", e["text"], flags=re.I)
    body = " ".join(body.split())
    if len(body) > limit:
        cut = body[:limit]
        body = (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(" ,.;:-") + "…"
    prefix = "Codex sprint kickoff" if e["day"] == 0 else f"Codex Day {e['day']}"
    return f"{prefix}: {body}"


def share_tags(text, url, title):
    """X intent link (works without JS) + copy / native-share buttons revealed by JS."""
    return (f'<a class="tag" href="{esc(tweet_intent(text, url))}" target="_blank" rel="noopener">SHARE ON X</a>'
            f'<button type="button" class="tag" data-copy="{esc(url)}" hidden>COPY LINK</button>'
            f'<button type="button" class="tag" data-share data-title="{esc(title)}" data-text="{esc(text)}" '
            f'data-url="{esc(url)}" hidden>SHARE…</button>')


JS = """(function(){
var d=document,n=navigator;
function each(s,f){Array.prototype.forEach.call(d.querySelectorAll(s),f)}
function flash(b,t){var o=b.textContent;b.textContent=t;b.disabled=true;setTimeout(function(){b.textContent=o;b.disabled=false},1600)}
if(n.clipboard&&window.isSecureContext){each('[data-copy]',function(b){b.hidden=false;b.addEventListener('click',function(){
n.clipboard.writeText(b.getAttribute('data-copy')).then(function(){flash(b,'COPIED!')},function(){flash(b,'COPY FAILED')})})})}
if(n.share){each('[data-share]',function(b){b.hidden=false;b.addEventListener('click',function(){
n.share({title:b.getAttribute('data-title'),text:b.getAttribute('data-text'),url:b.getAttribute('data-url')}).catch(function(){})})})}
var calm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function go(){var m=/^#day-(\\d+)$/.exec(location.hash);if(!m)return;
var el=d.getElementById('day-'+parseInt(m[1],10));if(!el)return;
each('.quest.is-hit',function(x){x.classList.remove('is-hit')});void el.offsetWidth;el.classList.add('is-hit');
el.scrollIntoView({behavior:calm?'auto':'smooth',block:'start'})}
addEventListener('hashchange',go);addEventListener('load',go);go();
})();"""


def render(log):
    entries = sorted(log["entries"], key=lambda e: e["day"])
    latest_day = max([e["day"] for e in entries if e["day"] > 0], default=0)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    leaf_svg = (f'<svg class="leaf {{cls}}" viewBox="0 0 100 100" aria-hidden="true" focusable="false">'
                f'<path d="{LEAF_PATH}"/></svg>')
    favicon = ("data:image/svg+xml," + f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
               f"<path fill='%23d23b2e' d='{LEAF_PATH}'/></svg>").replace(" ", "%20")

    cards = []
    for e in sorted(entries, key=lambda e: e["day"], reverse=True):
        is_new = e["day"] > 0 and e["day"] == latest_day
        label = "ANNOUNCEMENT" if e["day"] == 0 else f"DAY {e['day']:02d}"
        status = "QUEST START" if e["day"] == 0 else "CLEARED"
        iso, pretty = fmt_date(e.get("posted_at", ""))
        time_attr = f' datetime="{esc(iso)}"' if iso else ""
        paras = "".join(f"<p>{esc(p)}</p>" for p in e["text"].split("\n") if p.strip())
        cards.append(f"""<article class="quest{' is-new' if is_new else ''}" id="day-{e['day']}">
  {'<span class="new-ship px">NEW SHIP</span>' if is_new else ''}
  <div class="quest-head"><span class="badge px">{esc(label)}</span>
  <time{time_attr}>{esc(pretty)}</time><span class="status px">{status}</span></div>
  <div class="text">{paras}</div>
  <div class="meta"><span title="Likes">♥ {fmt_int(e.get('likes'))}</span><span title="Reposts">↻ {fmt_int(e.get('reposts'))}</span><span title="Replies">💬 {fmt_int(e.get('replies'))}</span><span title="Views">👁 {fmt_int(e.get('views'))}</span>
  <a class="orig" href="{esc(e['url'])}" target="_blank" rel="noopener">View on X →</a></div>
  <div class="share"><span class="share-label px">SHARE</span>{share_tags(share_blurb(e), day_url(e['day']), share_blurb(e).split(":")[0] + " — 28 Days of Shipping")}</div>
</article>""")
    cards_html = "\n".join(cards) if cards else '<p class="empty">No entries yet — check back soon.</p>'
    segs = "".join(
        '<i class="cur"></i>' if d == latest_day else ('<i class="on"></i>' if d < latest_day else "<i></i>")
        for d in range(1, TOTAL_DAYS + 1)
    )
    leaves = "".join(leaf_svg.format(cls=c) for c in ("l1", "l2", "l3", "l4"))
    n_entries = len(entries)

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
<meta property="og:url" content="{SITE_URL}">
<meta property="og:site_name" content="Codex: 28 Days of Shipping">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Codex: 28 Days of Shipping">
<meta name="twitter:description" content="Every daily Codex ship from Tibo's 28-day sprint, tracked day by day.">
<link rel="canonical" href="{SITE_URL}">
<meta name="theme-color" content="#faf8f3">
<link rel="icon" href="{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap">
<style>{CSS}</style>
</head>
<body>
<header class="hud">
<div class="wrap">
<p class="hud-title px">CODEX <b>//</b> 28-DAY SPRINT</p>
<div class="hud-right"><a class="hud-share px" href="#share">SHARE</a>
<span class="hud-lv px">LV.<strong>{latest_day:02d}</strong> / {TOTAL_DAYS}</span></div>
</div>
</header>
<main class="wrap">
<section class="hero">
<div class="leaves" aria-hidden="true">{leaves}</div>
<div class="hero-inner">
<p class="kicker px">SEASON 01 · AUTUMN 2026</p>
<h1>Codex: 28 Days<br>of <span>Shipping</span></h1>
<p class="lede">Unofficial daily tracker of <a href="https://x.com/{HANDLE}" target="_blank" rel="noopener">Tibo (@{HANDLE})</a>'s
28-day Codex improvement sprint (Oct 5 – Nov 1, 2026). One entry per ship, newest first.</p>
<div class="xp">
<div class="xp-row"><span class="xp-label px">XP</span><span class="xp-count px">{latest_day:02d} / {TOTAL_DAYS} SHIPPED</span></div>
<div class="xp-bar" role="progressbar" aria-label="Sprint progress" aria-valuemin="0" aria-valuemax="{TOTAL_DAYS}" aria-valuenow="{latest_day}">{segs}</div>
<p class="prog">Day {latest_day} of {TOTAL_DAYS} tracked · updated {esc(now)}</p>
</div>
</div>
</section>
<section aria-labelledby="log-title">
<div class="log-head"><h2 id="log-title" class="px">QUEST LOG</h2><span class="px">{n_entries} {'ENTRY' if n_entries == 1 else 'ENTRIES'}</span></div>
{cards_html}
</section>
<section class="share-site" id="share" aria-labelledby="share-title">
<h2 id="share-title" class="px">INVITE A PLAYER</h2>
<p>Know someone who lives in Codex? Send them the tracker.</p>
<div class="share">{share_tags(SITE_SHARE_TEXT, SITE_URL, "Codex: 28 Days of Shipping")}</div>
</section>
<footer class="site-foot">
<p class="px">GAME SAVED</p>
<p>Unofficial fan tracker. All posts belong to <a href="https://x.com/{HANDLE}" target="_blank" rel="noopener">@{HANDLE}</a> on X.
Source: public posts, refreshed twice daily. Not affiliated with OpenAI. ·
<a href="data/days.json">raw JSON</a> · <a href="https://github.com/Genuifx/codex-28-days">GitHub</a></p>
</footer>
</main>
<script>{JS}</script>
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
