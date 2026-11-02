/* Vergaderregister — webinterface. Vanilla JavaScript, geen bibliotheken. */
'use strict';

// ───────────────────────── basis ─────────────────────────
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const main = $('#main');
const S = { meta: null, gebruiker: leesOpslag('gebruiker') };

function leesOpslag(k) { try { return localStorage.getItem(k) || ''; } catch { return ''; } }
function schrijfOpslag(k, v) { try { localStorage.setItem(k, v); } catch { /* geen opslag: prima */ } }

const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const frag = f => esc(f).replace(/\x01/g, '<mark>').replace(/\x02/g, '</mark>');

async function api(pad, { methode = 'GET', data, body, headers = {} } = {}) {
  const opties = { method: methode, headers: { ...headers } };
  if (S.gebruiker) opties.headers['X-Gebruiker'] = S.gebruiker;
  if (data !== undefined) { opties.body = JSON.stringify(data); opties.headers['Content-Type'] = 'application/json'; }
  if (body !== undefined) opties.body = body;
  const r = await fetch('api/' + pad, opties);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.fout || `Er ging iets mis (${r.status}).`);
  return j;
}

function toast(tekst, fout = false) {
  const t = $('#toast');
  t.textContent = tekst; t.className = 'toast' + (fout ? ' fout' : ''); t.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, fout ? 6000 : 3200);
}

const go = h => { if (location.hash === h) route(); else location.hash = h; };
const qs = obj => { const p = new URLSearchParams(); Object.entries(obj).forEach(([k, v]) => { if (v !== '' && v != null) p.set(k, v); }); const s = p.toString(); return s ? '?' + s : ''; };

// ───────────────────────── datums ─────────────────────────
const MAANDEN = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];
const MAANDEN_LANG = ['januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli', 'augustus', 'september', 'oktober', 'november', 'december'];
const DAGEN = ['zo', 'ma', 'di', 'wo', 'do', 'vr', 'za'];
const pd = d => { const [y, m, dd] = d.split('-').map(Number); return new Date(y, m - 1, dd); };
function datum(d, { dag = true, jaar = true } = {}) {
  if (!d) return '';
  const x = pd(d);
  return `${dag ? DAGEN[x.getDay()] + ' ' : ''}${x.getDate()} ${MAANDEN[x.getMonth()]}${jaar ? ' ' + x.getFullYear() : ''}`;
}
const vandaag = () => S.meta?.vandaag || new Date().toISOString().slice(0, 10);
const dagenTot = d => Math.round((pd(d) - pd(vandaag())) / 86400000);
function deadline(a) {
  if (!a.deadline) return '<span class="deadline gedempt">geen deadline</span>';
  if (a.status === 'afgerond' || a.status === 'vervallen') return `<span class="deadline gedempt">${datum(a.deadline, { dag: false })}</span>`;
  const n = dagenTot(a.deadline);
  if (n < 0) return `<span class="deadline te-laat">${-n} ${-n === 1 ? 'dag' : 'dagen'} te laat</span>`;
  if (n === 0) return '<span class="deadline binnenkort">vandaag</span>';
  if (n <= 7) return `<span class="deadline binnenkort">over ${n} ${n === 1 ? 'dag' : 'dagen'}</span>`;
  return `<span class="deadline">${datum(a.deadline, { dag: false })}</span>`;
}
function groet() { const u = new Date().getHours(); return u < 12 ? 'Goedemorgen' : u < 18 ? 'Goedemiddag' : 'Goedenavond'; }

// ───────────────────────── iconen & soorten ─────────────────────────
const PADEN = {
  overzicht: '<path d="M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 7h6V4h-6z"/>',
  zoek: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  vergadering: '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  agendapunt: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
  besluit: '<path d="M12 3 4 7v5c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V7z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  actie: '<circle cx="12" cy="12" r="8.5"/><path d="m8 12 3 3 5-6"/>',
  stuk: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  persoon: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  onderwerp: '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  onderdeel: '<path d="M4 21V8l8-5 8 5v13M9 21v-6h6v6M8 11h.01M12 11h.01M16 11h.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  bewerk: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  download: '<path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14"/>',
  links: '<path d="m15 6-6 6 6 6"/>', rechts: '<path d="m9 6 6 6-6 6"/>',
  klok: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  pin: '<path d="M12 21s-6.5-5.4-6.5-11a6.5 6.5 0 0 1 13 0c0 5.6-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
  kruis: '<path d="M6 6l12 12M18 6 6 18"/>',
  let: '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4.5M12 17.5h.01"/>',
  mensen: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c1-3.5 3.5-5 6.5-5s5.5 1.5 6.5 5M16 4.5a3.5 3.5 0 0 1 0 7M18 15c2 .6 3 2.2 3.5 5"/>',
};
const ic = (n, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${PADEN[n] || ''}</svg>`;
const SOORT = {
  vergadering: { naam: 'Vergadering', mv: 'Vergaderingen', c: '--c-verg' },
  agendapunt: { naam: 'Agendapunt', mv: 'Agendapunten', c: '--c-agenda' },
  besluit: { naam: 'Besluit', mv: 'Besluiten', c: '--c-bes' },
  actie: { naam: 'Actie', mv: 'Acties', c: '--c-act' },
  stuk: { naam: 'Stuk', mv: 'Stukken', c: '--c-stuk' },
  persoon: { naam: 'Persoon', mv: 'Personen', c: '--c-pers' },
  onderwerp: { naam: 'Onderwerp', mv: 'Onderwerpen', c: '--c-ond' },
  onderdeel: { naam: 'Bedrijfsonderdeel', mv: 'Bedrijfsonderdelen', c: '--c-org' },
};
const soortIc = s => `<span class="soort-ic" style="--c:var(${SOORT[s].c})">${ic(s)}</span>`;
const pil = (status, extra = '') => status ? `<span class="pil ${esc(status.replace(/ /g, '-'))} ${extra}">${esc(status)}</span>` : '';

function itemLink(it) {
  switch (it.soort) {
    case 'vergadering': return `#/vergadering/${it.id}`;
    case 'agendapunt': return `#/vergadering/${it.v_id}?punt=${it.id}`;
    case 'besluit': return `#/besluit/${it.id}`;
    case 'actie': return `#/actie/${it.id}`;
    case 'stuk': return `bijlage/${it.id}`;
  }
  return '#/';
}
const persoon = id => S.meta.personen.find(p => p.id === Number(id));
const naamVan = p => p ? `${p.voornaam} ${p.achternaam}` : '';
function av(foto, naam, cls = '') {
  if (foto) return `<img class="av ${cls}" src="fotos/${esc(foto)}" alt="" loading="lazy">`;
  const init = String(naam || '?').split(' ').filter(Boolean).map(w => w[0]).filter(c => c === c.toUpperCase()).slice(0, 2).join('');
  return `<span class="av ${cls}" aria-hidden="true">${esc(init || '?')}</span>`;
}
const persoonLink = (id, naam, foto, cls = 'klein') => `<a class="persoonlink" href="#/persoon/${id}">${av(foto, naam, cls)}<span>${esc(naam)}</span></a>`;
const onderdeel = id => S.meta.onderdelen.find(o => o.id === Number(id));
const grootte = n => n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' kB';

// ───────────────────────── navigatie ─────────────────────────
const NAV = [
  ['#/', 'overzicht', 'Overzicht'], ['#/zoeken', 'zoek', 'Zoeken'], null,
  ['#/vergaderingen', 'vergadering', 'Vergaderingen'], ['#/besluiten', 'besluit', 'Besluiten'], ['#/acties', 'actie', 'Acties'], null,
  ['#/onderwerpen', 'onderwerp', 'Onderwerpen'], ['#/personen', 'persoon', 'Personen'], ['#/onderdelen', 'onderdeel', 'Bedrijfsonderdelen'],
];
function tekenNav() {
  const h = location.hash || '#/';
  const basis = h.split('?')[0];
  const actief = href => href === '#/' ? basis === '#/' || basis === '' :
    basis.startsWith(href) || basis.startsWith(href.replace(/en$|s$/, ''));
  $('#hoofdnav').innerHTML = NAV.map(n => n ? `<a href="${n[0]}" class="${actief(n[0]) ? 'actief' : ''}">${ic(n[1])}<span>${n[2]}</span>${n[1] === 'actie' && S.meta?.te_laat ? `<span class="teller" title="over de deadline">${S.meta.te_laat}</span>` : ''}</a>` : '<div class="scheiding"></div>').join('');
}
function tekenGebruiker() {
  $('#gebruiker').innerHTML = '<option value="">— kies wie je bent —</option>' + S.meta.personen.filter(p => p.actief)
    .map(p => `<option value="${p.id}" ${String(p.id) === S.gebruiker ? 'selected' : ''}>${esc(naamVan(p))}</option>`).join('');
}

const ROUTES = [
  [/^\/?$/, overzicht], [/^\/zoeken$/, zoeken],
  [/^\/vergaderingen$/, vergaderingen], [/^\/vergadering\/(\d+)$/, vergadering],
  [/^\/besluiten$/, besluiten], [/^\/besluit\/(\d+)$/, besluit],
  [/^\/acties$/, acties], [/^\/actie\/(\d+)$/, actie],
  [/^\/personen$/, personen], [/^\/persoon\/(\d+)$/, persoonPagina],
  [/^\/onderwerpen$/, onderwerpen], [/^\/onderwerp\/(\d+)$/, onderwerpPagina],
  [/^\/onderdelen$/, onderdelen], [/^\/onderdeel\/(\d+)$/, onderdeelPagina],
];
let routeTeller = 0;
async function route() {
  const nr = ++routeTeller;
  const [pad, query] = (location.hash.slice(1) || '/').split('?');
  const params = new URLSearchParams(query || '');
  const gevonden = ROUTES.find(([re]) => re.test(pad));
  tekenNav();
  // focus en cursor bewaren als de pagina opnieuw tekent (bijv. tijdens typen in een zoekveld)
  const actief = document.activeElement;
  const focusId = actief && actief.id && main.contains(actief) ? actief.id : null;
  const sel = focusId && 'selectionStart' in actief ? [actief.selectionStart, actief.selectionEnd] : null;
  try {
    const html = gevonden ? await gevonden[1](pad.match(gevonden[0]), params) : '<div class="leeg">Pagina niet gevonden.</div>';
    if (nr !== routeTeller) return;
    main.innerHTML = html;
    if (focusId) { const el = document.getElementById(focusId); if (el) { el.focus(); if (sel && el.setSelectionRange) try { el.setSelectionRange(...sel); } catch { } } }
    na_render(params);
  } catch (e) {
    if (nr !== routeTeller) return;
    main.innerHTML = `<div class="paneel"><h2>Dit lukte niet</h2><p class="gedempt">${esc(e.message)}</p></div>`;
  }
}
function na_render(params) {
  const punt = params.get('punt');
  if (punt) { const el = document.getElementById('punt-' + punt); if (el) { el.scrollIntoView({ block: 'start' }); el.style.boxShadow = '0 0 0 3px var(--accent-zacht)'; } }
}
async function herlaadMeta() { S.meta = await api('meta'); tekenGebruiker(); tekenNav(); }
const herlaad = async () => { const y = scrollY; await herlaadMeta(); await route(); scrollTo(0, y); };

