-- Vergaderregister: datamodel (zie ../datamodel.html)
-- Elke hoofdtabel heeft audit-kolommen: aangemaakt_op/door, gewijzigd_op/door.
--
-- Let op: deze database is alleen een INDEX. De bron van waarheid zijn de Markdown-bestanden in data/
-- (zie opslag.py). De index wordt bij het opstarten en na externe wijzigingen opnieuw opgebouwd.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bedrijfsonderdeel (
  id              INTEGER PRIMARY KEY,
  naam            TEXT NOT NULL,
  afkorting       TEXT NOT NULL UNIQUE,
  soort           TEXT NOT NULL CHECK (soort IN ('bestuur','directie','afdeling','team','commissie','projectgroep')),
  valt_onder      INTEGER REFERENCES bedrijfsonderdeel(id) ON DELETE SET NULL,
  actief          INTEGER NOT NULL DEFAULT 1,
  aangemaakt_op TEXT, aangemaakt_door TEXT, gewijzigd_op TEXT, gewijzigd_door TEXT
);

CREATE TABLE IF NOT EXISTS persoon (
  id                INTEGER PRIMARY KEY,
  voornaam          TEXT NOT NULL,
  achternaam        TEXT NOT NULL,
  email             TEXT NOT NULL UNIQUE,
  functie           TEXT,
  bedrijfsonderdeel INTEGER REFERENCES bedrijfsonderdeel(id) ON DELETE SET NULL,
  telefoon          TEXT,
  foto              TEXT,
  actief            INTEGER NOT NULL DEFAULT 1,
  aangemaakt_op TEXT, aangemaakt_door TEXT, gewijzigd_op TEXT, gewijzigd_door TEXT
);

-- Vaste leden per bedrijfsonderdeel: vult de aanwezigheidslijst van een nieuwe vergadering voor.
CREATE TABLE IF NOT EXISTS lidmaatschap (
  bedrijfsonderdeel INTEGER NOT NULL REFERENCES bedrijfsonderdeel(id) ON DELETE CASCADE,
  persoon           INTEGER NOT NULL REFERENCES persoon(id) ON DELETE CASCADE,
  rol               TEXT NOT NULL DEFAULT 'lid' CHECK (rol IN ('voorzitter','lid','notulist','adviseur','gast')),
  PRIMARY KEY (bedrijfsonderdeel, persoon)
);

CREATE TABLE IF NOT EXISTS onderwerp (
  id                 INTEGER PRIMARY KEY,
  naam               TEXT NOT NULL UNIQUE,
  omschrijving       TEXT,
  portefeuillehouder INTEGER REFERENCES persoon(id) ON DELETE SET NULL,
  trefwoorden        TEXT,
  aangemaakt_op TEXT, aangemaakt_door TEXT, gewijzigd_op TEXT, gewijzigd_door TEXT
);

CREATE TABLE IF NOT EXISTS vergadering (
  id                INTEGER PRIMARY KEY,
  bedrijfsonderdeel INTEGER NOT NULL REFERENCES bedrijfsonderdeel(id),
  datum             TEXT NOT NULL,            -- JJJJ-MM-DD
  begintijd         TEXT,                     -- UU:MM
  eindtijd          TEXT,
  titel             TEXT,
  locatie           TEXT,
  status            TEXT NOT NULL DEFAULT 'gepland' CHECK (status IN ('gepland','concept','vastgesteld')),
  vastgesteld_in    INTEGER REFERENCES vergadering(id) ON DELETE SET NULL,
  samenvatting      TEXT,
  aangemaakt_op TEXT, aangemaakt_door TEXT, gewijzigd_op TEXT, gewijzigd_door TEXT
);

CREATE TABLE IF NOT EXISTS deelname (
  vergadering  INTEGER NOT NULL REFERENCES vergadering(id) ON DELETE CASCADE,
  persoon      INTEGER NOT NULL REFERENCES persoon(id) ON DELETE CASCADE,
  rol          TEXT NOT NULL DEFAULT 'lid' CHECK (rol IN ('voorzitter','lid','notulist','adviseur','gast')),
  aanwezigheid TEXT NOT NULL DEFAULT 'aanwezig' CHECK (aanwezigheid IN ('aanwezig','deels','afwezig met bericht','afwezig')),
  PRIMARY KEY (vergadering, persoon)
);

