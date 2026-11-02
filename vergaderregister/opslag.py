"""Opslag in Markdown-bestanden met YAML-frontmatter.

De bestanden in data/ zijn de bron van waarheid. Elk record is één .md-bestand, in dezelfde mappen en met
dezelfde voorvoegsels als de Obsidian-proef. Verwijzingen zijn Obsidian-links: "[[👤 Anna de Vries]]".
SQLite (data/.cache/index.db) is alleen een zoekindex die uit de bestanden wordt opgebouwd.

  importeer(con)   bestanden → database  (bij opstarten en zodra een bestand van buitenaf wijzigt)
  exporteer(con)   database → bestanden  (na elke wijziging via de webinterface; schrijft alleen wat veranderde)
"""
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys

MAPPEN = {
    'bedrijfsonderdeel': '🏛 Bedrijfsonderdelen',
    'persoon': '👤 Personen',
    'onderwerp': '🚀 Onderwerpen',
    'vergadering': '📆 Vergaderingen',
    'stuk': '📎 Stukken',
    'besluit': '🎯 Besluiten',
    'actie': '✅ Acties',
}
VOORVOEGSEL = {s: m.split(' ')[0] for s, m in MAPPEN.items()}
BIJLAGEN_MAP = os.path.join('📎 Stukken', 'bestanden')
AUDIT = ['aangemaakt_op', 'aangemaakt_door', 'gewijzigd_op', 'gewijzigd_door']
PROBLEMEN = []  # bestanden die bij de laatste import zijn overgeslagen: [{'pad': ..., 'reden': ...}]


# ───────────────────────── YAML (klein subset, met PyYAML als dat er is) ─────────────────────────

