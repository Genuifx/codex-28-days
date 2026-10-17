"""Static publishing contracts; no live network is needed."""
import copy
import hashlib
import json
from pathlib import Path
import re
import unittest

from scripts import scrape

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/growth_log.json'
SHA = 'c86895d553ff78b818c95883ebb6a0a4171c0e9935d78d232f1b83b2c7cc7c54'


def log_fixture():
    return json.loads(FIXTURE.read_text())


class PublishContractTests(unittest.TestCase):
    def test_snapshot_preserves_data_boundary(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), SHA)
        log = log_fixture()
        self.assertEqual(len(log['entries']), 18)
        self.assertEqual(len(log['resets']), 4)
        self.assertEqual(len({e['id'] for e in log['entries'] + log['resets']}), 20)
        self.assertEqual(sum(len(e.get('followups', [])) for e in log['entries']), 4)

    def test_routes_are_id_based_unique_and_reject_bad_inputs(self):
        self.assertTrue(hasattr(scrape, 'entry_path'), 'stable route helper is missing')
        entries = log_fixture()['entries']
        paths = set()
        for e in entries:
            for lang in scrape.LANGS:
                prefix = '/zh' if lang == 'zh' else ''
                expected = f'{prefix}/updates/{e["id"]}/'
                self.assertEqual(scrape.entry_path(e, lang), expected)
                self.assertEqual(scrape.entry_url(e, lang), scrape.SITE_URL + expected)
                changed = dict(e, day=28, qual='changed', title='New title')
                self.assertEqual(scrape.entry_path(changed, lang), expected)
                paths.add(expected)
        self.assertEqual(len(paths), 36)
        for bad in ({}, {'id': '../12'}, {'id': '１２'}, {'id': ''}, {'id': 12}):
            with self.assertRaises(ValueError):
                scrape.entry_path(bad)
        with self.assertRaises(ValueError):
            scrape.entry_path(entries[0], 'fr')
        self.assertEqual(scrape.day_url('3-encore'), scrape.SITE_URL + '/#day-3-encore')

    def test_curated_titles_have_traceable_sources(self):
        self.assertTrue(hasattr(scrape, 'load_titles'), 'title map loader is missing')
        titles = scrape.load_titles()
        for e in log_fixture()['entries']:
            title = titles[e['id']]
            available = {e['id'], (e.get('quote') or {}).get('id')}
            for f in e.get('followups', []):
                available.update([f['id'], (f.get('quote') or {}).get('id')])
            self.assertTrue(title['source_ids'])
            self.assertTrue(set(title['source_ids']) <= available)
            self.assertLessEqual(len(title['en']), 80)
            self.assertLessEqual(len(title['zh']), 60)
            for lang in scrape.LANGS:
                self.assertIn(title[lang], scrape.entry_title(e, lang, titles))
        self.assertEqual(titles['2107548725359104441']['zh'], 'OpenAI API 使用档位调整')
        self.assertEqual(titles['2109430343346581527']['zh'], 'GPT-6.1 Sol 默认上下文增至 500k')
        for tid in ('2109045220411351517', '2109812216212099456', '2110595484180214059'):
            self.assertIn('Reset', titles[tid]['en'])

    def test_new_entry_uses_bounded_source_excerpt(self):
        self.assertTrue(hasattr(scrape, 'entry_title'), 'title helper is missing')
        e = {'id': '999', 'day': 13, 'text': 'Day 13/\n' + 'New capability ' * 20}
        title = scrape.entry_title(e, titles={})
        self.assertTrue(title.startswith('Codex Day 13: New capability'))
        self.assertLessEqual(len(title.split(': ', 1)[1]), 80)
        self.assertEqual(scrape.entry_title(e, 'zh', {}), title)
        with self.assertRaises(ValueError):
            scrape.entry_title(e, 'fr')


