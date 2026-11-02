# Vergaderregister (proof of concept)

Verslagen van vergaderingen als losse, gekoppelde gegevens in plaats van één Word-document. Elk besluit, elke actie en elk stuk is los terug te vinden: per persoon, per bedrijfsonderdeel, per onderwerp of door de tijd heen. Het datamodel staat in [../datamodel.html](../datamodel.html).

## Starten

Dubbelklik op `start.command` (macOS), of in een terminal:

```bash
python3 server.py
```

Open daarna http://127.0.0.1:8765. Je hebt alleen Python 3 nodig; er wordt niets geïnstalleerd en er gaat geen gegevensverkeer naar buiten (ook geen webfonts).

De demodata opnieuw laden, waarbij alle gegevens in `data/` worden gewist. De demodata spelen in een UWV-context: de organisatieonderdelen en thema's komen uit openbare UWV-publicaties (jaarverslag 2025, jaarplan 2026, viermaandenverslag 2026, financiële nota's). Alle personen, vergaderingen en besluiten zijn verzonnen, net als de meeste cijfers; cijfers die openbaar zijn, staan zo in de stukken vermeld.

```bash
python3 seed.py --opnieuw
```

### Zonder server, in de browser

Er is ook een browserversie die zonder installatie draait, bijvoorbeeld op GitHub Pages. Daarin draait `server.py` zelf in de browser via [Pyodide](https://pyodide.org) (Python in WebAssembly). Bouwen:

```bash
python3 bouw_web.py
```

Dat zet een statische site in `_site/`. Bij elke push naar `main` doet de workflow in `.github/workflows/pages.yml` dit automatisch en publiceert het resultaat. Verschillen met de lokale versie:

- Bij het eerste bezoek haalt de browser Pyodide op van cdn.jsdelivr.net (ongeveer 10 MB). Dit is dus de enige variant met gegevensverkeer naar buiten.
- Wijzigingen worden in de browser bewaard (IndexedDB), alleen voor die bezoeker en alleen op dat apparaat. Na 4 uur (`RESET_UUR` in `web/browser.js`) en na elke nieuwe publicatie begint de browser weer met de demodata uit `data/`. Met "Demogegevens terugzetten" linksonder kan dat ook meteen.

## Waar staan de gegevens?

Alles staat als **Markdown met YAML-frontmatter** in `data/`. Elk record is één bestand:

| Map | Inhoud |
|---|---|
| `🏛 Bedrijfsonderdelen/` | wie vergadert, met vaste leden |
| `👤 Personen/` | deelnemers en actiehouders |
| `🚀 Onderwerpen/` | dossiers die terugkomen |
| `📆 Vergaderingen/` | datum, aanwezigheid en agenda; elk agendapunt is een `## kop` met de bespreking eronder |
| `🎯 Besluiten/` | besluittekst en motivering, met vast besluitnummer |
| `✅ Acties/` | eigenaar, deadline, status en voortgang |
| `📎 Stukken/` | gegevens over de bijlage, met de uitgelezen tekst; de bestanden zelf staan in `📎 Stukken/bestanden/` |

Verwijzingen zijn Obsidian-links, zoals `eigenaar: "[[👤 Anna de Vries]]"`. Je kunt `data/` dus ook als vault openen in Obsidian, of de bestanden bewerken in elke teksteditor. De app ziet zulke wijzigingen meteen. Een nieuw bestand zonder `id` krijgt er automatisch een.

`data/.cache/index.db` is alleen een zoekindex (SQLite met full-text search). Die wordt bij het starten opnieuw opgebouwd uit de bestanden en mag altijd weg.

Er zijn ook twee exports:

- per vergadering een leesbaar verslag als Markdown (knop "Verslag (.md)")
- alles in één JSON-bestand (linksonder "Alles exporteren")

## Bestanden

| Bestand | Wat het doet |
|---|---|
| `server.py` | webserver, API, zoeken, uploads en tekstextractie uit bijlagen |
| `opslag.py` | lezen en schrijven van de Markdown-bestanden |
| `schema.sql` | structuur van de zoekindex |
| `seed.py` | demodata |
| `static/` | de webinterface (HTML, CSS en JavaScript, zonder bibliotheken) |
| `bouw_web.py` | bouwt de browserversie zonder server in `_site/` |
| `web/browser.js` | koppelt de webinterface in de browserversie aan `server.py` in Pyodide |

## Bewuste beperkingen van deze proof of concept

- Er is geen inlog. Linksonder kies je wie je bent; die naam wordt vastgelegd als maker of wijziger.
- Vertrouwelijkheid is alleen een label. Er zijn nog geen toegangsrechten per persoon.
- De server luistert alleen op deze computer (127.0.0.1) en verwerkt één verzoek tegelijk.
- Tekst uit PDF's wordt het best gelezen als `pypdf` geïnstalleerd is. Zonder `pypdf` werkt een eenvoudige ingebouwde lezer. Word-, PowerPoint-, Excel-, OpenDocument-, tekst- en Markdown-bestanden worden zonder extra software gelezen.
