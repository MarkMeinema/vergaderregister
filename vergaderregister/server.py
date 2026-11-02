#!/usr/bin/env python3
"""Vergaderregister — proof of concept.

Lokale webserver zonder externe afhankelijkheden: Python-standaardbibliotheek + SQLite (met FTS5).
Alle gegevens staan als Markdown-bestanden met YAML-frontmatter in data/ (zie opslag.py); bijlagen in
data/📎 Stukken/bestanden/. SQLite in data/.cache/ is alleen een zoekindex en mag altijd weg.

Starten:  python3 server.py   →  http://127.0.0.1:8765
"""
import datetime as dt
import html
import json
import mimetypes
import os
import re
import sqlite3
import sys
import threading
import urllib.parse
import uuid
import zipfile
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import opslag

BASIS = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASIS, 'data')
DB = os.path.join(DATA, '.cache', 'index.db')
BIJLAGEN = os.path.join(DATA, opslag.BIJLAGEN_MAP)
STATIC = os.path.join(BASIS, 'static')
POORT = int(os.environ.get('POORT', 8765))

SOORTEN = ['vergadering', 'agendapunt', 'besluit', 'actie', 'stuk']


# ───────────────────────── database ─────────────────────────

def verbind():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


SLOT = threading.RLock()   # één verzoek tegelijk: houdt bestanden en index in de pas
_handtekening = None


def init_db():
    os.makedirs(BIJLAGEN, exist_ok=True)
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = verbind()
    with open(os.path.join(BASIS, 'schema.sql'), encoding='utf-8') as f:
        con.executescript(f.read())
    con.commit()
    synchroniseer(con)
    con.close()


def synchroniseer(con):
    """Bouwt de index opnieuw op als er bestanden zijn toegevoegd, gewijzigd of verwijderd (ook van buitenaf, bijv. in Obsidian)."""
    global _handtekening
    if opslag.handtekening(DATA) == _handtekening:
        return
    nieuw = opslag.importeer(con, DATA)
    herindexeer(con)
    con.commit()
    if nieuw:  # bestanden zonder id hebben er een gekregen: terugschrijven
        opslag.exporteer(con, DATA)
    _handtekening = opslag.handtekening(DATA)


def bewaar_bestanden(con):
    """Na een wijziging via de webinterface: database → Markdown-bestanden."""
    global _handtekening
    opslag.exporteer(con, DATA)
    _handtekening = opslag.handtekening(DATA)


