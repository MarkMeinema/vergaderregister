#!/usr/bin/env python3
"""Bouwt de browserversie (zonder server) in _site/, voor GitHub Pages of elke andere statische webhost.

  python3 bouw_web.py [doelmap]

De browserversie draait server.py zelf in de browser met Pyodide (zie web/browser.js). Wijzigingen blijven
per browser bewaard in IndexedDB; de demodata in data/ wordt bij een eerste bezoek ingeladen.
"""
import hashlib
import os
import shutil
import sys
import zipfile

BASIS = os.path.dirname(os.path.abspath(__file__))


def zip_map(zf, map_, prefix=''):
    for wortel, mappen, bestanden in os.walk(map_):
        mappen[:] = [m for m in mappen if m not in ('.cache', '__pycache__')]
        for naam in bestanden:
            if naam.startswith('.'):
                continue
            pad = os.path.join(wortel, naam)
            zf.write(pad, os.path.join(prefix, os.path.relpath(pad, map_)))


def main():
    doel = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASIS, '_site'))
    shutil.rmtree(doel, ignore_errors=True)
    shutil.copytree(os.path.join(BASIS, 'static'), doel)
    shutil.copy(os.path.join(BASIS, 'web', 'browser.js'), doel)

    index = os.path.join(doel, 'index.html')
    with open(index, encoding='utf-8') as f:
        html = f.read()
    html = html.replace('<script src="app.js"></script>', '<script src="browser.js"></script>\n<script src="app.js"></script>')
    with open(index, 'w', encoding='utf-8') as f:
        f.write(html)

    with zipfile.ZipFile(os.path.join(doel, 'app.zip'), 'w', zipfile.ZIP_DEFLATED) as zf:
        for naam in ('server.py', 'opslag.py', 'schema.sql'):
            zf.write(os.path.join(BASIS, naam), naam)
    with zipfile.ZipFile(os.path.join(doel, 'data.zip'), 'w', zipfile.ZIP_DEFLATED) as zf:
        zip_map(zf, os.path.join(BASIS, 'data'))
    # Nieuwe demodata of code: de browser zet zijn opgeslagen gegevens dan terug (zie web/browser.js).
    with open(os.path.join(doel, 'versie.txt'), 'w') as f:
        h = hashlib.sha1()
        for naam in ('app.zip', 'data.zip'):
            with open(os.path.join(doel, naam), 'rb') as z:
                h.update(z.read())
        f.write(h.hexdigest()[:12])
    open(os.path.join(doel, '.nojekyll'), 'w').close()
    print(f'Browserversie gebouwd in {doel}')


if __name__ == '__main__':
    main()
