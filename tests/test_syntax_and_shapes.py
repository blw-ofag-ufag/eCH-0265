import pytest
from pathlib import Path
import rdflib
from pyshacl import validate

# Anchor the base directory dynamically to the repository root
BASE_DIR = Path(__file__).resolve().parent.parent

def discover_ttl_files():
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

@pytest.mark.parametrize("filepath", discover_ttl_files(), ids=lambda p: p.name)
def test_turtle_syntax(filepath):
    """
    Instantiates an ephemeral RDF graph and attempts to parse the Turtle file.
    A parsing exception indicates invalid syntax and fails the test.
    """
    graph = rdflib.Graph()
    try:
        graph.parse(str(filepath), format="turtle")
    except Exception as e:
        pytest.fail(f"Syntax validation failed for {filepath.name}\nDetails: {str(e)}")

@pytest.mark.parametrize("data_fixture", [
    "cultivation_graph",
    "agis_graph",
    "srppp_graph",
    "naebi_graph"
])
def test_shacl_compliance(data_fixture, request, datamodel_graph):
    """
    Validates multiple data graphs against the separated SHACL shapes in data-model.ttl.
    """
    data_graph = request.getfixturevalue(data_fixture)

    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=datamodel_graph,
        data_graph_format="turtle",
        shacl_graph_format="turtle",
        inference="rdfs", 
        debug=False
    )

    # Assert and report exactly where it failed
    assert conforms, (
        f"SHACL Validation Failed for {data_fixture}!\n"
        f"--- SHACL Report ---\n{results_text}"
    )