# Editorial Review Script

Automatinis redagavimo skriptas naudojant LangChain ir Mistral 8B.

## Įdiegimas

```bash
cd scripts
pip install -r requirements.txt
```

## Naudojimas

1. Įsitikinkite, kad Ollama veikia ir Mistral 8B modelis įdiegtas:
```bash
ollama list
# Jei Mistral nėra, įdiekite:
ollama pull mistral:8b
```

2. Paleiskite skriptą:
```bash
python editorial_review.py
```

## Ką skriptas daro

Skriptas peržiūri visus `.qmd` failus `books/1/` kataloge ir ieško:

1. **Anachronizmų** - modernių terminų, kurie netinka XIV a.
2. **Anglicizmų** - tiesioginių vertimų iš anglų kalbos
3. **Gramatinių klaidų** - neteisingų linksnių, neegzistuojančių žodžių
4. **Stiliaus problemų** - per daug būdvardžių, perteklinių žodžių

## Rezultatai

Rezultatai išsaugomi `editorial_review_results.json` faile JSON formatu.

## Pavyzdys

```json
{
  "file": "13_keitimas.qmd",
  "status": "reviewed",
  "result": {
    "errors": [
      {
        "type": "anachronism",
        "original": "strateginis planas",
        "fixed": "karo planas",
        "explanation": "Terminas 'strateginis' yra modernus",
        "line_approx": "...turėjo strateginį planą..."
      }
    ],
    "summary": "Rasta 1 klaida"
  }
}
```
