"""Run with python3 -B -m unittest discover -v; all network is isolated."""
import contextlib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import scrape


FIXTURES = Path(__file__).parent / "fixtures"
DAY10 = "2110595484180214059"
DAY11 = "2110750421367287996"
FOLLOWUP = "2110595554036400151"
DAY12 = "2111244596131111253"
PRO = "2111244957851984181"
HOME_SCREEN = "2111245052513259606"


def status_fixture(tweet_id):
    return json.loads((FIXTURES / f"{tweet_id}.json").read_text())


class DayMarkerTests(unittest.TestCase):
    def test_day10_marker_after_intro_is_recognized(self):
        text = status_fixture(DAY10)["tweet"]["text"]
        self.assertEqual(scrape.day_number(text), 10)

    def test_sub_and_qualifier_use_the_same_line_marker(self):
        text = "A short introduction.\n\nDay 12.2 (encore)/\nA new ship."
        self.assertEqual(scrape.day_number(text), 12)
        self.assertEqual(scrape.day_sub(text), ".2")
        self.assertEqual(scrape.day_qual(text), "encore")

    def test_existing_formats_still_work(self):
        for text, day, sub, qualifier in [
            (status_fixture(DAY11)["tweet"]["text"], 11, "", ""),
            ("Day 2.4/ API improvement", 2, ".4", ""),
            ("Day 5 (dots edition)/ New feature", 5, "", "dots edition"),
            ("  day 3 (encore)/ Another ship", 3, "", "encore"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(scrape.day_number(text), day)
                self.assertEqual(scrape.day_sub(text), sub)
                self.assertEqual(scrape.day_qual(text), qualifier)

    def test_inline_roundups_quotes_and_followups_are_not_day_entries(self):
        for text in [
            "Roundup of Day 2/ with four releases",
            "> Day 10/ Reset",
            'Someone said "Day 10/ Reset".',
            status_fixture(FOLLOWUP)["tweet"]["text"],
        ]:
            with self.subTest(text=text):
                self.assertIsNone(scrape.day_number(text))


class PosterLinkTests(unittest.TestCase):
    def setUp(self):
        self.entries = [
            {"day": 0, "text": "Sprint kickoff"},
            {"day": 2, "sub": ".1", "text": "Day 2.1/ Sub-day ship"},
            {"day": 3, "text": "Day 3/ First ship"},
            {"day": 3, "qual": "encore", "text": "Day 3 (encore)/ Second ship"},
            {"day": 5, "text": "Day 5/ First ship"},
            {"day": 5, "qual": "dots edition", "text": "Day 5 (dots edition)/ Second ship"},
            {"day": 12, "sub": ".2", "qual": "encore", "text": "Day 12.2 (encore)/ Another ship"},
        ]
        for index, entry in enumerate(self.entries):
            entry.update(id=str(index), url=f"https://x.com/thsottiaux/status/{index}")

    def test_poster_urls_use_unique_entry_keys(self):
        posters = json.loads(scrape.poster_data(self.entries, 12))["entries"]
        expected_keys = ["0", "2.1", "3", "3-encore", "5", "5-dots-edition", "12.2-encore"]
        self.assertEqual([poster["key"] for poster in posters], expected_keys)
        for poster, key in zip(posters, expected_keys):
            with self.subTest(key=key):
                self.assertEqual(poster["url"], scrape.entry_url(self.entries[expected_keys.index(key)]))

    def test_rendered_posters_link_to_their_own_cards(self):
        page = scrape.render({"entries": self.entries, "resets": []}, changed=True)
        posters = json.loads(re.search(
            r'<script type="application/json" id="poster-data">(.*?)</script>', page, re.S
        ).group(1))["entries"]
        cards = {}
        for anchor, body in re.findall(r'<article[^>]* id="([^"]+)"[^>]*>(.*?)</article>', page, re.S):
            key = re.search(r'data-poster="([^"]+)"', body).group(1)
            copy_url = re.search(r'data-copy="([^"]+)"', body).group(1)
            cards[key] = (anchor, copy_url)
        self.assertEqual(len(cards), len(self.entries))
        self.assertEqual(len(posters), len(self.entries))
        for poster in posters:
            with self.subTest(key=poster["key"]):
                anchor, copy_url = cards[poster["key"]]
                self.assertEqual("day-" + poster["key"], anchor)
                self.assertEqual(poster["url"], copy_url)


class ScrapeFlowTests(unittest.TestCase):
    def test_discovery_failure_is_explicit_and_preserves_existing_data(self):
        log = {"entries": [{"id": DAY12, "day": 12}], "resets": []}
        before = json.dumps(log)
        errors = io.StringIO()
        with patch.object(scrape, "fetch", side_effect=OSError("source offline")), \
                contextlib.redirect_stderr(errors):
            self.assertEqual(scrape.discover_statuses(log), [])
        self.assertEqual(json.dumps(log), before)
        self.assertIn("coverage unverified", errors.getvalue())
        self.assertEqual(errors.getvalue().count("Discovery source unavailable"), 2)

    def test_lagging_source_is_reported_and_ids_remain_strings(self):
        page = f'<a href="/thsottiaux/status/{DAY11}">post</a>'
        errors = io.StringIO()
        with patch.object(scrape, "fetch", return_value=page), \
                contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            posts = scrape.discover_statuses({"entries": [{"id": DAY12}]})
        self.assertEqual(posts, [{"id": DAY11}])
        self.assertIn("behind the archive", errors.getvalue())

    def test_source_staleness_includes_archived_followups(self):
        page = f'<a href="/thsottiaux/status/{DAY12}">post</a>'
        errors, coverage = io.StringIO(), {}
        log = {"entries": [{"id": DAY12, "followups": [{"id": HOME_SCREEN}]}]}
        with patch.object(scrape, "fetch", return_value=page), \
                contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
            scrape.discover_statuses(log, coverage)
        self.assertEqual(coverage["lagging_sources"], 1)

    def test_secondary_source_recovers_day_and_author_followups(self):
        self.assert_secondary_source_recovers_followups(preseed=False)

    def test_secondary_source_attaches_followups_to_already_archived_day(self):
        self.assert_secondary_source_recovers_followups(preseed=True)

    def assert_secondary_source_recovers_followups(self, preseed):
        fixtures = {tid: status_fixture(tid) for tid in (DAY12, PRO, HOME_SCREEN)}
        # The primary profile has omitted the day; the fallback includes replies
        # before their parent, duplicate links, and an unrelated author.
        unrelated = "2111249810502353152"
        fixtures[unrelated] = status_fixture(PRO)
        fixtures[unrelated]["tweet"].update(id=unrelated, replying_to_status="2111249534072529256")
        links = "".join(f'<a href="/thsottiaux/status/{tid}">View Details</a>'
                        for tid in (PRO, HOME_SCREEN, DAY12, PRO, unrelated))

        def fetch_fixture(url):
            if url == "https://twiscan.com/en/x/thsottiaux":
                return "<html>No recent posts available</html>"
            if url == "https://site.twstalker.com/thsottiaux":
                return links
            prefix = "https://api.fxtwitter.com/thsottiaux/status/"
            if url.startswith(prefix) and url[len(prefix):] in fixtures:
                return json.dumps(fixtures[url[len(prefix):]])
            raise AssertionError(f"Unexpected network request: {url}")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "data/days.json"
            data_path.parent.mkdir()
            seed = {"handle": "thsottiaux", "total_days": 28, "entries": [{
                "id": scrape.ANNOUNCEMENT_ID, "day": 0, "text": "Sprint kickoff",
                "text_zh": "冲刺开始", "url": "https://x.com/thsottiaux/status/" + scrape.ANNOUNCEMENT_ID,
                "posted_at": "Sun Oct 04 20:33:43 +0000 2026",
            }], "resets": []}
            if preseed:
                source = fixtures[DAY12]["tweet"]
                seed["entries"].append({"id": DAY12, "day": 12, "text": source["text"],
                                        "posted_at": source["created_at"], "url": source["url"],
                                        "text_zh": "已保存的第 12 天译文"})
            data_path.write_text(json.dumps(seed))
            (root / "data/titles.json").write_text("{}")
            (root / "assets/og").mkdir(parents=True)
            shutil.copyfile(Path(__file__).parents[1] / "assets/og/cover.png", root / "assets/og/cover.png")
            with patch.multiple(scrape, ROOT=str(root), DATA_PATH=str(data_path),
                                INDEX_PATH=str(root / "index.html")), \
                    patch.object(scrape, "fetch", side_effect=fetch_fixture), \
                    patch.object(scrape, "translate_entry", side_effect=lambda text: "译文：" + text), \
                    contextlib.redirect_stdout(io.StringIO()):
                scrape.main()
                first = json.loads(data_path.read_text())
                self.assertEqual([e["id"] for e in first["entries"]], [scrape.ANNOUNCEMENT_ID, DAY12])
                day = first["entries"][-1]
                self.assertEqual(day["day"], 12)
                self.assertEqual({e["id"] for e in day["followups"]}, {PRO, HOME_SCREEN})
                for e in day["followups"]:
                    self.assertEqual(e["replying_to_status"], DAY12)
                    self.assertTrue(e["text_zh"])
                    self.assertTrue(e["quote_text_zh"])
                rendered = (root / "index.html").read_text()
                self.assertIn('id="day-12"', rendered)
                self.assertIn('2111192259073094035', rendered)
                self.assertIn('2111136119945396436', rendered)
                self.assertNotIn(unrelated, rendered)
                self.assertIn(PRO, (root / "llms.txt").read_text())
                names = tuple(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
                self.assertTrue((root / "zh/feed.xml").exists())
                self.assertEqual(len(list(root.rglob("*.html"))), 2 + 2 * len(first["entries"]))
                before = {name: (root / name).read_bytes() for name in names}
                scrape.main()
                self.assertEqual(before, {name: (root / name).read_bytes() for name in names})
                output = io.StringIO()
                with patch.object(scrape, "fetch", side_effect=OSError("source offline")), \
                        contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    scrape.main()
                self.assertEqual(before, {name: (root / name).read_bytes() for name in names})
                self.assertIn("DEGRADED coverage", output.getvalue())
                self.assertIn("no-new is unverified", output.getvalue())
                self.assertIn("failed_sources=2", output.getvalue())

                def status_failure(url):
                    if "fxtwitter" in url:
                        raise OSError("status offline")
                    return links

                output = io.StringIO()
                with patch.object(scrape, "fetch", side_effect=status_failure), \
                        contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    scrape.main()
                self.assertEqual(before, {name: (root / name).read_bytes() for name in names})
                self.assertIn("failed_statuses=1", output.getvalue())

    def test_status_rejects_wrong_author_and_mismatched_id(self):
        for change in ({"author": {"screen_name": "someone_else"}}, {"id": PRO}):
            fixture = status_fixture(DAY12)
            fixture["tweet"].update(change)
            with self.subTest(change=change), patch.object(scrape, "fetch", return_value=json.dumps(fixture)):
                with self.assertRaises(ValueError):
                    scrape.fx_status(DAY12)

    def test_empty_status_never_uses_misattributed_preview(self):
        fixture = status_fixture(DAY12)
        fixture["tweet"]["text"] = ""
        with patch.object(scrape, "fetch", return_value=json.dumps(fixture)):
            with self.assertRaises(ValueError):
                scrape.fx_status(DAY12)

    def test_new_posts_are_saved_once_without_ingesting_quote_or_reply(self):
        fixtures = {tid: status_fixture(tid) for tid in (DAY10, DAY11, FOLLOWUP)}
        quote_id = "2110000000000000001"
        quoted = status_fixture(DAY11)
        quoted["tweet"].update(id=quote_id, text="Roundup of yesterday's updates.")
        quoted["tweet"]["quote"] = status_fixture(DAY10)["tweet"]
        fixtures[quote_id] = quoted
        timeline = "".join(
            f'<a href="https://twiscan.com/en/x/thsottiaux/{tid}">1 hour ago</a>'
            '<!-- text --><div class="whitespace-pre-wrap">Day 10/ misleading preview</div>'
            for tid in fixtures
        )

        def fetch_fixture(url):
            if url == "https://twiscan.com/en/x/thsottiaux":
                return timeline
            prefix = "https://api.fxtwitter.com/thsottiaux/status/"
            if url.startswith(prefix) and url[len(prefix):] in fixtures:
                return json.dumps(fixtures[url[len(prefix):]])
            raise AssertionError(f"Unexpected network request: {url}")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            data_path = root / "data/days.json"
            seed = {"handle": "thsottiaux", "total_days": 28, "entries": [{
                "id": scrape.ANNOUNCEMENT_ID, "day": 0, "text": "Sprint kickoff",
                "text_zh": "冲刺开始", "url": "https://x.com/thsottiaux/status/" + scrape.ANNOUNCEMENT_ID,
                "posted_at": "Sun Oct 04 20:33:43 +0000 2026",
            }], "resets": []}
            data_path.write_text(json.dumps(seed))
            (root / "data/titles.json").write_text("{}")
            (root / "assets/og").mkdir(parents=True)
            shutil.copyfile(Path(__file__).parents[1] / "assets/og/cover.png", root / "assets/og/cover.png")
            with patch.multiple(scrape, ROOT=str(root), DATA_PATH=str(data_path),
                                INDEX_PATH=str(root / "index.html")), \
                    patch.object(scrape, "fetch", side_effect=fetch_fixture), \
                    patch.object(scrape, "translate_entry", side_effect=lambda text: "译文：" + text), \
                    contextlib.redirect_stdout(io.StringIO()):
                scrape.main()
                first = json.loads(data_path.read_text())
                self.assertEqual({e["id"] for e in first["entries"]},
                                 {scrape.ANNOUNCEMENT_ID, DAY10, DAY11})
                entries = {e["id"]: e for e in first["entries"]}
                self.assertEqual(entries[DAY10]["text"], fixtures[DAY10]["tweet"]["text"])
                self.assertEqual(entries[DAY10]["day"], 10)
                self.assertEqual(entries[DAY11]["day"], 11)
                self.assertEqual(entries[DAY11]["posted_at"], "Thu Oct 15 15:11:30 +0000 2026")
                names = tuple(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
                self.assertTrue((root / "zh/feed.xml").exists())
                self.assertEqual(len(list(root.rglob("*.html"))), 2 + 2 * len(first["entries"]))
                before = {name: (root / name).read_bytes() for name in names}
                scrape.main()
                self.assertEqual(before, {name: (root / name).read_bytes() for name in names})


if __name__ == "__main__":
    unittest.main()

