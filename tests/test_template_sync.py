import json
import urllib.request
import urllib.error
import fnmatch
import warnings
from pathlib import Path
import pytest

REPO = "blw-ofag-ufag/semantic-web-template"
PATTERNS = [
    "tests/*.py",
    "docs/assets/*.xml",
    "docs/assets/*.typ",
    "LICENSE.md",
    ".gitattributes",
    "src/python/utils/*.py",
    "src/rdf/shapes/glossary.shacl.ttl",
    ".github/workflows/ci.yml",
    ".github/CONTRIBUTING.md"
]

def test_sync_with_template(pytestconfig):
    """
    Checks if managed files match the upstream template.
    Aggregates all discrepancies into a single warning to avoid test spam.
    """
    ref = pytestconfig.getoption("--template-ref")
    
    if ref == "latest":
        url = f"https://api.github.com/repos/{REPO}/releases/latest"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'pytest'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                ref = data["tag_name"]
        except urllib.error.HTTPError as e:
            ref = "main" if e.code == 404 else None
        except Exception:
            ref = None

    if not ref:
        pytest.skip("Failed to resolve the template release tag from GitHub.")

    tree_url = f"https://api.github.com/repos/{REPO}/git/trees/{ref}?recursive=1"
    files_to_check = []
    try:
        req = urllib.request.Request(tree_url, headers={'User-Agent': 'pytest'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            for item in data.get("tree", []):
                if item["type"] == "blob":
                    path = item["path"]
                    if any(fnmatch.fnmatchcase(path, p) for p in PATTERNS):
                        # Don't check this script against itself to prevent paradoxes
                        if path != "tests/test_template_sync.py":
                            files_to_check.append(path)
    except Exception as e:
        pytest.skip(f"Could not fetch tree from GitHub API: {e}")

    if not files_to_check:
        pytest.skip("No matching files found in the template repository.")

    discrepancies = []
    
    for path in files_to_check:
        local_path = Path(path)
        
        if not local_path.exists():
            discrepancies.append(f"- Missing: {path}")
            continue
            
        raw_url = f"https://raw.githubusercontent.com/{REPO}/{ref}/{path}"
        try:
            req = urllib.request.Request(raw_url, headers={'User-Agent': 'pytest'})
            with urllib.request.urlopen(req, timeout=10) as response:
                upstream_content = response.read().decode("utf-8")
        except Exception:
            discrepancies.append(f"- Failed to download upstream: {path}")
            continue
            
        local_content = local_path.read_text(encoding="utf-8")
        
        if local_content.replace('\r\n', '\n') != upstream_content.replace('\r\n', '\n'):
            discrepancies.append(f"- Diverged: {path}")

    if discrepancies:
        warning_msg = (
            f"The following files diverge from the upstream template ({ref}).\n"
            "Consider reverting these files or upstreaming your changes to the template repository:\n"
            + "\n".join(discrepancies)
        )
        warnings.warn(warning_msg, UserWarning)