// ───────────────────────── gedeelde weergaven ─────────────────────────
function actieRegel(a, { metVergadering = true } = {}) {
  return `<a class="regel" href="#/actie/${a.id}">
    ${av(a.p_foto, a.p_naam, 'mid')}
    <span class="hoofd"><span class="t">${esc(a.titel)}</span>
      <span class="m"><span>${esc(a.p_naam)}</span>${metVergadering && a.v_datum ? `<span>${esc(a.afkorting || '')} · ${datum(a.v_datum, { dag: false })}</span>` : ''}</span></span>
    <span class="rechts">${deadline(a)}</span></a>`;
}
function resultaat(it) {
  const extern = it.soort === 'stuk';
  const titel = it.soort === 'besluit' ? `<code>${esc(it.nummer)}</code>${esc(it.titel)}` : esc(it.soort === 'agendapunt' ? `${it.volgnummer}. ${it.titel}` : it.titel);
  const status = it.soort === 'actie' && it.te_laat ? pil('te laat', 'te-laat') : it.soort === 'agendapunt' ? '' : pil(it.status);
  const tekst = it.fragment ? frag(it.fragment) : it.soort === 'besluit' ? esc(it.kort) : '';
  const meta = [];
  if (it.soort === 'vergadering') {
    meta.push(`<span>${esc(it.onderdeel_naam)}</span>`, it.begintijd ? `<span>${esc(it.begintijd)}</span>` : '',
      `<span>${it.n_besluiten} besluiten · ${it.n_acties} acties · ${it.n_stukken} stukken</span>`);
  } else {
    meta.push(`<span>${SOORT[it.soort].naam}</span>`, `<span>${esc(it.afkorting || '')} · ${esc(it.v_titel || '')}, ${datum(it.v_datum || it.datum, { dag: false })}</span>`);
  }
  if (it.soort === 'actie') meta.push(`<span class="persoonlink">${av(it.p_foto, it.p_naam, 'klein')}${esc(it.p_naam)}</span>`, deadline(it));
  if (it.soort === 'stuk') meta.push(`<span>${esc(it.bestandsnaam)} · ${grootte(it.grootte || 0)}</span>`);
  return `<a class="resultaat" href="${itemLink(it)}" ${extern ? 'target="_blank" rel="noopener"' : ''} style="--c:var(${SOORT[it.soort].c})">
    ${soortIc(it.soort)}
    <div style="min-width:0"><div class="t">${titel} ${status}</div>
    ${it.soort === 'vergadering' ? `<div class="frag">${datum(it.datum)}</div>` : ''}
    ${tekst ? `<div class="frag">${tekst}</div>` : ''}
    <div class="m">${meta.join('')}</div></div></a>`;
}
function datumblok(d, c = '--c-verg') {
  const x = pd(d);
  return `<span class="datumblok num" style="--c:var(${c})"><small>${MAANDEN[x.getMonth()]}</small><b>${x.getDate()}</b><span>${DAGEN[x.getDay()]}</span></span>`;
}
function vergaderRegel(v) {
  return `<a class="regel" href="#/vergadering/${v.id}">${datumblok(v.datum)}
    <span class="hoofd"><span class="t">${esc(v.titel)}</span>
    <span class="m"><span>${esc(v.onderdeel_naam || '')}</span>${v.begintijd ? `<span>${esc(v.begintijd)}</span>` : ''}${v.locatie ? `<span>${esc(v.locatie)}</span>` : ''}
    ${v.n_besluiten != null ? `<span>${v.n_besluiten} besluiten · ${v.n_acties} acties</span>` : ''}${v.n_punten != null ? `<span>${v.n_punten} agendapunten</span>` : ''}</span></span>
    <span class="rechts">${pil(v.status)}</span></a>`;
}
const leegOf = (lijst, fn, tekst) => lijst.length ? lijst.map(fn).join('') : `<div class="leeg">${tekst}</div>`;
const optie = (w, l, sel) => `<option value="${esc(w)}" ${String(sel ?? '') === String(w) ? 'selected' : ''}>${esc(l)}</option>`;
const onderdeelOpties = sel => '<option value="">Alle bedrijfsonderdelen</option>' + boomVolgorde().map(([o, d]) => optie(o.id, ' '.repeat(d) + o.naam, sel)).join('');
const persoonOpties = (sel, leeg = 'Alle personen') => `<option value="">${leeg}</option>` + S.meta.personen.map(p => optie(p.id, naamVan(p), sel)).join('');
const onderwerpOpties = sel => '<option value="">Alle onderwerpen</option>' + S.meta.onderwerpen.map(o => optie(o.id, o.naam, sel)).join('');
function boomVolgorde() {
  const uit = [];
  const loop = (ouder, d) => S.meta.onderdelen.filter(o => (o.valt_onder || null) === ouder).forEach(o => { uit.push([o, d]); loop(o.id, d + 1); });
  loop(null, 0);
  return uit;
}

// ───────────────────────── overzicht ─────────────────────────
async function overzicht() {
  const d = await api('dashboard');
  const ik = persoon(S.gebruiker);
  const k = d.kpi;
  const maxOpen = Math.max(1, ...d.per_eigenaar.map(r => r.open));
  const maxOnd = Math.max(1, ...d.per_onderdeel.map(r => r.open + r.afgerond));
  const jaar = vandaag().slice(0, 4);
  return `
  <div class="welkom">
    ${ik ? av(ik.foto, naamVan(ik), 'mid') : ''}
    <div><h1>${groet()}${ik ? ', ' + esc(ik.voornaam) : ''}</h1><p class="gedempt">${datum(vandaag())} · ${k.vergaderingen_jaar} vergaderingen en ${k.besluiten_jaar} besluiten in ${jaar}</p></div>
  </div>
  ${S.meta.problemen?.length ? `<details class="callout" style="margin-bottom:18px"><summary>${ic('let')}${S.meta.problemen.length} ${S.meta.problemen.length === 1 ? 'bestand kon' : 'bestanden konden'} niet worden ingelezen</summary>
    <p class="klein gedempt" style="margin:8px 0">Deze bestanden blijven onaangeroerd in de map data/. Pas ze aan of verwijder ze; de app leest ze daarna vanzelf opnieuw in.</p>
    <ul class="klein" style="margin:0;padding-left:18px">${S.meta.problemen.map(x => `<li><code>${esc(x.pad)}</code>: ${esc(x.reden)}</li>`).join('')}</ul></details>` : ''}
  <div class="kentallen">
    <a class="kental" href="#/acties"><span class="getal">${k.open_acties}</span><span class="wat">openstaande acties</span></a>
    <a class="kental ${k.te_laat ? 'kritiek' : ''}" href="#/acties"><span class="getal">${k.te_laat}</span><span class="wat">over de deadline</span></a>
    <a class="kental ${k.deze_week ? 'let-op' : ''}" href="#/acties"><span class="getal">${k.deze_week}</span><span class="wat">deadline deze week</span></a>
    <a class="kental" href="#/besluiten${qs({ van: jaar + '-01-01' })}"><span class="getal">${k.besluiten_jaar}</span><span class="wat">besluiten in ${jaar}</span></a>
  </div>
  ${ik ? `<div class="paneel" style="margin-bottom:18px"><div class="paneel-kop"><h2>Mijn openstaande acties</h2><a class="klein" href="#/persoon/${ik.id}">Mijn pagina</a></div>
    <div class="regels">${leegOf(d.mijn, a => actieRegel(a), 'Je hebt geen openstaande acties.')}</div></div>`
    : `<div class="paneel" style="margin-bottom:18px"><p class="gedempt">Kies linksonder wie je bent. Dan zie je hier je eigen acties en worden wijzigingen op jouw naam vastgelegd.</p></div>`}
  <div class="raster twee">
    <div class="paneel"><div class="paneel-kop"><h2>Over de deadline</h2><a class="klein" href="#/acties">Alle acties</a></div>
      <div class="regels">${leegOf(d.te_laat, a => actieRegel(a), 'Niets over de deadline.')}</div></div>
    <div class="paneel"><div class="paneel-kop"><h2>Komende vergaderingen</h2><a class="klein" href="#/vergaderingen">Alle vergaderingen</a></div>
      <div class="regels">${leegOf(d.komend, vergaderRegel, 'Geen vergaderingen gepland.')}</div>
      ${d.binnenkort.length ? `<h3 style="margin:18px 0 4px">Deadlines die eraan komen</h3><div class="regels">${d.binnenkort.slice(0, 4).map(a => actieRegel(a)).join('')}</div>` : ''}</div>
    <div class="paneel"><div class="paneel-kop"><h2>Recente besluiten</h2><a class="klein" href="#/besluiten">Besluitenregister</a></div>
      <div class="regels">${d.recente_besluiten.map(b => `<a class="regel" href="#/besluit/${b.id}">${soortIc('besluit')}
        <span class="hoofd"><span class="t">${esc(b.titel)}</span><span class="m"><span>${esc(b.nummer)}</span><span>${esc(b.onderdeel_naam)} · ${datum(b.v_datum, { dag: false })}</span></span></span>
        <span class="rechts">${pil(b.status)}</span></a>`).join('')}</div></div>
    <div class="paneel"><div class="paneel-kop"><h2>Openstaande acties per persoon</h2></div>
      ${d.per_eigenaar.map(r => `<a class="balk-rij" href="#/persoon/${r.p_id}"><span class="balk-naam">${av(r.p_foto, r.p_naam, 'klein')}<span>${esc(r.p_naam)}</span></span>
        <span class="balk"><i class="te-laat" style="width:${r.te_laat / maxOpen * 100}%"></i><i class="open" style="width:${(r.open - r.te_laat) / maxOpen * 100}%"></i></span>
        <span class="num klein">${r.open}${r.te_laat ? ` <span class="deadline te-laat">(${r.te_laat})</span>` : ''}</span></a>`).join('')}
      <h3 style="margin:18px 0 6px">Opvolging per bedrijfsonderdeel</h3>
      ${d.per_onderdeel.map(r => `<a class="balk-rij" href="#/onderdeel/${r.id}"><span class="balk-naam"><span class="afk">${esc(r.afkorting)}</span><span>${esc(r.naam)}</span></span>
        <span class="balk"><i class="te-laat" style="width:${r.te_laat / maxOnd * 100}%"></i><i class="open" style="width:${(r.open - r.te_laat) / maxOnd * 100}%"></i><i class="afgerond" style="width:${r.afgerond / maxOnd * 100}%"></i></span>
        <span class="num klein">${r.afgerond}/${r.open + r.afgerond}</span></a>`).join('')}
      <div class="legenda"><span><i style="background:var(--kritiek)"></i>te laat</span><span><i style="background:var(--accent)"></i>open</span><span><i style="background:color-mix(in srgb,var(--goed) 55%,var(--zacht))"></i>afgerond</span></div>
    </div>
  </div>`;
}

// ───────────────────────── zoeken ─────────────────────────
const STATUS_OPTIES = [
  ['Acties', ['open', 'loopt', 'te laat', 'afgerond', 'vervallen']],
  ['Besluiten', ['genomen', 'aangehouden', 'herzien', 'ingetrokken']],
  ['Vergaderingen', ['gepland', 'concept', 'vastgesteld']],
  ['Stukken', ['openbaar', 'intern', 'vertrouwelijk']],
];
function periodes() {
  const v = vandaag(), j = v.slice(0, 4);
  const terug = m => { const d = pd(v); d.setMonth(d.getMonth() - m); return d.toISOString().slice(0, 10); };
  return [['dit jaar', `${j}-01-01`, ''], ['laatste 3 maanden', terug(3), ''], ['vorig jaar', `${j - 1}-01-01`, `${j - 1}-12-31`]];
}
async function zoeken(m, p) {
  const f = Object.fromEntries(['q', 'soort', 'onderdeel', 'persoon', 'onderwerp', 'van', 'tot', 'status'].map(k => [k, p.get(k) || '']));
  const r = await api('zoek' + qs(f));
  const totaal = Object.values(r.tellingen).reduce((a, b) => a + b, 0);
  const soorten = ['vergadering', 'agendapunt', 'besluit', 'actie', 'stuk'];
  const actieveSoort = f.soort;
  const label = { onderdeel: v => onderdeel(v)?.naam, persoon: v => naamVan(persoon(v)), onderwerp: v => S.meta.onderwerpen.find(o => o.id == v)?.naam,
    van: v => 'vanaf ' + datum(v, { dag: false }), tot: v => 't/m ' + datum(v, { dag: false }), status: v => v, soort: v => SOORT[v]?.mv };
  const actief = Object.keys(label).filter(k => f[k]);
  const periodeAan = periodes().find(([, v, t]) => v === f.van && t === f.tot);
  $('#snelzoek-q').value = f.q;
  return `
  <div class="kop"><div class="titelblok"><h1>Zoeken</h1><p class="gedempt">Doorzoek alle vergaderingen, besluiten, acties, agendapunten en de tekst van bijlagen. Combineer met filters.</p></div></div>
  <div class="zoek-layout">
    <aside class="facetten">
      <div class="facet"><span class="label-klein">Soort</span>
        <div class="soortfilter">
          <button class="${!actieveSoort ? 'aan' : ''}" data-actie="zoekfilter" data-k="soort" data-v="">${ic('zoek')}Alles<span class="n">${totaal}</span></button>
          ${soorten.map(s => `<button class="${actieveSoort === s ? 'aan' : ''}" data-actie="zoekfilter" data-k="soort" data-v="${s}" style="--c:var(${SOORT[s].c})"><span class="stip"></span>${SOORT[s].mv}<span class="n">${r.tellingen[s]}</span></button>`).join('')}
        </div></div>
      <div class="facet"><label class="label-klein" for="f-onderdeel">Bedrijfsonderdeel</label><select id="f-onderdeel" data-zoekveld="onderdeel">${onderdeelOpties(f.onderdeel)}</select>
        <span class="klein gedempt">Inclusief alles wat eronder valt.</span></div>
      <div class="facet"><label class="label-klein" for="f-persoon">Persoon</label><select id="f-persoon" data-zoekveld="persoon">${persoonOpties(f.persoon)}</select>
        <span class="klein gedempt">Als eigenaar, uitvoerder, aanwezige, inbrenger, auteur of betrokkene.</span></div>
      <div class="facet"><label class="label-klein" for="f-onderwerp">Onderwerp</label><select id="f-onderwerp" data-zoekveld="onderwerp">${onderwerpOpties(f.onderwerp)}</select></div>
      <div class="facet"><span class="label-klein">Periode (vergaderdatum)</span>
        <div class="snelperiode">${periodes().map(([l, v, t]) => `<button class="${periodeAan && periodeAan[0] === l ? 'aan' : ''}" data-actie="zoekperiode" data-van="${v}" data-tot="${t}">${l}</button>`).join('')}</div>
        <div class="periode"><input type="date" id="f-van" data-zoekveld="van" value="${esc(f.van)}" aria-label="Vanaf"><input type="date" id="f-tot" data-zoekveld="tot" value="${esc(f.tot)}" aria-label="Tot en met"></div></div>
      <div class="facet"><label class="label-klein" for="f-status">Status</label><select id="f-status" data-zoekveld="status"><option value="">Alle statussen</option>
        ${STATUS_OPTIES.map(([g, os]) => `<optgroup label="${g}">${os.map(o => optie(o, o, f.status)).join('')}</optgroup>`).join('')}</select></div>
    </aside>
    <section>
      <div class="grootzoek"><input type="search" id="zoek-q" value="${esc(f.q)}" placeholder="Bijvoorbeeld: dagloon, Werkcentrum, verzekeringsarts, export…" autocomplete="off" aria-label="Zoekterm"></div>
      ${r.personen.length || r.onderwerpen.length ? `<div class="treffers-extra">
        ${r.personen.map(x => `<a class="chip" style="--c:var(--c-pers)" href="#/persoon/${x.id}">${av(x.foto, naamVan(x), 'klein')}${esc(naamVan(x))}</a>`).join('')}
        ${r.onderwerpen.map(x => `<a class="chip" style="--c:var(--c-ond)" href="#/onderwerp/${x.id}"><span class="stip"></span>${esc(x.naam)}</a>`).join('')}</div>` : ''}
      <div class="resultaat-kop"><span class="gedempt num">${r.items.length} ${r.items.length === 1 ? 'resultaat' : 'resultaten'}${f.q ? `, beste treffer eerst` : ', nieuwste eerst'}</span>
        <div class="actieve-filters">${actief.map(k => `<button data-actie="zoekfilter" data-k="${k}" data-v="" title="Filter verwijderen">${esc(label[k](f[k]) || f[k])} ${ic('kruis')}</button>`).join('')}
        ${actief.length || f.q ? `<button data-actie="zoekwis">Alles wissen</button>` : ''}</div></div>
      <div class="resultaten">${r.items.length ? r.items.slice(0, 200).map(resultaat).join('') : `<div class="paneel leeg">Niets gevonden. Probeer een ander woord of haal een filter weg.</div>`}</div>
      ${r.items.length > 200 ? '<p class="gedempt klein" style="margin-top:10px">De eerste 200 resultaten worden getoond. Verfijn met filters.</p>' : ''}
    </section>
  </div>`;
}
function zoekNaar(wijziging) {
  const [, query] = location.hash.slice(1).split('?');
  const p = new URLSearchParams(location.hash.startsWith('#/zoeken') ? query || '' : '');
  Object.entries(wijziging).forEach(([k, v]) => v ? p.set(k, v) : p.delete(k));
  const s = p.toString();
  location.replace('#/zoeken' + (s ? '?' + s : ''));
}

