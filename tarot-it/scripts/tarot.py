#!/usr/bin/env python3
"""Run a local Tarot-it draw and render its fixed result."""

import argparse
from base64 import b64encode
from contextlib import closing, contextmanager
from datetime import date
import hashlib
from io import BytesIO
import json
from pathlib import Path
from random import SystemRandom
import re
import shutil
import sqlite3
import sys
from tempfile import NamedTemporaryFile
import time
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from board import render_html, render_overview


ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / 'assets' / 'deck'
REFERENCES = ROOT / 'references'
TTL = 24 * 60 * 60
SUITS = ('wands', 'cups', 'swords', 'pentacles')
RANKS = ('ace', *map(str, range(2, 11)), 'page', 'knight', 'queen', 'king')
MAJOR_IDS = {f'major-{n:02}' for n in range(22)}
MINOR_IDS = {f'{suit}-{rank}' for suit in SUITS for rank in RANKS}
CARD_IDS = MAJOR_IDS | MINOR_IDS
DECK_IDS = {'full': CARD_IDS, 'major': MAJOR_IDS, 'minor': MINOR_IDS}
IMAGE_KINDS = ('original', 'upright', 'reversed')


class TarotError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def load_assets():
    try:
        contents = [DECK / 'manifest.json', REFERENCES / 'spreads.json']
        contents.extend(REFERENCES / 'cards' / f'{key}.json' for key in sorted(CARD_IDS))
        raw = [path.read_bytes() for path in contents]
        manifest, spreads, *records = (json.loads(data) for data in raw)
        cards = {record['id']: record for record in records}
        expected = dict(zip(('single', 'present', 'timeline', 'relationship', 'dilemma', 'horseshoe', 'celtic-cross', 'annual'),
                            (1, 3, 3, 5, 5, 7, 10, 12)))
        if (not isinstance(spreads, dict) or manifest['schema'] != 1 or not isinstance(manifest['cards'], dict)
                or set(manifest['cards']) != CARD_IDS or set(cards) != CARD_IDS
                or {key: len(spread['positions']) for key, spread in spreads.items()} != expected):
            raise ValueError('牌面、牌义或牌阵不完整。')
        for key, asset in manifest['cards'].items():
            for kind in IMAGE_KINDS:
                image_digest(asset, key, kind)
        for record in records:
            if not (record['name_zh'] and record['name_en'] and record['upright']['meaning'] and record['reversed']['meaning']):
                raise ValueError(f"牌义缺项 {record['id']}")
        version = hashlib.sha256(b'\0'.join(raw)).hexdigest()
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise TarotError('assets', f'内置素材无法使用。{error}') from error
    return manifest['cards'], spreads, cards, version


def asset_path(key, kind):
    return DECK / kind / f'{key}.jpg'


def image_digest(asset, key, kind):
    try:
        expected = asset['sha256'] if kind == 'original' else asset['preview_sha256'][kind]
        if re.fullmatch(r'[0-9a-f]{64}', expected):
            return expected
    except (KeyError, TypeError):
        pass
    raise TarotError('assets', f'牌图清单的校验值缺失或无效 {key} ({kind})。')


def asset_bytes(manifest, key, kind):
    expected = image_digest(manifest[key], key, kind)
    try:
        data = asset_path(key, kind).read_bytes()
    except OSError as error:
        raise TarotError('assets', f'牌图缺失 {key} ({kind})。') from error
    if hashlib.sha256(data).hexdigest() != expected:
        raise TarotError('assets', f'牌图校验失败 {key} ({kind})。')
    return data


def check_assets(manifest, full=False):
    for key in sorted(manifest):
        for kind in IMAGE_KINDS:
            if not asset_path(key, kind).is_file():
                raise TarotError('assets', f'牌图缺失 {key} ({kind})。')
            if full:
                asset_bytes(manifest, key, kind)


def identifier(value):
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError('需要规范的小写 UUIDv4。') from error
    if str(parsed) != value or parsed.version != 4:
        raise argparse.ArgumentTypeError('需要规范的小写 UUIDv4。')
    return value


def remove_private_exports(state, run_id):
    identifier(run_id)
    directory = state / 'exports' / run_id
    try:
        if directory.is_dir() and not directory.is_symlink():
            shutil.rmtree(directory)
        else:
            directory.unlink(missing_ok=True)
    except FileNotFoundError:
        pass


def clean_exports(db, state, run_id):
    try:
        remove_private_exports(state, run_id)
    except OSError:
        db.execute('INSERT OR IGNORE INTO pending_cleanup VALUES (?)', (run_id,))
        return False
    db.execute('DELETE FROM pending_cleanup WHERE id=?', (run_id,))
    return True


