import re
import subprocess
from pathlib import Path
import pytest
from rdflib import Graph

def get_tracked_files():
    """Returns a list of tracked files that might contain prefix definitions."""
    try:
        result = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True)
        files = [f for f in result.stdout.split('\0') if f and f.endswith(('.ttl', '.rq', '.py', '.md', '.qmd'))]
        return [Path(f) for f in files]
        
    except (subprocess.SubprocessError, FileNotFoundError):
        files = []
        for ext in ("*.ttl", "*.rq", "*.py", "*.md", "*.qmd"):
            files.extend(
                p for p in Path(".").rglob(ext)
                if not set(p.parts) & {"venv", "build", ".quarto", ".git"}
            )
        return files

def get_defined_prefixes():
    """Finds all prefix definitions in the repo."""
    prefix_regex = re.compile(r'(?i)(?:@prefix|PREFIX)\s+([a-zA-Z0-9_.-]*):\s*<([^>]+)>')
    file_prefixes = []
    for f in get_tracked_files():
        if not f.exists():
            continue
        try:
            content = f.read_text(encoding="utf-8")
            for match in prefix_regex.finditer(content):
                prefix = match.group(1)
                uri = match.group(2)
                file_prefixes.append((prefix, uri, str(f)))
        except Exception:
            pass
    return file_prefixes

def test_prefix_consistency():
    """
    1. Loads the prefix/qname definitions in src/rdf/prefixes.ttl.
    2. Checks if the same qnames are used consistently throughout the repo.
    """
    prefixes = get_defined_prefixes()
    
    prefix_map = {}
    inconsistencies = []
    
    prefixes_file = Path("src/rdf/prefixes.ttl")
    if prefixes_file.exists():
        g = Graph(bind_namespaces="none")
        g.parse(prefixes_file, format="turtle")
        for prefix, uri in g.namespaces():
            prefix_map[str(prefix)] = str(uri)
            
    for prefix, uri, file_path in prefixes:
        if prefix in prefix_map:
            if prefix_map[prefix] != uri:
                inconsistencies.append(
                    f"Prefix '{prefix}:' is defined as <{uri}> in {file_path}, "
                    f"but expected/previously defined as <{prefix_map[prefix]}>"
                )
        else:
            prefix_map[prefix] = uri
            
    if inconsistencies:
        pytest.fail("Inconsistent prefix definitions found:\n" + "\n".join(inconsistencies))