#!/usr/bin/env python3
"""
ReAct Editorial Agent using Ministral 3 8B
Autonomously reviews and fixes anachronisms, anglicisms, and style issues.
Creates a PR with all changes for final review.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from langchain_community.llms import Ollama

# Configuration
OLLAMA_MODEL = "ministral-3:8b"
BOOKS_DIR = Path(__file__).parent.parent / "books" / "1"
MAX_FIXES_PER_FILE = 10  # Limit to avoid over-editing

# ReAct Agent Prompt
REACT_PROMPT = """Tu esi autonominis redagavimo agentas. Tavo užduotis: rasti ir IŠTAISYTI klaidas XIV a. lietuviškame tekste.

SVARBU: Tu turi galimybę TIESIOGIAI REDAGUOTI tekstą. Naudok ReAct (Reasoning + Acting) metodą.

TAISYKLĖS:
1. ANACHRONIZMAI - modernūs terminai, kurie netinka XIV a.
2. ANGLICIZMAI - tiesioginis vertimas iš anglų kalbos
3. GRAMATIKA - neteisingi linksniai, neegzistuojantys žodžiai
4. STILIUS - per daug būdvardžių, pertekliniai žodžiai

TEKSTAS:
```
{text}
```

ATSAKYK JSON FORMATU su TIKSLIAIS PAKEITIMAIS:
{{
  "thought": "Ką pastebėjau tekste...",
  "fixes": [
    {{
      "type": "anachronism|anglicism|grammar|style",
      "original": "TIKSLUS tekstas su klaida (10-50 žodžių)",
      "fixed": "TIKSLUS ištaisytas tekstas (10-50 žodžių)",
      "explanation": "Kodėl tai klaida ir kaip ištaisyta",
      "confidence": 0.0-1.0
    }}
  ],
  "summary": "Rasta X klaidų, ištaisyta Y"
}}