// ───────────────────────── vergaderingen ─────────────────────────
async function vergaderingen(m, p) {
  const f = { onderdeel: p.get('onderdeel') || '', status: p.get('status') || '' };
  const r = await api('zoek' + qs({ soort: 'vergadering', ...f }));
  const v = vandaag();
  const komend = r.items.filter(x => x.datum >= v).reverse();
  const geweest = r.items.filter(x => x.datum < v);
  const perMaand = {};
  geweest.forEach(x => { const k = x.datum.slice(0, 7); (perMaand[k] = perMaand[k] || []).push(x); });
  const rij = x => vergaderRegel({ ...x, titel: x.titel, onderdeel_naam: x.onderdeel_naam });
  return `
  <div class="kop"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-verg)">${ic('vergadering')}Vergaderingen</span><h1>Alle vergaderingen</h1></div>
    <div class="knoppen"><button class="knop primair" data-actie="nieuwe-vergadering" data-onderdeel="${esc(f.onderdeel)}">${ic('plus')}Nieuwe vergadering</button></div></div>
  <div class="filterbalk">
    <select id="vf-onderdeel" data-lijstfilter="onderdeel" aria-label="Bedrijfsonderdeel">${onderdeelOpties(f.onderdeel)}</select>
    <select id="vf-status" data-lijstfilter="status" aria-label="Status"><option value="">Alle statussen</option>${['gepland', 'concept', 'vastgesteld'].map(s => optie(s, s, f.status)).join('')}</select>
  </div>
  ${komend.length ? `<div class="paneel" style="margin-bottom:18px"><div class="paneel-kop"><h2>Gepland</h2></div><div class="regels">${komend.map(rij).join('')}</div></div>` : ''}
  ${Object.entries(perMaand).map(([k, lijst]) => `<div class="sectie" style="margin-top:18px"><h2 style="font-size:17px">${MAANDEN_LANG[+k.slice(5) - 1]} ${k.slice(0, 4)}</h2>
    <div class="paneel" style="padding-block:4px"><div class="regels">${lijst.map(rij).join('')}</div></div></div>`).join('')}
  ${!r.items.length ? '<div class="paneel leeg">Geen vergaderingen gevonden.</div>' : ''}`;
}

let V = null; // de geopende vergadering, voor formulieren
async function vergadering(m) {
  V = await api('vergadering/' + m[1]);
  const v = V;
  const titel = v.titel || v.onderdeel_naam;
  const aanwezig = v.deelname.filter(d => d.aanwezigheid === 'aanwezig' || d.aanwezigheid === 'deels').length;
  const losB = v.besluiten.filter(b => !b.agendapunt), losA = v.acties.filter(a => !a.agendapunt), losS = v.stukken.filter(s => !s.agendapunt);
  return `
  <div class="broodkruim"><a href="#/vergaderingen">Vergaderingen</a><span>/</span><a href="#/onderdeel/${v.bedrijfsonderdeel}">${esc(v.onderdeel_naam)}</a></div>
  <div class="vergaderkop" style="margin-top:10px">
    <div class="rij">
      <div style="display:grid;gap:6px;min-width:0">
        <span class="oogmerk" style="--c:var(--c-verg)">${ic('vergadering')}<a href="#/onderdeel/${v.bedrijfsonderdeel}">${esc(v.onderdeel_naam)}</a></span>
        <h1>${esc(titel === v.onderdeel_naam ? datum(v.datum) : titel)}</h1>
        <div class="feiten">
          ${titel !== v.onderdeel_naam ? `<span>${ic('vergadering')}${datum(v.datum)}</span>` : ''}
          ${v.begintijd ? `<span>${ic('klok')}${esc(v.begintijd)}${v.eindtijd ? '–' + esc(v.eindtijd) : ''}</span>` : ''}
          ${v.locatie ? `<span>${ic('pin')}${esc(v.locatie)}</span>` : ''}
          <span>${pil(v.status)}</span>
          ${v.vastgesteld_in_info ? `<span>verslag vastgesteld op <a href="#/vergadering/${v.vastgesteld_in_info.id}">&nbsp;${datum(v.vastgesteld_in_info.datum, { dag: false })}</a></span>` : ''}
        </div>
      </div>
      <div class="knoppen" style="display:flex;gap:8px;flex-wrap:wrap">
        <div class="navpijlen">
          ${v.vorige ? `<a class="knop klein" href="#/vergadering/${v.vorige.id}" title="Vorige vergadering (${datum(v.vorige.datum)})">${ic('links')}</a>` : ''}
          ${v.volgende ? `<a class="knop klein" href="#/vergadering/${v.volgende.id}" title="Volgende vergadering (${datum(v.volgende.datum)})">${ic('rechts')}</a>` : ''}
        </div>
        <a class="knop klein" href="export/vergadering/${v.id}.md" title="Download het verslag als Markdown-bestand">${ic('download')}Verslag (.md)</a>
        <button class="knop klein" data-actie="bewerk-vergadering">${ic('bewerk')}Bewerken</button>
      </div>
    </div>
    <div style="display:grid;gap:10px">
      <div class="paneel-kop" style="margin:0"><span class="label-klein">Aanwezig ${aanwezig} van ${v.deelname.length}</span><button class="knop stil klein" data-actie="bewerk-deelname">${ic('mensen')}Aanwezigheid</button></div>
      <div class="aanwezigheid">${v.deelname.map(d => `<a class="deelnemer ${d.aanwezigheid.startsWith('afwezig') ? 'afwezig' : ''}" href="#/persoon/${d.id}" title="${esc(d.aanwezigheid)}">
        ${av(d.foto, d.voornaam + ' ' + d.achternaam)}<span>${esc(d.voornaam + ' ' + d.achternaam)}<span class="rol">${esc(d.rol)}${d.aanwezigheid !== 'aanwezig' ? ' · ' + esc(d.aanwezigheid) : ''}</span></span></a>`).join('') || '<span class="leeg">Nog geen deelnemers.</span>'}</div>
    </div>
    ${v.samenvatting ? `<p class="samenvatting">${esc(v.samenvatting)}</p>` : ''}
  </div>
  ${v.openstaand_eerder.length ? `<details class="callout" ${v.status !== 'vastgesteld' ? 'open' : ''}><summary>${ic('let')}${v.openstaand_eerder.length} openstaande ${v.openstaand_eerder.length === 1 ? 'actie' : 'acties'} uit eerdere vergaderingen van ${esc(v.onderdeel_naam)}</summary>
    <div class="regels">${v.openstaand_eerder.map(a => actieRegel({ ...a, afkorting: '' })).join('')}</div></details>` : ''}
  <div class="paneel-kop" style="margin-bottom:12px"><h2>Agenda</h2><button class="knop klein" data-actie="nieuw-agendapunt">${ic('plus')}Agendapunt</button></div>
  <div class="agenda">
    ${v.agendapunten.map(pt => agendapuntBlok(pt)).join('') || '<div class="paneel leeg">Nog geen agendapunten. Voeg het eerste punt toe.</div>'}
    ${losB.length || losA.length || losS.length ? `<div class="punt"><div class="punt-kop"><span class="punt-nr">·</span><div><h3>Overige besluiten, acties en stukken</h3></div><span></span></div>
      <div class="punt-onderdelen">${puntInhoud(losS, losB, losA)}</div></div>` : ''}
  </div>
  <p class="gedempt klein" style="margin-top:22px">Vastgelegd door ${esc(v.aangemaakt_door || 'onbekend')} · laatst gewijzigd ${esc((v.gewijzigd_op || '').replace('T', ' '))} door ${esc(v.gewijzigd_door || 'onbekend')}</p>`;
}
function puntInhoud(stukken, besluiten, acties) {
  return `
    ${stukken.length ? `<div class="stukken">${stukken.map(s => `<span style="display:inline-flex;gap:2px;align-items:center"><a class="stukchip" href="bijlage/${s.id}" target="_blank" rel="noopener" title="${esc(s.bestandsnaam)}">${ic('stuk')}<span>${esc(s.titel)}</span>${s.vertrouwelijkheid !== 'intern' ? pil(s.vertrouwelijkheid) : ''}</a>
      <button class="knop stil klein" data-actie="bewerk-stuk" data-id="${s.id}" title="Stuk bewerken" aria-label="Stuk bewerken">${ic('bewerk')}</button></span>`).join('')}</div>` : ''}
    ${besluiten.map(b => `<a class="besluitkaart" href="#/besluit/${b.id}"><span class="t"><code>${esc(b.nummer)}</code>${esc(b.titel)} ${pil(b.status)}</span>
      <p>${esc(b.besluittekst)}</p>${b.vervangen_door.length ? `<span class="klein gedempt">Herzien door ${b.vervangen_door.map(x => esc(x.nummer)).join(', ')}</span>` : ''}</a>`).join('')}
    ${acties.map(a => `<div class="actieregel">${av(a.p_foto, a.p_naam, 'mid')}
      <div style="min-width:0"><a class="t" href="#/actie/${a.id}">${esc(a.titel)}</a>
      <div class="m"><a class="persoonlink" href="#/persoon/${a.p_id}">${esc(a.p_naam)}</a>${a.uitvoerders.length ? `<span>met ${a.uitvoerders.map(u => esc(u.voornaam)).join(', ')}</span>` : ''}${deadline(a)}${a.besluit_nummer ? `<span>uit ${esc(a.besluit_nummer)}</span>` : ''}</div></div>
      ${statusKeuze(a)}</div>`).join('')}`;
}
function statusKeuze(a) {
  return `<select class="statuskeuze" data-actiestatus="${a.id}" aria-label="Status van de actie">${['open', 'loopt', 'afgerond', 'vervallen'].map(s => optie(s, s, a.status)).join('')}</select>`;
}
function agendapuntBlok(pt) {
  const stukken = V.stukken.filter(s => s.agendapunt === pt.id), besluiten = V.besluiten.filter(b => b.agendapunt === pt.id), acties = V.acties.filter(a => a.agendapunt === pt.id);
  return `<article class="punt" id="punt-${pt.id}">
    <div class="punt-kop"><span class="punt-nr num">${pt.volgnummer}</span>
      <div style="min-width:0"><h3>${esc(pt.titel)}</h3>
        <div class="punt-meta">${pt.soort ? `<span>${esc(pt.soort)}</span>` : ''}${pt.inbrenger_naam ? `<span>ingebracht door ${esc(pt.inbrenger_naam)}</span>` : ''}
        ${pt.onderwerpen.map(o => `<a class="chip" style="--c:var(--c-ond)" href="#/onderwerp/${o.id}"><span class="stip"></span>${esc(o.naam)}</a>`).join('')}</div></div>
      <button class="knop stil klein" data-actie="bewerk-agendapunt" data-id="${pt.id}" aria-label="Agendapunt bewerken">${ic('bewerk')}</button></div>
    ${pt.bespreking ? `<p class="punt-tekst">${esc(pt.bespreking)}</p>` : ''}
    ${stukken.length || besluiten.length || acties.length ? `<div class="punt-onderdelen">${puntInhoud(stukken, besluiten, acties)}</div>` : ''}
    <div class="punt-knoppen">
      <button class="knop stil klein" data-actie="nieuw-besluit" data-punt="${pt.id}">${ic('besluit')}Besluit</button>
      <button class="knop stil klein" data-actie="nieuwe-actie" data-punt="${pt.id}">${ic('actie')}Actie</button>
      <button class="knop stil klein" data-actie="nieuw-stuk" data-punt="${pt.id}">${ic('stuk')}Stuk</button>
    </div></article>`;
}