def request_digest(scope, request):
    return hashlib.sha256(f'{scope}:{request}'.encode('ascii')).hexdigest()


@contextmanager
def transaction(state):
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = state / 'rounds.sqlite3'
    database.touch(mode=0o600, exist_ok=True)
    with closing(sqlite3.connect(database, timeout=15, isolation_level=None)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA secure_delete=ON')
        db.execute('''CREATE TABLE IF NOT EXISTS rounds (
            id TEXT PRIMARY KEY, scope TEXT NOT NULL, request TEXT NOT NULL,
            version TEXT NOT NULL, created INTEGER NOT NULL, parameters TEXT NOT NULL, positions TEXT NOT NULL,
            deck TEXT NOT NULL, cut INTEGER NOT NULL DEFAULT 0, selected TEXT, result TEXT,
            UNIQUE (scope, request))''')
        db.execute('''CREATE TABLE IF NOT EXISTS closed_requests (
            digest TEXT PRIMARY KEY, reason TEXT NOT NULL)''')
        db.execute('CREATE TABLE IF NOT EXISTS pending_cleanup (id TEXT PRIMARY KEY)')
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cancelled'").fetchone():
            db.executemany('INSERT OR IGNORE INTO closed_requests VALUES (?, ?)',
                           ((request_digest(row['scope'], row['request']), 'cancelled')
                            for row in db.execute('SELECT scope, request FROM cancelled')))
            db.execute('DROP TABLE cancelled')
        expiry = int(time.time()) - TTL
        expired = db.execute('SELECT id, scope, request FROM rounds WHERE created <= ?', (expiry,)).fetchall()
        db.executemany('INSERT OR IGNORE INTO closed_requests VALUES (?, ?)',
                       ((request_digest(row['scope'], row['request']), 'round_expired') for row in expired))
        db.executemany('INSERT OR IGNORE INTO pending_cleanup VALUES (?)', ((row['id'],) for row in expired))
        db.execute('DELETE FROM rounds WHERE created <= ?', (expiry,))
        for row in db.execute('SELECT id FROM pending_cleanup').fetchall():
            clean_exports(db, state, row['id'])
        db.commit()
        db.execute('BEGIN IMMEDIATE')
        with db:
            yield db


def deck_order(rng, upright_only, deck):
    cards = sorted(DECK_IDS[deck])
    rng.shuffle(cards)
    return [(key, 'upright' if upright_only or not rng.getrandbits(1) else 'reversed') for key in cards]


def parameters_for(args, spreads):
    if args.spread not in spreads:
        raise TarotError('spread', '请从支持的八套牌阵中选择。')
    if args.year is not None and (args.spread != 'annual' or not 1 <= args.year <= 9999):
        raise TarotError('year', '只在年度牌阵使用 1 至 9999 的年份。')
    return {'spread': args.spread, 'upright_only': args.upright_only, 'year': args.year, 'deck': args.deck}


def spread_positions(parameters, spreads, created):
    spread = spreads[parameters['spread']]
    if parameters['spread'] != 'annual':
        return spread['positions']
    today = date.fromtimestamp(created)
    offset = (parameters['year'] * 12) if parameters['year'] is not None else today.year * 12 + today.month
    return [f'{year:04} 年 {month + 1} 月' for year, month in (divmod(offset + i, 12) for i in range(12))]


def snapshot(row, spreads, cards):
    parameters = json.loads(row['parameters'])
    deck = parameters.get('deck', 'full')
    names = json.loads(row['positions'])
    response = {'run_id': row['id'], 'status': 'prepared', 'asset_version': row['version'],
                'spread': parameters['spread'], 'spread_name': spreads[parameters['spread']]['name'],
                'deck': deck, 'deck_size': len(DECK_IDS[deck]), 'upright_only': parameters['upright_only'],
                'count': len(names), 'positions': names}
    if row['result'] is not None:
        response['status'] = 'revealed'
        response['cards'] = [dict(position=i, label=name, id=key, orientation=direction,
                                  name_zh=cards[key]['name_zh'], name_en=cards[key]['name_en'])
                             for i, (name, (key, direction)) in enumerate(zip(names, json.loads(row['result'])), 1)]
    return response


def find_round(db, args, version):
    row = db.execute('SELECT * FROM rounds WHERE scope=? AND id=?', (args.scope, args.run)).fetchone()
    if row is None:
        raise TarotError('round_missing', '本聊天的这轮牌已过期、已清除或不存在。')
    if row['version'] != version and args.command != 'clear':
        raise TarotError('asset_version', '本轮使用了另一版素材。请保留原结果，或明确开始新一轮。')
    return row


def start(db, args, manifest, spreads, cards, version):
    parameters = parameters_for(args, spreads)
    closed = db.execute('SELECT reason FROM closed_requests WHERE digest=?',
                        (request_digest(args.scope, args.request),)).fetchone()
    if closed:
        status = '过期' if closed['reason'] == 'round_expired' else '取消'
        raise TarotError(closed['reason'], f'这次请求已{status}。明确开启新的一轮时使用新请求。')
    row = db.execute('SELECT * FROM rounds WHERE scope=? AND request=?', (args.scope, args.request)).fetchone()
    if row is None:
        check_assets(manifest)
        now = int(time.time())
        db.execute('INSERT INTO rounds (id,scope,request,version,created,parameters,positions,deck) VALUES (?,?,?,?,?,?,?,?)',
                   (str(uuid4()), args.scope, args.request, version, now, json.dumps(parameters),
                    json.dumps(spread_positions(parameters, spreads, now)),
                    json.dumps(deck_order(SystemRandom(), args.upright_only, args.deck))))
        row = db.execute('SELECT * FROM rounds WHERE scope=? AND request=?', (args.scope, args.request)).fetchone()
    saved_parameters = json.loads(row['parameters'])
    saved_parameters.setdefault('deck', 'full')
    if saved_parameters != parameters:
        raise TarotError('request_conflict', '这次请求已绑定其他牌阵、牌组或方向设置。')
    if row['version'] != version:
        raise TarotError('asset_version', '本轮素材版本已变化。')
    response = snapshot(row, spreads, cards)
    response.pop('cards', None)
    return response


def select(db, args, row, response):
    if row['result'] is not None:
        raise TarotError('already_revealed', '这轮已翻牌，可重新展示同一结果。')
    if args.cut is None and args.positions is None:
        raise TarotError('selection', '请提供切点或所选位置。')
    deck_size = response['deck_size']
    if args.cut is not None and not 1 <= args.cut < deck_size:
        raise TarotError('cut', f'切点必须在 1 至 {deck_size - 1} 之间。')
    if args.positions is not None:
        if len(set(args.positions)) != response['count'] or len(args.positions) != response['count']:
            raise TarotError('positions', f'请选择 {response["count"]} 个各不相同的位置。')
        if any(not 1 <= position <= deck_size for position in args.positions):
            raise TarotError('positions', f'所选位置须在 1 至 {deck_size} 之间。')
    cut = row['cut'] if args.cut is None else args.cut
    selected = row['selected'] if args.positions is None else json.dumps(args.positions)
    db.execute('UPDATE rounds SET cut=?, selected=? WHERE id=?', (cut, selected, row['id']))
    return dict(response, cut=cut, selection=json.loads(selected) if selected else None)


def reveal(db, row, response, manifest, spreads, cards):
    if row['result'] is None:
        order = json.loads(row['deck'])
        cut = row['cut']
        order = order[cut:] + order[:cut]
        selected = json.loads(row['selected']) if row['selected'] else range(1, response['count'] + 1)
        result = [order[index - 1] for index in selected]
        for key, direction in result:
            asset_bytes(manifest, key, 'original')
            asset_bytes(manifest, key, direction)
        db.execute('UPDATE rounds SET result=? WHERE id=?', (json.dumps(result), row['id']))
        row = db.execute('SELECT * FROM rounds WHERE id=?', (row['id'],)).fetchone()
    return snapshot(row, spreads, cards)


def atomic_write(path, data):
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def show(args, response, manifest):
    target = args.output_root.resolve() if args.output_root else args.state_dir / 'exports'
    target = target / response['run_id']
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    board = target / 'spread.html'
    images, originals = [], []
    for card in response['cards']:
        original = asset_bytes(manifest, card['id'], 'original')
        preview = asset_bytes(manifest, card['id'], card['orientation'])
        path = target / f'{card["position"]:02}-{card["id"]}-{card["orientation"]}.jpg'
        atomic_write(path, preview)
        images.append(path)
        originals.append(b64encode(original).decode('ascii'))
    board_html = render_html(response, originals).encode('utf-8')
    atomic_write(board, board_html)
    if args.zip_board:
        previews = [b64encode(asset_bytes(manifest, card['id'], 'upright')).decode('ascii')
                    for card in response['cards']]
        compact_html = render_html(response, previews, full_size=False).encode('utf-8')
        buffer = BytesIO()
        with ZipFile(buffer, 'w', compression=ZIP_DEFLATED, compresslevel=3) as archive:
            archive.writestr('spread.html', compact_html)
        board_zip = target / 'spread.zip'
        atomic_write(board_zip, buffer.getvalue())
        response['board_zip'] = str(board_zip)
    try:
        overview = render_overview(response, images)
        if overview is not None:
            overview_path = target / 'overview.png'
            atomic_write(overview_path, overview)
            response['overview'] = str(overview_path)
    except OSError:
        response['overview_status'] = 'unavailable'
    return dict(response, board=str(board), images=list(map(str, images)))


def meaning(record, direction):
    return {key: record[key] for key in ('id', 'name_zh', 'name_en', 'imagery', 'sources')} | {
        'orientation': direction, **record[direction]}


class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        raise TarotError('input', message)


def parse_args():
    parser = JsonParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=Path('.tarot-it'))
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check')
    check.add_argument('--full', action='store_true')
    check.add_argument('--output-root', type=Path)
    commands.add_parser('spreads')
    new = commands.add_parser('start')
    new.add_argument('--scope', required=True, type=identifier)
    new.add_argument('--request', required=True, type=identifier)
    new.add_argument('--spread', default='present')
    new.add_argument('--deck', choices=tuple(DECK_IDS), default='full')
    new.add_argument('--upright-only', action='store_true')
    new.add_argument('--year', type=int)
    for name in ('select', 'reveal', 'show', 'clear'):
        command = commands.add_parser(name)
        command.add_argument('--scope', required=True, type=identifier)
        command.add_argument('--run', required=True, type=identifier)
        if name == 'select':
            command.add_argument('--cut', type=int)
            command.add_argument('--positions', type=int, nargs='+')
        if name == 'show':
            command.add_argument('--output-root', type=Path)
            command.add_argument('--zip-board', action='store_true')
    lookup = commands.add_parser('meaning')
    source = lookup.add_mutually_exclusive_group(required=True)
    source.add_argument('--run', type=identifier)
    source.add_argument('--card', choices=sorted(CARD_IDS))
    lookup.add_argument('--scope', type=identifier)
    lookup.add_argument('--orientation', choices=('upright', 'reversed'))
    args = parser.parse_args()
    if args.command == 'meaning' and ((args.run and (not args.scope or args.orientation))
                                      or (args.card and (not args.orientation or args.scope))):
        parser.error('查轮次使用 --scope 和 --run，查单牌使用 --card 和 --orientation。')
    args.state_dir = args.state_dir.resolve()
    return args


