# I Knyga: Vilko Tremtis (The Wolf's Exile)

Šiame kataloge saugomi pirmosios "Geležinio Vilko Saugos" knygos tekstai ir planai.

## Progresas
- [x] Deep Scaffolding (Visi 30 skyrių)
- [x] Lietuviška proza:
    - [x] Prologas: Gintaro Ašaros 
    - [x] 1-10 Skyriai (I dalis: Nuosmukis)
    - [x] 11-19 Skyriai (II dalis: Pabėgimas)
    - [x] 20-30 Skyriai (III dalis: Karas ir Tvarka)

## Failų Struktūra
- `chapter_XX_plan.md`: Detalus skyriaus planas (scaffold).
- `XX_pavadinimas.qmd`: Galutinė lietuviška proza.
- `index.qmd`: Knygos pratarmė.
- `prologue.qmd`: Įžanginis tekstas.

## PDF Generavimas
Knygą galima sugeneruoti naudojant Quarto komandą iš šakninio `books/` katalogo:
```bash
quarto render --to pdf
```
Rezultatas išsaugomas `books/_book/Geležinio-Vilko-Saga.pdf`.
