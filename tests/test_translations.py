import re
from pathlib import Path
import pytest
from rdflib import Graph

DOCS_DIR = Path("docs")
ALLOWED_LANGS = {"de", "fr", "it", "en"}

def get_lang_dirs():
    """Finds specified 2-letter language directories in docs/ (de, fr, it, en)."""
    if not DOCS_DIR.exists():
        return []
    return [
        d for d in DOCS_DIR.iterdir() 
        if d.is_dir() and d.name in ALLOWED_LANGS
    ]

LANG_DIRS = get_lang_dirs()
REF_LANG = "de"

# Use 'de' as reference if it exists, otherwise pick the first available
if LANG_DIRS and REF_LANG not in [d.name for d in LANG_DIRS]:
    REF_LANG = LANG_DIRS[0].name

def get_qmd_files(lang_dir):
    """Returns a list of all .qmd files relative to the language directory."""
    return [p.relative_to(lang_dir) for p in lang_dir.rglob("*.qmd")]

def get_all_qmd_files():
    """Returns all .qmd files in the allowed language directories."""
    files = []
    for lang_dir in LANG_DIRS:
        files.extend(lang_dir.rglob("*.qmd"))
    return files

def get_translation_file_pairs():
    """Generates tuples of (relative_file_path, target_lang_name) for parametrization."""
    cases = []
    if not LANG_DIRS or not (DOCS_DIR / REF_LANG).exists():
        return cases
        
    ref_files = get_qmd_files(DOCS_DIR / REF_LANG)
    for lang_dir in LANG_DIRS:
        if lang_dir.name == REF_LANG:
            continue
        for ref_file in ref_files:
            cases.append((ref_file, lang_dir.name))
    return cases

