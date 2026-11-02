#!/usr/bin/env python3
"""Vult het Vergaderregister met fictieve demodata in een UWV-context.

Organisatieonderdelen en thema's zijn ontleend aan openbare UWV-publicaties (jaarverslag 2025, jaarplan 2026,
viermaandenverslag 2026, financiële nota's). Alle personen, vergaderingen en de meeste cijfers zijn verzonnen.

Schrijft Markdown-bestanden met frontmatter naar data/ (de index wordt daaruit opgebouwd).

Gebruik:  python3 seed.py           (alleen als data/ nog leeg is)
          python3 seed.py --opnieuw (wist eerst alle bestaande gegevens in data/)
"""
import os
import shutil
import sys

import opslag
import server
from server import BIJLAGEN, DATA, DB, maak, verbind

G = 'Demo-import'

ORGANISATIE = 'UWV · fictieve demodata'

ONDERDELEN = [
    # sleutel, naam, afkorting, soort, valt_onder
    ('rvb', 'Raad van Bestuur', 'RVB', 'bestuur', None),
    ('sio', 'Service en Inkomensondersteuning', 'SIO', 'directie', 'rvb'),
    ('smz', 'Sociaal-medische Zaken', 'SMZ', 'directie', 'rvb'),
    ('wb', 'Werkbedrijf', 'WB', 'directie', 'rvb'),
    ('wcz', 'Werkcentrum regio Zwolle', 'WCZ', 'team', 'wb'),
    ('gd', 'Gegevensdiensten', 'GD', 'directie', 'rvb'),
    ('wia', 'Programmaraad WIA-herstelactie', 'WIA', 'projectgroep', 'rvb'),
    ('ccu', 'Centrale Cliëntenraad', 'CCU', 'commissie', None),
]

PERSONEN = [
    # sleutel, voornaam, achternaam, functie, onderdeel, telefoon  (alle personen zijn verzonnen)
    ('pieter', 'Pieter', 'Smit', 'Voorzitter Raad van Bestuur', 'rvb', '06-11223344'),
    ('thomas', 'Thomas', 'Visser', 'Lid Raad van Bestuur (financiën en informatievoorziening)', 'rvb', '06-78901234'),
    ('lisa', 'Lisa', 'Hendriks', 'Lid Raad van Bestuur (sociaal-medische dienstverlening)', 'rvb', '06-67890123'),
    ('sophie', 'Sophie', 'Mulder', 'Algemeen directeur Werkbedrijf', 'wb', '06-89012345'),
    ('marieke', 'Marieke', 'van Dijk', 'Bestuurssecretaris', 'rvb', '06-22334455'),
    ('wouter', 'Wouter', 'Kok', 'Voorzitter Centrale Cliëntenraad', 'ccu', '06-55667788'),
    ('emma', 'Emma', 'Bos', 'Lid Centrale Cliëntenraad', 'ccu', '06-01234567'),
    ('anna', 'Anna', 'de Vries', 'Programmadirecteur WIA-herstelactie', 'wia', '06-12345678'),
    ('arie', 'Arie', 'Bakker', 'Directeur Sociaal-medische Zaken', 'smz', '06-23456789'),
    ('bas', 'Bas', 'Peters', 'Senior data-analist', 'gd', '06-33445566'),
    ('fleur', 'Fleur', 'Meijer', 'Teammanager Werkcentrum regio Zwolle', 'wcz', '06-44556677'),
    ('jeroen', 'Jeroen', 'de Groot', 'Directeur Gegevensdiensten', 'gd', '06-90123456'),
    ('mark', 'Mark', 'Jansen', 'Verzekeringsarts, coördinator capaciteit', 'smz', '06-34567890'),
    ('nick', 'Nick', 'van den Berg', 'Senior communicatieadviseur', 'rvb', '06-45678901'),
    ('stijn', 'Stijn', 'Vermeer', 'Directeur Service en Inkomensondersteuning', 'sio', '06-56789012'),
]
EMAILDOMEIN = 'uwv-demo.example'

LEDEN = {
    'rvb': [('pieter', 'voorzitter'), ('thomas', 'lid'), ('lisa', 'lid'), ('marieke', 'notulist')],
    'sio': [('stijn', 'voorzitter'), ('anna', 'lid'), ('nick', 'notulist'), ('bas', 'adviseur')],
    'smz': [('arie', 'voorzitter'), ('mark', 'lid'), ('bas', 'lid'), ('lisa', 'adviseur'), ('nick', 'notulist')],
    'wb': [('sophie', 'voorzitter'), ('fleur', 'lid'), ('bas', 'lid'), ('stijn', 'adviseur'), ('nick', 'notulist')],
    'wcz': [('fleur', 'voorzitter'), ('bas', 'lid'), ('nick', 'notulist')],
    'gd': [('jeroen', 'voorzitter'), ('bas', 'lid'), ('stijn', 'lid'), ('thomas', 'adviseur'), ('nick', 'notulist')],
    'wia': [('anna', 'voorzitter'), ('stijn', 'lid'), ('jeroen', 'lid'), ('arie', 'lid'), ('thomas', 'adviseur'), ('bas', 'notulist')],
    'ccu': [('wouter', 'voorzitter'), ('emma', 'lid'), ('pieter', 'adviseur'), ('lisa', 'adviseur'), ('marieke', 'notulist')],
}

ONDERWERPEN = [
    ('wiaherstel', 'WIA-herstelactie', 'Herstel van mogelijk onjuist vastgestelde WIA-uitkeringen (dagloonberekening, periode 2020–2024) en de vergoedingsregeling.', 'thomas', 'dagloon loonloze tijdvakken vergoedingsregeling herberekening'),
    ('smz', 'Ontwikkelagenda sociaal-medische dienstverlening', 'Kortere wachttijden en betere dienstverlening voor mensen die door ziekte niet of deels kunnen werken.', 'lisa', 'achterstanden claimbeoordeling verzekeringsartsen herbeoordeling intake'),
    ('kwaliteit', 'Kwaliteit op orde', 'Tijdige, juiste en begrijpelijke beslissingen: kwaliteitskaders, beheersingsraamwerk en kwaliteitsmanagementsysteem.', 'pieter', 'KMS beheersingsraamwerk kwaliteitskaders begrijpelijk'),
    ('verandermotor', 'Verandermotor', 'Organisatiebrede manier van veranderen met multidisciplinaire teams, clusters en vakgroepen.', 'pieter', 'clusters vakgroepen teams transitie'),
    ('werkcentra', 'Werkcentra en arbeidsmarktregio’s', 'Fysieke en digitale Werkcentra in de 35 arbeidsmarktregio’s, samen met gemeenten.', 'sophie', 'werkzoekenden werkgevers gemeenten regio'),
    ('ww', 'WW en export van uitkeringen', 'Werkloosheidswet: volume, werkvoorraad en export van WW naar andere EU-lidstaten (Verordening 883/2004).', 'stijn', 'werkloosheid export EU 883/2004'),
    ('digiweer', 'Digitale weerbaarheid', 'Bescherming van de belangrijkste diensten en processen tegen digitale dreigingen.', 'thomas', 'cyber security informatiebeveiliging BIO kroonjuwelen'),
    ('polis', 'Polisadministratie en gegevensdeling', 'Lonen, uitkeringen en arbeidscontracten van alle verzekerden, en het delen van die gegevens met ketenpartners.', 'jeroen', 'loonaangifte gegevens DPIA ketenpartners'),
    ('client', 'Cliëntparticipatie en klantervaring', 'Advies van de cliëntenraden en de ervaringen van cliënten met de dienstverlening.', 'pieter', 'cliëntenraad klanttevredenheid brieven'),
    ('financien', 'Begroting en financiële nota’s', 'Jaarplan, januarinota, juninota en tertaalverslagen.', 'thomas', 'jaarplan juninota januarinota verantwoording'),
    ('autonomie', 'Informatieautonomie', 'Zelf regie houden over informatie en systemen: open standaarden, minder afhankelijkheid van leveranciers.', 'thomas', 'open standaarden vendor lock-in vergaderregister'),
]

