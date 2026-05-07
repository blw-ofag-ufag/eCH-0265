import pytest
from pathlib import Path
from rdflib import Graph

BASE_DIR = Path(__file__).resolve().parent.parent

def _load_graph(*filepaths):
    """Helper to parse one or more TTL files into a single rdflib Graph."""
    g = Graph()
    for path in filepaths:
        if not path.exists():
            pytest.fail(f"Fixture setup failed: Could not find {path}")
        try:
            g.parse(path, format="turtle")
        except Exception as e:
            pytest.fail(f"Fixture setup failed: Syntax error in {path}\n{e}")
    return g

# ==========================================
# SESSION-SCOPED FIXTURES (Loaded only once)
# ==========================================

@pytest.fixture(scope="session")
def core_graph():
    """Returns the core structural ontology graph"""
    return _load_graph(BASE_DIR / "rdf" / "ontology" / "core.ttl")

@pytest.fixture(scope="session")
def cultivation_graph():
    """Returns ONLY the crop taxonomy graph"""
    return _load_graph(BASE_DIR / "rdf" / "ontology" / "cultivationtypes.ttl")

@pytest.fixture(scope="session")
def datamodel_graph():
    """Returns the SHACL shapes graph"""
    return _load_graph(BASE_DIR / "rdf" / "shape" / "data-model.ttl")

@pytest.fixture(scope="session")
def agis_graph():
    """Returns the AGIS data graph"""
    return _load_graph(BASE_DIR / "rdf" / "data" / "agis.ttl")

@pytest.fixture(scope="session")
def srppp_graph():
    """Returns the PSM (srppp) data graph"""
    return _load_graph(BASE_DIR / "rdf" / "data" / "srppp.ttl")

@pytest.fixture(scope="session")
def naebi_graph():
    """Returns the Suisse-Bilanz (naebi) data graph"""
    return _load_graph(BASE_DIR / "rdf" / "data" / "naebi.ttl")