def analyze_qmd(path):
    """Extracts structural metadata, character counts, and YAML keys from a .qmd file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    
    yaml_keys = set()
    body_lines = []
    
    # Parse YAML frontmatter
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                body_lines = lines[i+1:]
                break
            # Match top-level YAML keys (e.g., "title:", "author:")
            match = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
            if match:
                yaml_keys.add(match.group(1))
    else:
        body_lines = lines
        
    # Compute structural statistics
    stats = {
        "total_lines": len(lines),
        "headings": [],
        "headings_missing_ref": [],
        "code_block_delimiters": 0,
        "images": 0,
        "tables": 0,
        "text_chars": 0,
    }
    
    in_code_block = False
    
    for line in body_lines:
        stripped = line.strip()
        
        # Code block boundaries
        if stripped.startswith("```"):
            stats["code_block_delimiters"] += 1
            in_code_block = not in_code_block
            continue
            
        # Parse structural elements ONLY outside of code blocks 
        # (prevents counting python/bash comments as markdown headings)
        if not in_code_block:
            # Count character length of prose (ignoring whitespace padding/empty lines)
            stats["text_chars"] += len(stripped)
            
            if stripped.startswith("#"):
                # Find heading reference ID like {#sec-id} or {.class #sec-id}
                match = re.search(r'\{[^}]*#([A-Za-z0-9_-]+)[^}]*\}\s*$', stripped)
                if match:
                    stats["headings"].append(match.group(1))
                else:
                    stats["headings_missing_ref"].append(stripped)
            elif "![" in stripped or "<img" in stripped:
                stats["images"] += 1
            elif stripped.startswith("|"):
                stats["tables"] += 1
                
    return yaml_keys, stats

def format_uri(g, uri):
    """Attempts to shorten a full URI to a prefix:localname format for readability."""
    if not uri:
        return ""
    try:
        return g.namespace_manager.normalizeUri(uri)
    except Exception:
        return str(uri)

# ==============================================================================
# TESTS
# ==============================================================================

@pytest.fixture(scope="session")
def shacl_graph():
    """Loads the SHACL definition graph for translation completeness verification."""
    g = Graph()
    shacl_path = Path("src/rdf/shapes/model.shacl.ttl")
    if shacl_path.exists():
        g.parse(shacl_path, format="turtle")
    return g

def test_translation_directories_exist():
    """Sanity check to ensure language directories exist."""
    if not LANG_DIRS:
        pytest.skip(f"No allowed language directories {ALLOWED_LANGS} found in docs/")
    assert (DOCS_DIR / REF_LANG).exists(), f"Reference language directory '{REF_LANG}' missing."

@pytest.mark.parametrize("qmd_file", get_all_qmd_files(), ids=lambda p: str(p.relative_to(DOCS_DIR)))
def test_headings_have_references(qmd_file):
    """Ensures every heading in every .qmd file has a reference ID (e.g., {#sec-example})."""
    _, stats = analyze_qmd(qmd_file)
    assert not stats["headings_missing_ref"], (
        f"The following headings in {qmd_file} are missing a reference ID:\n" + 
        "\n".join(stats["headings_missing_ref"])
    )

@pytest.mark.parametrize("lang_dir", [d for d in LANG_DIRS if d.name != REF_LANG], ids=lambda d: d.name)
def test_file_structure_is_identical(lang_dir):
    """Ensures that target language directories contain the exact same .qmd files as the reference."""
    ref_dir = DOCS_DIR / REF_LANG
    
    ref_files = set(get_qmd_files(ref_dir))
    target_files = set(get_qmd_files(lang_dir))
    
    missing = ref_files - target_files
    extra = target_files - ref_files
    
    assert not missing, f"Language '{lang_dir.name}' is missing translated files: {missing}"
    assert not extra, f"Language '{lang_dir.name}' has extra files not present in reference ({REF_LANG}): {extra}"

@pytest.mark.parametrize("rel_path, target_lang", get_translation_file_pairs())
def test_translation_content_matches(rel_path, target_lang):
    """Checks structural parity, YAML key equality, and content length for a translated file."""
    ref_file = DOCS_DIR / REF_LANG / rel_path
    target_file = DOCS_DIR / target_lang / rel_path
    
    # Guard clause to fail gracefully if the file structure test didn't catch the missing file yet
    if not target_file.exists():
        pytest.fail(f"Target file {target_file} does not exist.")
        
    ref_yaml, ref_stats = analyze_qmd(ref_file)
    target_yaml, target_stats = analyze_qmd(target_file)
    
    # 1. Check YAML frontmatter variables
    assert target_yaml == ref_yaml, (
        f"YAML frontmatter keys differ in {target_file}.\n"
        f"Expected {ref_yaml}, but got {target_yaml}"
    )
    
    # 2. Check Line count
    assert target_stats["total_lines"] == ref_stats["total_lines"], (
        f"Total line count differs.\n"
        f"{ref_file}: {ref_stats['total_lines']} lines\n"
        f"{target_file}: {target_stats['total_lines']} lines"
    )
    
    # 3. Check headings alignment (verifies both count AND perfect matching of reference IDs)
    assert target_stats["headings"] == ref_stats["headings"], (
        f"Heading references differ or are out of order.\n"
        f"{ref_file}: {ref_stats['headings']}\n"
        f"{target_file}: {target_stats['headings']}"
    )
    
    # 4. Check code blocks
    assert target_stats["code_block_delimiters"] == ref_stats["code_block_delimiters"], (
        f"Number of code blocks differs.\n"
        f"{ref_file}: {ref_stats['code_block_delimiters']} delimiters\n"
        f"{target_file}: {target_stats['code_block_delimiters']} delimiters"
    )
    
    # 5. Check images count
    assert target_stats["images"] == ref_stats["images"], (
        f"Number of images differs.\n"
        f"{ref_file}: {ref_stats['images']} images\n"
        f"{target_file}: {target_stats['images']} images"
    )
    
    # 6. Check tables count (counts table rows)
    assert target_stats["tables"] == ref_stats["tables"], (
        f"Number of table rows differs.\n"
        f"{ref_file}: {ref_stats['tables']} table rows\n"
        f"{target_file}: {target_stats['tables']} table rows"
    )

    # 7. Check overall text length (Prose character count should be within +/- 25%)
    ref_chars = ref_stats["text_chars"]
    target_chars = target_stats["text_chars"]
    
    # Avoid division by zero and extreme volatility on files that contain almost no text
    if ref_chars > 50: 
        ratio = target_chars / ref_chars
        assert 0.75 <= ratio <= 1.25, (
            f"Translation length anomaly in {target_file}.\n"
            f"Expected roughly {ref_chars} characters, but got {target_chars} "
            f"({(ratio * 100):.1f}% of reference). A translation should be within +/- 25%."
        )

def test_shacl_translations_complete(shacl_graph):
    """
    Ensures that for all localized strings in the SHACL model,
    translations are provided for all languages that have documentation.
    """
    if not LANG_DIRS:
        pytest.skip(f"No allowed language directories {ALLOWED_LANGS} found in docs/")
        
    expected_langs = {d.name for d in LANG_DIRS}
    
    from collections import defaultdict
    lang_map = defaultdict(set)
    
    query = """
        SELECT DISTINCT ?s ?p (LANG(?o) AS ?lang)
        WHERE {
            ?s ?p ?o .
            FILTER(LANG(?o) != "")
        }
    """
    
    for row in shacl_graph.query(query):
        lang = str(row.lang).lower().split('-')[0]
        lang_map[(row.s, row.p)].add(lang)

    errors = []
    
    for (s, p), langs in lang_map.items():
        missing_langs = expected_langs - langs
        if missing_langs:
            errors.append({
                "subject": format_uri(shacl_graph, s),
                "predicate": format_uri(shacl_graph, p),
                "found": ", ".join(sorted(langs)),
                "missing": ", ".join(sorted(missing_langs))
            })

    if errors:
        subj_len = max(len("Subject"), max((len(e["subject"]) for e in errors), default=0))
        pred_len = max(len("Predicate"), max((len(e["predicate"]) for e in errors), default=0))
        found_len = max(len("Found"), max((len(e["found"]) for e in errors), default=0))
        missing_len = max(len("Missing"), max((len(e["missing"]) for e in errors), default=0))

        header = f"| {'Subject'.ljust(subj_len)} | {'Predicate'.ljust(pred_len)} | {'Found'.ljust(found_len)} | {'Missing'.ljust(missing_len)} |"
        separator = f"|-{'-' * subj_len}-|-{'-' * pred_len}-|-{'-' * found_len}-|-{'-' * missing_len}-|"

        table_lines = [
            "Incomplete translations found in the SHACL model.",
            f"Required languages based on docs/ directories: {', '.join(sorted(expected_langs))}",
            "",
            header,
            separator
        ]

        for e in sorted(errors, key=lambda x: (x["subject"], x["predicate"])):
            line = f"| {e['subject'].ljust(subj_len)} | {e['predicate'].ljust(pred_len)} | {e['found'].ljust(found_len)} | {e['missing'].ljust(missing_len)} |"
            table_lines.append(line)

        pytest.fail("\n".join(table_lines))