// ───────────────────────── besluiten ─────────────────────────
async function besluiten(m, p) {
  const f = Object.fromEntries(['q', 'onderdeel', 'onderwerp', 'status', 'van', 'tot'].map(k => [k, p.get(k) || '']));
  const r = await api('zoek' + qs({ soort: 'besluit', ...f }));
  return `
  <div class="kop"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-bes)">${ic('besluit')}Besluitenregister</span><h1>Besluiten</h1>
    <p class="gedempt">Elk besluit heeft een vast nummer: afkorting van het bedrijfsonderdeel, jaar en volgnummer.</p></div></div>
  <div class="filterbalk">
    <input type="search" id="bf-q" data-lijstfilter="q" value="${esc(f.q)}" placeholder="Zoek in besluiten…" aria-label="Zoek in besluiten">
    <select id="bf-onderdeel" data-lijstfilter="onderdeel" aria-label="Bedrijfsonderdeel">${onderdeelOpties(f.onderdeel)}</select>
    <select id="bf-onderwerp" data-lijstfilter="onderwerp" aria-label="Onderwerp">${onderwerpOpties(f.onderwerp)}</select>
    <select id="bf-status" data-lijstfilter="status" aria-label="Status"><option value="">Alle statussen</option>${['genomen', 'aangehouden', 'herzien', 'ingetrokken'].map(s => optie(s, s, f.status)).join('')}</select>
    <input type="date" id="bf-van" data-lijstfilter="van" value="${esc(f.van)}" aria-label="Vanaf" title="Vanaf">
  </div>
  <div class="tabelvak"><table class="tabel">
    <thead><tr><th>Nummer</th><th>Besluit</th><th>Datum</th><th>Onderdeel</th><th>Status</th></tr></thead>
    <tbody>${r.items.map(b => `<tr class="klikbaar" data-href="#/besluit/${b.id}"><td><code>${esc(b.nummer)}</code></td>
      <td><a href="#/besluit/${b.id}" style="color:var(--inkt);font-weight:600">${esc(b.titel)}</a><div class="klein gedempt">${b.fragment ? frag(b.fragment) : esc(b.kort)}</div></td>
      <td class="num" style="white-space:nowrap">${datum(b.v_datum, { dag: false })}</td><td><span class="afk">${esc(b.afkorting)}</span></td><td>${pil(b.status)}</td></tr>`).join('')
      || '<tr><td colspan="5" class="leeg">Geen besluiten gevonden.</td></tr>'}</tbody></table></div>
  <p class="gedempt klein" style="margin-top:10px">${r.items.length} besluiten</p>`;
}

async function besluit(m) {
  const b = await api('besluit/' + m[1]);
  return `
  <div class="broodkruim"><a href="#/besluiten">Besluiten</a><span>/</span><span>${esc(b.nummer)}</span></div>
  <div class="kop" style="margin-top:10px"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-bes)">${ic('besluit')}Besluit ${esc(b.nummer)}</span>
    <h1>${esc(b.titel)}</h1><div>${pil(b.status)}</div></div>
    <div class="knoppen"><button class="knop" data-actie="bewerk-besluit" data-id="${b.id}" data-vergadering="${b.vergadering}">${ic('bewerk')}Bewerken</button></div></div>
  ${b.vervangen_door.length ? `<div class="callout" style="margin-bottom:18px">${ic('let')} Dit besluit is herzien door ${b.vervangen_door.map(x => `<a href="#/besluit/${x.id}">${esc(x.nummer)} ${esc(x.titel)}</a>`).join(', ')}.</div>` : ''}
  <div class="detail-layout">
    <div style="display:grid;gap:18px">
      <div class="paneel"><span class="label-klein">Besluit</span><p class="tekstblok" style="margin-top:6px">${esc(b.besluittekst)}</p>
        ${b.motivering ? `<span class="label-klein" style="display:block;margin-top:18px">Motivering</span><p class="tekstblok" style="margin-top:6px">${esc(b.motivering)}</p>` : ''}</div>
      <div class="paneel"><div class="paneel-kop"><h2>Acties uit dit besluit</h2></div>
        <div class="regels">${leegOf(b.acties, a => actieRegel(a, { metVergadering: false }), 'Er zijn geen acties aan dit besluit gekoppeld.')}</div></div>
      ${b.vervangt || b.vervangen_door.length ? `<div class="paneel"><div class="paneel-kop"><h2>Besluitgeschiedenis</h2></div><div class="geschiedenis">
        ${b.vervangt ? `<a class="besluitkaart" href="#/besluit/${b.vervangt}"><span class="t"><code>${esc(b.vervangt_nummer)}</code>${esc(b.vervangt_titel)}</span><span class="klein gedempt">Eerder besluit, vervangen door dit besluit</span></a>` : ''}
        ${b.vervangen_door.map(x => `<a class="besluitkaart" href="#/besluit/${x.id}"><span class="t"><code>${esc(x.nummer)}</code>${esc(x.titel)}</span><span class="klein gedempt">Later besluit dat dit besluit vervangt</span></a>`).join('')}</div></div>` : ''}
    </div>
    <aside class="paneel velden">
      <div class="veld"><span>Genomen in</span><a href="#/vergadering/${b.vergadering}">${esc(b.onderdeel_naam)}, ${datum(b.v_datum)}</a></div>
      ${b.agendapunt ? `<div class="veld"><span>Agendapunt</span><a href="#/vergadering/${b.vergadering}?punt=${b.agendapunt}">${b.volgnummer}. ${esc(b.agendapunt_titel)}</a></div>` : ''}
      ${b.onderwerpen.length ? `<div class="veld"><span>Onderwerpen</span><div class="chips">${b.onderwerpen.map(o => `<a class="chip" style="--c:var(--c-ond)" href="#/onderwerp/${o.id}"><span class="stip"></span>${esc(o.naam)}</a>`).join('')}</div></div>` : ''}
      <div class="veld"><span>Op basis van</span>${b.grondslag.length ? `<div class="stukken">${b.grondslag.map(s => `<a class="stukchip" href="bijlage/${s.id}" target="_blank" rel="noopener">${ic('stuk')}<span>${esc(s.titel)}</span></a>`).join('')}</div>` : '<span class="gedempt klein">Geen stukken gekoppeld</span>'}</div>
      ${b.betrokkenen.length ? `<div class="veld"><span>Betrokkenen</span><div style="display:grid;gap:6px">${b.betrokkenen.map(x => persoonLink(x.id, x.voornaam + ' ' + x.achternaam, x.foto)).join('')}</div></div>` : ''}
      <div class="veld"><span>Bij de vergadering</span><div style="display:grid;gap:6px">${b.aanwezig.map(x => `<span style="display:flex;justify-content:space-between;gap:8px;align-items:center;${x.aanwezigheid.startsWith('afwezig') ? 'opacity:.6' : ''}">${persoonLink(x.id, x.voornaam + ' ' + x.achternaam, x.foto)}<span class="klein gedempt">${esc(x.aanwezigheid)}</span></span>`).join('')}</div></div>
      <div class="veld"><span>Vastgelegd</span><span class="klein gedempt">door ${esc(b.aangemaakt_door || 'onbekend')}, gewijzigd ${esc((b.gewijzigd_op || '').slice(0, 10))}</span></div>
    </aside>
  </div>`;
}

// ───────────────────────── acties ─────────────────────────
async function acties(m, p) {
  const f = Object.fromEntries(['q', 'eigenaar', 'onderdeel', 'onderwerp'].map(k => [k, p.get(k) || '']));
  const r = await api('zoek' + qs({ soort: 'actie', ...f, sorteer: 'oplopend' }));
  const items = r.items.sort((a, b) => (a.deadline || '9999').localeCompare(b.deadline || '9999'));
  const v = vandaag();
  const lopend = items.filter(a => a.status === 'open' || a.status === 'loopt');
  const groepen = [
    ['Over de deadline', '--kritiek', lopend.filter(a => a.deadline && a.deadline < v)],
    ['Deze week', '--let-op', lopend.filter(a => a.deadline && a.deadline >= v && dagenTot(a.deadline) <= 7)],
    ['Later', '--accent', lopend.filter(a => a.deadline && dagenTot(a.deadline) > 7)],
    ['Zonder deadline', '--gedempt', lopend.filter(a => !a.deadline)],
  ];
  const klaar = items.filter(a => a.status === 'afgerond' || a.status === 'vervallen').sort((a, b) => (b.afgerond_op || b.deadline || '').localeCompare(a.afgerond_op || a.deadline || ''));
  const kaart = (a, rand) => `<div class="actiekaart" style="--rand:var(${rand})">${av(a.p_foto, a.p_naam, 'mid')}
    <div style="min-width:0"><a class="t" href="#/actie/${a.id}">${esc(a.titel)}</a>
    <div class="m"><a class="persoonlink" href="#/persoon/${a.p_id}">${esc(a.p_naam)}</a><a href="#/vergadering/${a.v_id}">${esc(a.afkorting)} · ${datum(a.v_datum, { dag: false })}</a>${a.fragment ? `<span>${frag(a.fragment)}</span>` : ''}</div></div>
    <div class="rechts">${deadline(a)}${statusKeuze(a)}</div></div>`;
  const ik = S.gebruiker;
  return `
  <div class="kop"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-act)">${ic('actie')}Acties</span><h1>Wie doet wat</h1>
    <p class="gedempt">${lopend.length} openstaand, ${groepen[0][2].length} over de deadline. Status direct aan te passen.</p></div>
    ${ik ? `<div class="knoppen"><button class="knop ${f.eigenaar === ik ? 'primair' : ''}" data-actie="lijstfilter" data-k="eigenaar" data-v="${f.eigenaar === ik ? '' : ik}">${ic('persoon')}Alleen mijn acties</button></div>` : ''}</div>
  <div class="filterbalk">
    <input type="search" id="af-q" data-lijstfilter="q" value="${esc(f.q)}" placeholder="Zoek in acties…" aria-label="Zoek in acties">
    <select id="af-eigenaar" data-lijstfilter="eigenaar" aria-label="Eigenaar">${persoonOpties(f.eigenaar, 'Alle eigenaren')}</select>
    <select id="af-onderdeel" data-lijstfilter="onderdeel" aria-label="Bedrijfsonderdeel">${onderdeelOpties(f.onderdeel)}</select>
    <select id="af-onderwerp" data-lijstfilter="onderwerp" aria-label="Onderwerp">${onderwerpOpties(f.onderwerp)}</select>
  </div>
  ${groepen.map(([t, c, lijst]) => lijst.length ? `<div class="groep"><div class="groep-kop" style="--c:var(${c})">${t}<span class="n">${lijst.length}</span></div>${lijst.map(a => kaart(a, c)).join('')}</div>` : '').join('')}
  ${!lopend.length ? '<div class="paneel leeg" style="margin-bottom:20px">Geen openstaande acties met deze filters.</div>' : ''}
  ${klaar.length ? `<details class="groep"><summary class="groep-kop" style="cursor:pointer;--c:var(--goed)">Afgerond en vervallen<span class="n">${klaar.length}</span></summary>
    <div style="display:grid;gap:8px;margin-top:8px">${klaar.slice(0, 60).map(a => kaart(a, '--goed')).join('')}</div></details>` : ''}`;
}

