# World Bible: Geležinio Vilko Saga

The canon for the saga, the Lithuanian answer to what Sapkowski did for Polish history: folklore taken literally, history kept to the record, and grey morality on every side. Browse it rendered in the wiki (`wiki/`, the **Codex** and **Atlas** sections), or read the files here.

## Canon core (read first; precedence top to bottom)

| Doc | What it settles |
|---|---|
| [canon_decisions.md](canon_decisions.md) | Every resolved contradiction (D1–D10), glossary, kinship, open questions |
| [cosmology.md](cosmology.md) | World Tree; gods → Forces → craft; the Amber Queen office; the Silent Pact; the Unbinding |
| [magic_rules.md](magic_rules.md) | Senovės Kalba mechanics: formula, zeniths, costs, Five-Voice, surety, Sutartis rite, claims, bargains |
| [power_systems.md](power_systems.md) | Six schools, granted and bought powers, tiers 0–5, enchantment, named artifacts, power scale |
| [master_chronology.md](master_chronology.md) | Dated record 1009–1447 with hidden history and book mapping |

## The world

| Doc | |
|---|---|
| [geography_gazetteer.md](geography_gazetteer.md) | Lands, the Dykra, 45 places, travel times |
| [peoples_and_cultures.md](peoples_and_cultures.md) | Peoples, daily life, law, grey-morality notes |
| [houses_and_lineages.md](houses_and_lineages.md) | Gediminid tree, house cards, boyars, Order Grand Masters |
| [powers_and_politics.md](powers_and_politics.md) | Factions, treaties, board state per book, story engines |
| [religion_and_clergy.md](religion_and_clergy.md) | Pagan clergy, Orthodoxy, Catholicism, the Order, holy places |
| [bestiary.md](bestiary.md) | 28 creatures: folk source, half-wrong truth, banes and their cost |
| [iron_wolves.md](iron_wolves.md) | The vilkatai brotherhood |
| [legends_and_songs.md](legends_and_songs.md) | Ten legends retold with the saga's twist, proverbs, dainos |
| [languages_and_naming.md](languages_and_naming.md) | Languages, name structure, true names, glossary |
| [pronunciation_guide.md](pronunciation_guide.md) · [pronunciation_lexicon.json](pronunciation_lexicon.json) | How to say every name (IPA, stress, English sound-alike); TTS lexicon |
| [calendar_and_festivals.md](calendar_and_festivals.md) | Month names, festival wheel, zeniths, Book I dates |

## The graph (machine-checked canon)

- [graph/world_graph.json](graph/world_graph.json): nodes, time-bounded relations, and progressions (Pact, Unbinding, practitioner decline, Henė's stones, Vytautas's forms, the amber pebble).
- `python3 scripts/validate_world_graph.py` checks consistency and writes [graph/relation_maps.md](graph/relation_maps.md).
- `python3 scripts/build_wiki.py && quarto render wiki` builds the wiki and the Atlas.

## Story docs

- [../books/series_arc.md](../books/series_arc.md): the ten threads braided through Books I–VI
- [../books/character_arcs.md](../books/character_arcs.md): the protagonist's seven forms, antagonists per book, supporting arcs
- [../books/1/story_review.md](../books/1/story_review.md) · [../books/1/continuity_bible.md](../books/1/continuity_bible.md): Book I review and line-level fix list

## Older docs (superseded where they conflict)

`mythology_pantheon.md`, `meddling_forces.md`, `hidden_immortals.md`, `mythic_gaps.md`, `mystical_mechanics.md`, `history_timeline.md`, `surrounding_folklore.md`. Each carries a canon note pointing to its replacement.