# Per vergadering: onderdeel, datum, tijden, locatie, status, afwezig {persoon: aanwezigheid}, optioneel gasten [(persoon, rol)],
# samenvatting, punten.
# Punt: titel, soort, inbrenger, onderwerpen, bespreking, stukken, besluiten, acties.
# Stuk: (sleutel, titel, soort, auteur, vertrouwelijkheid, alinea's)
# Besluit: (sleutel, titel, tekst, motivering, status, betrokkenen, grondslag-stukken, vervangt)
# Actie: (titel, omschrijving, eigenaar, deadline, status, afgerond_op, uitvoerders, besluit-sleutel, voortgang[(datum, tekst)])

VERGADERINGEN = [
 dict(k='v1', o='rvb', d='2026-01-13', t=('09:30', '12:00'), loc='Amsterdam, La Guardiaweg', st='vastgesteld', afw={},
  gasten=[('anna', 'adviseur')],
  sam='De Raad van Bestuur stelde het jaarplan 2026 vast met vier strategische prioriteiten en bekrachtigde de planning van de WIA-herstelactie.',
  p=[
   dict(t='Jaarplan 2026', s='ter besluitvorming', i='thomas', ow=['financien', 'kwaliteit', 'verandermotor'],
        b='Het jaarplan kent vier prioriteiten: de WIA-herstelactie, de Ontwikkelagenda sociaal-medische dienstverlening, Kwaliteit op orde en de Verandermotor. Thomas Visser benadrukte dat de stijgende uitgaven aan uitkeringen druk zetten op de uitvoeringsbudgetten.',
        stukken=[('st_jp26', 'Jaarplan 2026 (bestuursversie)', 'voorstel', 'thomas', 'intern', [
            'Bestuursversie van het jaarplan 2026, binnen de strategie Meer voor elkaar 2025–2030.',
            'Vier strategische prioriteiten: (1) de WIA-herstelactie, (2) de Ontwikkelagenda sociaal-medische dienstverlening, (3) het programma Kwaliteit op orde, gericht op tijdige, juiste en begrijpelijke beslissingen, en (4) de Verandermotor als plek waar vanaf 2026 alle veranderopdrachten worden gerealiseerd.',
            'Daarnaast blijft de digitale weerbaarheid een randvoorwaarde. Het interne kwaliteitsmanagementsysteem (KMS) wordt versterkt.',
            'Voorgesteld besluit: het jaarplan 2026 vaststellen en aanbieden aan de minister van SZW.'])],
        besluiten=[('b_jp26', 'Jaarplan 2026 vastgesteld', 'De Raad van Bestuur stelt het jaarplan 2026 vast met vier strategische prioriteiten: WIA-herstelactie, Ontwikkelagenda sociaal-medische dienstverlening, Kwaliteit op orde en Verandermotor.',
                    'Het jaarplan geeft richting aan de verbetering van de dienstverlening binnen de beschikbare capaciteit.', 'genomen', ['pieter', 'thomas', 'lisa'], ['st_jp26'], None)],
        acties=[('Jaarplan 2026 aanbieden aan de minister en publiceren', 'Aanbiedingsbrief opstellen en publicatie op de website voorbereiden.', 'marieke', '2026-01-30', 'afgerond', '2026-01-28', ['nick'], 'b_jp26', [])]),
   dict(t='Planning WIA-herstelactie', s='ter besluitvorming', i='anna', ow=['wiaherstel'],
        b='Anna de Vries schetste de planning. Uitbetalingen uit de vergoedingsregeling zijn haalbaar vanaf oktober 2026, mits de gegevenslevering uit de Polisadministratie op tijd rond is.',
        stukken=[],
        besluiten=[('b_wiaplan', 'Eerste uitbetalingen WIA-vergoedingsregeling gepland voor oktober 2026', 'De Raad van Bestuur stelt oktober 2026 vast als streefdatum voor de eerste uitbetalingen uit de WIA-vergoedingsregeling.',
                    'Cliënten moeten zo snel mogelijk duidelijkheid krijgen; eerder uitbetalen is niet verantwoord gezien de benodigde controles.', 'genomen', ['pieter', 'thomas'], [], None)],
        acties=[('Uitvoeringsplan vergoedingsregeling opstellen', 'Werk processen, systeemaanpassingen en controles uit voor de uitbetalingen.', 'anna', '2026-03-01', 'afgerond', '2026-02-26', ['stijn', 'jeroen'], 'b_wiaplan', [])]),
  ]),
 dict(k='v2', o='smz', d='2026-01-20', t=('13:00', '15:00'), loc='Utrecht, Daalseplein', st='vastgesteld', afw={'lisa': 'afwezig met bericht'},
  sam='Bespreking van de achterstanden in WIA-claimbeoordelingen en de start van het ontwerp van een uniform intakeproces.',
  p=[
   dict(t='Achterstanden WIA-claimbeoordelingen', s='ter besluitvorming', i='mark', ow=['smz'],
        b='De werkvoorraad blijft groeien. Eind september 2025 lagen er al zo’n 25.000 claimbeoordelingen niet tijdig klaar. Sinds oktober 2025 worden geen zzp-verzekeringsartsen meer ingehuurd. Het MT kiest voor voorrang voor beoordelingen aan het einde van de wachttijd.',
        stukken=[('st_cap1', 'Capaciteitsrapportage SMZ januari 2026', 'rapport', 'mark', 'intern', [
            'Capaciteitsrapportage Sociaal-medische Zaken, januari 2026. Cijfers voor 2026 zijn illustratief voor deze demo.',
            'Achterstand WIA-claimbeoordelingen: circa 25.000 eind september 2025, oplopend naar naar schatting 30.000 eind december 2025. De instroom van nieuwe verzekeringsartsen stagneert, terwijl de uitstroom door pensionering doorgaat. Sinds oktober 2025 worden geen zzp-verzekeringsartsen meer ingehuurd.',
            'Zonder ingrijpen lopen de niet-tijdige claimbeoordelingen verder op. Voorstel: voorrang voor beoordelingen aan het einde van de wachttijd van twee jaar en een strakkere planning van herbeoordelingen.'])],
        besluiten=[('b_voorrang', 'Voorrang voor WIA-beoordelingen aan het einde van de wachttijd', 'SMZ geeft in 2026 voorrang aan WIA-claimbeoordelingen aan het einde van de wachttijd van twee jaar.',
                    'Deze cliënten lopen het grootste risico op inkomensonzekerheid.', 'genomen', ['arie', 'mark'], ['st_cap1'], None),
                   ('b_herb1', 'Planning herbeoordelingen 2026: 12.000', 'SMZ plant voor 2026 circa 12.000 WIA-herbeoordelingen.',
                    'Voorlopige planning, af te stemmen op de werkelijke capaciteit.', 'genomen', ['arie'], ['st_cap1'], None)],
        acties=[('Planning herbeoordelingen 2026 doorrekenen', 'Reken de planning door per district en per beroepsgroep.', 'mark', '2026-03-15', 'afgerond', '2026-03-12', ['bas'], 'b_herb1', [])]),
   dict(t='Uniform intakeproces', s='ter bespreking', i='arie', ow=['smz'],
        b='Er komt één intakeproces voor alle sociaal-medische producten. Begin 2026 start het ontwerp, implementatie volgt in de loop van het jaar.',
        stukken=[], besluiten=[],
        acties=[('Ontwerpteam uniform intakeproces samenstellen', 'Stel een team samen met verzekeringsartsen, arbeidsdeskundigen en klantadviseurs.', 'arie', '2026-02-15', 'afgerond', '2026-02-10', ['mark'], None, [])]),
  ]),
 dict(k='v3', o='wia', d='2026-02-03', t=('10:00', '12:00'), loc='Online', st='vastgesteld', afw={},
  sam='Selectiecriteria voor de herberekening van dagloonbedragen vastgesteld; afspraken over gegevenslevering en brieven aan cliënten.',
  p=[
   dict(t='Selectie dagloonberekeningen 2020–2024', s='ter besluitvorming', i='anna', ow=['wiaherstel', 'polis'],
        b='In de periode 2020–2024 zijn mogelijk tienduizenden WIA-uitkeringen niet juist vastgesteld. Voor herstel van dagloonfouten is € 120 miljoen beschikbaar; voor correcties in loonloze tijdvakken is € 449 miljoen gereserveerd.',
        stukken=[('st_pva', 'Plan van aanpak WIA-herstelactie, fase 2', 'notitie', 'anna', 'intern', [
            'Plan van aanpak voor fase 2 van de WIA-herstelactie.',
            'Doelgroep: cliënten bij wie de dagloonberekening in de periode 2020–2024 mogelijk onjuist is vastgesteld. Beschikbaar budget: € 120 miljoen voor herstel van dagloonfouten en € 449 miljoen voor correcties in loonloze tijdvakken.',
            'Selectie: op basis van gegevens uit de Polisadministratie worden dossiers geselecteerd met (1) loonloze tijdvakken in het refertejaar, (2) samenloop van dienstverbanden en (3) handmatige correcties in de dagloonberekening.',
            'Planning: herberekening in het tweede en derde kwartaal, eerste uitbetalingen uit de vergoedingsregeling vanaf oktober 2026.'])],
        besluiten=[('b_selectie', 'Selectiecriteria herberekening dagloon vastgesteld', 'De programmaraad stelt drie selectiecriteria vast voor de herberekening: loonloze tijdvakken, samenloop van dienstverbanden en handmatige correcties.',
                    'Zo worden alle mogelijk geraakte cliënten gevonden zonder onnodige herberekeningen.', 'genomen', ['anna', 'jeroen'], ['st_pva'], None)],
        acties=[('Datasets uit Polisadministratie klaarzetten voor herberekening', 'Lever per selectiecriterium een gecontroleerde dataset aan het programma.', 'bas', '2026-03-31', 'afgerond', '2026-03-27', ['jeroen'], 'b_selectie',
                 [('2026-03-02', 'Criteria 1 en 2 geleverd.'), ('2026-03-27', 'Criterium 3 geleverd na extra controle op handmatige correcties.')])]),
   dict(t='Brieven aan betrokken cliënten', s='ter bespreking', i='stijn', ow=['wiaherstel', 'client'],
        b='De eerste conceptbrieven zijn te juridisch. Ze worden getest met een cliëntpanel en voorgelegd aan de Centrale Cliëntenraad.',
        stukken=[], besluiten=[],
        acties=[('Conceptbrieven testen met cliëntpanel', 'Test de brieven op begrijpelijkheid en verwerk de uitkomsten.', 'stijn', '2026-03-15', 'afgerond', '2026-03-10', ['nick'], None, [])]),
  ]),
 dict(k='v4', o='wb', d='2026-02-10', t=('10:00', '12:30'), loc='Online', st='vastgesteld', afw={},
  sam='Planning voor de opening van fysieke Werkcentra in alle arbeidsmarktregio’s en de verwachte stijging van de WW-instroom.',
  p=[
   dict(t='Opening Werkcentra', s='ter besluitvorming', i='sophie', ow=['werkcentra'],
        b='Sinds februari heeft elke arbeidsmarktregio een digitaal Werkcentrum. Fysieke Werkcentra zijn open in 11 regio’s; de rest volgt.',
        stukken=[],
        besluiten=[('b_werkc', 'Alle fysieke Werkcentra uiterlijk juni 2026 open', 'Het Werkbedrijf opent uiterlijk in juni 2026 in alle arbeidsmarktregio’s een fysiek Werkcentrum, samen met gemeenten en regionale partners.',
                    'Werkzoekenden en werkgevers moeten in elke regio op één plek terechtkunnen.', 'genomen', ['sophie', 'fleur'], [], None)],
        acties=[('Opening Werkcentrum regio Zwolle voorbereiden', 'Regel locatie, bezetting en samenwerking met de gemeenten in de regio.', 'fleur', '2026-05-31', 'afgerond', '2026-05-29', [], 'b_werkc', [])]),
   dict(t='WW-instroom 2026', s='ter bespreking', i='bas', ow=['ww'],
        b='Het aantal WW-uitkeringen stijgt naar verwachting verder tot ongeveer 208.000 in 2026. Dat vraagt om meer inzet op werk-naar-werkbegeleiding.',
        stukken=[], besluiten=[],
        acties=[('Prognose WW-instroom per arbeidsmarktregio actualiseren', 'Maak de prognose per regio zodat de Werkcentra kunnen plannen.', 'bas', '2026-03-31', 'afgerond', '2026-03-25', [], None, [])]),
  ]),
 dict(k='v5', o='ccu', d='2026-02-24', t=('13:30', '16:00'), loc='Amsterdam, La Guardiaweg', st='vastgesteld', afw={},
  sam='De Centrale Cliëntenraad bracht advies uit over de brieven van de WIA-herstelactie en sprak met de Raad van Bestuur over wachttijden.',
  p=[
   dict(t='Brieven WIA-herstelactie', s='ter besluitvorming', i='wouter', ow=['wiaherstel', 'client'],
        b='De raad vindt de brieven nog te moeilijk. Cliënten moeten in de eerste alinea lezen wat er voor hen verandert en wanneer.',
        stukken=[('st_advies1', 'Advies Centrale Cliëntenraad over brieven WIA-herstelactie', 'brief', 'wouter', 'openbaar', [
            'Advies van de Centrale Cliëntenraad aan de Raad van Bestuur over de brieven van de WIA-herstelactie.',
            'De raad adviseert: (1) schrijf op taalniveau B1, (2) noem in de eerste alinea wat er verandert en wanneer de cliënt geld ontvangt, (3) geef één telefoonnummer en één aanspreekpunt, en (4) leg uit dat de herberekening geen gevolgen heeft voor andere uitkeringen of toeslagen, of zeg eerlijk als dat nog niet bekend is.'])],
        besluiten=[('b_advies1', 'Advies over brieven WIA-herstelactie uitgebracht', 'De Centrale Cliëntenraad brengt advies uit over de brieven van de WIA-herstelactie: taalniveau B1, kernboodschap vooraan, één aanspreekpunt.',
                    'Begrijpelijke brieven voorkomen onrust en onnodige vragen.', 'genomen', ['wouter', 'emma'], ['st_advies1'], None)],
        acties=[('Reactie Raad van Bestuur op advies brieven voorbereiden', 'Bereid de reactie voor op het advies over de herstelbrieven.', 'marieke', '2026-03-17', 'afgerond', '2026-03-13', [], 'b_advies1', [])]),
   dict(t='Wachttijden sociaal-medische beoordelingen', s='ter bespreking', i='emma', ow=['smz', 'client'],
        b='Cliënten wachten lang op een beoordeling en horen weinig over de stand van zaken. Lisa Hendriks lichtte de Ontwikkelagenda toe.',
        stukken=[], besluiten=[], acties=[]),
  ]),
 dict(k='v6', o='sio', d='2026-03-03', t=('10:00', '11:30'), loc='Online', st='vastgesteld', afw={'bas': 'afwezig met bericht'},
  sam='Extra capaciteit voor de WW-werkvoorraad en afspraken over begrijpelijker WW-beschikkingen.',
  p=[
   dict(t='Werkvoorraad WW eerste kwartaal', s='ter besluitvorming', i='stijn', ow=['ww'],
        b='Door de hogere instroom loopt de werkvoorraad WW-aanvragen op. Tijdelijke extra capaciteit is nodig om binnen de wettelijke termijn te beslissen.',
        stukken=[('st_wwq1', 'Werkvoorraad WW eerste kwartaal 2026', 'rapport', 'stijn', 'intern', [
            'Rapportage werkvoorraad WW, eerste kwartaal 2026. Cijfers zijn illustratief voor deze demo.',
            'De instroom van WW-aanvragen ligt circa 9% hoger dan in dezelfde periode van 2025. Het percentage tijdige beslissingen daalde van 94% naar 89%. Verwacht volume voor heel 2026: ongeveer 208.000 lopende uitkeringen.',
            'Voorstel: tijdelijk 40 fte extra inzetten op beoordeling van WW-aanvragen tot en met september.'])],
        besluiten=[('b_wwcap', 'Tijdelijk extra capaciteit voor WW-beoordeling', 'SIO zet tot en met september 2026 tijdelijk 40 fte extra in op de beoordeling van WW-aanvragen.',
                    'Tijdig beslissen over WW is essentieel voor inkomenszekerheid.', 'genomen', ['stijn'], ['st_wwq1'], None)],
        acties=[('Tijdelijke capaciteit WW werven en inwerken', 'Werf en werk 40 fte in via interne mobiliteit en tijdelijke contracten.', 'stijn', '2026-04-30', 'afgerond', '2026-04-24', ['anna'], 'b_wwcap', [])]),
   dict(t='Begrijpelijke WW-beschikkingen', s='ter bespreking', i='nick', ow=['kwaliteit', 'ww'],
        b='Binnen Kwaliteit op orde worden de standaardteksten van WW-beschikkingen herschreven.',
        stukken=[], besluiten=[],
        acties=[('Standaardteksten WW-beschikkingen herschrijven', 'Herschrijf de twintig meest gebruikte tekstblokken op taalniveau B1.', 'nick', '2026-09-30', 'loopt', None, ['stijn'], None,
                 [('2026-06-15', 'Twaalf van de twintig tekstblokken klaar en juridisch getoetst.')])]),
  ]),
 dict(k='v7', o='rvb', d='2026-03-17', t=('09:30', '12:30'), loc='Amsterdam, La Guardiaweg', st='vastgesteld', afw={'thomas': 'deels'},
  gasten=[('jeroen', 'adviseur'), ('stijn', 'adviseur')],
  sam='Advies van de cliëntenraad over de herstelbrieven overgenomen. Besluiten over digitale weerbaarheid en het beheersingsraamwerk van Kwaliteit op orde.',
  p=[
   dict(t='Advies cliëntenraad brieven WIA-herstelactie', s='ter besluitvorming', i='marieke', ow=['wiaherstel', 'client'],
        b='De Raad van Bestuur neemt het advies volledig over en vraagt het programma de brieven daarop aan te passen.', stukken=[],
        besluiten=[('b_b1', 'Advies cliëntenraad overgenomen: herstelbrieven op taalniveau B1', 'De Raad van Bestuur neemt het advies van de Centrale Cliëntenraad over. Alle brieven van de WIA-herstelactie worden op taalniveau B1 geschreven, met de kernboodschap vooraan en één aanspreekpunt.',
                    'Het advies sluit aan bij het doel van begrijpelijke beslissingen uit Kwaliteit op orde.', 'genomen', ['pieter', 'lisa'], ['st_advies1'], None)],
        acties=[('Brieven WIA-herstelactie aanpassen aan advies', 'Pas alle brieven aan en laat ze opnieuw testen.', 'anna', '2026-05-01', 'afgerond', '2026-04-28', ['nick'], 'b_b1', [])]),
   dict(t='Digitale weerbaarheid', s='ter besluitvorming', i='jeroen', ow=['digiweer'],
        b='Jeroen de Groot presenteerde de risicoanalyse. De aanpak wordt risicogestuurd: eerst de diensten en processen waarvan uitbetaling van uitkeringen afhangt.',
        stukken=[('st_digi', 'Risicoanalyse digitale weerbaarheid 2026', 'rapport', 'jeroen', 'vertrouwelijk', [
            'Risicoanalyse digitale weerbaarheid 2026. Inhoud is illustratief voor deze demo.',
            'De belangrijkste diensten en processen ("kroonjuwelen") zijn de betaalketen van uitkeringen, de Polisadministratie en de digitale klantkanalen. Voor deze processen gelden extra eisen voor detectie, herstel en oefenen van uitval.',
            'Aanbeveling: een risicogestuurde aanpak, een jaarlijkse crisisoefening met de betaalketen en multifactorauthenticatie voor alle beheertoegang.'])],
        besluiten=[('b_digi', 'Risicogestuurde aanpak digitale weerbaarheid vastgesteld', 'De Raad van Bestuur stelt een risicogestuurde aanpak voor digitale weerbaarheid vast, met voorrang voor de betaalketen, de Polisadministratie en de digitale klantkanalen.',
                    'Uitval van deze processen raakt direct het inkomen van cliënten.', 'genomen', ['thomas', 'jeroen'], ['st_digi'], None)],
        acties=[('Inventarisatie kroonjuwelen afronden', 'Leg per kritisch proces de eigenaar, afhankelijkheden en hersteltijd vast.', 'jeroen', '2026-05-31', 'afgerond', '2026-06-05', ['bas'], 'b_digi', [])]),
   dict(t='Kwaliteit op orde: beheersingsraamwerk', s='ter besluitvorming', i='stijn', ow=['kwaliteit'],
        b='Er zijn eerste organisatiebrede kwaliteitskaders opgesteld. Het nieuwe beheersingsraamwerk wordt de standaard voor alle onderdelen.', stukken=[],
        besluiten=[('b_raamwerk', 'UWV-breed beheersingsraamwerk wordt de standaard', 'Het UWV-brede beheersingsraamwerk wordt de standaard voor alle onderdelen; de eerste organisatiebrede kwaliteitskaders worden in 2026 ingevoerd.',
                    'Uniforme, betrouwbare en zorgvuldige dienstverlening.', 'genomen', ['pieter', 'stijn'], [], None)],
        acties=[('Kwaliteitskaders uitwerken voor WW-beslissingen', 'Vertaal de organisatiebrede kaders naar het WW-proces.', 'stijn', '2026-06-30', 'afgerond', '2026-06-26', [], 'b_raamwerk', [])]),
  ]),
 dict(k='v8', o='gd', d='2026-04-14', t=('14:00', '15:30'), loc='Online', st='vastgesteld', afw={},
  sam='Voorrang voor gegevenslevering aan de WIA-herstelactie en start van de pilot met het vergaderregister in open formaten.',
  p=[
   dict(t='Loonloze tijdvakken in de Polisadministratie', s='ter besluitvorming', i='bas', ow=['polis', 'wiaherstel'],
        b='Voor de correcties in loonloze tijdvakken zijn aanvullende gegevens nodig. Bas Peters analyseerde waar loongegevens ontbreken.', stukken=[],
        besluiten=[('b_gdvoorrang', 'Gegevenslevering aan WIA-herstelactie krijgt voorrang', 'Gegevensdiensten geeft tot en met oktober 2026 voorrang aan gegevenslevering voor de WIA-herstelactie.',
                    'De uitbetalingsdatum in oktober hangt af van tijdige levering.', 'genomen', ['jeroen'], [], None)],
        acties=[('Analyse ontbrekende loongegevens in loonloze tijdvakken', 'Breng per jaar in kaart hoeveel tijdvakken onvolledig zijn en waarom.', 'bas', '2026-05-31', 'afgerond', '2026-05-22', [], 'b_gdvoorrang', [])]),
   dict(t='Pilot vergaderregister in open formaten', s='ter besluitvorming', i='jeroen', ow=['autonomie'],
        b='Besluiten en acties worden vastgelegd als losse, doorzoekbare gegevens in open formaten (Markdown), zodat ze ook zonder leverancier leesbaar blijven.',
        stukken=[('st_pilot', 'Notitie pilot vergaderregister', 'notitie', 'bas', 'intern', [
            'Notitie over een pilot met een vergaderregister waarin vergaderingen, besluiten en acties als losse gegevens worden vastgelegd.',
            'Waarom: acties en besluiten zijn in Word-verslagen slecht terug te vinden. Bestuurders willen per persoon, per onderwerp en per onderdeel kunnen zoeken.',
            'Hoe: elk besluit en elke actie is een apart Markdown-bestand met gestructureerde kenmerken. Dat is een open formaat dat zonder speciale software leesbaar blijft en past bij informatieautonomie.'])],
        besluiten=[('b_pilot', 'Pilot vergaderregister gestart', 'Gegevensdiensten start een pilot met een vergaderregister in open formaten bij GD en de Programmaraad WIA-herstelactie.',
                    'Betere vindbaarheid van besluiten en acties, zonder afhankelijkheid van één leverancier.', 'genomen', ['jeroen', 'thomas'], ['st_pilot'], None)],
        acties=[('Pilot vergaderregister inrichten', 'Richt het register in en train de notulisten.', 'bas', '2026-06-01', 'afgerond', '2026-05-20', ['nick'], 'b_pilot', [])]),
  ]),
 dict(k='v9', o='rvb', d='2026-05-12', t=('09:30', '12:00'), loc='Amsterdam, La Guardiaweg', st='vastgesteld', afw={},
  sam='Start van de Verandermotor met de eerste clusters, vakgroepen en teams. Bespreking van de concept-juninota.',
  p=[
   dict(t='Start Verandermotor', s='ter besluitvorming', i='pieter', ow=['verandermotor'],
        b='Multidisciplinaire teams gaan organisatiebreed sneller verbeteringen doorvoeren. In mei starten de eerste clusters, vakgroepen en teams.', stukken=[],
        besluiten=[('b_vm', 'Verandermotor officieel gestart', 'De Raad van Bestuur start de Verandermotor. Vanaf mei 2026 werken de eerste clusters, vakgroepen en teams volgens de nieuwe werkwijze.',
                    'Veranderopdrachten worden zo op één plek gebundeld en sneller gerealiseerd.', 'genomen', ['pieter', 'lisa', 'thomas'], [], None)],
        acties=[('Besluitvorming en mandaten Verandermotor vastleggen', 'Leg vast wie waarover beslist in clusters en vakgroepen.', 'marieke', '2026-06-30', 'afgerond', '2026-07-03', [], 'b_vm', [])]),
   dict(t='Concept-juninota 2026', s='ter bespreking', i='thomas', ow=['financien', 'ww'],
        b='De uitgaven aan WW stijgen van € 4,0 miljard in 2025 naar naar verwachting € 4,5 miljard in 2026. De WIA blijft de grootste stijger.',
        stukken=[('st_juni', 'Concept-juninota 2026', 'rapport', 'thomas', 'intern', [
            'Concept-juninota 2026 met de raming van uitkeringslasten en volumes.',
            'WW: uitgaven stijgen van € 4,0 miljard in 2025 naar € 4,5 miljard in 2026 en € 5,1 miljard in 2027. WIA: de lijn van hogere uitkeringen en een groter beroep op de WIA zet door.',
            'Risico: de achterstanden in sociaal-medische beoordelingen kunnen leiden tot hogere uitgaven aan voorschotten en vertragingsschade.'])],
        besluiten=[],
        acties=[('Juninota 2026 aanbieden aan de minister van SZW', 'Verwerk de laatste cijfers en verstuur de nota.', 'thomas', '2026-06-20', 'afgerond', '2026-06-18', ['bas'], None, [])]),
  ]),
 dict(k='v10', o='smz', d='2026-05-26', t=('13:00', '15:00'), loc='Utrecht, Daalseplein', st='vastgesteld', afw={},
  sam='Planning van herbeoordelingen bijgesteld naar de werkelijke capaciteit. Afspraken over taakdelegatie en een pilot met het uniforme intakeproces.',
  p=[
   dict(t='Capaciteit verzekeringsartsen', s='ter besluitvorming', i='mark', ow=['smz'],
        b='De capaciteit is lager dan in januari aangenomen. Voor 2026 is ruimte voor 5.000 tot 7.000 herbeoordelingen. Taakdelegatie moet verzekeringsartsen ontlasten.',
        stukken=[('st_cap2', 'Capaciteitsrapportage SMZ mei 2026', 'rapport', 'mark', 'intern', [
            'Capaciteitsrapportage Sociaal-medische Zaken, mei 2026. Cijfers voor 2026 zijn illustratief, met uitzondering van de openbaar gemaakte bandbreedte voor herbeoordelingen.',
            'De beschikbare capaciteit voor 2026 is voldoende voor 5.000 tot 7.000 WIA-herbeoordelingen, ruim tienduizend minder dan in 2025. Voorrang blijft bij claimbeoordelingen aan het einde van de wachttijd.',
            'Kansen: taakdelegatie naar arbeidsdeskundigen en sociaal-medisch verpleegkundigen, en minder dubbel werk door één intakeproces.'])],
        besluiten=[('b_herb2', 'Herbeoordelingen 2026 bijgesteld naar 6.000', 'SMZ stelt de planning voor 2026 bij naar circa 6.000 WIA-herbeoordelingen, met voorrang voor herbeoordelingen die wettelijk of voor de cliënt noodzakelijk zijn.',
                    'De werkelijke capaciteit is lager dan in januari aangenomen.', 'genomen', ['arie', 'lisa'], ['st_cap2'], 'b_herb1')],
        acties=[('Taakdelegatie naar arbeidsdeskundigen en verpleegkundigen uitwerken', 'Werk uit welke taken onder supervisie kunnen worden overgedragen, met juridische toets.', 'mark', '2026-09-30', 'loopt', None, ['arie'], 'b_herb2',
                 [('2026-07-14', 'Takenlijst opgesteld; juridische toets loopt nog.')])]),
   dict(t='Pilot uniform intakeproces', s='ter besluitvorming', i='arie', ow=['smz', 'client'],
        b='Het ontwerp is gereed. Na de zomer start een pilot in twee districten.', stukken=[], besluiten=[],
        acties=[('Pilot uniform intakeproces starten in twee districten', 'Start de pilot en meet doorlooptijd en cliëntervaring.', 'arie', '2026-10-15', 'open', None, ['mark'], None, [])]),
  ]),
 dict(k='v11', o='wcz', d='2026-06-16', t=('09:00', '10:30'), loc='Zwolle, Werkcentrum', st='vastgesteld', afw={},
  gasten=[('sophie', 'gast')],
  sam='Eerste weken van het fysieke Werkcentrum regio Zwolle en afspraken met gemeenten en werkgevers.',
  p=[
   dict(t='Opening fysiek Werkcentrum', s='ter informatie', i='fleur', ow=['werkcentra'],
        b='Het Werkcentrum is sinds eind mei open. Bezoekers komen vooral voor sollicitatiehulp en vragen over de WW.', stukken=[], besluiten=[],
        acties=[('Samenwerkingsafspraken met gemeenten regio Zwolle vastleggen', 'Leg de taakverdeling vast in een convenant.', 'fleur', '2026-09-01', 'afgerond', '2026-08-27', [], None, [])]),
   dict(t='Werkgeversdienstverlening zorg en techniek', s='ter bespreking', i='bas', ow=['werkcentra', 'ww'],
        b='Werkgevers in zorg en techniek melden veel moeilijk vervulbare vacatures. Een analyse moet laten zien welke WW-gerechtigden met korte scholing kunnen overstappen.', stukken=[], besluiten=[],
        acties=[('Vacatureanalyse zorg en techniek regio Zwolle', 'Analyseer vacatures en het profiel van WW-gerechtigden in de regio.', 'bas', '2026-11-30', 'loopt', None, ['fleur'], None, [])]),
  ]),
 dict(k='v12', o='wia', d='2026-09-08', t=('10:00', '12:00'), loc='Online', st='vastgesteld', afw={'jeroen': 'afwezig met bericht'},
  sam='Go-besluit voor de eerste uitbetalingen uit de WIA-vergoedingsregeling in oktober 2026.',
  p=[
   dict(t='Gereedheid uitbetaling vergoedingsregeling', s='ter besluitvorming', i='anna', ow=['wiaherstel'],
        b='Alle voorbereidingen voor de eerste uitbetalingen zijn afgerond. Het klantcontactcentrum is voorbereid op vragen.',
        stukken=[('st_ready', 'Gereedheidsrapportage uitbetaling oktober 2026', 'rapport', 'anna', 'intern', [
            'Gereedheidsrapportage voor de eerste uitbetalingen uit de WIA-vergoedingsregeling. Aantallen zijn illustratief voor deze demo.',
            'Status: systeemaanpassingen getest, brieven op taalniveau B1 goedgekeurd door de cliëntenraad, klantcontactcentrum getraind. De eerste uitbetalingsrun omvat circa 4.800 cliënten.',
            'Risico’s: vragen over gevolgen voor toeslagen en schulden; mogelijke piek in telefonie in de eerste twee weken.'])],
        besluiten=[('b_go', 'Go voor eerste uitbetalingen WIA-vergoedingsregeling', 'De programmaraad geeft akkoord op de eerste uitbetalingsrun uit de WIA-vergoedingsregeling in oktober 2026.',
                    'Alle gereedheidscriteria zijn gehaald.', 'genomen', ['anna', 'stijn', 'thomas'], ['st_ready'], None)],
        acties=[('Eerste uitbetalingsrun monitoren', 'Volg de run dagelijks en rapporteer afwijkingen aan de programmaraad.', 'anna', '2026-11-15', 'loopt', None, ['bas'], 'b_go',
                 [('2026-10-09', 'Eerste run uitgevoerd zonder grote verstoringen.'), ('2026-10-23', 'Circa 3% van de betalingen vraagt handmatige nacontrole.')]),
                ('Klantcontactcentrum voorbereiden op vragen herstelactie', 'Vraag-en-antwoordlijst en extra bezetting regelen.', 'stijn', '2026-09-30', 'afgerond', '2026-09-25', ['nick'], 'b_go', [])]),
  ]),
 dict(k='v13', o='ccu', d='2026-09-22', t=('13:30', '16:00'), loc='Utrecht, Daalseplein', st='vastgesteld', afw={'lisa': 'afwezig met bericht'},
  sam='Ervaringen van cliënten met de Werkcentra en advies over het uniforme intakeproces.',
  p=[
   dict(t='Cliëntervaringen met Werkcentra', s='ter bespreking', i='emma', ow=['werkcentra', 'client'],
        b='De raad wil weten of de Werkcentra voor cliënten verschil maken en haalt ervaringen op in drie regio’s.', stukken=[], besluiten=[],
        acties=[('Cliëntervaringen Werkcentra ophalen in drie regio’s', 'Gesprekken met cliënten in de regio’s Zwolle, Groot Amsterdam en Zuid-Limburg.', 'emma', '2026-10-31', 'open', None, ['wouter'], None, [])]),
   dict(t='Advies uniform intakeproces', s='ter besluitvorming', i='wouter', ow=['smz', 'client'],
        b='Cliënten willen één aanspreekpunt van intake tot beslissing en vooraf weten hoe lang het duurt.', stukken=[],
        besluiten=[('b_advies2', 'Advies uniform intakeproces: één aanspreekpunt', 'De Centrale Cliëntenraad adviseert in het uniforme intakeproces één vast aanspreekpunt per cliënt en een verwachte doorlooptijd bij de start.',
                    'Onzekerheid over wachttijd is voor cliënten de grootste ergernis.', 'genomen', ['wouter', 'emma'], [], None)],
        acties=[('Reactie Raad van Bestuur op advies intakeproces voorbereiden', 'Bereid de reactie voor, in overleg met SMZ.', 'marieke', '2026-11-10', 'open', None, ['arie'], 'b_advies2', [])]),
  ]),
 dict(k='v14', o='gd', d='2026-10-06', t=('14:00', '15:30'), loc='Online', st='vastgesteld', afw={'thomas': 'afwezig met bericht'},
  sam='Protocol voor gegevensdeling met gemeenten in de Werkcentra vastgesteld, onder voorwaarde van een DPIA.',
  p=[
   dict(t='Gegevensdeling met gemeenten in Werkcentra', s='ter besluitvorming', i='jeroen', ow=['polis', 'werkcentra'],
        b='Gemeenten en UWV willen in de Werkcentra gegevens delen over gezamenlijke cliënten. Dat mag alleen met een duidelijke grondslag en een DPIA.', stukken=[],
        besluiten=[('b_protocol', 'Protocol gegevensdeling Werkcentra vastgesteld', 'Gegevensdiensten stelt een protocol vast voor gegevensdeling met gemeenten in de Werkcentra. Het protocol gaat pas in na een positieve DPIA.',
                    'Betere samenwerking in de regio, met bescherming van persoonsgegevens.', 'genomen', ['jeroen', 'bas'], [], None)],
        acties=[('DPIA gegevensdeling Werkcentra uitvoeren', 'Voer de DPIA uit met de privacy officer en twee gemeenten.', 'jeroen', '2026-10-31', 'loopt', None, ['bas'], 'b_protocol', [])]),
  ]),
 dict(k='v15', o='rvb', d='2026-10-20', t=('09:30', '12:00'), loc='Amsterdam, La Guardiaweg', st='concept', afw={'lisa': 'afwezig met bericht'},
  gasten=[('stijn', 'adviseur')],
  sam='Achtmaandenverslag 2026 vastgesteld. Voorbereiding op mogelijke verlenging van de exporttermijn van de WW onder EU-regels.',
  p=[
   dict(t='Achtmaandenverslag 2026', s='ter besluitvorming', i='thomas', ow=['financien', 'wiaherstel', 'smz'],
        b='Het verslag laat voortgang zien op de WIA-herstelactie en de Verandermotor, maar de sociaal-medische achterstanden blijven het grootste knelpunt.',
        stukken=[('st_acht', 'Achtmaandenverslag 2026 (concept)', 'rapport', 'thomas', 'intern', [
            'Concept achtmaandenverslag 2026 (januari tot en met augustus). Inhoud is illustratief voor deze demo.',
            'Voortgang: de eerste uitbetalingen uit de WIA-vergoedingsregeling zijn voorbereid voor oktober; alle fysieke Werkcentra zijn open; de Verandermotor werkt met de eerste clusters en vakgroepen.',
            'Knelpunten: de achterstand in sociaal-medische beoordelingen groeit verder; taakdelegatie en het uniforme intakeproces moeten in 2027 effect hebben.'])],
        besluiten=[('b_acht', 'Achtmaandenverslag 2026 vastgesteld', 'De Raad van Bestuur stelt het achtmaandenverslag 2026 vast en biedt het aan de minister van SZW aan.',
                    'Verantwoording over de eerste acht maanden.', 'genomen', ['pieter', 'thomas'], ['st_acht'], None)],
        acties=[('Achtmaandenverslag publiceren', 'Publicatie en nieuwsbericht voorbereiden.', 'nick', '2026-11-06', 'open', None, [], 'b_acht', [])]),
   dict(t='WW-export onder herziene EU-regels', s='ter besluitvorming', i='stijn', ow=['ww'],
        b='In Europees verband wordt voorgesteld de maximale exporttermijn van de WW te verlengen van drie naar zes maanden. UWV bereidt zich voor op extra controle vóór export.', stukken=[],
        besluiten=[('b_export', 'Voorbereiding controle vóór export WW', 'De Raad van Bestuur vraagt SIO een impactanalyse te maken van een verlenging van de exporttermijn van de WW naar zes maanden, inclusief controle op het recht vóór export.',
                    'Bij een langere exporttermijn wordt controle vooraf belangrijker.', 'genomen', ['pieter', 'stijn'], [], None)],
        acties=[('Impactanalyse verlenging exporttermijn WW', 'Breng gevolgen voor processen, systemen en capaciteit in kaart.', 'stijn', '2026-12-01', 'open', None, ['bas'], 'b_export', [])]),
  ]),
 dict(k='v16', o='rvb', d='2026-11-10', t=('09:30', '12:00'), loc='Amsterdam, La Guardiaweg', st='gepland', afw={}, sam=None,
  p=[
   dict(t='Vaststelling verslag 20 oktober', s='ter besluitvorming', i='marieke', ow=[], b=None, stukken=[], besluiten=[], acties=[]),
   dict(t='Concept-jaarplan 2027', s='ter bespreking', i='thomas', ow=['financien'], b=None, stukken=[], besluiten=[], acties=[]),
   dict(t='Reactie op advies cliëntenraad over intakeproces', s='ter besluitvorming', i='lisa', ow=['smz', 'client'], b=None, stukken=[], besluiten=[], acties=[]),
  ]),
 dict(k='v17', o='smz', d='2026-11-17', t=('13:00', '15:00'), loc='Utrecht, Daalseplein', st='gepland', afw={}, sam=None,
  p=[dict(t='Eerste resultaten pilot uniform intakeproces', s='ter bespreking', i='arie', ow=['smz'], b=None, stukken=[], besluiten=[], acties=[]),
     dict(t='Taakdelegatie: uitkomst juridische toets', s='ter besluitvorming', i='mark', ow=['smz'], b=None, stukken=[], besluiten=[], acties=[])]),
 dict(k='v18', o='wia', d='2026-11-24', t=('10:00', '12:00'), loc='Online', st='gepland', afw={}, sam=None,
  p=[dict(t='Evaluatie eerste uitbetalingsrun', s='ter besluitvorming', i='anna', ow=['wiaherstel'], b=None, stukken=[], besluiten=[], acties=[])]),
]

