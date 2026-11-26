"""Build the Pam-A deck from a saved Wikimedia imageinfo API response."""

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote, urlsplit

from PIL import Image, ImageOps


DECK = Path(__file__).resolve().parents[1] / 'tarot-it' / 'assets' / 'deck'
SUITS = {'Cups': 'cups', 'Pents': 'pentacles', 'Swords': 'swords', 'Wands': 'wands'}
RANKS = ['ace', *map(str, range(2, 11)), 'page', 'knight', 'queen', 'king']


def card_id(title):
    major = re.fullmatch(r'File:RWS Tarot (\d\d) [\w -]+\.jpg', title)
    if major:
        return f'major-{major[1]}'
    suit, ordinal = re.fullmatch(r'File:(Cups|Pents|Swords|Wands)(\d\d)\.jpg', title).groups()
    return f'{SUITS[suit]}-{RANKS[int(ordinal) - 1]}'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def download(url):
    return subprocess.check_output(['curl', '--fail', '--silent', '--show-error', '--proto', '=https',
                                    '--retry', '2', '--retry-delay', '3', '--retry-max-time', '18',
                                    '--max-time', '20', '--max-filesize', '5000000', url])


def prepare(page):
    title = page['title']
    key = card_id(title)
    info = page['imageinfo'][0]
    meta = {name: value['value'] for name, value in info['extmetadata'].items()}
    if (meta['LicenseShortName'] != 'Public domain' or meta['Copyrighted'] != 'False'
            or 'Pamela Colman Smith' not in meta['Artist'] or 'Pam-A' not in meta['ImageDescription']
            or 'muzendo.jp/blog/' not in meta['Credit']):
        raise ValueError(f'Review image rights and provenance: {title}')
    source = urlsplit(info['url'])
    if source.scheme != 'https' or source.netloc != 'upload.wikimedia.org' or not source.path.startswith('/wikipedia/commons/'):
        raise ValueError(f'Unexpected image URL: {title}')
    url = source._replace(query='', fragment='').geturl()
    original = DECK / 'original' / f'{key}.jpg'
    data = original.read_bytes() if original.exists() else download(url)
    if hashlib.sha1(data).hexdigest() != info['sha1']:
        raise ValueError(f'Wikimedia binary revision mismatch: {title}')
    with Image.open(BytesIO(data)) as image:
        if (image.format != 'JPEG' or image.size != (info['width'], info['height'])
                or image.width < 1000 or image.height < 1800 or image.height <= image.width
                or image.getexif().get(274, 1) != 1):
            raise ValueError(f'Unexpected original image: {title}')
        width, height = image.size
        preview = ImageOps.contain(image.convert('RGB'), (900, 900), Image.Resampling.LANCZOS)
        for direction, frame in [('upright', preview), ('reversed', preview.transpose(Image.Transpose.ROTATE_180))]:
            frame.save(DECK / direction / f'{key}.jpg', quality=86, optimize=True)
    original.write_bytes(data)
    revision = page['revisions'][0]['revid']
    file_page = 'https://commons.wikimedia.org/wiki/' + quote(title.replace(' ', '_'), safe=':')
    return key, {
        'artist': 'Pamela Colman Smith', 'edition': 'Rider–Waite–Smith, Pam-A',
        'source_credit': 'https://muzendo.jp/blog/', 'rights': 'Public domain per Wikimedia Commons file record',
        'file_page': file_page, 'file_revision': revision,
        'revision_url': f'https://commons.wikimedia.org/w/index.php?oldid={revision}',
        'original_url': url, 'upload_timestamp': info['timestamp'], 'uploader': info['user'],
        'width': width, 'height': height, 'source_sha1': info['sha1'],
        'sha256': sha256(data), 'preview_sha256': {
            direction: sha256((DECK / direction / f'{key}.jpg').read_bytes())
            for direction in ('upright', 'reversed')
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('imageinfo_json', type=Path)
    paths = parser.parse_args()
    pages = list(json.loads(paths.imageinfo_json.read_text())['query']['pages'].values())
    expected = {f'major-{n:02}' for n in range(22)} | {f'{suit}-{rank}' for suit in SUITS.values() for rank in RANKS}
    if len(pages) != 78 or {card_id(page['title']) for page in pages} != expected:
        raise ValueError('Expected all 78 distinct Pam-A cards')
    for folder in ('original', 'upright', 'reversed'):
        (DECK / folder).mkdir(parents=True, exist_ok=True)
    cards, failures = {}, []
    for page in pages:
        try:
            key, record = prepare(page)
            cards[key] = record
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            failures.append(f'{page["title"]}: {error}')
    if failures:
        raise SystemExit('\n'.join(failures))
    if len({entry['sha256'] for entry in cards.values()}) != 78:
        raise ValueError('Duplicate originals')
    manifest = {'schema': 1, 'preview_transform': 'JPEG fit within 900px, reversed rotated 180°', 'cards': cards}
    (DECK / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {len(cards)} checksum-verified originals and two preview sets.')


if __name__ == '__main__':
    main()
