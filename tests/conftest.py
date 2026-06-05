import pytest
import json
from pathlib import Path
from rdflib import Graph

BASE_DIR = Path(__file__).resolve().parent.parent

def discover_all_ttl_files():
    """
    Traverses the directory tree from the project root to discover all RDF Turtle files.
    Returns a list of Path objects.
    """
    if not BASE_DIR.exists() or not BASE_DIR.is_dir():
        return []
    return [
        p for p in BASE_DIR.rglob("*.ttl")
        if ".git" not in p.parts and "venv" not in p.parts
    ]

@pytest.fixture(scope="session")
def parsed_ttl_cache():
    """
    Parses every discovered TTL file exactly once per test session.
    Returns a dict mapping the file Path to a tuple of (rdflib.Graph, Exception).
    """
    cache = {}
    for path in discover_all_ttl_files():
        g = Graph()
        try:
            g.parse(str(path), format="turtle")
            cache[path] = (g, None)
        except Exception as e:
            cache[path] = (None, e)
    return cache

def _get_graph_from_cache(cache, filepath):
    """Helper to extract a graph from the cache and fail cleanly if syntax is invalid."""
    if filepath not in cache:
        pytest.fail(f"Fixture setup failed: {filepath.name} was not found in cache.")
    
    g, err = cache[filepath]
    if err:
        pytest.fail(f"Fixture setup failed due to prior syntax error in {filepath.name}: {err}")
    return g

# ==========================================
# SESSION-SCOPED FIXTURES 
# ==========================================

@pytest.fixture(scope="session")
def core_graph(parsed_ttl_cache):
    return _get_graph_from_cache(parsed_ttl_cache, BASE_DIR / "rdf" / "ontology" / "core.ttl")

@pytest.fixture(scope="session")
def cultivation_graph(parsed_ttl_cache):
    return _get_graph_from_cache(parsed_ttl_cache, BASE_DIR / "rdf" / "ontology" / "cultivationtypes.ttl")

@pytest.fixture(scope="session")
def datamodel_graph(parsed_ttl_cache):
    return _get_graph_from_cache(parsed_ttl_cache, BASE_DIR / "rdf" / "shape" / "data-model.ttl")

@pytest.fixture(scope="session")
def agis_graph(parsed_ttl_cache):
    return _get_graph_from_cache(parsed_ttl_cache, BASE_DIR / "rdf" / "data" / "agis.ttl")

@pytest.fixture(scope="session")
def srppp_graph(parsed_ttl_cache):
    return _get_graph_from_cache(parsed_ttl_cache, BASE_DIR / "rdf" / "data" / "srppp.ttl")

@pytest.fixture(scope="session")
def naebi_graph(parsed_ttl_cache):
    return _get_graph_from_cache(parsed_ttl_cache, BASE_DIR / "rdf" / "data" / "naebi.ttl")

import pytest
import json
from pathlib import Path
from rdflib import Graph


# ==========================================
# WARNINGS REPORTING
# ==========================================

WARNING_REPORT_DATA = []

def pytest_configure(config):
    config.warning_report_data = WARNING_REPORT_DATA

def pytest_warning_recorded(warning_message, when, nodeid, location):
    raw_message = str(warning_message.message)
    
    message_lines = [line.strip() for line in raw_message.splitlines() if line.strip()]

    warning_data = {
        "test_node": nodeid, 
        "warning_type": warning_message.category.__name__, 
        "message": message_lines, 
        "file": location[0] if location else "unknown",
        "line": location[1] if location else "unknown"
    }
    
    WARNING_REPORT_DATA.append(warning_data)

def pytest_unconfigure(config):
    if WARNING_REPORT_DATA:
        report_path = "tests/warnings_report.json"
        
        # Ensure the tests directory exists in case it was deleted
        Path("tests").mkdir(exist_ok=True)
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(WARNING_REPORT_DATA, f, indent=4, ensure_ascii=False)
        print(f"\n[+] Generated dedicated warnings report: {report_path}")