CREATE TABLE IF NOT EXISTS agendapunt (
  id          INTEGER PRIMARY KEY,
  vergadering INTEGER NOT NULL REFERENCES vergadering(id) ON DELETE CASCADE,
  volgnummer  INTEGER NOT NULL,
  titel       TEXT NOT NULL,
  soort       TEXT CHECK (soort IN ('ter besluitvorming','ter bespreking','ter informatie')),
  inbrenger   INTEGER REFERENCES persoon(id) ON DELETE SET NULL,
  bespreking  TEXT,
  aangemaakt_op TEXT, aangemaakt_door TEXT, gewijzigd_op TEXT, gewijzigd_door TEXT
);

CREATE TABLE IF NOT EXISTS agendapunt_onderwerp (
  agendapunt INTEGER NOT NULL REFERENCES agendapunt(id) ON DELETE CASCADE,
  onderwerp  INTEGER NOT NULL REFERENCES onderwerp(id) ON DELETE CASCADE,
  PRIMARY KEY (agendapunt, onderwerp)
);

CREATE TABLE IF NOT EXISTS stuk (
  id                INTEGER PRIMARY KEY,
  titel             TEXT NOT NULL,
  bestandsnaam      TEXT NOT NULL,
  bestandspad       TEXT NOT NULL,             -- relatief t.o.v. data/bijlagen
  mime              TEXT,
  grootte           INTEGER,
  vergadering       INTEGER NOT NULL REFERENCES vergadering(id) ON DELETE CASCADE,
  agendapunt        INTEGER REFERENCES agendapunt(id) ON DELETE SET NULL,
  soort             TEXT CHECK (soort IN ('voorstel','notitie','rapport','presentatie','brief','verslag')),
  auteur            INTEGER REFERENCES persoon(id) ON DELETE SET NULL,
  versie            TEXT,
  datum             TEXT,
  vertrouwelijkheid TEXT NOT NULL DEFAULT 'intern' CHECK (vertrouwelijkheid IN ('openbaar','intern','vertrouwelijk')),
  inhoud_tekst      TEXT,                      -- automatisch uit het bestand gehaald
  aangemaakt_op TEXT, aangemaakt_door TEXT, gewijzigd_op TEXT, gewijzigd_door TEXT
);

CREATE TABLE IF NOT EXISTS besluit (
  id           INTEGER PRIMARY KEY,
  nummer       TEXT NOT NULL UNIQUE,           -- AFKORTING-JAAR-VOLGNR
  titel        TEXT NOT NULL,
  besluittekst TEXT NOT NULL,
  motivering   TEXT,
  vergadering  INTEGER NOT NULL REFERENCES vergadering(id) ON DELETE CASCADE,
  agendapunt   INTEGER REFERENCES agendapunt(id) ON DELETE SET NULL,
  status       TEXT NOT NULL DEFAULT 'genomen' CHECK (status IN ('genomen','aangehouden','ingetrokken','herzien')),
  vervangt     INTEGER REFERENCES besluit(id) ON DELETE SET NULL,
  aangemaakt_op TEXT, aangemaakt_door TEXT, gewijzigd_op TEXT, gewijzigd_door TEXT
);

CREATE TABLE IF NOT EXISTS besluit_onderwerp (
  besluit   INTEGER NOT NULL REFERENCES besluit(id) ON DELETE CASCADE,
  onderwerp INTEGER NOT NULL REFERENCES onderwerp(id) ON DELETE CASCADE,
  PRIMARY KEY (besluit, onderwerp)
);
CREATE TABLE IF NOT EXISTS besluit_grondslag (
  besluit INTEGER NOT NULL REFERENCES besluit(id) ON DELETE CASCADE,
  stuk    INTEGER NOT NULL REFERENCES stuk(id) ON DELETE CASCADE,
  PRIMARY KEY (besluit, stuk)
);
CREATE TABLE IF NOT EXISTS besluit_betrokkene (
  besluit INTEGER NOT NULL REFERENCES besluit(id) ON DELETE CASCADE,
  persoon INTEGER NOT NULL REFERENCES persoon(id) ON DELETE CASCADE,
  PRIMARY KEY (besluit, persoon)
);

CREATE TABLE IF NOT EXISTS actie (
  id           INTEGER PRIMARY KEY,
  titel        TEXT NOT NULL,
  omschrijving TEXT,
  eigenaar     INTEGER NOT NULL REFERENCES persoon(id),
  deadline     TEXT,
  status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','loopt','afgerond','vervallen')),
  vergadering  INTEGER NOT NULL REFERENCES vergadering(id) ON DELETE CASCADE,
  agendapunt   INTEGER REFERENCES agendapunt(id) ON DELETE SET NULL,
  besluit      INTEGER REFERENCES besluit(id) ON DELETE SET NULL,
  afgerond_op  TEXT,
  aangemaakt_op TEXT, aangemaakt_door TEXT, gewijzigd_op TEXT, gewijzigd_door TEXT
);

