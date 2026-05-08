import pytest
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