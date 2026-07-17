import pytest
from rdflib import Graph

@pytest.fixture(scope="session")
def final_graph():
    """Loads the fully reasoned and processed graph for testing."""
    g = Graph()
    g.parse("build/rdf/03-processed.ttl", format="turtle")
    return g