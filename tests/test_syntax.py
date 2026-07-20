import pytest
from pathlib import Path
from rdflib import Graph

@pytest.mark.parametrize("file_path", list(Path("src/rdf").rglob("*.ttl")), ids=lambda p: str(p))
def test_turtle_syntax(file_path):
    """
    Tests if a given .ttl file contains valid Turtle syntax.
    """
    g = Graph()
    try:
        g.parse(source=file_path, format="turtle")
    except Exception as e:
        pytest.fail(f"Found a syntax error in '{file_path}':\n{e}", pytrace=False)