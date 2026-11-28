#!/usr/bin/env python3
"""Build small concept EPUB editions from the validated local corpus (stdlib only)."""
import html
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
def read(name):
    return json.loads((ROOT / name).read_text())
def esc(value):
    return html.escape(str(value), quote=True)

library = read('data/library.json')
works = {w['id']: w for w in library['works']}
is_talmud = (ROOT / 'data/inventory.json').exists()
series, deferred = [], []
if is_talmud:
    inventory = read('data/inventory.json')
    for corpus in inventory['corpora']:
        for tractate in corpus['tractates']:
            if tractate.get('units'):
                series.append((corpus['id'] + '-' + tractate['id'], corpus['title'] + ' · ' + tractate['title'], [u['id'] for u in tractate['units']]))
            else:
                deferred.append({'id': corpus['id'] + '-' + tractate['id'], 'title': corpus['title'] + ' · ' + tractate['title'], 'status': 'bronregister-nodig', 'gemara': tractate.get('gemara')})
    deferred.append({'id': 'mishnah', 'title': 'Zelfstandige Misjna', 'status': 'hoofdstukindeling-nodig', 'note': 'Ingebedde Misjna niet dubbel tellen.'})
else:
    corpus = read('data/corpus.json')
    for volume in ['I', 'II', 'III']:
        prefix = 'Zohar ' + volume + ' '
        series.append(('zohar-' + volume.lower(), 'Zohar ' + volume, [f['reference'][len(prefix):] for f in corpus['folios'] if f['reference'].startswith(prefix)]))
    deferred = [{'id': x, 'title': title, 'status': 'bronregister-en-concordantie-nodig'} for x, title in [('chadash', 'Zohar Chadasj'), ('tikkunim', 'Tikkoenei Zohar'), ('addenda', 'Afzonderlijke addenda buiten het hoofdregister')]]

out = ROOT / 'uitgaven'
out.mkdir(exist_ok=True)
editions = []
def xhtml(title, body):
    return '<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="nl" xml:lang="nl"><head><title>' + esc(title) + '</title></head><body>' + body + '</body></html>'

