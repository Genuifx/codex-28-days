"""Run with python3 -B -m unittest discover -v; all network is isolated."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import scrape


FIXTURES = Path(__file__).parent / "fixtures"
DAY10 = "2110595484180214059"
DAY11 = "2110750421367287996"
FOLLOWUP = "2110595554036400151"


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


class ScrapeFlowTests(unittest.TestCase):
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
                names = ("data/days.json", "index.html", "sitemap.xml", "llms.txt")
                before = {name: (root / name).read_bytes() for name in names}
                scrape.main()
                self.assertEqual(before, {name: (root / name).read_bytes() for name in names})


if __name__ == "__main__":
    unittest.main()
