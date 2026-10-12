# Residual history and canon fixes (2026-10-12)

Rule: for any decision rely on historically accurate facts. Saga-only matters follow `canon_decisions.md`, then the books, then the other docs. Format: item, record (source), action.

## History checked against the record

| Item | Record (source) | Action |
|---|---|---|
| Kamianets, autumn 1430: "taken by the Poles" or "refused to surrender"? | The Podolian and Polish lords took the castle in Oct-Nov 1430; the truce required Kamianets, Smotrych and Červonogrod to be returned to Lithuania, and the Poles did not return them; Podolian forces retook Kamianets only in 1433. Nothing supports a refusal to surrender. ([lt.wikipedia, Švitrigaila](https://lt.wikipedia.org/wiki/%C5%A0vitrigaila); [rzecz-pospolita.com, Kamieniec](https://rzecz-pospolita.com/kamieniec0.php3); [en.wikipedia, Battle of Murafa](https://en.wikipedia.org/wiki/Battle_of_Murafa)) | Book V ch. 3 ("paėmė Kamenecą") kept. Book V afterword rewritten (no more "pasidavė ne iš karto"). Graph edge note, `wiki/events/ev_podolia_seized.qmd`, `wiki/places/kamianets.qmd`, `books/5/notes/book5_fact_check.md` corrected. |
| Janusz I's seat in 1382 (Czersk or Warsaw) | He moved his capital from Czersk to Warsaw in 1406; he died at Czersk in 1429. ([en.wikipedia, Janusz I the Old](https://en.wikipedia.org/wiki/Janusz_I_the_Old)) | Book I ch. 17: "Varšuvos pilyje" became "Čersko pilyje". `wiki/characters/janusz1.qmd`, `wiki/places/masovia.qmd`, `world_rules/geography_gazetteer.md` aligned. |
| Czartorysk truce date (26 Aug or 1 Sep 1431) | Agreement reached 26 Aug at the Łuck talks; Švitrigaila issued the Czartorysk document on 1 Sep and Jogaila his on 2 Sep; truce to 24 Jun 1433. ([Polechow and Szybkowski, Roczniki Historyczne 83, 2017](https://apcz.umk.pl/RH/article/download/RH.2017.05/14436/39309); [en.wikipedia, Lithuanian Civil War](https://en.wikipedia.org/wiki/Lithuanian_Civil_War_%281432%E2%80%931438%29)) | Both dates are true of different acts. Graph keeps 1 Sep; `ev_czartorysk_truce` note now gives 26 Aug, 1 Sep and 2 Sep. Book V afterword ("rugsėjo 1 d.") already matched. |
| Julijona's wedding | en.wikipedia (Vytautas): 13 Nov 1418. en.wikipedia (Uliana Olshanska) and VLE: "before Christmas 1418"; VLE places it at Grodno; the Vilnius bishop refused, Jan Kropidło (Włocławek) officiated. ([VLE, Julijona](https://www.vle.lt/straipsnis/julijona-2/); [en.wikipedia, Uliana Olshanska](https://en.wikipedia.org/wiki/Uliana_Olshanska); [en.wikipedia, Vytautas](https://en.wikipedia.org/wiki/Vytautas)) | Date left at 13 Nov with the disagreement noted; place moved to Grodno. Book IV ch. 10 dateline and church porch changed from Vilnius to Gardinas, the boat to Trakai now "po kelių dienų kelio". Book IV afterword, master_chronology, houses_and_lineages, `wiki/characters/julijona.qmd` and the graph edge note updated. |
| Oleśnicki's career | Born 1389; royal secretary at about 20; at Grunwald 15 Jul 1410; bishop of Kraków 9 Jul 1423; cardinal 18 Dec 1439 (Eugene IV); died 1 Apr 1455. ([en.wikipedia, Zbigniew Oleśnicki](https://en.wikipedia.org/wiki/Zbigniew_Ole%C5%9Bnicki_%28cardinal%29)) | Book III ch. 30 already has no bishop's ring (opening is the ink recipe), so the ring survives only in Book IV ch. 14 (1424, correct). Cardinal date added to `houses_and_lineages.md`; career dates in the graph note. |
| Galminas as a historical namesake | Jurgis Galminas: a noble who helped organise the 1409 rising, at Constance in 1415, Samogitian elder late 1432 to late 1434. ([VLE, Galminas](https://www.vle.lt/straipsnis/galminas/); [en.wikipedia, Samogitian uprisings](https://en.wikipedia.org/wiki/Samogitian_uprisings)) | The saga's Galminas stays invented. Line added to the Book III afterword; graph note; `powers_and_politics.md` no longer calls the saga's Galminas the record's deputy; `wiki/characters/galminas.qmd` updated. |
| Elena, the maid | The maid exchange is in the Lithuanian Chronicle; the name and the execution are a 19th-century addition (Narbutt), per the Book I fact-check. | Graph `elena` set to record:false with a note. |
| Zbigniew Oleśnicki in Book III ch. 30 vs Book IV ch. 14 | See above. | Nothing further to vary: the Book III opening (ink) and the Book IV opening (the heavy ring) already differ. |
| Žygimantas's hostage years in Book V ch. 10 | 1390-98 is eight years (Book II decision). | "keturiolika metų Ordino pilyse" became "aštuonerius metus". |
| Uliana of Tver, Konrad von Jungingen | Uliana of Tver: married 1349, died 17 Mar 1391 ([en.wikipedia](https://en.wikipedia.org/wiki/Uliana_of_Tver)). Konrad von Jungingen: Grand Master 30 Nov 1393 to 30 Mar 1407, Ulrich's elder brother ([en.wikipedia](https://en.wikipedia.org/wiki/Conrad_von_Jungingen)). | New graph nodes and wiki pages. Persona folder `Julijona_Tveriete` renamed `Uliana_Tveriete`; dates fixed. |
| Samogitian bishopric, Czerwińsk bridge | Diocese founded 24 Oct 1417 at Medininkai; the pontoon bridge was assembled on 30 Jun 1410 at Czerwińsk (Book IV and Book III fact-checks). | New places and events in the graph with wiki pages. |
| Bibliography (`books/1/references.bib`) | Jurginis's book is Mintis 1976 ([goodreads and VU scan](https://tautosmenta.lt/wp-content/uploads/lituanistika/Jurginis_1976_LT.pdf)); Beresnevičius is Tyto alba 2004, subtitle "sisteminė studija"; the Lithuanian Dusburg is Lituanistinė biblioteka 23, 1985 (L. Valkūnas, ed. R. Batūra); the Nikon chronicle is PSRL 9-14, St Petersburg. | Entries corrected; the invented "Mokslas, Maskva" and Vaga-Vilnius imprints dropped. |

## Canon documents and personas

| Item | Action |
|---|---|
| `magic_rules.md` §4.1 said Book II ch. 9 shows the cost shifted into a child | Reworded: ch. 9 only offers it (Vytautas: "Ne"). |
| `iron_wolves.md` ember bearer, silver wolf, Pilkoji dates | Vytautas carries the 1387 ember (D11); the silver wolf passes through the Krėva wall in ch. 8; Pilkoji gives it at Kūčios 1430; Pilkoji born c. 1365; open questions 2-4 marked settled. `power_systems.md` §5 and `books/2/detailed_outline.md` aligned. |
| Flame-Keeper's age | Books say 14, nearly 15 at Kūčios 1405: sworn below the usual 16 as the one exception (`iron_wolves.md`, `canon_decisions.md` D11 addendum). Graph: member_of from 1405, ember keeper from 1399. |
| `bestiary.md` §18 "never named" | Giltinė is unnamed in Book I and named from Book IV (ch. 28 title). The Krėva glimpse is on the page (Book I ch. 9). |
| Hohenstein as the 1381 informant | Removed from `pronunciation_guide.md`, `persona/Kestutis`, `books/1/continuity_bible.md`. Liebenstein is the informant. |
| `persona/Jonas` "Vilnius barracks" | Changed to the camp near Trakai (D10). |
| `persona/Krivis` | Named Sirvydas (Book VI ch. 8); age reconciled with Book VI and the graph; ember question settled. |
| `persona/Sofija_Alseniske` | Annotated: Sonka, not Sofija Vytautaitė. |

## Graph additions

New nodes: `medyka`, `czerwinsk`, `medininkai`, `ragnit`, `ev_medyka_chill`, `ev_czerwinsk_bridge`, `ev_medininkai_bishopric`, `uliana_tver`, `konrad_jungingen`, `zacharijas`, `samuelis`, `dargis`, `gedvile`, `pusis`. New edges link Rimgailė, Spyglys, Kalvis, Pušis, Marquard and Elijas's sons. `dykra`, `kestutis_lodge` and `road_to_jogaila_camp` carry `start` and `end` (the years of the saga's scenes; see `meta.conventions.place_years`).

## Already done by the earlier pass (checked, no action)

Kamianets/Podolia timing in Book V ch. 3 and 6; Skirgaila regent 13 Mar 1386 and Trakai 1382; Blue Waters hedge; Liebenstein; the Kęstutis-seizes-Vilnius row; the 1361 capture and escape; the Birutė drowning attribution (Wigand); Manvydas and Strėva; artifact holder edges; Water-cost wording; the kneeling woman's pose (I ch. 27 and IV ch. 8 now agree); Žiežirba's arrival and death (the 1553 mother speaks of "the longest night" only); Praurimė marked doubtful in `cosmology.md`; the Book V ch. 15 Lutsk scene (1437, with the 1429 congress eight years back and 1431 six years back).

## Unresolved

- The exact day of Julijona's wedding (13 Nov or later in Advent) cannot be settled from the sources found.
- Rastenburg and Insterburg are named only in passing, so they have no graph nodes (a place with no event would be an orphan).
- Whether the Podolian lords took Kamianets by agreement with the starosta or by a ruse differs between Polish sources; the saga does not need to choose.