async function actie(m) {
  const a = await api('actie/' + m[1]);
  return `
  <div class="broodkruim"><a href="#/acties">Acties</a><span>/</span><a href="#/vergadering/${a.vergadering}">${esc(a.v_titel)}, ${datum(a.v_datum, { dag: false })}</a></div>
  <div class="kop" style="margin-top:10px"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-act)">${ic('actie')}Actie</span>
    <h1>${esc(a.titel)}</h1><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">${pil(a.status)} ${a.te_laat ? pil('te laat', 'te-laat') : ''} ${deadline(a)}</div></div>
    <div class="knoppen"><button class="knop" data-actie="bewerk-actie" data-id="${a.id}" data-vergadering="${a.vergadering}">${ic('bewerk')}Bewerken</button></div></div>
  <div class="detail-layout">
    <div style="display:grid;gap:18px">
      ${a.omschrijving ? `<div class="paneel"><span class="label-klein">Wat moet er gebeuren</span><p class="tekstblok" style="margin-top:6px">${esc(a.omschrijving)}</p></div>` : ''}
      <div class="paneel"><div class="paneel-kop"><h2>Voortgang</h2></div>
        <form class="voortgang" data-form="voortgang" data-id="${a.id}" style="margin-bottom:14px;display:grid;gap:8px">
          <textarea id="voortgang-tekst" name="tekst" placeholder="Korte update, bijvoorbeeld: offerte aangevraagd, wacht op reactie leverancier" style="min-height:70px" required></textarea>
          <div><button class="knop primair klein" type="submit">${ic('plus')}Update toevoegen</button></div></form>
        <div class="voortgang">${a.voortgang.map(g => `<div class="item"><small>${datum(g.datum)} · ${esc(g.aangemaakt_door || '')}</small>${esc(g.tekst)}</div>`).join('') || '<div class="leeg">Nog geen updates.</div>'}</div></div>
    </div>
    <aside class="paneel velden">
      <div class="veld"><span>Eigenaar</span>${persoonLink(a.p_id, a.p_naam, a.p_foto, 'mid')}</div>
      ${a.uitvoerders.length ? `<div class="veld"><span>Werkt mee</span><div style="display:grid;gap:6px">${a.uitvoerders.map(u => persoonLink(u.id, u.voornaam + ' ' + u.achternaam, u.foto)).join('')}</div></div>` : ''}
      <div class="veld"><span>Status</span><div>${statusKeuze(a)}</div></div>
      <div class="veld"><span>Deadline</span><span>${a.deadline ? datum(a.deadline) : 'geen'}</span></div>
      ${a.afgerond_op ? `<div class="veld"><span>Afgerond op</span><span>${datum(a.afgerond_op)}</span></div>` : ''}
      <div class="veld"><span>Uitgezet in</span><a href="#/vergadering/${a.vergadering}">${esc(a.v_titel)}, ${datum(a.v_datum)}</a></div>
      ${a.agendapunt ? `<div class="veld"><span>Agendapunt</span><a href="#/vergadering/${a.vergadering}?punt=${a.agendapunt}">${a.volgnummer}. ${esc(a.agendapunt_titel)}</a></div>` : ''}
      ${a.besluit ? `<div class="veld"><span>Voortkomend uit</span><a href="#/besluit/${a.besluit}">${esc(a.besluit_nummer)} ${esc(a.besluit_titel)}</a></div>` : ''}
      <div class="veld"><span>Vastgelegd</span><span class="klein gedempt">door ${esc(a.aangemaakt_door || 'onbekend')}, gewijzigd ${esc((a.gewijzigd_op || '').slice(0, 10))} door ${esc(a.gewijzigd_door || 'onbekend')}</span></div>
    </aside>
  </div>`;
}

// ───────────────────────── personen ─────────────────────────
async function personen() {
  const lijst = await api('personen');
  return `
  <div class="kop"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-pers)">${ic('persoon')}Personen</span><h1>Personen</h1></div>
    <div class="knoppen"><button class="knop" data-actie="nieuwe-persoon">${ic('plus')}Persoon</button></div></div>
  <div class="filterbalk"><input type="search" id="personen-filter" placeholder="Filter op naam, functie of onderdeel…" aria-label="Filter personen"></div>
  <div class="kaarten" id="personenkaarten">${lijst.map(p => `<a class="kaart" href="#/persoon/${p.id}" data-zoektekst="${esc((naamVan(p) + ' ' + (p.functie || '') + ' ' + (p.onderdeel_naam || '')).toLowerCase())}" ${p.actief ? '' : 'style="opacity:.6"'}>
    <div class="persoonkop">${av(p.foto, naamVan(p), 'mid')}<div style="min-width:0"><div class="t">${esc(naamVan(p))}</div><div class="klein gedempt">${esc(p.functie || '')}</div></div></div>
    <div class="tellers"><span><b>${p.n_open}</b> open</span>${p.n_te_laat ? `<span class="kritiek"><b>${p.n_te_laat}</b> te laat</span>` : ''}<span>${esc(p.onderdeel_naam || '')}</span>${p.actief ? '' : '<span>niet meer actief</span>'}</div></a>`).join('')}</div>`;
}

async function persoonPagina(m) {
  const p = await api('persoon/' + m[1]);
  const open = p.acties.filter(a => a.status === 'open' || a.status === 'loopt');
  const klaar = p.acties.filter(a => !(a.status === 'open' || a.status === 'loopt'));
  const geweest = p.vergaderingen.filter(v => v.datum <= vandaag());
  const aanw = geweest.filter(v => v.aanwezigheid === 'aanwezig' || v.aanwezigheid === 'deels').length;
  const naam = naamVan(p);
  return `
  <div class="broodkruim"><a href="#/personen">Personen</a></div>
  <div class="profielkop" style="margin-top:10px">${av(p.foto, naam, 'groot')}
    <div class="info"><h1>${esc(naam)}</h1><p class="gedempt">${esc(p.functie || '')}${p.onderdeel_naam ? ` · <a href="#/onderdeel/${p.bedrijfsonderdeel}">${esc(p.onderdeel_naam)}</a>` : ''}</p>
      <p class="klein gedempt" style="user-select:all">${esc(p.email)}${p.telefoon ? ' · ' + esc(p.telefoon) : ''}</p></div>
    <div class="knoppen" style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap">
      <a class="knop" href="#/zoeken${qs({ persoon: p.id })}">${ic('zoek')}Alles van ${esc(p.voornaam)}</a>
      <button class="knop" data-actie="bewerk-persoon" data-id="${p.id}">${ic('bewerk')}Bewerken</button></div>
  </div>
  <div class="kentallen">
    <div class="kental"><span class="getal">${open.length}</span><span class="wat">openstaande acties</span></div>
    <div class="kental ${open.some(a => a.te_laat) ? 'kritiek' : ''}"><span class="getal">${open.filter(a => a.te_laat).length}</span><span class="wat">over de deadline</span></div>
    <div class="kental"><span class="getal">${klaar.filter(a => a.status === 'afgerond').length}</span><span class="wat">acties afgerond</span></div>
    <div class="kental"><span class="getal">${geweest.length ? Math.round(aanw / geweest.length * 100) + '%' : '–'}</span><span class="wat">aanwezig (${aanw} van ${geweest.length} vergaderingen)</span></div>
  </div>
  <div class="raster twee">
    <div class="paneel"><div class="paneel-kop"><h2>Acties</h2><span class="klein gedempt">als eigenaar of meewerkend</span></div>
      <div class="regels">${leegOf(open, a => `<a class="regel" href="#/actie/${a.id}">${soortIc('actie')}<span class="hoofd"><span class="t">${esc(a.titel)}</span>
        <span class="m"><span>${a.als_eigenaar ? 'eigenaar' : 'werkt mee'}</span><span>${esc(a.afkorting)} · ${datum(a.v_datum, { dag: false })}</span></span></span><span class="rechts">${deadline(a)}</span></a>`, 'Geen openstaande acties.')}</div>
      ${klaar.length ? `<details style="margin-top:10px"><summary class="klein" style="cursor:pointer;color:var(--accent);font-weight:600">${klaar.length} afgeronde of vervallen acties</summary>
        <div class="regels">${klaar.map(a => `<a class="regel" href="#/actie/${a.id}">${soortIc('actie')}<span class="hoofd"><span class="t">${esc(a.titel)}</span><span class="m"><span>${esc(a.afkorting)} · ${datum(a.v_datum, { dag: false })}</span></span></span><span class="rechts">${pil(a.status)}</span></a>`).join('')}</div></details>` : ''}</div>
    <div class="paneel"><div class="paneel-kop"><h2>Betrokken bij besluiten</h2></div>
      <div class="regels">${leegOf(p.besluiten, b => `<a class="regel" href="#/besluit/${b.id}">${soortIc('besluit')}<span class="hoofd"><span class="t">${esc(b.titel)}</span><span class="m"><span>${esc(b.nummer)}</span><span>${datum(b.v_datum, { dag: false })}</span></span></span><span class="rechts">${pil(b.status)}</span></a>`, 'Geen besluiten.')}</div></div>
    <div class="paneel"><div class="paneel-kop"><h2>Vergaderingen</h2></div>
      <div class="regels">${leegOf(p.vergaderingen.slice(0, 15), v => `<a class="regel" href="#/vergadering/${v.id}">${datumblok(v.datum)}<span class="hoofd"><span class="t">${esc(v.titel)}</span><span class="m"><span>${esc(v.rol)}</span></span></span>
        <span class="rechts ${v.aanwezigheid.startsWith('afwezig') ? 'deadline te-laat' : 'gedempt'}">${v.datum > vandaag() ? 'gepland' : esc(v.aanwezigheid)}</span></a>`, 'Nog geen vergaderingen.')}</div></div>
    <div class="paneel"><div class="paneel-kop"><h2>Rollen</h2></div>
      <div class="velden">
        <div class="veld"><span>Vast lid van</span><div class="chips">${p.lidmaatschappen.map(l => `<a class="chip" style="--c:var(--c-org)" href="#/onderdeel/${l.id}"><span class="stip"></span>${esc(l.naam)} · ${esc(l.rol)}</a>`).join('') || '<span class="gedempt klein">—</span>'}</div></div>
        ${p.portefeuille.length ? `<div class="veld"><span>Portefeuillehouder voor</span><div class="chips">${p.portefeuille.map(o => `<a class="chip" style="--c:var(--c-ond)" href="#/onderwerp/${o.id}"><span class="stip"></span>${esc(o.naam)}</a>`).join('')}</div></div>` : ''}
        ${p.stukken.length ? `<div class="veld"><span>Auteur van</span><div class="stukken">${p.stukken.map(s => `<a class="stukchip" href="bijlage/${s.id}" target="_blank" rel="noopener">${ic('stuk')}<span>${esc(s.titel)}</span></a>`).join('')}</div></div>` : ''}
      </div></div>
  </div>`;
}

// ───────────────────────── onderwerpen ─────────────────────────
async function onderwerpen() {
  const lijst = await api('onderwerpen');
  return `
  <div class="kop"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-ond)">${ic('onderwerp')}Onderwerpen</span><h1>Dossiers</h1>
    <p class="gedempt">Onderwerpen komen terug over vergaderingen en bedrijfsonderdelen heen. Open er een voor de hele geschiedenis.</p></div>
    <div class="knoppen"><button class="knop" data-actie="nieuw-onderwerp">${ic('plus')}Onderwerp</button></div></div>
  <div class="kaarten">${lijst.map(o => `<a class="kaart" href="#/onderwerp/${o.id}" style="border-top:3px solid var(--c-ond)">
    <div class="t">${esc(o.naam)}</div><p class="klein gedempt">${esc(o.omschrijving || '')}</p>
    <div class="tellers"><span><b>${o.n_vergaderingen}</b> vergaderingen</span><span><b>${o.n_besluiten}</b> besluiten</span><span><b>${o.n_acties}</b> acties</span></div>
    <div class="tellers">${o.ph_naam ? `<span class="persoonlink">${av(o.ph_foto, o.ph_naam, 'klein')}${esc(o.ph_naam)}</span>` : ''}${o.laatst ? `<span>laatst ${datum(o.laatst, { dag: false })}</span>` : ''}</div></a>`).join('')}</div>`;
}

async function onderwerpPagina(m) {
  const o = await api('onderwerp/' + m[1]);
  const dagen = [];
  o.tijdlijn.forEach(it => {
    const vid = it.soort === 'vergadering' ? it.id : it.v_id;
    let d = dagen.find(x => x.vid === vid);
    if (!d) { d = { vid, datum: it.datum, titel: '', items: [] }; dagen.push(d); }
    if (it.soort === 'vergadering') d.titel = it.titel; else { d.items.push(it); d.titel = d.titel || it.v_titel; }
  });
  const volgorde = { agendapunt: 0, stuk: 1, besluit: 2, actie: 3 };
  return `
  <div class="broodkruim"><a href="#/onderwerpen">Onderwerpen</a></div>
  <div class="kop" style="margin-top:10px"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-ond)">${ic('onderwerp')}Dossier</span><h1>${esc(o.naam)}</h1>
    <p class="gedempt" style="max-width:70ch">${esc(o.omschrijving || '')}</p></div>
    <div class="knoppen"><a class="knop" href="#/zoeken${qs({ onderwerp: o.id })}">${ic('zoek')}Doorzoeken</a><button class="knop" data-actie="bewerk-onderwerp" data-id="${o.id}">${ic('bewerk')}Bewerken</button></div></div>
  <div class="detail-layout">
    <div class="paneel"><div class="paneel-kop"><h2>Tijdlijn</h2><span class="klein gedempt">${dagen.length} vergaderingen</span></div>
      <div class="tijdlijn" style="margin-top:10px">${dagen.map(d => `<div class="tl-dag"><div class="tl-datum num">${datum(d.datum, { dag: false })}<small><a href="#/vergadering/${d.vid}">${esc(d.titel)}</a></small></div>
        <div class="tl-items">${d.items.sort((a, b) => volgorde[a.soort] - volgorde[b.soort]).map(it => `<a class="tl-item" href="${itemLink(it)}" ${it.soort === 'stuk' ? 'target="_blank" rel="noopener"' : ''} style="--c:var(${SOORT[it.soort].c})">
          ${soortIc(it.soort)}<span style="min-width:0"><b style="font-weight:600">${it.soort === 'besluit' ? esc(it.nummer) + ' · ' : ''}${esc(it.titel)}</b>
          <span class="klein gedempt" style="display:block">${SOORT[it.soort].naam}${it.soort === 'actie' ? ' · ' + esc(it.p_naam) + ' · ' + it.status : it.soort === 'besluit' ? ' · ' + esc(it.status) : ''}</span></span></a>`).join('') || '<span class="gedempt klein">Besproken</span>'}</div></div>`).join('') || '<div class="leeg">Nog niets aan dit onderwerp gekoppeld.</div>'}</div></div>
    <aside class="paneel velden">
      ${o.ph_naam ? `<div class="veld"><span>Portefeuillehouder</span>${persoonLink(o.portefeuillehouder, o.ph_naam, o.ph_foto, 'mid')}</div>` : ''}
      ${o.trefwoorden ? `<div class="veld"><span>Trefwoorden</span><span class="klein">${esc(o.trefwoorden)}</span></div>` : ''}
      <div class="veld"><span>Meest betrokken</span><div style="display:grid;gap:6px">${o.betrokken.map(x => `<span style="display:flex;justify-content:space-between;align-items:center;gap:8px">${persoonLink(x.id, x.voornaam + ' ' + x.achternaam, x.foto)}<span class="klein gedempt num">${x.n}×</span></span>`).join('') || '<span class="gedempt klein">—</span>'}</div></div>
    </aside>
  </div>`;
}

