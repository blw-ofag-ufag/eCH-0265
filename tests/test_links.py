import subprocess
import re
from pathlib import Path
import urllib.request
import urllib.error
import pytest

def get_tracked_md_files():
    """Returns a list of .md files tracked by git, falling back to rglob if git fails."""
    try:
        result = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True)
        files = [f for f in result.stdout.split('\0') if f and f.endswith('.md')]
        return [Path(f) for f in files]
        
    except (subprocess.SubprocessError, FileNotFoundError):
        return [
            p for p in Path(".").rglob("*.md")
            if not set(p.parts) & {"venv", "build", ".quarto", ".git"}
        ]

def get_urls():
    """Extract URLs from all tracked Markdown files, ignoring code blocks."""
    url_regex = re.compile(r'\[[^\]]*\]\((https?://[^\)]+)\)')
    url_regex_angle = re.compile(r'<(https?://[^>]+)>')
    
    urls = []
    for md_file in get_tracked_md_files():
        if not md_file.exists():
            continue
            
        content = md_file.read_text(encoding="utf-8")
        content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
        content_no_code = re.sub(r'`[^`]*`', '', content_no_code)

        for match in url_regex.finditer(content_no_code):
            urls.append((str(md_file), match.group(1)))
        for match in url_regex_angle.finditer(content_no_code):
            urls.append((str(md_file), match.group(1)))

    return sorted(list(set(urls)))

@pytest.mark.parametrize("md_file, url", get_urls())
def test_markdown_link(md_file, url):
    """Checks the HTTP status code of referenced external URLs."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    try:
        req.get_method = lambda: 'HEAD'
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as e:
        if e.code in (405, 403, 401):
            try:
                req.get_method = lambda: 'GET'
                urllib.request.urlopen(req, timeout=10)
            except urllib.error.HTTPError as e2:
                if e2.code not in (401, 403):
                    pytest.fail(f"HTTPError {e2.code} for {url} in {md_file}")
            except Exception as e2:
                pytest.fail(f"Failed to fetch {url} in {md_file}: {e2}")
        else:
            pytest.fail(f"HTTPError {e.code} for {url} in {md_file}")
    except Exception as e:
        pytest.fail(f"Failed to fetch {url} in {md_file}: {e}")