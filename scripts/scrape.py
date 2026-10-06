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
SITE_URL = "https://codexy.fyi"  # custom domain (CNAME); no trailing slash
SITE_SHARE_TEXT = "Tracking Tibo's 28-day Codex shipping sprint"
CF_BEACON_TOKEN = "ce3e870636f3415c8020c3187dfd9319"  # Cloudflare Web Analytics

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


DAY_RE = re.compile(r"\s*Day\s*(\d{1,2})(\.\d+)?\s*/", re.I)


def day_number(text):
    """Int day of a 'Day N/' (or 'Day N.M/') post, e.g. 2 for 'Day 2.1/'."""
    m = DAY_RE.match(text or "")
    return int(m.group(1)) if m else None


def day_sub(text):
    """Sub-day suffix, e.g. '.1' for 'Day 2.1/', '' otherwise."""
    m = DAY_RE.match(text or "")
    return m.group(2) or "" if m else ""


def day_slug(e):
    """Human-readable day key for ids, urls and labels: '2' or '2.1'."""
    return f"{e['day']}{e.get('sub') or ''}"


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
--px:"Press Start 2P",ui-monospace,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--fs-body:clamp(16px,15.2px + .25vw,17px);--fs-small:clamp(13px,12.6px + .12vw,14px);
--px-xs:clamp(9px,8.6px + .12vw,10px);--px-s:clamp(9px,8.4px + .25vw,10px);--px-m:clamp(10px,9.4px + .2vw,11px);
--gut:clamp(18px,5vw,24px)}
*{box-sizing:border-box}
html{background:var(--paper);-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:var(--fs-body)/1.75 var(--sans);-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:var(--red-ink)}
a:focus-visible{outline:2px solid var(--red);outline-offset:3px}
.wrap{max-width:760px;margin:0 auto;padding:0 max(var(--gut),env(safe-area-inset-right)) 0 max(var(--gut),env(safe-area-inset-left))}
.px{font-family:var(--px);font-weight:400;letter-spacing:.5px;line-height:1.6}

/* HUD */
.hud{background:var(--card);border-bottom:1px solid var(--line)}
.hud .wrap{display:flex;justify-content:space-between;align-items:center;gap:8px 12px;flex-wrap:wrap;padding-top:12px;padding-bottom:12px}
.hud-title{font-size:var(--px-m);color:var(--ink);margin:0;white-space:nowrap}
.hud-title b{color:var(--red);font-weight:400}
.hud-lv{font-size:var(--px-m);color:var(--mut);white-space:nowrap}
.hud-lv strong{color:var(--red);font-weight:400}

/* Hero */
.hero{position:relative;padding:clamp(48px,10vw,72px) 0 clamp(28px,6vw,40px)}
.hero-inner{position:relative;z-index:1}
.kicker{font-size:var(--px-s);color:var(--red-ink);margin:0 0 20px}
.hero h1{margin:0 0 20px;font-size:clamp(32px,8.4vw,52px);line-height:1.08;letter-spacing:-.03em;font-weight:800}
.hero h1 span{color:var(--red)}
.lede{margin:0;max-width:560px;color:var(--mut);font-size:var(--fs-body)}
.lede a{text-decoration:none;border-bottom:1px solid currentColor}
.leaves{position:absolute;inset:0;overflow:hidden;pointer-events:none;z-index:0}
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
@keyframes fall-m{
0%{transform:translate(0,0) rotate(0deg);opacity:0}
10%{opacity:.6}
50%{transform:translate(-4px,220px) rotate(160deg)}
85%{opacity:.45}
100%{transform:translate(2px,440px) rotate(330deg);opacity:0}}