def run(args):
    if args.command == 'clear':
        with transaction(args.state_dir) as db:
            row = find_round(db, args, None)
            removed = clean_exports(db, args.state_dir, row['id'])
            db.execute('INSERT OR IGNORE INTO closed_requests VALUES (?, ?)',
                       (request_digest(row['scope'], row['request']), 'cancelled'))
            db.execute('DELETE FROM rounds WHERE id=?', (row['id'],))
            return {'status': 'cleared', 'run_id': row['id'], 'cleanup_pending': not removed}
    manifest, spreads, cards, version = load_assets()
    if args.command == 'spreads' or (args.command == 'meaning' and args.card):
        if (args.state_dir / 'rounds.sqlite3').is_file():
            with transaction(args.state_dir):
                pass
        if args.command == 'spreads':
            return {'spreads': spreads, 'asset_version': version}
        return {'meaning': meaning(cards[args.card], args.orientation)}
    with transaction(args.state_dir) as db:
        if args.command == 'check':
            check_assets(manifest, args.full)
            if args.output_root:
                args.output_root.mkdir(parents=True, exist_ok=True)
                with NamedTemporaryFile(dir=args.output_root):
                    pass
            return {'status': 'ready', 'cards': len(cards), 'spreads': len(spreads), 'asset_version': version}
        if args.command == 'start':
            return start(db, args, manifest, spreads, cards, version)
        row = find_round(db, args, version)
        response = snapshot(row, spreads, cards)
        if args.command == 'select':
            return select(db, args, row, response)
        if args.command == 'reveal':
            return reveal(db, row, response, manifest, spreads, cards)
        if row['result'] is None:
            raise TarotError('not_revealed', '这轮还没翻牌。')
        if args.command == 'show':
            return show(args, response, manifest)
        return dict(response, meanings=[meaning(cards[card['id']], card['orientation']) for card in response['cards']])


def main():
    try:
        data = {'ok': True, **run(parse_args())}
    except TarotError as error:
        data = {'ok': False, 'error': {'code': error.code, 'message': str(error)}}
    except (OSError, sqlite3.Error) as error:
        data = {'ok': False, 'error': {'code': 'local_io', 'message': str(error)}}
    print(json.dumps(data, ensure_ascii=False))
    return 0 if data['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