CREATE TABLE IF NOT EXISTS actie_uitvoerder (
  actie   INTEGER NOT NULL REFERENCES actie(id) ON DELETE CASCADE,
  persoon INTEGER NOT NULL REFERENCES persoon(id) ON DELETE CASCADE,
  PRIMARY KEY (actie, persoon)
);

CREATE TABLE IF NOT EXISTS actie_voortgang (
  id          INTEGER PRIMARY KEY,
  actie       INTEGER NOT NULL REFERENCES actie(id) ON DELETE CASCADE,
  datum       TEXT NOT NULL,
  tekst       TEXT NOT NULL,
  vergadering INTEGER REFERENCES vergadering(id) ON DELETE SET NULL,
  aangemaakt_op TEXT, aangemaakt_door TEXT
);

-- Welk record in welk Markdown-bestand staat (pad relatief t.o.v. data/). Bestandsnamen blijven stabiel.
CREATE TABLE IF NOT EXISTS bestand (
  soort TEXT NOT NULL,
  id    INTEGER NOT NULL,
  pad   TEXT NOT NULL,
  PRIMARY KEY (soort, id)
);

-- Volledige-tekstindex over alle soorten. Wordt door server.py bijgewerkt na elke wijziging.
CREATE VIRTUAL TABLE IF NOT EXISTS zoekindex USING fts5(
  soort UNINDEXED, ref UNINDEXED, titel, tekst,
  tokenize = 'unicode61 remove_diacritics 2'
);

-- Hulpviews voor zoeken en filteren: elk item met zijn vergaderdatum en bedrijfsonderdeel.
CREATE VIEW IF NOT EXISTS v_item AS
  SELECT 'vergadering' AS soort, v.id, COALESCE(v.titel, o.naam) AS titel, v.datum, v.bedrijfsonderdeel AS onderdeel, v.status, v.id AS vergadering
    FROM vergadering v JOIN bedrijfsonderdeel o ON o.id = v.bedrijfsonderdeel
  UNION ALL
  SELECT 'agendapunt', a.id, a.titel, v.datum, v.bedrijfsonderdeel, a.soort, v.id
    FROM agendapunt a JOIN vergadering v ON v.id = a.vergadering
  UNION ALL
  SELECT 'besluit', b.id, b.titel, v.datum, v.bedrijfsonderdeel, b.status, v.id
    FROM besluit b JOIN vergadering v ON v.id = b.vergadering
  UNION ALL
  SELECT 'actie', x.id, x.titel, v.datum, v.bedrijfsonderdeel, x.status, v.id
    FROM actie x JOIN vergadering v ON v.id = x.vergadering
  UNION ALL
  SELECT 'stuk', s.id, s.titel, v.datum, v.bedrijfsonderdeel, s.vertrouwelijkheid, v.id
    FROM stuk s JOIN vergadering v ON v.id = s.vergadering;

CREATE VIEW IF NOT EXISTS v_item_persoon AS
  SELECT 'vergadering' AS soort, vergadering AS id, persoon FROM deelname WHERE aanwezigheid IN ('aanwezig','deels')
  UNION SELECT 'agendapunt', id, inbrenger FROM agendapunt WHERE inbrenger IS NOT NULL
  UNION SELECT 'besluit', besluit, persoon FROM besluit_betrokkene
  UNION SELECT 'actie', id, eigenaar FROM actie
  UNION SELECT 'actie', actie, persoon FROM actie_uitvoerder
  UNION SELECT 'stuk', id, auteur FROM stuk WHERE auteur IS NOT NULL;

CREATE VIEW IF NOT EXISTS v_item_onderwerp AS
  SELECT 'agendapunt' AS soort, agendapunt AS id, onderwerp FROM agendapunt_onderwerp
  UNION SELECT 'besluit', besluit, onderwerp FROM besluit_onderwerp
  UNION SELECT 'besluit', b.id, ao.onderwerp FROM besluit b JOIN agendapunt_onderwerp ao ON ao.agendapunt = b.agendapunt
  UNION SELECT 'actie', x.id, ao.onderwerp FROM actie x JOIN agendapunt_onderwerp ao ON ao.agendapunt = x.agendapunt
  UNION SELECT 'stuk', s.id, ao.onderwerp FROM stuk s JOIN agendapunt_onderwerp ao ON ao.agendapunt = s.agendapunt
  UNION SELECT 'vergadering', a.vergadering, ao.onderwerp FROM agendapunt a JOIN agendapunt_onderwerp ao ON ao.agendapunt = a.id;
