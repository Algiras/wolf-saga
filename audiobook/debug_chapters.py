import yaml
from pathlib import Path

def load_quarto_config():
    with open('../book/_quarto.yml', 'r') as f:
        config = yaml.safe_load(f)
    return config.get('book', {}).get('chapters', [])

def get_ordered_chapters(chapters):
    all_chapters = []
    for chapter_entry in chapters:
        if isinstance(chapter_entry, str):
            chapter_file = chapter_entry
            chapter_name = Path(chapter_file).stem
            if chapter_file in ['index.qmd', 'references.qmd'] or chapter_name.startswith('interlude'):
                continue
            all_chapters.append((chapter_file, chapter_name))
        elif isinstance(chapter_entry, dict):
            if 'part' in chapter_entry and 'chapters' in chapter_entry:
                for nested_chapter in chapter_entry['chapters']:
                    if isinstance(nested_chapter, str):
                        chapter_file = nested_chapter
                        chapter_name = Path(chapter_file).stem
                        if chapter_file in ['index.qmd', 'references.qmd'] or chapter_name.startswith('interlude'):
                            continue
                        all_chapters.append((chapter_file, chapter_name))
    return all_chapters

config = load_quarto_config()
all_chapters = get_ordered_chapters(config)

for i, (file, name) in enumerate(all_chapters):
    print(f"{i:02d}: {name} ({file})")