def rijen(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def rij(con, sql, args=()):
    r = con.execute(sql, args).fetchone()
    return dict(r) if r else None


def vandaag():
    return dt.date.today().isoformat()


def nu():
    return dt.datetime.now().isoformat(timespec='seconds')


def plaatshouders(n):
    return ','.join('?' * n)


def onderliggende(con, onderdeel_id):
    """Het bedrijfsonderdeel zelf plus alles wat eronder valt."""
    return [r[0] for r in con.execute(
        '''WITH RECURSIVE boom(id) AS (SELECT ? UNION ALL
             SELECT b.id FROM bedrijfsonderdeel b JOIN boom ON b.valt_onder = boom.id)
           SELECT id FROM boom''', (onderdeel_id,))]


# ───────────────────────── zoekindex ─────────────────────────

def herindexeer(con):
    """Bouwt de volledige-tekstindex opnieuw op. Op PoC-schaal kost dit milliseconden."""
    con.execute('DELETE FROM zoekindex')
    ins = 'INSERT INTO zoekindex(soort, ref, titel, tekst) VALUES (?,?,?,?)'
    for r in con.execute('''SELECT v.id, COALESCE(v.titel, o.naam) t, o.naam || ' ' || o.afkorting || ' ' || COALESCE(v.locatie,'') || ' ' || COALESCE(v.samenvatting,'') x
                            FROM vergadering v JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel'''):
        con.execute(ins, ('vergadering', r['id'], r['t'], r['x']))
    for r in con.execute('SELECT id, titel, COALESCE(bespreking,\'\') x FROM agendapunt'):
        con.execute(ins, ('agendapunt', r['id'], r['titel'], r['x']))
    for r in con.execute('SELECT id, nummer || \' \' || titel t, besluittekst || \' \' || COALESCE(motivering,\'\') x FROM besluit'):
        con.execute(ins, ('besluit', r['id'], r['t'], r['x']))
    for r in con.execute('''SELECT a.id, a.titel, COALESCE(a.omschrijving,'') || ' ' ||
                              COALESCE((SELECT group_concat(tekst, ' ') FROM actie_voortgang WHERE actie = a.id),'') x
                            FROM actie a'''):
        con.execute(ins, ('actie', r['id'], r['titel'], r['x']))
    for r in con.execute('SELECT id, titel || \' \' || bestandsnaam t, COALESCE(inhoud_tekst,\'\') x FROM stuk'):
        con.execute(ins, ('stuk', r['id'], r['t'], r['x']))
    for r in con.execute('SELECT id, voornaam || \' \' || achternaam t, COALESCE(functie,\'\') || \' \' || email x FROM persoon'):
        con.execute(ins, ('persoon', r['id'], r['t'], r['x']))
    for r in con.execute('SELECT id, naam, COALESCE(omschrijving,\'\') || \' \' || COALESCE(trefwoorden,\'\') x FROM onderwerp'):
        con.execute(ins, ('onderwerp', r['id'], r['naam'], r['x']))


def fts_vraag(q):
    woorden = re.findall(r'\w+', q, re.UNICODE)
    return ' '.join(f'"{w}"*' for w in woorden)


# ───────────────────────── tekst uit bijlagen ─────────────────────────

def _xml_naar_tekst(xml):
    xml = re.sub(r'</(w:p|a:p|text:p|text:h|si)>', '\n', xml)
    xml = re.sub(r'<w:tab/>|<w:br/>', ' ', xml)
    return html.unescape(re.sub(r'<[^>]+>', '', xml))


def _pdf_string(s):
    uit, i = bytearray(), 0
    while i < len(s):
        c = s[i]
        if c == 0x5C and i + 1 < len(s):  # backslash
            n = s[i + 1]
            kaart = {ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('b'): 8, ord('f'): 12}
            if n in kaart:
                uit.append(kaart[n]); i += 2
            elif 0x30 <= n <= 0x37:
                m = re.match(rb'[0-7]{1,3}', s[i + 1:i + 4])
                uit.append(int(m.group(), 8) & 0xFF); i += 1 + len(m.group())
            elif n in (10, 13):
                i += 2
            else:
                uit.append(n); i += 2
        else:
            uit.append(c); i += 1
    return uit.decode('cp1252', errors='replace')


def _pdf_tekst_eenvoudig(data):
    """Noodoplossing zonder bibliotheken: leest tekst uit (eventueel Flate-gecomprimeerde) contentstreams."""
    delen = []
    for m in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', data, re.S):
        blok = m.group(1)
        try:
            blok = zlib.decompress(blok)
        except zlib.error:
            pass
        if b'BT' not in blok:
            continue
        for bt in re.findall(rb'BT(.*?)ET', blok, re.S):
            regel = []
            for t in re.finditer(rb'\(((?:\\.|[^\\)])*)\)\s*(?:Tj|\'|")|\[((?:\\.|[^\]])*)\]\s*TJ|(T\*|Td|TD)', bt, re.S):
                if t.group(1) is not None:
                    regel.append(_pdf_string(t.group(1)))
                elif t.group(2) is not None:
                    regel.append(''.join(_pdf_string(x) for x in re.findall(rb'\(((?:\\.|[^\\)])*)\)', t.group(2))))
                else:
                    regel.append('\n')
            delen.append(''.join(regel))
    return '\n'.join(delen)


def tekst_uit_bestand(pad, naam):
    ext = naam.lower().rsplit('.', 1)[-1] if '.' in naam else ''
    try:
        if ext in ('txt', 'md', 'csv'):
            with open(pad, 'rb') as f:
                return f.read().decode('utf-8', errors='replace')
        if ext in ('docx', 'pptx', 'xlsx', 'odt', 'odp', 'ods'):
            with zipfile.ZipFile(pad) as z:
                namen = z.namelist()
                if ext == 'docx':
                    delen = ['word/document.xml']
                elif ext == 'pptx':
                    delen = sorted(n for n in namen if re.match(r'ppt/slides/slide\d+\.xml', n))
                elif ext == 'xlsx':
                    delen = ['xl/sharedStrings.xml']
                else:
                    delen = ['content.xml']
                return '\n'.join(_xml_naar_tekst(z.read(n).decode('utf-8', errors='replace')) for n in delen if n in namen)
        if ext == 'pdf':
            try:
                import pypdf  # optioneel, geeft betere resultaten als het geïnstalleerd is
                return '\n'.join((p.extract_text() or '') for p in pypdf.PdfReader(pad).pages)
            except ImportError:
                with open(pad, 'rb') as f:
                    return _pdf_tekst_eenvoudig(f.read())
    except Exception as e:  # een onleesbare bijlage mag het opslaan niet blokkeren
        print('tekstextractie mislukt voor', naam, e, file=sys.stderr)
    return ''


# ───────────────────────── entiteiten (generieke CRUD) ─────────────────────────

ENTITEITEN = {
    'bedrijfsonderdeel': dict(velden=['naam', 'afkorting', 'soort', 'valt_onder', 'actief']),
    'persoon': dict(velden=['voornaam', 'achternaam', 'email', 'functie', 'bedrijfsonderdeel', 'telefoon', 'foto', 'actief']),
    'onderwerp': dict(velden=['naam', 'omschrijving', 'portefeuillehouder', 'trefwoorden']),
    'vergadering': dict(velden=['bedrijfsonderdeel', 'datum', 'begintijd', 'eindtijd', 'titel', 'locatie', 'status', 'vastgesteld_in', 'samenvatting']),
    'agendapunt': dict(velden=['vergadering', 'volgnummer', 'titel', 'soort', 'inbrenger', 'bespreking'],
                       m2m={'onderwerpen': ('agendapunt_onderwerp', 'agendapunt', 'onderwerp')}),
    'stuk': dict(velden=['titel', 'agendapunt', 'soort', 'auteur', 'versie', 'datum', 'vertrouwelijkheid']),
    'besluit': dict(velden=['titel', 'besluittekst', 'motivering', 'vergadering', 'agendapunt', 'status', 'vervangt'],
                    m2m={'onderwerpen': ('besluit_onderwerp', 'besluit', 'onderwerp'),
                         'grondslag': ('besluit_grondslag', 'besluit', 'stuk'),
                         'betrokkenen': ('besluit_betrokkene', 'besluit', 'persoon')}),
    'actie': dict(velden=['titel', 'omschrijving', 'eigenaar', 'deadline', 'status', 'vergadering', 'agendapunt', 'besluit', 'afgerond_op'],
                  m2m={'uitvoerders': ('actie_uitvoerder', 'actie', 'persoon')}),
}


class Fout(Exception):
    def __init__(self, bericht, code=400):
        super().__init__(bericht)
        self.code = code


def schoon(waarde):
    if isinstance(waarde, str):
        waarde = waarde.strip()
        return waarde or None
    return waarde


def volgend_besluitnummer(con, vergadering_id):
    r = rij(con, '''SELECT o.afkorting, substr(v.datum,1,4) jaar FROM vergadering v
                    JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel WHERE v.id = ?''', (vergadering_id,))
    if not r:
        raise Fout('Onbekende vergadering')
    prefix = f"{r['afkorting']}-{r['jaar']}-"
    hoogste = con.execute('SELECT MAX(CAST(substr(nummer, ?) AS INTEGER)) FROM besluit WHERE nummer LIKE ?',
                          (len(prefix) + 1, prefix + '%')).fetchone()[0] or 0
    return f'{prefix}{hoogste + 1:03d}'


def schrijf_m2m(con, cfg, eid, data):
    for sleutel, (tabel, eigen, ander) in cfg.get('m2m', {}).items():
        if sleutel in data:
            con.execute(f'DELETE FROM {tabel} WHERE {eigen} = ?', (eid,))
            for w in data[sleutel] or []:
                con.execute(f'INSERT OR IGNORE INTO {tabel}({eigen}, {ander}) VALUES (?,?)', (eid, int(w)))


def maak(con, soort, data, gebruiker):
    cfg = ENTITEITEN[soort]
    waarden = {k: schoon(data.get(k)) for k in cfg['velden'] if k in data}
    if soort == 'besluit':
        waarden['nummer'] = volgend_besluitnummer(con, waarden.get('vergadering'))
    if soort == 'agendapunt' and not waarden.get('volgnummer'):
        waarden['volgnummer'] = (con.execute('SELECT MAX(volgnummer) FROM agendapunt WHERE vergadering = ?',
                                             (waarden.get('vergadering'),)).fetchone()[0] or 0) + 1
    if soort == 'actie' and waarden.get('status') == 'afgerond' and not waarden.get('afgerond_op'):
        waarden['afgerond_op'] = vandaag()
    waarden.update(aangemaakt_op=nu(), aangemaakt_door=gebruiker, gewijzigd_op=nu(), gewijzigd_door=gebruiker)
    kolommen = ','.join(waarden)
    try:
        cur = con.execute(f'INSERT INTO {soort}({kolommen}) VALUES ({plaatshouders(len(waarden))})', list(waarden.values()))
    except sqlite3.IntegrityError as e:
        raise Fout(vertaal_integriteit(e))
    eid = cur.lastrowid
    schrijf_m2m(con, cfg, eid, data)
    if soort == 'vergadering':  # aanwezigheidslijst voorinvullen met de vaste leden
        con.execute('''INSERT INTO deelname(vergadering, persoon, rol, aanwezigheid)
                       SELECT ?, persoon, rol, 'aanwezig' FROM lidmaatschap WHERE bedrijfsonderdeel = ?''',
                    (eid, waarden['bedrijfsonderdeel']))
    return eid


def wijzig(con, soort, eid, data, gebruiker):
    cfg = ENTITEITEN[soort]
    waarden = {k: schoon(data[k]) for k in cfg['velden'] if k in data}
    if soort == 'actie' and 'status' in waarden:
        oud = rij(con, 'SELECT status, afgerond_op FROM actie WHERE id = ?', (eid,))
        if waarden['status'] == 'afgerond' and not waarden.get('afgerond_op') and not (oud and oud['afgerond_op']):
            waarden['afgerond_op'] = vandaag()
        elif waarden['status'] in ('open', 'loopt'):
            waarden['afgerond_op'] = None
    waarden.update(gewijzigd_op=nu(), gewijzigd_door=gebruiker)
    zet = ','.join(f'{k} = ?' for k in waarden)
    try:
        n = con.execute(f'UPDATE {soort} SET {zet} WHERE id = ?', [*waarden.values(), eid]).rowcount
    except sqlite3.IntegrityError as e:
        raise Fout(vertaal_integriteit(e))
    if not n:
        raise Fout('Niet gevonden', 404)
    schrijf_m2m(con, cfg, eid, data)


def verwijder(con, soort, eid):
    if soort == 'stuk':
        s = rij(con, 'SELECT bestandspad FROM stuk WHERE id = ?', (eid,))
        if s:
            pad = os.path.join(BIJLAGEN, s['bestandspad'])
            if os.path.exists(pad):
                os.remove(pad)
    try:
        con.execute(f'DELETE FROM {soort} WHERE id = ?', (eid,))
    except sqlite3.IntegrityError:
        raise Fout('Dit item wordt nog gebruikt (bijvoorbeeld als eigenaar van een actie) en kan daarom niet weg.')


def vertaal_integriteit(e):
    t = str(e)
    if 'UNIQUE' in t:
        return 'Deze waarde bestaat al: ' + t.split(':')[-1].strip()
    if 'NOT NULL' in t:
        return 'Verplicht veld ontbreekt: ' + t.split('.')[-1].strip()
    if 'CHECK' in t:
        return 'Ongeldige keuze in een van de velden.'
    if 'FOREIGN KEY' in t:
        return 'Een gekoppeld item bestaat niet (meer).'
    return t


# ───────────────────────── leesfuncties ─────────────────────────

def naam(p):
    return f"{p['voornaam']} {p['achternaam']}" if p else None


def op_achternaam(lijst):
    """Nederlandse volgorde: 'de Groot' staat bij de G."""
    tv = re.compile(r"^(van der|van den|van de|van|de|den|der|ter|te|het|'t)\s+", re.I)
    return sorted(lijst, key=lambda p: (tv.sub('', p['achternaam']).lower(), p['voornaam'].lower()))


def meta(con):
    return {
        'onderdelen': rijen(con, 'SELECT id, naam, afkorting, soort, valt_onder, actief FROM bedrijfsonderdeel ORDER BY naam'),
        'personen': op_achternaam(rijen(con, '''SELECT p.id, p.voornaam, p.achternaam, p.functie, p.foto, p.actief, p.bedrijfsonderdeel, p.email
                                   FROM persoon p''')),
        'onderwerpen': rijen(con, 'SELECT id, naam FROM onderwerp ORDER BY naam'),
        'problemen': list(opslag.PROBLEMEN),
        'te_laat': con.execute("SELECT COUNT(*) FROM actie WHERE status IN ('open','loopt') AND deadline < ?", (vandaag(),)).fetchone()[0],
        'vandaag': vandaag(),
    }


PERSOON_KORT = "p.id AS p_id, p.voornaam || ' ' || p.achternaam AS p_naam, p.foto AS p_foto"


def verrijk(con, items):
    """Voegt per soort de velden toe die je in een resultatenlijst wilt zien."""
    per = {}
    for it in items:
        per.setdefault(it['soort'], []).append(it['id'])
    extra = {}
    if per.get('vergadering'):
        ids = per['vergadering']
        for r in rijen(con, f'''SELECT v.id, v.begintijd, v.locatie, o.naam onderdeel_naam, o.afkorting,
                                  (SELECT COUNT(*) FROM besluit WHERE vergadering = v.id) n_besluiten,
                                  (SELECT COUNT(*) FROM actie WHERE vergadering = v.id) n_acties,
                                  (SELECT COUNT(*) FROM stuk WHERE vergadering = v.id) n_stukken
                                FROM vergadering v JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                WHERE v.id IN ({plaatshouders(len(ids))})''', ids):
            extra[('vergadering', r['id'])] = r
    vergaderinfo = '''v.id AS v_id, COALESCE(v.titel, o.naam) AS v_titel, v.datum AS v_datum, o.afkorting'''
    if per.get('agendapunt'):
        ids = per['agendapunt']
        for r in rijen(con, f'''SELECT a.id, a.volgnummer, {vergaderinfo} FROM agendapunt a
                                JOIN vergadering v ON v.id = a.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                WHERE a.id IN ({plaatshouders(len(ids))})''', ids):
            extra[('agendapunt', r['id'])] = r
    if per.get('besluit'):
        ids = per['besluit']
        for r in rijen(con, f'''SELECT b.id, b.nummer, substr(b.besluittekst, 1, 220) kort, {vergaderinfo} FROM besluit b
                                JOIN vergadering v ON v.id = b.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                WHERE b.id IN ({plaatshouders(len(ids))})''', ids):
            extra[('besluit', r['id'])] = r
    if per.get('actie'):
        ids = per['actie']
        for r in rijen(con, f'''SELECT x.id, x.deadline, x.afgerond_op, {PERSOON_KORT}, {vergaderinfo},
                                  (x.status IN ('open','loopt') AND x.deadline < date('now','localtime')) te_laat
                                FROM actie x JOIN persoon p ON p.id = x.eigenaar
                                JOIN vergadering v ON v.id = x.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                WHERE x.id IN ({plaatshouders(len(ids))})''', ids):
            extra[('actie', r['id'])] = r
    if per.get('stuk'):
        ids = per['stuk']
        for r in rijen(con, f'''SELECT s.id, s.bestandsnaam, s.mime, s.grootte, s.soort stuksoort, {vergaderinfo} FROM stuk s
                                JOIN vergadering v ON v.id = s.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                WHERE s.id IN ({plaatshouders(len(ids))})''', ids):
            extra[('stuk', r['id'])] = r
    for it in items:
        e = extra.get((it['soort'], it['id']))
        if e:
            it.update({k: v for k, v in e.items() if k != 'id'})
    return items


def zoek(con, p):
    q = (p.get('q') or '').strip()
    fq = fts_vraag(q) if q else ''
    gevraagd = [s for s in (p.get('soort') or '').split(',') if s in SOORTEN] or SOORTEN
    waar, args = [], []
    if p.get('onderdeel'):
        ids = onderliggende(con, int(p['onderdeel']))
        waar.append(f'i.onderdeel IN ({plaatshouders(len(ids))})'); args += ids
    if p.get('van'):
        waar.append('i.datum >= ?'); args.append(p['van'])
    if p.get('tot'):
        waar.append('i.datum <= ?'); args.append(p['tot'])
    if p.get('persoon'):
        waar.append('EXISTS (SELECT 1 FROM v_item_persoon vp WHERE vp.soort = i.soort AND vp.id = i.id AND vp.persoon = ?)')
        args.append(int(p['persoon']))
    if p.get('onderwerp'):
        waar.append('EXISTS (SELECT 1 FROM v_item_onderwerp vo WHERE vo.soort = i.soort AND vo.id = i.id AND vo.onderwerp = ?)')
        args.append(int(p['onderwerp']))
    statussen = [s for s in (p.get('status') or '').split(',') if s]
    if statussen:
        delen = []
        if 'te laat' in statussen:
            delen.append("(i.soort = 'actie' AND EXISTS (SELECT 1 FROM actie x WHERE x.id = i.id AND x.status IN ('open','loopt') AND x.deadline < date('now','localtime')))")
            statussen = [s for s in statussen if s != 'te laat']
        if statussen:
            delen.append(f'i.status IN ({plaatshouders(len(statussen))})'); args += statussen
        waar.append('(' + ' OR '.join(delen) + ')')
    if p.get('eigenaar'):
        waar.append("(i.soort = 'actie' AND EXISTS (SELECT 1 FROM actie x WHERE x.id = i.id AND x.eigenaar = ?))")
        args.append(int(p['eigenaar']))
    sql_waar = ('WHERE ' + ' AND '.join(waar)) if waar else ''
    if fq:
        sql = f'''SELECT i.*, f.rang, f.fragment FROM v_item i
                  JOIN (SELECT soort, ref, bm25(zoekindex, 0, 0, 4.0, 1.0) rang,
                               snippet(zoekindex, -1, char(1), char(2), '…', 18) fragment
                        FROM zoekindex WHERE zoekindex MATCH ?) f ON f.soort = i.soort AND f.ref = i.id
                  {sql_waar} ORDER BY f.rang LIMIT 600'''
        alles = rijen(con, sql, [fq, *args])
    elif q:
        alles = []
    else:
        sorteer = 'i.datum DESC, i.id DESC'
        if p.get('sorteer') == 'oplopend':
            sorteer = 'i.datum ASC, i.id ASC'
        alles = rijen(con, f'SELECT i.* FROM v_item i {sql_waar} ORDER BY {sorteer} LIMIT 600', args)
    tellingen = {s: 0 for s in SOORTEN}
    for r in alles:
        tellingen[r['soort']] += 1
    items = verrijk(con, [r for r in alles if r['soort'] in gevraagd])
    resultaat = {'items': items, 'tellingen': tellingen, 'personen': [], 'onderwerpen': []}
    if fq:
        for soort in ('persoon', 'onderwerp'):
            ids = [r[0] for r in con.execute('SELECT ref FROM zoekindex WHERE zoekindex MATCH ? AND soort = ? ORDER BY rank LIMIT 8', (fq, soort))]
            if ids and soort == 'persoon':
                resultaat['personen'] = rijen(con, f'SELECT id, voornaam, achternaam, functie, foto FROM persoon WHERE id IN ({plaatshouders(len(ids))})', ids)
            if ids and soort == 'onderwerp':
                resultaat['onderwerpen'] = rijen(con, f'SELECT id, naam, omschrijving FROM onderwerp WHERE id IN ({plaatshouders(len(ids))})', ids)
    return resultaat


def dashboard(con, gebruiker_id):
    d = vandaag()
    jaar = d[:4]
    acties_basis = f'''SELECT x.id, 'actie' soort, x.titel, x.status, x.deadline, {PERSOON_KORT},
                         v.id v_id, COALESCE(v.titel, o.naam) v_titel, v.datum v_datum, o.afkorting,
                         (x.status IN ('open','loopt') AND x.deadline < date('now','localtime')) te_laat
                       FROM actie x JOIN persoon p ON p.id = x.eigenaar
                       JOIN vergadering v ON v.id = x.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel'''
    res = {
        'kpi': {
            'open_acties': con.execute("SELECT COUNT(*) FROM actie WHERE status IN ('open','loopt')").fetchone()[0],
            'te_laat': con.execute("SELECT COUNT(*) FROM actie WHERE status IN ('open','loopt') AND deadline < ?", (d,)).fetchone()[0],
            'deze_week': con.execute("SELECT COUNT(*) FROM actie WHERE status IN ('open','loopt') AND deadline BETWEEN ? AND date(?, '+7 days')", (d, d)).fetchone()[0],
            'besluiten_jaar': con.execute('SELECT COUNT(*) FROM besluit b JOIN vergadering v ON v.id = b.vergadering WHERE substr(v.datum,1,4) = ?', (jaar,)).fetchone()[0],
            'vergaderingen_jaar': con.execute("SELECT COUNT(*) FROM vergadering WHERE substr(datum,1,4) = ? AND datum <= ?", (jaar, d)).fetchone()[0],
            'afgerond_30d': con.execute("SELECT COUNT(*) FROM actie WHERE status = 'afgerond' AND afgerond_op >= date(?, '-30 days')", (d,)).fetchone()[0],
        },
        'te_laat': rijen(con, acties_basis + " WHERE x.status IN ('open','loopt') AND x.deadline < ? ORDER BY x.deadline LIMIT 12", (d,)),
        'binnenkort': rijen(con, acties_basis + " WHERE x.status IN ('open','loopt') AND x.deadline >= ? ORDER BY x.deadline LIMIT 8", (d,)),
        'komend': rijen(con, '''SELECT v.id, v.datum, v.begintijd, v.locatie, COALESCE(v.titel, o.naam) titel, o.afkorting, o.naam onderdeel_naam,
                                  (SELECT COUNT(*) FROM agendapunt WHERE vergadering = v.id) n_punten
                                FROM vergadering v JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                WHERE v.datum >= ? ORDER BY v.datum, v.begintijd LIMIT 5''', (d,)),
        'recente_besluiten': rijen(con, '''SELECT b.id, b.nummer, b.titel, b.status, v.id v_id, v.datum v_datum, o.afkorting, o.naam onderdeel_naam
                                           FROM besluit b JOIN vergadering v ON v.id = b.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                           ORDER BY v.datum DESC, b.nummer DESC LIMIT 6'''),
        'per_eigenaar': rijen(con, f'''SELECT {PERSOON_KORT}, COUNT(*) open, SUM(x.deadline < ?) te_laat
                                       FROM actie x JOIN persoon p ON p.id = x.eigenaar
                                       WHERE x.status IN ('open','loopt') GROUP BY p.id ORDER BY open DESC, te_laat DESC LIMIT 8''', (d,)),
        'per_onderdeel': rijen(con, '''SELECT o.id, o.naam, o.afkorting,
                                         SUM(x.status IN ('open','loopt')) open, SUM(x.status IN ('open','loopt') AND x.deadline < ?) te_laat,
                                         SUM(x.status = 'afgerond') afgerond
                                       FROM actie x JOIN vergadering v ON v.id = x.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                       GROUP BY o.id ORDER BY open DESC''', (d,)),
        'mijn': [],
    }
    if gebruiker_id:
        res['mijn'] = rijen(con, acties_basis + " WHERE x.status IN ('open','loopt') AND (x.eigenaar = ? OR x.id IN (SELECT actie FROM actie_uitvoerder WHERE persoon = ?)) ORDER BY x.deadline IS NULL, x.deadline", (gebruiker_id, gebruiker_id))
    return res


def vergadering_volledig(con, vid):
    v = rij(con, '''SELECT v.*, o.naam onderdeel_naam, o.afkorting, o.soort onderdeel_soort FROM vergadering v
                    JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel WHERE v.id = ?''', (vid,))
    if not v:
        raise Fout('Vergadering niet gevonden', 404)
    v['deelname'] = rijen(con, '''SELECT d.rol, d.aanwezigheid, p.id, p.voornaam, p.achternaam, p.functie, p.foto FROM deelname d
                                  JOIN persoon p ON p.id = d.persoon WHERE d.vergadering = ?
                                  ORDER BY CASE d.rol WHEN 'voorzitter' THEN 0 WHEN 'lid' THEN 1 WHEN 'notulist' THEN 2 ELSE 3 END, p.achternaam''', (vid,))
    punten = rijen(con, f'''SELECT a.*, p.voornaam || ' ' || p.achternaam inbrenger_naam FROM agendapunt a
                            LEFT JOIN persoon p ON p.id = a.inbrenger WHERE a.vergadering = ? ORDER BY a.volgnummer''', (vid,))
    onderwerpen = rijen(con, '''SELECT ao.agendapunt, o.id, o.naam FROM agendapunt_onderwerp ao JOIN onderwerp o ON o.id = ao.onderwerp
                                WHERE ao.agendapunt IN (SELECT id FROM agendapunt WHERE vergadering = ?)''', (vid,))
    stukken = rijen(con, '''SELECT s.id, s.titel, s.bestandsnaam, s.mime, s.grootte, s.soort, s.vertrouwelijkheid, s.agendapunt, s.versie, s.datum,
                              s.auteur, p.voornaam || ' ' || p.achternaam auteur_naam
                            FROM stuk s LEFT JOIN persoon p ON p.id = s.auteur WHERE s.vergadering = ? ORDER BY s.id''', (vid,))
    besluiten = rijen(con, '''SELECT b.*, vb.nummer vervangt_nummer FROM besluit b LEFT JOIN besluit vb ON vb.id = b.vervangt
                              WHERE b.vergadering = ? ORDER BY b.nummer''', (vid,))
    for b in besluiten:
        b['onderwerpen'] = [r['onderwerp'] for r in rijen(con, 'SELECT onderwerp FROM besluit_onderwerp WHERE besluit = ?', (b['id'],))]
        b['grondslag'] = rijen(con, 'SELECT s.id, s.titel FROM besluit_grondslag g JOIN stuk s ON s.id = g.stuk WHERE g.besluit = ?', (b['id'],))
        b['betrokkenen'] = rijen(con, 'SELECT p.id, p.voornaam, p.achternaam, p.foto FROM besluit_betrokkene bb JOIN persoon p ON p.id = bb.persoon WHERE bb.besluit = ?', (b['id'],))
        b['vervangen_door'] = rijen(con, 'SELECT id, nummer FROM besluit WHERE vervangt = ?', (b['id'],))
    acties = rijen(con, f'''SELECT x.*, {PERSOON_KORT}, b.nummer besluit_nummer,
                              (x.status IN ('open','loopt') AND x.deadline < date('now','localtime')) te_laat
                            FROM actie x JOIN persoon p ON p.id = x.eigenaar LEFT JOIN besluit b ON b.id = x.besluit
                            WHERE x.vergadering = ? ORDER BY x.id''', (vid,))
    for a in acties:
        a['uitvoerders'] = rijen(con, 'SELECT p.id, p.voornaam, p.achternaam, p.foto FROM actie_uitvoerder u JOIN persoon p ON p.id = u.persoon WHERE u.actie = ?', (a['id'],))
    for pt in punten:
        pt['onderwerpen'] = [{'id': o['id'], 'naam': o['naam']} for o in onderwerpen if o['agendapunt'] == pt['id']]
    v['agendapunten'] = punten
    v['stukken'] = stukken
    v['besluiten'] = besluiten
    v['acties'] = acties
    v['vorige'] = rij(con, 'SELECT id, datum FROM vergadering WHERE bedrijfsonderdeel = ? AND (datum < ? OR (datum = ? AND id < ?)) ORDER BY datum DESC, id DESC LIMIT 1', (v['bedrijfsonderdeel'], v['datum'], v['datum'], vid))
    v['volgende'] = rij(con, 'SELECT id, datum FROM vergadering WHERE bedrijfsonderdeel = ? AND (datum > ? OR (datum = ? AND id > ?)) ORDER BY datum, id LIMIT 1', (v['bedrijfsonderdeel'], v['datum'], v['datum'], vid))
    v['vastgesteld_in_info'] = rij(con, 'SELECT id, datum FROM vergadering WHERE id = ?', (v['vastgesteld_in'],)) if v['vastgesteld_in'] else None
    v['stelt_vast'] = rijen(con, 'SELECT id, datum FROM vergadering WHERE vastgesteld_in = ?', (vid,))
    v['openstaand_eerder'] = rijen(con, f'''SELECT x.id, x.titel, x.status, x.deadline, {PERSOON_KORT}, v2.id v_id, v2.datum v_datum,
                                              (x.deadline < date('now','localtime')) te_laat
                                            FROM actie x JOIN persoon p ON p.id = x.eigenaar JOIN vergadering v2 ON v2.id = x.vergadering
                                            WHERE v2.bedrijfsonderdeel = ? AND v2.datum < ? AND x.status IN ('open','loopt')
                                            ORDER BY x.deadline''', (v['bedrijfsonderdeel'], v['datum']))
    return v


def actie_volledig(con, aid):
    a = rij(con, f'''SELECT x.*, {PERSOON_KORT}, b.nummer besluit_nummer, b.titel besluit_titel, ap.titel agendapunt_titel, ap.volgnummer,
                       COALESCE(v.titel, o.naam) v_titel, v.datum v_datum, o.afkorting,
                       (x.status IN ('open','loopt') AND x.deadline < date('now','localtime')) te_laat
                     FROM actie x JOIN persoon p ON p.id = x.eigenaar JOIN vergadering v ON v.id = x.vergadering
                     JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                     LEFT JOIN besluit b ON b.id = x.besluit LEFT JOIN agendapunt ap ON ap.id = x.agendapunt WHERE x.id = ?''', (aid,))
    if not a:
        raise Fout('Actie niet gevonden', 404)
    a['uitvoerders'] = rijen(con, 'SELECT p.id, p.voornaam, p.achternaam, p.foto FROM actie_uitvoerder u JOIN persoon p ON p.id = u.persoon WHERE u.actie = ?', (aid,))
    a['voortgang'] = rijen(con, '''SELECT g.*, v.datum v_datum FROM actie_voortgang g LEFT JOIN vergadering v ON v.id = g.vergadering
                                   WHERE g.actie = ? ORDER BY g.datum DESC, g.id DESC''', (aid,))
    return a


def besluit_volledig(con, bid):
    b = rij(con, '''SELECT b.*, COALESCE(v.titel, o.naam) v_titel, v.datum v_datum, o.afkorting, o.naam onderdeel_naam,
                      ap.titel agendapunt_titel, ap.volgnummer, vb.nummer vervangt_nummer, vb.titel vervangt_titel
                    FROM besluit b JOIN vergadering v ON v.id = b.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                    LEFT JOIN agendapunt ap ON ap.id = b.agendapunt LEFT JOIN besluit vb ON vb.id = b.vervangt WHERE b.id = ?''', (bid,))
    if not b:
        raise Fout('Besluit niet gevonden', 404)
    b['onderwerpen'] = rijen(con, '''SELECT DISTINCT o.id, o.naam FROM v_item_onderwerp vo JOIN onderwerp o ON o.id = vo.onderwerp
                                     WHERE vo.soort = 'besluit' AND vo.id = ?''', (bid,))
    b['onderwerp_ids'] = [r['onderwerp'] for r in rijen(con, 'SELECT onderwerp FROM besluit_onderwerp WHERE besluit = ?', (bid,))]
    b['grondslag'] = rijen(con, 'SELECT s.id, s.titel, s.bestandsnaam, s.vertrouwelijkheid FROM besluit_grondslag g JOIN stuk s ON s.id = g.stuk WHERE g.besluit = ?', (bid,))
    b['betrokkenen'] = rijen(con, 'SELECT p.id, p.voornaam, p.achternaam, p.foto, p.functie FROM besluit_betrokkene bb JOIN persoon p ON p.id = bb.persoon WHERE bb.besluit = ?', (bid,))
    b['vervangen_door'] = rijen(con, 'SELECT id, nummer, titel FROM besluit WHERE vervangt = ?', (bid,))
    b['acties'] = rijen(con, f'''SELECT x.id, x.titel, x.status, x.deadline, {PERSOON_KORT},
                                   (x.status IN ('open','loopt') AND x.deadline < date('now','localtime')) te_laat
                                 FROM actie x JOIN persoon p ON p.id = x.eigenaar WHERE x.besluit = ?''', (bid,))
    b['aanwezig'] = rijen(con, '''SELECT p.id, p.voornaam, p.achternaam, p.foto, d.rol, d.aanwezigheid FROM deelname d JOIN persoon p ON p.id = d.persoon
                                  WHERE d.vergadering = ? ORDER BY d.aanwezigheid, p.achternaam''', (b['vergadering'],))
    return b


def persoon_volledig(con, pid):
    p = rij(con, '''SELECT p.*, o.naam onderdeel_naam FROM persoon p LEFT JOIN bedrijfsonderdeel o ON o.id = p.bedrijfsonderdeel WHERE p.id = ?''', (pid,))
    if not p:
        raise Fout('Persoon niet gevonden', 404)
    p['lidmaatschappen'] = rijen(con, '''SELECT o.id, o.naam, o.afkorting, l.rol FROM lidmaatschap l JOIN bedrijfsonderdeel o ON o.id = l.bedrijfsonderdeel
                                         WHERE l.persoon = ? ORDER BY o.naam''', (pid,))
    p['acties'] = rijen(con, f'''SELECT x.id, x.titel, x.status, x.deadline, x.afgerond_op, x.eigenaar = ? als_eigenaar,
                                   v.id v_id, COALESCE(v.titel, o.naam) v_titel, v.datum v_datum, o.afkorting,
                                   (x.status IN ('open','loopt') AND x.deadline < date('now','localtime')) te_laat
                                 FROM actie x JOIN vergadering v ON v.id = x.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                 WHERE x.eigenaar = ? OR x.id IN (SELECT actie FROM actie_uitvoerder WHERE persoon = ?)
                                 ORDER BY x.status IN ('afgerond','vervallen'), x.deadline IS NULL, x.deadline''', (pid, pid, pid))
    p['besluiten'] = rijen(con, '''SELECT b.id, b.nummer, b.titel, b.status, v.id v_id, v.datum v_datum, o.afkorting
                                   FROM besluit_betrokkene bb JOIN besluit b ON b.id = bb.besluit JOIN vergadering v ON v.id = b.vergadering
                                   JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel WHERE bb.persoon = ? ORDER BY v.datum DESC''', (pid,))
    p['vergaderingen'] = rijen(con, '''SELECT v.id, v.datum, COALESCE(v.titel, o.naam) titel, o.afkorting, d.rol, d.aanwezigheid
                                       FROM deelname d JOIN vergadering v ON v.id = d.vergadering JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
                                       WHERE d.persoon = ? ORDER BY v.datum DESC''', (pid,))
    p['stukken'] = rijen(con, '''SELECT s.id, s.titel, s.bestandsnaam, v.id v_id, v.datum v_datum FROM stuk s JOIN vergadering v ON v.id = s.vergadering
                                 WHERE s.auteur = ? ORDER BY v.datum DESC''', (pid,))
    p['portefeuille'] = rijen(con, 'SELECT id, naam FROM onderwerp WHERE portefeuillehouder = ?', (pid,))
    return p


def onderwerp_volledig(con, oid):
    o = rij(con, '''SELECT o.*, p.voornaam || ' ' || p.achternaam ph_naam, p.foto ph_foto FROM onderwerp o
                    LEFT JOIN persoon p ON p.id = o.portefeuillehouder WHERE o.id = ?''', (oid,))
    if not o:
        raise Fout('Onderwerp niet gevonden', 404)
    o['tijdlijn'] = zoek(con, {'onderwerp': str(oid), 'sorteer': 'oplopend'})['items']
    o['betrokken'] = rijen(con, '''SELECT p.id, p.voornaam, p.achternaam, p.foto, COUNT(*) n FROM v_item_onderwerp vo
                                   JOIN v_item_persoon vp ON vp.soort = vo.soort AND vp.id = vo.id
                                   JOIN persoon p ON p.id = vp.persoon WHERE vo.onderwerp = ? AND vo.soort != 'vergadering'
                                   GROUP BY p.id ORDER BY n DESC LIMIT 10''', (oid,))
    return o


def onderdeel_volledig(con, oid):
    o = rij(con, 'SELECT o.*, b.naam boven_naam FROM bedrijfsonderdeel o LEFT JOIN bedrijfsonderdeel b ON b.id = o.valt_onder WHERE o.id = ?', (oid,))
    if not o:
        raise Fout('Bedrijfsonderdeel niet gevonden', 404)
    o['onder'] = rijen(con, 'SELECT id, naam, afkorting, soort FROM bedrijfsonderdeel WHERE valt_onder = ? ORDER BY naam', (oid,))
    o['leden'] = rijen(con, '''SELECT p.id, p.voornaam, p.achternaam, p.functie, p.foto, l.rol FROM lidmaatschap l JOIN persoon p ON p.id = l.persoon
                               WHERE l.bedrijfsonderdeel = ? ORDER BY CASE l.rol WHEN 'voorzitter' THEN 0 ELSE 1 END, p.achternaam''', (oid,))
    o['vergaderingen'] = verrijk(con, rijen(con, "SELECT i.* FROM v_item i WHERE i.soort = 'vergadering' AND i.onderdeel = ? ORDER BY i.datum DESC", (oid,)))
    return o


def markdown_verslag(con, vid):
    v = vergadering_volledig(con, vid)
    titel = v['titel'] or v['onderdeel_naam']
    uit = [f"# {titel}", '', f"**Datum:** {v['datum']}" + (f" {v['begintijd']}–{v['eindtijd'] or ''}" if v['begintijd'] else ''),
           f"**Bedrijfsonderdeel:** {v['onderdeel_naam']}  ", f"**Status:** {v['status']}", '']
    if v['locatie']:
        uit.insert(4, f"**Locatie:** {v['locatie']}  ")
    uit += ['## Aanwezigheid', '']
    for d in v['deelname']:
        uit.append(f"- {d['voornaam']} {d['achternaam']} ({d['rol']}): {d['aanwezigheid']}")
    if v['samenvatting']:
        uit += ['', '## Samenvatting', '', v['samenvatting']]
    for pt in v['agendapunten']:
        uit += ['', f"## {pt['volgnummer']}. {pt['titel']}", '']
        if pt['soort']:
            uit.append(f"*{pt['soort']}*")
        if pt['onderwerpen']:
            uit.append('Onderwerp: ' + ', '.join(o['naam'] for o in pt['onderwerpen']))
        if pt['bespreking']:
            uit += ['', pt['bespreking']]
        for s in [s for s in v['stukken'] if s['agendapunt'] == pt['id']]:
            uit.append(f"- 📎 {s['titel']} ({s['bestandsnaam']}, {s['vertrouwelijkheid']})")
        for b in [b for b in v['besluiten'] if b['agendapunt'] == pt['id']]:
            uit += ['', f"**Besluit {b['nummer']}: {b['titel']}** ({b['status']})", '', b['besluittekst']]
        for a in [a for a in v['acties'] if a['agendapunt'] == pt['id']]:
            uit.append(f"- [{'x' if a['status'] == 'afgerond' else ' '}] **Actie:** {a['titel']} — {a['p_naam']}" + (f", uiterlijk {a['deadline']}" if a['deadline'] else ''))
    los_b = [b for b in v['besluiten'] if not b['agendapunt']]
    los_a = [a for a in v['acties'] if not a['agendapunt']]
    if los_b or los_a:
        uit += ['', '## Overige besluiten en acties', '']
        for b in los_b:
            uit += [f"**Besluit {b['nummer']}: {b['titel']}** ({b['status']})", '', b['besluittekst'], '']
        for a in los_a:
            uit.append(f"- [{'x' if a['status'] == 'afgerond' else ' '}] **Actie:** {a['titel']} — {a['p_naam']}" + (f", uiterlijk {a['deadline']}" if a['deadline'] else ''))
    uit += ['', f"*Geëxporteerd uit het Vergaderregister op {vandaag()}.*", '']
    return titel, '\n'.join(uit)


def export_alles(con):
    tabellen = ['bedrijfsonderdeel', 'persoon', 'lidmaatschap', 'onderwerp', 'vergadering', 'deelname', 'agendapunt',
                'agendapunt_onderwerp', 'stuk', 'besluit', 'besluit_onderwerp', 'besluit_grondslag', 'besluit_betrokkene',
                'actie', 'actie_uitvoerder', 'actie_voortgang']
    return {'geexporteerd_op': nu(), **{t: rijen(con, f'SELECT * FROM {t}') for t in tabellen}}


# ───────────────────────── HTTP ─────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = 'Vergaderregister/0.1'

    def log_message(self, fmt, *args):
        if os.environ.get('STIL') != '1':
            sys.stderr.write('%s  %s\n' % (self.log_date_time_string(), fmt % args))

    # hulpfuncties
    def stuur(self, code, body, ctype='application/json; charset=utf-8', extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def lees_json(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    def gebruiker(self, con):
        gid = self.headers.get('X-Gebruiker')
        if gid and gid.isdigit():
            p = rij(con, 'SELECT id, voornaam, achternaam FROM persoon WHERE id = ?', (int(gid),))
            if p:
                return p['id'], naam(p)
        return None, 'onbekend'

    def stuur_bestand(self, pad, ctype=None, extra=None):
        with open(pad, 'rb') as f:
            data = f.read()
        self.stuur(200, data, ctype or mimetypes.guess_type(pad)[0] or 'application/octet-stream', extra)

    def afhandelen(self, methode):
        url = urllib.parse.urlparse(self.path)
        pad = urllib.parse.unquote(url.path)
        params = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
        SLOT.acquire()
        con = verbind()
        try:
            synchroniseer(con)
            if pad.startswith('/api/'):
                resultaat = self.api(con, methode, pad[5:].strip('/').split('/'), params)
                if methode != 'GET':
                    bewaar_bestanden(con)
                if resultaat is not None:
                    self.stuur(200, resultaat)
            elif methode == 'GET':
                self.statisch(con, pad)
            else:
                raise Fout('Niet gevonden', 404)
        except Fout as e:
            con.rollback()
            self.stuur(e.code, {'fout': str(e)})
        except Exception as e:  # onverwachte fout: netjes melden, server blijft draaien
            con.rollback()
            import traceback; traceback.print_exc()
            self.stuur(500, {'fout': f'Interne fout: {e}'})
        finally:
            con.close()
            SLOT.release()

    def do_GET(self): self.afhandelen('GET')
    def do_HEAD(self): self.afhandelen('GET')
    def do_POST(self): self.afhandelen('POST')
    def do_PUT(self): self.afhandelen('PUT')
    def do_DELETE(self): self.afhandelen('DELETE')

    def statisch(self, con, pad):
        if pad.startswith('/bijlage/'):
            sid = pad.split('/')[2]
            s = rij(con, 'SELECT * FROM stuk WHERE id = ?', (int(sid),)) if sid.isdigit() else None
            if not s:
                raise Fout('Bijlage niet gevonden', 404)
            naam_q = urllib.parse.quote(s['bestandsnaam'])
            self.stuur_bestand(os.path.join(BIJLAGEN, s['bestandspad']), s['mime'],
                               {'Content-Disposition': f"inline; filename*=UTF-8''{naam_q}"})
            return
        if pad.startswith('/export/vergadering/'):
            vid = re.findall(r'\d+', pad)
            titel, md = markdown_verslag(con, int(vid[0]))
            bestand = urllib.parse.quote(f"{titel}.md")
            self.stuur(200, md, 'text/markdown; charset=utf-8', {'Content-Disposition': f"attachment; filename*=UTF-8''{bestand}"})
            return
        if pad == '/export/alles.json':
            self.stuur(200, export_alles(con), extra={'Content-Disposition': f'attachment; filename="vergaderregister-{vandaag()}.json"'})
            return
        if pad in ('/', '/index.html'):
            pad = '/index.html'
        doel = os.path.normpath(os.path.join(STATIC, pad.lstrip('/')))
        if not doel.startswith(STATIC) or not os.path.isfile(doel):
            raise Fout('Niet gevonden', 404)
        self.stuur_bestand(doel)

    def api(self, con, methode, delen, params):
        gid, gnaam = self.gebruiker(con)
        hoofd = delen[0]
        eid = int(delen[1]) if len(delen) > 1 and delen[1].isdigit() else None

        if methode == 'GET':
            if hoofd == 'meta':
                return meta(con)
            if hoofd == 'dashboard':
                return dashboard(con, gid)
            if hoofd == 'zoek':
                return zoek(con, params)
            if hoofd == 'vergadering' and eid:
                return vergadering_volledig(con, eid)
            if hoofd == 'besluit' and eid:
                return besluit_volledig(con, eid)
            if hoofd == 'actie' and eid:
                return actie_volledig(con, eid)
            if hoofd == 'persoon' and eid:
                return persoon_volledig(con, eid)
            if hoofd == 'onderwerp' and eid:
                return onderwerp_volledig(con, eid)
            if hoofd == 'bedrijfsonderdeel' and eid:
                return onderdeel_volledig(con, eid)
            if hoofd == 'onderwerpen':
                return rijen(con, f'''SELECT o.id, o.naam, o.omschrijving, p.voornaam || ' ' || p.achternaam ph_naam, p.foto ph_foto,
                                        (SELECT COUNT(DISTINCT id) FROM v_item_onderwerp WHERE onderwerp = o.id AND soort = 'besluit') n_besluiten,
                                        (SELECT COUNT(DISTINCT id) FROM v_item_onderwerp WHERE onderwerp = o.id AND soort = 'actie') n_acties,
                                        (SELECT COUNT(DISTINCT id) FROM v_item_onderwerp WHERE onderwerp = o.id AND soort = 'vergadering') n_vergaderingen,
                                        (SELECT MAX(i.datum) FROM v_item_onderwerp vo JOIN v_item i ON i.soort = vo.soort AND i.id = vo.id WHERE vo.onderwerp = o.id) laatst
                                      FROM onderwerp o LEFT JOIN persoon p ON p.id = o.portefeuillehouder ORDER BY laatst DESC''')
            if hoofd == 'personen':
                return op_achternaam(rijen(con, '''SELECT p.*, o.naam onderdeel_naam,
                                       (SELECT COUNT(*) FROM actie WHERE eigenaar = p.id AND status IN ('open','loopt')) n_open,
                                       (SELECT COUNT(*) FROM actie WHERE eigenaar = p.id AND status IN ('open','loopt') AND deadline < date('now','localtime')) n_te_laat
                                     FROM persoon p LEFT JOIN bedrijfsonderdeel o ON o.id = p.bedrijfsonderdeel'''))
            if hoofd == 'onderdelen':
                return rijen(con, '''SELECT o.*, (SELECT COUNT(*) FROM vergadering WHERE bedrijfsonderdeel = o.id) n_vergaderingen,
                                       (SELECT COUNT(*) FROM lidmaatschap WHERE bedrijfsonderdeel = o.id) n_leden,
                                       (SELECT MAX(datum) FROM vergadering WHERE bedrijfsonderdeel = o.id AND datum <= date('now','localtime')) laatst
                                     FROM bedrijfsonderdeel o ORDER BY o.naam''')
            raise Fout('Niet gevonden', 404)

        if methode == 'POST' and hoofd == 'upload':
            return self.upload(con, params, gnaam)

        if methode == 'POST' and hoofd == 'actie' and eid and len(delen) > 2 and delen[2] == 'voortgang':
            data = self.lees_json()
            if not schoon(data.get('tekst')):
                raise Fout('Schrijf een korte voortgangsnotitie.')
            con.execute('INSERT INTO actie_voortgang(actie, datum, tekst, vergadering, aangemaakt_op, aangemaakt_door) VALUES (?,?,?,?,?,?)',
                        (eid, data.get('datum') or vandaag(), data['tekst'].strip(), schoon(data.get('vergadering')), nu(), gnaam))
            herindexeer(con); con.commit()
            return actie_volledig(con, eid)

        if methode == 'PUT' and hoofd == 'vergadering' and eid and len(delen) > 2 and delen[2] == 'deelname':
            data = self.lees_json()
            con.execute('DELETE FROM deelname WHERE vergadering = ?', (eid,))
            for d in data.get('deelname', []):
                con.execute('INSERT INTO deelname(vergadering, persoon, rol, aanwezigheid) VALUES (?,?,?,?)',
                            (eid, int(d['persoon']), d.get('rol') or 'lid', d.get('aanwezigheid') or 'aanwezig'))
            con.execute('UPDATE vergadering SET gewijzigd_op = ?, gewijzigd_door = ? WHERE id = ?', (nu(), gnaam, eid))
            con.commit()
            return {'ok': True}

        if methode == 'PUT' and hoofd == 'bedrijfsonderdeel' and eid and len(delen) > 2 and delen[2] == 'leden':
            data = self.lees_json()
            con.execute('DELETE FROM lidmaatschap WHERE bedrijfsonderdeel = ?', (eid,))
            for d in data.get('leden', []):
                con.execute('INSERT INTO lidmaatschap(bedrijfsonderdeel, persoon, rol) VALUES (?,?,?)', (eid, int(d['persoon']), d.get('rol') or 'lid'))
            con.commit()
            return {'ok': True}

        if hoofd not in ENTITEITEN:
            raise Fout('Niet gevonden', 404)
        if methode == 'POST':
            nieuw = maak(con, hoofd, self.lees_json(), gnaam)
            herindexeer(con); con.commit()
            return {'id': nieuw}
        if methode == 'PUT' and eid:
            wijzig(con, hoofd, eid, self.lees_json(), gnaam)
            herindexeer(con); con.commit()
            return {'id': eid}
        if methode == 'DELETE' and eid:
            verwijder(con, hoofd, eid)
            herindexeer(con); con.commit()
            return {'ok': True}
        raise Fout('Niet gevonden', 404)

    def upload(self, con, params, gnaam):
        bestandsnaam = urllib.parse.unquote(self.headers.get('X-Bestandsnaam') or '')
        n = int(self.headers.get('Content-Length') or 0)
        if not bestandsnaam or not n:
            raise Fout('Kies een bestand om toe te voegen.')
        if n > 50 * 1024 * 1024:
            raise Fout('Bestand is groter dan 50 MB.')
        vid = int(params.get('vergadering') or 0)
        if not rij(con, 'SELECT id FROM vergadering WHERE id = ?', (vid,)):
            raise Fout('Onbekende vergadering.')
        data = self.rfile.read(n)
        veilig = re.sub(r'[^\w.\- ]', '_', os.path.basename(bestandsnaam))[:120]
        relatief = os.path.join(str(vid), f'{uuid.uuid4().hex[:8]}_{veilig}')
        doel = os.path.join(BIJLAGEN, relatief)
        os.makedirs(os.path.dirname(doel), exist_ok=True)
        with open(doel, 'wb') as f:
            f.write(data)
        tekst = tekst_uit_bestand(doel, bestandsnaam)
        titel = schoon(params.get('titel')) or os.path.splitext(bestandsnaam)[0]
        cur = con.execute('''INSERT INTO stuk(titel, bestandsnaam, bestandspad, mime, grootte, vergadering, agendapunt, soort, auteur, versie, datum,
                               vertrouwelijkheid, inhoud_tekst, aangemaakt_op, aangemaakt_door, gewijzigd_op, gewijzigd_door)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (titel, bestandsnaam, relatief, self.headers.get('Content-Type') or mimetypes.guess_type(bestandsnaam)[0],
                           len(data), vid, schoon(params.get('agendapunt')), schoon(params.get('soort')), schoon(params.get('auteur')),
                           schoon(params.get('versie')), schoon(params.get('datum')) or vandaag(), params.get('vertrouwelijkheid') or 'intern',
                           tekst, nu(), gnaam, nu(), gnaam))
        herindexeer(con); con.commit()
        return {'id': cur.lastrowid, 'tekens_gelezen': len(tekst.strip())}


def main():
    init_db()
    srv = ThreadingHTTPServer(('127.0.0.1', POORT), Handler)
    print(f'Vergaderregister draait op http://127.0.0.1:{POORT}  (stoppen: Ctrl+C)')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nGestopt.')


if __name__ == '__main__':
    main()
