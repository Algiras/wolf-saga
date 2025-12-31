#!/usr/bin/env python3
"""
Clean invalid TTS tags from preprocessed files.
Only keep supported paralinguistic tags.
"""

import re
from pathlib import Path

# Valid paralinguistic tags that Chatterbox-Turbo supports
VALID_TAGS = {
    '[chuckle]',
    '[laugh]',
    '[sigh]',
    '[gasp]',
    '[cough]',
    '[groan]',
    '[sniff]',
    '[clear throat]',
    '[shush]'
}

def clean_file(file_path):
    """Remove invalid tags from a file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Find all tags
    all_tags = re.findall(r'\[[^\]]+\]', content)
    
    # Remove invalid tags
    for tag in set(all_tags):
        if tag.lower() not in {v.lower() for v in VALID_TAGS}:
            # Remove the tag
            content = content.replace(tag, '')
    
    # Clean up extra whitespace that might result from tag removal
    content = re.sub(r' +', ' ', content)  # Multiple spaces to single
    content = re.sub(r'\n\n\n+', '\n\n\n', content)  # Max 3 newlines
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    preprocessed_dir = Path('preprocessed')
    
    if not preprocessed_dir.exists():
        print("❌ preprocessed/ directory not found")
        return
    
    files = list(preprocessed_dir.glob('*.txt'))
    print(f"🔍 Found {len(files)} preprocessed files")
    
    cleaned_count = 0
    for file_path in files:
        if clean_file(file_path):
            cleaned_count += 1
            print(f"   ✓ Cleaned: {file_path.name}")
    
    print(f"\n✅ Cleaned {cleaned_count}/{len(files)} files")
    print(f"\nValid tags kept: {', '.join(sorted(VALID_TAGS))}")

if __name__ == '__main__':
    main()
