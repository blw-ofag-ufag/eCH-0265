import json
import os
import re
import subprocess
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
    "docs/assets/*.lua",
    "docs/assets/*.yml",
    "docs/assets/*.html",
    "docs/assets/*.scss",
    "docs/assets/*.svg",
    "docs/assets/*.csl",
    "LICENSE.md",
    ".gitattributes",
    "src/python/utils/*.py",
    "src/r/utils/*.R",
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


def github_api(url):
    """GET a GitHub API resource as JSON; uses GITHUB_TOKEN when available."""
    headers = {"User-Agent": "pytest", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())


def fetch_labels(repo):
    """Returns the labels of a repository as {name: (description, color)}."""
    labels = {}
    page = 1
    while True:
        batch = github_api(f"https://api.github.com/repos/{repo}/labels?per_page=100&page={page}")
        for label in batch:
            labels[label["name"]] = ((label.get("description") or "").strip(), label["color"].lower())
        if len(batch) < 100:
            return labels
        page += 1


def current_repo():
    """Derives owner/name of this repository from the origin remote, or None."""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return match.group(1) if match else None


def test_labels_match_template():
    """
    Checks that this repository has at least the issue labels of the template
    repository, with the same description and colour (GitHub issue #36).
    Discrepancies are reported as a single warning.
    """
    repo = current_repo()
    if not repo:
        pytest.skip("Could not determine this repository from the git remote.")

    try:
        template_labels = fetch_labels(REPO)
        local_labels = fetch_labels(repo)
    except Exception as e:
        pytest.skip(f"Could not fetch labels from the GitHub API: {e}")

    discrepancies = []
    for name, (description, color) in sorted(template_labels.items()):
        if name not in local_labels:
            discrepancies.append(f"- Missing: '{name}' (#{color}, {description!r})")
            continue
        local_description, local_color = local_labels[name]
        if local_description != description:
            discrepancies.append(f"- Description differs: '{name}' is {local_description!r}, template has {description!r}")
        if local_color != color:
            discrepancies.append(f"- Colour differs: '{name}' is #{local_color}, template has #{color}")

    if discrepancies:
        warnings.warn(
            f"The issue labels of {repo} diverge from the template repository ({REPO}).\n"
            "Create or adjust these labels (Issues > Labels) so that the template's labels are present:\n"
            + "\n".join(discrepancies),
            UserWarning,
        )