def _yaml_scalar(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if re.fullmatch(r'\d{4}-\d\d-\d\d', s):  # datums onaangehaald, zoals Obsidian ze als datum herkent
        return s
    return json.dumps(s, ensure_ascii=False)  # een JSON-string is geldige YAML


def maak_yaml(paren):
    uit = []
    for k, v in paren:
        if isinstance(v, list):
            if not v:
                uit.append(f'{k}: []')
                continue
            uit.append(f'{k}:')
            for item in v:
                if isinstance(item, dict):
                    eerste = True
                    for ik, iv in item.items():
                        uit.append(f"  {'- ' if eerste else '  '}{ik}: {_yaml_scalar(iv)}" if not isinstance(iv, list)
                                   else f"  {'- ' if eerste else '  '}{ik}: [{', '.join(_yaml_scalar(x) for x in iv)}]")
                        eerste = False
                else:
                    uit.append(f'  - {_yaml_scalar(item)}')
        else:
            uit.append(f'{k}: {_yaml_scalar(v)}')
    return '\n'.join(uit)


def _scalar(s):
    s = s.strip()
    if s in ('', 'null', '~'):
        return None
    if s in ('true', 'false'):
        return s == 'true'
    if s.startswith('"'):
        return json.loads(s)
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    if s.startswith('[') and s.endswith(']'):
        binnen = s[1:-1].strip()
        return [_scalar(x) for x in re.findall(r'"(?:\\.|[^"])*"|\'[^\']*\'|[^,]+', binnen)] if binnen else []
    if re.fullmatch(r'-?\d+', s):
        return int(s)
    return s


def _lees_yaml_eenvoudig(tekst):
    """Leest het subset dat maak_yaml schrijft, plus gangbare Obsidian-notatie."""
    regels = [r.rstrip() for r in tekst.split('\n') if r.strip() and not r.lstrip().startswith('#')]
    uit, i = {}, 0
    while i < len(regels):
        m = re.match(r'^([^\s:][^:]*):(.*)$', regels[i])
        if not m:
            i += 1
            continue
        sleutel, rest = m.group(1).strip(), m.group(2).strip()
        i += 1
        if rest:
            uit[sleutel] = _scalar(rest)
            continue
        lijst = []
        while i < len(regels) and regels[i].startswith((' ', '-')):
            r = regels[i].strip()
            if r.startswith('- '):
                inhoud = r[2:]
                km = re.match(r'^([\w ]+):\s*(.*)$', inhoud)
                if km and not inhoud.startswith(('"', "'", '[')):
                    item = {km.group(1).strip(): _scalar(km.group(2))}
                    i += 1
                    while i < len(regels) and regels[i].startswith('    ') and not regels[i].strip().startswith('- '):
                        km2 = re.match(r'^\s+([\w ]+):\s*(.*)$', regels[i])
                        if km2:
                            item[km2.group(1).strip()] = _scalar(km2.group(2))
                        i += 1
                    lijst.append(item)
                    continue
                lijst.append(_scalar(inhoud))
            i += 1
        uit[sleutel] = lijst if lijst else None
    return uit


def lees_yaml(tekst):
    try:
        import yaml  # PyYAML, als het geïnstalleerd is: kan ook met de hand bewerkte bestanden aan
        data = yaml.safe_load(tekst) or {}
    except ImportError:
        data = _lees_yaml_eenvoudig(tekst)

    def normaal(v):
        if isinstance(v, (dt.date, dt.datetime)):
            return v.isoformat()
        if isinstance(v, list):
            return [normaal(x) for x in v]
        if isinstance(v, dict):
            return {k: normaal(x) for k, x in v.items()}
        return v
    return normaal(data) if isinstance(data, dict) else {}


def splits(tekst):
    tekst = tekst.replace('\r\n', '\n').lstrip('﻿')
    if tekst.startswith('---\n'):
        einde = tekst.find('\n---', 4)
        if einde != -1:
            return lees_yaml(tekst[4:einde]), tekst[einde + 4:].lstrip('\n')
    return {}, tekst


def maak_bestand(paren, body):
    return f"---\n{maak_yaml(paren)}\n---\n\n{body.strip()}\n" if body and body.strip() else f"---\n{maak_yaml(paren)}\n---\n"


# ───────────────────────── koppelingen en bestandsnamen ─────────────────────────

def link(stam):
    return f'[[{stam}]]' if stam else None


def ontlink(v):
    if not v:
        return None
    s = str(v).strip()
    m = re.match(r'^\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]$', s)
    s = m.group(1) if m else s
    return os.path.basename(s[:-3] if s.endswith('.md') else s).strip()


def veilige_naam(s, max_len=90):
    s = re.sub(r'[\\/:*?"<>|#^\[\]\n\r\t]', '-', str(s))
    s = re.sub(r'\s+', ' ', s).strip(' .-')
    return s[:max_len].rstrip(' .-') or 'zonder titel'


def handtekening(data_map):
    """Vingerafdruk van alle .md-bestanden: verandert zodra iemand een bestand toevoegt, wijzigt of weghaalt."""
    h = hashlib.sha1()
    for soort, map_ in MAPPEN.items():
        p = os.path.join(data_map, map_)
        if not os.path.isdir(p):
            continue
        for naam in sorted(os.listdir(p)):
            if naam.endswith('.md'):
                st = os.stat(os.path.join(p, naam))
                h.update(f'{map_}/{naam}:{st.st_mtime_ns}:{st.st_size};'.encode())
    return h.hexdigest()


# ───────────────────────── tekstdelen in de body ─────────────────────────

def secties(body):
    """Splitst een body in (voortekst, {kop: tekst}) op '## '-koppen."""
    delen = re.split(r'^## +(.+)$', body, flags=re.M)
    voor = delen[0].strip()
    rest = {}
    for k, t in zip(delen[1::2], delen[2::2]):
        rest[k.strip()] = t.strip()
    return voor, rest


# ───────────────────────── importeren ─────────────────────────

TABELLEN_WISSEN = ['actie_voortgang', 'actie_uitvoerder', 'actie', 'besluit_betrokkene', 'besluit_grondslag', 'besluit_onderwerp',
                   'besluit', 'stuk', 'agendapunt_onderwerp', 'agendapunt', 'deelname', 'vergadering', 'onderwerp',
                   'lidmaatschap', 'persoon', 'bedrijfsonderdeel', 'bestand']


def importeer(con, data_map):
    """Leest alle bestanden in en bouwt de database opnieuw op. Geeft het aantal bestanden terug dat een nieuwe id kreeg.

    Een bestand dat niet te gebruiken is (bijv. een verwijzing naar een vergadering die niet bestaat) wordt overgeslagen
    en in PROBLEMEN gemeld. Het bestand zelf blijft onaangeroerd: het staat dan niet in de tabel 'bestand',
    dus exporteer() zal het nooit overschrijven of verwijderen.
    """
    PROBLEMEN.clear()
    con.execute('PRAGMA foreign_keys = OFF')
    for t in TABELLEN_WISSEN:
        con.execute(f'DELETE FROM {t}')
    bestanden = {s: [] for s in MAPPEN}
    for soort, map_ in MAPPEN.items():
        p = os.path.join(data_map, map_)
        if not os.path.isdir(p):
            continue
        for naam in sorted(os.listdir(p)):
            if not naam.endswith('.md'):
                continue
            with open(os.path.join(p, naam), encoding='utf-8') as f:
                fm, body = splits(f.read())
            bestanden[soort].append({'stam': naam[:-3], 'pad': f'{map_}/{naam}', 'fm': fm, 'body': body})

    # ids toekennen (bestaande ids blijven, nieuwe bestanden krijgen de volgende vrije)
    nieuw = 0
    for soort, lijst in bestanden.items():
        gebruikt = set()
        for b in lijst:
            i = b['fm'].get('id')
            b['id'] = i if isinstance(i, int) and i not in gebruikt else None
            if b['id']:
                gebruikt.add(b['id'])
        volgende = max(gebruikt, default=0)
        for b in lijst:
            if not b['id']:
                volgende += 1; b['id'] = volgende; nieuw += 1
    stam = {}
    for soort, lijst in bestanden.items():
        for b in lijst:
            stam[b['stam']] = (soort, b['id'])
            con.execute('INSERT INTO bestand(soort, id, pad) VALUES (?,?,?)', (soort, b['id'], b['pad']))

    def ref(v, soort):
        s = stam.get(ontlink(v)) if v else None
        return s[1] if s and s[0] == soort else None

    def mist(veld, waarde):
        return f'{veld} {waarde!r} niet gevonden' if waarde else f'{veld} ontbreekt'

    def overslaan(b, soort, reden):
        PROBLEMEN.append({'pad': b['pad'], 'reden': reden})
        print(f"Overgeslagen: {b['pad']}: {reden}", file=sys.stderr)
        con.execute('DELETE FROM bestand WHERE soort = ? AND id = ?', (soort, b['id']))
        stam.pop(b['stam'], None)

    def voeg_toe(b, soort, sql, args):
        try:
            con.execute(sql, args)
            return True
        except sqlite3.IntegrityError as e:
            overslaan(b, soort, f'ongeldige of dubbele waarde ({e})')
            return False

    def refs(v, soort):
        return [x for x in (ref(i, soort) for i in (v or [])) if x]

    def audit(fm):
        return [fm.get(k) for k in AUDIT]

    def tekst(v):
        return None if v is None else str(v)

    for b in bestanden['bedrijfsonderdeel']:
        fm = b['fm']
        voeg_toe(b, 'bedrijfsonderdeel', f'INSERT INTO bedrijfsonderdeel(id, naam, afkorting, soort, actief, {",".join(AUDIT)}) VALUES (?,?,?,?,?,?,?,?,?)',
                    (b['id'], fm.get('naam') or b['stam'].removeprefix(VOORVOEGSEL['bedrijfsonderdeel']).strip(),
                     tekst(fm.get('afkorting')) or f"O{b['id']}", fm.get('soort') or 'team', 0 if fm.get('actief') is False else 1, *audit(fm)))
    for b in bestanden['bedrijfsonderdeel']:
        con.execute('UPDATE bedrijfsonderdeel SET valt_onder = ? WHERE id = ?', (ref(b['fm'].get('valt_onder'), 'bedrijfsonderdeel'), b['id']))
    for b in bestanden['persoon']:
        fm = b['fm']
        naamdelen = b['stam'].removeprefix(VOORVOEGSEL['persoon']).strip().split(' ', 1)
        voeg_toe(b, 'persoon', f'''INSERT INTO persoon(id, voornaam, achternaam, email, functie, bedrijfsonderdeel, telefoon, foto, actief, {",".join(AUDIT)})
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (b['id'], fm.get('voornaam') or naamdelen[0], fm.get('achternaam') or (naamdelen[1] if len(naamdelen) > 1 else ''),
                     fm.get('email') or f"persoon{b['id']}@onbekend", fm.get('functie'), ref(fm.get('bedrijfsonderdeel'), 'bedrijfsonderdeel'),
                     tekst(fm.get('telefoon')), fm.get('foto'), 0 if fm.get('actief') is False else 1, *audit(fm)))
    for b in bestanden['bedrijfsonderdeel']:
        for lid in b['fm'].get('leden') or []:
            if isinstance(lid, dict) and ref(lid.get('persoon'), 'persoon'):
                con.execute('INSERT OR IGNORE INTO lidmaatschap(bedrijfsonderdeel, persoon, rol) VALUES (?,?,?)',
                            (b['id'], ref(lid.get('persoon'), 'persoon'), lid.get('rol') or 'lid'))
    for b in bestanden['onderwerp']:
        fm = b['fm']
        voeg_toe(b, 'onderwerp', f'INSERT INTO onderwerp(id, naam, omschrijving, portefeuillehouder, trefwoorden, {",".join(AUDIT)}) VALUES (?,?,?,?,?,?,?,?,?)',
                    (b['id'], fm.get('naam') or b['stam'].removeprefix(VOORVOEGSEL['onderwerp']).strip(), b['body'].strip() or None,
                     ref(fm.get('portefeuillehouder'), 'persoon'), tekst(fm.get('trefwoorden')), *audit(fm)))

    # vergaderingen met agenda en aanwezigheid
    punt_ids = set()
    for b in bestanden['vergadering']:
        for p in b['fm'].get('agenda') or []:
            if isinstance(p, dict) and isinstance(p.get('id'), int):
                punt_ids.add(p['id'])
    volgend_punt = max(punt_ids, default=0)
    for b in bestanden['vergadering']:
        fm = b['fm']
        voor, kopjes = secties(b['body'])
        if not ref(fm.get('bedrijfsonderdeel'), 'bedrijfsonderdeel'):
            overslaan(b, 'vergadering', mist('bedrijfsonderdeel', fm.get('bedrijfsonderdeel')))
            continue
        if not voeg_toe(b, 'vergadering', f'''INSERT INTO vergadering(id, bedrijfsonderdeel, datum, begintijd, eindtijd, titel, locatie, status, samenvatting, {",".join(AUDIT)})
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (b['id'], ref(fm.get('bedrijfsonderdeel'), 'bedrijfsonderdeel'), tekst(fm.get('datum')) or '1970-01-01',
                     tekst(fm.get('begintijd')), tekst(fm.get('eindtijd')), fm.get('titel'), fm.get('locatie'), fm.get('status') or 'gepland',
                     voor or None, *audit(fm))):
            continue
        for d in fm.get('aanwezigheid') or []:
            if isinstance(d, dict) and ref(d.get('persoon'), 'persoon'):
                con.execute('INSERT OR IGNORE INTO deelname(vergadering, persoon, rol, aanwezigheid) VALUES (?,?,?,?)',
                            (b['id'], ref(d.get('persoon'), 'persoon'), d.get('rol') or 'lid', d.get('aanwezigheid') or 'aanwezig'))
        meta = {p['id']: p for p in (fm.get('agenda') or []) if isinstance(p, dict) and isinstance(p.get('id'), int)}
        gezien = set()
        for kop, inhoud in kopjes.items():
            m = re.match(r'^(\d+)\.\s*(.*?)(?:\s+\^p(\d+))?$', kop)
            if not m:
                continue
            nr, titel, pid = int(m.group(1)), m.group(2).strip(), int(m.group(3)) if m.group(3) else None
            if not pid or pid in gezien:
                volgend_punt += 1; pid = volgend_punt; nieuw += 1
            gezien.add(pid)
            pm = meta.get(pid, {})
            con.execute('INSERT INTO agendapunt(id, vergadering, volgnummer, titel, soort, inbrenger, bespreking) VALUES (?,?,?,?,?,?,?)',
                        (pid, b['id'], nr, titel, pm.get('soort'), ref(pm.get('inbrenger'), 'persoon'), inhoud or None))
            for o in refs(pm.get('onderwerpen'), 'onderwerp'):
                con.execute('INSERT OR IGNORE INTO agendapunt_onderwerp(agendapunt, onderwerp) VALUES (?,?)', (pid, o))
    for b in bestanden['vergadering']:
        con.execute('UPDATE vergadering SET vastgesteld_in = ? WHERE id = ?', (ref(b['fm'].get('vastgesteld_in'), 'vergadering'), b['id']))

    def punt(v, vergadering_id):
        r = con.execute('SELECT id FROM agendapunt WHERE id = ? AND vergadering = ?', (v, vergadering_id)).fetchone() if isinstance(v, int) else None
        return r[0] if r else None

    for b in bestanden['stuk']:
        fm = b['fm']
        vid = ref(fm.get('vergadering'), 'vergadering')
        if not vid:
            overslaan(b, 'stuk', mist('vergadering', fm.get('vergadering')))
            continue
        pad = str(fm.get('bestand') or '')
        if pad.startswith(BIJLAGEN_MAP + '/') or pad.startswith(BIJLAGEN_MAP + os.sep):
            pad = pad[len(BIJLAGEN_MAP) + 1:]
        voeg_toe(b, 'stuk', f'''INSERT INTO stuk(id, titel, bestandsnaam, bestandspad, mime, grootte, vergadering, agendapunt, soort, auteur, versie, datum,
                          vertrouwelijkheid, inhoud_tekst, {",".join(AUDIT)}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (b['id'], fm.get('titel') or b['stam'].removeprefix(VOORVOEGSEL['stuk']).strip(), fm.get('bestandsnaam') or os.path.basename(pad),
                     pad, fm.get('mime'), fm.get('grootte'), vid, punt(fm.get('agendapunt'), vid), fm.get('soort'), ref(fm.get('auteur'), 'persoon'),
                     tekst(fm.get('versie')), tekst(fm.get('datum')), fm.get('vertrouwelijkheid') or 'intern', b['body'].strip() or None, *audit(fm)))
    for b in bestanden['besluit']:
        fm = b['fm']
        vid = ref(fm.get('vergadering'), 'vergadering')
        voor, kopjes = secties(b['body'])
        if not vid:
            overslaan(b, 'besluit', mist('vergadering', fm.get('vergadering')))
            continue
        if not voeg_toe(b, 'besluit', f'''INSERT INTO besluit(id, nummer, titel, besluittekst, motivering, vergadering, agendapunt, status, {",".join(AUDIT)})
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (b['id'], tekst(fm.get('nummer')) or f"ZONDER-NUMMER-{b['id']}", fm.get('titel') or b['stam'].removeprefix(VOORVOEGSEL['besluit']).strip(),
                     voor or '(geen besluittekst)', kopjes.get('Motivering') or None, vid, punt(fm.get('agendapunt'), vid), fm.get('status') or 'genomen', *audit(fm))):
            continue
        for o in refs(fm.get('onderwerpen'), 'onderwerp'):
            con.execute('INSERT OR IGNORE INTO besluit_onderwerp VALUES (?,?)', (b['id'], o))
        for s in refs(fm.get('grondslag'), 'stuk'):
            con.execute('INSERT OR IGNORE INTO besluit_grondslag VALUES (?,?)', (b['id'], s))
        for p in refs(fm.get('betrokkenen'), 'persoon'):
            con.execute('INSERT OR IGNORE INTO besluit_betrokkene VALUES (?,?)', (b['id'], p))
    for b in bestanden['besluit']:
        if b['stam'] not in stam:
            continue
        con.execute('UPDATE besluit SET vervangt = ? WHERE id = ?', (ref(b['fm'].get('vervangt'), 'besluit'), b['id']))
    for b in bestanden['actie']:
        fm = b['fm']
        vid = ref(fm.get('vergadering'), 'vergadering')
        voor, kopjes = secties(b['body'])
        if not vid:
            overslaan(b, 'actie', mist('vergadering', fm.get('vergadering')))
            continue
        if not ref(fm.get('eigenaar'), 'persoon'):
            overslaan(b, 'actie', mist('eigenaar', fm.get('eigenaar')) + ' (een actie heeft precies één eigenaar nodig)')
            continue
        if not voeg_toe(b, 'actie', f'''INSERT INTO actie(id, titel, omschrijving, eigenaar, deadline, status, vergadering, agendapunt, besluit, afgerond_op, {",".join(AUDIT)})
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (b['id'], fm.get('titel') or b['stam'].removeprefix(VOORVOEGSEL['actie']).strip(), voor or None, ref(fm.get('eigenaar'), 'persoon'),
                     tekst(fm.get('deadline')), fm.get('status') or 'open', vid, punt(fm.get('agendapunt'), vid), ref(fm.get('besluit'), 'besluit'),
                     tekst(fm.get('afgerond_op')), *audit(fm))):
            continue
        for p in refs(fm.get('uitvoerders'), 'persoon'):
            con.execute('INSERT OR IGNORE INTO actie_uitvoerder VALUES (?,?)', (b['id'], p))
        for regel in (kopjes.get('Voortgang') or '').splitlines():
            m = re.match(r'^[-*]\s+(\d{4}-\d\d-\d\d)(?:\s+·\s+([^:]+))?:\s*(.+)$', regel.strip())
            if m:
                con.execute('INSERT INTO actie_voortgang(actie, datum, tekst, aangemaakt_door) VALUES (?,?,?,?)', (b['id'], m.group(1), m.group(3).strip(), m.group(2)))
    con.execute('PRAGMA foreign_keys = ON')
    return nieuw


# ───────────────────────── exporteren ─────────────────────────

def exporteer(con, data_map):
    """Schrijft elk record naar zijn bestand. Alleen gewijzigde bestanden worden aangeraakt; weggehaalde records verdwijnen."""
    paden = {(r[0], r[1]): r[2] for r in con.execute('SELECT soort, id, pad FROM bestand')}
    stammen = {os.path.basename(p)[:-3] for p in paden.values()}

    def basis(soort, r):
        if soort == 'bedrijfsonderdeel':
            return r['naam']
        if soort == 'persoon':
            return f"{r['voornaam']} {r['achternaam']}"
        if soort == 'onderwerp':
            return r['naam']
        if soort == 'vergadering':
            return f"{r['datum']} {r['afkorting']}"
        if soort == 'besluit':
            return f"{r['nummer']} {r['titel']}"
        return r['titel']

    rijen = {
        'bedrijfsonderdeel': con.execute('SELECT * FROM bedrijfsonderdeel ORDER BY id').fetchall(),
        'persoon': con.execute('SELECT * FROM persoon ORDER BY id').fetchall(),
        'onderwerp': con.execute('SELECT * FROM onderwerp ORDER BY id').fetchall(),
        'vergadering': con.execute('SELECT v.*, o.afkorting FROM vergadering v JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel ORDER BY v.id').fetchall(),
        'stuk': con.execute('SELECT * FROM stuk ORDER BY id').fetchall(),
        'besluit': con.execute('SELECT * FROM besluit ORDER BY id').fetchall(),
        'actie': con.execute('SELECT * FROM actie ORDER BY id').fetchall(),
    }
    # eerst alle bestandsnamen vastleggen, zodat koppelingen kloppen
    for soort, lijst in rijen.items():
        for r in lijst:
            if (soort, r['id']) not in paden:
                stam = f"{VOORVOEGSEL[soort]} {veilige_naam(basis(soort, r))}"
                kandidaat, n = stam, 2
                while kandidaat in stammen:
                    kandidaat = f'{stam} ({n})'; n += 1
                stammen.add(kandidaat)
                paden[(soort, r['id'])] = f'{MAPPEN[soort]}/{kandidaat}.md'
                con.execute('INSERT OR REPLACE INTO bestand(soort, id, pad) VALUES (?,?,?)', (soort, r['id'], paden[(soort, r['id'])]))

    def L(soort, i):
        return link(os.path.basename(paden[(soort, i)])[:-3]) if i and (soort, i) in paden else None

    def lijst(sql, args, soort):
        return [L(soort, r[0]) for r in con.execute(sql, args)]

    def audit(r):
        return [(k, r[k]) for k in AUDIT if r[k]]

    inhoud = {}
    for r in rijen['bedrijfsonderdeel']:
        leden = [{'persoon': L('persoon', p), 'rol': rol} for p, rol in con.execute(
            "SELECT persoon, rol FROM lidmaatschap WHERE bedrijfsonderdeel = ? ORDER BY rol != 'voorzitter', persoon", (r['id'],))]
        inhoud[('bedrijfsonderdeel', r['id'])] = maak_bestand(
            [('id', r['id']), ('type', 'bedrijfsonderdeel'), ('naam', r['naam']), ('afkorting', r['afkorting']), ('soort', r['soort']),
             ('valt_onder', L('bedrijfsonderdeel', r['valt_onder'])), ('actief', bool(r['actief'])), ('leden', leden), *audit(r)], '')
    for r in rijen['persoon']:
        inhoud[('persoon', r['id'])] = maak_bestand(
            [('id', r['id']), ('type', 'persoon'), ('voornaam', r['voornaam']), ('achternaam', r['achternaam']), ('functie', r['functie']),
             ('email', r['email']), ('telefoon', r['telefoon']), ('bedrijfsonderdeel', L('bedrijfsonderdeel', r['bedrijfsonderdeel'])),
             ('foto', r['foto']), ('actief', bool(r['actief'])), *audit(r)], '')
    for r in rijen['onderwerp']:
        inhoud[('onderwerp', r['id'])] = maak_bestand(
            [('id', r['id']), ('type', 'onderwerp'), ('naam', r['naam']), ('portefeuillehouder', L('persoon', r['portefeuillehouder'])),
             ('trefwoorden', r['trefwoorden']), *audit(r)], r['omschrijving'] or '')
    for r in rijen['vergadering']:
        aanw = [{'persoon': L('persoon', p), 'rol': rol, 'aanwezigheid': a} for p, rol, a in con.execute(
            '''SELECT persoon, rol, aanwezigheid FROM deelname WHERE vergadering = ?
               ORDER BY CASE rol WHEN 'voorzitter' THEN 0 WHEN 'lid' THEN 1 WHEN 'notulist' THEN 2 ELSE 3 END, persoon''', (r['id'],))]
        punten = con.execute('SELECT * FROM agendapunt WHERE vergadering = ? ORDER BY volgnummer, id', (r['id'],)).fetchall()
        agenda, body = [], [r['samenvatting'] or '']
        for p in punten:
            agenda.append({'id': p['id'], 'soort': p['soort'], 'inbrenger': L('persoon', p['inbrenger']),
                           'onderwerpen': lijst('SELECT onderwerp FROM agendapunt_onderwerp WHERE agendapunt = ? ORDER BY onderwerp', (p['id'],), 'onderwerp')})
            body.append(f"## {p['volgnummer']}. {p['titel']} ^p{p['id']}\n\n{p['bespreking'] or ''}".rstrip())
        inhoud[('vergadering', r['id'])] = maak_bestand(
            [('id', r['id']), ('type', 'vergadering'), ('bedrijfsonderdeel', L('bedrijfsonderdeel', r['bedrijfsonderdeel'])), ('datum', r['datum']),
             ('begintijd', r['begintijd']), ('eindtijd', r['eindtijd']), ('titel', r['titel']), ('locatie', r['locatie']), ('status', r['status']),
             ('vastgesteld_in', L('vergadering', r['vastgesteld_in'])), ('aanwezigheid', aanw), ('agenda', agenda), *audit(r)],
            '\n\n'.join(b for b in body if b))
    for r in rijen['stuk']:
        inhoud[('stuk', r['id'])] = maak_bestand(
            [('id', r['id']), ('type', 'stuk'), ('titel', r['titel']), ('vergadering', L('vergadering', r['vergadering'])), ('agendapunt', r['agendapunt']),
             ('soort', r['soort']), ('auteur', L('persoon', r['auteur'])), ('versie', r['versie']), ('datum', r['datum']),
             ('vertrouwelijkheid', r['vertrouwelijkheid']), ('bestand', f"{BIJLAGEN_MAP}/{r['bestandspad']}".replace(os.sep, '/')),
             ('bestandsnaam', r['bestandsnaam']), ('mime', r['mime']), ('grootte', r['grootte']), *audit(r)], r['inhoud_tekst'] or '')
    for r in rijen['besluit']:
        body = r['besluittekst'] + (f"\n\n## Motivering\n\n{r['motivering']}" if r['motivering'] else '')
        inhoud[('besluit', r['id'])] = maak_bestand(
            [('id', r['id']), ('type', 'besluit'), ('nummer', r['nummer']), ('titel', r['titel']), ('status', r['status']),
             ('vergadering', L('vergadering', r['vergadering'])), ('agendapunt', r['agendapunt']), ('vervangt', L('besluit', r['vervangt'])),
             ('onderwerpen', lijst('SELECT onderwerp FROM besluit_onderwerp WHERE besluit = ? ORDER BY onderwerp', (r['id'],), 'onderwerp')),
             ('grondslag', lijst('SELECT stuk FROM besluit_grondslag WHERE besluit = ? ORDER BY stuk', (r['id'],), 'stuk')),
             ('betrokkenen', lijst('SELECT persoon FROM besluit_betrokkene WHERE besluit = ? ORDER BY persoon', (r['id'],), 'persoon')), *audit(r)], body)
    for r in rijen['actie']:
        voortgang = con.execute('SELECT datum, tekst, aangemaakt_door FROM actie_voortgang WHERE actie = ? ORDER BY datum, id', (r['id'],)).fetchall()
        body = (r['omschrijving'] or '').strip()
        if voortgang:
            body += '\n\n## Voortgang\n\n' + '\n'.join(f"- {d}{' · ' + door if door else ''}: {t}" for d, t, door in voortgang)
        inhoud[('actie', r['id'])] = maak_bestand(
            [('id', r['id']), ('type', 'actie'), ('titel', r['titel']), ('status', r['status']), ('eigenaar', L('persoon', r['eigenaar'])),
             ('uitvoerders', lijst('SELECT persoon FROM actie_uitvoerder WHERE actie = ? ORDER BY persoon', (r['id'],), 'persoon')),
             ('deadline', r['deadline']), ('afgerond_op', r['afgerond_op']), ('vergadering', L('vergadering', r['vergadering'])),
             ('agendapunt', r['agendapunt']), ('besluit', L('besluit', r['besluit'])), *audit(r)], body)

    geschreven = 0
    for sleutel, tekst in inhoud.items():
        pad = os.path.join(data_map, paden[sleutel])
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        try:
            with open(pad, encoding='utf-8') as f:
                if f.read() == tekst:
                    continue
        except FileNotFoundError:
            pass
        with open(pad, 'w', encoding='utf-8') as f:
            f.write(tekst)
        geschreven += 1
    for sleutel, rel in list(paden.items()):
        if sleutel not in inhoud:  # record is verwijderd
            pad = os.path.join(data_map, rel)
            if os.path.exists(pad):
                os.remove(pad)
            con.execute('DELETE FROM bestand WHERE soort = ? AND id = ?', sleutel)
    con.commit()
    return geschreven