/* XP bar */
.xp{margin-top:clamp(28px,7vw,40px)}
.xp-row{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.xp-label{font-size:var(--px-s);color:var(--ink)}
.xp-count{font-size:var(--px-s);color:var(--red-ink)}
.xp-bar{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:3px;padding:4px;background:var(--card);border:1px solid var(--line)}
.xp-bar i{display:block;height:14px;background:var(--paper);border:1px solid var(--line)}
.xp-bar i.on{background:var(--red);border-color:var(--red)}
.xp-bar i.cur{background:var(--red);border-color:var(--ink);animation:blink 1.6s steps(2,start) infinite}
@keyframes blink{50%{background:#f2a497}}
.prog{margin:10px 0 0;color:var(--mut);font-size:var(--fs-small)}

/* Quest log */
.log-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin:clamp(40px,9vw,56px) 0 20px;padding-bottom:12px;border-bottom:1px solid var(--ink)}
.log-head h2{margin:0;font-size:var(--px-m);color:var(--ink)}
.log-head span{font-size:var(--px-s);color:var(--mut)}
.quest{position:relative;background:var(--card);border:1px solid var(--line);padding:clamp(20px,5vw,24px) clamp(18px,5vw,28px) clamp(16px,4vw,18px);margin:0 0 24px;scroll-margin-top:20px}
.quest.is-new{border-color:var(--red)}
.quest-head{display:flex;align-items:center;gap:10px 14px;flex-wrap:wrap;margin-bottom:16px}
.badge{display:inline-block;font-size:var(--px-s);color:#fff;background:var(--red);padding:5px 8px 4px;margin:2px;
box-shadow:0 -2px 0 0 var(--red),0 2px 0 0 var(--red),-2px 0 0 0 var(--red),2px 0 0 0 var(--red)}
.quest-head time{color:var(--mut);font-size:var(--fs-small)}
.status{margin-left:auto;font-size:var(--px-xs);color:var(--mut)}
.new-ship{position:absolute;top:-10px;right:clamp(14px,4vw,20px);font-size:var(--px-xs);color:var(--red-ink);background:var(--card);border:1px solid var(--red);padding:3px 7px 2px}
.text p{margin:0 0 14px;white-space:pre-wrap;overflow-wrap:anywhere}
.meta{display:flex;gap:8px 18px;align-items:center;flex-wrap:wrap;color:var(--mut);font-size:var(--fs-small);border-top:1px dashed var(--line);padding-top:14px;margin-top:6px}
.meta span{white-space:nowrap}
.orig{margin-left:auto;font-weight:600;text-decoration:none}
.orig:hover{text-decoration:underline}
.empty{color:var(--mut)}
.quest:target,.quest.is-hit{border-color:var(--red);animation:hit 1.2s steps(4,end) 2}
@keyframes hit{0%,100%{box-shadow:0 0 0 0 var(--red-soft)}50%{box-shadow:0 0 0 6px var(--red-soft)}}

/* Share tags */
[hidden]{display:none!important}
.share{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:14px}
.share-label{font-size:var(--px-xs);color:var(--mut);margin-right:2px}
.tag{display:inline-flex;align-items:center;justify-content:center;min-height:32px;font:400 var(--px-xs)/1.6 var(--px);letter-spacing:.5px;color:var(--red-ink);background:var(--card);
border:1px solid var(--red);padding:6px 10px 5px;text-decoration:none;text-align:center;cursor:pointer;-webkit-appearance:none;appearance:none;border-radius:0;
-webkit-tap-highlight-color:transparent;touch-action:manipulation}
.tag:hover{background:var(--red);color:#fff}
.tag:focus-visible{outline:2px solid var(--red);outline-offset:2px}
.tag:disabled{cursor:default;background:var(--red);color:#fff}
.tag.is-main{background:var(--red);color:#fff;box-shadow:3px 3px 0 var(--ink)}
.tag.is-main:hover{background:var(--red-ink)}
.tag.is-main:disabled{background:var(--line);color:var(--mut);box-shadow:none}
.hud-share{display:inline-flex;align-items:center;font-size:var(--px-xs);color:var(--red-ink);text-decoration:none;border:1px solid var(--red);padding:5px 8px 4px}
.hud-share:hover{background:var(--red);color:#fff}
.hud-right{display:flex;align-items:center;gap:14px}
.share-site{background:var(--card);border:1px solid var(--line);padding:clamp(18px,5vw,24px);margin:0 0 28px;scroll-margin-top:20px}
.share-site h2{margin:0 0 6px;font-size:var(--px-m);color:var(--ink)}
.share-site p{margin:0;color:var(--mut);font-size:var(--fs-small)}

/* Poster preview */
html.pm-open,html.pm-open body{overflow:hidden}
.pm{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(43,23,18,.78)}
.pm-box{display:flex;flex-direction:column;gap:14px;width:min(560px,100%);max-height:100%;overflow:auto;background:var(--paper);border:1px solid var(--ink);padding:18px;box-shadow:6px 6px 0 var(--red)}
.pm-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.pm-title{margin:0;font-size:var(--px-s);color:var(--ink)}
.pm-stage{display:flex;align-items:center;justify-content:center;min-height:220px;background:var(--card);border:1px solid var(--line);padding:8px}
.pm-stage img{display:block;width:auto;height:auto;max-width:100%;max-height:calc(100vh - 290px);max-height:calc(100dvh - 290px);-webkit-touch-callout:default;-webkit-user-select:auto;user-select:auto}
.pm-wait{margin:0;font-size:var(--px-s);color:var(--mut);animation:blink-t 1s steps(2,start) infinite}
@keyframes blink-t{50%{opacity:.35}}
.pm-hint{margin:0;color:var(--mut);font-size:var(--fs-small);text-align:center}
.pm-hint strong{color:var(--ink)}
.pm-act{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
.pm-act .tag{min-height:44px;padding:10px 16px 9px}

/* Footer */
.site-foot{margin:clamp(40px,9vw,56px) 0 0;padding:24px 0 max(56px,env(safe-area-inset-bottom));border-top:1px solid var(--line);color:var(--mut);font-size:var(--fs-small)}
.site-foot p{margin:0}
.site-foot .px{font-size:var(--px-xs);color:var(--red-ink);margin-bottom:10px}

@media (max-width:560px){
.hud .wrap{padding-top:10px;padding-bottom:6px}
.hud-right{width:100%;justify-content:space-between}
.hud-lv{order:-1}
.hud-share{min-height:44px;padding:0 14px}
.xp-bar{grid-template-columns:repeat(var(--half),1fr);gap:3px;padding:3px}
.xp-bar i{height:16px}
.quest-head .status{margin-left:0}
.orig{margin-left:0;flex-basis:100%;display:inline-flex;align-items:center;min-height:44px}
.share{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.share-label{grid-column:1/-1;margin:0}
.share .tag{min-height:44px;padding:8px 6px 7px}
.leaves{left:auto;right:calc(-1 * var(--gut));width:var(--gut)}
.leaf{animation-name:fall-m}
.leaf.l1,.leaf.l4{display:none}
.leaf.l2{left:2px;width:12px}
.leaf.l3{left:4px;width:13px}
.pm{padding:0;align-items:stretch}
.pm-box{width:100%;max-height:none;border:0;box-shadow:none;gap:12px;
padding:max(12px,env(safe-area-inset-top)) 14px max(14px,env(safe-area-inset-bottom))}
.pm-head .tag{min-height:44px;padding:0 14px}
.pm-stage{flex:1 1 auto;min-height:0}
.pm-stage img{max-height:calc(100vh - 250px);max-height:calc(100dvh - 250px)}
.pm-act{display:grid;grid-template-columns:1fr;gap:10px}
.pm-act .tag{min-height:52px;font-size:11px}
}
@media (orientation:landscape) and (max-height:540px){
.pm{padding:0;align-items:stretch}
.pm-box{width:100%;max-height:none;border:0;box-shadow:none;display:grid;gap:12px 16px;
grid-template-columns:auto minmax(200px,1fr);grid-template-rows:auto 1fr auto;grid-template-areas:"stage head" "stage hint" "stage act";
padding:12px max(16px,env(safe-area-inset-right)) 12px max(16px,env(safe-area-inset-left))}
.pm-head{grid-area:head}.pm-stage{grid-area:stage;min-height:0}.pm-hint{grid-area:hint;align-self:center}.pm-act{grid-area:act;display:grid;grid-template-columns:1fr}
.pm-stage img{max-height:calc(100vh - 42px);max-height:calc(100dvh - 42px)}
}
@media (prefers-reduced-motion:reduce){
.leaf{animation:none;opacity:.5}
.leaf.l1{top:40px}.leaf.l2{top:110px}.leaf.l3{top:18px}.leaf.l4{top:170px}
.xp-bar i.cur,.pm-wait{animation:none}
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
    return f"{SITE_URL}/#day-{day}"


def tweet_intent(text, url):
    q = urllib.parse.urlencode({"text": text, "url": url}, quote_via=urllib.parse.quote)
    return f"https://twitter.com/intent/tweet?{q}"


def strip_day_prefix(text):
    return re.sub(r"^\s*Day\s*\d{1,2}(?:\.\d+)?\s*/\s*", "", text or "", flags=re.I)


def share_blurb(e, limit=80):
    """'Codex Day N: <first ~80 chars of the post>…' for the X intent."""
    body = " ".join(strip_day_prefix(e["text"]).split())
    if len(body) > limit:
        cut = body[:limit]
        body = (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(" ,.;:-") + "…"
    prefix = "Codex sprint kickoff" if e["day"] == 0 else f"Codex Day {day_slug(e)}"
    return f"{prefix}: {body}"


def share_tags(text, url, title, poster, poster_label="POSTER"):
    """X intent link (works without JS) + copy / native-share / poster buttons revealed by JS."""
    return (f'<a class="tag" href="{esc(tweet_intent(text, url))}" target="_blank" rel="noopener">SHARE ON X</a>'
            f'<button type="button" class="tag" data-copy="{esc(url)}" hidden>COPY LINK</button>'
            f'<button type="button" class="tag" data-share data-title="{esc(title)}" data-text="{esc(text)}" '
            f'data-url="{esc(url)}" hidden>SHARE…</button>'
            f'<button type="button" class="tag" data-poster="{esc(poster)}" hidden>{esc(poster_label)}</button>')


def poster_data(entries, latest_day):
    """Everything the canvas poster renderer needs, embedded as JSON (no fetch)."""
    items = []
    for e in entries:
        items.append({
            "day": e["day"],
            "label": "KICKOFF" if e["day"] == 0 else f"DAY {day_slug(e).zfill(2)}",
            "status": "QUEST START" if e["day"] == 0 else "CLEARED",
            "date": fmt_date(e.get("posted_at", ""))[1],
            "body": strip_day_prefix(e["text"]).strip(),
            "stats": [fmt_int(e.get(k)) for k in ("likes", "reposts", "replies", "views")],
            "url": day_url(day_slug(e)),
        })
    data = {"total": TOTAL_DAYS, "latest": latest_day, "site": f"{SITE_URL}/", "handle": HANDLE,
            "leaf": LEAF_PATH, "entries": items}
    # Safe inside <script type="application/json">: no "</" can close the tag early.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


JS = """(function(){
var d=document,n=navigator;
function each(s,f){Array.prototype.forEach.call(d.querySelectorAll(s),f)}
function flash(b,t){var o=b.textContent;b.textContent=t;b.disabled=true;setTimeout(function(){b.textContent=o;b.disabled=false},1600)}
if(n.clipboard&&window.isSecureContext){each('[data-copy]',function(b){b.hidden=false;b.addEventListener('click',function(){
n.clipboard.writeText(b.getAttribute('data-copy')).then(function(){flash(b,'COPIED!')},function(){flash(b,'COPY FAILED')})})})}
if(n.share){each('[data-share]',function(b){b.hidden=false;b.addEventListener('click',function(){
n.share({title:b.getAttribute('data-title'),text:b.getAttribute('data-text'),url:b.getAttribute('data-url')}).catch(function(){})})})}
var calm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function go(){var m=/^#day-([\\d.]+)$/.exec(location.hash);if(!m)return;
var el=d.getElementById('day-'+m[1].replace(/^0+(\\d)/,'$1'));if(!el)return;
each('.quest.is-hit',function(x){x.classList.remove('is-hit')});void el.offsetWidth;el.classList.add('is-hit');
el.scrollIntoView({behavior:calm?'auto':'smooth',block:'start'})}
addEventListener('hashchange',go);addEventListener('load',go);go();
})();"""


# Canvas share posters (day + site). Pixel font and QR lib are optional; both degrade.
POSTER_JS = r"""(function(){
var d=document,w=window,n=navigator;
var src=d.getElementById('poster-data'),probe=d.createElement('canvas');
if(!src||!w.Promise||!probe.getContext||!probe.getContext('2d')||!probe.toDataURL)return;
var D;try{D=JSON.parse(src.textContent)}catch(e){return}
var W=1080,H=1350,X0=108,X1=972,CW=X1-X0;
var C={paper:'#faf8f3',card:'#fff',ink:'#2b1712',mut:'#6f564d',line:'#e7ddd0',red:'#d23b2e',redInk:'#a92d1f',soft:'#fbe9e5',pink:'#e98b7d'};
var SANS='system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif',PX='monospace';
var QR_SRC='https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.min.js';
var LEAF=null;try{if(w.Path2D)LEAF=new Path2D(D.leaf)}catch(e){}
function pad(x){return(x<10?'0':'')+x}
function settle(p,ms){return new Promise(function(res){var t=setTimeout(function(){res(false)},ms);
p.then(function(v){clearTimeout(t);res(v)},function(){clearTimeout(t);res(false)})})}

/* --- assets: pixel font + QR lib (both optional) --- */
var fontP,qrP;
function fontReady(){if(!fontP){
fontP=(d.fonts&&d.fonts.load)?settle(d.fonts.load('32px "Press Start 2P"').then(function(l){return l.length>0}),3000):Promise.resolve(false);
fontP=fontP.then(function(ok){PX=ok?'"Press Start 2P",monospace':'monospace';if(!ok)fontP=null;return ok})}return fontP}
function qrReady(){if(typeof w.qrcode==='function')return Promise.resolve(true);if(!qrP){
qrP=settle(new Promise(function(res,rej){var s=d.createElement('script');s.src=QR_SRC;s.async=true;
s.onload=function(){typeof w.qrcode==='function'?res(true):rej()};s.onerror=rej;d.head.appendChild(s)}),5000)
.then(function(ok){if(!ok)qrP=null;return ok})}return qrP}

/* --- drawing primitives --- */
function F(size,weight,px){return(weight||'400')+' '+size+'px '+(px?PX:SANS)}
function leaf(x,cx,cy,size,rot,col,alpha){x.save();x.globalAlpha=alpha==null?1:alpha;x.fillStyle=col;x.translate(cx,cy);x.rotate(rot*Math.PI/180);
var s=size/100;x.scale(s,s);x.translate(-50,-50);
if(LEAF)x.fill(LEAF);else{x.beginPath();x.moveTo(50,0);x.lineTo(100,50);x.lineTo(50,100);x.lineTo(0,50);x.closePath();x.fill()}x.restore()}
function pxBox(x,bx,by,bw,bh,s,col){x.fillStyle=col;x.fillRect(bx+s,by,bw-2*s,bh);x.fillRect(bx,by+s,bw,bh-2*s)}
function pxText(x,t,tx,ty,size,col,align){x.font=F(size,'400',true);x.fillStyle=col;x.textAlign=align||'left';x.textBaseline='top';x.fillText(t,tx,ty);x.textAlign='left'}
function fitPx(x,t,size,maxW){x.font=F(size,'400',true);while(size>12&&x.measureText(t).width>maxW){size-=2;x.font=F(size,'400',true)}return size}
var ICONS={
like:['.XX.XX.','XXXXXXX','XXXXXXX','.XXXXX.','..XXX..','...X...'],
repost:['..X....','.XXXXX.','..X...X','......X','X......','X...X..','.XXXXX.','....X..'],
reply:['XXXXXXX','X.....X','X.X.X.X','X.....X','XXXXXXX','.X.....','X......'],
view:['..XXXXX..','.X.....X.','X...X...X','X..XXX..X','.X.....X.','..XXXXX..']};
function icon(x,name,ix,iy,s,col){var rows=ICONS[name];x.fillStyle=col;
for(var r=0;r<rows.length;r++)for(var c=0;c<rows[r].length;c++)if(rows[r][c]==='X')x.fillRect(ix+c*s,iy+r*s,s,s);return rows[0].length*s}

/* word wrap: spaces for Latin, per-glyph for CJK, hard-break overlong tokens (URLs) */
var CJK='⺀-鿿가-힯豈-﫿＀-￯';
var TOK=new RegExp('['+CJK+']|[^\\s'+CJK+']+|\\s+','g');
function wrap(x,text,maxW){var out=[];
String(text||'').split('\n').forEach(function(p){p=p.replace(/\s+/g,' ').trim();if(!p)return;if(out.length)out.push('');
var line='';(p.match(TOK)||[]).forEach(function(t){
if(/^\s+$/.test(t)){if(line)line+=' ';return}
if(x.measureText(line+t).width<=maxW){line+=t;return}
if(line.trim())out.push(line.trim());line='';
while(x.measureText(t).width>maxW){var k=t.length;while(k>1&&x.measureText(t.slice(0,k)).width>maxW)k--;out.push(t.slice(0,k));t=t.slice(k)}
line=t});
if(line.trim())out.push(line.trim())});return out}
function blockH(lines,lh){var h=0;lines.forEach(function(l){h+=l===''?lh*.5:lh});return h}
/* largest size that fits maxH; at the smallest size, truncate with an ellipsis */
function fit(x,text,maxW,maxH,sizes,weight){var r;
for(var i=0;i<sizes.length;i++){x.font=F(sizes[i],weight);var lh=Math.round(sizes[i]*1.45),lines=wrap(x,text,maxW);
r={size:sizes[i],lh:lh,lines:lines};if(blockH(lines,lh)<=maxH)return r}
var keep=[],h=0;for(var j=0;j<r.lines.length;j++){var add=r.lines[j]===''?r.lh*.5:r.lh;if(h+add>maxH)break;keep.push(r.lines[j]);h+=add}
while(keep.length&&keep[keep.length-1]==='')keep.pop();
if(keep.length<r.lines.length&&keep.length){var last=keep[keep.length-1],sp=last.lastIndexOf(' ');if(sp>last.length*.6)last=last.slice(0,sp);
while(last&&x.measureText(last+'…').width>maxW)last=last.slice(0,-1);keep[keep.length-1]=last.replace(/[\s,.;:-]+$/,'')+'…'}
r.lines=keep;return r}
function drawLines(x,r,tx,ty,col,weight){x.font=F(r.size,weight);x.fillStyle=col;x.textBaseline='top';var y=ty;
r.lines.forEach(function(l){if(l===''){y+=r.lh*.5;return}x.fillText(l,tx,y+(r.lh-r.size)/2);y+=r.lh});return y}

/* --- shared poster chrome --- */
function frame(right){var c=d.createElement('canvas');c.width=W;c.height=H;var x=c.getContext('2d');
x.fillStyle=C.paper;x.fillRect(0,0,W,H);
x.fillStyle=C.line;for(var gy=18;gy<H;gy+=36)for(var gx=18;gx<W;gx+=36)x.fillRect(gx,gy,3,3);
x.fillStyle=C.card;x.fillRect(48,48,W-96,H-96);x.strokeStyle=C.ink;x.lineWidth=3;x.strokeRect(49.5,49.5,W-99,H-99);
x.fillStyle=C.red;[[30,30,1,1],[W-30,30,-1,1],[30,H-30,1,-1],[W-30,H-30,-1,-1]].forEach(function(k){
x.fillRect(k[2]>0?k[0]:k[0]-56,k[3]>0?k[1]:k[1]-10,56,10);x.fillRect(k[2]>0?k[0]:k[0]-10,k[3]>0?k[1]:k[1]-56,10,56)});
var s=fitPx(x,'CODEX // 28-DAY SPRINT',22,CW-260);x.font=F(s,'400',true);x.textBaseline='top';var tx=X0;
[['CODEX ',C.ink],['//',C.red],[' 28-DAY SPRINT',C.ink]].forEach(function(p){x.fillStyle=p[1];x.fillText(p[0],tx,100);tx+=x.measureText(p[0]).width});
pxText(x,right,X1,100,s,C.redInk,'right');
x.fillStyle=C.ink;x.fillRect(X0,146,CW,3);
return {c:c,x:x}}
function stats(x,vals,y){var names=['like','repost','reply','view'],col=CW/4;
vals.forEach(function(v,i){var ix=X0+i*col,iw=icon(x,names[i],ix,y+3,5,i===0?C.red:C.mut);
x.font=F(32,'700');x.fillStyle=C.ink;x.textBaseline='top';x.fillText(v,ix+iw+14,y-1)})}
function footer(x,url,cta,tail){var y=1050,q=200,qx=X1-q,qy=H-48-q-26,hasQR=false;
x.strokeStyle=C.line;x.lineWidth=2;x.setLineDash([10,8]);x.beginPath();x.moveTo(X0,y-14);x.lineTo(X1,y-14);x.stroke();x.setLineDash([]);
if(typeof w.qrcode==='function'){try{var g=w.qrcode(0,'M');g.addData(url);g.make();var m=g.getModuleCount(),cell=Math.floor((q-20)/(m+2)),
size=cell*(m+2),ox=qx+Math.floor((q-size)/2),oy=qy+Math.floor((q-size)/2);
x.fillStyle=C.card;x.fillRect(qx,qy,q,q);x.strokeStyle=C.ink;x.lineWidth=3;x.strokeRect(qx+1.5,qy+1.5,q-3,q-3);x.fillStyle=C.ink;
for(var r=0;r<m;r++)for(var k=0;k<m;k++)if(g.isDark(r,k))x.fillRect(ox+(k+1)*cell,oy+(r+1)*cell,cell,cell);hasQR=true}catch(e){hasQR=false}}
var maxW=hasQR?qx-X0-36:CW,parts=url.replace(/^https?:\/\//,'').split('/'),host=parts.shift(),path='/'+parts.join('/');
var ps=fitPx(x,cta,18,maxW);pxText(x,cta,X0,y+16,ps,C.redInk);
var us=36;x.font=F(us,'700');while(us>20&&Math.max(x.measureText(host).width,x.measureText(path).width)>maxW){us-=2;x.font=F(us,'700')}
x.textBaseline='top';x.fillStyle=C.ink;x.fillText(host,X0,y+62);if(path!=='/'){x.fillStyle=C.red;x.fillText(path,X0,y+62+us*1.3)}
x.font=F(22);x.fillStyle=C.mut;x.fillText(tail,X0,H-48-26-24)}

/* --- posters --- */
function dayPoster(e){var f=frame('LV.'+pad(D.latest)+' / '+D.total),x=f.x;
var bs=fitPx(x,e.label,52,560);x.font=F(bs,'400',true);var bw=Math.round(x.measureText(e.label).width)+60,bh=bs+44;
pxBox(x,X0,196,bw,bh,8,C.red);pxText(x,e.label,X0+30,196+22+4,bs,'#fff');
leaf(x,900,222,96,-18,C.red);leaf(x,968,270,48,28,C.pink);leaf(x,838,286,38,64,C.red,.85);
x.font=F(28);x.fillStyle=C.mut;x.textBaseline='top';x.fillText(e.date,X0,326);
pxText(x,e.status,X1,332,16,C.redInk,'right');
leaf(x,800,690,480,14,C.red,.05);
var r=fit(x,e.body,CW,530,[46,42,38,35,32,30,28],'400');drawLines(x,r,X0,388,C.ink,'400');
stats(x,e.stats,962);
footer(x,e.url,e.day===0?'SCAN TO READ THE KICKOFF':'SCAN TO READ '+e.label,'Unofficial fan tracker of @'+D.handle+' on X');
return f.c}
function sitePoster(){var f=frame('SEASON 01'),x=f.x,total=D.total,lv=D.latest;
pxText(x,'AUTUMN 2026 // OCT 5 - NOV 1',X0,196,fitPx(x,'AUTUMN 2026 // OCT 5 - NOV 1',20,CW),C.redInk);
var ts=118;x.font=F(ts,'800');while(x.measureText('Codex: 28 Days').width>CW&&ts>60){ts-=4;x.font=F(ts,'800')}
x.textBaseline='top';x.fillStyle=C.ink;x.fillText('Codex: 28 Days',X0-4,244);
var l2=244+Math.round(ts*1.08);x.fillText('of ',X0-4,l2);var ow=x.measureText('of ').width;x.fillStyle=C.red;x.fillText('Shipping',X0-4+ow,l2);
var endX=X0+ow+x.measureText('Shipping').width;if(endX<760){leaf(x,904,l2+78,100,-16,C.red);leaf(x,966,l2+136,48,32,C.pink);leaf(x,826,l2+132,36,70,C.red,.85)}
var r=fit(x,'Every daily Codex ship from Tibo’s 28-day sprint, tracked day by day.',CW,90,[32,30,28]);drawLines(x,r,X0,l2+ts+44,C.mut);
var by=650;pxText(x,'XP',X0,by,22,C.ink);pxText(x,'LV.'+pad(lv)+' / '+total,X1,by,22,C.redInk,'right');
var bx=X0,bt=by+40,bw=CW,bh=60,gap=4,inner=8,sw=(bw-2*inner-gap*(total-1))/total;
x.fillStyle=C.card;x.fillRect(bx,bt,bw,bh);x.strokeStyle=C.line;x.lineWidth=2;x.strokeRect(bx+1,bt+1,bw-2,bh-2);
for(var i=1;i<=total;i++){var sx=bx+inner+(i-1)*(sw+gap),sy=bt+inner,sh=bh-2*inner;
x.fillStyle=i<=lv?C.red:C.paper;x.fillRect(sx,sy,sw,sh);x.lineWidth=2;x.strokeStyle=i===lv?C.ink:(i<lv?C.red:C.line);x.strokeRect(sx+1,sy+1,sw-2,sh-2)}
x.font=F(26);x.fillStyle=C.mut;x.textBaseline='top';x.fillText('Day '+lv+' of '+total+' tracked',X0,bt+bh+16);
var latest=null;D.entries.forEach(function(e){if(!latest||e.day>latest.day)latest=e});
var ly=850;
if(latest){pxText(x,'LATEST SHIP // '+latest.label,X0,ly,fitPx(x,'LATEST SHIP // '+latest.label,20,CW),C.redInk);
drawLines(x,fit(x,latest.body.replace(/\s+/g,' '),CW,132,[32,30,28]),X0,ly+42,C.ink)}
else{x.font=F(34);x.fillStyle=C.ink;x.fillText('The sprint is about to begin.',X0,ly+42)}
footer(x,D.site,'SCAN TO JOIN THE SPRINT','Unofficial fan tracker · @'+D.handle+' on X');
return f.c}

/* --- preview modal --- */
var M,img,wait,title,saveB,shareB,lastFocus,cur=null,job=0;
function el(tag,cls,txt){var e=d.createElement(tag);if(cls)e.className=cls;if(txt)e.textContent=txt;return e}
function btn(cls,txt){var b=el('button',cls,txt);b.type='button';return b}
function build(){M=el('div','pm');M.hidden=true;M.setAttribute('role','dialog');M.setAttribute('aria-modal','true');M.setAttribute('aria-labelledby','pm-t');
var box=el('div','pm-box'),head=el('div','pm-head'),x=btn('tag pm-x','CLOSE');title=el('p','pm-title px');title.id='pm-t';
x.setAttribute('aria-label','Close poster preview');head.appendChild(title);head.appendChild(x);
var stage=el('div','pm-stage');img=el('img');img.hidden=true;img.alt='';wait=el('p','pm-wait px','RENDERING...');stage.appendChild(img);stage.appendChild(wait);
var hint=el('p','pm-hint');hint.appendChild(el('strong','','Long-press to save'));hint.appendChild(d.createTextNode(' on mobile, or tap SAVE IMAGE.'));
var act=el('div','pm-act');saveB=btn('tag is-main','SAVE IMAGE');shareB=btn('tag','SHARE IMAGE');shareB.hidden=true;act.appendChild(saveB);act.appendChild(shareB);
[head,stage,hint,act].forEach(function(c){box.appendChild(c)});M.appendChild(box);
M.addEventListener('click',function(e){if(e.target===M)close()});x.addEventListener('click',close);
saveB.addEventListener('click',save);shareB.addEventListener('click',shareImg);
d.addEventListener('keydown',function(e){if(M.hidden)return;
if(e.key==='Escape'||e.key==='Esc'){e.preventDefault();close();return}
if(e.key!=='Tab')return;var f=Array.prototype.filter.call(M.querySelectorAll('button'),function(b){return !b.hidden&&!b.disabled});if(!f.length)return;
var i=f.indexOf(d.activeElement);if(e.shiftKey&&i<=0){e.preventDefault();f[f.length-1].focus()}else if(!e.shiftKey&&i===f.length-1){e.preventDefault();f[0].focus()}});
d.body.appendChild(M)}
function open(key,from){var e=null;
if(key!=='site'){D.entries.forEach(function(x){if(String(x.day)===key&&!e)e=x});if(!e)return}
if(!M)build();lastFocus=from;var my=++job;cur=null;
var name=e?'codex-'+(e.day===0?'kickoff':'day-'+pad(e.day))+'-poster.png':'codex-28-days-poster.png';
title.textContent=e?'POSTER // '+e.label:'SITE POSTER';
img.hidden=true;img.removeAttribute('src');wait.hidden=false;wait.textContent='RENDERING...';saveB.disabled=true;shareB.hidden=true;
M.hidden=false;d.documentElement.classList.add('pm-open');M.querySelector('.pm-x').focus();
Promise.all([fontReady(),qrReady()]).then(function(){if(my!==job)return;
var c=e?dayPoster(e):sitePoster();cur={c:c,name:name,url:e?e.url:D.site,file:null};
img.src=c.toDataURL('image/png');img.alt=e?'Share poster for Codex '+e.label:'Codex: 28 Days of Shipping share poster';
img.hidden=false;wait.hidden=true;saveB.disabled=false;prepShare(cur,my)})
.catch(function(){if(my===job)wait.textContent='COULD NOT RENDER'})}
function prepShare(p,my){if(!n.canShare||!p.c.toBlob||typeof File!=='function')return;
p.c.toBlob(function(b){if(!b||my!==job)return;try{var f=new File([b],p.name,{type:'image/png'});
if(n.canShare({files:[f]})){p.file=f;shareB.hidden=false}}catch(e){}},'image/png')}
function save(){if(!cur)return;var p=cur;
function go(href,blob){var a=d.createElement('a');a.href=href;a.download=p.name;a.rel='noopener';d.body.appendChild(a);a.click();a.parentNode.removeChild(a);
if(blob)setTimeout(function(){URL.revokeObjectURL(href)},4000)}
if(p.c.toBlob&&w.URL&&URL.createObjectURL)p.c.toBlob(function(b){b?go(URL.createObjectURL(b),true):go(p.c.toDataURL('image/png'))},'image/png');
else go(p.c.toDataURL('image/png'))}
function shareImg(){if(!cur||!cur.file)return;n.share({files:[cur.file],title:'Codex: 28 Days of Shipping',text:cur.url}).catch(function(){})}
function close(){if(!M||M.hidden)return;job++;cur=null;M.hidden=true;d.documentElement.classList.remove('pm-open');
if(lastFocus&&lastFocus.focus)lastFocus.focus()}
Array.prototype.forEach.call(d.querySelectorAll('[data-poster]'),function(b){b.hidden=false;
b.addEventListener('click',function(){open(b.getAttribute('data-poster'),b)})});
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
        label = "ANNOUNCEMENT" if e["day"] == 0 else f"DAY {day_slug(e).zfill(2)}"
        status = "QUEST START" if e["day"] == 0 else "CLEARED"
        iso, pretty = fmt_date(e.get("posted_at", ""))
        time_attr = f' datetime="{esc(iso)}"' if iso else ""
        paras = "".join(f"<p>{esc(p)}</p>" for p in e["text"].split("\n") if p.strip())
        cards.append(f"""<article class="quest{' is-new' if is_new else ''}" id="day-{day_slug(e)}">
  {'<span class="new-ship px">NEW SHIP</span>' if is_new else ''}
  <div class="quest-head"><span class="badge px">{esc(label)}</span>
  <time{time_attr}>{esc(pretty)}</time><span class="status px">{status}</span></div>
  <div class="text">{paras}</div>
  <div class="meta"><span title="Likes">♥ {fmt_int(e.get('likes'))}</span><span title="Reposts">↻ {fmt_int(e.get('reposts'))}</span><span title="Replies">💬 {fmt_int(e.get('replies'))}</span><span title="Views">👁 {fmt_int(e.get('views'))}</span>
  <a class="orig" href="{esc(e['url'])}" target="_blank" rel="noopener">View on X →</a></div>
  <div class="share"><span class="share-label px">SHARE</span>{share_tags(share_blurb(e), day_url(day_slug(e)), share_blurb(e).split(":")[0] + " — 28 Days of Shipping", day_slug(e))}</div>
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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Codex: 28 Days of Shipping — tracking @{HANDLE}</title>
<meta name="description" content="Unofficial daily tracker of Tibo (@{HANDLE}, OpenAI Codex lead)'s 28-day shipping sprint: every Codex improvement, day by day, Oct 5 – Nov 1 2026.">
<meta property="og:title" content="Codex: 28 Days of Shipping">
<meta property="og:description" content="Every daily Codex ship from Tibo's 28-day sprint, tracked day by day.">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE_URL}/">
<meta property="og:site_name" content="Codex: 28 Days of Shipping">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Codex: 28 Days of Shipping">
<meta name="twitter:description" content="Every daily Codex ship from Tibo's 28-day sprint, tracked day by day.">
<link rel="canonical" href="{SITE_URL}/">
<meta name="theme-color" content="#faf8f3">
<link rel="icon" href="{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap">
<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "{CF_BEACON_TOKEN}"}}'></script>
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
<div class="xp-bar" style="--n:{TOTAL_DAYS};--half:{(TOTAL_DAYS + 1) // 2}" role="progressbar" aria-label="Sprint progress" aria-valuemin="0" aria-valuemax="{TOTAL_DAYS}" aria-valuenow="{latest_day}">{segs}</div>
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
<div class="share">{share_tags(SITE_SHARE_TEXT, f"{SITE_URL}/", "Codex: 28 Days of Shipping", "site", "SITE POSTER")}</div>
</section>
<footer class="site-foot">
<p class="px">GAME SAVED</p>
<p>Unofficial fan tracker. All posts belong to <a href="https://x.com/{HANDLE}" target="_blank" rel="noopener">@{HANDLE}</a> on X.
Source: public posts, refreshed twice daily. Not affiliated with OpenAI. ·
<a href="data/days.json">raw JSON</a> · <a href="https://github.com/Genuifx/codex-28-days">GitHub</a></p>
</footer>
</main>
<script type="application/json" id="poster-data">{poster_data(entries, latest_day)}</script>
<script>{JS}</script>
<script>{POSTER_JS}</script>
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
            t["sub"] = day_sub(t["text"])
            log["entries"].append(t)
            known_ids.add(tw["id"])
            added += 1
            print(f"added Day {day_slug(t)}: {tw['id']}", flush=True)

    save_log(log)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(render(log))
    print(f"done: {added} new, {len(log['entries'])} total entries", flush=True)


if __name__ == "__main__":
    main()