// ───────────────────────── bedrijfsonderdelen ─────────────────────────
async function onderdelen() {
  const lijst = await api('onderdelen');
  const knoop = o => `<a class="boomknoop" href="#/onderdeel/${o.id}" ${o.actief ? '' : 'style="opacity:.6"'}><span class="afk">${esc(o.afkorting)}</span>
    <span><span class="t">${esc(o.naam)}</span><span class="klein gedempt" style="display:block">${esc(o.soort)}${o.actief ? '' : ' · opgeheven'}</span></span>
    <span class="m">${o.n_leden} vaste leden · ${o.n_vergaderingen} vergaderingen${o.laatst ? `<br>laatst ${datum(o.laatst, { dag: false })}` : ''}</span></a>`;
  const tak = ouder => lijst.filter(o => (o.valt_onder || null) === ouder).map(o => {
    const sub = tak(o.id);
    return knoop(o) + (sub ? `<div class="tak">${sub}</div>` : '');
  }).join('');
  return `
  <div class="kop"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-org)">${ic('onderdeel')}Bedrijfsonderdelen</span><h1>Wie vergadert</h1>
    <p class="gedempt">Zoeken en filteren op een onderdeel neemt automatisch alles mee wat eronder valt.</p></div>
    <div class="knoppen"><button class="knop" data-actie="nieuw-onderdeel">${ic('plus')}Bedrijfsonderdeel</button></div></div>
  <div class="boom">${tak(null)}</div>`;
}

async function onderdeelPagina(m) {
  const o = await api('bedrijfsonderdeel/' + m[1]);
  const v = vandaag();
  return `
  <div class="broodkruim"><a href="#/onderdelen">Bedrijfsonderdelen</a>${o.valt_onder ? `<span>/</span><a href="#/onderdeel/${o.valt_onder}">${esc(o.boven_naam)}</a>` : ''}</div>
  <div class="kop" style="margin-top:10px"><div class="titelblok"><span class="oogmerk" style="--c:var(--c-org)">${ic('onderdeel')}${esc(o.soort)} · <span class="afk">${esc(o.afkorting)}</span></span><h1>${esc(o.naam)}</h1></div>
    <div class="knoppen"><a class="knop" href="#/zoeken${qs({ onderdeel: o.id })}">${ic('zoek')}Zoek binnen ${esc(o.afkorting)}</a>
      <button class="knop" data-actie="bewerk-onderdeel" data-id="${o.id}">${ic('bewerk')}Bewerken</button>
      <button class="knop primair" data-actie="nieuwe-vergadering" data-onderdeel="${o.id}">${ic('plus')}Nieuwe vergadering</button></div></div>
  <div class="raster twee">
    <div class="paneel"><div class="paneel-kop"><h2>Vergaderingen</h2></div>
      <div class="regels">${leegOf(o.vergaderingen, x => vergaderRegel({ ...x }), 'Nog geen vergaderingen.')}</div></div>
    <div style="display:grid;gap:18px;align-content:start">
      <div class="paneel"><div class="paneel-kop"><h2>Vaste leden</h2><button class="knop stil klein" data-actie="bewerk-leden" data-id="${o.id}">${ic('bewerk')}Wijzigen</button></div>
        <p class="klein gedempt" style="margin-bottom:6px">Worden automatisch op de aanwezigheidslijst van een nieuwe vergadering gezet.</p>
        <div class="regels">${leegOf(o.leden, l => `<a class="regel" href="#/persoon/${l.id}">${av(l.foto, l.voornaam + ' ' + l.achternaam, 'mid')}<span class="hoofd"><span class="t">${esc(l.voornaam + ' ' + l.achternaam)}</span><span class="m">${esc(l.functie || '')}</span></span><span class="rechts gedempt">${esc(l.rol)}</span></a>`, 'Nog geen vaste leden.')}</div></div>
      ${o.onder.length ? `<div class="paneel"><div class="paneel-kop"><h2>Valt hieronder</h2></div><div class="regels">${o.onder.map(x => `<a class="regel" href="#/onderdeel/${x.id}"><span class="afk">${esc(x.afkorting)}</span><span class="hoofd"><span class="t">${esc(x.naam)}</span></span><span class="rechts gedempt">${esc(x.soort)}</span></a>`).join('')}</div></div>` : ''}
    </div>
  </div>`;
}

// ───────────────────────── modals & formulieren ─────────────────────────
const laag = $('#modal-laag');
let vorigeFocus = null;
function openModal(html, breed = false) {
  vorigeFocus = document.activeElement;
  laag.innerHTML = `<div class="modal ${breed ? 'breed' : ''}" role="dialog" aria-modal="true">${html}</div>`;
  laag.hidden = false;
  const eerste = laag.querySelector('input:not([type=hidden]):not([type=file]), select, textarea');
  if (eerste) eerste.focus();
}
function sluitModal() { laag.hidden = true; laag.innerHTML = ''; if (vorigeFocus) vorigeFocus.focus?.(); }

function veldHtml(v, waarden) {
  if (v.rij) return `<div class="rij2">${v.rij.map(x => veldHtml(x, waarden)).join('')}</div>`;
  const w = waarden[v.n] ?? v.standaard ?? '';
  const id = 'veld-' + v.n;
  const req = v.req ? 'required' : '';
  let invoer;
  switch (v.t) {
    case 'textarea': invoer = `<textarea id="${id}" name="${v.n}" ${req} placeholder="${esc(v.ph || '')}">${esc(w)}</textarea>`; break;
    case 'select': invoer = `<select id="${id}" name="${v.n}" ${req}>${v.leeg !== undefined ? `<option value="">${esc(v.leeg)}</option>` : ''}${v.opties.map(([o, l]) => optie(o, l, w)).join('')}</select>`; break;
    case 'multi': {
      const gekozen = (w || []).map(String);
      invoer = `<div class="keuzelijst" id="${id}">${v.opties.map(([o, l, foto]) => `<label class="${foto === undefined ? 'zonder-av' : ''}"><input type="checkbox" name="${v.n}" value="${esc(o)}" ${gekozen.includes(String(o)) ? 'checked' : ''}>${foto !== undefined ? av(foto, l, 'klein') : ''}${esc(l)}</label>`).join('') || '<span class="klein gedempt">Nog niets om te kiezen.</span>'}</div>`;
      return `<div class="veld"><span class="lbl">${esc(v.l)}</span>${invoer}${v.hulp ? `<span class="hulp">${esc(v.hulp)}</span>` : ''}</div>`;
    }
    default: invoer = `<input id="${id}" name="${v.n}" type="${v.t || 'text'}" value="${esc(w)}" ${req} placeholder="${esc(v.ph || '')}" ${v.t === 'number' ? 'min="1"' : ''}>`;
  }
  return `<div class="veld"><label for="${id}">${esc(v.l)}${v.req ? ' *' : ''}</label>${invoer}${v.hulp ? `<span class="hulp">${esc(v.hulp)}</span>` : ''}</div>`;
}
function vlak(velden) { return velden.flatMap(v => v.rij ? v.rij : [v]); }

function formulier({ titel, velden, waarden = {}, opslaan, verwijder, breed = false, knop = 'Opslaan' }) {
  openModal(`<div class="modal-kop"><h2>${esc(titel)}</h2><button class="sluit" data-actie="sluit-modal" aria-label="Sluiten">${ic('kruis')}</button></div>
    <form id="modal-form" novalidate>${velden.map(v => veldHtml(v, waarden)).join('')}<div class="foutmelding" id="modal-fout" hidden></div></form>
    <div class="modal-voet">${verwijder ? `<button class="knop gevaar" type="button" id="modal-verwijder">Verwijderen</button>` : ''}
      <div class="rechts"><button class="knop" type="button" data-actie="sluit-modal">Annuleren</button><button class="knop primair" type="submit" form="modal-form">${esc(knop)}</button></div></div>`, breed);
  const form = $('#modal-form');
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const fout = $('#modal-fout');
    const leeg = vlak(velden).find(v => v.req && !String(form.elements[v.n]?.value || '').trim());
    if (leeg) { fout.textContent = `Vul “${leeg.l}” in.`; fout.hidden = false; form.elements[leeg.n]?.focus(); return; }
    const data = {};
    vlak(velden).forEach(v => { data[v.n] = v.t === 'multi' ? $$(`input[name="${v.n}"]:checked`, form).map(i => Number(i.value)) : (form.elements[v.n]?.value ?? ''); });
    try { await opslaan(data); sluitModal(); }
    catch (err) { fout.textContent = err.message; fout.hidden = false; }
  });
  const del = $('#modal-verwijder');
  if (del) del.addEventListener('click', async () => {
    if (!del.classList.contains('bevestig')) { del.classList.add('bevestig'); del.textContent = 'Klik nogmaals om definitief te verwijderen'; return; }
    try { await verwijder(); sluitModal(); }
    catch (err) { const f = $('#modal-fout'); f.textContent = err.message; f.hidden = false; }
  });
}

const PERS_OPTIES = () => S.meta.personen.filter(p => p.actief).map(p => [p.id, naamVan(p)]);
const PERS_MULTI = () => S.meta.personen.filter(p => p.actief).map(p => [p.id, naamVan(p), p.foto || '']);
const OND_MULTI = () => S.meta.onderwerpen.map(o => [o.id, o.naam]);
const ONDERDEEL_OPTIES = () => boomVolgorde().map(([o, d]) => [o.id, ' '.repeat(d) + o.naam]);

async function formVergadering(v = null, standaard = {}) {
  const lijst = (await api('zoek?soort=vergadering')).items.filter(x => !v || x.id !== v.id);
  formulier({
    titel: v ? 'Vergadering bewerken' : 'Nieuwe vergadering',
    waarden: v || { status: 'gepland', datum: vandaag(), ...standaard },
    velden: [
      { n: 'bedrijfsonderdeel', l: 'Bedrijfsonderdeel', t: 'select', req: true, leeg: 'Kies…', opties: ONDERDEEL_OPTIES(), hulp: v ? '' : 'De vaste leden worden automatisch op de aanwezigheidslijst gezet.' },
      { rij: [{ n: 'datum', l: 'Datum', t: 'date', req: true }, { n: 'begintijd', l: 'Begin', t: 'time' }, { n: 'eindtijd', l: 'Eind', t: 'time' }] },
      { rij: [{ n: 'locatie', l: 'Locatie', ph: 'Zaal of online' }, { n: 'status', l: 'Status', t: 'select', opties: [['gepland', 'gepland'], ['concept', 'concept (verslag in de maak)'], ['vastgesteld', 'vastgesteld']] }] },
      { n: 'titel', l: 'Titel', ph: 'Leeg laten: naam van het bedrijfsonderdeel' },
      { n: 'samenvatting', l: 'Samenvatting', t: 'textarea', ph: 'Twee of drie zinnen. De details horen bij de agendapunten.' },
      ...(v ? [{ n: 'vastgesteld_in', l: 'Verslag vastgesteld in', t: 'select', leeg: '—', opties: lijst.map(x => [x.id, `${datum(x.datum)} · ${x.titel}`]) }] : []),
    ],
    opslaan: async d => {
      if (v) { await api('vergadering/' + v.id, { methode: 'PUT', data: d }); toast('Vergadering opgeslagen'); await herlaad(); }
      else { const r = await api('vergadering', { methode: 'POST', data: d }); toast('Vergadering aangemaakt'); await herlaadMeta(); go('#/vergadering/' + r.id); }
    },
    verwijder: v ? async () => { await api('vergadering/' + v.id, { methode: 'DELETE' }); toast('Vergadering verwijderd'); await herlaadMeta(); go('#/vergaderingen'); } : null,
  });
}