SVARBIAUSIA:
- "original" turi būti TIKSLUS tekstas iš failo (su tarpais, skyrybos ženklais)
- "fixed" turi būti PILNAS ištaisytas fragmentas
- Jei klaidų nėra: {{"thought": "...", "fixes": [], "summary": "Tekstas švarus"}}
- Maksimaliai {max_fixes} taisymų per failą
"""

class EditorialAgent:
    """ReAct agent for autonomous text editing"""
    
    def __init__(self, model: str = OLLAMA_MODEL):
        self.llm = Ollama(model=model, temperature=0.1, num_ctx=8192)
        self.changes_log = []
        
    def review_and_fix(self, file_path: Path) -> Dict:
        """Review file and return fixes"""
        print(f"\n📖 Analizuoja: {file_path.name}")
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            if len(content) < 100:
                return {"file": file_path.name, "status": "skipped", "reason": "per trumpas"}
            
            # Get fixes from LLM
            prompt = REACT_PROMPT.format(text=content, max_fixes=MAX_FIXES_PER_FILE)
            response = self.llm.invoke(prompt)
            
            # Parse JSON response
            try:
                # Extract JSON from response (might have markdown code blocks)
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1)
                elif '```' in response:
                    # Remove code blocks
                    response = re.sub(r'```[a-z]*\s*', '', response)
                    response = response.replace('```', '')
                
                fixes_data = json.loads(response.strip())
                
                return {
                    "file": file_path.name,
                    "status": "reviewed",
                    "thought": fixes_data.get("thought", ""),
                    "fixes": fixes_data.get("fixes", []),
                    "summary": fixes_data.get("summary", "")
                }
            except json.JSONDecodeError as e:
                print(f"   ⚠️  JSON klaida: {e}")
                print(f"   Response: {response[:200]}...")
                return {
                    "file": file_path.name,
                    "status": "error",
                    "error": f"JSON parse error: {str(e)}",
                    "raw_response": response[:500]
                }
                
        except Exception as e:
            return {
                "file": file_path.name,
                "status": "error",
                "error": str(e)
            }
    
    def apply_fixes(self, file_path: Path, fixes: List[Dict]) -> Tuple[bool, int]:
        """Apply fixes to file"""
        if not fixes:
            return False, 0
        
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        applied_count = 0
        
        # Sort fixes by confidence (highest first)
        fixes_sorted = sorted(fixes, key=lambda x: x.get('confidence', 0.5), reverse=True)
        
        for fix in fixes_sorted:
            original = fix.get('original', '').strip()
            fixed = fix.get('fixed', '').strip()
            confidence = fix.get('confidence', 0.5)
            
            if not original or not fixed:
                continue
            
            # Only apply high-confidence fixes automatically
            if confidence < 0.7:
                print(f"   ⏭️  Praleista (žema pasitikėjimo: {confidence:.2f}): {original[:50]}...")
                continue
            
            # Try to find and replace
            if original in content:
                content = content.replace(original, fixed, 1)
                applied_count += 1
                print(f"   ✅ Ištaisyta ({confidence:.2f}): {fix.get('type', 'unknown')}")
                print(f"      - {original[:60]}...")
                print(f"      + {fixed[:60]}...")
                
                # Log change
                self.changes_log.append({
                    "file": file_path.name,
                    "type": fix.get('type'),
                    "original": original,
                    "fixed": fixed,
                    "explanation": fix.get('explanation'),
                    "confidence": confidence
                })
            else:
                print(f"   ⚠️  Nerastas tekstas: {original[:50]}...")
        
        # Write back if changes were made
        if applied_count > 0:
            file_path.write_text(content, encoding='utf-8')
            return True, applied_count
        
        return False, 0

def main():
    """Main execution"""
    print("🤖 ReAct Editorial Agent - Autonominis Redagavimas")
    print("=" * 70)
    
    # Initialize agent
    print("\n⚙️  Inicializuojama Ministral 3 8B...")
    agent = EditorialAgent()
    print("✅ Agentas paruoštas")
    
    # Find all .qmd files
    qmd_files = sorted(BOOKS_DIR.glob("*.qmd"))
    print(f"\n📚 Rasta {len(qmd_files)} failų")
    print(f"🎯 Maksimaliai {MAX_FIXES_PER_FILE} taisymų per failą")
    print(f"🔒 Tik aukšto pasitikėjimo (≥0.7) taisymai bus pritaikyti")
    
    # Process each file
    total_files_changed = 0
    total_fixes_applied = 0
    all_results = []
    
    for i, file_path in enumerate(qmd_files, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(qmd_files)}] {file_path.name}")
        print('='*70)
        
        # Review
        result = agent.review_and_fix(file_path)
        all_results.append(result)
        
        if result["status"] == "reviewed":
            fixes = result.get("fixes", [])
            print(f"\n💭 Mintis: {result.get('thought', 'N/A')}")
            print(f"📊 {result.get('summary', 'N/A')}")
            
            if fixes:
                print(f"\n🔧 Taikomi taisymai...")
                changed, count = agent.apply_fixes(file_path, fixes)
                if changed:
                    total_files_changed += 1
                    total_fixes_applied += count
                    print(f"\n✨ Pritaikyta {count} taisymų")
                else:
                    print(f"\n⏭️  Taisymai nebuvo pritaikyti (žemas pasitikėjimas arba tekstas nerastas)")
            else:
                print(f"\n✅ Klaidų nerasta")
        elif result["status"] == "skipped":
            print(f"⏭️  Praleista: {result.get('reason', 'N/A')}")
        else:
            print(f"❌ Klaida: {result.get('error', 'N/A')}")
    
    # Final summary
    print("\n" + "=" * 70)
    print("📊 GALUTINĖ SUVESTINĖ")
    print("=" * 70)
    print(f"📝 Pakeisti failai: {total_files_changed}/{len(qmd_files)}")
    print(f"✅ Pritaikyta taisymų: {total_fixes_applied}")
    
    # Save detailed log
    log_file = Path(__file__).parent / "editorial_changes_log.json"
    log_file.write_text(json.dumps({
        "summary": {
            "total_files": len(qmd_files),
            "files_changed": total_files_changed,
            "fixes_applied": total_fixes_applied
        },
        "changes": agent.changes_log,
        "all_results": all_results
    }, indent=2, ensure_ascii=False))
    
    print(f"\n💾 Detalus log: {log_file}")
    print(f"\n🔍 Peržiūrėkite pakeitimus: git diff books/1/")
    print(f"📦 Sukurkite PR: git add books/1/ && git commit -m 'Auto-fix editorial issues'")

if __name__ == "__main__":
    main()
