/* Vergaderregister — browserversie. Draait server.py in de browser met Pyodide, zodat er geen server nodig is.
   Vangt verzoeken naar api/, bijlage/ en export/ af en stuurt ze naar de Python-Handler. De gegevens staan
   in IndexedDB (per browser) en gaan na RESET_UUR, of na een nieuwe publicatie, terug naar de meegeleverde
   demodata. "Demogegevens terugzetten" doet dat meteen. */
'use strict';
(() => {
  const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/';
  const BASIS = new URL('.', location.href).pathname;
  const APP = '/app', DATA = '/app/data', STEMPEL = DATA + '/.demo.json';
  const RESET_UUR = 4;

  const PY_WIS = `
import os, shutil

def wis_data():
    for naam in os.listdir('${DATA}'):
        p = os.path.join('${DATA}', naam)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
`;

  const PY_BRUG = `
import io, json, os, sys
sys.path.insert(0, '/app')
os.environ['STIL'] = '1'
import server

class _Koppen(dict):
    def get(self, k, d=None):
        for kk, v in self.items():
            if kk.lower() == k.lower():
                return v
        return d

class BrowserVerzoek(server.Handler):
    """Dezelfde Handler als de echte server, maar zonder socket: het antwoord gaat terug naar JavaScript."""
    def __init__(self, methode, pad, koppen, body):
        self.command, self.path = methode, pad
        self.headers, self.rfile = _Koppen(koppen), io.BytesIO(body)
        self.antwoord = None

    def stuur(self, code, body, ctype='application/json; charset=utf-8', extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.antwoord = [code, ctype, json.dumps(extra or {}), body]

def verzoek(methode, pad, koppen, body):
    v = BrowserVerzoek(methode, pad, koppen.to_py(), bytes(body.to_py()) if body is not None else b'')
    v.afhandelen(methode)
    return v.antwoord

server.init_db()
`;

  let py = null, versie = '';
  const meld = t => { const el = document.querySelector('#main .laden'); if (el) el.textContent = t; };
  const syncfs = vullen => new Promise((ok, fout) => py.FS.syncfs(vullen, e => (e ? fout(e) : ok())));
  const haal = async pad => new Uint8Array(await (await fetch(BASIS + pad, { cache: 'no-store' })).arrayBuffer());

  // Wanneer zijn de demodata in deze browser voor het laatst ingeladen, en van welke publicatie?
  const stempel = () => { try { return JSON.parse(py.FS.readFile(STEMPEL, { encoding: 'utf8' })); } catch { return null; } };
  const resetOm = () => { const s = stempel(); return s ? new Date(s.tijd + RESET_UUR * 3600e3) : null; };
  const verlopen = () => { const s = stempel(); return !s || s.versie !== versie || Date.now() >= resetOm().getTime(); };

  const klaar = (async () => {
    meld('Vergaderregister wordt geladen… (de eerste keer duurt dit even)');
    await new Promise((ok, fout) => {
      const s = document.createElement('script');
      s.src = PYODIDE + 'pyodide.js'; s.onload = ok; s.onerror = () => fout(new Error('Pyodide kon niet worden geladen. Is er internet?'));
      document.head.appendChild(s);
    });
    py = await loadPyodide({ indexURL: PYODIDE });
    meld('Gegevens worden klaargezet…');
    await py.loadPackage('sqlite3');
    py.FS.mkdirTree(DATA);
    py.FS.mount(py.FS.filesystems.IDBFS, {}, DATA);
    await syncfs(true);
    py.unpackArchive(await haal('app.zip'), 'zip', { extractDir: APP });
    versie = new TextDecoder().decode(await haal('versie.txt')).trim();
    py.runPython(PY_WIS);
    if (verlopen()) {  // eerste bezoek, na terugzetten, na RESET_UUR of na een nieuwe publicatie
      py.globals.get('wis_data')();
      py.unpackArchive(await haal('data.zip'), 'zip', { extractDir: DATA });
      py.FS.writeFile(STEMPEL, JSON.stringify({ versie, tijd: Date.now() }));
    }
    py.runPython(PY_BRUG);
    await syncfs(false);
    return py.globals.get('verzoek');
  })();
  klaar.catch(e => meld(e.message));

  // Eén verzoek tegelijk, zodat het wegschrijven naar IndexedDB niet door elkaar loopt.
  let rij = Promise.resolve();
  const opslaan = () => (rij = rij.then(() => syncfs(false)).catch(console.error));

  function voerUit(verzoek, methode, pad, koppen, body) {
    const r = verzoek(methode, pad, koppen, body || null);
    const [code, ctype, extra, data] = r.toJs();
    r.destroy();
    return { code, ctype, extra: JSON.parse(extra), data };
  }

  const relatief = url => (url.origin === location.origin && url.pathname.startsWith(BASIS) ? url.pathname.slice(BASIS.length) : null);

  const echteFetch = window.fetch.bind(window);
  window.fetch = async (invoer, opties = {}) => {
    const url = new URL(typeof invoer === 'string' ? invoer : invoer.url, location.href);
    const rel = relatief(url);
    if (rel === null || !rel.startsWith('api/')) return echteFetch(invoer, opties);
    const verzoek = await klaar;
    const methode = (opties.method || 'GET').toUpperCase();
    let body = opties.body;
    if (typeof body === 'string') body = new TextEncoder().encode(body);
    else if (body instanceof Blob) body = new Uint8Array(await body.arrayBuffer());
    const koppen = { ...(opties.headers || {}) };
    if (body) koppen['Content-Length'] = String(body.length);
    const a = voerUit(verzoek, methode, '/' + rel + url.search, koppen, body);
    if (methode !== 'GET') await opslaan();
    return new Response(a.data, { status: a.code, headers: { 'Content-Type': a.ctype } });
  };

  // Links naar bijlagen en exports: in de browser maken en openen of downloaden.
  document.addEventListener('click', async e => {
    const link = e.target.closest('a[href]');
    if (!link || e.defaultPrevented || e.button !== 0) return;
    const rel = relatief(new URL(link.href));
    if (rel === null || !/^(bijlage|export)\//.test(rel)) return;
    e.preventDefault();
    const venster = rel.startsWith('bijlage/') ? window.open('', '_blank') : null;  // nu openen, anders blokkeert de browser het
    const a = voerUit(await klaar, 'GET', '/' + rel, {}, null);
    if (a.code !== 200) { venster?.close(); alert(JSON.parse(new TextDecoder().decode(a.data)).fout || 'Niet gevonden'); return; }
    const blobUrl = URL.createObjectURL(new Blob([a.data], { type: a.ctype }));
    if (venster) { venster.location = blobUrl; return; }
    const m = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/.exec(a.extra['Content-Disposition'] || '');
    const d = Object.assign(document.createElement('a'), { href: blobUrl, download: m ? decodeURIComponent(m[1] || m[2]) : rel.split('/').pop() });
    document.body.appendChild(d); d.click(); d.remove();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
  }, true);

  // Uitleg en terugzetknop onder in de zijbalk.
  document.addEventListener('DOMContentLoaded', () => {
    const voet = document.querySelector('.zijbalk-voet');
    if (!voet) return;
    const uitleg = Object.assign(document.createElement('p'), { className: 'gedempt klein demo-uitleg',
      textContent: `Demo: je wijzigingen blijven alleen in deze browser bewaard en worden elke ${RESET_UUR} uur teruggezet.` });
    klaar.then(() => {
      const om = resetOm();
      if (om) uitleg.textContent += ` Volgende keer: ${om.toLocaleString('nl-NL', { weekday: 'short', hour: '2-digit', minute: '2-digit' })}.`;
    });
    const stijl = Object.assign(document.createElement('style'), {
      textContent: '.demo-uitleg { margin: 4px 0 0; } @media (max-width: 900px) { .demo-uitleg { display: none; } }' });
    const terug = Object.assign(document.createElement('a'), { className: 'link-klein', href: '#', textContent: 'Demogegevens terugzetten' });
    terug.addEventListener('click', async e => {
      e.preventDefault();
      if (!confirm('Al je wijzigingen in deze browser wissen en opnieuw beginnen met de demodata?')) return;
      await klaar;
      py.globals.get('wis_data')();
      await syncfs(false);
      location.reload();
    });
    document.head.appendChild(stijl);
    voet.append(uitleg, terug);
  });

  // Staat het tabblad lang open? Bij terugkeer na de resettijd opnieuw beginnen.
  document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState !== 'visible' || !py) return;
    await klaar;
    if (Date.now() >= (resetOm()?.getTime() ?? 0)) location.reload();
  });
})();