function formAgendapunt(pt = null) {
  formulier({
    titel: pt ? 'Agendapunt bewerken' : 'Nieuw agendapunt',
    waarden: pt ? { ...pt, onderwerpen: pt.onderwerpen.map(o => o.id) } : { soort: 'ter besluitvorming' },
    velden: [
      { n: 'titel', l: 'Titel', req: true },
      { rij: [{ n: 'soort', l: 'Soort', t: 'select', leeg: '—', opties: [['ter besluitvorming', 'ter besluitvorming'], ['ter bespreking', 'ter bespreking'], ['ter informatie', 'ter informatie']] },
        { n: 'inbrenger', l: 'Ingebracht door', t: 'select', leeg: '—', opties: PERS_OPTIES() },
        ...(pt ? [{ n: 'volgnummer', l: 'Volgnummer', t: 'number' }] : [])] },
      { n: 'onderwerpen', l: 'Onderwerpen', t: 'multi', opties: OND_MULTI(), hulp: 'Besluiten, acties en stukken bij dit punt erven deze onderwerpen.' },
      { n: 'bespreking', l: 'Bespreking', t: 'textarea', ph: 'De kern van de discussie in een paar zinnen.' },
    ],
    opslaan: async d => {
      if (pt) await api('agendapunt/' + pt.id, { methode: 'PUT', data: d });
      else await api('agendapunt', { methode: 'POST', data: { ...d, vergadering: V.id } });
      toast('Agendapunt opgeslagen'); await herlaad();
    },
    verwijder: pt ? async () => { await api('agendapunt/' + pt.id, { methode: 'DELETE' }); toast('Agendapunt verwijderd'); await herlaad(); } : null,
  });
}

async function formBesluit(b = null, standaard = {}) {
  const alle = (await api('zoek?soort=besluit')).items.filter(x => !b || x.id !== b.id);
  formulier({
    titel: b ? `Besluit ${b.nummer} bewerken` : 'Nieuw besluit',
    breed: true,
    waarden: b ? { ...b, betrokkenen: (b.betrokkenen || []).map(x => x.id), grondslag: (b.grondslag || []).map(x => x.id), onderwerpen: b.onderwerp_ids || b.onderwerpen || [] } : { status: 'genomen', ...standaard },
    velden: [
      { n: 'titel', l: 'Korte titel', req: true, ph: 'Bijvoorbeeld: Jaarplan 2026 vastgesteld' },
      { n: 'besluittekst', l: 'Besluittekst', t: 'textarea', req: true },
      { n: 'motivering', l: 'Motivering', t: 'textarea' },
      { rij: [{ n: 'agendapunt', l: 'Agendapunt', t: 'select', leeg: '—', opties: V.agendapunten.map(p => [p.id, `${p.volgnummer}. ${p.titel}`]) },
        { n: 'status', l: 'Status', t: 'select', opties: ['genomen', 'aangehouden', 'herzien', 'ingetrokken'].map(s => [s, s]) }] },
      { n: 'vervangt', l: 'Vervangt eerder besluit', t: 'select', leeg: '—', opties: alle.map(x => [x.id, `${x.nummer} · ${x.titel}`]), hulp: 'Het eerdere besluit krijgt dan een verwijzing naar dit besluit.' },
      { n: 'grondslag', l: 'Op basis van stukken', t: 'multi', opties: V.stukken.map(s => [s.id, s.titel]) },
      { n: 'betrokkenen', l: 'Betrokkenen', t: 'multi', opties: PERS_MULTI() },
      { n: 'onderwerpen', l: 'Extra onderwerpen', t: 'multi', opties: OND_MULTI(), hulp: 'Onderwerpen van het agendapunt gelden al automatisch.' },
    ],
    opslaan: async d => {
      if (b) { await api('besluit/' + b.id, { methode: 'PUT', data: d }); }
      else { const r = await api('besluit', { methode: 'POST', data: { ...d, vergadering: V.id } }); toast('Besluit vastgelegd'); }
      if (d.vervangt) await api('besluit/' + d.vervangt, { methode: 'PUT', data: { status: 'herzien' } });
      if (b) toast('Besluit opgeslagen');
      await herlaad();
    },
    verwijder: b ? async () => { await api('besluit/' + b.id, { methode: 'DELETE' }); toast('Besluit verwijderd'); location.hash.startsWith('#/besluit/') ? go('#/vergadering/' + V.id) : await herlaad(); } : null,
  });
}

function formActie(a = null, standaard = {}) {
  formulier({
    titel: a ? 'Actie bewerken' : 'Nieuwe actie',
    waarden: a ? { ...a, eigenaar: a.eigenaar, uitvoerders: (a.uitvoerders || []).map(x => x.id) } : { status: 'open', ...standaard },
    velden: [
      { n: 'titel', l: 'Wat moet er gebeuren', req: true, ph: 'Begin met een werkwoord: Stel op, Informeer, Organiseer…' },
      { n: 'omschrijving', l: 'Toelichting', t: 'textarea' },
      { rij: [{ n: 'eigenaar', l: 'Eigenaar', t: 'select', req: true, leeg: 'Kies één eigenaar…', opties: PERS_OPTIES() }, { n: 'deadline', l: 'Deadline', t: 'date' }, { n: 'status', l: 'Status', t: 'select', opties: ['open', 'loopt', 'afgerond', 'vervallen'].map(s => [s, s]) }] },
      { n: 'uitvoerders', l: 'Werkt mee', t: 'multi', opties: PERS_MULTI() },
      { rij: [{ n: 'agendapunt', l: 'Agendapunt', t: 'select', leeg: '—', opties: V.agendapunten.map(p => [p.id, `${p.volgnummer}. ${p.titel}`]) },
        { n: 'besluit', l: 'Voortkomend uit besluit', t: 'select', leeg: '—', opties: V.besluiten.map(b => [b.id, `${b.nummer} · ${b.titel}`]) }] },
    ],
    opslaan: async d => {
      if (a) await api('actie/' + a.id, { methode: 'PUT', data: d });
      else await api('actie', { methode: 'POST', data: { ...d, vergadering: V.id } });
      toast(a ? 'Actie opgeslagen' : 'Actie uitgezet'); await herlaad();
    },
    verwijder: a ? async () => { await api('actie/' + a.id, { methode: 'DELETE' }); toast('Actie verwijderd'); location.hash.startsWith('#/actie/') ? go('#/vergadering/' + V.id) : await herlaad(); } : null,
  });
}

function formStukUpload(standaard = {}) {
  openModal(`<div class="modal-kop"><h2>Stuk toevoegen</h2><button class="sluit" data-actie="sluit-modal" aria-label="Sluiten">${ic('kruis')}</button></div>
    <form id="upload-form">
      <label class="dropzone" id="dropzone" for="upload-bestand"><b>Kies een bestand</b> of sleep het hierheen<br><span class="klein">PDF, Word, PowerPoint, Excel, OpenDocument, tekst of Markdown. De tekst wordt doorzoekbaar.</span><br><span id="upload-naam" class="klein"></span></label>
      <input type="file" id="upload-bestand" hidden>
      ${veldHtml({ n: 'titel', l: 'Titel', ph: 'Leeg laten: bestandsnaam' }, {})}
      <div class="rij2">
        ${veldHtml({ n: 'soort', l: 'Soort', t: 'select', leeg: '—', opties: ['voorstel', 'notitie', 'rapport', 'presentatie', 'brief', 'verslag'].map(s => [s, s]) }, {})}
        ${veldHtml({ n: 'vertrouwelijkheid', l: 'Vertrouwelijkheid', t: 'select', opties: [['openbaar', 'openbaar'], ['intern', 'intern'], ['vertrouwelijk', 'vertrouwelijk']] }, { vertrouwelijkheid: 'intern' })}
      </div>
      <div class="rij2">
        ${veldHtml({ n: 'agendapunt', l: 'Agendapunt', t: 'select', leeg: '—', opties: V.agendapunten.map(p => [p.id, `${p.volgnummer}. ${p.titel}`]) }, standaard)}
        ${veldHtml({ n: 'auteur', l: 'Auteur', t: 'select', leeg: '—', opties: PERS_OPTIES() }, {})}
      </div>
      <div class="foutmelding" id="modal-fout" hidden></div>
    </form>
    <div class="modal-voet"><div class="rechts"><button class="knop" type="button" data-actie="sluit-modal">Annuleren</button><button class="knop primair" type="submit" form="upload-form" id="upload-knop">Toevoegen</button></div></div>`);
  let bestand = null;
  const zet = f => { bestand = f; $('#upload-naam').textContent = f ? `${f.name} · ${grootte(f.size)}` : ''; };
  $('#upload-bestand').addEventListener('change', e => zet(e.target.files[0]));
  const dz = $('#dropzone');
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('over'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('over'));
  dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('over'); zet(e.dataTransfer.files[0]); });
  $('#upload-form').addEventListener('submit', async e => {
    e.preventDefault();
    const fout = $('#modal-fout');
    if (!bestand) { fout.textContent = 'Kies eerst een bestand.'; fout.hidden = false; return; }
    const f = e.target.elements;
    const knop = $('#upload-knop'); knop.disabled = true; knop.textContent = 'Bezig…';
    try {
      const r = await api('upload' + qs({ vergadering: V.id, titel: f.titel.value, soort: f.soort.value, vertrouwelijkheid: f.vertrouwelijkheid.value, agendapunt: f.agendapunt.value, auteur: f.auteur.value }),
        { methode: 'POST', body: bestand, headers: { 'X-Bestandsnaam': encodeURIComponent(bestand.name), 'Content-Type': bestand.type || 'application/octet-stream' } });
      sluitModal();
      toast(r.tekens_gelezen ? `Stuk toegevoegd · ${r.tekens_gelezen.toLocaleString('nl-NL')} tekens doorzoekbaar` : 'Stuk toegevoegd · er kon geen tekst uit worden gehaald');
      await herlaad();
    } catch (err) { fout.textContent = err.message; fout.hidden = false; knop.disabled = false; knop.textContent = 'Toevoegen'; }
  });
}

function formStuk(s) {
  formulier({
    titel: 'Stuk bewerken', waarden: s,
    velden: [
      { n: 'titel', l: 'Titel', req: true },
      { rij: [{ n: 'soort', l: 'Soort', t: 'select', leeg: '—', opties: ['voorstel', 'notitie', 'rapport', 'presentatie', 'brief', 'verslag'].map(x => [x, x]) },
        { n: 'vertrouwelijkheid', l: 'Vertrouwelijkheid', t: 'select', opties: ['openbaar', 'intern', 'vertrouwelijk'].map(x => [x, x]) }] },
      { rij: [{ n: 'agendapunt', l: 'Agendapunt', t: 'select', leeg: '—', opties: V.agendapunten.map(p => [p.id, `${p.volgnummer}. ${p.titel}`]) },
        { n: 'auteur', l: 'Auteur', t: 'select', leeg: '—', opties: PERS_OPTIES() }] },
      { rij: [{ n: 'versie', l: 'Versie' }, { n: 'datum', l: 'Datum', t: 'date' }] },
    ],
    opslaan: async d => { await api('stuk/' + s.id, { methode: 'PUT', data: d }); toast('Stuk opgeslagen'); await herlaad(); },
    verwijder: async () => { await api('stuk/' + s.id, { methode: 'DELETE' }); toast('Stuk en bestand verwijderd'); await herlaad(); },
  });
}

function formDeelname() {
  let rijen = V.deelname.map(d => ({ persoon: d.id, rol: d.rol, aanwezigheid: d.aanwezigheid }));
  const ROLLEN = ['voorzitter', 'lid', 'notulist', 'adviseur', 'gast'], AANW = ['aanwezig', 'deels', 'afwezig met bericht', 'afwezig'];
  const teken = () => {
    $('#deelname-rijen').innerHTML = rijen.map((r, i) => { const p = persoon(r.persoon); return `<tr>
      <td><span class="persoonlink">${av(p?.foto, naamVan(p), 'klein')}${esc(naamVan(p))}</span></td>
      <td><select data-i="${i}" data-k="rol" aria-label="Rol">${ROLLEN.map(x => optie(x, x, r.rol)).join('')}</select></td>
      <td><select data-i="${i}" data-k="aanwezigheid" aria-label="Aanwezigheid">${AANW.map(x => optie(x, x, r.aanwezigheid)).join('')}</select></td>
      <td><button class="knop stil klein" type="button" data-weg="${i}" aria-label="Verwijderen">${ic('kruis')}</button></td></tr>`; }).join('');
    $('#deelname-toevoegen').innerHTML = '<option value="">+ Persoon toevoegen…</option>' + S.meta.personen.filter(p => !rijen.some(r => r.persoon === p.id)).map(p => optie(p.id, naamVan(p))).join('');
  };
  openModal(`<div class="modal-kop"><h2>Aanwezigheid</h2><button class="sluit" data-actie="sluit-modal" aria-label="Sluiten">${ic('kruis')}</button></div>
    <form id="deelname-form"><table class="deelnametabel"><tbody id="deelname-rijen"></tbody></table>
    <select id="deelname-toevoegen" aria-label="Persoon toevoegen"></select><div class="foutmelding" id="modal-fout" hidden></div></form>
    <div class="modal-voet"><div class="rechts"><button class="knop" type="button" data-actie="sluit-modal">Annuleren</button><button class="knop primair" type="submit" form="deelname-form">Opslaan</button></div></div>`, true);
  teken();
  const form = $('#deelname-form');
  form.addEventListener('change', e => {
    if (e.target.id === 'deelname-toevoegen') { if (e.target.value) { rijen.push({ persoon: Number(e.target.value), rol: 'gast', aanwezigheid: 'aanwezig' }); teken(); } return; }
    const i = e.target.dataset.i; if (i !== undefined) rijen[i][e.target.dataset.k] = e.target.value;
  });
  form.addEventListener('click', e => { const b = e.target.closest('[data-weg]'); if (b) { rijen.splice(Number(b.dataset.weg), 1); teken(); } });
  form.addEventListener('submit', async e => {
    e.preventDefault();
    try { await api(`vergadering/${V.id}/deelname`, { methode: 'PUT', data: { deelname: rijen } }); sluitModal(); toast('Aanwezigheid opgeslagen'); await herlaad(); }
    catch (err) { const f = $('#modal-fout'); f.textContent = err.message; f.hidden = false; }
  });
}

