# Writing Brief: Drafting Books II–VI

Shared instructions for every drafting agent. **Read this whole file first.**

## Binding sources (precedence order)

1. `world_rules/canon_decisions.md` (D1–D11 and the open-question defaults)
2. `world_rules/cosmology.md`, `magic_rules.md`, `power_systems.md`, `master_chronology.md`
3. `books/series_arc.md`, `books/character_arcs.md`
4. **Your book's outline**, `books/N/detailed_outline.md` (premise, forms, antagonists, magic state, the chapter rows, the continuity checklist)
5. Reference: `world_rules/` (geography, peoples, houses, politics, religion, bestiary, iron_wolves, legends, languages, calendar, pronunciation), `persona/`
6. **Voice model:** read Book I chapters `books/1/03_gintaro_sapnas.qmd`, `books/1/08_krevos_pozemiai.qmd`, `books/1/24_pasirinkimas.qmd` and `books/1/28b_krevos_sutartis.qmd` before writing. Book II agents: also read Book I ch. 28–30 (the hand-off). Book VI agents: also read Book I ch. 1–3 (where the prequel must land).

## Language and voice

- **Lithuanian**, literary, with correct diacritics and grammar. Third person, past tense; one POV per scene (the outline names the chapter POV).
- Dark, grounded, sensory (smell, cold, weight, sound). Folklore is literal and the folk are half right. Grey morality on every side.
- **Lean prose.** Avoid stacked intensifiers ("mirtinai", "neįtikėtinai", "negailestingai") and the "tai buvo / tai nebuvo" crutch. No copy-pasted passages or repeated templates across chapters. Vary chapter openings.
- Dialogue carries character. Kinship terms per D9; names per D4 ("Vyti" only from Birutė, Kęstutis or the Beggar; "Vytis" only for the coat of arms).

## History and magic

- Real dates, office-holders and outcomes are **fixed** (`master_chronology.md`). Myth explains gaps and never contradicts the record. Where the outline says "(verify)", write around it: don't invent a precise contested fact.
- Every magic use shows its **cost** on the page (`magic_rules.md` §4). Respect zeniths, the Law of Truth (no illusions by mortals), the power scale ceiling (a mortal working never exceeds "a castle, a night"), and the declining practitioner counts and Unbinding level in the graph progressions.
- Track the recurring objects: Birutė's pebble (state per book), the silver wolf, the Last Flame, Henė's stones (3 → 2 in 1397 → 1 in 1430 → 0).

## Format

- One file per chapter: `books/N/NN_slug.qmd` (two-digit number, ASCII slug from the Lithuanian title, e.g. `books/2/01_stepiu_vejas.qmd`). Use the outline's chapter numbers and titles.
- The file starts with `# <Lithuanian chapter title>`, then prose. Optionally use one dateline in italics under the title, e.g. `*1389 m. ruduo, Trakai*`.
- **Length:** 1,500–2,500 words per chapter (fuller than Book I). Set pieces such as battles, sieges and deaths may run to 3,000.
- No front matter, no English, no meta-commentary in chapter files.

## Ownership and hand-off

- Each agent owns **one part** (about 10 chapters) of one book and writes only those chapter files plus its notes file `books/N/notes/partK_notes.md`.
- Parts of the same book are drafted **in parallel**, so follow the outline exactly at part boundaries (the first chapter's situation, the last chapter's ending state).
- In your notes file record facts you **established** that others must respect: new minor names, wounds, objects, who knows what, exact places, dates used, and any deviation from the outline with the reason. Keep it short and factual.
- Do not edit canon docs, outlines, Book I, `_quarto.yml` or other parts' files. If the outline conflicts with canon, follow canon and note it.
- Do not commit.

## Report

When done, report: the files written (with word counts), a 2-line summary per chapter, the facts established that matter for other parts, outline deviations, and canon questions.
