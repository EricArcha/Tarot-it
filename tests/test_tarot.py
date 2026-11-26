import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1] / 'tarot-it'
RUNNER = ROOT / 'scripts' / 'tarot.py'
ASSETS = ROOT / 'assets' / 'deck'
SPREADS = {'single': 1, 'present': 3, 'timeline': 3, 'relationship': 5,
           'dilemma': 5, 'horseshoe': 7, 'celtic-cross': 10, 'annual': 12}


def new_id():
    return str(uuid4())


class BoardHTML(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.images = []
        self.external = []
        self.feed(markup)

    def handle_starttag(self, tag, attributes):
        data = dict(attributes)
        if tag == 'img':
            self.images.append(data)
        self.external.extend(data[key] for key in ('src', 'href') if key in data and data[key].startswith(('https:', 'http:', '//')))


class TarotTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='Tarot it test ')
        self.addCleanup(self.folder.cleanup)
        self.state = Path(self.folder.name) / 'state'
        self.scope = new_id()

    def cli(self, *arguments, error=None, runner=RUNNER, python_flags=()):
        result = subprocess.run([sys.executable, *python_flags, str(runner), '--state-dir', str(self.state), *map(str, arguments)],
                                capture_output=True, text=True, check=False)
        self.assertIn(result.returncode, (0, 2), result.stderr)
        response = json.loads(result.stdout)
        if error is None:
            self.assertEqual((result.returncode, response['ok']), (0, True), response)
        else:
            self.assertEqual((result.returncode, response['ok']), (2, False), response)
            self.assertEqual(response['error']['code'], error)
        return response

    def start(self, spread='present', *args, request=None):
        return self.cli('start', '--scope', self.scope, '--request', request or new_id(), '--spread', spread, *args)

    def action(self, name, round_, *args, **kwargs):
        return self.cli(name, '--scope', self.scope, '--run', round_['run_id'], *args, **kwargs)

    def test_asset_completeness_and_sources(self):
        result = self.cli('check', '--full')
        self.assertEqual((result['cards'], result['spreads']), (78, 8))
        manifest = json.loads((ASSETS / 'manifest.json').read_text())['cards']
        self.assertEqual(len({record['sha256'] for record in manifest.values()}), 78)
        for key, image in manifest.items():
            with self.subTest(card=key):
                self.assertGreaterEqual(image['width'], 1000)
                self.assertGreaterEqual(image['height'], 1800)
                self.assertGreater(image['file_revision'], 0)
                self.assertIn('Public domain', image['rights'])
                card = json.loads((ROOT / 'references' / 'cards' / f'{key}.json').read_text())
                self.assertEqual((card['id'], card['image_id']), (key, key))
                self.assertTrue(card['sources']['waite'])
                contemporary = card['sources']['modern_review']
                self.assertEqual(contemporary['status'], 'reviewed')
                self.assertTrue(contemporary['card_url'].startswith('https://biddytarot.com/tarot-card-meanings/'))
                self.assertEqual(contemporary['method_url'], 'https://www.learntarot.com/less17.htm')
                self.assertTrue(contemporary['editorial_note'])
                self.assertIn(len(card['imagery']), (2, 3, 4))
                self.assertNotEqual(card['upright']['meaning'], card['reversed']['meaning'])
                self.assertNotRegex(card['upright']['meaning'] + card['reversed']['meaning'], r'[\u0e00-\u0e7f]')

    def test_each_spread_shows_real_ordered_images(self):
        for spread, count in SPREADS.items():
            with self.subTest(spread=spread):
                started = self.start(spread)
                revealed = self.action('reveal', started)
                shown = self.action('show', started)
                self.assertEqual(revealed['cards'], shown['cards'])
                self.assertEqual(len({entry['id'] for entry in shown['cards']}), count)
                board = BoardHTML(Path(shown['board']).read_text())
                self.assertEqual(len(board.images), count)
                self.assertEqual(board.external, [])
                for i, (entry, image, file) in enumerate(zip(shown['cards'], board.images, shown['images']), 1):
                    self.assertEqual(entry['position'], i)
                    self.assertIn(entry['name_zh'], image['alt'])
                    self.assertIn('正位' if entry['orientation'] == 'upright' else '逆位', image['alt'])
                    raw = base64.b64decode(image['src'].split(',', 1)[1])
                    self.assertEqual(raw, (ASSETS / 'original' / f'{entry["id"]}.jpg').read_bytes())
                    self.assertEqual(Path(file).read_bytes(), (ASSETS / entry['orientation'] / f'{entry["id"]}.jpg').read_bytes())

    def test_prepared_state_and_request_idempotency(self):
        request = new_id()
        started = self.start('timeline', request=request)
        self.assertNotIn('cards', started)
        for action in ('show', 'meaning'):
            self.action(action, started, error='not_revealed')
        self.assertEqual(started, self.start('timeline', request=request))
        self.cli('start', '--scope', self.scope, '--request', request, '--spread', 'annual', error='request_conflict')
        self.action('reveal', started)
        retried = self.start('timeline', request=request)
        self.assertEqual(retried['run_id'], started['run_id'])
        self.assertEqual(retried['status'], 'revealed')
        self.assertNotIn('cards', retried)

    def test_cut_selection_and_invalid_input(self):
        started = self.start('present', '--upright-only')
        self.action('select', started, '--cut', 78, error='cut')
        for bad in ((1, 1, 2), (1, 2), (1, 2, 79)):
            self.action('select', started, '--cut', 7, '--positions', *bad, error='positions')
        selected = self.action('select', started, '--cut', 7, '--positions', 78, 2, 1)
        self.assertEqual(selected, self.action('select', started, '--cut', 7, '--positions', 78, 2, 1))
        self.assertNotIn('cards', selected)
        with sqlite3.connect(self.state / 'rounds.sqlite3') as db:
            order = json.loads(db.execute('SELECT deck FROM rounds').fetchone()[0])
        revealed = self.action('reveal', started)
        self.assertEqual([x['id'] for x in revealed['cards']], [order[i][0] for i in (6, 8, 7)])
        self.assertTrue(all(x['orientation'] == 'upright' for x in revealed['cards']))
        self.action('select', started, '--cut', 4, error='already_revealed')

    def test_concurrent_reveal_and_reshow(self):
        start = self.start('annual')
        with ThreadPoolExecutor(3) as pool:
            runs = list(pool.map(lambda _: self.action('reveal', start), range(3)))
        self.assertTrue(all(result == runs[0] for result in runs))
        first = self.action('show', start)
        path = Path(first['board'])
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        path.unlink()
        self.assertEqual(first, self.action('show', start))
        self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_annual_month_labels(self):
        explicit = self.start('annual', '--year', 2027)
        self.assertEqual((explicit['positions'][0], explicit['positions'][-1]), ('2027 年 1 月', '2027 年 12 月'))
        today = date.today()
        year, month = divmod(today.year * 12 + today.month, 12)
        self.assertEqual(self.start('annual')['positions'][0], f'{year} 年 {month + 1} 月')
        self.cli('start', '--scope', self.scope, '--request', new_id(), '--year', 2027, error='year')

    def test_scope_clear_and_expiry(self):
        start = self.start()
        self.cli('reveal', '--scope', new_id(), '--run', start['run_id'], error='round_missing')
        self.action('reveal', start)
        path = Path(self.action('show', start)['board'])
        self.action('clear', start)
        self.assertFalse(path.exists())
        self.action('show', start, error='round_missing')
        expired = self.start()
        self.action('reveal', expired)
        path = Path(self.action('show', expired)['board'])
        with sqlite3.connect(self.state / 'rounds.sqlite3') as db:
            db.execute('UPDATE rounds SET created=1')
        self.action('reveal', expired, error='round_missing')
        self.assertFalse(path.exists())

    def test_cleared_start_request_cannot_recreate_a_deck(self):
        request = new_id()
        start = self.start('single', request=request)
        self.action('clear', start)
        args = ('start', '--scope', self.scope, '--request', request, '--spread', 'single')
        with ThreadPoolExecutor(3) as pool:
            list(pool.map(lambda _: self.cli(*args, error='cancelled'), range(3)))
        self.assertNotEqual(self.start('single')['run_id'], start['run_id'])

    def test_expired_start_request_cannot_recreate_a_deck(self):
        request = new_id()
        self.cli('spreads')
        self.assertFalse(self.state.exists())
        start = self.start('single', request=request)
        self.action('reveal', start)
        path = Path(self.action('show', start)['board'])
        with sqlite3.connect(self.state / 'rounds.sqlite3') as db:
            db.execute('UPDATE rounds SET created=1')
        self.cli('spreads')
        self.assertFalse(path.exists())
        self.action('show', start, error='round_missing')
        args = ('start', '--scope', self.scope, '--request', request, '--spread', 'single')
        with ThreadPoolExecutor(3) as pool:
            list(pool.map(lambda _: self.cli(*args, error='round_expired'), range(3)))
        with sqlite3.connect(self.state / 'rounds.sqlite3') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM rounds').fetchone()[0], 0)
            digest, reason = db.execute('SELECT digest, reason FROM closed_requests').fetchone()
            self.assertEqual(digest, hashlib.sha256(f'{self.scope}:{request}'.encode()).hexdigest())
            self.assertEqual(reason, 'round_expired')
        self.assertNotEqual(self.start('single')['run_id'], start['run_id'])

    def test_old_cancelled_requests_survive_upgrade(self):
        request = new_id()
        self.state.mkdir()
        with sqlite3.connect(self.state / 'rounds.sqlite3') as db:
            db.execute('CREATE TABLE cancelled (scope TEXT, request TEXT, created INTEGER, PRIMARY KEY(scope, request))')
            db.execute('INSERT INTO cancelled VALUES (?, ?, ?)', (self.scope, request, 1))
        for _ in range(2):
            self.cli('start', '--scope', self.scope, '--request', request, '--spread', 'single', error='cancelled')

    def test_clear_scrubs_draw_from_the_database(self):
        start = self.start('present')
        self.action('reveal', start)
        database = self.state / 'rounds.sqlite3'
        with sqlite3.connect(database) as db:
            draw = db.execute('SELECT result FROM rounds').fetchone()[0].encode()
        self.assertIn(draw, database.read_bytes())
        self.action('clear', start)
        self.assertNotIn(draw, database.read_bytes())

    def test_meanings_match_reveal(self):
        start = self.start('relationship')
        draw = self.action('reveal', start)
        readings = self.action('meaning', start)['meanings']
        self.assertEqual([(x['id'], x['orientation']) for x in draw['cards']],
                         [(x['id'], x['orientation']) for x in readings])
        for meaning in readings:
            single = self.cli('meaning', '--card', meaning['id'], '--orientation', meaning['orientation'])['meaning']
            self.assertEqual(meaning, single)
        self.cli('meaning', '--card', 'major-00', error='input')

    def test_failed_output_can_retry_the_same_draw(self):
        start = self.start('single')
        original = self.action('reveal', start)
        blocked = Path(self.folder.name) / 'file'
        blocked.touch()
        self.action('show', start, '--output-root', blocked, error='local_io')
        good = Path(self.folder.name) / 'delivery folder'
        self.cli('check', '--output-root', good)
        result = self.action('show', start, '--output-root', good)
        self.assertEqual(original['cards'], result['cards'])
        self.assertTrue(Path(result['board']).is_relative_to(good.resolve()))

    def test_board_without_optional_pillow(self):
        start = self.start('annual')
        self.action('reveal', start)
        result = self.action('show', start, python_flags=('-S',))
        self.assertNotIn('overview', result)
        self.assertEqual(len(BoardHTML(Path(result['board']).read_text()).images), 12)

    def test_zip_contains_same_cards_as_the_full_size_board(self):
        start = self.start('annual')
        self.action('reveal', start)
        result = self.action('show', start, '--zip-board', python_flags=('-S',))
        full = BoardHTML(Path(result['board']).read_text())
        with ZipFile(result['board_zip']) as archive:
            self.assertEqual(archive.namelist(), ['spread.html'])
            attachment = BoardHTML(archive.read('spread.html').decode('utf-8'))
        self.assertEqual([i['alt'] for i in full.images], [i['alt'] for i in attachment.images])
        self.assertEqual(attachment.external, [])
        for image, card in zip(attachment.images, result['cards']):
            raw = base64.b64decode(image['src'].split(',', 1)[1])
            self.assertEqual(raw, (ASSETS / 'upright' / f'{card["id"]}.jpg').read_bytes())

    def test_overview_write_failure_preserves_required_outputs(self):
        start = self.start('annual')
        self.action('reveal', start)
        directory = self.state / 'exports' / start['run_id']
        (directory / 'overview.png').mkdir(parents=True)
        result = self.action('show', start)
        self.assertNotIn('overview', result)
        self.assertEqual(len(BoardHTML(Path(result['board']).read_text()).images), 12)
        self.assertTrue(all(Path(path).is_file() for path in result['images']))

    def test_wrong_type_of_expired_export_does_not_block_other_runs(self):
        start = self.start('single')
        output = self.state / 'exports' / start['run_id']
        output.parent.mkdir()
        output.touch()
        with sqlite3.connect(self.state / 'rounds.sqlite3') as db:
            db.execute('UPDATE rounds SET created=1')
        self.assertEqual(self.cli('check')['status'], 'ready')
        self.assertFalse(output.exists())
        self.assertEqual(self.start('single')['status'], 'prepared')

    def test_corrupt_selected_asset_cannot_be_revealed(self):
        start = self.start('single', '--upright-only')
        with sqlite3.connect(self.state / 'rounds.sqlite3') as db:
            key = json.loads(db.execute('SELECT deck FROM rounds').fetchone()[0])[0][0]
        copy = Path(self.folder.name) / 'tarot-it'
        shutil.copytree(ROOT, copy, copy_function=os.link)
        broken = copy / f'assets/deck/original/{key}.jpg'
        broken.unlink()
        broken.write_bytes(b'invalid')
        self.action('reveal', start, runner=copy / 'scripts/tarot.py', error='assets')
        self.action('show', start, error='not_revealed')
        self.assertEqual(self.action('reveal', start)['cards'][0]['id'], key)

    def test_invalid_image_manifest_returns_structured_errors(self):
        start = self.start('single', '--upright-only')
        with sqlite3.connect(self.state / 'rounds.sqlite3') as db:
            key = json.loads(db.execute('SELECT deck FROM rounds').fetchone()[0])[0][0]
        copy = Path(self.folder.name) / 'tarot-it'
        shutil.copytree(ROOT, copy, copy_function=os.link)
        manifest_path = copy / 'assets/deck/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest_path.unlink()
        runner = copy / 'scripts/tarot.py'
        for invalid in (None, 'not-a-digest'):
            asset = manifest['cards'][key]
            if invalid is None:
                del asset['preview_sha256']
            else:
                asset['preview_sha256'] = {'upright': invalid}
            manifest_path.write_text(json.dumps(manifest))
            self.cli('check', '--full', runner=runner, error='assets')
            self.action('reveal', start, runner=runner, error='assets')
        self.action('show', start, error='not_revealed')
        self.assertEqual(self.action('reveal', start)['cards'][0]['id'], key)

    def test_celtic_layout_and_malformed_id(self):
        start = self.start('celtic-cross')
        self.cli('reveal', '--scope', self.scope, '--run', '../../out', error='input')
        self.action('reveal', start)
        path = Path(self.action('show', start)['board'])
        markup = path.read_text()
        self.assertEqual(len(re.findall(r'class="crossing"', markup)), 1)
        self.assertIn('max-width:720px', markup)


if __name__ == '__main__':
    unittest.main()