async function formPersoon(id = null) {
  const p = id ? await api('persoon/' + id) : null;
  formulier({
    titel: p ? 'Persoon bewerken' : 'Nieuwe persoon', waarden: p || { actief: '1' },
    velden: [
      { rij: [{ n: 'voornaam', l: 'Voornaam', req: true }, { n: 'achternaam', l: 'Achternaam', req: true }] },
      { n: 'functie', l: 'Functie' },
      { rij: [{ n: 'email', l: 'E-mail', t: 'email', req: true }, { n: 'telefoon', l: 'Telefoon' }] },
      { rij: [{ n: 'bedrijfsonderdeel', l: 'Werkt bij', t: 'select', leeg: '—', opties: ONDERDEEL_OPTIES() }, { n: 'actief', l: 'Actief', t: 'select', opties: [['1', 'ja'], ['0', 'nee, vertrokken']] }] },
      { n: 'foto', l: 'Foto (bestandsnaam in static/fotos)', ph: 'voornaam-achternaam.jpg' },
    ],
    opslaan: async d => {
      d.actief = Number(d.actief);
      if (p) { await api('persoon/' + p.id, { methode: 'PUT', data: d }); toast('Persoon opgeslagen'); await herlaad(); }
      else { const r = await api('persoon', { methode: 'POST', data: d }); toast('Persoon toegevoegd'); await herlaadMeta(); go('#/persoon/' + r.id); }
    },
    verwijder: p ? async () => { await api('persoon/' + p.id, { methode: 'DELETE' }); toast('Persoon verwijderd'); await herlaadMeta(); go('#/personen'); } : null,
  });
}

async function formOnderwerp(id = null) {
  const o = id ? await api('onderwerp/' + id) : null;
  formulier({
    titel: o ? 'Onderwerp bewerken' : 'Nieuw onderwerp', waarden: o || {},
    velden: [
      { n: 'naam', l: 'Naam', req: true },
      { n: 'omschrijving', l: 'Omschrijving', t: 'textarea' },
      { n: 'portefeuillehouder', l: 'Portefeuillehouder', t: 'select', leeg: '—', opties: PERS_OPTIES() },
      { n: 'trefwoorden', l: 'Trefwoorden', ph: 'Extra zoektermen en synoniemen, gescheiden door spaties' },
    ],
    opslaan: async d => {
      if (o) { await api('onderwerp/' + o.id, { methode: 'PUT', data: d }); toast('Onderwerp opgeslagen'); await herlaad(); }
      else { const r = await api('onderwerp', { methode: 'POST', data: d }); toast('Onderwerp toegevoegd'); await herlaadMeta(); go('#/onderwerp/' + r.id); }
    },
    verwijder: o ? async () => { await api('onderwerp/' + o.id, { methode: 'DELETE' }); toast('Onderwerp verwijderd'); await herlaadMeta(); go('#/onderwerpen'); } : null,
  });
}

async function formOnderdeel(id = null) {
  const o = id ? await api('bedrijfsonderdeel/' + id) : null;
  formulier({
    titel: o ? 'Bedrijfsonderdeel bewerken' : 'Nieuw bedrijfsonderdeel', waarden: o ? { ...o, actief: String(o.actief) } : { actief: '1', soort: 'team' },
    velden: [
      { rij: [{ n: 'naam', l: 'Naam', req: true }, { n: 'afkorting', l: 'Afkorting', req: true, hulp: 'Gebruikt in besluitnummers, bijv. MTB-2026-004' }] },
      { rij: [{ n: 'soort', l: 'Soort', t: 'select', opties: ['bestuur', 'directie', 'afdeling', 'team', 'commissie', 'projectgroep'].map(s => [s, s]) },
        { n: 'valt_onder', l: 'Valt onder', t: 'select', leeg: '— (hoogste niveau)', opties: ONDERDEEL_OPTIES().filter(([x]) => !o || x !== o.id) }] },
      { n: 'actief', l: 'Actief', t: 'select', opties: [['1', 'ja'], ['0', 'nee, opgeheven']] },
    ],
    opslaan: async d => {
      d.actief = Number(d.actief); d.afkorting = d.afkorting.toUpperCase();
      if (o) { await api('bedrijfsonderdeel/' + o.id, { methode: 'PUT', data: d }); toast('Opgeslagen'); await herlaad(); }
      else { const r = await api('bedrijfsonderdeel', { methode: 'POST', data: d }); toast('Bedrijfsonderdeel toegevoegd'); await herlaadMeta(); go('#/onderdeel/' + r.id); }
    },
    verwijder: o ? async () => { await api('bedrijfsonderdeel/' + o.id, { methode: 'DELETE' }); toast('Verwijderd'); await herlaadMeta(); go('#/onderdelen'); } : null,
  });
}

async function formLeden(id) {
  const o = await api('bedrijfsonderdeel/' + id);
  const ROLLEN = ['voorzitter', 'lid', 'notulist', 'adviseur', 'gast'];
  const leden = Object.fromEntries(o.leden.map(l => [l.id, l.rol]));
  openModal(`<div class="modal-kop"><h2>Vaste leden van ${esc(o.naam)}</h2><button class="sluit" data-actie="sluit-modal" aria-label="Sluiten">${ic('kruis')}</button></div>
    <form id="leden-form"><table class="deelnametabel"><tbody>${S.meta.personen.filter(p => p.actief).map(p => `<tr>
      <td><label class="persoonlink" style="cursor:pointer"><input type="checkbox" name="lid" value="${p.id}" ${leden[p.id] ? 'checked' : ''}> ${av(p.foto, naamVan(p), 'klein')}${esc(naamVan(p))}</label></td>
      <td><select name="rol-${p.id}" aria-label="Rol">${ROLLEN.map(r => optie(r, r, leden[p.id] || 'lid')).join('')}</select></td></tr>`).join('')}</tbody></table>
      <div class="foutmelding" id="modal-fout" hidden></div></form>
    <div class="modal-voet"><div class="rechts"><button class="knop" type="button" data-actie="sluit-modal">Annuleren</button><button class="knop primair" type="submit" form="leden-form">Opslaan</button></div></div>`, true);
  $('#leden-form').addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target;
    const data = $$('input[name=lid]:checked', f).map(i => ({ persoon: Number(i.value), rol: f.elements['rol-' + i.value].value }));
    try { await api(`bedrijfsonderdeel/${id}/leden`, { methode: 'PUT', data: { leden: data } }); sluitModal(); toast('Vaste leden opgeslagen'); await herlaad(); }
    catch (err) { const m = $('#modal-fout'); m.textContent = err.message; m.hidden = false; }
  });
}

async function zorgVoorV(vid) { if (!V || V.id !== Number(vid)) V = await api('vergadering/' + vid); }

// ───────────────────────── gebeurtenissen ─────────────────────────
const ACTIES = {
  'sluit-modal': () => sluitModal(),
  'nieuwe-vergadering': el => formVergadering(null, el.dataset.onderdeel ? { bedrijfsonderdeel: el.dataset.onderdeel } : {}),
  'bewerk-vergadering': () => formVergadering(V),
  'bewerk-deelname': () => formDeelname(),
  'nieuw-agendapunt': () => formAgendapunt(),
  'bewerk-agendapunt': el => formAgendapunt(V.agendapunten.find(p => p.id === Number(el.dataset.id))),
  'nieuw-besluit': el => formBesluit(null, { agendapunt: el.dataset.punt }),
  'bewerk-besluit': async el => { await zorgVoorV(el.dataset.vergadering); formBesluit(await api('besluit/' + el.dataset.id)); },
  'nieuwe-actie': el => formActie(null, { agendapunt: el.dataset.punt }),
  'bewerk-actie': async el => { await zorgVoorV(el.dataset.vergadering); formActie(await api('actie/' + el.dataset.id)); },
  'nieuw-stuk': el => formStukUpload({ agendapunt: el.dataset.punt }),
  'bewerk-stuk': el => formStuk(V.stukken.find(s => s.id === Number(el.dataset.id))),
  'nieuwe-persoon': () => formPersoon(),
  'bewerk-persoon': el => formPersoon(el.dataset.id),
  'nieuw-onderwerp': () => formOnderwerp(),
  'bewerk-onderwerp': el => formOnderwerp(el.dataset.id),
  'nieuw-onderdeel': () => formOnderdeel(),
  'bewerk-onderdeel': el => formOnderdeel(el.dataset.id),
  'bewerk-leden': el => formLeden(el.dataset.id),
  'zoekfilter': el => zoekNaar({ [el.dataset.k]: el.dataset.v }),
  'zoekperiode': el => zoekNaar({ van: el.dataset.van, tot: el.dataset.tot }),
  'zoekwis': () => location.replace('#/zoeken'),
  'lijstfilter': el => lijstFilter(el.dataset.k, el.dataset.v),
};
function lijstFilter(k, v) {
  const [pad, query] = location.hash.slice(1).split('?');
  const p = new URLSearchParams(query || '');
  v ? p.set(k, v) : p.delete(k);
  const s = p.toString();
  location.replace('#' + pad + (s ? '?' + s : ''));
}

document.addEventListener('click', async e => {
  const el = e.target.closest('[data-actie]');
  if (el && ACTIES[el.dataset.actie]) {
    e.preventDefault();
    try { await ACTIES[el.dataset.actie](el, e); } catch (err) { toast(err.message, true); }
    return;
  }
  const rij = e.target.closest('tr[data-href]');
  if (rij && !e.target.closest('a')) go(rij.dataset.href);
  if (e.target === laag) sluitModal();
});

let typTimer;
document.addEventListener('input', e => {
  const t = e.target;
  if (t.id === 'zoek-q') { clearTimeout(typTimer); typTimer = setTimeout(() => zoekNaar({ q: t.value.trim() }), 250); }
  else if (t.matches('[data-lijstfilter]') && t.type === 'search') { clearTimeout(typTimer); typTimer = setTimeout(() => lijstFilter(t.dataset.lijstfilter, t.value.trim()), 300); }
  else if (t.id === 'personen-filter') {
    const q = t.value.toLowerCase().trim();
    $$('#personenkaarten .kaart').forEach(k => { k.hidden = q && !k.dataset.zoektekst.includes(q); });
  }
});
document.addEventListener('change', async e => {
  const t = e.target;
  if (t.matches('[data-zoekveld]')) zoekNaar({ [t.dataset.zoekveld]: t.value });
  else if (t.matches('[data-lijstfilter]') && t.type !== 'search') lijstFilter(t.dataset.lijstfilter, t.value);
  else if (t.matches('[data-actiestatus]')) {
    try { await api('actie/' + t.dataset.actiestatus, { methode: 'PUT', data: { status: t.value } }); toast(`Status: ${t.value}`); await herlaad(); }
    catch (err) { toast(err.message, true); }
  } else if (t.id === 'gebruiker') {
    S.gebruiker = t.value; schrijfOpslag('gebruiker', t.value);
    toast(t.value ? `Je werkt nu als ${naamVan(persoon(t.value))}` : 'Geen gebruiker gekozen'); route();
  }
});
document.addEventListener('submit', async e => {
  const f = e.target;
  if (f.id === 'snelzoek') { e.preventDefault(); const q = $('#snelzoek-q').value.trim(); location.hash = '#/zoeken' + qs({ q }); }
  else if (f.dataset.form === 'voortgang') {
    e.preventDefault();
    const tekst = f.elements.tekst.value.trim();
    if (!tekst) return;
    try { await api(`actie/${f.dataset.id}/voortgang`, { methode: 'POST', data: { tekst } }); toast('Update toegevoegd'); await route(); }
    catch (err) { toast(err.message, true); }
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !laag.hidden) { sluitModal(); return; }
  if (e.key === '/' && !e.target.closest('input, textarea, select') && laag.hidden) { e.preventDefault(); $('#snelzoek-q').focus(); }
});

window.addEventListener('hashchange', () => { route().then(() => { if (!/[?&]punt=/.test(location.hash) && !location.hash.startsWith('#/zoeken') && !/^#\/(acties|besluiten|vergaderingen)\?/.test(location.hash)) scrollTo(0, 0); }); });

(async function start() {
  try { await herlaadMeta(); await route(); }
  catch (e) { main.innerHTML = `<div class="paneel"><h2>De server is niet bereikbaar</h2><p class="gedempt">Start het vergaderregister met <code>python3 server.py</code> en ververs deze pagina.</p></div>`; }
})();
