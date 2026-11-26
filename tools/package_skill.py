"""Build and checksum a standalone Tarot-it installation ZIP."""

import hashlib
import json
from pathlib import Path
from subprocess import run
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'tarot-it'
VERSION = '1.0.0-rc.3'


def main():
    with TemporaryDirectory() as state:
        run([sys.executable, str(SKILL / 'scripts/tarot.py'), '--state-dir', state, 'check', '--full'], check=True)
    manifest = json.loads((SKILL / 'assets/deck/manifest.json').read_text(encoding='utf-8'))['cards']
    files = ['SKILL.md', 'scripts/tarot.py', 'scripts/board.py', 'references/spreads.json',
             'references/hosts.md', 'references/credits.md', 'assets/deck/manifest.json']
    for key in manifest:
        files.append(f'references/cards/{key}.json')
        files.extend(f'assets/deck/{kind}/{key}.jpg' for kind in ('original', 'upright', 'reversed'))
    output = ROOT / 'dist' / f'tarot-it-{VERSION}.zip'
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, 'w') as archive:
        for relative in sorted(files):
            member = ZipInfo(f'tarot-it/{relative}')
            member.external_attr = 0o100644 << 16
            archive.writestr(member, (SKILL / relative).read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=3)
    with output.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest() if sys.version_info >= (3, 11) else hashlib.sha256(stream.read()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='utf-8')
    print(f'{output} ({len(files)} files)\nSHA-256 {digest}')


if __name__ == '__main__':
    main()
