import pytest
from rdflib import Graph

def pytest_addoption(parser):
    parser.addoption(
        "--template-ref",
        action="store",
        default="latest",
        help="Tag (e.g., 'v1.2.3') or 'latest' of the template repository to check against."
    )

@pytest.fixture(scope="session")
def final_graph():
    """Loads the fully reasoned and processed graph for testing."""
    g = Graph()
    g.parse("build/rdf/03-processed.ttl", format="turtle")
    return g