class PublishPageTests(unittest.TestCase):
    def setUp(self):
        self.log = log_fixture()
        self.titles = scrape.load_titles()

    def test_all_details_have_localized_identity_and_preserved_content(self):
        self.assertTrue(hasattr(scrape, 'render_detail'), 'detail rendering is missing')
        for e in self.log['entries']:
            for lang in scrape.LANGS:
                with self.subTest(id=e['id'], lang=lang):
                    page = scrape.render_detail(self.log, e, lang, self.titles)
                    url = scrape.entry_url(e, lang)
                    title = scrape.entry_title(e, lang, self.titles)
                    self.assertIn(f'<link rel="canonical" href="{url}">', page)
                    for locale, target in [('en', 'en'), ('zh-CN', 'zh'), ('x-default', 'en')]:
                        self.assertIn(f'hreflang="{locale}" href="{scrape.entry_url(e, target)}"', page)
                    self.assertIn(f'<h1 class="detail-title">{scrape.esc(title)}</h1>', page)
                    self.assertIn(f'<title>{scrape.esc(title)}', page)
                    self.assertIn(f'data-copy="{url}"', page)
                    self.assertIn('href="/data/days.json"', page)
                    self.assertIn(f'href="{scrape.home_path(lang)}#day-{scrape.day_uid(e)}"', page)
                    for post in [e, *e.get('followups', [])]:
                        bodies = [post.get('text'), post.get('text_zh'), (post.get('quote') or {}).get('text'), post.get('quote_text_zh')]
                        for body in filter(None, bodies):
                            for paragraph in filter(str.strip, body.split('\n')):
                                self.assertIn(scrape.esc(paragraph), page)
                    graph = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)[1])
                    self.assertEqual(graph['headline'], title)
                    self.assertEqual(graph['url'], url)
                    self.assertEqual(graph['inLanguage'], 'zh-CN' if lang == 'zh' else 'en')

    def test_home_preserves_all_old_anchors_and_static_language(self):
        for lang in scrape.LANGS:
            self.assertTrue(hasattr(scrape, 'render_entry'), 'reusable entry rendering is missing')
            page = scrape.render(self.log, True, lang, self.titles)
            for e in self.log['entries']:
                self.assertIn(f'id="day-{scrape.day_uid(e)}"', page)
                self.assertIn(f'href="{scrape.entry_path(e, lang)}"', page)
                for f in e.get('followups', []):
                    self.assertIn(f'id="post-{f["id"]}"', page)
            self.assertIn(f'<html lang="{"zh-CN" if lang == "zh" else "en"}" data-lang="{lang}">', page)
            self.assertRegex(page, r'<a[^>]*class="lang-tag px"[^>]*href="[^" ]+"[^>]*data-lang-toggle')
            self.assertNotIn('localStorage', page)
            self.assertNotIn('navigator.language', page)
            self.assertNotIn("d.title=", page)

    def test_safe_scripts_and_missing_translation_fallback(self):
        self.assertTrue(hasattr(scrape, 'render_detail'), 'detail rendering is missing')
        evil = '</script><img src=x onerror="alert(1)"> & "quoted"'
        e = {'id': '998', 'day': 14, 'text': evil, 'url': 'https://x.com/test/status/998',
             'quote': {'text': evil, 'id': '997', 'handle': 'test', 'url': 'https://x.com/test/status/997'},
             'followups': [{'id': '999', 'text': evil, 'url': 'https://x.com/test/status/999'}]}
        page = scrape.render_detail({'entries': [e]}, e, 'zh', {})
        self.assertNotIn('<img src=x', page)
        self.assertIn(scrape.esc(evil), page)
        self.assertIn('暂无中文译文', page)
        self.assertIn('lang="en"', page)
        self.assertNotIn('noindex', page)
        self.assertNotIn('http-equiv="refresh"', page)
        post = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)[1])
        self.assertEqual(post['articleBody'], evil)
        poster = json.loads(re.search(r'id="poster-data">(.*?)</script>', page, re.S)[1])
        self.assertEqual(poster['entries'][0]['url'], scrape.entry_url(e, 'zh'))

    def test_all_share_surfaces_use_the_current_locale(self):
        for lang in scrape.LANGS:
            self.assertTrue(hasattr(scrape, 'render_detail'), 'detail rendering is missing')
            for e in self.log['entries']:
                page = scrape.render_detail(self.log, e, lang, self.titles)
                url = scrape.entry_url(e, lang)
                self.assertIn(f'data-copy="{url}"', page)
                self.assertIn(f'data-url="{url}"', page)
                posters = json.loads(re.search(r'id="poster-data">(.*?)</script>', page, re.S)[1])
                self.assertEqual(posters['entries'][0]['key'], scrape.day_uid(e))
                self.assertEqual(posters['entries'][0]['url'], url)
                self.assertIn(scrape.esc(scrape.tweet_intent(scrape.entry_title(e, lang, self.titles), url)), page)


class PublishDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.log = log_fixture()
        self.titles = scrape.load_titles()

    def test_feed_items_have_stable_identity_source_dates_and_locale(self):
        import email.utils
        import xml.etree.ElementTree as ET
        self.assertTrue(hasattr(scrape, 'render_feed'), 'RSS renderer is missing')
        for lang in scrape.LANGS:
            feed = scrape.render_feed(self.log, lang, self.titles)
            items = ET.fromstring(feed).findall('./channel/item')
            self.assertEqual(len(items), 18)
            dates = [email.utils.parsedate_to_datetime(i.findtext('pubDate')) for i in items]
            self.assertEqual(dates, sorted(dates, reverse=True))
            for e, item in zip(sorted(self.log['entries'], key=lambda e: scrape.parse_dt(e['posted_at']), reverse=True), items):
                self.assertEqual(item.findtext('title'), scrape.entry_title(e, lang, self.titles))
                self.assertEqual(item.findtext('link'), scrape.entry_url(e, lang))
                self.assertEqual(item.findtext('guid'), f'urn:codexy:x:{e["id"]}:{lang}')
                self.assertEqual(item.find('guid').attrib, {'isPermaLink': 'false'})
                self.assertIn(e['url'], item.findtext('description'))
            self.assertEqual(scrape.render_feed(self.log, lang, self.titles), feed)
            self.assertNotIn('lastBuildDate', feed)

    def test_followup_updates_parent_and_handles_missing_dates_translation_and_xml(self):
        import xml.etree.ElementTree as ET
        self.assertTrue(hasattr(scrape, 'render_feed'), 'RSS renderer is missing')
        e = {'id': '1', 'day': 1, 'text': 'Day 1/ <img src=x> & "hello"', 'url': 'https://x.com/test/status/1'}
        log = {'entries': [e]}
        first = ET.fromstring(scrape.render_feed(log, 'zh', {})).find('./channel/item')
        self.assertIsNone(first.find('pubDate'))
        self.assertIn('暂无中文译文', first.findtext('description'))
        self.assertIn('&lt;img', first.findtext('description'))
        e['followups'] = [{'id': '2', 'text': 'Follow-up & update', 'url': 'https://x.com/test/status/2'}]
        items = ET.fromstring(scrape.render_feed(log, 'zh', {})).findall('./channel/item')
        self.assertEqual(len(items), 1)
        self.assertEqual(first.findtext('guid'), items[0].findtext('guid'))
        self.assertIn('作者补充', items[0].findtext('description'))
        self.assertIn('https://x.com/test/status/2', items[0].findtext('description'))
        self.assertNotEqual(first.findtext('description'), items[0].findtext('description'))

    def test_sitemap_and_llms_have_all_pages_and_complete_sources(self):
        import xml.etree.ElementTree as ET
        urls = [node.text for node in ET.fromstring(scrape.render_sitemap(self.log)).iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertEqual(len(urls), 38)
        self.assertEqual(len(set(urls)), 38)
        self.assertFalse(any('#' in u for u in urls))
        self.assertNotIn('lastmod', scrape.render_sitemap(self.log))
        content = scrape.render_llms(self.log, self.titles)
        for e in self.log['entries']:
            for lang in scrape.LANGS:
                self.assertIn(scrape.entry_url(e, lang), content)
            for post in [e, *e.get('followups', [])]:
                for text in (post['text'], post.get('text_zh'), (post.get('quote') or {}).get('text'), post.get('quote_text_zh')):
                    if text:
                        self.assertIn(text.strip(), content)

    def test_og_dimensions_and_metadata(self):
        import struct
        png = ROOT / 'assets/og/cover.png'
        self.assertTrue(png.exists(), 'static preview PNG is missing')
        data = png.read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', data[16:24]), (1200, 630))
        self.assertGreater(len(data), 1000)
        for lang in scrape.LANGS:
            pages = [scrape.render(self.log, False, lang, self.titles)]
            pages += [scrape.render_detail(self.log, e, lang, self.titles) for e in self.log['entries']]
            for page in pages:
                self.assertIn('name="twitter:card" content="summary_large_image"', page)
                self.assertIn('property="og:image" content="https://codexy.fyi/assets/og/cover.png"', page)
                self.assertIn('name="twitter:image" content="https://codexy.fyi/assets/og/cover.png"', page)
                self.assertIn('property="og:image:width" content="1200"', page)
                self.assertIn('property="og:image:height" content="630"', page)
                self.assertIn(f'type="application/rss+xml" title="Codexy RSS" href="{scrape.SITE_URL + scrape.home_path(lang)}feed.xml"', page)
                self.assertIn(f'href="{scrape.home_path(lang)}feed.xml"', page)


class PublishBuildTests(unittest.TestCase):
    def assert_offline_roundtrip(self):
        import tempfile
        from unittest.mock import patch
        self.assertTrue(hasattr(scrape, 'write_site'), 'offline writer is missing')
        from scripts import build
        before = Path(scrape.DATA_PATH).read_bytes()
        current = json.loads(before)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'unrelated.txt').write_text('keep me')
            with patch.object(scrape, 'fetch', side_effect=AssertionError('network prohibited')), \
                 patch.object(scrape, 'translate_entry', side_effect=AssertionError('translation prohibited')), \
                 patch.object(scrape, 'save_log', side_effect=AssertionError('source write prohibited')):
                build.main(['--output', str(root)])
                first = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                build.main(['--output', str(root)])
                second = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(first, second)
            self.assertEqual(len(list(root.rglob('*.html'))), 2 + 2 * len(current['entries']))
            for name in ('feed.xml', 'zh/feed.xml', 'sitemap.xml', 'llms.txt', 'assets/og/cover.png', 'data/days.json'):
                self.assertTrue((root / name).is_file(), name)
            self.assertEqual((root / 'data/days.json').read_bytes(), before)
            self.assertEqual((root / 'unrelated.txt').read_text(), 'keep me')
            for e in current['entries']:
                for lang in scrape.LANGS:
                    self.assertTrue((root / scrape.entry_path(e, lang).lstrip('/') / 'index.html').is_file())
        self.assertEqual(Path(scrape.DATA_PATH).read_bytes(), before)

    def test_offline_build_is_complete_repeatable_and_preserves_source_bytes(self):
        # Production data can legitimately change after the daily scraper runs.
        # Its page count is data-driven; only the immutable fixture has a fixed SHA.
        self.assert_offline_roundtrip()

    def test_fixed_fixture_build_preserves_the_snapshot(self):
        import tempfile
        import shutil
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as source_directory:
            source = Path(source_directory)
            (source / 'data').mkdir()
            (source / 'data/days.json').write_bytes(FIXTURE.read_bytes())
            shutil.copyfile(ROOT / 'data/titles.json', source / 'data/titles.json')
            (source / 'assets/og').mkdir(parents=True)
            shutil.copyfile(ROOT / 'assets/og/cover.png', source / 'assets/og/cover.png')
            with patch.multiple(scrape, ROOT=str(source), DATA_PATH=str(source / 'data/days.json')):
                self.assert_offline_roundtrip()
            self.assertEqual(hashlib.sha256((source / 'data/days.json').read_bytes()).hexdigest(), SHA)

    def test_contract_accepts_future_entries_metrics_and_followups(self):
        import tempfile
        import shutil
        from unittest.mock import patch
        log = log_fixture()
        new_entry = copy.deepcopy(log['entries'][-1])
        new_entry.update(id='2222222222222222222', day=13, text='Day 13/ A verified new update',
                         text_zh='Day 13/ 已核实的新更新',
                         url='https://x.com/thsottiaux/status/2222222222222222222',
                         posted_at='Sat Oct 17 06:00:00 +0000 2026')
        new_entry.pop('followups', None)
        log['entries'].append(new_entry)
        log['entries'][0]['likes'] += 1
        log['entries'][0].setdefault('followups', []).append({
            'id': '2222222222222222223', 'text': 'New follow-up', 'url': 'https://x.com/thsottiaux/status/2222222222222222223',
            'posted_at': 'Sat Oct 17 06:00:00 +0000 2026'})
        with tempfile.TemporaryDirectory() as source_directory:
            source = Path(source_directory)
            (source / 'data').mkdir()
            (source / 'data/days.json').write_text(json.dumps(log))
            shutil.copyfile(ROOT / 'data/titles.json', source / 'data/titles.json')
            (source / 'assets/og').mkdir(parents=True)
            shutil.copyfile(ROOT / 'assets/og/cover.png', source / 'assets/og/cover.png')
            with patch(__name__ + '.ROOT', source), \
                 patch.multiple(scrape, ROOT=str(source), DATA_PATH=str(source / 'data/days.json')):
                self.assert_offline_roundtrip()

    def test_render_failure_keeps_existing_outputs(self):
        import tempfile
        from unittest.mock import patch
        self.assertTrue(hasattr(scrape, 'write_site'), 'offline writer is missing')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scrape.write_site(log_fixture(), True, directory)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            original = scrape.render_detail
            def fail_after_some_pages(log, e, lang='en', titles=None):
                if e['day'] == 7:
                    raise ValueError('broken page')
                return original(log, e, lang, titles)
            with patch.object(scrape, 'render_detail', side_effect=fail_after_some_pages):
                with self.assertRaisesRegex(ValueError, 'broken page'):
                    scrape.write_site(log_fixture(), True, directory)
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_duplicate_ids_fail_before_publishing(self):
        self.assertTrue(hasattr(scrape, 'build_outputs'), 'pure builder is missing')
        log = log_fixture()
        log['entries'].append(dict(log['entries'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            scrape.build_outputs(log, scrape.load_titles())

    def test_source_timestamp_is_deterministic_and_uses_followups(self):
        log = log_fixture()
        page = scrape.render(log, True)
        self.assertIn('2026-10-16 23:57 UTC', page)
        self.assertEqual(page, scrape.render(log, False))
        empty = scrape.render({'entries': [], 'resets': []}, True, 'zh', {})
        self.assertIn('更新时间未知', empty)

    def test_daily_workflow_covers_outputs_and_retests_conflict_rebuild(self):
        workflow = (ROOT / '.github/workflows/daily.yml').read_text()
        adds = re.findall(r'^\s+git add (.+)$', workflow, re.M)
        self.assertGreaterEqual(len(adds), 2)
        for line in adds:
            for path in ('data/days.json', 'index.html', 'zh', 'updates', 'feed.xml', 'sitemap.xml', 'llms.txt', 'assets/og'):
                self.assertIn(path, line)
        recovery = workflow.split('git rebase --abort', 1)[1]
        self.assertIn('python3 -B -m unittest discover -v', recovery)
        self.assertLess(recovery.index('python3 -B -m unittest discover -v'), recovery.index('git commit'))
