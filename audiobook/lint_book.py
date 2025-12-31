#!/usr/bin/env python3
import glob
import re
from pathlib import Path
import yaml
import sys

BOOK_DIR = Path("../books")
files = sorted(glob.glob(str(BOOK_DIR / "*.qmd")))

errors = []
titles = {}

print(f"🔍 Linting {len(files)} QMD files in {BOOK_DIR}...\n")

for file_path in files:
    path = Path(file_path)
    filename = path.name
    
    # Skip reference files if needed, or specific ones
    if filename.startswith("_"):
        continue

    with open(path, 'r') as f:
        content = f.read()
        lines = content.split('\n')

    # Rule 1: Must have a top-level header # Title
    has_title = False
    title_text = ""
    for line in lines:
        match = re.match(r'^#\s+(.+?)(\s+\{[^}]*\})?\s*$', line)
        if match:
            has_title = True
            title_text = match.group(1).strip()
            break
    
    if not has_title:
        errors.append(f"❌ {filename}: Missing top-level header (# Title)")
    else:
        # Rule 2: Unique titles
        if title_text in titles:
            errors.append(f"❌ {filename}: Duplicate title '{title_text}' (also in {titles[title_text]})")
        else:
            titles[title_text] = filename

    # Rule 3: Check for proper frontmatter ending (optional)
    if content.startswith("---"):
        if content.count("---") < 2:
             errors.append(f"⚠️ {filename}: Potentially unclosed YAML frontmatter")

if not errors:
    print("✅ All files passed linting checks!")
    sys.exit(0)
else:
    print("\nFound issues:")
    for err in errors:
        print(err)
    sys.exit(1)
