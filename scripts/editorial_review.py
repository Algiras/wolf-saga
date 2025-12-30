#!/usr/bin/env python3
"""
Editorial Review Script using Ministral 3 8B
Automatically reviews and fixes anachronisms, anglicisms, and style issues in Lithuanian text.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict
from langchain_community.llms import Ollama

# Configuration
OLLAMA_MODEL = "ministral-3:8b"
BOOKS_DIR = Path(__file__).parent.parent / "books" / "1"

# Editorial rules prompt
EDITORIAL_PROMPT = """Tu esi profesionalus lietuvių kalbos redaktorius, specializuojantis XIV amžiaus istorinėje literatūroje.

Tavo užduotis: peržiūrėti tekstą ir rasti VISAS klaidas:

1. ANACHRONIZMAI (modernūs terminai):
   - "strateginis", "operacinis", "administracinis" → keisti į viduramžiškus terminus
   - "kliniškas" → "šaltas", "tikslus"
   - Bet kokie XIX-XXI a. terminai

2. ANGLICIZMAI:
   - "pasijuto" (it felt) → "pasirodė", "atrodė", "jautėsi"
   - Tiesioginis vertimas iš anglų kalbos

3. GRAMATINĖS KLAIDOS:
   - Neteisingas linksnių derinimas
   - Neegzistuojantys žodžiai
   - Neteisingi veiksmažodžiai

4. STILIUS:
   - Per daug būdvardžių (daugiau nei 2 iš eilės)
   - Pertekliniai žodžiai
   - Pasikartojantys posakiai

TEKSTAS:
{text}

ATSAKYK JSON FORMATU:
{{
  "errors": [
    {{
      "type": "anachronism|anglicism|grammar|style",
      "original": "tikslus tekstas su klaida",
      "fixed": "ištaisytas tekstas",
      "explanation": "kodėl tai klaida",
      "line_approx": "apytikslė eilutė arba frazė"
    }}
  ],
  "summary": "trumpa suvestinė: kiek klaidų rasta"
}}

Jei klaidų nėra, grąžink: {{"errors": [], "summary": "Tekstas švarus, klaidų nerasta"}}
"""

def init_llm():
    """Initialize Ollama LLM with Ministral"""
    try:
        llm = Ollama(
            model=OLLAMA_MODEL,
            temperature=0.1,  # Low temperature for consistent editorial work
            num_ctx=4096,     # Context window
        )
        # Test connection
        llm.invoke("test")
        return llm
    except Exception as e:
        print(f"❌ Klaida inicializuojant Ollama: {e}")
        print("Patikrinkite ar Ollama veikia: ollama list")
        sys.exit(1)

def review_file(file_path: Path, llm: Ollama) -> Dict:
    """Review a single .qmd file"""
    print(f"\n📖 Peržiūrima: {file_path.name}")
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Skip if file is too short (likely just a title)
        if len(content) < 100:
            return {"file": file_path.name, "status": "skipped", "reason": "per trumpas"}
        
        # Review with LLM
        prompt = EDITORIAL_PROMPT.format(text=content)
        result = llm.invoke(prompt)
        
        return {
            "file": file_path.name,
            "status": "reviewed",
            "result": result
        }
    except Exception as e:
        return {
            "file": file_path.name,
            "status": "error",
            "error": str(e)
        }

def main():
    """Main execution"""
    print("🔍 Geležinio Vilko Saga - Automatinė Redakcija")
    print("=" * 60)
    
    # Initialize
    print("\n⚙️  Inicializuojama Ministral 3 8B...")
    llm = init_llm()
    print("✅ Ministral 3 8B paruoštas")
    
    # Find all .qmd files
    qmd_files = sorted(BOOKS_DIR.glob("*.qmd"))
    print(f"\n📚 Rasta {len(qmd_files)} failų")
    
    # Review each file
    results = []
    for i, file_path in enumerate(qmd_files, 1):
        print(f"\n[{i}/{len(qmd_files)}]", end=" ")
        result = review_file(file_path, llm)
        results.append(result)
        
        # Print summary
        if result["status"] == "reviewed":
            print("✅ Peržiūrėta")
            # Try to parse JSON response
            try:
                response_data = json.loads(result['result'])
                error_count = len(response_data.get('errors', []))
                print(f"   Rasta klaidų: {error_count}")
                if error_count > 0:
                    print(f"   {response_data.get('summary', '')}")
            except:
                print(f"   Rezultatas: {result['result'][:150]}...")
        elif result["status"] == "skipped":
            print(f"⏭️  Praleista: {result['reason']}")
        else:
            print(f"❌ Klaida: {result.get('error', 'Nežinoma')}")
    
    # Final summary
    print("\n" + "=" * 60)
    print("📊 GALUTINĖ SUVESTINĖ")
    print("=" * 60)
    reviewed = sum(1 for r in results if r["status"] == "reviewed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    
    print(f"✅ Peržiūrėta: {reviewed}")
    print(f"⏭️  Praleista: {skipped}")
    print(f"❌ Klaidos: {errors}")
    
    # Save results
    output_file = Path(__file__).parent / "editorial_review_results.json"
    output_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n💾 Rezultatai išsaugoti: {output_file}")

if __name__ == "__main__":
    main()
