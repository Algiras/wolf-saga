# Publishing the e-books and the Lithuanian market

How to get *Geležinio Vilko Saga* into the e-stores. The print edition (6 x 9 in paperback, wrap covers) is in
[PRINTING.md](PRINTING.md). Facts below were checked in October 2026; each is marked **verified** (read on the
named page) or **unverified** (could not be confirmed, check before relying on it).

## 1. The most important finding: KDP does not accept Lithuanian

Amazon KDP's supported-languages page lists the languages books can be published in. **Lithuanian, Latvian and
Estonian are not on it** (verified, [KDP supported languages](https://kdp.amazon.com/en_US/help/topic/G200673300)).
So the Lithuanian edition cannot be published on KDP, neither as an e-book nor as a paperback. KDP does list
English, so:

* the Lithuanian files (`saga-N-store.epub`, `saga-N-print.pdf`) are for the **Lithuanian channels** in section 8;
* the **English edition**, when it exists, is the Amazon route. Everything KDP-specific in this repository was
  built language-neutral for that: the 6 x 9 interior extension (`books/_extensions/saga-print`, no Lithuanian
  strings; the language comes from the project's `lang:`), the wrap covers (`make_covers.py --lang en print ...`
  uses `title_en` and `blurb_en`), the e-book extension (`books/_extensions/saga-store`) and the metadata sheets
  in section 7 (both languages).

What to change for an English edition: copy a book project, translate the chapters, set `lang: en`, adjust
`books/_extensions/saga-store/subjects.xml` (the `dc:subject` list is Lithuanian), and set the description in
`books/book_meta.yml`. Amazon's Lithuanian readers can still buy English Kindle books and paperbacks on
amazon.de and the other EU stores (unverified for any particular title: availability depends on each
marketplace's catalogue).

## 2. What the build produces

| File | Made by | For |
|---|---|---|
| `books/N/_book/saga-N-store.epub` (book 1: `books/_book/saga-1-store.epub`) | `quarto render --profile store --to saga-store-epub --no-clean` | every e-store |
| `books/N/_book/saga-N.epub` | the normal render | web readers (kept as it was) |
| `books/N/_book/saga-N-print.pdf` | `--profile print --to saga-print-pdf` | print, see PRINTING.md |

The store EPUB is a **separate file**, not a rebuild of `saga-N.epub`: it has the licence page moved to the front
(title page, copyright, contents, then the book), real Part pages, a Part > Chapter navigation tree, the web-only
"Skaitymo tvarka" page removed (its links to `2/index.html` would be dead in a store), a proper `landmarks` list
(cover, titlepage, toc, bodymatter, backmatter), a stable identifier and series metadata, and no inline Quarto
styles. All six pass [epubcheck 5.4.0](https://github.com/w3c/epubcheck) with 0 errors and 0 warnings; CI runs
epubcheck on them (`.github/workflows/render.yml`).

Technical facts about the EPUB: EPUB 3, reflowable, language `lt`, cover `1600 x 2560` JPEG
(`books/covers/out/bookN/front_ebook_1600x2560.jpg`, about 0.7 MB), nav TOC with landmarks, `dc:identifier` =
`urn:uuid:...` (stable, stored in `books/book_meta.yml`), `belongs-to-collection` = "Geležinio Vilko Saga" with
`group-position` N and `collection-type` series, publisher and rights set. `ebook.css` has no fixed font sizes
or colours; the reader's own font, size and theme apply. MOBI is retired and is not produced.

**ISBN.** The EPUB carries no ISBN yet (do not invent one). When one is issued, enter it in the store forms and put
it on the copyright page (`isbn_print` in `books/book_meta.yml` prints it in the paperback's copyright block).

## 3. Licence and selling your own book

The books are CC BY-NC-SA 4.0 (`books/*/copyright.qmd`). **An author may sell their own work.** The NonCommercial
condition restricts other people, not the rights holder: Creative Commons' FAQ says "As the rights holder, you may
still sell your own work commercially" (verified,
[CC FAQ](https://creativecommons.org/faq/)). Others still need your permission for commercial use. Keep the
licence line on the copyright page so buyers know what they may do with the file.

Housekeeping: `README.md` says CC BY-NC-ND 4.0 while `copyright.qmd` and the EPUB metadata say CC BY-NC-SA 4.0.
Decide which one is true before publishing and make them match.

## 4. Amazon KDP (English edition)

### 4.1 e-book upload

1. KDP Bookshelf, **+ Create**, **Kindle eBook**.
2. **Details:** language, title, series (name and number), author, description, publishing rights ("I own the
   copyright"), keywords (seven boxes), categories, adult-content question. Fill the same title, series, author and
   language on the paperback later, so Amazon can merge the two editions (section 4.5).
3. **Content:** DRM choice, upload the manuscript (`saga-N-store.epub`; KDP takes EPUB), upload the cover JPEG
   (`front_ebook_1600x2560.jpg`), answer the **AI-generated content** questions (section 4.2), use the online
   previewer to check the TOC and a few chapters.
4. **Pricing:** territories, royalty plan, list price, KDP Select yes or no (section 4.3). Publish.

The step order is the usual dashboard flow; the exact labels move around, so follow what the dashboard shows.

### 4.2 AI-content disclosure (mandatory)

Amazon requires you to tell KDP about **AI-generated** text, images and translations when you publish a new book or
republish an edited one. Definitions, from Amazon's content guidelines (verified,
[KDP content guidelines](https://kdp.amazon.com/en_US/help/topic/G200672390)):

* **AI-generated:** text, images or translations *created by* an AI-based tool, and it stays AI-generated even if
  you edit the result substantially. AI-generated images explicitly include cover and interior art.
* **AI-assisted:** you created the content and AI only helped edit, refine, check or improve it (brainstorming
  counts if you wrote the text or made the images yourself). Not disclosed.

How to answer for this series, honestly and per category (the author must make the call; this is the mapping):

| Item | Answer | Why |
|---|---|---|
| Text | **AI-generated** if the chapters were drafted by an AI tool (the stated situation: "drafted with AI assistance"). If every sentence was written by the author and AI only edited, it is AI-assisted. | Substantial editing does not remove the label. |
| Cover and interior art | **AI-generated** | Created by an image model (`books/covers/art_prompts.md`, "Viršelio dizainas ir iliustracijos: ... (su AI pagalba)" on the copyright page). |
| Translations (English edition) | **AI-generated** if machine-translated, even if post-edited | Same rule. |

KDP asks about text, images and translations separately and asks for the tool used (per secondary guides;
**unverified** in detail, so read the questions in the dashboard). Name the real tools. The copyright page already
credits the cover and art as AI-assisted: keep that line and make sure the KDP answers agree with it. Amazon does not
describe the method or the penalties on that page; do not skip the question, an undisclosed AI title violates the
guidelines.

### 4.3 DRM, KDP Select, pricing

* **DRM:** your choice at upload. For a CC BY-NC-SA work that readers may share non-commercially, **no DRM** fits the
  licence; DRM contradicts the "free to share" terms. Once published the DRM setting cannot be changed back (check
  the dashboard text, **unverified** here).
* **KDP Select** means exclusivity to Amazon for the enrolment period (90 days, auto-renewing, per KDP's terms;
  secondary source, **unverified** on Amazon's own page here), in exchange for Kindle Unlimited and promotions. It
  conflicts with selling the same e-book on Apple Books, Kobo, Google Play or through D2D. Recommended default for
  this series: **do not enrol**, go wide (section 5), keep the series on all stores. Enrol only if you decide to
  trade reach for Kindle Unlimited page-reads.
* **Royalty bands** (verified, [KDP eBook pricing](https://kdp.amazon.com/help/topic/G200634560)): the **35%** option
  has a minimum list price depending on file size (on Amazon.com $0.99 below 3 MB, $1.99 for 3 to under 10 MB,
  $2.99 from 10 MB) up to $200; the **70%** option on Amazon.com is **$2.99 to $12.99**. KDP's page says the 70%
  ceiling rose from $9.99 to $12.99 effective **7 July 2026**; older articles still say $9.99. 70% pays a file-delivery
  fee (amount on KDP's pricing page; the EPUBs here are under 1 MB, so the fee is a few cents). In Brazil, Japan,
  Mexico and India 70% also requires KDP Select. EU stores: 70% band EUR 2.69 to EUR 12.99. Suggested list price
  for each book: about $4.99 to $6.99 (70% band), the first book possibly $2.99 or free-promoted.

### 4.4 Paperback

See [PRINTING.md](PRINTING.md) (interior, wrap cover, upload settings). One KDP rule changes the plan:
KDP's own free ISBN works only for KDP; if the same paperback goes to IngramSpark or a bookshop distributor, use
your own ISBN.

### 4.5 One product page for e-book and paperback

Amazon tries to merge your e-book and print editions onto one detail page automatically when the metadata matches:
title, subtitle, author, contributors, series, language, edition, volume (verified,
[KDP help](https://kdp.amazon.com/en_US/help/topic/GTQGN866DSS6XBD2); linking takes up to a week after each
edition is live; the formats must all be published through KDP under the same account). So enter **identical**
title, series and author text in both editions. If the pages do not merge, contact KDP support with the e-book's
ASIN and the paperback's ISBN-10. Linking the two on your Bookshelf is separate and does not merge the public pages.

## 5. Apple Books, Kobo, Google Play Books, Draft2Digital

All four take the same `saga-N-store.epub`.

| Store | How | ISBN |
|---|---|---|
| Apple Books | Apple Books for Authors, or via an aggregator | Sources conflict. The newest one, quoting Apple's metadata guide, says an ISBN is optional (a permanent Vendor ID is required). **Unverified**; check Apple's current guide. |
| Kobo | Kobo Writing Life | Optional; Kobo assigns an internal identifier if you give none (a 2013 source plus a 2025-era guide; **unverified** on Kobo's own page). Some retail partners want a real 13-digit ISBN. |
| Google Play Books | Partner Center | Not required: Google assigns a `GGKEY` identifier (verified, [Google](https://support.google.com/books/partner/answer/3431108)). |
| Draft2Digital | one upload, many stores | Assigns a free ISBN (usable only through D2D, D2D as publisher of record) unless you provide your own. Its Amazon channel is **invitation-only** (verified, [D2D Amazon page](https://www.draft2digital.com/partners/amazon)). Whether D2D's language list includes Lithuanian is **unverified**; look at the language dropdown in your account. |

Use one ISBN per edition across all stores if you want one identity: the same e-book ISBN everywhere, a different
ISBN for the paperback. Lithuanian language support on each portal is **unverified** for all four; test with
book 1 first.

## 6. ISBN in Lithuania (important correction)

The national ISBN agency is part of the Martynas Mažvydas National Library (LNB). **It is a paid service, not free**:
the agency's procedure sits in LNB's "paid services" section and says a natural person or a legal entity pays "pagal
Nacionalinės bibliotekos generalinio direktoriaus įsakymu patvirtintas paslaugų kainas" (according to the prices
approved by the library director), by bank transfer (verified, text of
[ISBN ir ISMN tvarka](https://www.lnb.lt/media/public/paslaugos/mokamos_paslaugos/ISBN_ir_ISMN_tvarka.pdf)).
The price list itself was **not found**: ask the agency. The same document says:

* a **natural person** may register as a publisher and apply (so the author can be the publisher, no company
  needed); a legal entity sends registration documents on the first application;
* a natural-person publisher gets numbers from a "collective block" (kolektyvinis blokas);
* numbers and barcode are issued within 5 working days of the request and payment, within 1 working day if
  urgent;
* the contact address in the document is `isbnltu@lnb.lt`.

**Legal deposit (privalomieji egzemplioriai).** Verified only through the encyclopedia entry
[VLE: privalomasis egzempliorius](https://www.vle.lt/straipsnis/privalomasis-egzempliorius/), citing the Government
resolution of 6 Dec 2017: all publishers must deliver within **20 working days** after a print run of **more than 25
copies**; the National Library receives **2** free copies; other libraries get 1 copy each, depending on print run
and document type. Whether and how e-books are delivered, and the precise recipient list, are **unverified**:
check the current resolution on [e-tar.lt](https://www.e-tar.lt) or ask the library. A POD run of a handful of
copies falls under the 25-copy threshold per that entry (unverified reading).

## 7. Metadata sheets

Copy these into the store forms. Titles: the cover shows the series name and the book title, so the book's
**title** is its own name (e.g. "Vilko Tremtis") and the **series** field carries "Geležinio Vilko Saga", number N.
Keywords: seven, each under 50 characters. Categories: **names unverified** (Amazon's category list changes and I
could not fetch it); pick the nearest in the dashboard picker; use the deepest, most specific node; KDP lets you
choose up to three (secondary sources, **unverified**).

### Book I: Vilko Tremtis / The Wolf's Exile

| Field | Value |
|---|---|
| Title (LT / EN) | Vilko Tremtis / The Wolf's Exile |
| Subtitle | none (series name goes in the Series field) |
| Series | Geležinio Vilko Saga / The Iron Wolf Saga, number 1 |
| Author | Algimantas Krasauskas |
| Period covered | 1377–1387 |
| Language | Lithuanian (not available on KDP) / English (planned) |
| EPUB identifier | `urn:uuid:e058f845-8cb1-4e44-8d6f-11869c9c3768` (ISBN: to be issued) |
| Files | `saga-1-store.epub`, `print_cover_kdp.pdf`, `saga-1-print.pdf` |
| Keywords (EN, 7) | dark fantasy; historical fantasy; medieval Lithuania; Vytautas the Great; Teutonic Order; pagan Baltic mythology; epic fantasy series |
| Keywords (LT, 7) | tamsioji fantastika; istorinė fantastika; Vytautas Didysis; Lietuvos istorija; Kęstutis; Krėvos pilis; epinė fantastika |
| Categories (verify in the picker) | Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Dark Fantasy ; Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Epic ; Kindle Store > Kindle eBooks > Literature & Fiction > Historical Fiction > Medieval |

**Lietuviškas aprašymas:** Po klastingos Kęstučio mirties Krėvos požemiuose Vytautas lieka vienas prieš savo mirtinus pusbrolius. XIV amžiaus pabaigos Lietuvoje broliai kovoja dėl sosto, senieji dievai dar nenutilo, o iš vakarų slenka plieninė Ordino tvarka. Kad atgautų tėvų žemę, jam teks tapti tuo, ko labiausiai bijojo: negailestingu vilku. Pabėgimas persirengus moterimi, sandėris su Marienburgo magistru, svetimos ugnies atvedimas į gimtąją žemę ir Vilniaus apgultis: kerštas tampa vieninteliu degalu gyventi. „Vilko Tremtis“ yra pirmoji epinės tamsiosios fantastikos sagos knyga apie nuosmukį, išdavystę ir transformaciją (1377–1387).

**English description:** After the treacherous death of Kęstutis in the dungeons of Kreva, Vytautas stands alone against his deadly cousins. In late fourteenth-century Lithuania, brothers fight for the throne, the old gods have not yet fallen silent, and the steel order of the Teutonic Knights presses in from the west. To win back his father's land he must become the thing he fears most: a merciless wolf. A flight in a woman's clothes, a bargain with the Grand Master at Marienburg, a foreign fire carried into his own country and the siege of Vilnius: vengeance becomes the only fuel to live on. The Wolf's Exile opens an epic dark-fantasy saga of decline, betrayal and transformation (1377–1387).

### Book II: Auksinis Šešėlis / The Golden Shadow

| Field | Value |
|---|---|
| Title (LT / EN) | Auksinis Šešėlis / The Golden Shadow |
| Subtitle | none (series name goes in the Series field) |
| Series | Geležinio Vilko Saga / The Iron Wolf Saga, number 2 |
| Author | Algimantas Krasauskas |
| Period covered | 1387–1399 |
| Language | Lithuanian (not available on KDP) / English (planned) |
| EPUB identifier | `urn:uuid:4f380ceb-61be-4a01-a469-1f64f30f48d4` (ISBN: to be issued) |
| Files | `saga-2-store.epub`, `print_cover_kdp.pdf`, `saga-2-print.pdf` |
| Keywords (EN, 7) | dark fantasy; historical fantasy; medieval Lithuania; Battle of the Vorskla; Vytautas the Great; Golden Horde steppe; epic fantasy series |
| Keywords (LT, 7) | tamsioji fantastika; istorinė fantastika; Vorsklos mūšis; Vytautas Didysis; Lietuvos istorija; Aukso Orda; epinė fantastika |
| Categories (verify in the picker) | Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Dark Fantasy ; Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Epic ; Kindle Store > Kindle eBooks > Literature & Fiction > Historical Fiction > Medieval |

**Lietuviškas aprašymas:** Tylioji Sutartis mirusi, šventoji ugnis Vilniuje užgesinta, o Vytautas gyvena su viena paslaptimi: maža liepsna, kurią slapčia saugo nebaigtos tėvo pilies pamatuose. Šį kartą jį varo ne kerštas, o ambicija. Ji antrą kartą nuveda jį pas Ordiną ir į trečią išdavystę, o Astravo susitarimas padaro jį Didžiuoju kunigaikščiu ir pažadina imperijos sapną nuo Baltijos iki Juodosios jūros. Už kiekvieną žingsnį kažkas sumoka. 1399 metų rugpjūčio 12-ąją, ties Vorskla, stepė suėda jo kariuomenę. Tai knyga, kurioje herojus pralaimi, ir būtent todėl ji parašyta: auksas meta ilgą šešėlį, o šešėlis anksčiau ar vėliau pradeda eiti pirmas.

**English description:** The Silent Pact is dead, the holy fire in Vilnius is put out, and Vytautas lives with one secret: a small flame he guards in the foundations of his father's unfinished island castle. This time he is driven not by revenge but by ambition. It leads him to the Order a second time and into a third betrayal, and the Astrava agreement makes him Grand Duke and wakes a dream of empire from the Baltic to the Black Sea. For every step, someone pays. On 12 August 1399, on the river Vorskla, the steppe devours his army. This is a book in which the hero loses, and that is exactly why it was written: gold casts a long shadow, and sooner or later the shadow walks ahead.

### Book III: Žaliasis Miškas / The Green Wood

| Field | Value |
|---|---|
| Title (LT / EN) | Žaliasis Miškas / The Green Wood |
| Subtitle | none (series name goes in the Series field) |
| Series | Geležinio Vilko Saga / The Iron Wolf Saga, number 3 |
| Author | Algimantas Krasauskas |
| Period covered | 1399–1411 |
| Language | Lithuanian (not available on KDP) / English (planned) |
| EPUB identifier | `urn:uuid:5939e729-e557-4c02-af7c-5a5d53d1af8e` (ISBN: to be issued) |
| Files | `saga-3-store.epub`, `print_cover_kdp.pdf`, `saga-3-print.pdf` |
| Keywords (EN, 7) | dark fantasy; historical fantasy; Battle of Grunwald; Samogitia; medieval Lithuania; Vytautas the Great; epic fantasy series |
| Keywords (LT, 7) | tamsioji fantastika; istorinė fantastika; Žalgirio mūšis; Žemaitija; Lietuvos istorija; Vytautas Didysis; epinė fantastika |
| Categories (verify in the picker) | Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Dark Fantasy ; Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Epic ; Kindle Store > Kindle eBooks > Literature & Fiction > Historical Fiction > Medieval |

**Lietuviškas aprašymas:** Po Vorsklos Vytautui nebeliko nieko, tik miškas. Žemaitija, parduota visų sutarčių, kyla vėl ir vėl, o Ordinas ruošia paskutinį didįjį kryžiaus žygį. Kad jį sustabdytų, Vytautas turės susitaikyti su pusbroliu, kurio vyrai pasmaugė jo tėvą. Pasitelkęs senųjų dievų likučius, jis žengia link lauko, kuriame vienas amžius turės užleisti vietą kitam: 1410 metų liepos 15-oji, Žalgiris. Bet ar pergalė ką nors pakeis tiems, kurie miške laukia?

**English description:** After the Vorskla, nothing was left to Vytautas but the forest. Samogitia, sold by every treaty, rises again and again, and the Order prepares its last great crusade. To stop it, Vytautas must make peace with the cousin whose men strangled his father. Calling on what remains of the old gods, he walks toward the field where one age must make way for another: 15 July 1410, Grunwald. But will victory change anything for those who wait in the forest?

### Book IV: Nematoma Karūna / The Invisible Crown

| Field | Value |
|---|---|
| Title (LT / EN) | Nematoma Karūna / The Invisible Crown |
| Subtitle | none (series name goes in the Series field) |
| Series | Geležinio Vilko Saga / The Iron Wolf Saga, number 4 |
| Author | Algimantas Krasauskas |
| Period covered | 1411–1430 |
| Language | Lithuanian (not available on KDP) / English (planned) |
| EPUB identifier | `urn:uuid:61e869e6-5986-40b9-8e62-20265e558088` (ISBN: to be issued) |
| Files | `saga-4-store.epub`, `print_cover_kdp.pdf`, `saga-4-print.pdf` |
| Keywords (EN, 7) | dark fantasy; historical fantasy; medieval Lithuania; Christianization of Samogitia; Council of Constance; Vytautas the Great; epic fantasy series |
| Keywords (LT, 7) | tamsioji fantastika; istorinė fantastika; Žemaitijos krikštas; Konstanco susirinkimas; Lucko suvažiavimas; Vytauto karūna; epinė fantastika |
| Categories (verify in the picker) | Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Dark Fantasy ; Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Epic ; Kindle Store > Kindle eBooks > Literature & Fiction > Historical Fiction > Medieval |

**Lietuviškas aprašymas:** Žalgiris laimėjo karą, bet ne dievus. Žemaitijos giraitės krikštijamos, vienas po kito užgęsta šventi aukurai, o Vytautas dieną kartoja tikėjimo išpažinimą, naktį saugo paslaptį, kurios neturėtų žinoti niekas. Jo valdos driekiasi nuo jūros iki jūros, ir trūksta tik vieno: karūnos. Bet už karūną kas nors visada paprašys kainos, o Šešėlių Pardavėjas niekada nepamiršta savo sąskaitų. Istorija žino pabaigą: karūna sulaikyta pakeliui, senasis kunigaikštis miršta Trakuose 1430 metų spalio 27-ąją. Ši knyga klausia, kas tą naktį užgeso kartu su juo.

**English description:** Grunwald won the war, but not the gods. The groves of Samogitia are baptised, one holy altar after another goes dark, and by day Vytautas recites the Creed while by night he guards a secret no one should know. His lands stretch from sea to sea, and only one thing is missing: a crown. But someone always asks a price for a crown, and the Seller of Shadows never forgets his accounts. History knows the ending: the crown is held back on the road, and the old duke dies at Trakai on 27 October 1430. This book asks what went out that night together with him.

### Book V: Vilko Palikimas / The Wolf's Legacy

| Field | Value |
|---|---|
| Title (LT / EN) | Vilko Palikimas / The Wolf's Legacy |
| Subtitle | none (series name goes in the Series field) |
| Series | Geležinio Vilko Saga / The Iron Wolf Saga, number 5 |
| Author | Algimantas Krasauskas |
| Period covered | 1430–1450 |
| Language | Lithuanian (not available on KDP) / English (planned) |
| EPUB identifier | `urn:uuid:ac2b421e-63c8-45d8-909f-ad5fe55c4cfa` (ISBN: to be issued) |
| Files | `saga-5-store.epub`, `print_cover_kdp.pdf`, `saga-5-print.pdf` |
| Keywords (EN, 7) | dark fantasy; historical fantasy; medieval Lithuania; Lithuanian civil war; Švitrigaila; Grand Duchy of Lithuania; epic fantasy series |
| Keywords (LT, 7) | tamsioji fantastika; istorinė fantastika; Švitrigaila; Žygimantas Kęstutaitis; Pabaisko mūšis; Lietuvos istorija; epinė fantastika |
| Categories (verify in the picker) | Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Dark Fantasy ; Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Epic ; Kindle Store > Kindle eBooks > Literature & Fiction > Historical Fiction > Medieval |

**Lietuviškas aprašymas:** Didysis kunigaikštis mirė, o kartu su juo nutilo kažkas senesnio už Lietuvą. Rūsyje užgęsta Paskutinė Liepsna, jo įpėdiniai kariauja dėl sosto, o jaunas vilkas, kurio užduotis buvo ją saugoti, lieka su šaltais pelenais rankose ir vienu troškimu: viską atkurti. Bet ugnį gali uždegti bet kas, o kai kurių sutarčių vienas žmogus iš naujo prisiekti negali. Brolis kovoja prieš brolį iki Pabaisko lauko, vietoj priesaikų ir ženklų ateina antspaudai ir raštai. Pasakoja ta, kuri viską mena nuo pat pradžios.

**English description:** The Grand Duke is dead, and with him something older than Lithuania has fallen silent. In the cellar the Last Flame goes out; his heirs wage war for the throne, and the young wolf who was sworn to guard it is left with cold ashes in his hands and one desire: to restore it all. But anyone can light a fire, and some pacts one man cannot swear again. Brother fights brother to the field of Pabaiskas, and seals and charters replace oaths and signs. The tale is told by the one who remembers everything from the very beginning.

### Book VI: Šventasis Miškas / The Holy Forest

| Field | Value |
|---|---|
| Title (LT / EN) | Šventasis Miškas / The Holy Forest |
| Subtitle | none (series name goes in the Series field) |
| Series | Geležinio Vilko Saga / The Iron Wolf Saga, number 6 |
| Author | Algimantas Krasauskas |
| Period covered | 1345–1377 |
| Language | Lithuanian (not available on KDP) / English (planned) |
| EPUB identifier | `urn:uuid:a038c1bc-a3c1-4213-b1ec-e1a94388d2e9` (ISBN: to be issued) |
| Files | `saga-6-store.epub`, `print_cover_kdp.pdf`, `saga-6-print.pdf` |
| Keywords (EN, 7) | dark fantasy; historical fantasy; prequel; Kęstutis and Birutė; medieval Lithuania; Teutonic Order; epic fantasy series |
| Keywords (LT, 7) | tamsioji fantastika; istorinė fantastika; priešistorė; Kęstutis ir Birutė; Lietuvos istorija; Algirdas; epinė fantastika |
| Categories (verify in the picker) | Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Dark Fantasy ; Kindle Store > Kindle eBooks > Science Fiction & Fantasy > Fantasy > Epic ; Kindle Store > Kindle eBooks > Literature & Fiction > Historical Fiction > Medieval |

**Lietuviškas aprašymas:** Lietuva turėjo žlugti per Ordino šimtmečio kryžiaus žygį, bet nežlugo. Priežastis slypi vienoje nakties priesaikoje Šventaragio slėnyje, kur du broliai davė žodį senesniems už juos. Kęstutis, jaunesnysis, ištarė paskutinį sakinį garsiai, ir visą likusį gyvenimą moka už jį kainą. Gintaro žynė iš Palangos, Marienburgo požemiai ir brolis, kuris niekada neatleido. Tai priešistorė, kuri baigiasi ten, kur prasideda pirmoji saga, ir istorija, nuo kurios prasideda viskas.

**English description:** Lithuania should have fallen in the Order's century-long crusade, but it did not. The reason lies in one night's oath in the Valley of Šventaragis, where two brothers gave their word to powers older than themselves. Kęstutis, the younger, spoke the last sentence aloud, and has paid for it all his life. An amber priestess from Palanga, the dungeons of Marienburg and a brother who never forgave. This prequel ends where the first book of the saga begins: the story from which everything starts.


## 8. Lietuvos rinka (Lithuanian market)

Research found no Lithuanian self-serve platform like KDP, so the route is a combination of small channels.
Verified facts are marked; the rest is a lead to confirm by email.

**(1) E-books in Lithuanian shops.** knygos.lt, pegasas.lt, patogupirkti.lt and vaga.lt sell e-books, but none has an
author upload. You go through a distributor:

* **UAB "Išmintis" / Mintis** ([mintis.eu](https://www.mintis.eu/content/8-tiekejams), "Tiekėjams" page). Verified:
  it describes itself as a seller and distributor of publications in Lithuania, supplies **knygos.lt,
  patogupirkti.lt, vaga.lt and pegasas.lt** and a list of independent bookshops, and invites suppliers to send
  offers to `ismintis.uab@gmail.com` (general: `ismintis@mintis.eu`, +370 684 77427). The page gives **no** commission
  or discount terms and **does not mention e-books**: ask whether they take e-books or only print.
* **Knygute.lt**: an e-book publisher that digitises books of other publishers and says "kviečiame bendradarbiavimui"
  (we invite cooperation) (verified on the home page). Royalties, ISBN handling and which shops it reaches are
  **not stated**: use the "Leidėjams" page or write to them.

**(2) Print on demand and short runs in Lithuania** (the 6 x 9 in KDP interior PDF is a normal book PDF; if a
printer prefers A5, re-impose or re-render with the same extension at A5):

* **TUKa** (tuka.lt, Kaunas): contact `pardavimai@tuka.lt`, 0 685 70534 (verified on the home page); it advertises
  "Spauda pagal poreikį" (print on demand) and hard and soft cover books. "From 1 copy" and prices are **unverified**.
* **knyguspausdinimas.lt**: "Kieto įrišimo knygos mažais tiražais nuo 10 vnt." and runs mostly between 10 and
  300 copies; PDF preferred; `info@knyguspausdinimas.lt` (verified on the site).
* **Reklamos forma** (Panevėžys, `info@reklamosforma.lt`): its site (checked) shows business printing only; the
  "author-funded book with a proof copy in about 10 days" claim is **unverified**: ask.

**(3) ISBN and legal deposit.** See section 6: the ISBN is paid, the author can register as a natural person, and
legal deposit copies are due for runs over 25 copies.

**(4) Amazon still reaches Lithuanian readers** with the English edition (section 1) through amazon.de and the other
EU stores.

**Other routes for the Lithuanian edition**

* **IngramSpark**: Lithuania is on its list of countries where publishers may have an account, for print and for
  e-books (verified, [IngramSpark help](https://help.ingramspark.com/hc/en-us/articles/16684961523085-IngramSpark-Can-Provide-Print-Ebook-Distribution-Services-To-These-Countries)).
  Whether it **accepts a Lithuanian-language title** and whether its channels ever put it on Amazon (mainly US and
  Canada, never guaranteed) is **unverified**.
* **Draft2Digital**: its Amazon channel is invitation-only (verified) and its Lithuanian support is **unverified**
  (section 5).

**Recommended combined plan**

1. **Now:** register as a publisher with the ISBN agency (natural person is enough), buy one e-book ISBN and one
   print ISBN per book (12 in total), or start with book 1.
2. **Lithuanian paperback:** a small TUKa run (a proof copy first), sold through Mintis into Lithuanian bookshops;
   deposit the legal-deposit copies if the run exceeds 25.
3. **Lithuanian e-book:** `saga-N-store.epub` through Mintis (if they take e-books) or Knygute to knygos.lt and
   pegasas.lt.
4. **Worldwide:** the English edition on KDP (paperback and Kindle, section 4), going wide to Apple, Kobo and Google
   (section 5) or Kindle-exclusive in Select, your choice. The Lithuanian edition is not eligible for KDP.

## 9. English descriptions

The English descriptions in section 7 are translations of the Lithuanian blurbs, for the international storefronts
and for the back cover of an English edition (`make_covers.py --lang en print N`). They are in
`books/book_meta.yml` (`blurb_en`); the Lithuanian sheets and the covers read the same file.

## 10. Checklist per book

1. `python3 scripts/gen_book_quarto.py --profiles` if `book_meta.yml` changed.
2. `quarto render --profile store --to saga-store-epub --no-clean` and run epubcheck (0 errors).
3. Add the ISBN to `book_meta.yml` once issued; rebuild.
4. Fill the store forms from section 7; upload the EPUB and `front_ebook_1600x2560.jpg`.
5. Answer the AI-disclosure questions truthfully (section 4.2).
6. Paperback: see PRINTING.md.