def build_epub(entry, chapters, work):
    title = entry['title']
    intro = '<h1>' + esc(title) + '</h1><p>Volledige conceptvertaling van het aangegeven bronbereik. Onafhankelijke inhoudelijke eindcontrole staat open.</p><p>Bronzijden zijn geen gedrukte boekpagina’s. Discussies en zinnen kunnen doorlopen in een volgend deel.</p><p>' + esc(work.get('license', 'CC BY-SA 4.0')) + '</p><p><a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a> · Nederlandse conceptvertaling: ' + esc(library['title']) + ', 2026. Grondtekst: Hebreeuwse Wikisource-bijdragers; vaste revisies en auteursgeschiedenis bij de bronnen.</p>'
    if not is_talmud:
        dating = read('data/dating.json')
        intro += '<h2>Geschatte datering</h2><p>' + esc(dating['label']) + '. ' + esc(dating['scope']) + '</p><p>Traditionele toeschrijving: ' + esc(dating['traditionalAttribution']) + '. ' + esc(dating['note']) + '</p>'
        intro += '<p>' + ' · '.join('<a href="' + esc(source['url']) + '">' + esc(source['title']) + '</a>' for source in dating['sources']) + '</p>'
    files = {'intro.xhtml': xhtml(title, intro)}
    links = ['<li><a href="intro.xhtml">Verantwoording</a></li>']
    for n, chapter in enumerate(chapters):
        body = '<h1>' + esc(chapter['title']) + '</h1>'
        for passage in chapter['passages']:
            body += '<section id="p-' + esc(passage['id']) + '"><h2>' + esc(passage.get('locator', passage.get('reference', passage['id']))) + '</h2><p>' + esc(passage['nl']) + '</p><p dir="rtl" lang="he">' + esc(passage['original']) + '</p>'
            notes = [note['text'] if isinstance(note, dict) else note for note in passage.get('notes', [])]
            notes += ['Onzekere lezing: ' + note for note in passage.get('uncertainties', [])]
            body += ''.join('<p>' + esc(note) + '</p>' for note in notes)
            if is_talmud:
                src = sources[passage['sourceId']]
            else:
                src = passage['source']
            # Preserve the full recorded attribution/revision metadata, including source history.
            body += '<details><summary>Bronverantwoording</summary><pre>' + esc(json.dumps(src, ensure_ascii=False, indent=2)) + '</pre></details></section>'
        name = 'chapter-' + str(n + 1) + '.xhtml'
        files[name] = xhtml(chapter['title'], body)
        links.append('<li><a href="' + name + '">' + esc(chapter['title']) + '</a></li>')
    files['nav.xhtml'] = xhtml('Inhoud', '<nav epub:type="toc"><h1>Inhoud</h1><ol>' + ''.join(links) + '</ol></nav>')
    manifest = ''.join('<item id="f' + str(n) + '" href="' + name + '" media-type="application/xhtml+xml"' + (' properties="nav"' if name == 'nav.xhtml' else '') + '/>' for n, name in enumerate(files))
    spine = ''.join('<itemref idref="f' + str(n) + '"/>' for n, name in enumerate(files) if name != 'nav.xhtml')
    opf = '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="uid">urn:didache:' + esc(entry['id']) + '</dc:identifier><dc:title>' + esc(title) + '</dc:title><dc:language>nl</dc:language><dc:creator>' + esc(library['title']) + '</dc:creator><dc:rights>CC BY-SA 4.0; ongeredigeerde conceptvertaling</dc:rights><meta property="dcterms:modified">2026-11-28T00:00:00Z</meta></metadata><manifest>' + manifest + '</manifest><spine>' + spine + '</spine></package>'
    with zipfile.ZipFile(out / entry['epub'], 'w') as archive:
        archive.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        archive.writestr('META-INF/container.xml', '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        archive.writestr('EPUB/package.opf', opf)
        for name, data in files.items():
            archive.writestr('EPUB/' + name, data, compress_type=zipfile.ZIP_DEFLATED)

if is_talmud:
    raw = read('data/sources.json')
    # Source registry schema is explicit; unsupported changes should fail loudly.
    sources = {s['id']: s for s in raw['sources']}
for work_id, title, units in series:
    work = works.get(work_id, {})
    chapters = {c['id']: c for c in work.get('chapters', [])}
    for offset in range(0, len(units), 20):
        block = units[offset:offset + 20]
        complete = [u for u in block if u in chapters and (is_talmud or chapters[u].get('completeFolio') is True)]
        number = offset // 20 + 1
        eid = work_id + '-deel-' + str(number).zfill(2)
        ready = len(complete) == len(block)
        entry = {'id': eid, 'title': title + ' · deel ' + str(number) + ' · ' + block[0] + '–' + block[-1], 'workId': work_id, 'units': block, 'completeUnits': complete, 'status': 'volledig-concept' if ready else ('in-vertaling' if complete else 'gepland'), 'independentReview': 'open', 'epub': eid + '.epub' if ready else None}
        editions.append(entry)
        if ready:
            build_epub(entry, [chapters[u] for u in block], work)
manifest = {'version': 1, 'maxSourceSidesPerEdition': 20, 'policy': 'Vaste bronvolgorde; geen grens over tractaten of hoofdvolumes. Alleen volledige conceptdelen worden als EPUB aangeboden. Bronlacunes blijven open.', 'editions': editions, 'deferred': deferred}
(out / 'index.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
lines = ['# Kleine uitgaven', '', 'Elk deel omvat maximaal twintig bronzijden in de vaste bronvolgorde. Dit is geen telling van gedrukte boekpagina’s. De indeling is praktisch; een zin of discussie kan over een deelgrens doorlopen. Bronverwijzingen, grondtekst en noten blijven behouden.', '', 'Alle beschikbare EPUBs zijn conceptvertalingen; onafhankelijke inhoudelijke controle staat open. Onvolledige delen worden pas als EPUB gebouwd zodra alle bronzijden compleet zijn.', '', '| Deel | Volledige bronzijden | Status / bestand |', '| --- | ---: | --- |']
for e in editions:
    link = '[' + e['status'] + '](' + e['epub'] + ')' if e['epub'] else e['status']
    lines.append('| ' + e['title'] + ' | ' + str(len(e['completeUnits'])) + '/' + str(len(e['units'])) + ' | ' + link + ' |')
lines += ['', 'Overige tractaten of aanvullende werken staan in `index.json` onder `deferred`: hun bronregister of concordantie moet eerst worden vastgelegd. Er worden daarvoor geen fictieve grenzen of voltooiingspercentages ingevuld.', '', 'Na iedere gevalideerde vertaalronde: `python3 scripts/build-editions.py`. Dezelfde deelcodes en bronbereiken blijven behouden.']
(out / 'README.md').write_text('\n'.join(lines) + '\n')
print(json.dumps({'planned': len(editions), 'epubs': sum(bool(e['epub']) for e in editions)}, ensure_ascii=False))