VASTGESTELD_IN = {'v1': 'v7', 'v7': 'v9', 'v9': 'v15', 'v2': 'v10', 'v3': 'v12', 'v5': 'v13', 'v8': 'v14'}


# ───────────────────────── eenvoudige PDF-schrijver ─────────────────────────

def _pdf_esc(s):
    b = s.encode('cp1252', errors='replace')
    return b.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def _breek(tekst, breedte=88):
    regels, huidig = [], ''
    for w in tekst.split():
        if len(huidig) + len(w) + 1 > breedte:
            regels.append(huidig); huidig = w
        else:
            huidig = f'{huidig} {w}'.strip()
    if huidig:
        regels.append(huidig)
    return regels


def schrijf_pdf(pad, titel, alineas, onderschrift):
    regels = [('F2', 16, titel), ('F1', 9, onderschrift), ('F1', 11, '')]
    for a in alineas:
        regels += [('F1', 11, r) for r in _breek(a)] + [('F1', 11, '')]
    paginas, huidig, y = [], [], 780
    for font, grootte, tekst in regels:
        if y < 70:
            paginas.append(huidig); huidig, y = [], 780
        if tekst:
            huidig.append(b'BT /%s %d Tf 60 %d Td (%s) Tj ET' % (font.encode(), grootte, y, _pdf_esc(tekst)))
        y -= grootte + 7
    paginas.append(huidig)
    objecten = [b'<< /Type /Catalog /Pages 2 0 R >>', None,
                b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
                b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>']
    kids = []
    for regs in paginas:
        inhoud = b'\n'.join(regs)
        objecten.append(b'<< /Length %d >>\nstream\n%s\nendstream' % (len(inhoud), inhoud))
        inhoud_nr = len(objecten)
        objecten.append(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>' % inhoud_nr)
        kids.append(len(objecten))
    objecten[1] = b'<< /Type /Pages /Kids [%s] /Count %d >>' % (b' '.join(b'%d 0 R' % k for k in kids), len(kids))
    uit, posities = bytearray(b'%PDF-1.4\n'), []
    for i, o in enumerate(objecten, 1):
        posities.append(len(uit))
        uit += b'%d 0 obj\n%s\nendobj\n' % (i, o)
    xref = len(uit)
    uit += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objecten) + 1)
    uit += b''.join(b'%010d 00000 n \n' % p for p in posities)
    uit += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objecten) + 1, xref)
    with open(pad, 'wb') as f:
        f.write(uit)


