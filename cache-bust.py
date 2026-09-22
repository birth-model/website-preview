#!/usr/bin/env python3
"""Stamp a content hash onto every local asset URL in the site's HTML.

Run this before each deploy:

    python3 cache-bust.py

Every reference to nav.css, an image, etc. becomes `nav.css?v=<hash>`, where the
hash is derived from the file's bytes. Change a file and its URL changes with it,
so browsers fetch the new version immediately. Leave a file alone and its URL
stays put, so the cached copy keeps being used.

The script is idempotent: an existing ?v=... is replaced, not appended to, so it
is safe to run as often as you like. Pass --check to verify without writing
(exit code 1 if anything is stale), or --strip to remove all stamps.
"""
import glob
import hashlib
import pathlib
import re
import sys

# asset types worth fingerprinting; HTML is deliberately excluded because page
# URLs must stay clean and are handled by cache headers instead
ASSET_EXT = ('css', 'js', 'png', 'jpg', 'jpeg', 'webp', 'avif', 'svg', 'gif', 'ico', 'woff', 'woff2')


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def main() -> int:
    check = '--check' in sys.argv
    strip = '--strip' in sys.argv

    hashes = {}
    for ext in ASSET_EXT:
        for a in glob.glob(f'*.{ext}'):
            hashes[a] = digest(pathlib.Path(a))
    if not hashes:
        print('no local assets found')
        return 0

    # match src="file.png", href="file.css", optionally already stamped
    names = '|'.join(re.escape(n) for n in sorted(hashes, key=len, reverse=True))
    pattern = re.compile(r'((?:src|href)=")(' + names + r')(\?v=[0-9a-z]+)?(")')

    changed, stale = [], []
    for f in sorted(glob.glob('*.html')):
        p = pathlib.Path(f)
        text = original = p.read_text()

        def sub(m):
            attr, name, _old, close = m.groups()
            if strip:
                return f'{attr}{name}{close}'
            return f'{attr}{name}?v={hashes[name]}{close}'

        text = pattern.sub(sub, text)
        if text != original:
            if check:
                stale.append(f)
            else:
                p.write_text(text)
                changed.append(f)

    if check:
        if stale:
            print(f'STALE: {len(stale)} file(s) need re-stamping: {", ".join(stale[:5])}'
                  + (' ...' if len(stale) > 5 else ''))
            return 1
        print(f'up to date: {len(hashes)} assets, all references stamped correctly')
        return 0

    verb = 'stripped' if strip else 'stamped'
    print(f'{verb} {len(hashes)} assets across {len(changed)} HTML file(s)')
    for name in sorted(hashes):
        print(f'  {name:32s} ?v={hashes[name]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