# ───────────────────────── vullen ─────────────────────────

def ruim_op(con):
    """Verwijdert bestanden die niet bij de zojuist geschreven dataset horen.

    Nodig omdat een synchronisatiedienst (bijv. Google Drive) net gewiste bestanden soms terugzet.
    """
    bekend = {r[0] for r in con.execute('SELECT pad FROM bestand')}
    bijlagen = {os.path.normpath(r[0]) for r in con.execute('SELECT bestandspad FROM stuk')}
    weg = 0
    for map_ in opslag.MAPPEN.values():
        p = os.path.join(DATA, map_)
        for naam in os.listdir(p) if os.path.isdir(p) else []:
            if naam.endswith('.md') and f'{map_}/{naam}' not in bekend:
                os.remove(os.path.join(p, naam)); weg += 1
    for wortel, _, namen in os.walk(BIJLAGEN):
        for naam in namen:
            rel = os.path.normpath(os.path.relpath(os.path.join(wortel, naam), BIJLAGEN))
            if rel not in bijlagen:
                os.remove(os.path.join(wortel, naam)); weg += 1
    return weg


def vul():
    server.init_db()
    con = verbind()
    od, pers, ow, verg, stukken, besl = {}, {}, {}, {}, {}, {}
    for k, n, afk, soort, boven in ONDERDELEN:
        od[k] = maak(con, 'bedrijfsonderdeel', dict(naam=n, afkorting=afk, soort=soort, valt_onder=od.get(boven), actief=1), G)
    for k, vn, an, fn, o, tel in PERSONEN:
        foto = f"{vn}-{an}".lower().replace(' ', '-') + '.jpg'
        email = f"{vn}.{an.replace(' ', '')}@{EMAILDOMEIN}".lower()
        pers[k] = maak(con, 'persoon', dict(voornaam=vn, achternaam=an, functie=fn, bedrijfsonderdeel=od[o], telefoon=tel,
                                            email=email, foto=foto, actief=1), G)
    for o, leden in LEDEN.items():
        for p, rol in leden:
            con.execute('INSERT INTO lidmaatschap(bedrijfsonderdeel, persoon, rol) VALUES (?,?,?)', (od[o], pers[p], rol))
    for k, n, oms, ph, tw in ONDERWERPEN:
        ow[k] = maak(con, 'onderwerp', dict(naam=n, omschrijving=oms, portefeuillehouder=pers[ph], trefwoorden=tw), G)

    for v in VERGADERINGEN:
        vid = maak(con, 'vergadering', dict(bedrijfsonderdeel=od[v['o']], datum=v['d'], begintijd=v['t'][0], eindtijd=v['t'][1],
                                            locatie=v['loc'], status=v['st'], samenvatting=v['sam']), G)
        verg[v['k']] = vid
        for p, aanw in v['afw'].items():
            con.execute('UPDATE deelname SET aanwezigheid = ? WHERE vergadering = ? AND persoon = ?', (aanw, vid, pers[p]))
        for p, rol in v.get('gasten', []):  # schuift deze keer aan, naast de vaste leden
            con.execute("INSERT OR IGNORE INTO deelname(vergadering, persoon, rol, aanwezigheid) VALUES (?,?,?,'aanwezig')", (vid, pers[p], rol))
        for nr, pt in enumerate(v['p'], 1):
            aid = maak(con, 'agendapunt', dict(vergadering=vid, volgnummer=nr, titel=pt['t'], soort=pt['s'], inbrenger=pers[pt['i']],
                                               bespreking=pt['b'], onderwerpen=[ow[o] for o in pt['ow']]), G)
            for sk, titel, soort, auteur, vertr, alineas in pt['stukken']:
                bestandsnaam = titel.replace('/', '-') + '.pdf'
                relatief = os.path.join(str(vid), f'{sk}_{bestandsnaam}')
                pad = os.path.join(BIJLAGEN, relatief)
                os.makedirs(os.path.dirname(pad), exist_ok=True)
                schrijf_pdf(pad, titel, alineas, f'{ORGANISATIE} · {vertr} · {v["d"]}')
                tekst = server.tekst_uit_bestand(pad, bestandsnaam)
                cur = con.execute('''INSERT INTO stuk(titel, bestandsnaam, bestandspad, mime, grootte, vergadering, agendapunt, soort, auteur,
                                       versie, datum, vertrouwelijkheid, inhoud_tekst, aangemaakt_op, aangemaakt_door, gewijzigd_op, gewijzigd_door)
                                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                                  (titel, bestandsnaam, relatief, 'application/pdf', os.path.getsize(pad), vid, aid, soort, pers[auteur],
                                   '1.0', v['d'], vertr, tekst, server.nu(), G, server.nu(), G))
                stukken[sk] = cur.lastrowid
            for bk, titel, tekst, mot, status, betr, grond, vervangt in pt['besluiten']:
                besl[bk] = maak(con, 'besluit', dict(titel=titel, besluittekst=tekst, motivering=mot, vergadering=vid, agendapunt=aid,
                                                     status=status, vervangt=besl.get(vervangt), betrokkenen=[pers[p] for p in betr],
                                                     grondslag=[stukken[s] for s in grond]), G)
                if vervangt:
                    con.execute("UPDATE besluit SET status = 'herzien' WHERE id = ?", (besl[vervangt],))
            for titel, oms, eig, dl, status, afg, uitv, bk, voortgang in pt['acties']:
                xid = maak(con, 'actie', dict(titel=titel, omschrijving=oms, eigenaar=pers[eig], deadline=dl, status=status, afgerond_op=afg,
                                              vergadering=vid, agendapunt=aid, besluit=besl.get(bk), uitvoerders=[pers[p] for p in uitv]), G)
                for datum, t in voortgang:
                    con.execute('INSERT INTO actie_voortgang(actie, datum, tekst, aangemaakt_op, aangemaakt_door) VALUES (?,?,?,?,?)',
                                (xid, datum, t, server.nu(), next(f"{vn} {an}" for k, vn, an, *_ in PERSONEN if k == eig)))
    for v, door in VASTGESTELD_IN.items():
        con.execute('UPDATE vergadering SET vastgesteld_in = ? WHERE id = ?', (verg[door], verg[v]))
    server.herindexeer(con)
    con.commit()
    geschreven = opslag.exporteer(con, DATA)
    opgeruimd = ruim_op(con)
    tel = {t: con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('vergadering', 'agendapunt', 'besluit', 'actie', 'stuk', 'persoon')}
    con.close()
    print('Demodata geladen:', ', '.join(f'{n} {t}' for t, n in tel.items()))
    print(f'{geschreven} Markdown-bestanden geschreven in {DATA}')
    if opgeruimd:
        print(f'{opgeruimd} achtergebleven bestanden van een eerdere dataset verwijderd')


if __name__ == '__main__':
    mappen = [os.path.join(DATA, m) for m in opslag.MAPPEN.values()]
    if any(os.path.isdir(m) and os.listdir(m) for m in mappen):
        if '--opnieuw' not in sys.argv:
            print('Er staan al gegevens in data/. Gebruik --opnieuw om die te wissen en de demodata opnieuw te laden.')
            sys.exit(0)
        for m in mappen:
            shutil.rmtree(m, ignore_errors=True)
    shutil.rmtree(os.path.dirname(DB), ignore_errors=True)
    vul()
